# .timeloop/driver/loop.py
"""The continuous loop: lease, signals, breaker, ceilings, and the CLI."""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import signal
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from driver.brief import render_brief
from driver.config import DriverConfig, load_config
from driver.dispatcher import Brief, apply_stalls, select, unpark
from driver.recorder import CommitFailure, ExamFailure, Hooks, default_hooks, record, snapshot
from driver.runner import run_turn
from driver.state import State, append_jsonl, load_state, read_jsonl
from driver.status import format_status


class LeaseHeld(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _lease_path(root: Path) -> Path:
    return root / "driver" / "lease.json"


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def acquire(root: Path, seed: int, stale_seconds: int) -> None:
    p = _lease_path(root)
    if p.exists():
        L = json.loads(p.read_text(encoding="utf-8"))
        hb = datetime.fromisoformat(str(L["heartbeat"]).replace("Z", "+00:00"))
        age = (datetime.now(UTC) - hb).total_seconds()
        if age < stale_seconds and _alive(int(L["pid"])):
            raise LeaseHeld(
                f"researcher pid {L['pid']} holds the lease (heartbeat {int(age)}s ago)"
            )
        append_jsonl(
            root / "driver" / "turns.jsonl",
            {"event": "lease_expired", "pid": L["pid"], "heartbeat": L["heartbeat"], "at": _now()},
        )
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "started": _now(),
                "seed": seed,
                "heartbeat": _now(),
                "turn_id": None,
            }
        ),
        encoding="utf-8",
    )


def heartbeat(root: Path, brief: Brief | None) -> None:
    p = _lease_path(root)
    L = json.loads(p.read_text(encoding="utf-8"))
    L["heartbeat"] = _now()
    if brief is not None:
        L.update(
            {
                "turn_id": brief.turn_id,
                "kind": brief.kind,
                "target": brief.target,
                "frames": list(brief.frames),
            }
        )
    p.write_text(json.dumps(L), encoding="utf-8")


def release(root: Path) -> None:
    p = _lease_path(root)
    if p.exists():
        p.unlink()


def _inject_next(state: State, root: Path) -> State:
    idx = root / "index.md"
    nexts: dict[str, str] = {}
    if idx.exists():
        for line in idx.read_text(encoding="utf-8").splitlines():
            if line.startswith("- ") and "| next: " in line:
                slug = line[2:].split(" |")[0]
                nxt = line.split("| next: ", 1)[1].strip()
                if nxt and not nxt.startswith("(no"):
                    nexts[slug] = nxt
    targets = tuple(
        dataclasses.replace(t, raw={**t.raw, "_next": nexts[t.slug]}) if t.slug in nexts else t
        for t in state.targets
    )
    return dataclasses.replace(state, targets=targets)


class _Signals:
    """First SIGINT/SIGTERM: finish the current turn, then stop. Second: kill it.

    The child runs in its own session, so a terminal Ctrl-C reaches only the
    loop; the turn keeps running until the loop decides otherwise."""

    def __init__(self) -> None:
        self.count = 0

    def install(self) -> None:
        signal.signal(signal.SIGINT, self._handle)
        signal.signal(signal.SIGTERM, self._handle)

    def _handle(self, signum: int, frame: object) -> None:
        self.count += 1

    def requested(self) -> bool:
        return self.count >= 1

    def hard(self) -> bool:
        return self.count >= 2


