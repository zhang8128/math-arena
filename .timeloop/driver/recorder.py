# .timeloop/driver/recorder.py
"""Validate a turn against what it actually changed, then log and commit it.

The working tree is routinely dirty with human work. The recorder therefore
acts only on the delta between the git status before the turn and after it.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import subprocess
from collections.abc import Callable
from pathlib import Path

from driver.brief import ALLOWED_WRITES, sha256, template_digest
from driver.dispatcher import Brief
from driver.runner import RunResult
from driver.state import PRODUCTIVE, TurnRecord, append_jsonl, read_jsonl, validate_frame

FORAGE_KINDS = frozenset({"forage-target", "forage-frontier"})


class ExamFailure(RuntimeError):
    """The blind exam failed after this turn; later verdicts cannot be trusted."""


class CommitFailure(RuntimeError):
    """A turn's git add or commit operation failed."""


@dataclasses.dataclass(frozen=True)
class Hooks:
    lint: Callable[[], list[str]]
    exam: Callable[[], bool]
    reap: Callable[[], None]
    index: Callable[[], None]


def _run(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=repo_root, capture_output=True, text=True, check=False)


def default_hooks(repo_root: Path) -> Hooks:
    tl = repo_root / ".timeloop"

    def lint() -> list[str]:
        p = _run(repo_root, str(tl / "bin" / "lint"), "--report")
        if p.returncode != 0:
            return [f"lint harness failed (exit {p.returncode}): {p.stderr.strip()[:200]}"]
        if not p.stdout.strip():
            return []
        msg = json.loads(p.stdout).get("systemMessage", "")
        return [msg] if msg else []

    def exam() -> bool:
        p = _run(
            repo_root, "uv", "run", "--frozen", "--with", "sympy",
            str(tl / "bin" / "exam"), "--report",
        )
        if p.returncode != 0:
            return False
        return not p.stdout.strip()

    def reap() -> None:
        _run(repo_root, str(tl / "bin" / "reap"), "--kill")

    def index() -> None:
        _run(repo_root, str(tl / "bin" / "lint"), "--index")

    return Hooks(lint=lint, exam=exam, reap=reap, index=index)


def snapshot(repo_root: Path) -> dict[str, str]:
    """Every path git reports as changed, mapped to a content hash.

    Status codes are not enough: a file that was already modified before the
    turn and is modified again during it has the same code both times."""
    p = _run(repo_root, "git", "status", "--porcelain", "--untracked-files=all", "-z")
    out: dict[str, str] = {}
    for entry in p.stdout.split("\0"):
        if len(entry) < 4:
            continue
        path = entry[3:]
        if " -> " in path:
            path = path.split(" -> ")[-1]
        f = repo_root / path
        if f.is_file():
            out[path] = hashlib.sha256(f.read_bytes()).hexdigest()
        else:
            out[path] = "<deleted>"
    return out


def delta(before: dict[str, str], after: dict[str, str]) -> set[str]:
    return {p for p in set(before) | set(after) if before.get(p) != after.get(p)}


def is_allowed(path: str) -> bool:
    if path.startswith("publication/"):
        return False
    return any(path == a or (a.endswith("/") and path.startswith(a)) for a in ALLOWED_WRITES)


DRIVER_OWNED_PREFIXES = (".timeloop/driver/results/", ".timeloop/driver/briefs/")
DRIVER_OWNED_FILES = (".timeloop/driver/turns.jsonl",)


def is_driver_owned(path: str) -> bool:
    """Paths the dispatcher and recorder write themselves.

    Deliberately narrow: a turn that edits the driver's own code must be
    reverted like any other disallowed write, not waved through by prefix.
    """
    return path in DRIVER_OWNED_FILES or path.startswith(DRIVER_OWNED_PREFIXES)


def revert(repo_root: Path, paths: set[str]) -> None:
    if not paths:
        return
    tracked = set(
        _run(repo_root, "git", "ls-files", "-z", "--", *sorted(paths)).stdout.split("\0")
    ) - {""}
    for p in sorted(paths):
        if p in tracked:
            _run(repo_root, "git", "checkout", "--", p)
        else:
            f = repo_root / p
            if f.is_file():
                f.unlink()


