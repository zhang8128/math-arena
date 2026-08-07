from __future__ import annotations

import gc
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runs"))

from lychrel_arbitrary_topology import (  # noqa: E402
    compile_grouped_one_hot_cnf,
    compile_one_hot_cnf,
)
from lychrel_interface_perturbations import (  # noqa: E402
    InterfaceMove,
    move_interface,
    n_zero_relevant_moves,
)
from lychrel_wordproof import ParametricWord  # noqa: E402
from t22_lychrel_affine_lift import base17_reference_cycle  # noqa: E402
from t25_lychrel_interface_perturbations_independent import BinaryCNF  # noqa: E402
import t26_radial_frontier as radial_frontier  # noqa: E402
from t26_lychrel_interface_cores import (  # noqa: E402
    discover_variant_families,
    extract_hybrid_core,
    verify_hybrid_core,
)
from t26_radial_frontier import (  # noqa: E402
    replay_radial_witness,
    solve_radial_frontier,
)


ROOT = Path(__file__).resolve().parents[2]


class _FakeSolver:
    def __init__(self, status: object, model: object | None = None) -> None:
        self.status = status
        self.saved_model = model

    def check(self) -> object:
        return self.status

    def model(self) -> object:
        return self.saved_model

    def reason_unknown(self) -> str:
        return "test-unknown"


def base19_radial_candidate() -> tuple[str, ...]:
    return radial_frontier.base19_candidate_provenances()


def test_checked_model_distinguishes_exact_solver_statuses() -> None:
    sat = object()
    unsat = object()

    class FakeZ3:
        pass

    FakeZ3.sat = sat
    FakeZ3.unsat = unsat
    model = {"digit": 7}

    assert radial_frontier._checked_model(
        FakeZ3,
        _FakeSolver(sat, model),
    ) == model
    assert radial_frontier._checked_model(
        FakeZ3,
        _FakeSolver(unsat),
    ) is None
    with pytest.raises(radial_frontier.ExactSolverError, match="test-unknown"):
        radial_frontier._checked_model(
            FakeZ3,
            _FakeSolver(object()),
        )


def test_certificate_mode_exports_sorted_states_matching_digests() -> None:
    pytest.importorskip("z3")
    words = (
        ParametricWord(2, ((1, 1),), ()),
        ParametricWord(2, ((1, 1),), ()),
    )
    provenances = (
        "phase=0,n=0,column=0",
        "phase=0,n=0,column=1",
        "phase=1,n=0,column=0",
        "phase=1,n=0,column=1",
    )

    evidence = solve_radial_frontier(
        words,
        2,
        provenances,
        include_certificate=True,
    )

    for layer in evidence["layers"]:
        assert len(layer["equation_provenances"]) == layer["equation_count"]
        assert layer["input_variables"] == sorted(layer["input_variables"])
        assert layer["output_variables"] == sorted(layer["output_variables"])
        assert layer["output_states"] == sorted(layer["output_states"])
        payload = json.dumps(
            layer["output_states"],
            separators=(",", ":"),
        ).encode("ascii")
        assert hashlib.sha256(payload).hexdigest() == layer["output_states_sha256"]


def test_base19_candidate_coordinates_have_frozen_digest() -> None:
    candidate = radial_frontier.base19_candidate_provenances()

    assert len(candidate) == len(set(candidate)) == 409
    assert candidate[0] == "phase=0,n=0,column=0"
    assert candidate[-1] == "phase=5,n=0,column=83"
    payload = "".join(f"{item}\n" for item in candidate).encode("utf-8")
    assert hashlib.sha256(payload).hexdigest() == (
        "df743120f7733a45a946ee006a2d7301634e472b8b23ecef197641fee3ee080b"
    )


