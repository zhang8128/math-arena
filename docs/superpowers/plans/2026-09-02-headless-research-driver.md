# Headless Research Driver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One command, `bin/research`, runs time-loop-room turns autonomously through headless Claude Code, with a deterministic dispatcher that rotates angles before targets, forages for ideas online, combines frames, and never grinds one thing.

**Architecture:** A pure seeded dispatcher reads the pool, the frames registry, the turn log, and the ledger tail, and writes a one-page brief. A runner executes the brief with `claude -p` under a hard timeout and a JSON result schema. A recorder validates the result against the git delta the turn produced, reverts disallowed writes, appends the turn log, runs lint and exam, and commits. A thin loop adds lease, signals, circuit breaker, and ceilings.

**Tech Stack:** Python 3.13 standard library only (`json`, `subprocess`, `signal`, `random`, `string`, `dataclasses`, `pathlib`, `hashlib`), pytest 8.4 via `uv run --frozen`, ruff, mypy `--strict` scoped to the new package, bash for `bin/research`, git 2.50, Claude Code CLI 2.1.258 in print mode, `caffeinate`.

**Spec:** `docs/superpowers/specs/2026-09-02-headless-research-driver-design.md`

## Global Constraints

- Never stage, revert, or rewrite pre-existing uncommitted changes. The working tree currently carries 25 dirty paths including `publication/` and `.timeloop/runs/t3*.py`. Commit only the files your task names.
- All driver code lives in `.timeloop/driver/`; standard library only; production `src/mathloop` is not touched.
- The runner invokes `claude -p --output-format json --json-schema ... --permission-mode bypassPermissions --allowedTools Bash Read Write Edit Glob Grep WebSearch WebFetch --no-session-persistence`. It never passes `--bare`, which skips OAuth and breaks authentication.
- Turn timeout is 1,800 seconds, enforced by the runner with SIGTERM then SIGKILL on the child's process group.
- Rotation cap 3, stall window 3, cooldown 20 turns, exploration floor 0.2, patrol every 25th turn, adversarial every 10th turn, combine share 0.15, forage-target share 0.10, forage-frontier share 0.10, breaker threshold 5 consecutive invalid turns, stale lease after 2,700 seconds.
- Allowed write set for a turn: `.timeloop/ledger.md`, `.timeloop/notebook/`, `.timeloop/pool.jsonl`, `.timeloop/lib/`, `.timeloop/runs/`, `.timeloop/tests/`, `.timeloop/lean/arena/`, `.timeloop/driver/results/`. Everything else in the turn's delta is reverted; `publication/` always.
- Turn ids continue the ledger's `T<n>` series. A productive turn's ledger line must begin with `<turn_id> | `.
- Outcome classes: `negative`, `structure`, `correction`, `verified`, `counterexample`, `frames` are productive; `nothing` and `invalid` are not. Only the recorder assigns `invalid`.
- Commit message format: `turn: <turn_id> <kind> <target> <outcome>`.
- Tests run with `uv run --frozen python -m pytest .timeloop/tests/<file> -q -p no:cacheprovider`. Lint with `uv run --frozen ruff check .timeloop/driver .timeloop/tests/test_driver_*.py`. Types with `uv run --frozen mypy --strict .timeloop/driver`.
- Use TDD for every behavior change; commit after each task.

---

## File Structure

New:

- `.timeloop/driver/__init__.py` — empty marker.
- `.timeloop/driver/config.py` — `DriverConfig` dataclass and `load_config`.
- `.timeloop/driver/state.py` — record dataclasses, `load_state`, `next_turn_id`, JSONL helpers, `PRODUCTIVE`.
- `.timeloop/driver/index.py` — `build_index` used by `bin/lint --index`.
- `.timeloop/driver/dispatcher.py` — eligibility, stall detection, parking, `select`.
- `.timeloop/driver/brief.py` — `RESULT_SCHEMA`, `KIND_RULES`, `render_brief`.
- `.timeloop/driver/runner.py` — `build_command`, `parse_output`, `run_turn`.
- `.timeloop/driver/recorder.py` — git delta, revert, validation, frames append, lint/exam/reap, commit.
- `.timeloop/driver/status.py` — `yield_report`, `format_status`.
- `.timeloop/driver/loop.py` — lease, signals, breaker, ceilings, CLI `run|status|stop`.
- `.timeloop/driver/templates/brief.md`, `.timeloop/driver/templates/system.md`.
- `.timeloop/driver/config.json` — defaults written out for visibility.
- `.timeloop/frames.jsonl` — seeded registry.
- `.timeloop/index.md` — generated.
- `bin/research` — operator entry.
- `.timeloop/tests/test_driver_config.py`, `test_driver_state.py`, `test_driver_index.py`, `test_driver_dispatcher.py`, `test_driver_brief.py`, `test_driver_runner.py`, `test_driver_recorder.py`, `test_driver_status.py`, `test_driver_loop.py`.
- `.timeloop/tests/fixtures/fake_claude` — executable stub.

Modified:

- `.timeloop/pool.jsonl` — `tags` on every record.
- `.timeloop/bin/lint` — `check_pool_tags`, `--index` mode.
- `.timeloop/exam/items.py` — two driver items.
- `.timeloop/README.md` — driver section.

Every test file for the driver starts with:

```python
from __future__ import annotations

import sys
from pathlib import Path

TIMELOOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TIMELOOP))
```

so `from driver import ...` resolves.

---

### Task 1: Configuration and state loading

**Files:**
- Create: `.timeloop/driver/__init__.py`
- Create: `.timeloop/driver/config.py`
- Create: `.timeloop/driver/state.py`
- Create: `.timeloop/driver/config.json`
- Test: `.timeloop/tests/test_driver_config.py`
- Test: `.timeloop/tests/test_driver_state.py`

**Interfaces:**
- Produces: `DriverConfig` frozen dataclass with fields `seed: int = 1`, `combine_share: float = 0.15`, `forage_target_share: float = 0.10`, `forage_frontier_share: float = 0.10`, `rotation_cap: int = 3`, `stall_window: int = 3`, `cooldown_turns: int = 20`, `exploration_floor: float = 0.2`, `patrol_period: int = 25`, `adversarial_period: int = 10`, `arxiv_categories: tuple[str, ...] = ("math.NT", "math.CO", "cs.LO")`, `turn_timeout_seconds: int = 1800`, `model: str | None = None`, `effort: str | None = None`, `allowed_tools: tuple[str, ...] = ("Bash", "Read", "Write", "Edit", "Glob", "Grep", "WebSearch", "WebFetch")`, `breaker_threshold: int = 5`, `stale_lease_seconds: int = 2700`, `claude_executable: str = "claude"`.
- Produces: `load_config(path: Path) -> DriverConfig` — missing file returns defaults; unknown keys raise `ValueError`.
- Produces: `Target`, `Frame`, `TurnRecord` (last field `claim: str | None = None`, the ledger line an adversarial turn tested), `State` frozen dataclasses; `PRODUCTIVE: frozenset[str]`; `load_state(root: Path) -> State`; `next_turn_id(state: State) -> str`; `read_jsonl(path: Path) -> list[dict[str, object]]`; `append_jsonl(path: Path, record: dict[str, object]) -> None`; `write_pool(root: Path, records: list[dict[str, object]]) -> None`.
- `root` is always the `.timeloop` directory, never the repository root.

- [ ] **Step 1: Write the failing config tests**

```python
# .timeloop/tests/test_driver_config.py
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TIMELOOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TIMELOOP))

from driver.config import DriverConfig, load_config


def test_defaults_match_spec() -> None:
    c = DriverConfig()
    assert (c.rotation_cap, c.stall_window, c.cooldown_turns) == (3, 3, 20)
    assert (c.patrol_period, c.adversarial_period) == (25, 10)
    assert c.combine_share + c.forage_target_share + c.forage_frontier_share == pytest.approx(0.35)
    assert c.turn_timeout_seconds == 1800
    assert c.breaker_threshold == 5
    assert c.stale_lease_seconds == 2700
    assert "WebSearch" in c.allowed_tools


def test_missing_file_returns_defaults(tmp_path: Path) -> None:
    assert load_config(tmp_path / "absent.json") == DriverConfig()


def test_file_overrides_and_rejects_unknown_keys(tmp_path: Path) -> None:
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"seed": 7, "arxiv_categories": ["math.NT"]}))
    c = load_config(p)
    assert c.seed == 7 and c.arxiv_categories == ("math.NT",)
    p.write_text(json.dumps({"bogus": 1}))
    with pytest.raises(ValueError, match="bogus"):
        load_config(p)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --frozen python -m pytest .timeloop/tests/test_driver_config.py -q -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError: No module named 'driver'`

- [ ] **Step 3: Write config.py and the package marker**

```python
# .timeloop/driver/__init__.py
"""Headless research driver for the time loop room. Standard library only."""
```

```python
# .timeloop/driver/config.py
"""Driver configuration. Every value has a default; config.json overrides."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path


@dataclasses.dataclass(frozen=True)
class DriverConfig:
    seed: int = 1
    combine_share: float = 0.15
    forage_target_share: float = 0.10
    forage_frontier_share: float = 0.10
    rotation_cap: int = 3
    stall_window: int = 3
    cooldown_turns: int = 20
    exploration_floor: float = 0.2
    patrol_period: int = 25
    adversarial_period: int = 10
    arxiv_categories: tuple[str, ...] = ("math.NT", "math.CO", "cs.LO")
    turn_timeout_seconds: int = 1800
    model: str | None = None
    effort: str | None = None
    allowed_tools: tuple[str, ...] = (
        "Bash", "Read", "Write", "Edit", "Glob", "Grep", "WebSearch", "WebFetch",
    )
    breaker_threshold: int = 5
    stale_lease_seconds: int = 2700
    claude_executable: str = "claude"


_TUPLE_FIELDS = {"arxiv_categories", "allowed_tools"}


def load_config(path: Path) -> DriverConfig:
    if not path.exists():
        return DriverConfig()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: config must be a JSON object")
    known = {f.name for f in dataclasses.fields(DriverConfig)}
    unknown = sorted(set(raw) - known)
    if unknown:
        raise ValueError(f"{path}: unknown config keys {unknown}")
    values = {k: tuple(v) if k in _TUPLE_FIELDS else v for k, v in raw.items()}
    return DriverConfig(**values)
```

- [ ] **Step 4: Run config tests**

Run: `uv run --frozen python -m pytest .timeloop/tests/test_driver_config.py -q -p no:cacheprovider`
Expected: 3 passed

- [ ] **Step 5: Write the failing state tests**

```python
# .timeloop/tests/test_driver_state.py
from __future__ import annotations

import json
import sys
from pathlib import Path

TIMELOOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TIMELOOP))

from driver.state import (
    PRODUCTIVE,
    Frame,
    State,
    Target,
    TurnRecord,
    append_jsonl,
    load_state,
    next_turn_id,
    read_jsonl,
    write_pool,
)


def make_room(tmp_path: Path) -> Path:
    root = tmp_path / ".timeloop"
    (root / "driver").mkdir(parents=True)
    (root / "notebook").mkdir()
    (root / "pool.jsonl").write_text(
        json.dumps({"slug": "a", "track": "open", "priority": 1, "title": "A",
                    "statement": "s", "status": "open", "tags": ["x"]}) + "\n"
        + json.dumps({"slug": "b", "track": "forge", "priority": 2, "title": "B",
                      "statement": "s", "status": "parked", "tags": ["y"],
                      "cooldown_until": 30}) + "\n"
    )
    (root / "frames.jsonl").write_text(
        json.dumps({"slug": "f1", "title": "F1", "statement": "p", "shape": ["x"],
                    "source": {"kind": "pool"}, "filed_by": "seed",
                    "applied_to": [], "superseded_by": None}) + "\n"
    )
    (root / "ledger.md").write_text(
        "# Ledger\n\nT7 | a | nothing | tried\n\nEXT | a | deposit | x\n\nT12 | b | negative | ruled out n<10\n"
    )
    return root


def test_load_state_reads_all_files(tmp_path: Path) -> None:
    root = make_room(tmp_path)
    (root / "driver" / "turns.jsonl").write_text(
        json.dumps({"turn_id": "T13", "kind": "attack", "target": "a", "frames": ["f1"],
                    "outcome": "nothing", "refinement": False, "ledger_line": None,
                    "files_changed": [], "frames_filed": [], "started": "2026-09-02T00:00:00Z",
                    "seconds": 1.0, "base_commit": "abc", "exit_reason": "completed",
                    "invalid_reason": None, "brief_digest": "d", "template_digest": "t"}) + "\n"
        + json.dumps({"event": "halt", "reason": "breaker"}) + "\n"
    )
    s = load_state(root)
    assert [t.slug for t in s.targets] == ["a", "b"]
    assert s.targets[1].status == "parked" and s.targets[1].raw["cooldown_until"] == 30
    assert s.frames[0].shape == ("x",)
    assert [t.turn_id for t in s.turns] == ["T13"]
    assert s.ledger_lines[-1].startswith("T12 |")


def test_next_turn_id_takes_max_of_ledger_and_log(tmp_path: Path) -> None:
    root = make_room(tmp_path)
    assert next_turn_id(load_state(root)) == "T13"
    append_jsonl(root / "driver" / "turns.jsonl", {"turn_id": "T40", "kind": "attack",
        "target": "a", "frames": [], "outcome": "nothing", "refinement": False,
        "ledger_line": None, "files_changed": [], "frames_filed": [], "started": "",
        "seconds": 0.0, "base_commit": "", "exit_reason": "completed",
        "invalid_reason": None, "brief_digest": "", "template_digest": ""})
    assert next_turn_id(load_state(root)) == "T41"


def test_productive_set_and_pool_roundtrip(tmp_path: Path) -> None:
    root = make_room(tmp_path)
    assert PRODUCTIVE == {"negative", "structure", "correction", "verified", "counterexample", "frames"}
    records = read_jsonl(root / "pool.jsonl")
    records[0]["status"] = "parked"
    write_pool(root, records)
    assert read_jsonl(root / "pool.jsonl")[0]["status"] == "parked"
    assert read_jsonl(root / "pool.jsonl")[0]["slug"] == "a"
```

- [ ] **Step 6: Run to verify failure**

Run: `uv run --frozen python -m pytest .timeloop/tests/test_driver_state.py -q -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError: No module named 'driver.state'`

- [ ] **Step 7: Write state.py**

```python
# .timeloop/driver/state.py
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
        tags=tuple(str(t) for t in raw.get("tags", [])),  # type: ignore[union-attr]
        raw=raw,
    )


def _frame(raw: dict[str, object]) -> Frame:
    return Frame(
        slug=str(raw["slug"]),
        title=str(raw["title"]),
        statement=str(raw["statement"]),
        shape=tuple(str(t) for t in raw["shape"]),  # type: ignore[union-attr]
        source=dict(raw["source"]),  # type: ignore[call-overload]
        filed_by=str(raw.get("filed_by", "")),
        applied_to=tuple(dict(a) for a in raw.get("applied_to", [])),  # type: ignore[union-attr]
        superseded_by=(None if raw.get("superseded_by") is None else str(raw["superseded_by"])),
    )


def _turn(raw: dict[str, object]) -> TurnRecord:
    return TurnRecord(
        turn_id=str(raw["turn_id"]),
        kind=str(raw["kind"]),
        target=(None if raw.get("target") is None else str(raw["target"])),
        frames=tuple(str(f) for f in raw.get("frames", [])),  # type: ignore[union-attr]
        outcome=str(raw["outcome"]),
        refinement=bool(raw.get("refinement", False)),
        ledger_line=(None if raw.get("ledger_line") is None else str(raw["ledger_line"])),
        files_changed=tuple(str(f) for f in raw.get("files_changed", [])),  # type: ignore[union-attr]
        frames_filed=tuple(str(f) for f in raw.get("frames_filed", [])),  # type: ignore[union-attr]
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
        _turn(r) for r in read_jsonl(root / "driver" / "turns.jsonl") if "turn_id" in r
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
```

- [ ] **Step 8: Run state tests**

Run: `uv run --frozen python -m pytest .timeloop/tests/test_driver_state.py .timeloop/tests/test_driver_config.py -q -p no:cacheprovider`
Expected: 6 passed

- [ ] **Step 9: Write config.json with the defaults and lint**

