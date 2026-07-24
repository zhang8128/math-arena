from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from mathloop.codex.domain import (
    CodexModelRole,
    CodexPolicy,
    CodexTurnReceipt,
    CodexTurnReservation,
    CodexUsage,
)


def test_default_codex_policy_matches_approved_envelope() -> None:
    policy = CodexPolicy()
    assert policy.daily_turn_limit == 100
    assert policy.concurrent_turn_limit == 4
    assert policy.turn_timeout_seconds == 1800
    assert policy.model_turn_limits == {"luna": 40, "terra": 40, "sol": 20}
    assert policy.reserved_sol_turns == 10


def test_codex_receipt_is_bound_to_the_reservation() -> None:
    reservation = CodexTurnReservation(
        id=uuid4(),
        experiment_id=uuid4(),
        budget_day=date(2026, 7, 23),
        role=CodexModelRole.TERRA,
        model="gpt-5.6-terra",
        deadline_seconds=1800,
        created_at=datetime.now(UTC),
    )
    receipt = CodexTurnReceipt(
        reservation_id=reservation.id,
        experiment_id=reservation.experiment_id,
        thread_id="thread-1",
        model=reservation.model,
        cli_version="0.145.0",
        usage=CodexUsage(
            input_tokens=100,
            cached_input_tokens=20,
            output_tokens=30,
            reasoning_output_tokens=10,
        ),
        final_status="completed",
    )
    assert receipt.reservation_id == reservation.id
    with pytest.raises(ValidationError):
        CodexTurnReceipt.model_validate(
            {
                **receipt.model_dump(mode="python"),
                "final_status": "invented",
            }
        )