@pytest.fixture(scope="module")
def group_mus_binary(tmp_path_factory: pytest.TempPathFactory) -> Path:
    binary = tmp_path_factory.mktemp("t26-group-mus") / "t26_group_mus"
    subprocess.run(
        (
            "clang++",
            "-std=c++17",
            "-O2",
            str(ROOT / ".timeloop" / "runs" / "t26_group_mus.cpp"),
            "-I/opt/homebrew/opt/cadical/include",
            "/opt/homebrew/opt/cadical/lib/libcadical.a",
            "-o",
            str(binary),
        ),
        check=True,
        text=True,
        capture_output=True,
    )
    return binary


def run_group_mus_fixture(
    binary: Path,
    tmp_path: Path,
    mode: str,
) -> dict[str, object]:
    formula = tmp_path / "fixture.cnf"
    selectors = tmp_path / "selectors.txt"
    formula.write_text(
        "p cnf 4 3\n"
        "-2 1 0\n"
        "-3 -1 0\n"
        "-4 1 -1 0\n",
        encoding="utf-8",
    )
    selectors.write_text("2\n3\n4\n", encoding="utf-8")
    completed = subprocess.run(
        (str(binary), str(formula), str(selectors), mode),
        check=True,
        text=True,
        capture_output=True,
    )
    assert completed.stderr == ""
    return json.loads(completed.stdout)


def test_group_mus_client_extracts_unique_irreducible_core(
    group_mus_binary: Path,
    tmp_path: Path,
) -> None:
    evidence = run_group_mus_fixture(group_mus_binary, tmp_path, "extract")

    assert evidence["status"] == "UNSAT"
    assert evidence["input_variables"] == 4
    assert evidence["input_clauses"] == 3
    assert evidence["requested_selectors"] == [2, 3, 4]
    assert evidence["core_selectors"] == [2, 3]
    assert evidence["deletion_statuses"] == [
        {"selector": 2, "status": "SAT"},
        {"selector": 3, "status": "SAT"},
    ]
    assert evidence["solve_calls"] >= 3
    assert evidence["cadical_version"]
    assert evidence["deletion_algorithm"] == "parallel-batch-ddmin"
    assert evidence["worker_count"] == 8


def test_group_mus_client_verifies_requested_nonminimal_set(
    group_mus_binary: Path,
    tmp_path: Path,
) -> None:
    evidence = run_group_mus_fixture(group_mus_binary, tmp_path, "verify")

    assert evidence["status"] == "UNSAT"
    assert evidence["core_selectors"] == [2, 3, 4]
    assert evidence["deletion_statuses"] == [
        {"selector": 2, "status": "SAT"},
        {"selector": 3, "status": "SAT"},
        {"selector": 4, "status": "UNSAT"},
    ]


def test_group_mus_client_returns_failed_assumption_seed(
    group_mus_binary: Path,
    tmp_path: Path,
) -> None:
    evidence = run_group_mus_fixture(group_mus_binary, tmp_path, "seed")

    assert evidence["status"] == "UNSAT"
    assert evidence["core_selectors"] == [2, 3]
    assert evidence["deletion_statuses"] == []
    assert evidence["solve_calls"] == 1