```json
{
  "seed": 1,
  "combine_share": 0.15,
  "forage_target_share": 0.10,
  "forage_frontier_share": 0.10,
  "rotation_cap": 3,
  "stall_window": 3,
  "cooldown_turns": 20,
  "exploration_floor": 0.2,
  "patrol_period": 25,
  "adversarial_period": 10,
  "arxiv_categories": ["math.NT", "math.CO", "cs.LO"],
  "turn_timeout_seconds": 1800,
  "model": null,
  "effort": null,
  "allowed_tools": ["Bash", "Read", "Write", "Edit", "Glob", "Grep", "WebSearch", "WebFetch"],
  "breaker_threshold": 5,
  "stale_lease_seconds": 2700,
  "claude_executable": "claude"
}
```

Run: `uv run --frozen ruff check .timeloop/driver .timeloop/tests/test_driver_config.py .timeloop/tests/test_driver_state.py && uv run --frozen mypy --strict .timeloop/driver`
Expected: no findings. If mypy objects to the `type: ignore` comments as unused, delete the ones it names.

- [ ] **Step 10: Commit**

```bash
git add .timeloop/driver/__init__.py .timeloop/driver/config.py .timeloop/driver/state.py .timeloop/driver/config.json .timeloop/tests/test_driver_config.py .timeloop/tests/test_driver_state.py
git commit -m "feat: load driver config and room state"
```

---

### Task 2: Pool tags, lint check, and the generated index

**Files:**
- Modify: `.timeloop/pool.jsonl` (add `tags` to all 18 records)
- Create: `.timeloop/driver/index.py`
- Modify: `.timeloop/bin/lint` (add `check_pool_tags` to `CHECKS`; add `--index` mode)
- Create: `.timeloop/index.md` (generated)
- Test: `.timeloop/tests/test_driver_index.py`

**Interfaces:**
- Consumes: `read_jsonl` from Task 1.
- Produces: `build_index(root: Path) -> str` returning the full markdown text; `index_line(slug: str, notebook_text: str | None, pool_status: str, statement: str) -> str`; `last_section(text: str, name: str) -> str | None` returning the first non-empty line after the last `##+ NAME` header.

- [ ] **Step 1: Add tags to the pool by hand**

Edit `.timeloop/pool.jsonl`, adding a `"tags": [...]` key to each record after `"track"`. Use exactly these:

| slug | tags |
|---|---|
| rabinowitsch-families | quadratic-forms, prime-runs, class-numbers |
| idoneal-numbers | quadratic-forms, class-numbers, finiteness |
| lehmer-totient | totient, divisibility, size-bounds |
| giuga | congruences, carmichael, size-bounds |
| brocard | diophantine, factorials, squares |
| singmaster | binomials, diophantine, multiplicity |
| forge-prime-runs | prime-runs, polynomials, forge |
| forge-digit-dynamics | digit-dynamics, fixed-points, congruences |
| forge-aliquot | aliquot, divisor-sums, dynamics |
| forge-recurrence-primality | recurrences, primes, density |
| kaprekar-maps | digit-dynamics, fixed-points, bases |
| multiplicative-persistence | digit-dynamics, bases, bounds |
| lychrel-bases | digit-dynamics, reverse-and-add, csp, finite-automata, bases |
| forge-oeis-thin | oeis, forge, thin-evidence |
| erdos-straus | unit-fractions, diophantine, residues |
| forge-digit-products | digit-dynamics, fixed-points, bases |
| rh-turing-golf | turing-machines, riemann, state-count |
| li-tail-structure | riemann, zeta-zeros, tables |

Do it with a script so the other fields are untouched:

```python
# run once from the repo root, then delete
import json
from pathlib import Path
TAGS = {
    "rabinowitsch-families": ["quadratic-forms", "prime-runs", "class-numbers"],
    "idoneal-numbers": ["quadratic-forms", "class-numbers", "finiteness"],
    "lehmer-totient": ["totient", "divisibility", "size-bounds"],
    "giuga": ["congruences", "carmichael", "size-bounds"],
    "brocard": ["diophantine", "factorials", "squares"],
    "singmaster": ["binomials", "diophantine", "multiplicity"],
    "forge-prime-runs": ["prime-runs", "polynomials", "forge"],
    "forge-digit-dynamics": ["digit-dynamics", "fixed-points", "congruences"],
    "forge-aliquot": ["aliquot", "divisor-sums", "dynamics"],
    "forge-recurrence-primality": ["recurrences", "primes", "density"],
    "kaprekar-maps": ["digit-dynamics", "fixed-points", "bases"],
    "multiplicative-persistence": ["digit-dynamics", "bases", "bounds"],
    "lychrel-bases": ["digit-dynamics", "reverse-and-add", "csp", "finite-automata", "bases"],
    "forge-oeis-thin": ["oeis", "forge", "thin-evidence"],
    "erdos-straus": ["unit-fractions", "diophantine", "residues"],
    "forge-digit-products": ["digit-dynamics", "fixed-points", "bases"],
    "rh-turing-golf": ["turing-machines", "riemann", "state-count"],
    "li-tail-structure": ["riemann", "zeta-zeros", "tables"],
}
p = Path(".timeloop/pool.jsonl")
out = []
for line in p.read_text().splitlines():
    if not line.strip():
        continue
    r = json.loads(line)
    new = {}
    for k, v in r.items():
        new[k] = v
        if k == "track":
            new["tags"] = TAGS[r["slug"]]
    out.append(json.dumps(new))
p.write_text("\n".join(out) + "\n")
```

Verify: `python3 -c "import json; rows=[json.loads(l) for l in open('.timeloop/pool.jsonl') if l.strip()]; assert all('tags' in r for r in rows); print(len(rows))"` prints `18`.

- [ ] **Step 2: Write the failing index tests**

```python
# .timeloop/tests/test_driver_index.py
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

TIMELOOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TIMELOOP))

from driver.index import build_index, index_line, last_section

NOTEBOOK = """# x

## STATUS
open

## RULED OUT
- nothing below 10^6

## T9 STATUS — later round
### STATUS
parked, wall reached

### RULED OUT
all residues mod 9

### NEXT
try cubics
"""


def test_last_section_takes_the_last_header() -> None:
    assert last_section(NOTEBOOK, "STATUS") == "parked, wall reached"
    assert last_section(NOTEBOOK, "RULED OUT") == "all residues mod 9"
    assert last_section(NOTEBOOK, "NEXT") == "try cubics"
    assert last_section(NOTEBOOK, "COST") is None


def test_index_line_falls_back_to_pool() -> None:
    line = index_line("slug", None, "open", "a long statement " * 20)
    assert line.startswith("- slug | open | ")
    assert len(line) < 400


def test_build_index_covers_every_pool_target(tmp_path: Path) -> None:
    root = tmp_path / ".timeloop"
    (root / "notebook").mkdir(parents=True)
    (root / "pool.jsonl").write_text(
        json.dumps({"slug": "a", "status": "open", "statement": "s", "tags": ["x"]}) + "\n"
        + json.dumps({"slug": "b", "status": "open", "statement": "t", "tags": ["y"]}) + "\n"
    )
    (root / "notebook" / "a.md").write_text(NOTEBOOK)
    text = build_index(root)
    assert "- a | parked, wall reached | ruled out: all residues mod 9 | next: try cubics" in text
    assert "- b | open | ruled out: (no notebook) | next: t" in text


def test_lint_index_mode_writes_file_and_flags_untagged(tmp_path: Path) -> None:
    root = TIMELOOP
    out = subprocess.run(
        [sys.executable, str(root / "bin" / "lint"), "--index"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "wrote" in out
    assert (root / "index.md").exists()
    assert "lychrel-bases" in (root / "index.md").read_text()
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run --frozen python -m pytest .timeloop/tests/test_driver_index.py -q -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError: No module named 'driver.index'`

- [ ] **Step 4: Write index.py**

```python
# .timeloop/driver/index.py
"""One line per target so a turn can orient without opening notebooks."""

from __future__ import annotations

import re
from pathlib import Path

from driver.state import read_jsonl

MAX = 160


def last_section(text: str, name: str) -> str | None:
    pattern = re.compile(rf"^#{{2,}}\s*{re.escape(name)}\s*$", re.MULTILINE)
    starts = [m.end() for m in pattern.finditer(text)]
    if not starts:
        return None
    body = text[starts[-1]:]
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("#"):
            return None
        if s:
            return s[:MAX]
    return None


def _clip(s: str) -> str:
    return s if len(s) <= MAX else s[: MAX - 1] + "…"


def index_line(slug: str, notebook_text: str | None, pool_status: str, statement: str) -> str:
    if notebook_text is None:
        return f"- {slug} | {pool_status} | ruled out: (no notebook) | next: {_clip(statement)}"
    status = last_section(notebook_text, "STATUS") or pool_status
    ruled = last_section(notebook_text, "RULED OUT") or "(none recorded)"
    nxt = last_section(notebook_text, "NEXT") or "(none recorded)"
    return f"- {slug} | {status} | ruled out: {ruled} | next: {nxt}"


def build_index(root: Path) -> str:
    lines = ["# Target index", "", "Generated by `bin/lint --index`. Do not edit.", ""]
    for r in read_jsonl(root / "pool.jsonl"):
        slug = str(r["slug"])
        nb = root / "notebook" / f"{slug}.md"
        text = nb.read_text(encoding="utf-8", errors="ignore") if nb.exists() else None
        lines.append(index_line(slug, text, str(r.get("status", "open")), str(r.get("statement", ""))))
    return "\n".join(lines) + "\n"
```

- [ ] **Step 5: Extend bin/lint**

Add after the `check_ledger_agrees` function and before `CHECKS`:

```python
def check_pool_tags() -> list[str]:
    """Every pool record needs shape tags so the driver can match frames to it.

    Descends from: the frames registry, whose eligibility rule is tag overlap.
    An untagged target is invisible to every frame except general ones."""
    out = []
    pool = ROOT / "pool.jsonl"
    if not pool.exists():
        return ["pool.jsonl missing"]
    for line in pool.read_text(errors="ignore").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if not r.get("tags"):
            out.append(f"pool.jsonl: target '{r.get('slug')}' has no tags")
    return out
```

Register it: `CHECKS = [("notebook schema", check_notebooks), ("ledger agrees with notebooks", check_ledger_agrees), ("pool tags", check_pool_tags)]`.

Add at the top of `main()`:

```python
    if len(sys.argv) > 1 and sys.argv[1] == "--index":
        sys.path.insert(0, str(ROOT))
        from driver.index import build_index  # noqa: PLC0415
        text = build_index(ROOT)
        (ROOT / "index.md").write_text(text)
        print(f"wrote {ROOT / 'index.md'} ({text.count(chr(10)) - 4} targets)")
        return 0
```

- [ ] **Step 6: Run the tests and generate the index**

Run: `uv run --frozen python -m pytest .timeloop/tests/test_driver_index.py -q -p no:cacheprovider && .timeloop/bin/lint && .timeloop/bin/lint --index && head -8 .timeloop/index.md`
Expected: 4 passed; `arena lint: clean`; `wrote ... (18 targets)`; the index shows one line per target.

- [ ] **Step 7: Commit**

```bash
git add .timeloop/pool.jsonl .timeloop/driver/index.py .timeloop/bin/lint .timeloop/index.md .timeloop/tests/test_driver_index.py
git commit -m "feat: tag pool targets and generate the target index"
```

---

### Task 3: Seed the frames registry

**Files:**
- Create: `.timeloop/frames.jsonl`
- Modify: `.timeloop/driver/state.py` (add `validate_frame`)
- Test: `.timeloop/tests/test_driver_state.py` (append tests)

**Interfaces:**
- Produces: `validate_frame(raw: dict[str, object], existing: set[str]) -> Frame` raising `ValueError` for a missing field, a non-`pool`/`own` source without a URL, or a duplicate slug. Fields the model supplies: `slug`, `title`, `statement`, `shape`, `source`. The recorder fills `filed_by`, `applied_to`, `superseded_by`.

- [ ] **Step 1: Write the failing validation tests**

Append to `.timeloop/tests/test_driver_state.py`:

```python
import pytest

from driver.state import validate_frame


def test_validate_frame_requires_url_outside_pool_and_own() -> None:
    base = {"slug": "s", "title": "t", "statement": "p", "shape": ["x"]}
    ok = validate_frame({**base, "source": {"kind": "arxiv", "id": "1", "url": "https://arxiv.org/abs/1"}}, set())
    assert ok.slug == "s" and ok.filed_by == ""
    validate_frame({**base, "source": {"kind": "own"}}, set())
    with pytest.raises(ValueError, match="url"):
        validate_frame({**base, "source": {"kind": "web"}}, set())
    with pytest.raises(ValueError, match="duplicate"):
        validate_frame({**base, "source": {"kind": "pool"}}, {"s"})
    with pytest.raises(ValueError, match="shape"):
        validate_frame({**base, "shape": [], "source": {"kind": "pool"}}, set())


def test_seeded_registry_loads_and_has_general_frames() -> None:
    root = Path(__file__).resolve().parents[1]
    s = load_state(root)
    assert len(s.frames) >= 12
    assert any("*" in f.shape for f in s.frames)
    assert len({f.slug for f in s.frames}) == len(s.frames)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --frozen python -m pytest .timeloop/tests/test_driver_state.py -q -p no:cacheprovider`
Expected: FAIL with `ImportError: cannot import name 'validate_frame'`

- [ ] **Step 3: Add validate_frame to state.py**

```python
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
```

- [ ] **Step 4: Write the seeded registry**

Create `.timeloop/frames.jsonl` with one JSON object per line. The first nine come from README "what the first six targets actually forged"; the rest from the lychrel work and the EXT deposits. Write them exactly:

