"""Durable room state as read by the driver. Pure loading; no selection logic."""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path

PRODUCTIVE: frozenset[str] = frozenset(
    {"negative", "structure", "correction", "verified", "counterexample", "frames"}
)
OUTCOMES: frozenset[str] = PRODUCTIVE | {"nothing", "invalid"}
TURN_ID = re.compile(r"^T(\d+)\b")


@dataclasses.dataclass(frozen=True)
class Target:
    slug: str
    track: str
    priority: int
    title: str
    statement: str
    status: str
    tags: tuple[str, ...]
    raw: dict[str, object]


@dataclasses.dataclass(frozen=True)
class Frame:
    slug: str
    title: str
    statement: str
    shape: tuple[str, ...]
    source: dict[str, object]
    filed_by: str
    applied_to: tuple[dict[str, object], ...]
    superseded_by: str | None


@dataclasses.dataclass(frozen=True)
class TurnRecord:
    turn_id: str
    kind: str
    target: str | None
    frames: tuple[str, ...]
    outcome: str
    refinement: bool
    ledger_line: str | None
    files_changed: tuple[str, ...]
    frames_filed: tuple[str, ...]
    started: str
    seconds: float
    base_commit: str
    exit_reason: str
    invalid_reason: str | None
    brief_digest: str
    template_digest: str
    claim: str | None = None  # adversarial turns: the ledger line under test

    def to_json(self) -> dict[str, object]:
        d = dataclasses.asdict(self)
        for k in ("frames", "files_changed", "frames_filed"):
            d[k] = list(d[k])
        return d


@dataclasses.dataclass(frozen=True)
class State:
    targets: tuple[Target, ...]
    frames: tuple[Frame, ...]
    turns: tuple[TurnRecord, ...]
    ledger_lines: tuple[str, ...]

    def target(self, slug: str) -> Target:
        for t in self.targets:
            if t.slug == slug:
                return t
        raise KeyError(slug)

    def frame(self, slug: str) -> Frame:
        for f in self.frames:
            if f.slug == slug:
                return f
        raise KeyError(slug)


def read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    out: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            obj = json.loads(line)
            if not isinstance(obj, dict):
                raise ValueError(f"{path}: non-object line")
            out.append(obj)
    return out


def append_jsonl(path: Path, record: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=False) + "\n")


def write_pool(root: Path, records: list[dict[str, object]]) -> None:
    text = "".join(json.dumps(r) + "\n" for r in records)
    (root / "pool.jsonl").write_text(text, encoding="utf-8")


def _target(raw: dict[str, object]) -> Target:
    return Target(
        slug=str(raw["slug"]),
        track=str(raw.get("track", "open")),
        priority=int(raw.get("priority", 9)),  # type: ignore[call-overload]
        title=str(raw.get("title", "")),
        statement=str(raw.get("statement", "")),
        status=str(raw.get("status", "open")),
        tags=tuple(str(t) for t in raw.get("tags", [])),  # type: ignore[attr-defined]
        raw=raw,
    )


def _frame(raw: dict[str, object]) -> Frame:
    return Frame(
        slug=str(raw["slug"]),
        title=str(raw["title"]),
        statement=str(raw["statement"]),
        shape=tuple(str(t) for t in raw["shape"]),  # type: ignore[attr-defined]
        source=dict(raw["source"]),  # type: ignore[call-overload]
        filed_by=str(raw.get("filed_by", "")),
        applied_to=tuple(dict(a) for a in raw.get("applied_to", [])),  # type: ignore[attr-defined]
        superseded_by=(None if raw.get("superseded_by") is None else str(raw["superseded_by"])),
    )


SOURCE_KINDS = frozenset({"arxiv", "doi", "oeis", "web", "pool", "own"})


def validate_frame(raw: dict[str, object], existing: set[str]) -> Frame:
    for key in ("slug", "title", "statement", "shape", "source"):
        if key not in raw:
            raise ValueError(f"frame missing {key}")
    slug = str(raw["slug"])
    if slug in existing:
        raise ValueError(f"duplicate frame slug {slug}")
    shape = raw["shape"]
    if not isinstance(shape, list) or not shape:
        raise ValueError("frame shape must be a non-empty list")
    source = raw["source"]
    if not isinstance(source, dict) or source.get("kind") not in SOURCE_KINDS:
        raise ValueError(f"frame source kind must be one of {sorted(SOURCE_KINDS)}")
    if source["kind"] not in ("pool", "own") and not source.get("url"):
        raise ValueError("frame source needs a url")
    return Frame(
        slug=slug,
        title=str(raw["title"]),
        statement=str(raw["statement"]),
        shape=tuple(str(t) for t in shape),
        source=dict(source),
        filed_by=str(raw.get("filed_by", "")),
        applied_to=tuple(),
        superseded_by=None,
    )


def _turn(raw: dict[str, object]) -> TurnRecord:
    return TurnRecord(
        turn_id=str(raw["turn_id"]),
        kind=str(raw["kind"]),
        target=(None if raw.get("target") is None else str(raw["target"])),
        frames=tuple(str(f) for f in raw.get("frames", [])),  # type: ignore[attr-defined]
        outcome=str(raw["outcome"]),
        refinement=bool(raw.get("refinement", False)),
        ledger_line=(None if raw.get("ledger_line") is None else str(raw["ledger_line"])),
        files_changed=tuple(str(f) for f in raw.get("files_changed", [])),  # type: ignore[attr-defined]
        frames_filed=tuple(str(f) for f in raw.get("frames_filed", [])),  # type: ignore[attr-defined]
        started=str(raw.get("started", "")),
        seconds=float(raw.get("seconds", 0.0)),  # type: ignore[arg-type]
        base_commit=str(raw.get("base_commit", "")),
        exit_reason=str(raw.get("exit_reason", "completed")),
        invalid_reason=(None if raw.get("invalid_reason") is None else str(raw["invalid_reason"])),
        brief_digest=str(raw.get("brief_digest", "")),
        template_digest=str(raw.get("template_digest", "")),
        claim=(None if raw.get("claim") is None else str(raw["claim"])),
    )


def load_state(root: Path) -> State:
    targets = tuple(_target(r) for r in read_jsonl(root / "pool.jsonl"))
    frames = tuple(_frame(r) for r in read_jsonl(root / "frames.jsonl"))
    turns = tuple(
        _turn(r) for r in read_jsonl(root / "driver" / "turns.jsonl")
        if "turn_id" in r and "event" not in r
    )
    ledger = root / "ledger.md"
    lines: tuple[str, ...] = ()
    if ledger.exists():
        lines = tuple(
            ln for ln in ledger.read_text(encoding="utf-8").splitlines()
            if TURN_ID.match(ln) or ln.startswith("EXT |")
        )
    return State(targets=targets, frames=frames, turns=turns, ledger_lines=lines)


def next_turn_id(state: State) -> str:
    best = -1
    for line in state.ledger_lines:
        m = TURN_ID.match(line)
        if m:
            best = max(best, int(m.group(1)))
    for t in state.turns:
        m = TURN_ID.match(t.turn_id)
        if m:
            best = max(best, int(m.group(1)))
    return f"T{best + 1}"
