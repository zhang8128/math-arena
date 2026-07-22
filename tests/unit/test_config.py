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