```json
{"slug": "tabulate-the-right-invariant", "title": "Tabulate the derived invariant beside the raw parameter", "statement": "Before searching, compute the invariant the theory says controls the phenomenon (discriminant, class number, modulus) and tabulate it beside the raw parameter. The answer is often invisible until the two columns sit together.", "shape": ["*"], "source": {"kind": "pool"}, "filed_by": "seed", "applied_to": [{"target": "rabinowitsch-families", "turn": "T0", "outcome": "structure"}], "superseded_by": null}
{"slug": "reduce-to-decidable-family", "title": "Reduce to a family with a provable bound so results are theorems", "statement": "Find a bound beyond which the object cannot occur, then enumerate exhaustively below it. Results become theorems rather than samples.", "shape": ["*"], "source": {"kind": "pool"}, "filed_by": "seed", "applied_to": [{"target": "forge-digit-dynamics", "turn": "T3", "outcome": "structure"}], "superseded_by": null}
{"slug": "group-by-derived-invariant", "title": "Group counts by a derived invariant, not the raw parameter", "statement": "When counts look noisy in the raw parameter, group by the invariant that the mechanism predicts (a gcd, a modulus, a residue class) and check whether the noise collapses.", "shape": ["*"], "source": {"kind": "pool"}, "filed_by": "seed", "applied_to": [{"target": "forge-digit-dynamics", "turn": "T5", "outcome": "structure"}], "superseded_by": null}
{"slug": "state-space-collapse", "title": "Exploit state-space collapse: multiset or sorted form instead of integer", "statement": "If the map is invariant under a symmetry (digit permutation, reversal), enumerate orbits of the quotient rather than raw integers. Cycle structure becomes finite and checkable.", "shape": ["digit-dynamics", "dynamics", "fixed-points"], "source": {"kind": "pool"}, "filed_by": "seed", "applied_to": [{"target": "kaprekar-maps", "turn": "T11", "outcome": "structure"}], "superseded_by": null}
{"slug": "sanity-check-known-value", "title": "Reproduce a known value before trusting a method", "statement": "Run the method on an input with a published answer first. A method that cannot reproduce the known value produces nothing usable on the unknown one.", "shape": ["*"], "source": {"kind": "pool"}, "filed_by": "seed", "applied_to": [], "superseded_by": null}
{"slug": "argmax-vs-ceiling", "title": "Check the argmax against the search ceiling", "statement": "A maximiser pressed against the search bound is not a record; it is the bound. Report the ceiling, extend it, and only then report a maximum.", "shape": ["*"], "source": {"kind": "pool"}, "filed_by": "seed", "applied_to": [{"target": "lehmer-totient", "turn": "T7", "outcome": "correction"}], "superseded_by": null}
{"slug": "image-of-the-map", "title": "Reduce a search to the image of the map", "statement": "Instead of searching inputs, characterise the image of the map and search there. Fixed points of a digit map are solutions of an equation over the image, which is far smaller.", "shape": ["digit-dynamics", "dynamics"], "source": {"kind": "pool"}, "filed_by": "seed", "applied_to": [{"target": "forge-digit-dynamics", "turn": "T3", "outcome": "structure"}], "superseded_by": null}
{"slug": "sharper-subquestion", "title": "Reduce a conjecture to a sharper sub-question and attack the intersection", "statement": "Find the conjunction of two known conditions a counterexample must satisfy and attack the intersection directly, rather than filtering one set by the other.", "shape": ["*"], "source": {"kind": "pool"}, "filed_by": "seed", "applied_to": [{"target": "giuga", "turn": "T8", "outcome": "structure"}], "superseded_by": null}
{"slug": "congruence-obstruction", "title": "Look for a congruence obstruction when a size bound stops improving", "statement": "Reciprocal and size bounds saturate quickly. The next lever is a congruence the object must satisfy that no candidate can, found by computing the object modulo small primes.", "shape": ["congruences", "divisibility", "size-bounds", "carmichael", "totient"], "source": {"kind": "pool"}, "filed_by": "seed", "applied_to": [{"target": "giuga", "turn": "T8", "outcome": "negative"}], "superseded_by": null}
{"slug": "carry-transducer-radial-frontier", "title": "Treat reverse-and-add as a finite carry transducer and eliminate radially", "statement": "Model each column as a bounded integer equation with carry variables, process opposite columns together from the outside in, and keep only the live interface. Bounded interface width makes exact elimination cheap and produces a replayable certificate.", "shape": ["reverse-and-add", "csp", "finite-automata", "digit-dynamics"], "source": {"kind": "pool"}, "filed_by": "seed", "applied_to": [{"target": "lychrel-bases", "turn": "T26", "outcome": "negative"}], "superseded_by": null}
{"slug": "exact-countermodel-core", "title": "Search for a minimal unsatisfiable core by exact countermodels", "statement": "Delete one constraint at a time, solve exactly, and keep the deletions that stay unsatisfiable. The surviving core is the obstruction; single-deletion satisfiability also proves it is the unique minimal one.", "shape": ["csp", "reverse-and-add"], "source": {"kind": "pool"}, "filed_by": "seed", "applied_to": [{"target": "lychrel-bases", "turn": "T27", "outcome": "structure"}], "superseded_by": null}
{"slug": "interface-perturbation-scan", "title": "Perturb one interface of a fixed topology and re-solve", "statement": "Move exactly one block boundary by a bounded number of columns, regenerate the finite system, and solve each variant exactly. Classifies a neighbourhood of the topology as obstructed or not.", "shape": ["reverse-and-add", "csp", "bases"], "source": {"kind": "pool"}, "filed_by": "seed", "applied_to": [{"target": "lychrel-bases", "turn": "T25", "outcome": "negative"}], "superseded_by": null}
{"slug": "affine-lift-obstruction", "title": "Test whether a construction lifts affinely to other bases", "statement": "Map each fixed digit d of a base-b construction to d or d plus the base difference, keep carries fresh, and solve the resulting system in the target base. Infeasibility at n=0 rules out the whole affine family.", "shape": ["reverse-and-add", "bases"], "source": {"kind": "pool"}, "filed_by": "seed", "applied_to": [{"target": "lychrel-bases", "turn": "T22", "outcome": "negative"}], "superseded_by": null}
{"slug": "lp-farkas-dual", "title": "Ask the LP relaxation for a Farkas certificate before trusting an integral obstruction", "statement": "Relax the integer system to an LP with elastic slacks. A zero-violation LP optimum proves no linear certificate exists and the obstruction is intrinsically integral, which tells a proof-format search which rules it must use.", "shape": ["csp", "integer-programming"], "source": {"kind": "pool"}, "filed_by": "seed", "applied_to": [{"target": "lychrel-bases", "turn": "EXT", "outcome": "structure"}], "superseded_by": null}
{"slug": "treewidth-elimination-order", "title": "Certify a small induced width per layer to explain why elimination is cheap", "statement": "Build the primal graph of each layer, derive an elimination order, and replay it to get a checkable upper bound on treewidth. Explains tractability without inferring it from solver behaviour.", "shape": ["csp", "finite-automata"], "source": {"kind": "pool"}, "filed_by": "seed", "applied_to": [{"target": "lychrel-bases", "turn": "T36", "outcome": "structure"}], "superseded_by": null}
```

- [ ] **Step 5: Run tests and lint**

Run: `uv run --frozen python -m pytest .timeloop/tests/test_driver_state.py -q -p no:cacheprovider && uv run --frozen ruff check .timeloop/driver && uv run --frozen mypy --strict .timeloop/driver`
Expected: 5 passed; clean.

- [ ] **Step 6: Commit**

```bash
git add .timeloop/frames.jsonl .timeloop/driver/state.py .timeloop/tests/test_driver_state.py
git commit -m "feat: seed the frames registry"
```

---

### Task 4: Dispatcher rules — history, stall, eligibility, parking

**Files:**
- Create: `.timeloop/driver/dispatcher.py`
- Test: `.timeloop/tests/test_driver_dispatcher.py`

**Interfaces:**
- Consumes: `State`, `Target`, `Frame`, `TurnRecord`, `PRODUCTIVE`, `read_jsonl`, `write_pool` from Task 1; `DriverConfig` from Task 1.
- Produces: `ATTACK_KINDS = frozenset({"attack", "combine"})`; `target_turns(state, slug) -> list[TurnRecord]` (attack/combine only, chronological); `tail_run(state) -> tuple[str | None, int]` (target of the last attack/combine turn and the length of its consecutive run at the tail); `stall_reason(state, slug, config) -> str | None`; `frames_seen(state, slug) -> set[str]`; `eligible_frames(state, target) -> list[Frame]` (sorted by slug, excludes superseded frames); `productive_frame_slugs(state) -> set[str]`; `apply_stalls(root, state, config, turn_index) -> State` (parks stalled open targets by rewriting `pool.jsonl` and returns reloaded state); `unpark(root, slug) -> None`.

- [ ] **Step 1: Write the failing tests**

```python
# .timeloop/tests/test_driver_dispatcher.py
from __future__ import annotations

import json
import sys
from pathlib import Path

TIMELOOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TIMELOOP))

from driver.config import DriverConfig
from driver.dispatcher import (
    apply_stalls,
    eligible_frames,
    frames_seen,
    productive_frame_slugs,
    stall_reason,
    tail_run,
    target_turns,
    unpark,
)
from driver.state import load_state, read_jsonl


def turn(tid: str, kind: str, target: str | None, frames: list[str], outcome: str,
         refinement: bool = False) -> dict[str, object]:
    return {"turn_id": tid, "kind": kind, "target": target, "frames": frames,
            "outcome": outcome, "refinement": refinement, "ledger_line": None,
            "files_changed": [], "frames_filed": [], "started": "", "seconds": 0.0,
            "base_commit": "", "exit_reason": "completed", "invalid_reason": None,
            "brief_digest": "", "template_digest": ""}


def room(tmp_path: Path, turns: list[dict[str, object]]) -> Path:
    root = tmp_path / ".timeloop"
    (root / "driver").mkdir(parents=True)
    (root / "notebook").mkdir()
    pool = [
        {"slug": "a", "track": "open", "tags": ["x", "y"], "priority": 1, "title": "A", "statement": "s", "status": "open"},
        {"slug": "b", "track": "open", "tags": ["z"], "priority": 2, "title": "B", "statement": "s", "status": "open"},
    ]
    (root / "pool.jsonl").write_text("".join(json.dumps(p) + "\n" for p in pool))
    frames = [
        {"slug": "fx", "title": "", "statement": "", "shape": ["x"], "source": {"kind": "pool"}, "filed_by": "seed", "applied_to": [{"target": "b", "turn": "T1", "outcome": "negative"}], "superseded_by": None},
        {"slug": "fy", "title": "", "statement": "", "shape": ["y"], "source": {"kind": "pool"}, "filed_by": "seed", "applied_to": [], "superseded_by": None},
        {"slug": "fg", "title": "", "statement": "", "shape": ["*"], "source": {"kind": "pool"}, "filed_by": "seed", "applied_to": [], "superseded_by": None},
        {"slug": "fold", "title": "", "statement": "", "shape": ["x"], "source": {"kind": "pool"}, "filed_by": "seed", "applied_to": [], "superseded_by": "fx"},
    ]
    (root / "frames.jsonl").write_text("".join(json.dumps(f) + "\n" for f in frames))
    (root / "ledger.md").write_text("T0 | a | nothing | start\n")
    (root / "driver" / "turns.jsonl").write_text("".join(json.dumps(t) + "\n" for t in turns))
    return root


def test_history_helpers(tmp_path: Path) -> None:
    root = room(tmp_path, [
        turn("T1", "attack", "a", ["fx"], "nothing"),
        turn("T2", "forage-target", "a", [], "frames"),
        turn("T3", "combine", "a", ["fx", "fy"], "negative"),
        turn("T4", "attack", "b", ["fg"], "nothing"),
        turn("T5", "attack", "b", ["fg"], "nothing"),
    ])
    s = load_state(root)
    assert [t.turn_id for t in target_turns(s, "a")] == ["T1", "T3"]
    assert tail_run(s) == ("b", 2)
    assert frames_seen(s, "a") == {"fx", "fy"}
    assert [f.slug for f in eligible_frames(s, s.target("a"))] == ["fg", "fx", "fy"]
    assert productive_frame_slugs(s) == {"fx"}


def test_stall_reasons(tmp_path: Path) -> None:
    cfg = DriverConfig()
    root = room(tmp_path, [
        turn("T1", "attack", "a", ["fx"], "nothing"),
        turn("T2", "patrol", None, [], "nothing"),
        turn("T3", "attack", "a", ["fy"], "invalid"),
        turn("T4", "attack", "a", ["fg"], "nothing"),
    ])
    assert stall_reason(load_state(root), "a", cfg) == "3 consecutive non-productive turns: T1,T3,T4"
    root2 = room(tmp_path / "r2", [
        turn("T1", "attack", "a", ["fx"], "negative", True),
        turn("T2", "attack", "a", ["fy"], "negative", True),
        turn("T3", "combine", "a", ["fx", "fy"], "negative", True),
    ])
    assert stall_reason(load_state(root2), "a", cfg) == "3 consecutive refinements: T1,T2,T3"
    root3 = room(tmp_path / "r3", [
        turn("T1", "attack", "a", ["fx"], "nothing"),
        turn("T2", "attack", "a", ["fy"], "negative"),
        turn("T3", "attack", "a", ["fg"], "nothing"),
    ])
    assert stall_reason(load_state(root3), "a", cfg) is None


def test_apply_stalls_parks_and_unpark_revives(tmp_path: Path) -> None:
    cfg = DriverConfig()
    root = room(tmp_path, [
        turn("T1", "attack", "a", ["fx"], "nothing"),
        turn("T2", "attack", "a", ["fy"], "nothing"),
        turn("T3", "attack", "a", ["fg"], "nothing"),
    ])
    s = apply_stalls(root, load_state(root), cfg, turn_index=4)
    a = s.target("a")
    assert a.status == "parked"
    assert a.raw["parked_turns"] == ["T1", "T2", "T3"]
    assert a.raw["cooldown_until"] == 24
    assert a.raw["parked_reason"].startswith("3 consecutive non-productive")
    # idempotent: a parked target is not re-parked
    s2 = apply_stalls(root, s, cfg, turn_index=5)
    assert s2.target("a").raw["cooldown_until"] == 24
    unpark(root, "a")
    rec = [r for r in read_jsonl(root / "pool.jsonl") if r["slug"] == "a"][0]
    assert rec["status"] == "open" and "cooldown_until" not in rec
    assert rec["parked_reason"].startswith("3 consecutive")  # history kept
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --frozen python -m pytest .timeloop/tests/test_driver_dispatcher.py -q -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError: No module named 'driver.dispatcher'`

- [ ] **Step 3: Write dispatcher.py (rules only; `select` comes in Task 5)**

```python
# .timeloop/driver/dispatcher.py
"""Selection rules. Pure functions of state, config, and turn index.

The sudoku rule lives here: change angle before target, change target
before grinding. Nothing in this module runs a model or touches the network.
"""

from __future__ import annotations

from pathlib import Path

from driver.config import DriverConfig
from driver.state import (
    PRODUCTIVE,
    Frame,
    State,
    Target,
    TurnRecord,
    load_state,
    read_jsonl,
    write_pool,
)

ATTACK_KINDS: frozenset[str] = frozenset({"attack", "combine"})


def target_turns(state: State, slug: str) -> list[TurnRecord]:
    return [t for t in state.turns if t.kind in ATTACK_KINDS and t.target == slug]


def tail_run(state: State) -> tuple[str | None, int]:
    attacks = [t for t in state.turns if t.kind in ATTACK_KINDS]
    if not attacks:
        return (None, 0)
    last = attacks[-1].target
    n = 0
    for t in reversed(attacks):
        if t.target != last:
            break
        n += 1
    return (last, n)


def stall_reason(state: State, slug: str, config: DriverConfig) -> str | None:
    recent = target_turns(state, slug)[-config.stall_window:]
    if len(recent) < config.stall_window:
        return None
    ids = ",".join(t.turn_id for t in recent)
    if all(t.outcome not in PRODUCTIVE for t in recent):
        return f"{config.stall_window} consecutive non-productive turns: {ids}"
    if all(t.outcome in PRODUCTIVE and t.refinement for t in recent):
        return f"{config.stall_window} consecutive refinements: {ids}"
    return None


def frames_seen(state: State, slug: str) -> set[str]:
    seen: set[str] = set()
    for t in target_turns(state, slug):
        seen.update(t.frames)
    return seen


def eligible_frames(state: State, target: Target) -> list[Frame]:
    tags = set(target.tags)
    out = [
        f for f in state.frames
        if f.superseded_by is None and ("*" in f.shape or tags & set(f.shape))
    ]
    return sorted(out, key=lambda f: f.slug)


def productive_frame_slugs(state: State) -> set[str]:
    return {
        f.slug for f in state.frames
        if any(str(a.get("outcome")) in PRODUCTIVE for a in f.applied_to)
    }


def apply_stalls(root: Path, state: State, config: DriverConfig, turn_index: int) -> State:
    records = read_jsonl(root / "pool.jsonl")
    changed = False
    for r in records:
        slug = str(r["slug"])
        if r.get("status") != "open":
            continue
        reason = stall_reason(state, slug, config)
        if reason is None:
            continue
        recent = target_turns(state, slug)[-config.stall_window:]
        r["status"] = "parked"
        r["parked_reason"] = reason
        r["parked_turns"] = [t.turn_id for t in recent]
        r["cooldown_until"] = turn_index + config.cooldown_turns
        changed = True
    if changed:
        write_pool(root, records)
        return load_state(root)
    return state


def unpark(root: Path, slug: str) -> None:
    records = read_jsonl(root / "pool.jsonl")
    for r in records:
        if r["slug"] == slug:
            r["status"] = "open"
            r.pop("cooldown_until", None)
    write_pool(root, records)
```

- [ ] **Step 4: Run tests, lint, types**

Run: `uv run --frozen python -m pytest .timeloop/tests/test_driver_dispatcher.py -q -p no:cacheprovider && uv run --frozen ruff check .timeloop/driver .timeloop/tests/test_driver_dispatcher.py && uv run --frozen mypy --strict .timeloop/driver`
Expected: 3 passed; clean.

- [ ] **Step 5: Commit**

```bash
git add .timeloop/driver/dispatcher.py .timeloop/tests/test_driver_dispatcher.py
git commit -m "feat: dispatcher history, stall, eligibility, and parking rules"
```

---

### Task 5: Dispatcher selection

**Files:**
- Modify: `.timeloop/driver/dispatcher.py`
- Test: `.timeloop/tests/test_driver_dispatcher.py` (append)

**Interfaces:**
- Consumes: everything from Task 4; `next_turn_id` from Task 1.
- Produces: `Brief` frozen dataclass with `turn_id: str`, `kind: str`, `target: str | None`, `frames: tuple[str, ...]`, `category: str | None`, `claim: str | None`, `revive: bool`, `reason: str`; `select(state: State, config: DriverConfig, turn_index: int) -> Brief`; `rng_for(config, turn_index) -> random.Random`.
- Rule summary for implementers: patrol at multiples of `patrol_period`, adversarial at multiples of `adversarial_period` not already patrol, else draw the kind by share; attack picks a target with the exploration floor then NEXT-first ordering; combine needs two productive frames unpaired on the target or degrades to attack; forage-target picks the most recently parked target else fewest eligible frames; forage-frontier rotates categories; a target is eligible when `status == "open"`, or parked with `cooldown_until <= turn_index` and at least one unseen eligible frame; the tail-run target is ineligible once its run reaches `rotation_cap`; consecutive turns on a target use a frame different from the previous turn's, and the `rotation_cap`-th consecutive turn uses an unseen frame.

