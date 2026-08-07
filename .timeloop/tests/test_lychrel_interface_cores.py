from __future__ import annotations

import gc
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


ROOT = Path(__file__).resolve().parents[2]


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
