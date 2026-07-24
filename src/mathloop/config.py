from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from mathloop.billing import validate_database_usd


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MATHLOOP_", env_file=".env")

    database_url: str = "postgresql://mathloop:mathloop@localhost:55432/mathloop"
    artifact_root: Path = Path(".mathloop/artifacts")
    incoming_root: Path = Path("data/incoming")
    daily_api_budget_usd: Decimal = Field(default=Decimal("5.0"), gt=0)
    max_experiment_seconds: int = Field(default=300, gt=0)
    lease_seconds: int = Field(default=420, gt=0)
    max_container_memory_mb: int = Field(default=1024, ge=128)
    max_container_cpus: float = Field(default=1.0, gt=0)
    openai_model_scout: str = "gpt-5.6-luna"
    openai_model_reasoner: str = "gpt-5.6-terra"
    openai_model_escalation: str = "gpt-5.6-sol"
    max_model_output_tokens: int = Field(default=4096, ge=128, le=128_000)
    max_api_cost_usd_per_experiment: Decimal = Field(default=Decimal("1.0"), gt=0)

    # Codex settings
    codex_enabled: bool = False
    codex_cli_path: Path = Path("codex")
    codex_repo_root: Path = Path(".")
    codex_worktree_root: Path = Path(".mathloop/codex-worktrees")
    codex_daily_turn_limit: int = Field(default=100, ge=1)
    codex_concurrent_turn_limit: int = Field(default=4, ge=1)
    codex_turn_timeout_seconds: int = Field(default=1800, ge=60)
    codex_luna_turn_limit: int = Field(default=40, ge=0)
    codex_terra_turn_limit: int = Field(default=40, ge=0)
    codex_sol_turn_limit: int = Field(default=20, ge=0)
    codex_reserved_sol_turns: int = Field(default=10, ge=0)
    codex_model_luna: str = "gpt-5.6-luna"
    codex_model_terra: str = "gpt-5.6-terra"
    codex_model_sol: str = "gpt-5.6-sol"
    codex_min_cli_version: str = "0.145.0"

    @model_validator(mode="after")
    def validate_runtime(self) -> "Settings":
        self.artifact_root = self.artifact_root.expanduser().resolve()
        self.incoming_root = self.incoming_root.expanduser().resolve()
        self.codex_repo_root = self.codex_repo_root.expanduser().resolve()
        self.codex_worktree_root = self.codex_worktree_root.expanduser().resolve()
        if self.lease_seconds <= self.max_experiment_seconds:
            raise ValueError("lease_seconds must exceed max_experiment_seconds")
        validate_database_usd(
            self.daily_api_budget_usd,
            field_name="daily_api_budget_usd",
            positive=True,
        )
        validate_database_usd(
            self.max_api_cost_usd_per_experiment,
            field_name="max_api_cost_usd_per_experiment",
            positive=True,
        )
        # Validate Codex settings
        role_limits_sum = (
            self.codex_luna_turn_limit
            + self.codex_terra_turn_limit
            + self.codex_sol_turn_limit
        )
        if role_limits_sum != self.codex_daily_turn_limit:
            raise ValueError(
                f"codex role limits (luna={self.codex_luna_turn_limit}, "
                f"terra={self.codex_terra_turn_limit}, "
                f"sol={self.codex_sol_turn_limit}) must sum to "
                f"codex_daily_turn_limit={self.codex_daily_turn_limit}"
            )
        if self.codex_reserved_sol_turns > self.codex_sol_turn_limit:
            raise ValueError(
                f"codex_reserved_sol_turns={self.codex_reserved_sol_turns} "
                f"cannot exceed codex_sol_turn_limit={self.codex_sol_turn_limit}"
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
