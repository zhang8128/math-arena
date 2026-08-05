"""Boolean carry constraints for affine lifts of parametric reverse-add cycles."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from lychrel_affine import AffineDigit, AffineWord, verify_affine_cycle
from lychrel_wordproof import ParametricWord


@dataclass(frozen=True, order=True)
class AnchorVariable:
    phase: int
    fragment: int
    digit: int

    @property
    def key(self) -> str:
        return f"p{self.phase}:f{self.fragment}:d{self.digit}"


@dataclass(frozen=True)
class CarryEquation:
    terms: tuple[tuple[str, int], ...]
    rhs: int
    provenance: str

    def __post_init__(self) -> None:
        combined: dict[str, int] = {}
        for variable, coefficient in self.terms:
            if not variable:
                raise ValueError("variable names must be nonempty")
            if not isinstance(coefficient, int):
                raise ValueError("coefficients must be integers")
            combined[variable] = combined.get(variable, 0) + coefficient
        normalized = tuple(
            (variable, coefficient)
            for variable, coefficient in sorted(combined.items())
            if coefficient
        )
        object.__setattr__(self, "terms", normalized)
        if not isinstance(self.rhs, int):
            raise ValueError("rhs must be an integer")
        if not self.provenance:
            raise ValueError("provenance must be nonempty")


@dataclass(frozen=True)
class LiftClassification:
    status: str
    equation_count: int
    unique_equation_count: int
    solution_count: int
    cycles: tuple[tuple[AffineWord, ...], ...]
    unsat_core: tuple[CarryEquation, ...]


@dataclass(frozen=True)
class _SymbolicDigit:
    reference_value: int
    variable: str | None
    fixed_slope: int


def _equation_assignments(
    equation: CarryEquation,
    domains: dict[str, set[int]],
) -> tuple[tuple[int, ...], ...]:
    variables = tuple(variable for variable, _ in equation.terms)
    coefficients = tuple(coefficient for _, coefficient in equation.terms)
    return tuple(
        values
        for values in product(*(sorted(domains[variable]) for variable in variables))
        if sum(
            coefficient * value
            for coefficient, value in zip(coefficients, values)
        )
        == equation.rhs
    )


def _propagate(
    equations: tuple[CarryEquation, ...],
    domains: dict[str, set[int]],
) -> dict[str, set[int]] | None:
    changed = True
    while changed:
        changed = False
        for equation in equations:
            if not equation.terms:
                if equation.rhs != 0:
                    return None
                continue
            assignments = _equation_assignments(equation, domains)
            if not assignments:
                return None
            for index, (variable, _) in enumerate(equation.terms):
                supported = {values[index] for values in assignments}
                narrowed = domains[variable] & supported
                if not narrowed:
                    return None
                if narrowed != domains[variable]:
                    domains[variable] = narrowed
                    changed = True
    return domains


def solve_boolean_equations(
    equations: tuple[CarryEquation, ...],
    *,
    limit: int = 1,
) -> tuple[dict[str, int], ...]:
    if limit < 1:
        raise ValueError("limit must be positive")
    variables = sorted(
        {variable for equation in equations for variable, _ in equation.terms}
    )
    frequencies = {
        variable: sum(
            variable in {item for item, _ in equation.terms}
            for equation in equations
        )
        for variable in variables
    }
    solutions: list[dict[str, int]] = []

    def visit(domains: dict[str, set[int]]) -> None:
        if len(solutions) >= limit:
            return
        reduced = _propagate(
            equations,
            {variable: set(values) for variable, values in domains.items()},
        )
        if reduced is None:
            return
        unresolved = [
            variable for variable in variables if len(reduced[variable]) > 1
        ]
        if not unresolved:
            solutions.append(
                {variable: next(iter(reduced[variable])) for variable in variables}
            )
            return
        chosen = min(unresolved, key=lambda item: (-frequencies[item], item))
        for value in sorted(reduced[chosen]):
            branch = {
                variable: set(values) for variable, values in reduced.items()
            }
            branch[chosen] = {value}
            visit(branch)

    visit({variable: {0, 1} for variable in variables})
    return tuple(solutions)


def irreducible_unsat_core(
    equations: tuple[CarryEquation, ...],
) -> tuple[CarryEquation, ...]:
    if solve_boolean_equations(equations):
        raise ValueError("equations are feasible")
    core = list(equations)
    index = 0
    while index < len(core):
        trial = tuple(core[:index] + core[index + 1 :])
        if not solve_boolean_equations(trial):
            core.pop(index)
        else:
            index += 1
    result = tuple(core)
    if solve_boolean_equations(result):
        raise AssertionError("core unexpectedly became feasible")
    if any(
        not solve_boolean_equations(result[:index] + result[index + 1 :])
        for index in range(len(result))
    ):
        raise AssertionError("core is not deletion-irreducible")
    return result


def _render_symbolic(
    word: ParametricWord,
    phase: int,
    n: int,
) -> tuple[_SymbolicDigit, ...]:
    result = [
        _SymbolicDigit(
            digit,
            AnchorVariable(phase, 0, offset).key,
            0,
        )
        for offset, digit in enumerate(word.fragments[0])
    ]
    for fragment_index, (repeat, fragment) in enumerate(
        zip(word.repeats, word.fragments[1:]),
        start=1,
    ):
        repeat_slope = int(repeat == word.base - 1)
        result.extend(
            _SymbolicDigit(repeat, None, repeat_slope) for _ in range(n)
        )
        result.extend(
            _SymbolicDigit(
                digit,
                AnchorVariable(phase, fragment_index, offset).key,
                0,
            )
            for offset, digit in enumerate(fragment)
        )
    return tuple(result)


def _add_term(
    terms: list[tuple[str, int]],
    digit: _SymbolicDigit,
    coefficient: int,
) -> int:
    if digit.variable is not None:
        terms.append((digit.variable, coefficient))
        return 0
    return coefficient * digit.fixed_slope


def build_carry_equations(
    words: tuple[ParametricWord, ...],
    *,
    parameters: range = range(4),
) -> tuple[CarryEquation, ...]:
    if not words:
        raise ValueError("at least one phase is required")
    base = words[0].base
    if any(word.base != base for word in words):
        raise ValueError("all phases must use one reference base")
    equations = []
    for phase, word in enumerate(words):
        for n in parameters:
            if n < 0:
                raise ValueError("parameters must be nonnegative")
            source = _render_symbolic(word, phase, n)
            next_phase = (phase + 1) % len(words)
            output_n = n + int(phase == len(words) - 1)
            output = _render_symbolic(words[next_phase], next_phase, output_n)
            if len(output) not in (len(source), len(source) + 1):
                raise ValueError("reference transition has an invalid length change")
            carry = 0
            for column in range(len(output)):
                if column < len(source):
                    left = source[len(source) - 1 - column]
                    right = source[column]
                else:
                    left = _SymbolicDigit(0, None, 0)
                    right = _SymbolicDigit(0, None, 0)
                target = output[len(output) - 1 - column]
                total = left.reference_value + right.reference_value + carry
                if total % base != target.reference_value:
                    raise ValueError("reference transition digit mismatch")
                carry_out = total // base
                terms: list[tuple[str, int]] = []
                fixed_slope = 0
                fixed_slope += _add_term(terms, left, 1)
                fixed_slope += _add_term(terms, right, 1)
                fixed_slope += _add_term(terms, target, -1)
                equations.append(
                    CarryEquation(
                        tuple(terms),
                        carry_out - fixed_slope,
                        provenance=f"phase={phase},n={n},column={column}",
                    )
                )
                carry = carry_out
            if carry:
                raise ValueError("reference transition leaves an unconsumed carry")
    return tuple(equations)


def materialize_affine_cycle(
    words: tuple[ParametricWord, ...],
    assignment: dict[str, int],
) -> tuple[AffineWord, ...]:
    result = []
    for phase, word in enumerate(words):
        fragments = tuple(
            tuple(
                AffineDigit(
                    digit,
                    assignment[AnchorVariable(phase, fragment_index, offset).key],
                    word.base,
                )
                for offset, digit in enumerate(fragment)
            )
            for fragment_index, fragment in enumerate(word.fragments)
        )
        repeats = tuple(int(repeat == word.base - 1) for repeat in word.repeats)
        result.append(AffineWord(fragments, repeats))
    return tuple(result)


def classify_affine_lift(
    words: tuple[ParametricWord, ...],
) -> LiftClassification:
    equations = build_carry_equations(words)
    unique_by_content: dict[
        tuple[tuple[tuple[str, int], ...], int], CarryEquation
    ] = {}
    for equation in equations:
        unique_by_content.setdefault(
            (equation.terms, equation.rhs),
            equation,
        )
    unique = tuple(unique_by_content.values())
    solutions = solve_boolean_equations(unique, limit=2)
    if not solutions:
        return LiftClassification(
            status="infeasible",
            equation_count=len(equations),
            unique_equation_count=len(unique),
            solution_count=0,
            cycles=(),
            unsat_core=irreducible_unsat_core(unique),
        )
    cycles = tuple(
        cycle
        for assignment in solutions
        if verify_affine_cycle(
            cycle := materialize_affine_cycle(words, assignment)
        )
    )
    return LiftClassification(
        status="verified_lift" if cycles else "candidates_rejected",
        equation_count=len(equations),
        unique_equation_count=len(unique),
        solution_count=len(solutions),
        cycles=cycles,
        unsat_core=(),
    )
