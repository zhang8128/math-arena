"""Exact finite-domain constraints for one fixed reverse-add topology."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

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


@dataclass(frozen=True)
class CNFFormula:
    base: int
    parameters: tuple[int, ...]
    clauses: tuple[tuple[int, ...], ...]
    semantic_keys: tuple[str, ...]
    digit_keys: tuple[str, ...]

    @property
    def variable_count(self) -> int:
        return len(self.semantic_keys)

    @property
    def clause_count(self) -> int:
        return len(self.clauses)

    @property
    def variable_ids(self) -> dict[str, int]:
        return {
            semantic: index
            for index, semantic in enumerate(self.semantic_keys, start=1)
        }

    def dimacs_bytes(self) -> bytes:
        lines = [f"p cnf {self.variable_count} {self.clause_count}\n"]
        lines.extend(
            " ".join(str(literal) for literal in clause) + " 0\n"
            if clause
            else "0\n"
            for clause in self.clauses
        )
        return "".join(lines).encode("ascii")

    @property
    def digest(self) -> str:
        digest = sha256()
        digest.update(
            f"p cnf {self.variable_count} {self.clause_count}\n".encode("ascii")
        )
        for clause in self.clauses:
            digest.update(
                (
                    " ".join(str(literal) for literal in clause) + " 0\n"
                    if clause
                    else "0\n"
                ).encode("ascii")
            )
        return digest.hexdigest()


def _reference_base(words: tuple[ParametricWord, ...]) -> int:
    if not words:
        raise ValueError("at least one phase is required")
    base = words[0].base
    if any(word.base != base for word in words):
        raise ValueError("all phases must use one reference base")
    return base


def _digit_key(phase: int, fragment: int, offset: int) -> str:
    return f"p{phase}:f{fragment}:d{offset}"


def _all_digit_keys(words: tuple[ParametricWord, ...]) -> tuple[str, ...]:
    return tuple(
        _digit_key(phase, fragment_index, offset)
        for phase, word in enumerate(words)
        for fragment_index, fragment in enumerate(word.fragments)
        for offset in range(len(fragment))
    )


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


def compile_one_hot_cnf(
    words: tuple[ParametricWord, ...],
    base: int,
    *,
    parameters: tuple[int, ...] = (0,),
) -> CNFFormula:
    """Compile digit domains and exact columns into deterministic CNF."""
    constraints = build_column_constraints(
        words,
        base,
        parameters=parameters,
    )
    digit_keys = _all_digit_keys(words)
    semantic_keys: list[str] = []
    variable_ids: dict[str, int] = {}
    clauses: list[tuple[int, ...]] = []

    def variable(semantic: str) -> int:
        if semantic not in variable_ids:
            semantic_keys.append(semantic)
            variable_ids[semantic] = len(semantic_keys)
        return variable_ids[semantic]

    def digit_variable(key: str, value: int) -> int:
        return variable(f"digit:{key}:value{value}")

    for key in digit_keys:
        domain = tuple(digit_variable(key, value) for value in range(base))
        clauses.append(domain)
        for left in range(base):
            for right in range(left + 1, base):
                clauses.append((-domain[left], -domain[right]))

    for phase, word in enumerate(words):
        if not word.fragments[0]:
            raise ValueError("the first fragment of every phase must be nonempty")
        clauses.append((-digit_variable(_digit_key(phase, 0, 0), 0),))

    for constraint in constraints:
        left_values = (
            range(base)
            if constraint.left.variable is not None
            else (constraint.left.value,)
        )
        right_values = (
            range(base)
            if constraint.right.variable is not None
            else (constraint.right.value,)
        )
        carry_values = (0, 1) if constraint.carry_in is not None else (0,)
        for left_value in left_values:
            for right_value in right_values:
                for carry_in in carry_values:
                    condition: list[int] = []
                    if constraint.left.variable is not None:
                        condition.append(
                            -digit_variable(constraint.left.variable, left_value)
                        )
                    if constraint.right.variable is not None:
                        condition.append(
                            -digit_variable(constraint.right.variable, right_value)
                        )
                    if constraint.carry_in is not None:
                        carry_variable = variable(constraint.carry_in)
                        condition.append(
                            -carry_variable if carry_in else carry_variable
                        )
                    total = left_value + right_value + carry_in
                    target_value = total % base
                    carry_out = total // base
                    if constraint.target.variable is not None:
                        clauses.append(
                            tuple(condition)
                            + (
                                digit_variable(
                                    constraint.target.variable,
                                    target_value,
                                ),
                            )
                        )
                    elif constraint.target.value != target_value:
                        clauses.append(tuple(condition))
                    if constraint.carry_out is not None:
                        output_variable = variable(constraint.carry_out)
                        clauses.append(
                            tuple(condition)
                            + (
                                output_variable if carry_out else -output_variable,
                            )
                        )
                    elif carry_out:
                        clauses.append(tuple(condition))

    return CNFFormula(
        base=base,
        parameters=parameters,
        clauses=tuple(clauses),
        semantic_keys=tuple(semantic_keys),
        digit_keys=digit_keys,
    )


def reference_assignment(
    words: tuple[ParametricWord, ...],
    formula: CNFFormula,
) -> dict[str, bool]:
    """Build the complete known assignment when the formula uses the reference base."""
    reference_base = _reference_base(words)
    if formula.base != reference_base:
        raise ValueError("reference assignment requires the reference base")
    digits = {
        _digit_key(phase, fragment_index, offset): digit
        for phase, word in enumerate(words)
        for fragment_index, fragment in enumerate(word.fragments)
        for offset, digit in enumerate(fragment)
    }
    assignment = {
        f"digit:{key}:value{value}": value == digits[key]
        for key in formula.digit_keys
        for value in range(reference_base)
    }
    for phase, word in enumerate(words):
        for n in formula.parameters:
            source = word.render(n)
            next_phase = (phase + 1) % len(words)
            output_n = n + int(phase == len(words) - 1)
            output = words[next_phase].render(output_n)
            carry = 0
            for column in range(len(output)):
                if column < len(source):
                    total = source[column] + source[-1 - column] + carry
                else:
                    total = carry
                if output[-1 - column] != total % reference_base:
                    raise ValueError("reference words do not satisfy a transition")
                carry = total // reference_base
                if column + 1 < len(output):
                    assignment[f"c:p{phase}:n{n}:col{column}"] = bool(carry)
                elif carry:
                    raise ValueError("reference transition leaves an unconsumed carry")
    missing = set(formula.semantic_keys) - assignment.keys()
    if missing:
        raise ValueError(f"reference assignment misses variables: {sorted(missing)[:3]}")
    return assignment


def assignment_satisfies(
    formula: CNFFormula,
    assignment: dict[str, bool],
) -> bool:
    """Evaluate every CNF clause under a complete semantic assignment."""
    if any(key not in assignment for key in formula.semantic_keys):
        return False
    values = (False,) + tuple(assignment[key] for key in formula.semantic_keys)
    return all(
        any(values[abs(literal)] == (literal > 0) for literal in clause)
        for clause in formula.clauses
    )


def decode_digit_assignment(
    formula: CNFFormula,
    model: tuple[bool | None, ...],
) -> dict[str, int]:
    """Decode exactly one selected value for every fixed occurrence."""
    if len(model) <= formula.variable_count:
        raise ValueError("SAT model is shorter than the formula variable range")
    variable_ids = formula.variable_ids
    digits: dict[str, int] = {}
    for key in formula.digit_keys:
        selected = [
            value
            for value in range(formula.base)
            if model[variable_ids[f"digit:{key}:value{value}"]]
        ]
        if len(selected) != 1:
            raise ValueError(f"digit {key} does not have exactly one value")
        digits[key] = selected[0]
    return digits


def materialize_cycle(
    words: tuple[ParametricWord, ...],
    base: int,
    digits: dict[str, int],
) -> tuple[ParametricWord, ...]:
    """Replace every fixed occurrence and map repeat extremes to a target base."""
    reference_base = _reference_base(words)
    if base < reference_base:
        raise ValueError("base must not be below the reference base")
    materialized = []
    for phase, word in enumerate(words):
        fragments = tuple(
            tuple(
                digits[_digit_key(phase, fragment_index, offset)]
                for offset in range(len(fragment))
            )
            for fragment_index, fragment in enumerate(word.fragments)
        )
        repeats = tuple(
            base - 1 if repeat == reference_base - 1 else 0
            for repeat in word.repeats
        )
        materialized.append(ParametricWord(base, fragments, repeats))
    return tuple(materialized)
