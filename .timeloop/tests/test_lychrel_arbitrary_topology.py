from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from lychrel_arbitrary_topology import (  # noqa: E402
    ColumnConstraint,
    DigitAtom,
    build_column_constraints,
    render_arbitrary,
)
from lychrel_wordproof import ParametricWord  # noqa: E402


def test_renderer_maps_repeats_but_not_fixed_occurrences() -> None:
    word = ParametricWord(17, ((3,), (4,), (5,)), (0, 16))

    rendered = render_arbitrary((word,), 0, 1, 20)

    assert rendered == (
        DigitAtom("p0:f0:d0"),
        DigitAtom(None, 0),
        DigitAtom("p0:f1:d0"),
        DigitAtom(None, 19),
        DigitAtom("p0:f2:d0"),
    )


def test_column_constraint_is_hand_derived() -> None:
    words = (
        ParametricWord(17, ((3, 5),), ()),
        ParametricWord(17, ((8, 8),), ()),
    )

    constraints = build_column_constraints(
        words,
        20,
        parameters=(0,),
        phases=(0,),
    )

    assert constraints[0] == ColumnConstraint(
        left=DigitAtom("p0:f0:d0"),
        right=DigitAtom("p0:f0:d1"),
        target=DigitAtom("p1:f0:d1"),
        carry_in=None,
        carry_out="c:p0:n0:col0",
        provenance="phase=0,n=0,column=0",
    )


def test_wrap_transition_targets_the_incremented_parameter() -> None:
    words = (
        ParametricWord(17, ((1,), (2,)), (0,)),
        ParametricWord(17, ((3,), (4,)), (16,)),
    )

    constraints = build_column_constraints(
        words,
        20,
        parameters=(0,),
        phases=(1,),
    )

    assert len(constraints) == 3
    assert constraints[1].target == DigitAtom(None, 0)


def test_compiler_rejects_invalid_base_phase_and_parameter() -> None:
    words = (ParametricWord(17, ((1,),), ()),)

    for kwargs in (
        {"base": 16},
        {"base": 17, "parameters": (-1,)},
        {"base": 17, "phases": (1,)},
    ):
        try:
            build_column_constraints(words, **kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for {kwargs}")
