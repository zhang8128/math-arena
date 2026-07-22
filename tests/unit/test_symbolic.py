from mathloop.methods.symbolic import SymbolicInductionMethod


def test_sum_of_odds_produces_an_induction_certificate() -> None:
    result = SymbolicInductionMethod().prove_sum_odds()

    assert result.status == "candidate"
    assert result.witness == {"certificate": "sum_odds_induction", "base": 0, "step": 0}
    assert result.claim == "the sum of the first n positive odd integers equals n^2"
