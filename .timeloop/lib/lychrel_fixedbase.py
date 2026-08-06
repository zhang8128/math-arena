"""Exact fixed-base transplants of a reference reverse-add topology."""

from __future__ import annotations

from dataclasses import dataclass

from lychrel_anchor_csp import (
    AnchorVariable,
    CarryEquation,
    solve_boolean_equations,
)
from lychrel_wordproof import (
    ParametricWord,
    fixed_palindrome_mismatch,
    verify_cycle,
)


@dataclass(frozen=True)
class _FixedDigit:
    value: int
    variable: str | None


@dataclass(frozen=True)
class FixedBaseClassification:
    base: int
    status: str
    parameters_checked: tuple[int, ...]
    equation_count: int
    variable_count: int
    solution_count: int
    cycle: tuple[ParametricWord, ...] | None
    polynomial_verified: bool
    nonpalindrome_witnesses: tuple[tuple[int, int, int], ...]


def _reference_base(words: tuple[ParametricWord, ...]) -> int:
    if not words:
        raise ValueError("at least one reference phase is required")
    reference_base = words[0].base
    if any(word.base != reference_base for word in words):
        raise ValueError("all reference phases must use one base")
    return reference_base


def _render_symbolic(
    word: ParametricWord,
    phase: int,
    n: int,
    base: int,
) -> tuple[_FixedDigit, ...]:
    result = []
    for fragment_index, fragment in enumerate(word.fragments):
        if fragment_index:
            repeat = word.repeats[fragment_index - 1]
            value = (base - 1) if repeat == word.base - 1 else 0
            result.extend(_FixedDigit(value, None) for _ in range(n))
        result.extend(
            _FixedDigit(
                digit,
                AnchorVariable(phase, fragment_index, offset).key,
            )
            for offset, digit in enumerate(fragment)
        )
    return tuple(result)


def build_fixed_base_carry_equations(
    words: tuple[ParametricWord, ...],
    base: int,
    *,
    parameters: range = range(3),
    phases: tuple[int, ...] | None = None,
) -> tuple[CarryEquation, ...]:
    """Compile fresh Boolean carries for concrete interpolation parameters."""
    reference_base = _reference_base(words)
    if base < reference_base:
        raise ValueError("base must not be below the reference base")
    selected_phases = tuple(range(len(words))) if phases is None else phases
    if any(phase < 0 or phase >= len(words) for phase in selected_phases):
        raise ValueError("phase is outside the reference cycle")
    parameter_values = tuple(parameters)
    if any(n < 0 for n in parameter_values):
        raise ValueError("parameters must be nonnegative")
    delta = base - reference_base
    equations = []
    for phase in selected_phases:
        word = words[phase]
        for n in parameter_values:
            source = _render_symbolic(word, phase, n, base)
            next_phase = (phase + 1) % len(words)
            output_n = n + int(phase == len(words) - 1)
            output = _render_symbolic(
                words[next_phase],
                next_phase,
                output_n,
                base,
            )
            if len(output) not in (len(source), len(source) + 1):
                raise ValueError("reference transition has an invalid length change")
            for column in range(len(output)):
                if column < len(source):
                    left = source[len(source) - 1 - column]
                    right = source[column]
                else:
                    left = right = _FixedDigit(0, None)
                target = output[len(output) - 1 - column]
                constant = left.value + right.value - target.value
                terms = []
                for digit, coefficient in (
                    (left, delta),
                    (right, delta),
                    (target, -delta),
                ):
                    if digit.variable is not None and coefficient:
                        terms.append((digit.variable, coefficient))
                if column:
                    terms.append((f"c:p{phase}:n{n}:col{column - 1}", 1))
                if column + 1 < len(output):
                    terms.append((f"c:p{phase}:n{n}:col{column}", -base))
                equations.append(
                    CarryEquation(
                        tuple(terms),
                        -constant,
                        provenance=f"phase={phase},n={n},column={column}",
                    )
                )
    return tuple(equations)


def materialize_fixed_base_cycle(
    words: tuple[ParametricWord, ...],
    base: int,
    assignment: dict[str, int],
) -> tuple[ParametricWord, ...]:
    """Apply independent lower/upper anchors at one fixed base."""
    reference_base = _reference_base(words)
    if base < reference_base:
        raise ValueError("base must not be below the reference base")
    delta = base - reference_base
    materialized = []
    for phase, word in enumerate(words):
        fragments = tuple(
            tuple(
                digit
                + delta
                * assignment.get(
                    AnchorVariable(phase, fragment_index, offset).key,
                    0,
                )
                for offset, digit in enumerate(fragment)
            )
            for fragment_index, fragment in enumerate(word.fragments)
        )
        repeats = tuple(
            (base - 1) if repeat == reference_base - 1 else 0
            for repeat in word.repeats
        )
        materialized.append(ParametricWord(base, fragments, repeats))
    return tuple(materialized)


def _variable_count(equations: tuple[CarryEquation, ...]) -> int:
    return len(
        {
            variable
            for equation in equations
            for variable, _ in equation.terms
        }
    )


def classify_fixed_base_transplant(
    words: tuple[ParametricWord, ...],
    base: int,
) -> FixedBaseClassification:
    """Decide exact identity feasibility for one lower/upper transplant base."""
    n_zero = build_fixed_base_carry_equations(
        words,
        base,
        parameters=range(1),
    )
    if not solve_boolean_equations(n_zero):
        return FixedBaseClassification(
            base=base,
            status="infeasible",
            parameters_checked=(0,),
            equation_count=len(n_zero),
            variable_count=_variable_count(n_zero),
            solution_count=0,
            cycle=None,
            polynomial_verified=False,
            nonpalindrome_witnesses=(),
        )

    equations = build_fixed_base_carry_equations(words, base)
    solutions = solve_boolean_equations(equations)
    if not solutions:
        return FixedBaseClassification(
            base=base,
            status="infeasible",
            parameters_checked=(0, 1, 2),
            equation_count=len(equations),
            variable_count=_variable_count(equations),
            solution_count=0,
            cycle=None,
            polynomial_verified=False,
            nonpalindrome_witnesses=(),
        )

    cycle = materialize_fixed_base_cycle(words, base, solutions[0])
    polynomial_verified = verify_cycle(cycle)
    witnesses = tuple(
        witness
        for word in cycle
        if (witness := fixed_palindrome_mismatch(word)) is not None
    )
    if not polynomial_verified:
        status = "verification_failure"
    elif len(witnesses) != len(cycle):
        status = "identity_without_nonpalindrome_certificate"
    else:
        status = "verified_transplant"
    return FixedBaseClassification(
        base=base,
        status=status,
        parameters_checked=(0, 1, 2),
        equation_count=len(equations),
        variable_count=_variable_count(equations),
        solution_count=1,
        cycle=cycle,
        polynomial_verified=polynomial_verified,
        nonpalindrome_witnesses=witnesses,
    )