@pytest.mark.parametrize(
    ("formula_text", "selector_text", "mode"),
    (
        ("p cnf 4 2\n-2 1 0\n", "2\n", "extract"),
        ("p cnf 4 1\n-2 5 0\n", "2\n", "extract"),
        ("p cnf 4 1\n-2 1 0\n1\n", "2\n", "extract"),
        ("p cnf 4 1\n-2 1 0\n", "0\n", "extract"),
        ("p cnf 4 1\n-2 1 0\n", "5\n", "extract"),
        ("p cnf 4 1\n-2 1 0\n", "2\n2\n", "extract"),
        ("p cnf 4 1\n-2 1 0\n", "2\n", "minimize"),
    ),
)
def test_group_mus_client_rejects_malformed_inputs_without_json(
    group_mus_binary: Path,
    tmp_path: Path,
    formula_text: str,
    selector_text: str,
    mode: str,
) -> None:
    formula = tmp_path / "malformed.cnf"
    selectors = tmp_path / "malformed-selectors.txt"
    formula.write_text(formula_text, encoding="utf-8")
    selectors.write_text(selector_text, encoding="utf-8")

    completed = subprocess.run(
        (str(group_mus_binary), str(formula), str(selectors), mode),
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stdout == ""
    assert completed.stderr.startswith("t26_group_mus: ")


def test_bounded_family_discovery_is_complete_irreducible_and_deterministic(
    group_mus_binary: Path,
) -> None:
    words = base17_reference_cycle()
    move = InterfaceMove(0, 0, -2)

    def fixed_certificate(*args: object) -> dict[str, object]:
        certificate = {
            "status": "UNSAT",
            "deletion_statuses": ["SAT"],
        }
        return {
            "base": 18,
            "seed_size": 1,
            "core_size": 1,
            "core_provenances": ["phase=0,n=0,column=0"],
            "binary_certificate": certificate,
            "one_hot_certificate": certificate,
        }

    first = discover_variant_families(
        words,
        move,
        (18,),
        group_mus_binary,
        extract_core=fixed_certificate,
    )
    second = discover_variant_families(
        words,
        move,
        (18,),
        group_mus_binary,
        extract_core=fixed_certificate,
    )

    assert first == second
    assert first["variant_id"] == "phase0-interface0-minus2"
    assert first["bases"] == [18]
    assert first["uncovered_bases"] == []
    families = first["families"]
    assert families[0]["representative_base"] == 18
    assigned = [base for family in families for base in family["covered_bases"]]
    assert assigned == [18]
    assert len(assigned) == len(set(assigned))
    for family in families:
        assert family["core_size"] == len(family["core_provenances"])
        assert family["core_size"] > 0
        for verification in family["verifications"]:
            for encoding in ("binary_certificate", "one_hot_certificate"):
                certificate = verification[encoding]
                assert certificate["status"] == "UNSAT"
                assert set(certificate["deletion_statuses"]) == {"SAT"}
        assert len(family["canonical_incidence_sha256"]) == 64


def test_hybrid_base18_core_matches_binary_and_one_hot_certificates(
    group_mus_binary: Path,
) -> None:
    evidence = extract_hybrid_core(
        base17_reference_cycle(),
        InterfaceMove(0, 0, -2),
        18,
        group_mus_binary,
    )

    assert evidence["seed_size"] == 158
    assert evidence["core_size"] == 156
    assert evidence["binary_certificate"]["status"] == "UNSAT"
    assert set(evidence["binary_certificate"]["deletion_statuses"]) == {"SAT"}
    assert evidence["one_hot_certificate"]["status"] == "UNSAT"
    assert set(evidence["one_hot_certificate"]["deletion_statuses"]) == {"SAT"}
    assert evidence["columns_by_phase"] == {
        "0": [[1, 12], [69, 82]],
        "1": [[0, 12], [70, 82]],
        "2": [[0, 12], [70, 82]],
        "3": [[0, 12], [70, 82]],
        "4": [[0, 12], [70, 82]],
        "5": [[0, 12], [71, 83]],
    }


def test_base18_band_core_does_not_persist_unchanged_at_base19(
    group_mus_binary: Path,
) -> None:
    bands = {
        0: ((1, 12), (69, 82)),
        1: ((0, 12), (70, 82)),
        2: ((0, 12), (70, 82)),
        3: ((0, 12), (70, 82)),
        4: ((0, 12), (70, 82)),
        5: ((0, 12), (71, 83)),
    }
    provenances = tuple(
        f"phase={phase},n=0,column={column}"
        for phase, ranges in bands.items()
        for start, stop in ranges
        for column in range(start, stop + 1)
    )

    evidence = verify_hybrid_core(
        base17_reference_cycle(),
        InterfaceMove(0, 0, -2),
        19,
        provenances,
        group_mus_binary,
    )

    assert evidence["core_size"] == 156
    assert evidence["binary_certificate"]["status"] == "SAT"
    assert evidence["binary_certificate"]["deletion_statuses"] == []
    assert evidence["one_hot_certificate"]["status"] == "SAT"
    assert evidence["one_hot_certificate"]["deletion_statuses"] == []


def test_base19_radial_frontier_proves_409_column_candidate_unsat() -> None:
    pytest.importorskip("z3")
    moved = move_interface(
        base17_reference_cycle(),
        InterfaceMove(0, 0, -2),
    )

    evidence = solve_radial_frontier(
        moved,
        19,
        base19_radial_candidate(),
    )

    assert evidence["status"] == "UNSAT"
    assert evidence["equation_count"] == 409
    assert evidence["active_digit_count"] == 409
    assert evidence["active_carry_count"] == 410
    assert evidence["max_frontier_digit_count"] == 2
    assert evidence["max_frontier_carry_count"] == 12
    assert evidence["max_reachable_state_count"] == 314
    assert evidence["layers"][0]["layer"] == -1
    assert evidence["layers"][0]["output_state_count"] == 1
    assert evidence["layers"][-1]["layer"] == 33
    assert evidence["layers"][-1]["output_state_count"] == 0
    assert "witness" not in evidence


def test_base19_radial_frontier_reconstructs_exact_deletion_witness() -> None:
    pytest.importorskip("z3")
    moved = move_interface(
        base17_reference_cycle(),
        InterfaceMove(0, 0, -2),
    )
    deletion = "phase=0,n=0,column=0"
    provenances = tuple(
        provenance
        for provenance in base19_radial_candidate()
        if provenance != deletion
    )

    evidence = solve_radial_frontier(
        moved,
        19,
        provenances,
        include_witness=True,
    )

    assert evidence["status"] == "SAT"
    assert evidence["equation_count"] == 408
    assert evidence["max_reachable_state_count"] == 1480
    assert evidence["layers"][-1]["output_state_count"] == 1
    assert replay_radial_witness(
        moved,
        19,
        provenances,
        evidence["witness"],
    ) == {
        "status": "valid",
        "equation_count": 408,
        "digit_count": 409,
        "carry_count": 410,
    }


def test_grouped_formula_keeps_domains_hard_and_groups_exact_columns() -> None:
    words = (
        ParametricWord(2, ((1, 1),), ()),
        ParametricWord(2, ((1, 1),), ()),
    )

    grouped = compile_grouped_one_hot_cnf(words, 2, parameters=(0,))
    ordinary = compile_one_hot_cnf(words, 2, parameters=(0,))

    assert grouped.selector_keys == (
        "selector:phase=0,n=0,column=0",
        "selector:phase=0,n=0,column=1",
        "selector:phase=1,n=0,column=0",
        "selector:phase=1,n=0,column=1",
    )
    assert tuple(group.provenance for group in grouped.groups) == (
        "phase=0,n=0,column=0",
        "phase=0,n=0,column=1",
        "phase=1,n=0,column=0",
        "phase=1,n=0,column=1",
    )
    assert grouped.hard_clauses[:2] == ordinary.clauses[:2]
    assert tuple(
        clause
        for group in grouped.groups
        for clause in group.clauses
    ) == ordinary.clauses[len(grouped.hard_clauses) :]
    assert grouped.hard_clauses + tuple(
        clause for group in grouped.groups for clause in group.clauses
    ) == ordinary.clauses


def test_binary_column_ranges_preserve_t25_formula_bytes(tmp_path: Path) -> None:
    moved = move_interface(
        base17_reference_cycle(),
        InterfaceMove(0, 0, -2),
    )
    phases = [
        {
            "fragments": [list(fragment) for fragment in word.fragments],
            "repeats": list(word.repeats),
        }
        for word in moved
    ]
    formula = BinaryCNF(18, phases)
    formula.build()

    assert len(formula.column_groups) == 499
    assert formula.column_groups[0][1] == formula.hard_clause_count
    assert formula.column_groups[-1][2] == len(formula.clauses)
    for (_, start, stop), (_, next_start, _) in zip(
        formula.column_groups,
        formula.column_groups[1:],
    ):
        assert start < stop
        assert stop == next_start
    path = tmp_path / "binary.cnf"
    assert formula.dimacs_digest_and_write(path) == (
        "8e720f877b10aa0496422b789978b110bda52f2f54de2e0d9be4f71dc0378f8a"
    )


def test_guarded_formula_uses_negative_selectors_and_appends_variables() -> None:
    words = (
        ParametricWord(2, ((1, 1),), ()),
        ParametricWord(2, ((1, 1),), ()),
    )

    grouped = compile_grouped_one_hot_cnf(words, 2, parameters=(0,))
    guarded = grouped.guarded_formula()
    ids = guarded.variable_ids

    assert guarded.semantic_keys == grouped.semantic_keys + grouped.selector_keys
    assert guarded.clauses[: len(grouped.hard_clauses)] == grouped.hard_clauses
    offset = len(grouped.hard_clauses)
    for group, selector_key in zip(grouped.groups, grouped.selector_keys):
        selector = ids[selector_key]
        expected = tuple((-selector,) + clause for clause in group.clauses)
        assert guarded.clauses[offset : offset + len(expected)] == expected
        offset += len(expected)
    assert offset == len(guarded.clauses)


@pytest.mark.parametrize(
    ("move", "expected_digest"),
    (
        (InterfaceMove(0, 0, -2), "114c55b40fcfcef70b19250c4c0a279c91b4eafe419066b71113ab07a93845ec"),
        (InterfaceMove(0, 0, -1), "6e9fc9b1b2f5fc96b21f087ca20d7735da7255d642612c6718ebc461749309f1"),
        (InterfaceMove(0, 0, 1), "0d5148b585e172ba086fc0e79e2daea225c42516b991cad3578b475e11477e88"),
        (InterfaceMove(0, 0, 2), "2944bb1a83b598beeaeae046fd97f486c313409f472731302d2966a86f271265"),
        (InterfaceMove(0, 1, -2), "bb19ec526234f438b7950e3aa5163f16a144460e1fa72cdec10ed439dcc0fa88"),
        (InterfaceMove(0, 1, -1), "d88676c283407763185ea03ca5cc99bfdaae6c95310ec11edd09a59e775217d3"),
        (InterfaceMove(0, 1, 1), "7040edd74f66a873968055ecba8c15f5b44728285cc8774cfa1500b79812360c"),
        (InterfaceMove(0, 1, 2), "d477cf31995d78fd7514b70cd8b5fd25993249c32671ddcf64a04cd962ab040f"),
    ),
)
def test_grouped_t25_formula_preserves_every_base18_clause(
    move: InterfaceMove,
    expected_digest: str,
) -> None:
    words = base17_reference_cycle()
    assert move in n_zero_relevant_moves(words)
    moved = move_interface(words, move)

    ordinary = compile_one_hot_cnf(moved, 18, parameters=(0,))
    grouped = compile_grouped_one_hot_cnf(moved, 18, parameters=(0,))
    guarded = grouped.guarded_formula()

    assert ordinary.digest == expected_digest
    assert len(grouped.groups) == 499
    assert len(set(group.provenance for group in grouped.groups)) == 499
    assert grouped.hard_clauses + tuple(
        clause for group in grouped.groups for clause in group.clauses
    ) == ordinary.clauses
    offset = len(grouped.hard_clauses)
    for group in grouped.groups:
        guarded_group = guarded.clauses[offset : offset + len(group.clauses)]
        assert tuple(clause[1:] for clause in guarded_group) == group.clauses
        offset += len(group.clauses)
    assert offset == len(guarded.clauses)
    del ordinary, grouped, guarded
    gc.collect()