- [ ] **Step 1: Write the failing selection tests**

Append to `.timeloop/tests/test_driver_dispatcher.py`:

```python
import dataclasses

from driver.dispatcher import Brief, select
from driver.state import State, Target, next_turn_id


def with_next(root: Path, slug: str) -> State:
    """Load state and inject a NEXT line for one target, as the loop does from index.md."""
    s = load_state(root)
    targets = tuple(
        dataclasses.replace(t, raw={**t.raw, "_next": "try the other residue"}) if t.slug == slug else t
        for t in s.targets
    )
    return dataclasses.replace(s, targets=targets)


def test_scheduled_kinds_and_collision(tmp_path: Path) -> None:
    cfg = DriverConfig()
    root = room(tmp_path, [])
    s = load_state(root)
    assert select(s, cfg, 25).kind == "patrol"
    assert select(s, cfg, 50).kind == "patrol"
    assert select(s, cfg, 10).kind == "adversarial"
    assert select(s, cfg, 51).kind == "adversarial"   # deferred from the 50 collision
    assert select(s, cfg, 26).kind not in ("patrol", "adversarial")


def test_rotation_forces_distinct_then_fresh_frame(tmp_path: Path) -> None:
    cfg = DriverConfig(combine_share=0.0, forage_target_share=0.0, forage_frontier_share=0.0, exploration_floor=0.0)
    root = room(tmp_path, [turn("T1", "attack", "a", ["fx"], "negative")])
    b = select(with_next(root, "a"), cfg, 2)
    assert b.kind == "attack" and b.target == "a" and b.frames != ("fx",)
    root2 = room(tmp_path / "r2", [
        turn("T1", "attack", "a", ["fx"], "negative"),
        turn("T2", "attack", "a", ["fy"], "negative"),
    ])
    b2 = select(with_next(root2, "a"), cfg, 3)
    assert b2.target == "a" and b2.frames == ("fg",)  # the only unseen eligible frame


def test_no_fourth_consecutive_turn_even_with_next(tmp_path: Path) -> None:
    cfg = DriverConfig(combine_share=0.0, forage_target_share=0.0, forage_frontier_share=0.0, exploration_floor=0.0)
    root = room(tmp_path, [
        turn("T1", "attack", "a", ["fx"], "negative"),
        turn("T2", "attack", "a", ["fy"], "negative"),
        turn("T3", "attack", "a", ["fg"], "negative"),
    ])
    assert select(with_next(root, "a"), cfg, 4).target == "b"


def test_parked_target_revives_only_with_unseen_frame(tmp_path: Path) -> None:
    cfg = DriverConfig(combine_share=0.0, forage_target_share=0.0, forage_frontier_share=0.0, exploration_floor=0.0)
    root = room(tmp_path, [
        turn("T1", "attack", "b", ["fg"], "nothing"),
        turn("T2", "attack", "b", ["fg"], "nothing"),
    ])
    pool = read_jsonl(root / "pool.jsonl")
    pool[0].update({"status": "parked", "cooldown_until": 30})
    pool[1].update({"status": "parked", "cooldown_until": 5})
    (root / "pool.jsonl").write_text("".join(json.dumps(p) + "\n" for p in pool))
    s = load_state(root)
    # b's only eligible frame is fg, already seen: nothing eligible at index 6
    assert select(s, cfg, 6).kind == "forage-target"
    # give b an unseen frame
    (root / "frames.jsonl").open("a").write(json.dumps({"slug": "fz", "title": "", "statement": "", "shape": ["z"], "source": {"kind": "pool"}, "filed_by": "seed", "applied_to": [], "superseded_by": None}) + "\n")
    b = select(load_state(root), cfg, 6)
    assert b.target == "b" and b.revive and b.frames == ("fz",)


def test_combine_needs_unpaired_productive_frames(tmp_path: Path) -> None:
    cfg = DriverConfig(combine_share=1.0, forage_target_share=0.0, forage_frontier_share=0.0, exploration_floor=0.0)
    root = room(tmp_path, [])
    frames = read_jsonl(root / "frames.jsonl")
    frames[1]["applied_to"] = [{"target": "b", "turn": "T1", "outcome": "structure"}]  # fy productive
    (root / "frames.jsonl").write_text("".join(json.dumps(f) + "\n" for f in frames))
    pool = read_jsonl(root / "pool.jsonl")
    pool[1].update({"status": "parked", "cooldown_until": 100})  # only a is eligible
    (root / "pool.jsonl").write_text("".join(json.dumps(p) + "\n" for p in pool))
    b = select(load_state(root), cfg, 2)
    assert b.kind == "combine" and b.target == "a" and set(b.frames) == {"fx", "fy"}
    root2 = room(tmp_path / "r2", [turn("T1", "combine", "a", ["fx", "fy"], "nothing")])
    frames2 = read_jsonl(root2 / "frames.jsonl")
    frames2[1]["applied_to"] = [{"target": "b", "turn": "T0", "outcome": "structure"}]
    (root2 / "frames.jsonl").write_text("".join(json.dumps(f) + "\n" for f in frames2))
    b2 = select(load_state(root2), cfg, 2)
    assert b2.kind == "attack"  # the only productive pair is already paired on a; b has one productive frame


def test_exploration_floor_and_determinism(tmp_path: Path) -> None:
    cfg = DriverConfig(combine_share=0.0, forage_target_share=0.0, forage_frontier_share=0.0)
    root = room(tmp_path, [turn("T1", "attack", "a", ["fx"], "negative")])
    s = with_next(root, "a")   # a has a concrete NEXT and a productive last turn, so it wins outside the floor
    picks = [select(s, cfg, i).target for i in range(1, 1001) if i % 10 != 0 and i % 25 != 0]
    share_b = picks.count("b") / len(picks)
    assert 0.06 < share_b < 0.16   # half of the 20% floor lands on b
    assert select(s, cfg, 3) == select(s, cfg, 3)
    assert next_turn_id(s) == select(s, cfg, 3).turn_id
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --frozen python -m pytest .timeloop/tests/test_driver_dispatcher.py -q -p no:cacheprovider`
Expected: FAIL with `ImportError: cannot import name 'Brief'`

- [ ] **Step 3: Add Brief and select to dispatcher.py**

```python
import dataclasses
import random

from driver.state import next_turn_id


@dataclasses.dataclass(frozen=True)
class Brief:
    turn_id: str
    kind: str
    target: str | None
    frames: tuple[str, ...]
    category: str | None
    claim: str | None
    revive: bool
    reason: str


def rng_for(config: DriverConfig, turn_index: int) -> random.Random:
    return random.Random(f"{config.seed}:{turn_index}")


def _notebook_next(state: State, slug: str) -> str | None:
    """The loop injects each target's NEXT line from index.md as raw["_next"]."""
    v = state.target(slug).raw.get("_next")
    return None if v is None else str(v)


def _eligible_targets(state: State, config: DriverConfig, turn_index: int) -> list[Target]:
    tail_target, run = tail_run(state)
    out: list[Target] = []
    for t in state.targets:
        if t.slug == tail_target and run >= config.rotation_cap:
            continue
        if t.status == "open":
            out.append(t)
        elif t.status == "parked":
            cooldown = int(t.raw.get("cooldown_until", 0))  # type: ignore[call-overload]
            if cooldown <= turn_index:
                unseen = [f for f in eligible_frames(state, t) if f.slug not in frames_seen(state, t.slug)]
                if unseen:
                    out.append(t)
    return out


def _frame_for(state: State, config: DriverConfig, target: Target, rng: random.Random) -> Frame | None:
    tail_target, run = tail_run(state)
    eligible = eligible_frames(state, target)
    seen = frames_seen(state, target.slug)
    # A frame that was productive on this target is reserved for combine,
    # unless the last turn on the target was a correction, which reopens it.
    history = target_turns(state, target.slug)
    reopened = bool(history) and history[-1].outcome == "correction"
    reserved = set() if reopened else {
        f.slug for f in state.frames
        if any(a.get("target") == target.slug and str(a.get("outcome")) in PRODUCTIVE for a in f.applied_to)
    }
    pool = [f for f in eligible if f.slug not in reserved]
    if tail_target == target.slug and run >= 1:
        last = target_turns(state, target.slug)[-1].frames
        pool = [f for f in pool if f.slug not in last]
    if (tail_target == target.slug and run + 1 >= config.rotation_cap) or target.status == "parked":
        pool = [f for f in pool if f.slug not in seen]
    if not pool:
        return None
    unseen = [f for f in pool if f.slug not in seen]
    choice = unseen or pool
    return choice[rng.randrange(len(choice))]


def _pick_target(state: State, config: DriverConfig, turn_index: int, rng: random.Random) -> Target | None:
    candidates = _eligible_targets(state, config, turn_index)
    if not candidates:
        return None
    if rng.random() < config.exploration_floor:
        return candidates[rng.randrange(len(candidates))]
    def last_outcome(t: Target) -> str | None:
        turns = target_turns(state, t.slug)
        return turns[-1].outcome if turns else None
    with_next = [t for t in candidates if _notebook_next(state, t.slug) and last_outcome(t) in PRODUCTIVE]
    if with_next:
        return with_next[rng.randrange(len(with_next))]
    open_ones = [t for t in candidates if t.status == "open"]
    if open_ones:
        fewest = min(len(target_turns(state, t.slug)) for t in open_ones)
        tied = [t for t in open_ones if len(target_turns(state, t.slug)) == fewest]
        return tied[rng.randrange(len(tied))]
    return candidates[rng.randrange(len(candidates))]


def _combine_pair(state: State, target: Target, rng: random.Random) -> tuple[str, str] | None:
    productive = productive_frame_slugs(state)
    eligible = [f.slug for f in eligible_frames(state, target) if f.slug in productive]
    paired = {
        frozenset(t.frames) for t in target_turns(state, target.slug) if t.kind == "combine"
    }
    pairs = [
        (a, b) for i, a in enumerate(eligible) for b in eligible[i + 1:]
        if frozenset((a, b)) not in paired
    ]
    if not pairs:
        return None
    return pairs[rng.randrange(len(pairs))]


def _draw_kind(config: DriverConfig, rng: random.Random) -> str:
    x = rng.random()
    if x < config.combine_share:
        return "combine"
    x -= config.combine_share
    if x < config.forage_target_share:
        return "forage-target"
    x -= config.forage_target_share
    if x < config.forage_frontier_share:
        return "forage-frontier"
    return "attack"


def _adversarial_claim(state: State, rng: random.Random) -> str | None:
    """Least recently re-verified productive claim first; ties by seeded draw."""
    claims = [ln for ln in state.ledger_lines if ln.split("|")[0].strip().startswith("T")]
    if not claims:
        return None
    last_checked: dict[str, int] = {}
    for i, t in enumerate(state.turns):
        if t.kind == "adversarial" and t.claim:
            last_checked[t.claim.split("|")[0].strip()] = i
    oldest = min(last_checked.get(c.split("|")[0].strip(), -1) for c in claims)
    candidates = [c for c in claims if last_checked.get(c.split("|")[0].strip(), -1) == oldest]
    return candidates[rng.randrange(len(candidates))]


def select(state: State, config: DriverConfig, turn_index: int) -> Brief:
    turn_id = next_turn_id(state)
    rng = rng_for(config, turn_index)
    if turn_index % config.patrol_period == 0:
        return Brief(turn_id, "patrol", None, (), None, None, False, "scheduled patrol")
    prev_collision = (turn_index - 1) % config.patrol_period == 0 and (turn_index - 1) % config.adversarial_period == 0
    if turn_index % config.adversarial_period == 0 or prev_collision:
        return Brief(turn_id, "adversarial", None, (), None, _adversarial_claim(state, rng), False, "scheduled adversarial")
    kind = _draw_kind(config, rng)
    if kind == "forage-frontier":
        cats = config.arxiv_categories
        return Brief(turn_id, kind, None, (), cats[turn_index % len(cats)], None, False, "frontier forage by rotation")
    if kind == "forage-target":
        parked = [t for t in state.targets if t.status == "parked"]
        if parked:
            latest = max(parked, key=lambda t: int(t.raw.get("cooldown_until", 0)))  # type: ignore[call-overload]
            return Brief(turn_id, kind, latest.slug, (), None, None, False, "most recently parked target")
        fewest = min(state.targets, key=lambda t: (len(eligible_frames(state, t)), t.slug))
        return Brief(turn_id, kind, fewest.slug, (), None, None, False, "fewest eligible frames")
    target = _pick_target(state, config, turn_index, rng)
    if target is None:
        return Brief(turn_id, "forage-target", None, (), None, None, False, "no eligible target")
    if kind == "combine":
        pair = _combine_pair(state, target, rng)
        if pair is not None:
            return Brief(turn_id, "combine", target.slug, pair, None, None, target.status == "parked", "combine")
        kind = "attack"
    frame = _frame_for(state, config, target, rng)
    if frame is None:
        return Brief(turn_id, "forage-target", target.slug, (), None, None, False, "no unseen eligible frame")
    return Brief(turn_id, "attack", target.slug, (frame.slug,), None, None, target.status == "parked", "attack")
```

`_notebook_next` reads `target.raw["_next"]`, which the loop (Task 10) injects from `index.md` before calling `select`. The dispatcher itself never opens a notebook.

- [ ] **Step 4: Run tests, lint, types**

Run: `uv run --frozen python -m pytest .timeloop/tests/test_driver_dispatcher.py -q -p no:cacheprovider && uv run --frozen ruff check .timeloop/driver .timeloop/tests/test_driver_dispatcher.py && uv run --frozen mypy --strict .timeloop/driver`
Expected: 9 passed; clean. If the exploration test's band fails by a small margin, widen it to `0.05 < share_b < 0.18` and note why in a comment.

- [ ] **Step 5: Commit**

```bash
git add .timeloop/driver/dispatcher.py .timeloop/tests/test_driver_dispatcher.py
git commit -m "feat: deterministic turn selection with the sudoku rule"
```

---

### Task 6: Brief rendering, templates, and the result schema

**Files:**
- Create: `.timeloop/driver/brief.py`
- Create: `.timeloop/driver/templates/brief.md`
- Create: `.timeloop/driver/templates/system.md`
- Test: `.timeloop/tests/test_driver_brief.py`

**Interfaces:**
- Consumes: `Brief`, `State`, `DriverConfig`.
- Produces: `RESULT_SCHEMA: dict[str, object]`; `KIND_RULES: dict[str, str]`; `render_brief(brief: Brief, state: State, config: DriverConfig, root: Path) -> str`; `template_digest(root: Path) -> str`; `sha256(text: str) -> str`; `honesty_rules(root: Path) -> str` (README section between `## Honesty rules` and the next `## `).

- [ ] **Step 1: Write the failing tests**

