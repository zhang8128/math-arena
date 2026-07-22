import json
from datetime import UTC, datetime
from uuid import uuid4

from mathloop.config import Settings
from mathloop.domain import Problem, ProblemStatus
from mathloop.methods.base import MethodContext
from mathloop.methods.sage import SagePolynomialMethod


class RecordingRunner:
    def __init__(self) -> None:
        self.payloads: list[dict[str, object]] = []

    def run_json(self, payload: dict[str, object]) -> dict[str, object]:
        self.payloads.append(payload)
        return {"ok": True, "factors": [[41, 2]]}


def _problem() -> Problem:
    return Problem(
        id=uuid4(),
        source_id="test",
        source_uri="local://test",
        source_hash="hash",
        statement="factor a value",
        normalized_statement="factor a value",
        domain="number_theory",
        features={},
        checker={"kind": "factor"},
        status=ProblemStatus.ELIGIBLE,
        cohort="development",
        version=1,
        created_at=datetime.now(UTC),
    )


def test_sage_method_wraps_only_the_allowlisted_factor_operation(tmp_path) -> None:
    runner = RecordingRunner()
    settings = Settings(artifact_root=tmp_path / "artifacts", incoming_root=tmp_path / "incoming")
    method = SagePolynomialMethod(settings, runner=runner)
    context = MethodContext(
        problem=_problem(),
        seed=0,
        config={"value": 1681, "source": "print('arbitrary generated code')"},
    )

    result = method.run(context)

    assert runner.payloads == [{"operation": "factor", "value": 1681}]
    assert result.status == "completed"
    assert json.loads(result.artifact or b"{}") == {"ok": True, "factors": [[41, 2]]}
    assert result.claim is None
