from __future__ import annotations

import json
import sys
from pathlib import Path

TIMELOOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TIMELOOP))

from driver.config import DriverConfig  # noqa: E402
from driver.dispatcher import (  # noqa: E402
    apply_stalls,
    eligible_frames,
    frames_seen,
    productive_frame_slugs,
    stall_reason,
    tail_run,
    target_turns,
    unpark,
)
from driver.state import load_state, read_jsonl  # noqa: E402


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
        {
            "slug": "a", "track": "open", "tags": ["x", "y"], "priority": 1,
            "title": "A", "statement": "s", "status": "open",
        },
        {
            "slug": "b", "track": "open", "tags": ["z"], "priority": 2,
            "title": "B", "statement": "s", "status": "open",
        },
    ]
    (root / "pool.jsonl").write_text("".join(json.dumps(p) + "\n" for p in pool))
    frames = [
        {
            "slug": "fx", "title": "", "statement": "", "shape": ["x"],
            "source": {"kind": "pool"}, "filed_by": "seed",
            "applied_to": [{"target": "b", "turn": "T1", "outcome": "negative"}],
            "superseded_by": None,
        },
        {
            "slug": "fy", "title": "", "statement": "", "shape": ["y"],
            "source": {"kind": "pool"}, "filed_by": "seed",
            "applied_to": [], "superseded_by": None,
        },
        {
            "slug": "fg", "title": "", "statement": "", "shape": ["*"],
            "source": {"kind": "pool"}, "filed_by": "seed",
            "applied_to": [], "superseded_by": None,
        },
        {
            "slug": "fold", "title": "", "statement": "", "shape": ["x"],
            "source": {"kind": "pool"}, "filed_by": "seed",
            "applied_to": [], "superseded_by": "fx",
        },
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
    expected = "3 consecutive non-productive turns: T1,T3,T4"
    assert stall_reason(load_state(root), "a", cfg) == expected
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
    rec = next(r for r in read_jsonl(root / "pool.jsonl") if r["slug"] == "a")
    assert rec["status"] == "open" and "cooldown_until" not in rec
    assert rec["parked_reason"].startswith("3 consecutive")  # history kept
