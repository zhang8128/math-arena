from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    @model_validator(mode="after")
    def validate_runtime(self) -> "Settings":
        self.artifact_root = self.artifact_root.expanduser().resolve()
        self.incoming_root = self.incoming_root.expanduser().resolve()
        if self.lease_seconds <= self.max_experiment_seconds:
            raise ValueError("lease_seconds must exceed max_experiment_seconds")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