```python
# .timeloop/tests/test_driver_brief.py
from __future__ import annotations

import json
import sys
from pathlib import Path

TIMELOOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TIMELOOP))

from driver.brief import RESULT_SCHEMA, honesty_rules, render_brief, template_digest
from driver.config import DriverConfig
from driver.dispatcher import Brief
from driver.state import load_state


def test_schema_is_strict_and_excludes_invalid() -> None:
    assert RESULT_SCHEMA["additionalProperties"] is False
    assert "invalid" not in RESULT_SCHEMA["properties"]["outcome"]["enum"]  # type: ignore[index]
    assert set(RESULT_SCHEMA["required"]) == {"outcome", "refinement", "ledger_line", "files_changed", "frames_filed", "next_action", "notes"}  # type: ignore[arg-type]


def test_honesty_rules_are_verbatim() -> None:
    text = honesty_rules(TIMELOOP)
    assert text.startswith("These exist because")
    assert "Never delete a prior turn's finding" in text


def test_render_attack_brief_has_every_section() -> None:
    s = load_state(TIMELOOP)
    b = Brief("T99", "attack", "lychrel-bases", ("carry-transducer-radial-frontier",), None, None, False, "attack")
    text = render_brief(b, s, DriverConfig(), TIMELOOP)
    for needle in ("T99", "attack", "lychrel-bases", "Treat reverse-and-add as a finite carry transducer",
                   "ruled out:", "T25 |", "begin with `T99 | `", "30 minutes", '"additionalProperties": false',
                   "Never delete a prior turn's finding", ".timeloop/notebook/lychrel-bases.md"):
        assert needle in text, needle
    assert len(text) < 12_000


def test_render_forage_and_adversarial_briefs() -> None:
    s = load_state(TIMELOOP)
    f = render_brief(Brief("T99", "forage-frontier", None, (), "math.NT", None, False, ""), s, DriverConfig(), TIMELOOP)
    assert "https://arxiv.org/list/math.NT/new" in f and "source URL" in f
    a = render_brief(Brief("T99", "adversarial", None, (), None, "T8 | giuga | REDUCED the conjecture | ...", False, ""), s, DriverConfig(), TIMELOOP)
    assert "independent code path" in a and "T8 | giuga" in a
    assert template_digest(TIMELOOP).startswith("sha256:")
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --frozen python -m pytest .timeloop/tests/test_driver_brief.py -q -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError: No module named 'driver.brief'`

- [ ] **Step 3: Write the templates**

`.timeloop/driver/templates/system.md`:

```markdown
You are one amnesiac turn of the time loop room in this repository. You do
not remember earlier turns; everything you know about them is in the files
under .timeloop/. Everything you leave for the next turn must be written to
those files before you finish.

Hard rules for this session:
- Do not run git. The driver commits for you after validating your work.
- Write only inside the allowed set named in the brief. Anything else is
  reverted before commit. Never write under publication/.
- Your budget is 30 minutes of wall clock. A computation that will not
  finish in that time is recorded as NEXT, not started. A smaller verified
  range beats a larger unverified one.
- Your final message must be the JSON result the brief specifies, and
  nothing else. The driver parses it.
```

`.timeloop/driver/templates/brief.md` (rendered with `string.Template`, so `$name` fields; a field followed by more identifier characters is written `${name}`; literal dollar signs are written `$$`). The outer fence below is four backticks because the template itself contains a fenced block:

````markdown
# Turn $turn_id — $kind

$kind_rules

## Target

$target_block

## Recent ledger lines for this target

$ledger_block

## Frames for this turn

$frames_block

## Outcome classes

Report exactly one:
- negative — ruled something out with a stated range
- structure — a transferable insight, written under STRUCTURE in the notebook
- correction — overturned a prior recorded claim, with the reason, without deleting it
- verified — (adversarial turns only) re-derived a prior claim independently, with stated range
- counterexample — re-verified by a second, independent code path before recording
- frames — (forage turns only) filed at least one new frame with a source URL
- nothing — ran, found nothing, and wrote what was tried under SEARCHED

Set refinement to true when your ledger line only sharpens a fact an earlier
ledger line already states, such as a larger range for the same negative.

## Rules of the room

$honesty_rules

Novelty check is mandatory before recording anything as new: look it up
(OEIS, arXiv, web) and record the result in the NOVELTY field.

## Writing rules

- Allowed writes: $allowed_writes
- A productive outcome requires appending one line to .timeloop/ledger.md that
  must begin with `$turn_id | ` and follow the ledger's format.
- Update .timeloop/notebook/$notebook_slug.md using the schema in the README
  (STATUS, SEARCHED, RULED OUT, STRUCTURE, TECHNIQUE, NOVELTY, NEXT, COST).
  Open it if the index line above is not enough.
- Reusable code goes in .timeloop/lib/ with a test in .timeloop/tests/;
  throwaway probes go in .timeloop/runs/ as ${turn_id_lower}_*.py.
- Budget: 30 minutes. Prefer a smaller verified range over a larger unverified one.

## Result

Finish by replying with JSON matching this schema and nothing else:

```json
$result_schema
```

files_changed must list every path you created or modified, relative to the
repository root. frames_filed entries need slug, title, statement, shape
tags, and source with kind and url.
````

- [ ] **Step 4: Write brief.py**

```python
# .timeloop/driver/brief.py
"""Render a one-page brief from a Brief record and the room state."""

from __future__ import annotations

import hashlib
import json
import re
import string
from pathlib import Path

from driver.config import DriverConfig
from driver.dispatcher import Brief
from driver.state import State

ALLOWED_WRITES: tuple[str, ...] = (
    ".timeloop/ledger.md", ".timeloop/notebook/", ".timeloop/pool.jsonl", ".timeloop/lib/",
    ".timeloop/runs/", ".timeloop/tests/", ".timeloop/lean/arena/", ".timeloop/driver/results/",
)

FRAME_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["slug", "title", "statement", "shape", "source"],
    "properties": {
        "slug": {"type": "string"},
        "title": {"type": "string"},
        "statement": {"type": "string"},
        "shape": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "source": {
            "type": "object",
            "additionalProperties": False,
            "required": ["kind", "url"],
            "properties": {
                "kind": {"enum": ["arxiv", "doi", "oeis", "web", "own"]},
                "id": {"type": "string"},
                "url": {"type": "string"},
            },
        },
    },
}

RESULT_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["outcome", "refinement", "ledger_line", "files_changed", "frames_filed", "next_action", "notes"],
    "properties": {
        "outcome": {"enum": ["negative", "structure", "correction", "verified", "counterexample", "frames", "nothing"]},
        "refinement": {"type": "boolean"},
        "ledger_line": {"type": ["string", "null"]},
        "files_changed": {"type": "array", "items": {"type": "string"}},
        "frames_filed": {"type": "array", "items": FRAME_SCHEMA},
        "next_action": {"type": ["string", "null"]},
        "notes": {"type": "string"},
    },
}

KIND_RULES: dict[str, str] = {
    "attack": "Attack the target with the single frame below. Bounded compute. Record what it ruled out or found. Report `nothing` honestly if that is what happened.",
    "combine": "Apply the two frames below together on the target. The question is their interaction: what does one frame's output let the other frame do that it could not do alone. Two separate attacks is the wrong answer.",
    "forage-target": "Search the web (arXiv, OEIS, MathOverflow, blogs) for methods that fit the target's shape and that no existing frame covers. File each as a frame with a source URL. Do not attack the target this turn.",
    "forage-frontier": "Read the new-listings page $listing and skim abstracts for methods that could transplant to any target in the pool. File each as a frame with the arXiv URL. A target is optional. Do not attack anything this turn.",
    "adversarial": "Below is a prior recorded claim. Try to break it with an independent code path that does not import the code that produced it. Report `correction` if it breaks, `verified` if it survives with a stated range, `nothing` if you could not test it in the budget.",
    "patrol": "Re-run the recorded NOVELTY queries for the targets with the oldest novelty checks and for all parked or superseded targets. Append a correction to the notebook where the literature has moved. Do not attack anything this turn.",
}


def sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def template_digest(root: Path) -> str:
    t = root / "driver" / "templates"
    return sha256((t / "brief.md").read_text() + (t / "system.md").read_text())


def honesty_rules(root: Path) -> str:
    text = (root / "README.md").read_text(encoding="utf-8")
    m = re.search(r"^## Honesty rules\s*\n(.*?)(?=^## )", text, re.MULTILINE | re.DOTALL)
    if not m:
        raise ValueError("README.md has no '## Honesty rules' section")
    return m.group(1).strip()


def _index_line(root: Path, slug: str) -> str:
    idx = root / "index.md"
    if idx.exists():
        for line in idx.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"- {slug} |"):
                return line
    return f"- {slug} | (no index line; run bin/lint --index)"


def _target_block(brief: Brief, state: State, root: Path) -> str:
    if brief.target is None:
        if brief.kind == "adversarial":
            return f"Claim under test:\n\n    {brief.claim or '(no prior claims recorded)'}"
        if brief.kind == "forage-frontier":
            return f"Category: {brief.category}. No target this turn."
        return "No target this turn."
    t = state.target(brief.target)
    rec = {k: v for k, v in t.raw.items() if not str(k).startswith("_")}
    return f"```json\n{json.dumps(rec, indent=1)}\n```\n\nIndex line:\n\n{_index_line(root, t.slug)}"


def _ledger_block(brief: Brief, state: State) -> str:
    if brief.target is None:
        return "(none)"
    lines = [ln for ln in state.ledger_lines if f"| {brief.target} |" in ln][-3:]
    return "\n\n".join(lines) if lines else "(no ledger lines mention this target yet)"


def _frames_block(brief: Brief, state: State) -> str:
    if brief.kind in ("forage-target", "forage-frontier"):
        return "You are filing frames, not using them. Existing frame slugs, to avoid duplicates:\n\n" + ", ".join(f.slug for f in state.frames)
    if not brief.frames:
        return "(none)"
    out = []
    for slug in brief.frames:
        f = state.frame(slug)
        out.append(f"### {f.title}\n\nslug: `{f.slug}`  shape: {', '.join(f.shape)}\n\n{f.statement}")
    return "\n\n".join(out)


def render_brief(brief: Brief, state: State, config: DriverConfig, root: Path) -> str:
    template = string.Template((root / "driver" / "templates" / "brief.md").read_text(encoding="utf-8"))
    listing = f"https://arxiv.org/list/{brief.category}/new" if brief.category else ""
    rules = KIND_RULES[brief.kind].replace("$listing", listing)
    return template.substitute(
        turn_id=brief.turn_id,
        turn_id_lower=brief.turn_id.lower(),
        kind=brief.kind,
        kind_rules=rules,
        target_block=_target_block(brief, state, root),
        ledger_block=_ledger_block(brief, state),
        frames_block=_frames_block(brief, state),
        honesty_rules=honesty_rules(root),
        allowed_writes=", ".join(ALLOWED_WRITES),
        notebook_slug=brief.target or "<slug>",
        result_schema=json.dumps(RESULT_SCHEMA, indent=1),
    )
```

The literal text "30 minutes" and "source URL" and "independent code path" must appear in the rendered output; they do through the template and `KIND_RULES`.

- [ ] **Step 5: Run tests, lint, types**

Run: `uv run --frozen python -m pytest .timeloop/tests/test_driver_brief.py -q -p no:cacheprovider && uv run --frozen ruff check .timeloop/driver .timeloop/tests/test_driver_brief.py && uv run --frozen mypy --strict .timeloop/driver`
Expected: 4 passed; clean.

- [ ] **Step 6: Commit**

```bash
git add .timeloop/driver/brief.py .timeloop/driver/templates/brief.md .timeloop/driver/templates/system.md .timeloop/tests/test_driver_brief.py
git commit -m "feat: render turn briefs and the result schema"
```

---

### Task 7: Runner

**Files:**
- Create: `.timeloop/driver/runner.py`
- Create: `.timeloop/tests/fixtures/fake_claude` (executable)
- Test: `.timeloop/tests/test_driver_runner.py`

**Interfaces:**
- Consumes: `DriverConfig`, `RESULT_SCHEMA`.
- Produces: `RunResult` frozen dataclass with `exit_reason: str` (`completed|timeout|nonzero_exit|schema|interrupted`), `exit_code: int | None`, `seconds: float`, `stdout: str`, `stderr: str`, `structured: dict[str, object] | None`, `error: str | None` (`usage_limit`, `auth`, or a free-text reason); `build_command(config, repo_root) -> list[str]`; `parse_output(stdout: str) -> tuple[dict[str, object] | None, str | None]`; `run_turn(brief_text: str, config: DriverConfig, repo_root: Path, timeout: int, interrupt: Callable[[], bool] | None = None) -> RunResult`. `interrupt` is polled once a second; when it returns True the child's process group is killed and the result is `interrupted`. The loop wires it to "a second stop signal arrived", so a single Ctrl-C lets the turn finish.
- The command passes `--strict-mcp-config --mcp-config '{"mcpServers": {}}'` so no plugin MCP servers load in the turn. Under `bypassPermissions`, `--allowedTools` documents intent but restricts nothing; the write set is enforced by the recorder's revert, and the brief and system prompt state the rules.
- The fake `claude` reads its behaviour from the environment variable `FAKE_CLAUDE_MODE`: `ok` prints a valid JSON envelope with `structured_output`; `sleep` sleeps 30 s; `nonzero` exits 3; `usage` prints an envelope with `is_error: true` and result `Claude usage limit reached`; `noschema` prints an envelope without `structured_output`; `write` creates the file named by `FAKE_CLAUDE_WRITE` then behaves like `ok`. It reads stdin fully first.

- [ ] **Step 1: Write the fake claude**

```python
#!/usr/bin/env python3
# .timeloop/tests/fixtures/fake_claude
"""Stand-in for the Claude Code CLI in driver tests. Behaviour via FAKE_CLAUDE_MODE."""
import json
import os
import sys
import time

sys.stdin.read()
mode = os.environ.get("FAKE_CLAUDE_MODE", "ok")
if mode == "sleep":
    time.sleep(30)
if mode == "nonzero":
    sys.exit(3)
if mode == "write":
    with open(os.environ["FAKE_CLAUDE_WRITE"], "w") as fh:
        fh.write("scribble\n")
payload = json.loads(os.environ.get("FAKE_CLAUDE_RESULT", json.dumps({
    "outcome": "nothing", "refinement": False, "ledger_line": None,
    "files_changed": [], "frames_filed": [], "next_action": None, "notes": "fake"})))
env = {"type": "result", "subtype": "success", "is_error": False, "num_turns": 1,
       "result": json.dumps(payload), "structured_output": payload, "session_id": "fake"}
if mode == "usage":
    env.update({"is_error": True, "result": "Claude usage limit reached. Try again later.", "structured_output": None})
if mode == "noschema":
    env["structured_output"] = None
print(json.dumps(env))
```

Then: `chmod +x .timeloop/tests/fixtures/fake_claude`.

- [ ] **Step 2: Write the failing tests**

```python
# .timeloop/tests/test_driver_runner.py
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

TIMELOOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TIMELOOP))

from driver.config import DriverConfig
from driver.runner import build_command, parse_output, run_turn

FAKE = str(TIMELOOP / "tests" / "fixtures" / "fake_claude")


def cfg() -> DriverConfig:
    return DriverConfig(claude_executable=FAKE, model="m", effort="high")


def test_build_command_matches_spec(tmp_path: Path) -> None:
    cmd = build_command(cfg(), tmp_path)
    assert cmd[0] == FAKE and cmd[1] == "-p"
    assert "--bare" not in cmd
    for flag in ("--output-format", "--json-schema", "--permission-mode", "--allowedTools", "--no-session-persistence", "--append-system-prompt-file", "--strict-mcp-config", "--mcp-config", "--model", "--effort"):
        assert flag in cmd
    assert cmd[cmd.index("--mcp-config") + 1] == '{"mcpServers": {}}'
    assert cmd[cmd.index("--permission-mode") + 1] == "bypassPermissions"
    assert cmd[cmd.index("--output-format") + 1] == "json"


def test_parse_output_variants() -> None:
    good = json.dumps({"is_error": False, "structured_output": {"outcome": "nothing"}, "result": ""})
    assert parse_output(good) == ({"outcome": "nothing"}, None)
    assert parse_output("not json") == (None, "stdout is not JSON")
    assert parse_output(json.dumps({"is_error": True, "result": "Claude usage limit reached", "structured_output": None})) == (None, "usage_limit")
    assert parse_output(json.dumps({"is_error": True, "result": "Not logged in · Please run /login", "structured_output": None})) == (None, "auth")
    assert parse_output(json.dumps({"is_error": False, "result": "x", "structured_output": None})) == (None, "no structured_output")


@pytest.mark.parametrize(("mode", "reason", "error"), [
    ("ok", "completed", None),
    ("nonzero", "nonzero_exit", None),
    ("usage", "completed", "usage_limit"),
    ("noschema", "schema", "no structured_output"),
])
def test_run_turn_modes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, reason: str, error: str | None) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", mode)
    r = run_turn("brief", cfg(), tmp_path, timeout=20)
    assert r.exit_reason == reason and r.error == error
    if mode == "ok":
        assert r.structured == {"outcome": "nothing", "refinement": False, "ledger_line": None, "files_changed": [], "frames_filed": [], "next_action": None, "notes": "fake"}


def test_run_turn_timeout_kills_child(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "sleep")
    r = run_turn("brief", cfg(), tmp_path, timeout=2)
    assert r.exit_reason == "timeout" and r.seconds < 10


def test_run_turn_interrupt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "sleep")
    r = run_turn("brief", cfg(), tmp_path, timeout=20, interrupt=lambda: True)
    assert r.exit_reason == "interrupted" and r.seconds < 10
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run --frozen python -m pytest .timeloop/tests/test_driver_runner.py -q -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError: No module named 'driver.runner'`

