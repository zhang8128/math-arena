"""Driver configuration. Every value has a default; config.json overrides."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any


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
    values: dict[str, Any] = {
        k: tuple(v) if k in _TUPLE_FIELDS else v for k, v in raw.items()
    }
    return DriverConfig(**values)
