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


import dataclasses  # noqa: E402

from driver.dispatcher import Brief, select  # noqa: E402, F401
from driver.state import State, Target, next_turn_id  # noqa: E402, F401


def with_next(root: Path, slug: str) -> State:
    """Load state and inject a NEXT line for one target, as the loop does from index.md."""
    s = load_state(root)
    targets = tuple(
        dataclasses.replace(t, raw={**t.raw, "_next": "try the other residue"})
        if t.slug == slug else t
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
    cfg = DriverConfig(
        combine_share=0.0, forage_target_share=0.0, forage_frontier_share=0.0, exploration_floor=0.0
    )
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
    cfg = DriverConfig(
        combine_share=0.0, forage_target_share=0.0, forage_frontier_share=0.0, exploration_floor=0.0
    )
    root = room(tmp_path, [
        turn("T1", "attack", "a", ["fx"], "negative"),
        turn("T2", "attack", "a", ["fy"], "negative"),
        turn("T3", "attack", "a", ["fg"], "negative"),
    ])
    assert select(with_next(root, "a"), cfg, 4).target == "b"


def test_parked_target_revives_only_with_unseen_frame(tmp_path: Path) -> None:
    cfg = DriverConfig(
        combine_share=0.0, forage_target_share=0.0, forage_frontier_share=0.0, exploration_floor=0.0
    )
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
    new_frame = {
        "slug": "fz", "title": "", "statement": "", "shape": ["z"], "source": {"kind": "pool"},
        "filed_by": "seed", "applied_to": [], "superseded_by": None,
    }
    (root / "frames.jsonl").open("a").write(json.dumps(new_frame) + "\n")
    b = select(load_state(root), cfg, 6)
    assert b.target == "b" and b.revive and b.frames == ("fz",)


def test_combine_needs_unpaired_productive_frames(tmp_path: Path) -> None:
    cfg = DriverConfig(
        combine_share=1.0, forage_target_share=0.0, forage_frontier_share=0.0, exploration_floor=0.0
    )
    root = room(tmp_path, [])
    frames = read_jsonl(root / "frames.jsonl")
    # fy productive
    frames[1]["applied_to"] = [{"target": "b", "turn": "T1", "outcome": "structure"}]
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
    # the only productive pair is already paired on a; b has one productive frame
    assert b2.kind == "attack"


def test_exploration_floor_and_determinism(tmp_path: Path) -> None:
    cfg = DriverConfig(combine_share=0.0, forage_target_share=0.0, forage_frontier_share=0.0)
    root = room(tmp_path, [turn("T1", "attack", "a", ["fx"], "negative")])
    # a has a concrete NEXT and a productive last turn, so it wins outside the floor
    s = with_next(root, "a")
    picks = [select(s, cfg, i).target for i in range(1, 1001) if i % 10 != 0 and i % 25 != 0]
    share_b = picks.count("b") / len(picks)
    assert 0.06 < share_b < 0.16   # half of the 20% floor lands on b
    assert select(s, cfg, 3) == select(s, cfg, 3)
    assert next_turn_id(s) == select(s, cfg, 3).turn_id


def test_first_turn_is_not_a_phantom_collision(tmp_path: Path) -> None:
    cfg = DriverConfig(combine_share=0.0, forage_target_share=0.0, forage_frontier_share=0.0)
    root = room(tmp_path, [])
    assert select(load_state(root), cfg, 1).kind == "attack"


def test_forage_target_on_empty_pool_does_not_crash(tmp_path: Path) -> None:
    cfg = DriverConfig(combine_share=0.0, forage_target_share=1.0, forage_frontier_share=0.0)
    root = room(tmp_path, [])
    (root / "pool.jsonl").write_text("")
    b = select(load_state(root), cfg, 2)
    assert b.kind == "forage-target" and b.target is None and b.reason == "empty pool"