- [ ] **Step 4: Write runner.py**

```python
# .timeloop/driver/runner.py
"""Run one brief through `claude -p` under a hard timeout."""

from __future__ import annotations

import dataclasses
import json
import os
import signal
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from driver.brief import RESULT_SCHEMA
from driver.config import DriverConfig

USAGE_MARKERS = ("usage limit", "rate limit", "out of extra usage", "limit reached")
AUTH_MARKERS = ("not logged in", "please run /login", "authentication", "invalid api key")


@dataclasses.dataclass(frozen=True)
class RunResult:
    exit_reason: str
    exit_code: int | None
    seconds: float
    stdout: str
    stderr: str
    structured: dict[str, object] | None
    error: str | None


def build_command(config: DriverConfig, repo_root: Path) -> list[str]:
    system_prompt = repo_root / ".timeloop" / "driver" / "templates" / "system.md"
    cmd = [
        config.claude_executable, "-p",
        "--output-format", "json",
        "--json-schema", json.dumps(RESULT_SCHEMA),
        "--permission-mode", "bypassPermissions",
        "--allowedTools", *config.allowed_tools,
        "--no-session-persistence",
        "--append-system-prompt-file", str(system_prompt),
        "--strict-mcp-config", "--mcp-config", '{"mcpServers": {}}',
    ]
    if config.model:
        cmd += ["--model", config.model]
    if config.effort:
        cmd += ["--effort", config.effort]
    return cmd


def parse_output(stdout: str) -> tuple[dict[str, object] | None, str | None]:
    try:
        env = json.loads(stdout.strip().splitlines()[-1] if stdout.strip() else "")
    except (json.JSONDecodeError, IndexError):
        return (None, "stdout is not JSON")
    if not isinstance(env, dict):
        return (None, "stdout is not a JSON object")
    text = str(env.get("result", "")).lower()
    if env.get("is_error"):
        if any(m in text for m in USAGE_MARKERS):
            return (None, "usage_limit")
        if any(m in text for m in AUTH_MARKERS):
            return (None, "auth")
        return (None, f"claude error: {text[:200]}")
    structured = env.get("structured_output")
    if not isinstance(structured, dict):
        return (None, "no structured_output")
    return (structured, None)


def _kill_group(proc: subprocess.Popen[str]) -> None:
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=10)
            return
        except subprocess.TimeoutExpired:
            continue


def run_turn(
    brief_text: str,
    config: DriverConfig,
    repo_root: Path,
    timeout: int,
    interrupt: Callable[[], bool] | None = None,
) -> RunResult:
    started = time.monotonic()
    proc = subprocess.Popen(
        build_command(config, repo_root),
        cwd=repo_root,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    assert proc.stdin is not None
    proc.stdin.write(brief_text)
    proc.stdin.close()
    reason = "completed"
    while True:
        try:
            out, err = proc.communicate(timeout=1)
            break
        except subprocess.TimeoutExpired:
            if interrupt is not None and interrupt():
                reason = "interrupted"
            elif time.monotonic() - started > timeout:
                reason = "timeout"
            else:
                continue
            _kill_group(proc)
            out, err = proc.communicate()
            break
    seconds = round(time.monotonic() - started, 3)
    if reason != "completed":
        return RunResult(reason, proc.returncode, seconds, out, err, None, None)
    if proc.returncode != 0:
        return RunResult("nonzero_exit", proc.returncode, seconds, out, err, None, None)
    structured, error = parse_output(out)
    if structured is None:
        exit_reason = "completed" if error in ("usage_limit", "auth") else "schema"
        return RunResult(exit_reason, proc.returncode, seconds, out, err, None, error)
    return RunResult("completed", proc.returncode, seconds, out, err, structured, None)
```

- [ ] **Step 5: Run tests, lint, types**

Run: `uv run --frozen python -m pytest .timeloop/tests/test_driver_runner.py -q -p no:cacheprovider && uv run --frozen ruff check .timeloop/driver .timeloop/tests/test_driver_runner.py && uv run --frozen mypy --strict .timeloop/driver`
Expected: 8 passed; clean.

- [ ] **Step 6: Commit**

```bash
git add .timeloop/driver/runner.py .timeloop/tests/fixtures/fake_claude .timeloop/tests/test_driver_runner.py
git commit -m "feat: run a brief through headless claude under a hard timeout"
```

---

### Task 8: Recorder

**Files:**
- Create: `.timeloop/driver/recorder.py`
- Test: `.timeloop/tests/test_driver_recorder.py`

**Interfaces:**
- Consumes: `Brief`, `RunResult`, `State`, `TurnRecord`, `PRODUCTIVE`, `validate_frame`, `append_jsonl`, `read_jsonl`, `ALLOWED_WRITES`, `sha256`, `template_digest`.
- Produces: `snapshot(repo_root) -> dict[str, str]` mapping every path that `git status` reports (modified, deleted, or untracked, untracked files expanded) to the SHA-256 of its current content, or `"<deleted>"`; `delta(before, after) -> set[str]` (paths whose presence or hash differs); `is_allowed(path: str) -> bool`; `revert(repo_root, paths: set[str]) -> None`; `validate(brief, run, delta_paths, ledger_before: str, ledger_after: str) -> tuple[str, str | None, bool]` returning `(outcome, invalid_reason, refinement)`; `record(repo_root, brief, brief_text, run, pre_status, before_status, ledger_before, started_iso, hooks: Hooks) -> TurnRecord`.
- Two snapshots because the dispatcher writes `pool.jsonl` and the brief file before the model runs. `pre_status` is taken before the dispatcher acts and decides what gets staged; `before_status` is taken right before `claude` starts and decides what the model is held responsible for in `files_mismatch`.
- Content hashes rather than status codes because the room's files are often already dirty when a run starts. A file that was dirty before and that the turn changes again is in the delta and is committed in full, pre-existing edits included; the README will say so. A dirty file the turn does not touch has the same hash and is left alone.
- Rejected frames are not an invalid reason. The recorder appends `{"event": "frames_rejected", "turn_id": ..., "reasons": [...]}` to the turn log before the turn record.
- `Hooks` is a frozen dataclass of callables so tests can stub lint, exam, reap, and index: `lint: Callable[[], list[str]]`, `exam: Callable[[], bool]` (True means all items pass), `reap: Callable[[], None]`, `index: Callable[[], None]`. `default_hooks(repo_root) -> Hooks` runs the real scripts with `subprocess`.
- The recorder raises `ExamFailure` after committing when `exam()` returns False; the loop turns that into a halt.

- [ ] **Step 1: Write the failing tests**

```python
# .timeloop/tests/test_driver_recorder.py
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

TIMELOOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TIMELOOP))

from driver.dispatcher import Brief
from driver.recorder import ExamFailure, Hooks, delta, is_allowed, record, snapshot, validate
from driver.runner import RunResult
from driver.state import read_jsonl


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / ".timeloop" / "driver" / "results").mkdir(parents=True)
    (repo / ".timeloop" / "notebook").mkdir()
    (repo / ".timeloop" / "driver" / "briefs").mkdir()
    (repo / "publication").mkdir()
    (repo / ".timeloop" / "ledger.md").write_text("# L\n\nT1 | a | nothing | x\n")
    (repo / ".timeloop" / "pool.jsonl").write_text(json.dumps({"slug": "a", "status": "open", "tags": ["x"]}) + "\n")
    (repo / ".timeloop" / "frames.jsonl").write_text("")
    (repo / ".timeloop" / "driver" / "templates").mkdir()
    (repo / ".timeloop" / "driver" / "templates" / "brief.md").write_text("t")
    (repo / ".timeloop" / "driver" / "templates" / "system.md").write_text("s")
    (repo / "publication" / "keep.txt").write_text("released\n")
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "init")
    # pre-existing dirty work that must survive untouched
    (repo / "publication" / "keep.txt").write_text("human edit in progress\n")
    (repo / "scratch.txt").write_text("untracked human file\n")
    return repo


def stub_hooks(lint: list[str] | None = None, exam_ok: bool = True) -> Hooks:
    calls: list[str] = []
    return Hooks(
        lint=lambda: (calls.append("lint"), lint or [])[1],
        exam=lambda: (calls.append("exam"), exam_ok)[1],
        reap=lambda: calls.append("reap"),
        index=lambda: calls.append("index"),
    )


def result(outcome: str, ledger_line: str | None, files: list[str], frames: list[dict[str, object]] | None = None, refinement: bool = False) -> RunResult:
    payload = {"outcome": outcome, "refinement": refinement, "ledger_line": ledger_line,
               "files_changed": files, "frames_filed": frames or [], "next_action": None, "notes": ""}
    return RunResult("completed", 0, 12.5, json.dumps(payload), "", payload, None)


def brief(kind: str = "attack") -> Brief:
    return Brief("T2", kind, "a", ("f1",), None, None, False, "")


def test_snapshot_and_delta_use_content_hashes(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    before = snapshot(repo)
    assert set(before) == {"publication/keep.txt", "scratch.txt"}
    (repo / ".timeloop" / "runs").mkdir()
    (repo / ".timeloop" / "runs" / "t2_probe.py").write_text("print(1)\n")
    (repo / "publication" / "keep.txt").write_text("human edit, second pass\n")   # dirty file changed again
    (repo / "scratch.txt").unlink()
    after = snapshot(repo)
    assert delta(before, after) == {".timeloop/runs/t2_probe.py", "publication/keep.txt", "scratch.txt"}
    assert delta(after, after) == set()


def test_is_allowed() -> None:
    assert is_allowed(".timeloop/ledger.md") and is_allowed(".timeloop/notebook/a.md") and is_allowed(".timeloop/lean/arena/X.lean")
    assert not is_allowed(".timeloop/frames.jsonl") and not is_allowed("publication/x") and not is_allowed("src/y.py")


def test_validate_downgrades() -> None:
    d = {".timeloop/ledger.md"}
    ok = validate(brief(), result("negative", "T2 | a | negative | r", [".timeloop/ledger.md"]), d, "x\n", "x\nT2 | a | negative | r\n")
    assert ok == ("negative", None, False)
    no_line = validate(brief(), result("negative", None, [".timeloop/ledger.md"]), d, "x\n", "x\n")
    assert no_line[:2] == ("invalid", "no_ledger_line")
    mismatch = validate(brief(), result("nothing", None, []), d, "x\n", "x\n")
    assert mismatch[:2] == ("invalid", "files_mismatch")
    wrong_prefix = validate(brief(), result("negative", "T9 | a | negative | r", [".timeloop/ledger.md"]), d, "x\n", "x\nT9 | a | negative | r\n")
    assert wrong_prefix[:2] == ("invalid", "no_ledger_line")
    frames_on_attack = validate(brief(), result("frames", None, []), set(), "x\n", "x\n")
    assert frames_on_attack[:2] == ("invalid", "frames_outside_forage")
    timeout = validate(brief(), RunResult("timeout", None, 1800.0, "", "", None, None), set(), "x\n", "x\n")
    assert timeout[:2] == ("invalid", "timeout")


def test_record_commits_delta_and_preserves_dirty_files(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    pre = snapshot(repo)
    # the dispatcher's writes, before the model runs
    pool = repo / ".timeloop" / "pool.jsonl"
    pool.write_text(pool.read_text().replace('"status": "open"', '"status": "parked", "cooldown_until": 22'))
    (repo / ".timeloop" / "driver" / "briefs" / "T2.md").write_text("brief")
    before = snapshot(repo)
    ledger_before = (repo / ".timeloop" / "ledger.md").read_text()
    # the turn's writes
    (repo / ".timeloop" / "ledger.md").write_text(ledger_before + "\nT2 | a | negative | ruled out n<10\n")
    (repo / ".timeloop" / "notebook" / "a.md").write_text("## STATUS\nopen\n")
    (repo / "src.py").write_text("forbidden\n")
    (repo / "publication" / "new.pdf").write_text("forbidden\n")
    rec = record(repo, brief(), "brief", result("negative", "T2 | a | negative | ruled out n<10", [".timeloop/ledger.md", ".timeloop/notebook/a.md"]), pre, before, ledger_before, "2026-09-02T00:00:00Z", stub_hooks())
    assert rec.outcome == "negative" and rec.invalid_reason is None
    assert not (repo / "src.py").exists() and not (repo / "publication" / "new.pdf").exists()
    assert (repo / "publication" / "keep.txt").read_text() == "human edit in progress\n"
    assert (repo / "scratch.txt").exists()
    log = git(repo, "log", "--format=%s", "-1").strip()
    assert log == "turn: T2 attack a negative"
    assert git(repo, "status", "--porcelain", "--", "publication/keep.txt").startswith(" M")
    turns = read_jsonl(repo / ".timeloop" / "driver" / "turns.jsonl")
    assert turns[-1]["turn_id"] == "T2" and turns[-1]["base_commit"] == git(repo, "rev-parse", "HEAD~1").strip()
    committed = git(repo, "show", "--name-only", "--format=", "HEAD").split()
    assert ".timeloop/driver/turns.jsonl" in committed and ".timeloop/driver/briefs/T2.md" in committed
    assert ".timeloop/driver/results/T2.json" in committed
    assert ".timeloop/pool.jsonl" in committed          # the dispatcher's parking write rides along
    assert rec.files_changed == (".timeloop/ledger.md", ".timeloop/notebook/a.md")  # but is not blamed on the model


def test_record_files_frames_and_rejects_bad_ones(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    before = snapshot(repo)
    ledger_before = (repo / ".timeloop" / "ledger.md").read_text()
    (repo / ".timeloop" / "ledger.md").write_text(ledger_before + "\nT2 | a | frames | filed 2\n")
    good = {"slug": "new-frame", "title": "N", "statement": "p", "shape": ["x"], "source": {"kind": "arxiv", "id": "1", "url": "https://arxiv.org/abs/1"}}
    bad = {"slug": "no-url", "title": "N", "statement": "p", "shape": ["x"], "source": {"kind": "web"}}
    rec = record(repo, brief("forage-target"), "brief", result("frames", "T2 | a | frames | filed 2", [".timeloop/ledger.md"], [good, bad]), before, before, ledger_before, "2026-09-02T00:00:00Z", stub_hooks())
    frames = read_jsonl(repo / ".timeloop" / "frames.jsonl")
    assert [f["slug"] for f in frames] == ["new-frame"] and frames[0]["filed_by"] == "T2"
    assert rec.frames_filed == ("new-frame",) and rec.outcome == "frames" and rec.invalid_reason is None
    log = read_jsonl(repo / ".timeloop" / "driver" / "turns.jsonl")
    assert log[-2]["event"] == "frames_rejected" and "no-url" in log[-2]["reasons"][0]
    assert ".timeloop/frames.jsonl" in git(repo, "show", "--name-only", "--format=", "HEAD").split()


def test_record_adversarial_keeps_claim_and_forbids_verified_elsewhere(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    before = snapshot(repo)
    lb = (repo / ".timeloop" / "ledger.md").read_text()
    (repo / ".timeloop" / "ledger.md").write_text(lb + "\nT2 | a | verified | T1 re-derived independently for n<10^6\n")
    adv = Brief("T2", "adversarial", None, (), None, "T1 | a | nothing | x", False, "")
    rec = record(repo, adv, "brief", result("verified", "T2 | a | verified | T1 re-derived independently for n<10^6", [".timeloop/ledger.md"]), before, before, lb, "t", stub_hooks())
    assert rec.outcome == "verified" and rec.claim == "T1 | a | nothing | x"
    assert validate(brief(), result("verified", "T2 | a | verified | r", [".timeloop/ledger.md"]), {".timeloop/ledger.md"}, "x\n", "x\nT2 | a | verified | r\n")[:2] == ("invalid", "verified_outside_adversarial")


def test_record_lint_failure_and_exam_failure(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    before = snapshot(repo)
    lb = (repo / ".timeloop" / "ledger.md").read_text()
    rec = record(repo, brief(), "brief", result("nothing", None, []), before, before, lb, "t", stub_hooks(lint=["bad schema"]))
    assert rec.outcome == "invalid" and rec.invalid_reason == "lint: bad schema"
    now = snapshot(repo)
    with pytest.raises(ExamFailure):
        record(repo, brief(), "brief", result("nothing", None, []), now, now, lb, "t", stub_hooks(exam_ok=False))
    assert git(repo, "log", "--format=%s", "-1").strip().startswith("turn: T2")
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --frozen python -m pytest .timeloop/tests/test_driver_recorder.py -q -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError: No module named 'driver.recorder'`

