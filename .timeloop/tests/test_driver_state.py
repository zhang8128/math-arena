from __future__ import annotations

import json
import sys
from pathlib import Path

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
