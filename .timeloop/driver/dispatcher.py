"""Selection rules. Pure functions of state, config, and turn index.

The sudoku rule lives here: change angle before target, change target
before grinding. Nothing in this module runs a model or touches the network.
"""

from __future__ import annotations

import dataclasses
import random
from pathlib import Path

from driver.config import DriverConfig
from driver.state import (
    PRODUCTIVE,
    Frame,
    State,
    Target,
    TurnRecord,
    load_state,
    next_turn_id,
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
                seen = frames_seen(state, t.slug)
                unseen = [f for f in eligible_frames(state, t) if f.slug not in seen]
                if unseen:
                    out.append(t)
    return out


def _frame_for(
    state: State, config: DriverConfig, target: Target, rng: random.Random
) -> Frame | None:
    tail_target, run = tail_run(state)
    eligible = eligible_frames(state, target)
    seen = frames_seen(state, target.slug)
    # A frame that was productive on this target is reserved for combine,
    # unless the last turn on the target was a correction, which reopens it.
    history = target_turns(state, target.slug)
    reopened = bool(history) and history[-1].outcome == "correction"
    reserved = set() if reopened else {
        f.slug for f in state.frames
        if any(
            a.get("target") == target.slug and str(a.get("outcome")) in PRODUCTIVE
            for a in f.applied_to
        )
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


def _pick_target(
    state: State, config: DriverConfig, turn_index: int, rng: random.Random
) -> Target | None:
    candidates = _eligible_targets(state, config, turn_index)
    if not candidates:
        return None
    if rng.random() < config.exploration_floor:
        return candidates[rng.randrange(len(candidates))]
    def last_outcome(t: Target) -> str | None:
        turns = target_turns(state, t.slug)
        return turns[-1].outcome if turns else None
    with_next = [
        t for t in candidates
        if _notebook_next(state, t.slug) and last_outcome(t) in PRODUCTIVE
    ]
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
    prev_collision = (
        turn_index > 1
        and (turn_index - 1) % config.patrol_period == 0
        and (turn_index - 1) % config.adversarial_period == 0
    )
    if turn_index % config.adversarial_period == 0 or prev_collision:
        claim = _adversarial_claim(state, rng)
        return Brief(turn_id, "adversarial", None, (), None, claim, False, "scheduled adversarial")
    kind = _draw_kind(config, rng)
    if kind == "forage-frontier":
        cats = config.arxiv_categories
        category = cats[turn_index % len(cats)]
        return Brief(turn_id, kind, None, (), category, None, False, "frontier forage by rotation")
    if kind == "forage-target":
        parked = [t for t in state.targets if t.status == "parked"]
        if parked:
            latest = max(parked, key=lambda t: int(t.raw.get("cooldown_until", 0)))  # type: ignore[call-overload]
            reason = "most recently parked target"
            return Brief(turn_id, kind, latest.slug, (), None, None, False, reason)
        if not state.targets:
            return Brief(turn_id, kind, None, (), None, None, False, "empty pool")
        fewest = min(state.targets, key=lambda t: (len(eligible_frames(state, t)), t.slug))
        return Brief(turn_id, kind, fewest.slug, (), None, None, False, "fewest eligible frames")
    target = _pick_target(state, config, turn_index, rng)
    if target is None:
        return Brief(turn_id, "forage-target", None, (), None, None, False, "no eligible target")
    if kind == "combine":
        pair = _combine_pair(state, target, rng)
        if pair is not None:
            revive = target.status == "parked"
            return Brief(turn_id, "combine", target.slug, pair, None, None, revive, "combine")
        kind = "attack"
    frame = _frame_for(state, config, target, rng)
    if frame is None:
        reason = "no unseen eligible frame"
        return Brief(turn_id, "forage-target", target.slug, (), None, None, False, reason)
    revive = target.status == "parked"
    return Brief(turn_id, "attack", target.slug, (frame.slug,), None, None, revive, "attack")
