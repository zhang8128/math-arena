from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from mathloop.config import Settings


def test_settings_require_positive_budgets(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql://mathloop:mathloop@localhost:55432/mathloop",
            artifact_root=tmp_path,
            daily_api_budget_usd=0,
            max_experiment_seconds=30,
            lease_seconds=60,
        )


def test_settings_create_absolute_artifact_root(tmp_path: Path) -> None:
    settings = Settings(
        database_url="postgresql://mathloop:mathloop@localhost:55432/mathloop",
        artifact_root=tmp_path / "artifacts",
        daily_api_budget_usd=5,
        max_experiment_seconds=30,
        lease_seconds=60,
    )
    assert settings.artifact_root.is_absolute()
    assert settings.lease_seconds > settings.max_experiment_seconds
    assert isinstance(settings.daily_api_budget_usd, Decimal)
    assert isinstance(settings.max_api_cost_usd_per_experiment, Decimal)


@pytest.mark.parametrize(
    "field",
    ["DAILY_API_BUDGET_USD", "MAX_API_COST_USD_PER_EXPERIMENT"],
)
@pytest.mark.parametrize("value", ["0.0000001", "1.0000000"])
def test_settings_reject_cost_caps_beyond_database_precision(
    monkeypatch: pytest.MonkeyPatch, field: str, value: str
) -> None:
    monkeypatch.setenv(f"MATHLOOP_{field}", value)

    with pytest.raises(ValidationError, match="six decimal places"):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_codex_settings_defaults() -> None:
    settings = Settings(
        database_url="postgresql://mathloop:mathloop@localhost:55432/mathloop",
        artifact_root=Path("."),
        daily_api_budget_usd=5,
        max_experiment_seconds=30,
        lease_seconds=60,
    )
    assert settings.codex_enabled is False
    assert settings.codex_cli_path == Path("codex")
    assert settings.codex_repo_root.is_absolute()
    assert settings.codex_worktree_root.is_absolute()
    assert settings.codex_daily_turn_limit == 100
    assert settings.codex_concurrent_turn_limit == 4
    assert settings.codex_turn_timeout_seconds == 1800
    assert settings.codex_luna_turn_limit == 40
    assert settings.codex_terra_turn_limit == 40
    assert settings.codex_sol_turn_limit == 20
    assert settings.codex_reserved_sol_turns == 10
    assert settings.codex_model_luna == "gpt-5.6-luna"
    assert settings.codex_model_terra == "gpt-5.6-terra"
    assert settings.codex_model_sol == "gpt-5.6-sol"
    assert settings.codex_min_cli_version == "0.145.0"


def test_codex_role_limits_must_sum_to_daily_limit() -> None:
    with pytest.raises(
        ValidationError,
        match=r"codex role limits.*must sum to codex_daily_turn_limit",
    ):
        Settings(
            database_url="postgresql://mathloop:mathloop@localhost:55432/mathloop",
            artifact_root=Path("."),
            daily_api_budget_usd=5,
            max_experiment_seconds=30,
            lease_seconds=60,
            codex_daily_turn_limit=100,
            codex_luna_turn_limit=40,
            codex_terra_turn_limit=40,
            codex_sol_turn_limit=15,  # Sum is 95, not 100
        )


def test_codex_reserved_sol_turns_cannot_exceed_sol_limit() -> None:
    with pytest.raises(
        ValidationError,
        match=r"codex_reserved_sol_turns.*cannot exceed codex_sol_turn_limit",
    ):
        Settings(
            database_url="postgresql://mathloop:mathloop@localhost:55432/mathloop",
            artifact_root=Path("."),
            daily_api_budget_usd=5,
            max_experiment_seconds=30,
            lease_seconds=60,
            codex_daily_turn_limit=100,
            codex_luna_turn_limit=40,
            codex_terra_turn_limit=40,
            codex_sol_turn_limit=20,
            codex_reserved_sol_turns=25,  # Exceeds sol_turn_limit of 20
        )
