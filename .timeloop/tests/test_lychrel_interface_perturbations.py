from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runs"))

from lychrel_arbitrary_topology import (  # noqa: E402
    DigitAtom,
    build_column_constraints,
)
from lychrel_interface_perturbations import (  # noqa: E402
    InterfaceMove,
    all_moves,
    move_interface,
    n_zero_relevant_moves,
)
from lychrel_wordproof import ParametricWord  # noqa: E402
from t22_lychrel_affine_lift import base17_reference_cycle  # noqa: E402


def test_positive_shift_moves_boundary_right_by_literal_columns() -> None:
    words = (
        ParametricWord(
            17,
            ((1, 2, 3), (4, 5, 6), (7, 8)),
            (0, 16),
        ),
    )

    moved = move_interface(words, InterfaceMove(0, 0, 2))

    assert moved == (
        ParametricWord(
            17,
            ((1, 2, 3, 4, 5), (6,), (7, 8)),
            (0, 16),
        ),
    )


def test_negative_shift_moves_boundary_left_and_preserves_order() -> None:
    words = (
        ParametricWord(
            17,
            ((1, 2, 3), (4, 5, 6), (7, 8)),
            (0, 16),
        ),
    )

    moved = move_interface(words, InterfaceMove(0, 1, -1))

    assert moved[0].fragments == ((1, 2, 3), (4, 5), (6, 7, 8))
    assert moved[0].repeats == (0, 16)
    assert tuple(digit for fragment in moved[0].fragments for digit in fragment) == (
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
    )


@pytest.mark.parametrize(
    "move",
    (
        InterfaceMove(0, 0, 0),
        InterfaceMove(-1, 0, 1),
        InterfaceMove(1, 0, 1),
        InterfaceMove(0, -1, 1),
        InterfaceMove(0, 2, 1),
        InterfaceMove(0, 0, 3),
        InterfaceMove(0, 0, -2),
    ),
)
def test_invalid_or_empty_fragment_moves_are_rejected(move: InterfaceMove) -> None:
    words = (ParametricWord(17, ((1,), (2, 3), (4,)), (0, 16)),)

    with pytest.raises(ValueError):
        move_interface(words, move)


def test_t21_enumeration_has_48_moves_and_eight_relevant_moves() -> None:
    words = base17_reference_cycle()

    moves = all_moves(words, max_shift=2)
    relevant = n_zero_relevant_moves(words, max_shift=2)

    assert len(moves) == 48
    assert len(set(moves)) == 48
    assert {move.phase for move in relevant} == {0}
    assert {(move.interface, move.shift) for move in relevant} == {
        (interface, shift)
        for interface in (0, 1)
        for shift in (-2, -1, 1, 2)
    }


def _digit_renaming(words: tuple[ParametricWord, ...]) -> dict[str, str]:
    names = {}
    for phase, word in enumerate(words):
        flat = 0
        for fragment_index, fragment in enumerate(word.fragments):
            for offset in range(len(fragment)):
                names[f"p{phase}:f{fragment_index}:d{offset}"] = (
                    f"p{phase}:flat{flat}"
                )
                flat += 1
    return names


def _canonical_atom(atom: DigitAtom, names: dict[str, str]) -> tuple[str, object]:
    if atom.variable is not None:
        return ("variable", names[atom.variable])
    return ("constant", atom.value)


def _canonical_n_zero_columns(
    words: tuple[ParametricWord, ...],
) -> tuple[tuple[object, ...], ...]:
    names = _digit_renaming(words)
    return tuple(
        (
            _canonical_atom(column.left, names),
            _canonical_atom(column.right, names),
            _canonical_atom(column.target, names),
            column.carry_in,
            column.carry_out,
            column.provenance,
        )
        for column in build_column_constraints(words, 17, parameters=(0,))
    )


def test_only_phase_zero_moves_change_the_canonical_n_zero_system() -> None:
    words = base17_reference_cycle()
    baseline = _canonical_n_zero_columns(words)

    for move in all_moves(words, max_shift=2):
        changed = _canonical_n_zero_columns(move_interface(words, move)) != baseline
        assert changed is (move.phase == 0), move
