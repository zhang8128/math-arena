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