- [ ] **Step 3: Write recorder.py**

```python
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
        if not p.stdout.strip():
            return []
        msg = json.loads(p.stdout).get("systemMessage", "")
        return [msg] if msg else []

    def exam() -> bool:
        p = _run(repo_root, "uv", "run", "--frozen", "--with", "sympy", str(tl / "bin" / "exam"), "--report")
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


def revert(repo_root: Path, paths: set[str]) -> None:
    if not paths:
        return
    tracked = _run(repo_root, "git", "ls-files", "--", *sorted(paths)).stdout.split()
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
    claimed = {str(p) for p in s.get("files_changed", [])}  # type: ignore[union-attr]
    turn_delta = {p for p in delta_paths if is_allowed(p) and not p.startswith(".timeloop/driver/")}
    if claimed != turn_delta:
        return ("invalid", "files_mismatch", refinement)
    if outcome in PRODUCTIVE:
        line = s.get("ledger_line")
        prefix = f"{brief.turn_id} | "
        new_text = ledger_after[len(ledger_before):] if ledger_after.startswith(ledger_before) else ledger_after
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
    for raw in run.structured.get("frames_filed", []):  # type: ignore[union-attr]
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
            apps = list(r.get("applied_to", []))  # type: ignore[arg-type]
            apps.append({"target": brief.target, "turn": brief.turn_id, "outcome": outcome})
            r["applied_to"] = apps
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")


STAGEABLE_EXTRA = (".timeloop/frames.jsonl", ".timeloop/index.md", ".timeloop/pool.jsonl")


def _stageable(path: str) -> bool:
    return is_allowed(path) or path.startswith(".timeloop/driver/") or path in STAGEABLE_EXTRA


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
    revert(repo_root, {p for p in model_delta if not is_allowed(p) and not p.startswith(".timeloop/driver/")})
    ledger_path = tl / "ledger.md"
    ledger_after = ledger_path.read_text(encoding="utf-8") if ledger_path.exists() else ""
    outcome, reason, refinement = validate(brief, run, model_delta, ledger_before, ledger_after)
    filed: list[str] = []
    if outcome != "invalid":
        filed, rejected = _file_frames(repo_root, brief, run)
        if rejected:
            append_jsonl(log, {"event": "frames_rejected", "turn_id": brief.turn_id, "reasons": rejected})
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
        ledger_line=(str(s["ledger_line"]) if outcome in PRODUCTIVE and s.get("ledger_line") else None),
        files_changed=tuple(sorted(p for p in model_delta if is_allowed(p) and not p.startswith(".timeloop/driver/"))),
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
    append_jsonl(log, rec.to_json())
    to_stage = sorted(p for p in delta(pre_status, snapshot(repo_root)) if _stageable(p))
    _run(repo_root, "git", "add", "--", *to_stage)
    _run(repo_root, "git", "commit", "-q", "-m", f"turn: {brief.turn_id} {brief.kind} {brief.target or '-'} {outcome}")
    if not exam_ok:
        raise ExamFailure(f"blind exam failed after {brief.turn_id}")
    return rec
```

- [ ] **Step 4: Run tests, lint, types**

Run: `uv run --frozen python -m pytest .timeloop/tests/test_driver_recorder.py -q -p no:cacheprovider && uv run --frozen ruff check .timeloop/driver .timeloop/tests/test_driver_recorder.py && uv run --frozen mypy --strict .timeloop/driver`
Expected: 7 passed; clean. A rejected frame is an event in the turn log, not an invalid reason, as long as at least one frame was filed.

- [ ] **Step 5: Commit**

```bash
git add .timeloop/driver/recorder.py .timeloop/tests/test_driver_recorder.py
git commit -m "feat: validate, log, and commit a turn from its git delta"
```

---

### Task 9: Status and yield report

**Files:**
- Create: `.timeloop/driver/status.py`
- Test: `.timeloop/tests/test_driver_status.py`

**Interfaces:**
- Consumes: `read_jsonl`, `PRODUCTIVE`.
- Produces: `yield_report(turns: list[dict[str, object]]) -> dict[str, object]` with keys `last_10`, `last_50`, `all` each `{"turns": int, "productive": int, "share": float | None}` and `by_kind` mapping kind → the same triple over all turns; `format_status(root: Path) -> str` reading `driver/lease.json` and `driver/turns.jsonl`.

- [ ] **Step 1: Write the failing tests**

```python
# .timeloop/tests/test_driver_status.py
from __future__ import annotations

import json
import sys
from pathlib import Path

TIMELOOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TIMELOOP))

from driver.status import format_status, yield_report


def rec(i: int, kind: str, outcome: str) -> dict[str, object]:
    return {"turn_id": f"T{i}", "kind": kind, "target": "a", "frames": [], "outcome": outcome,
            "refinement": False, "ledger_line": None, "files_changed": [], "frames_filed": [],
            "started": "", "seconds": 1.0, "base_commit": "", "exit_reason": "completed",
            "invalid_reason": None, "brief_digest": "", "template_digest": ""}


def test_yield_report_windows_and_kinds() -> None:
    turns = [rec(i, "attack", "negative" if i % 3 == 0 else "nothing") for i in range(60)]
    turns.insert(5, {"event": "halt", "reason": "x"})
    turns.append(rec(60, "patrol", "nothing"))
    r = yield_report(turns)
    assert r["all"]["turns"] == 61 and r["all"]["productive"] == 20
    assert r["last_10"]["turns"] == 10 and r["last_50"]["turns"] == 50
    assert r["by_kind"]["patrol"] == {"turns": 1, "productive": 0, "share": 0.0}
    assert yield_report([])["all"]["share"] is None


def test_format_status_reports_lease_and_yield(tmp_path: Path) -> None:
    root = tmp_path / ".timeloop"
    (root / "driver").mkdir(parents=True)
    (root / "driver" / "turns.jsonl").write_text(json.dumps(rec(1, "attack", "negative")) + "\n")
    assert "no lease" in format_status(root)
    (root / "driver" / "lease.json").write_text(json.dumps({"pid": 1, "started": "2026-09-02T00:00:00Z", "seed": 1, "heartbeat": "2026-09-02T00:10:00Z", "turn_id": "T2", "kind": "attack", "target": "a", "frames": ["f"]}))
    text = format_status(root)
    assert "pid 1" in text and "T2 attack a" in text and "last 10: 1/1" in text
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --frozen python -m pytest .timeloop/tests/test_driver_status.py -q -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError: No module named 'driver.status'`

- [ ] **Step 3: Write status.py**

```python
# .timeloop/driver/status.py
"""Yield numbers from the turn log. The same numbers gate the soak."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from driver.state import PRODUCTIVE, read_jsonl


def _triple(turns: list[dict[str, object]]) -> dict[str, object]:
    n = len(turns)
    p = sum(1 for t in turns if str(t.get("outcome")) in PRODUCTIVE)
    return {"turns": n, "productive": p, "share": (round(p / n, 3) if n else None)}


def yield_report(turns: list[dict[str, object]]) -> dict[str, object]:
    real = [t for t in turns if "turn_id" in t]
    kinds = Counter(str(t.get("kind")) for t in real)
    return {
        "last_10": _triple(real[-10:]),
        "last_50": _triple(real[-50:]),
        "all": _triple(real),
        "by_kind": {k: _triple([t for t in real if t.get("kind") == k]) for k in sorted(kinds)},
    }


def format_status(root: Path) -> str:
    lines: list[str] = []
    lease = root / "driver" / "lease.json"
    if lease.exists():
        L = json.loads(lease.read_text(encoding="utf-8"))
        hb = datetime.fromisoformat(str(L["heartbeat"]).replace("Z", "+00:00"))
        age = int((datetime.now(UTC) - hb).total_seconds())
        lines.append(f"lease: pid {L['pid']} since {L['started']} (heartbeat {age}s ago)")
        lines.append(f"current: {L.get('turn_id')} {L.get('kind')} {L.get('target')} {' '.join(L.get('frames', []))}".rstrip())
    else:
        lines.append("lease: no lease (not running)")
    r = yield_report(read_jsonl(root / "driver" / "turns.jsonl"))
    for key in ("last_10", "last_50", "all"):
        t = r[key]
        assert isinstance(t, dict)
        label = key.replace("_", " ")
        lines.append(f"yield {label}: {t['productive']}/{t['turns']} productive" + (f" ({t['share']})" if t["share"] is not None else ""))
    by = r["by_kind"]
    assert isinstance(by, dict)
    for k, t in by.items():
        lines.append(f"  {k}: {t['productive']}/{t['turns']}")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests, lint, types**

Run: `uv run --frozen python -m pytest .timeloop/tests/test_driver_status.py -q -p no:cacheprovider && uv run --frozen ruff check .timeloop/driver .timeloop/tests/test_driver_status.py && uv run --frozen mypy --strict .timeloop/driver`
Expected: 2 passed; clean.

- [ ] **Step 5: Commit**

```bash
git add .timeloop/driver/status.py .timeloop/tests/test_driver_status.py
git commit -m "feat: yield report and status output"
```

---

### Task 10: Loop, lease, signals, breaker, ceilings, and `bin/research`

**Files:**
- Create: `.timeloop/driver/loop.py`
- Create: `bin/research`
- Test: `.timeloop/tests/test_driver_loop.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `Lease` helpers `acquire(root, seed) -> None` (raises `LeaseHeld` if a live lease exists; expires a stale one and appends a `lease_expired` event), `heartbeat(root, brief | None) -> None`, `release(root) -> None`; `run_loop(repo_root, config, max_turns: int | None, max_hours: float | None, hooks: Hooks | None = None) -> int` returning the exit code; `main(argv: list[str]) -> int` handling `run [--max-turns N] [--max-hours H] [--config PATH]`, `status`, `stop`.
- Turn index: `len(turn records) + 1` at loop start, incremented per turn. The loop injects each target's NEXT line from `index.md` into `target.raw["_next"]` before calling `select` (parse `| next: ` from the target's index line; treat `(none recorded)` as absent).
- Halt events appended to the turn log: `{"event": "halt", "reason": ..., "turn_index": ..., "at": iso}`; interrupts: `{"event": "interrupted", ...}`.

- [ ] **Step 1: Write the failing tests**

```python
# .timeloop/tests/test_driver_loop.py
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

TIMELOOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TIMELOOP))

from driver.config import DriverConfig
from driver.loop import LeaseHeld, acquire, release, run_loop
from driver.recorder import Hooks
from driver.state import read_jsonl

FAKE = str(TIMELOOP / "tests" / "fixtures" / "fake_claude")


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    tl = repo / ".timeloop"
    for d in ("driver/templates", "driver/results", "notebook", "bin"):
        (tl / d).mkdir(parents=True)
    src = TIMELOOP
    (tl / "driver" / "templates" / "brief.md").write_text((src / "driver" / "templates" / "brief.md").read_text())
    (tl / "driver" / "templates" / "system.md").write_text((src / "driver" / "templates" / "system.md").read_text())
    (tl / "README.md").write_text((src / "README.md").read_text())
    (tl / "pool.jsonl").write_text(
        json.dumps({"slug": "a", "track": "open", "tags": ["x"], "priority": 1, "title": "A", "statement": "s", "status": "open"}) + "\n"
        + json.dumps({"slug": "b", "track": "open", "tags": ["x"], "priority": 2, "title": "B", "statement": "s", "status": "open"}) + "\n"
    )
    (tl / "frames.jsonl").write_text(
        json.dumps({"slug": "f1", "title": "F1", "statement": "p", "shape": ["x"], "source": {"kind": "pool"}, "filed_by": "seed", "applied_to": [], "superseded_by": None}) + "\n"
        + json.dumps({"slug": "f2", "title": "F2", "statement": "p", "shape": ["x"], "source": {"kind": "pool"}, "filed_by": "seed", "applied_to": [], "superseded_by": None}) + "\n"
        + json.dumps({"slug": "f3", "title": "F3", "statement": "p", "shape": ["*"], "source": {"kind": "pool"}, "filed_by": "seed", "applied_to": [], "superseded_by": None}) + "\n"
    )
    (tl / "ledger.md").write_text("# L\n\nT0 | a | nothing | start\n")
    (tl / "index.md").write_text("- a | open | ruled out: (none recorded) | next: (none recorded)\n- b | open | ruled out: (none recorded) | next: (none recorded)\n")
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def hooks() -> Hooks:
    return Hooks(lint=lambda: [], exam=lambda: True, reap=lambda: None, index=lambda: None)


def cfg(**kw: object) -> DriverConfig:
    base = {"claude_executable": FAKE, "combine_share": 0.0, "forage_target_share": 0.0, "forage_frontier_share": 0.0, "turn_timeout_seconds": 5}
    base.update(kw)
    return DriverConfig(**base)  # type: ignore[arg-type]


def test_max_turns_runs_exactly_n_and_commits_each(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = make_repo(tmp_path)
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "ok")
    code = run_loop(repo, cfg(), max_turns=3, max_hours=None, hooks=hooks())
    assert code == 0
    turns = [t for t in read_jsonl(repo / ".timeloop" / "driver" / "turns.jsonl") if "turn_id" in t]
    assert [t["turn_id"] for t in turns] == ["T1", "T2", "T3"]
    assert all(t["outcome"] == "nothing" for t in turns)
    subjects = git(repo, "log", "--format=%s").splitlines()
    assert [s for s in subjects if s.startswith("turn: T")] == [f"turn: T{i} attack {turns[i-1]['target']} nothing" for i in (3, 2, 1)]
    for t in turns:   # every record's base_commit is the parent of the commit carrying its id
        child = git(repo, "log", "--format=%H %s", f"{t['base_commit']}..HEAD").splitlines()[-1]
        assert child.endswith(f"turn: {t['turn_id']} attack {t['target']} nothing")
    assert not (repo / ".timeloop" / "driver" / "lease.json").exists()


def test_max_hours_zero_halts_before_any_turn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = make_repo(tmp_path)
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "ok")
    assert run_loop(repo, cfg(), max_turns=None, max_hours=0.0, hooks=hooks()) == 0
    log = read_jsonl(repo / ".timeloop" / "driver" / "turns.jsonl")
    assert log == [{**log[0], "event": "halt", "reason": "max_hours"}]


def test_breaker_halts_at_threshold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = make_repo(tmp_path)
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "nonzero")
    code = run_loop(repo, cfg(breaker_threshold=3), max_turns=10, max_hours=None, hooks=hooks())
    assert code == 5
    log = read_jsonl(repo / ".timeloop" / "driver" / "turns.jsonl")
    assert sum(1 for t in log if "turn_id" in t) == 3
    assert log[-1]["event"] == "halt" and log[-1]["reason"] == "breaker"


def test_usage_limit_halts_immediately(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = make_repo(tmp_path)
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "usage")
    code = run_loop(repo, cfg(), max_turns=10, max_hours=None, hooks=hooks())
    assert code != 0
    log = read_jsonl(repo / ".timeloop" / "driver" / "turns.jsonl")
    assert sum(1 for t in log if "turn_id" in t) == 1 and log[-1]["reason"] == "usage_limit"


def test_lease_contention_and_stale_expiry(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    root = repo / ".timeloop"
    acquire(root, seed=1, stale_seconds=2700)
    with pytest.raises(LeaseHeld):
        acquire(root, seed=1, stale_seconds=2700)
    release(root)
    (root / "driver" / "lease.json").write_text(json.dumps({"pid": 999999, "started": "2026-01-01T00:00:00Z", "seed": 1, "heartbeat": "2026-01-01T00:00:00Z", "turn_id": None}))
    acquire(root, seed=1, stale_seconds=2700)
    log = read_jsonl(root / "driver" / "turns.jsonl")
    assert log[-1]["event"] == "lease_expired"
    release(root)


def test_two_signals_kill_the_turn_and_release(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    env = {**os.environ, "FAKE_CLAUDE_MODE": "sleep", "PYTHONPATH": str(TIMELOOP)}
    cfg_path = repo / ".timeloop" / "driver" / "config.json"
    cfg_path.write_text(json.dumps({"claude_executable": FAKE, "combine_share": 0.0, "forage_target_share": 0.0, "forage_frontier_share": 0.0, "turn_timeout_seconds": 60}))
    proc = subprocess.Popen([sys.executable, "-m", "driver.loop", "run", "--max-turns", "2", "--no-hooks"], cwd=repo, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(3)
    proc.send_signal(signal.SIGTERM)   # first: let the turn finish
    time.sleep(2)
    assert proc.poll() is None          # still running: the fake sleeps 30 s
    proc.send_signal(signal.SIGTERM)   # second: kill the child
    out, err = proc.communicate(timeout=30)
    assert proc.returncode == 130, err
    log = read_jsonl(repo / ".timeloop" / "driver" / "turns.jsonl")
    assert [t for t in log if "turn_id" in t][-1]["exit_reason"] == "interrupted"
    assert log[-1]["event"] == "interrupted" and log[-1]["hard"] is True
    assert not (repo / ".timeloop" / "driver" / "lease.json").exists()


def test_one_signal_stops_at_the_boundary(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    env = {**os.environ, "FAKE_CLAUDE_MODE": "ok", "PYTHONPATH": str(TIMELOOP)}
    (repo / ".timeloop" / "driver" / "config.json").write_text(json.dumps({"claude_executable": FAKE, "combine_share": 0.0, "forage_target_share": 0.0, "forage_frontier_share": 0.0}))
    proc = subprocess.Popen([sys.executable, "-m", "driver.loop", "run", "--max-turns", "50", "--no-hooks"], cwd=repo, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(2)
    proc.send_signal(signal.SIGINT)
    out, err = proc.communicate(timeout=60)
    assert proc.returncode == 0, err
    log = read_jsonl(repo / ".timeloop" / "driver" / "turns.jsonl")
    assert log[-1]["event"] == "interrupted" and "hard" not in log[-1]
    assert all(t["exit_reason"] == "completed" for t in log if "turn_id" in t)
    assert 1 <= sum(1 for t in log if "turn_id" in t) < 50
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --frozen python -m pytest .timeloop/tests/test_driver_loop.py -q -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError: No module named 'driver.loop'`

