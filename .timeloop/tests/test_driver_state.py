from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TIMELOOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TIMELOOP))

from driver.state import (  # noqa: E402
    PRODUCTIVE,
    Frame,  # noqa: F401
    State,  # noqa: F401
    Target,  # noqa: F401
    TurnRecord,  # noqa: F401
    append_jsonl,
    load_state,
    next_turn_id,
    read_jsonl,
    validate_frame,
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
        "# Ledger\n\nT7 | a | nothing | tried\n\n"
        "EXT | a | deposit | x\n\n"
        "T12 | b | negative | ruled out n<10\n"
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


def test_load_state_ignores_frames_rejected_event(tmp_path: Path) -> None:
    """C1 regression: a rejected-frame event carries `event`, not `turn_id`, and
    must never reach `_turn`, which would KeyError on the missing `kind` field
    and wedge every later `load_state` call until a human edits the log by hand."""
    root = make_room(tmp_path)
    (root / "driver" / "turns.jsonl").write_text(
        json.dumps({"turn_id": "T13", "kind": "attack", "target": "a", "frames": ["f1"],
                    "outcome": "nothing", "refinement": False, "ledger_line": None,
                    "files_changed": [], "frames_filed": [], "started": "2026-09-02T00:00:00Z",
                    "seconds": 1.0, "base_commit": "abc", "exit_reason": "completed",
                    "invalid_reason": None, "brief_digest": "d", "template_digest": "t"}) + "\n"
        + json.dumps({"event": "frames_rejected", "turn": "T14", "reasons": ["bad"]}) + "\n"
    )
    s = load_state(root)  # must not raise KeyError
    assert [t.turn_id for t in s.turns] == ["T13"]


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
    expected = {
        "negative",
        "structure",
        "correction",
        "verified",
        "counterexample",
        "frames",
    }
    assert PRODUCTIVE == expected
    records = read_jsonl(root / "pool.jsonl")
    records[0]["status"] = "parked"
    write_pool(root, records)
    assert read_jsonl(root / "pool.jsonl")[0]["status"] == "parked"
    assert read_jsonl(root / "pool.jsonl")[0]["slug"] == "a"


def test_validate_frame_requires_url_outside_pool_and_own() -> None:
    base = {"slug": "s", "title": "t", "statement": "p", "shape": ["x"]}
    arxiv_frame = {
        **base,
        "source": {"kind": "arxiv", "id": "1", "url": "https://arxiv.org/abs/1"},
    }
    ok = validate_frame(arxiv_frame, set())
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
