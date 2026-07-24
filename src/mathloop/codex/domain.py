"""Codex domain types for turn accounting, policy, and receipts."""

from datetime import date, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field

from mathloop.domain import FrozenModel


class CodexModelRole(StrEnum):
    """Model roles for Codex turn dispatch."""

    LUNA = "luna"
    TERRA = "terra"
    SOL = "sol"


class CodexTurnStatus(StrEnum):
    """Status lifecycle for a Codex turn."""

    RESERVED = "reserved"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    AMBIGUOUS = "ambiguous"


class CodexPolicy(FrozenModel):
    """Turn and resource policy for Codex supervised execution."""

    daily_turn_limit: int = Field(default=100, ge=1)
    concurrent_turn_limit: int = Field(default=4, ge=1)
    turn_timeout_seconds: int = Field(default=1800, ge=60)
    model_turn_limits: dict[str, int] = Field(
        default_factory=lambda: {"luna": 40, "terra": 40, "sol": 20}
    )
    reserved_sol_turns: int = Field(default=10, ge=0)
    max_jsonl_bytes: int = Field(default=16 * 1024 * 1024, ge=1024)
    max_patch_bytes: int = Field(default=4 * 1024 * 1024, ge=1024)


class CodexUsage(FrozenModel):
    """Token usage from a Codex turn."""

    input_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    reasoning_output_tokens: int = Field(ge=0)


class CodexTurnReservation(FrozenModel):
    """Reserved slot for a Codex turn before dispatch."""

    id: UUID
    experiment_id: UUID
    budget_day: date
    role: CodexModelRole
    model: str = Field(min_length=1)
    deadline_seconds: int = Field(ge=60)
    created_at: datetime


class CodexTurnReceipt(FrozenModel):
    """Immutable record of a completed Codex turn."""

    reservation_id: UUID
    experiment_id: UUID
    thread_id: str = Field(min_length=1)
    model: str = Field(min_length=1)
    cli_version: str = Field(min_length=1)
    usage: CodexUsage
    final_status: Literal["completed"]