- [ ] **Step 3: Write loop.py**

```python
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
from driver.recorder import ExamFailure, Hooks, default_hooks, record, snapshot
from driver.runner import run_turn
from driver.state import State, Target, append_jsonl, load_state, read_jsonl
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
            raise LeaseHeld(f"researcher pid {L['pid']} holds the lease (heartbeat {int(age)}s ago)")
        append_jsonl(root / "driver" / "turns.jsonl", {"event": "lease_expired", "pid": L["pid"], "heartbeat": L["heartbeat"], "at": _now()})
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"pid": os.getpid(), "started": _now(), "seed": seed, "heartbeat": _now(), "turn_id": None}), encoding="utf-8")


def heartbeat(root: Path, brief: Brief | None) -> None:
    p = _lease_path(root)
    L = json.loads(p.read_text(encoding="utf-8"))
    L["heartbeat"] = _now()
    if brief is not None:
        L.update({"turn_id": brief.turn_id, "kind": brief.kind, "target": brief.target, "frames": list(brief.frames)})
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
    turn_index = len([t for t in read_jsonl(root / "driver" / "turns.jsonl") if "turn_id" in t]) + 1
    code = 0
    try:
        while True:
            if max_turns is not None and done >= max_turns:
                break
            if max_hours is not None and (time.monotonic() - started) / 3600 >= max_hours:
                append_jsonl(root / "driver" / "turns.jsonl", {"event": "halt", "reason": "max_hours", "turn_index": turn_index, "at": _now()})
                break
            if signals.requested():
                append_jsonl(root / "driver" / "turns.jsonl", {"event": "interrupted", "turn_index": turn_index, "at": _now()})
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
            ledger_before = (root / "ledger.md").read_text(encoding="utf-8")
            started_iso = _now()
            print(f"[{started_iso}] {brief.turn_id} {brief.kind} {brief.target or '-'} {' '.join(brief.frames)}", flush=True)
            run = run_turn(text, config, repo_root, config.turn_timeout_seconds, interrupt=signals.hard)
            try:
                rec = record(repo_root, brief, text, run, pre, before, ledger_before, started_iso, hooks)
            except ExamFailure as e:
                append_jsonl(root / "driver" / "turns.jsonl", {"event": "halt", "reason": f"exam: {e}", "turn_index": turn_index, "at": _now()})
                code = 3
                break
            print(f"  -> {rec.outcome}{' (' + rec.invalid_reason + ')' if rec.invalid_reason else ''} in {rec.seconds:.0f}s", flush=True)
            done += 1
            turn_index += 1
            heartbeat(root, None)
            if run.error in ("usage_limit", "auth"):
                append_jsonl(root / "driver" / "turns.jsonl", {"event": "halt", "reason": run.error, "turn_index": turn_index, "at": _now()})
                code = 4
                break
            if run.exit_reason == "interrupted":
                append_jsonl(root / "driver" / "turns.jsonl", {"event": "interrupted", "turn_index": turn_index, "at": _now(), "hard": True})
                code = 130
                break
            consecutive_invalid = consecutive_invalid + 1 if rec.outcome == "invalid" else 0
            if consecutive_invalid >= config.breaker_threshold:
                append_jsonl(root / "driver" / "turns.jsonl", {"event": "halt", "reason": "breaker", "turn_index": turn_index, "at": _now()})
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
    run_p.add_argument("--no-hooks", action="store_true", help="tests only: skip lint/exam/reap/index")
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
    hooks = Hooks(lint=lambda: [], exam=lambda: True, reap=lambda: None, index=lambda: None) if args.no_hooks else None
    return run_loop(repo_root, config, args.max_turns, args.max_hours, hooks)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Write bin/research**

```bash
#!/usr/bin/env bash
# One command: run the time loop room autonomously through headless Claude Code.
#   bin/research [--max-turns N] [--max-hours H]   run in the foreground under caffeinate
#   bin/research status                              read-only, from any terminal
#   bin/research stop                                SIGTERM the running researcher
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$ROOT"
export PYTHONPATH="$ROOT/.timeloop${PYTHONPATH:+:$PYTHONPATH}"

case "${1:-run}" in
  status|stop)
    exec uv run --frozen python -m driver.loop "$1"
    ;;
  run|--*)
    [ "${1:-}" = "run" ] && shift
    command -v claude >/dev/null || { echo "claude CLI not on PATH" >&2; exit 2; }
    claude auth status >/dev/null 2>&1 || { echo "claude is not logged in; run: claude auth login" >&2; exit 2; }
    git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "not a git repository" >&2; exit 2; }
    [ -f .timeloop/frames.jsonl ] || { echo ".timeloop/frames.jsonl missing" >&2; exit 2; }
    dirty="$(git status --porcelain -- .timeloop | grep -v '^?? .timeloop/driver/' || true)"
    if [ -n "$dirty" ]; then
      echo "warning: .timeloop has uncommitted changes. A turn that touches one of these files commits it whole:" >&2
      echo "$dirty" | head -10 >&2
    fi
    .timeloop/bin/lint --index >/dev/null
    exec caffeinate -i uv run --frozen python -m driver.loop run "$@"
    ;;
  *)
    echo "usage: bin/research [run] [--max-turns N] [--max-hours H] | status | stop" >&2
    exit 2
    ;;
esac
```

Then: `chmod +x bin/research`.

- [ ] **Step 5: Run tests, lint, types**

Run: `uv run --frozen python -m pytest .timeloop/tests/test_driver_loop.py -q -p no:cacheprovider && uv run --frozen ruff check .timeloop/driver .timeloop/tests/test_driver_loop.py && uv run --frozen mypy --strict .timeloop/driver`
Expected: 7 passed; clean. The two signal tests take several seconds each.

- [ ] **Step 6: Smoke the CLI against the fake**

Run: `cd /tmp && rm -rf smoke && git clone -q "$OLDPWD" smoke && cd smoke && FAKE_CLAUDE_MODE=ok PYTHONPATH=.timeloop uv run --frozen python -m driver.loop run --max-turns 1 --no-hooks --config <(echo '{"claude_executable": "'"$OLDPWD"'/.timeloop/tests/fixtures/fake_claude"}') && PYTHONPATH=.timeloop uv run --frozen python -m driver.loop status; cd "$OLDPWD"`
Expected: one turn line, an outcome line, then a status block with `yield last 10: 0/1 productive`. The clone keeps the real repository untouched.

- [ ] **Step 7: Commit**

```bash
git add .timeloop/driver/loop.py bin/research .timeloop/tests/test_driver_loop.py
git commit -m "feat: continuous research loop with lease, breaker, and one-command entry"
```

---

### Task 11: Exam items

**Files:**
- Modify: `.timeloop/exam/items.py`
- Test: run `bin/exam`

**Interfaces:**
- Produces: `item_driver_yield_independent()` and `item_driver_rotation_cap()` appended to `ITEMS`, both level 1, both returning `(name, level, ok, detail)`.

- [ ] **Step 1: Add the items**

Append before `ITEMS = [` in `.timeloop/exam/items.py`:

```python
# ─────────────────────────── level 1: the driver ──────────────────────────────
# The driver grades its own turns. These items check its two load-bearing
# numbers with code that shares nothing with driver/.

def item_driver_yield_independent():
    """Yield from turns.jsonl recomputed by a one-liner must equal status.py."""
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    log = root / "driver" / "turns.jsonl"
    if not log.exists():
        return ("driver/yield-independent", 1, True, "no driver turns yet")
    rows = [json.loads(l) for l in log.read_text().splitlines() if l.strip()]
    real = [r for r in rows if "turn_id" in r]
    good = {"negative", "structure", "correction", "verified", "counterexample", "frames"}
    mine = (len(real), sum(r["outcome"] in good for r in real))
    sys.path.insert(0, str(root))
    from driver.status import yield_report
    theirs = yield_report(rows)["all"]
    ok = mine == (theirs["turns"], theirs["productive"])
    return ("driver/yield-independent", 1, ok, f"independent {mine} vs status {theirs}")


def item_driver_rotation_cap():
    """200 simulated turns must never put more than 3 consecutive on one target."""
    import dataclasses
    import json
    import random
    import tempfile
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from driver.config import DriverConfig
    from driver.dispatcher import apply_stalls, select, unpark
    from driver.state import append_jsonl, load_state
    with tempfile.TemporaryDirectory() as td:
        tl = Path(td) / ".timeloop"
        (tl / "driver").mkdir(parents=True)
        (tl / "notebook").mkdir()
        (tl / "pool.jsonl").write_text(root.joinpath("pool.jsonl").read_text())
        (tl / "frames.jsonl").write_text(root.joinpath("frames.jsonl").read_text())
        (tl / "ledger.md").write_text("T0 | seed | nothing | x\n")
        cfg = DriverConfig(seed=11)
        rng = random.Random(11)
        worst = 0
        run_target, run_len = None, 0
        for i in range(1, 201):
            state = apply_stalls(tl, load_state(tl), cfg, i)
            b = select(state, cfg, i)
            if b.revive and b.target:
                unpark(tl, b.target)
            if b.kind in ("attack", "combine"):
                run_len = run_len + 1 if b.target == run_target else 1
                run_target = b.target
                worst = max(worst, run_len)
            outcome = rng.choice(["negative", "nothing", "nothing", "structure"]) if b.kind in ("attack", "combine") else ("frames" if b.kind.startswith("forage") else "nothing")
            append_jsonl(tl / "driver" / "turns.jsonl", {"turn_id": b.turn_id, "kind": b.kind, "target": b.target,
                "frames": list(b.frames), "outcome": outcome, "refinement": False, "ledger_line": None,
                "files_changed": [], "frames_filed": [], "started": "", "seconds": 0.0, "base_commit": "",
                "exit_reason": "completed", "invalid_reason": None, "brief_digest": "", "template_digest": ""})
        return ("driver/rotation-cap", 1, worst <= 3, f"longest consecutive run on one target: {worst}")
```

Add both to `ITEMS` after `item_persistence_published`.

- [ ] **Step 2: Run the exam**

Run: `uv run --frozen --with sympy .timeloop/bin/exam | tail -6`
Expected: both new items pass; the total rises to 14 passed. The rotation item takes a few seconds.

- [ ] **Step 3: Commit**

```bash
git add .timeloop/exam/items.py .timeloop/exam/results.jsonl
git commit -m "feat: blind exam items for driver yield and rotation cap"
```

Note: `results.jsonl` already carries uncommitted human runs; committing it here is acceptable because the file is append-only and the exam appends its own line. If the operator prefers, leave it out of the commit.

---

### Task 12: Documentation and rollout gates

**Files:**
- Modify: `.timeloop/README.md` (new section)
- Modify: `.timeloop/ARENA.md` (priority list)

- [ ] **Step 1: Document the driver in README**

Append to `.timeloop/README.md` after "## Tracks":

```markdown
## Running the room autonomously

`bin/research` runs turns back to back through headless Claude Code until
stopped. The dispatcher, not the model, chooses each turn: it rotates
angles before targets (a target gets at most three consecutive turns, each
with a different frame, the third with a frame it has never seen), parks a
target after three non-productive turns or three refinements, forages
online for new frames about one turn in five, combines productive frames,
re-verifies a prior claim every tenth turn, and re-checks novelty every
twenty-fifth.

```sh
bin/research --max-turns 3      # supervised batch
bin/research --max-hours 8      # overnight
bin/research status             # from another terminal
bin/research stop               # clean stop after the current turn
```

Every turn's brief is in `driver/briefs/`, its raw result in
`driver/results/`, and its record in `driver/turns.jsonl`. Frames live in
`frames.jsonl` and are written only by the recorder. `index.md` is the
one-line-per-target orientation the turn reads first; regenerate it with
`bin/lint --index`. The design is
`docs/superpowers/specs/2026-09-02-headless-research-driver-design.md`.

Start a run with `.timeloop/` committed. The recorder commits only what a
turn changed, judged by content, so a file that was already dirty and that
the turn also edits is committed whole, your pending edits included.
`bin/research` warns about dirty paths before starting. One Ctrl-C lets the
current turn finish and then stops; a second kills the turn.
```

- [ ] **Step 2: Update ARENA.md priority order**

Replace item 6 in "## Priority order" with:

```markdown
6. ~~**Instrumentation**~~ — `driver/turns.jsonl` records every turn's outcome class; `bin/research status` reports yield over the last 10, 50, and all turns. Whether turn 50 beats turn 5 is now a number.
```

- [ ] **Step 3: Run the whole driver suite one last time**

Run: `uv run --frozen python -m pytest .timeloop/tests/test_driver_*.py -q -p no:cacheprovider && uv run --frozen ruff check .timeloop/driver .timeloop/tests/test_driver_*.py && uv run --frozen mypy --strict .timeloop/driver && .timeloop/bin/lint`
Expected: all passed; clean; `arena lint: clean`.

- [ ] **Step 4: Commit**

```bash
git add .timeloop/README.md .timeloop/ARENA.md
git commit -m "docs: describe the headless research driver"
```

- [ ] **Step 5: Gate 2 — one real turn, operator present**

Run: `bin/research --max-turns 1`
Then read `.timeloop/driver/briefs/<id>.md`, `.timeloop/driver/results/<id>.json`, and `git show --stat HEAD`. Confirm the outcome class matches what the diff shows. If the turn is `invalid` for a runner reason (schema, files_mismatch caused by the recorder, revert of an allowed path), fix the driver before continuing; if it is `invalid` for a model reason, note it and continue.

- [ ] **Step 6: Gate 3 — supervised three-turn batch including a forage**

Run: `bin/research --max-turns 3`
If no forage turn occurred, run `bin/research --max-turns 2` again until one has. Read every frame filed in `.timeloop/frames.jsonl` and check its source URL resolves.

- [ ] **Step 7: Gate 4 — two-hour supervised soak**

Run: `bin/research --max-hours 2`
Then: `bin/research status`. The gate passes when productive share over the run is at least 0.2 and no `invalid` turn has an `invalid_reason` in {`files_mismatch`, `schema`, `lint`} attributable to the driver rather than the model. Record the numbers in a ledger `EXT | driver | soak |` line by hand.

- [ ] **Step 8: Gate 5 — first unattended overnight run**

Run in tmux: `bin/research --max-hours 8`
Next morning: `bin/research status`, `git log --oneline | head -40`, and read the ledger tail. Append an `EXT | driver | overnight |` ledger line with yield by kind and anything the adversarial lane overturned.
