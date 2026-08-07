from __future__ import annotations

import gc
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
