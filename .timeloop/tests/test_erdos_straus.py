from __future__ import annotations

import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

from sympy import factorint

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from erdos_straus import factor_pair_solutions, first_solution, first_tame_solution, is_decomposition


def test_exact_decomposition_predicate() -> None:
    assert is_decomposition(5, 2, 4, 20)
    assert not is_decomposition(5, 2, 4, 19)
    assert not is_decomposition(5, 0, 4, 20)


def test_even_positive_control() -> None:
    for n in range(2, 100, 2):
        assert is_decomposition(n, n // 2, n, n)


def test_three_mod_four_positive_control() -> None:
    for n in range(3, 100, 4):
        assert is_decomposition(n, (n + 1) // 4, n * (n + 1) // 2, n * (n + 1) // 2)


def test_new_wild_candidates_have_nontame_decompositions() -> None:
    decompositions = (
        (5_212_561, 1_303_143, 617_519_307_252, 7_640_493_702_695_576_827_004),
        (8_813_281, 2_203_321, 6_472_829_035_494, 447_304_438_314_532_718_777_574),
    )
    for n, x, y, z in decompositions:
        assert is_decomposition(n, x, y, z)
        q = n * x
        assert q % y or q % z


def test_factor_pair_generator_matches_bruteforce_for_small_n() -> None:
    for n in range(2, 30):
        for x in range((n + 3) // 4, (3 * n) // 4 + 1):
            got = set(factor_pair_solutions(n, x))
            residual_numerator = 4 * x - n
            if residual_numerator <= 0:
                want: set[tuple[int, int]] = set()
            else:
                max_y = (2 * n * x) // residual_numerator
                want = set()
                for y in range(x, max_y + 1):
                    remainder = Fraction(4, n) - Fraction(1, x) - Fraction(1, y)
                    if remainder > 0 and remainder.numerator == 1:
                        z = remainder.denominator
                        if y <= z:
                            want.add((y, z))
            assert got == want


def test_factor_pair_generator_accepts_precomputed_factorization() -> None:
    for n in range(2, 30):
        for x in range((n + 3) // 4, n // 2 + 1):
            assert factor_pair_solutions(
                n,
                x,
                q_factorization=factorint(n * x),
            ) == factor_pair_solutions(n, x)


def test_first_solution_covers_small_range() -> None:
    for n in range(2, 500):
        solution = first_solution(n)
        assert solution is not None
        assert is_decomposition(n, *solution)


def test_tame_generator_matches_filtered_factor_pairs() -> None:
    for n in (73, 97, 193, 241, 409):
        for x in range((n + 3) // 4, n // 2 + 1):
            q = n * x
            expected = next(
                ((y, z) for y, z in factor_pair_solutions(n, x) if q % y == 0 and q % z == 0),
                None,
            )
            assert first_tame_solution(n, x) == expected


def test_residue_script_emits_exact_scoped_results(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[1] / "runs" / "t19_erdos_residues.py"
    checkpoint = tmp_path / "checkpoint.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--max-m",
            "10",
            "--modulus",
            "840",
            "--checkpoint",
            str(checkpoint),
            "--checkpoint-every",
            "7",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["m_range"] == [1, 10]
    assert payload["prime_n"] == [73, 97, 193, 241]
    assert payload["modulus"] == 840
    assert set(payload) >= {"solutions", "wild", "residue_summary"}
    assert checkpoint.exists()
    for raw_n, solution in payload["solutions"].items():
        n = int(raw_n)
        q = n * solution["x"]
        assert q % solution["y"] == 0
        assert q % solution["z"] == 0


def test_independent_script_rechecks_tame_and_wild_records(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    explorer = root / "runs" / "t19_erdos_residues.py"
    verifier = root / "runs" / "t19_erdos_independent.py"
    results = tmp_path / "results.json"
    subprocess.run(
        [
            sys.executable,
            str(explorer),
            "--max-m",
            "25",
            "--modulus",
            "840",
            "--checkpoint",
            str(results),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    completed = subprocess.run(
        [sys.executable, str(verifier), str(results)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "PASS" in completed.stdout
    assert "range=1..25" in completed.stdout
    assert "identity_checks=1000" in completed.stdout