def run_loop(
    repo_root: Path,
    config: DriverConfig,
    max_turns: int | None,
    max_hours: float | None,
    hooks: Hooks | None = None,
) -> int:
    root = repo_root / ".timeloop"
    turns_log = root / "driver" / "turns.jsonl"
    hooks = hooks or default_hooks(repo_root)
    signals = _Signals()
    signals.install()
    try:
        acquire(root, config.seed, config.stale_lease_seconds)
    except LeaseHeld as e:
        print(str(e), file=sys.stderr)
        return 2
    started = time.monotonic()
    consecutive_invalid = 0
    done = 0
    turn_index = (
        len([t for t in read_jsonl(turns_log) if "turn_id" in t and "event" not in t]) + 1
    )
    code = 0

    def halt(reason: str) -> None:
        event = {"event": "halt", "reason": reason, "turn_index": turn_index, "at": _now()}
        append_jsonl(turns_log, event)

    try:
        while True:
            if max_turns is not None and done >= max_turns:
                break
            if max_hours is not None and (time.monotonic() - started) / 3600 >= max_hours:
                halt("max_hours")
                break
            if signals.requested():
                event = {"event": "interrupted", "turn_index": turn_index, "at": _now()}
                append_jsonl(turns_log, event)
                break
            pre = snapshot(repo_root)   # before the dispatcher writes anything
            state = _inject_next(apply_stalls(root, load_state(root), config, turn_index), root)
            brief = select(state, config, turn_index)
            if brief.revive and brief.target:
                unpark(root, brief.target)
            text = render_brief(brief, state, config, root)
            (root / "driver" / "briefs").mkdir(parents=True, exist_ok=True)
            (root / "driver" / "briefs" / f"{brief.turn_id}.md").write_text(text, encoding="utf-8")
            heartbeat(root, brief)
            before = snapshot(repo_root)   # what the model is answerable for
            ledger_path = root / "ledger.md"
            ledger_before = ledger_path.read_text(encoding="utf-8") if ledger_path.exists() else ""
            started_iso = _now()
            frames = " ".join(brief.frames)
            head = f"[{started_iso}] {brief.turn_id} {brief.kind} {brief.target or '-'} {frames}"
            print(head, flush=True)
            run = run_turn(
                text, config, repo_root, config.turn_timeout_seconds, interrupt=signals.hard
            )
            try:
                rec = record(
                    repo_root, brief, text, run, pre, before, ledger_before, started_iso, hooks
                )
            except ExamFailure as e:
                halt(f"exam: {e}")
                code = 3
                break
            except CommitFailure as e:
                halt(f"commit: {e}")
                code = 6
                break
            extra = f" ({rec.invalid_reason})" if rec.invalid_reason else ""
            print(f"  -> {rec.outcome}{extra} in {rec.seconds:.0f}s", flush=True)
            done += 1
            turn_index += 1
            heartbeat(root, None)
            if run.error in ("usage_limit", "auth", "missing_executable"):
                # Retrying cannot help any of these: the window is spent, the
                # session is unauthenticated, or the binary simply isn't there.
                halt(run.error)
                code = 4
                break
            if run.exit_reason == "interrupted":
                append_jsonl(
                    turns_log,
                    {"event": "interrupted", "turn_index": turn_index, "at": _now(), "hard": True},
                )
                code = 130
                break
            consecutive_invalid = consecutive_invalid + 1 if rec.outcome == "invalid" else 0
            if consecutive_invalid >= config.breaker_threshold:
                halt("breaker")
                code = 5
                break
    finally:
        release(root)
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="research")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run_p = sub.add_parser("run")
    run_p.add_argument("--max-turns", type=int, default=None)
    run_p.add_argument("--max-hours", type=float, default=None)
    run_p.add_argument("--config", type=Path, default=None)
    run_p.add_argument(
        "--no-hooks", action="store_true", help="tests only: skip lint/exam/reap/index"
    )
    sub.add_parser("status")
    sub.add_parser("stop")
    args = parser.parse_args(argv)
    repo_root = Path.cwd()
    root = repo_root / ".timeloop"
    if args.cmd == "status":
        print(format_status(root))
        return 0
    if args.cmd == "stop":
        p = _lease_path(root)
        if not p.exists():
            print("no lease; nothing to stop")
            return 1
        pid = int(json.loads(p.read_text())["pid"])
        os.kill(pid, signal.SIGTERM)
        print(f"sent SIGTERM to pid {pid}; it will finish or abort the current turn and exit")
        return 0
    config = load_config(args.config or root / "driver" / "config.json")
    hooks = None
    if args.no_hooks:
        hooks = Hooks(lint=lambda: [], exam=lambda: True, reap=lambda: None, index=lambda: None)
    return run_loop(repo_root, config, args.max_turns, args.max_hours, hooks)


if __name__ == "__main__":
    sys.exit(main())