def validate(
    brief: Brief,
    run: RunResult,
    delta_paths: set[str],
    ledger_before: str,
    ledger_after: str,
) -> tuple[str, str | None, bool]:
    if run.exit_reason != "completed":
        return ("invalid", run.exit_reason, False)
    if run.structured is None:
        return ("invalid", run.error or "schema", False)
    s = run.structured
    outcome = str(s.get("outcome"))
    refinement = bool(s.get("refinement", False))
    if outcome == "frames" and brief.kind not in FORAGE_KINDS:
        return ("invalid", "frames_outside_forage", refinement)
    if outcome == "verified" and brief.kind != "adversarial":
        return ("invalid", "verified_outside_adversarial", refinement)
    claimed = {str(p) for p in s.get("files_changed", [])}  # type: ignore[attr-defined]
    turn_delta = {p for p in delta_paths if is_allowed(p) and not is_driver_owned(p)}
    if claimed != turn_delta:
        return ("invalid", "files_mismatch", refinement)
    if outcome in PRODUCTIVE:
        line = s.get("ledger_line")
        prefix = f"{brief.turn_id} | "
        new_text = (
            ledger_after[len(ledger_before):]
            if ledger_after.startswith(ledger_before)
            else ledger_after
        )
        if not isinstance(line, str) or not line.startswith(prefix) or prefix not in new_text:
            return ("invalid", "no_ledger_line", refinement)
    return (outcome, None, refinement)


def _file_frames(repo_root: Path, brief: Brief, run: RunResult) -> tuple[list[str], list[str]]:
    filed: list[str] = []
    rejected: list[str] = []
    if run.structured is None:
        return (filed, rejected)
    path = repo_root / ".timeloop" / "frames.jsonl"
    existing = {str(r["slug"]) for r in read_jsonl(path)}
    for raw in run.structured.get("frames_filed", []):  # type: ignore[attr-defined]
        try:
            frame = validate_frame(dict(raw), existing)
        except ValueError as e:
            rejected.append(f"rejected frame {dict(raw).get('slug')}: {e}")
            continue
        rec = dataclasses.asdict(frame)
        rec.update({"filed_by": brief.turn_id, "applied_to": [], "superseded_by": None})
        rec["shape"] = list(frame.shape)
        append_jsonl(path, rec)
        existing.add(frame.slug)
        filed.append(frame.slug)
    return (filed, rejected)


def _apply_to_frames(repo_root: Path, brief: Brief, outcome: str) -> None:
    if brief.kind not in ("attack", "combine") or not brief.frames:
        return
    path = repo_root / ".timeloop" / "frames.jsonl"
    records = read_jsonl(path)
    for r in records:
        if r["slug"] in brief.frames:
            apps = list(r.get("applied_to", []))  # type: ignore[call-overload]
            apps.append({"target": brief.target, "turn": brief.turn_id, "outcome": outcome})
            r["applied_to"] = apps
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")


STAGEABLE_EXTRA = (
    ".timeloop/frames.jsonl", ".timeloop/index.md", ".timeloop/pool.jsonl",
    ".timeloop/exam/results.jsonl",
)


def _stageable(path: str) -> bool:
    return is_allowed(path) or is_driver_owned(path) or path in STAGEABLE_EXTRA


def _restore_log(log: Path, prior_text: str | None) -> None:
    """Undo an append_jsonl call. `None` means the log did not exist yet."""
    if prior_text is None:
        if log.exists():
            log.unlink()
    else:
        log.write_text(prior_text, encoding="utf-8")


