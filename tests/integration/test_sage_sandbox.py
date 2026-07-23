import pytest

from mathloop.provenance import SAGE_IMAGE_DIGEST
from mathloop.tools.docker import DockerLimits, DockerRunner

SAGE_EMULATION_TIMEOUT_SECONDS = 60


@pytest.mark.integration
def test_sage_runner_returns_exact_factorization() -> None:
    runner = DockerRunner(
        image=SAGE_IMAGE_DIGEST,
        # Cold amd64-on-arm emulation can exceed the standard 20-second budget.
        limits=DockerLimits(
            seconds=SAGE_EMULATION_TIMEOUT_SECONDS,
            memory_mb=512,
            cpus=1.0,
        ),
    )
    result = runner.run_json({"operation": "factor", "value": 1681})
    assert result == {"ok": True, "factors": [[41, 2]]}
    induction = runner.run_json({"operation": "verify_sum_odds_induction"})
    assert induction == {"ok": True, "base": True, "step": True}
    integer_sum = runner.run_json({"operation": "verify_sum_integers_induction"})
    assert integer_sum == {"ok": True, "base": True, "step": True}
    witness = runner.run_json(
        {
            "operation": "find_integer_counterexample",
            "predicate_id": "euler_prime",
            "start": 0,
            "stop": 100,
            "order": "ascending",
        }
    )
    assert witness == {
        "ok": True,
        "found": True,
        "n": 40,
        "value": 1681,
    }
    for predicate_id in ("sum_odds", "sum_integers"):
        bounded = runner.run_json(
            {
                "operation": "find_integer_counterexample",
                "predicate_id": predicate_id,
                "start": 0,
                "stop": 100,
                "order": "ascending",
            }
        )
        assert bounded == {"ok": True, "found": False}
