import pytest

from mathloop.tools.docker import DockerLimits, DockerRunner


@pytest.mark.integration
def test_sage_runner_returns_exact_factorization() -> None:
    runner = DockerRunner(
        image="mathloop-sage:10.9",
        limits=DockerLimits(seconds=20, memory_mb=512, cpus=1.0),
    )
    result = runner.run_json({"operation": "factor", "value": 1681})
    assert result == {"ok": True, "factors": [[41, 2]]}
    induction = runner.run_json({"operation": "verify_sum_odds_induction"})
    assert induction == {"ok": True, "base": True, "step": True}
