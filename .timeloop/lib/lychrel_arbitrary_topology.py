"""Exact finite-domain constraints for one fixed reverse-add topology."""

from __future__ import annotations

from dataclasses import dataclass

from lychrel_wordproof import ParametricWord


@dataclass(frozen=True)
class DigitAtom:
    variable: str | None
    value: int | None = None

    def __post_init__(self) -> None:
        if (self.variable is None) == (self.value is None):
            raise ValueError("a digit atom must be exactly one of variable or value")


@dataclass(frozen=True)
class ColumnConstraint:
    left: DigitAtom
    right: DigitAtom
    target: DigitAtom
    carry_in: str | None
    carry_out: str | None
    provenance: str


def _reference_base(words: tuple[ParametricWord, ...]) -> int:
    if not words:
        raise ValueError("at least one phase is required")
    base = words[0].base
    if any(word.base != base for word in words):
        raise ValueError("all phases must use one reference base")
    return base


def _digit_key(phase: int, fragment: int, offset: int) -> str:
    return f"p{phase}:f{fragment}:d{offset}"


def render_arbitrary(
    words: tuple[ParametricWord, ...],
    phase: int,
    n: int,
    base: int,
) -> tuple[DigitAtom, ...]:
    """Render fixed occurrences as variables and repeats as target-base digits."""
    reference_base = _reference_base(words)
    if base < reference_base:
        raise ValueError("base must not be below the reference base")
    if phase < 0 or phase >= len(words):
        raise ValueError("phase is outside the reference cycle")
    if n < 0:
        raise ValueError("parameter must be nonnegative")
    word = words[phase]
    rendered: list[DigitAtom] = []
    for fragment_index, fragment in enumerate(word.fragments):
        if fragment_index:
            repeat = word.repeats[fragment_index - 1]
            value = base - 1 if repeat == reference_base - 1 else 0
            rendered.extend(DigitAtom(None, value) for _ in range(n))
        rendered.extend(
            DigitAtom(_digit_key(phase, fragment_index, offset))
            for offset in range(len(fragment))
        )
    return tuple(rendered)


def build_column_constraints(
    words: tuple[ParametricWord, ...],
    base: int,
    *,
    parameters: tuple[int, ...] = (0,),
    phases: tuple[int, ...] | None = None,
) -> tuple[ColumnConstraint, ...]:
    """Compile exact least-significant-first reverse-add columns."""
    reference_base = _reference_base(words)
    if base < reference_base:
        raise ValueError("base must not be below the reference base")
    if any(n < 0 for n in parameters):
        raise ValueError("parameters must be nonnegative")
    selected = tuple(range(len(words))) if phases is None else phases
    if any(phase < 0 or phase >= len(words) for phase in selected):
        raise ValueError("phase is outside the reference cycle")

    constraints: list[ColumnConstraint] = []
    zero = DigitAtom(None, 0)
    for phase in selected:
        for n in parameters:
            source = render_arbitrary(words, phase, n, base)
            next_phase = (phase + 1) % len(words)
            output_n = n + int(phase == len(words) - 1)
            output = render_arbitrary(words, next_phase, output_n, base)
            if len(output) not in (len(source), len(source) + 1):
                raise ValueError("transition has an invalid length change")
            for column in range(len(output)):
                if column < len(source):
                    left = source[column]
                    right = source[len(source) - 1 - column]
                else:
                    left = right = zero
                constraints.append(
                    ColumnConstraint(
                        left=left,
                        right=right,
                        target=output[len(output) - 1 - column],
                        carry_in=(
                            f"c:p{phase}:n{n}:col{column - 1}"
                            if column
                            else None
                        ),
                        carry_out=(
                            f"c:p{phase}:n{n}:col{column}"
                            if column + 1 < len(output)
                            else None
                        ),
                        provenance=f"phase={phase},n={n},column={column}",
                    )
                )
    return tuple(constraints)