def record(
    repo_root: Path,
    brief: Brief,
    brief_text: str,
    run: RunResult,
    pre_status: dict[str, str],
    before_status: dict[str, str],
    ledger_before: str,
    started_iso: str,
    hooks: Hooks,
) -> TurnRecord:
    tl = repo_root / ".timeloop"
    log = tl / "driver" / "turns.jsonl"
    base_commit = _run(repo_root, "git", "rev-parse", "HEAD").stdout.strip()
    after = snapshot(repo_root)
    model_delta = delta(before_status, after)
    disallowed = {p for p in model_delta if not is_allowed(p) and not is_driver_owned(p)}
    revert(repo_root, disallowed)
    ledger_path = tl / "ledger.md"
    ledger_after = ledger_path.read_text(encoding="utf-8") if ledger_path.exists() else ""
    outcome, reason, refinement = validate(brief, run, model_delta, ledger_before, ledger_after)
    if disallowed:
        # An undeclared write outside the allowed set was reverted above; the
        # turn does not get a clean outcome just because the model omitted it
        # from files_changed. See spec's outcome table: a disallowed write is
        # `invalid`, not whatever the model otherwise reported.
        outcome, reason = "invalid", "disallowed_write"
    filed: list[str] = []
    if outcome != "invalid":
        filed, rejected = _file_frames(repo_root, brief, run)
        if rejected:
            append_jsonl(
                log, {"event": "frames_rejected", "turn": brief.turn_id, "reasons": rejected}
            )
        if outcome == "frames" and not filed:
            outcome, reason = "invalid", "no_frames_filed"
    if outcome != "invalid":
        problems = hooks.lint()
        if problems:
            outcome, reason = "invalid", f"lint: {problems[0]}"
    _apply_to_frames(repo_root, brief, outcome)
    exam_ok = hooks.exam()
    hooks.reap()
    hooks.index()
    pool_rel = ".timeloop/pool.jsonl"
    if pool_rel in model_delta:
        try:
            pool_ok = all("slug" in r for r in read_jsonl(tl / "pool.jsonl"))
        except ValueError:
            # read_jsonl raises ValueError (json.JSONDecodeError is a subclass)
            # on a malformed line or a non-object line.
            pool_ok = False
        if not pool_ok:
            _run(repo_root, "git", "checkout", "--", pool_rel)
            outcome, reason = "invalid", "pool_invalid"
    (tl / "driver" / "results").mkdir(parents=True, exist_ok=True)
    (tl / "driver" / "results" / f"{brief.turn_id}.json").write_text(
        json.dumps(dataclasses.asdict(run), indent=1), encoding="utf-8"
    )
    (tl / "driver" / "briefs").mkdir(parents=True, exist_ok=True)
    brief_path = tl / "driver" / "briefs" / f"{brief.turn_id}.md"
    if not brief_path.exists():
        brief_path.write_text(brief_text, encoding="utf-8")
    s = run.structured or {}
    rec = TurnRecord(
        turn_id=brief.turn_id,
        kind=brief.kind,
        target=brief.target,
        frames=brief.frames,
        outcome=outcome,
        refinement=refinement,
        ledger_line=(
            str(s["ledger_line"]) if outcome in PRODUCTIVE and s.get("ledger_line") else None
        ),
        files_changed=tuple(sorted(
            p for p in model_delta if is_allowed(p) and not is_driver_owned(p)
        )),
        frames_filed=tuple(filed),
        started=started_iso,
        seconds=run.seconds,
        base_commit=base_commit,
        exit_reason=run.exit_reason,
        invalid_reason=reason,
        brief_digest=sha256(brief_text),
        template_digest=template_digest(tl),
        claim=brief.claim,
    )
    # The record is written to the log now (so it lands in the same commit as
    # the rest of the turn's files, per the design), but only durably: if
    # either git operation below fails, the append is rolled back so a
    # CommitFailure can never leave a logged turn with no matching commit.
    log_before = log.read_text(encoding="utf-8") if log.exists() else None
    append_jsonl(log, rec.to_json())
    to_stage = sorted(p for p in delta(pre_status, snapshot(repo_root)) if _stageable(p))
    added = _run(repo_root, "git", "add", "--", *to_stage)
    if added.returncode != 0:
        _restore_log(log, log_before)
        raise CommitFailure(
            f"git add failed for {brief.turn_id}: {added.stderr.strip()[:400]}"
        )
    committed = _run(
        repo_root, "git", "commit", "-q", "-m",
        f"turn: {brief.turn_id} {brief.kind} {brief.target or '-'} {outcome}",
    )
    if committed.returncode != 0:
        _restore_log(log, log_before)
        raise CommitFailure(
            f"git commit failed for {brief.turn_id}: {committed.stderr.strip()[:400]}"
        )
    if not exam_ok:
        raise ExamFailure(f"blind exam failed after {brief.turn_id}")
    return rec
