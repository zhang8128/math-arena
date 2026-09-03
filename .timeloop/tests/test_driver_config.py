from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TIMELOOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TIMELOOP))

from driver.config import DriverConfig, load_config  # noqa: E402


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
