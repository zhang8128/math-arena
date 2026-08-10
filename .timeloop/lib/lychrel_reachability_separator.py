"""Typed evidence for reachability-aware reverse-and-add separators."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from lychrel_invariant_certificate import Conjunction, LayerPredicate, LinearAtom


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


@dataclass(frozen=True)
class TraceStep:
    iteration: int
    input_state: tuple[tuple[str, int], ...]
    rejected_class: str
    obligation: str
    candidate_atom_count: int
    node_count: int
    path_depth: int

    def __post_init__(self) -> None:
        if not _is_int(self.iteration) or self.iteration < 1:
            raise ValueError("trace iteration must be a positive integer")
        if not self.input_state or tuple(sorted(self.input_state)) != self.input_state:
            raise ValueError("trace input assignment must be nonempty and sorted")
        if len({name for name, _ in self.input_state}) != len(self.input_state) or any(
            not isinstance(name, str) or not name or not _is_int(value)
            for name, value in self.input_state
        ):
            raise ValueError("trace input assignment is invalid")
        if (
            not isinstance(self.rejected_class, str)
            or not self.rejected_class
            or not isinstance(self.obligation, str)
            or not self.obligation
        ):
            raise ValueError("trace class and obligation must be strings")
        for value in (
            self.candidate_atom_count,
            self.node_count,
            self.path_depth,
        ):
            if not _is_int(value) or value < 0:
                raise ValueError("trace measurements must be nonnegative integers")

    def to_payload(self) -> dict[str, object]:
        return {
            "iteration": self.iteration,
            "input_state": dict(self.input_state),
            "rejected_class": self.rejected_class,
            "obligation": self.obligation,
            "candidate_atom_count": self.candidate_atom_count,
            "node_count": self.node_count,
            "path_depth": self.path_depth,
        }


@dataclass(frozen=True)
class CounterexampleTrace:
    schema: str
    variables: tuple[str, ...]
    steps: tuple[TraceStep, ...]
    terminal_iteration: int
    stop_reason: str

    def __post_init__(self) -> None:
        if self.schema != "t29-base19-counterexample-trace-v1":
            raise ValueError(f"unsupported counterexample trace schema: {self.schema}")
        if not self.variables or len(set(self.variables)) != len(self.variables) or any(
            not isinstance(variable, str) or not variable for variable in self.variables
        ):
            raise ValueError("trace variables must be nonempty and unique")
        if not self.steps:
            raise ValueError("trace must contain a counterexample")
        if tuple(step.iteration for step in self.steps) != tuple(
            range(1, len(self.steps) + 1)
        ):
            raise ValueError("trace iterations must be consecutive from one")
        if any(
            tuple(name for name, _ in step.input_state) != self.variables
            for step in self.steps
        ):
            raise ValueError("trace assignments must match the variable scope")
        if len({step.input_state for step in self.steps}) != len(self.steps):
            raise ValueError("trace counterexamples must be unique")
        if self.terminal_iteration != len(self.steps) + 1:
            raise ValueError("terminal iteration must follow the final counterexample")
        if not isinstance(self.stop_reason, str) or not self.stop_reason:
            raise ValueError("trace stop reason must be a string")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "variables": list(self.variables),
            "steps": [step.to_payload() for step in self.steps],
            "terminal_iteration": self.terminal_iteration,
            "stop_reason": self.stop_reason,
        }


@dataclass(frozen=True)
class SeparatorDataset:
    variables: tuple[str, ...]
    positives: tuple[tuple[int, ...], ...]
    trace_negatives: tuple[tuple[int, ...], ...]
    live_controls: tuple[tuple[int, ...], ...]

    def __post_init__(self) -> None:
        if (
            not self.variables
            or len(set(self.variables)) != len(self.variables)
            or any(
                not isinstance(variable, str) or not variable
                for variable in self.variables
            )
        ):
            raise ValueError("dataset variables must be nonempty strings and unique")
        parts = (self.positives, self.trace_negatives, self.live_controls)
        if any(not part for part in parts):
            raise ValueError("dataset parts must be nonempty")
        if any(
            tuple(sorted(set(part))) != part
            or any(
                len(state) != len(self.variables)
                or any(not _is_int(value) for value in state)
                for state in part
            )
            for part in parts
        ):
            raise ValueError("dataset states must be canonical integral rows")
        positive_set, trace_set, live_set = map(set, parts)
        if positive_set & trace_set or positive_set & live_set or trace_set & live_set:
            raise ValueError("dataset parts must be disjoint")

    def to_payload(self) -> dict[str, object]:
        return {
            "variables": list(self.variables),
            "positives": [list(state) for state in self.positives],
            "trace_negatives": [list(state) for state in self.trace_negatives],
            "live_controls": [list(state) for state in self.live_controls],
        }


def _validate_assignment(
    assignment: tuple[tuple[str, int], ...],
    context: str,
    *,
    allow_empty: bool = False,
) -> None:
    if not allow_empty and not assignment:
        raise ValueError(f"{context} assignment must be nonempty")
    if tuple(sorted(assignment)) != assignment:
        raise ValueError(f"{context} assignment must be sorted")
    if len({name for name, _ in assignment}) != len(assignment) or any(
        not isinstance(name, str) or not name or not _is_int(value)
        for name, value in assignment
    ):
        raise ValueError(f"{context} assignment is invalid")


@dataclass(frozen=True)
class SemanticWitness:
    input_state: tuple[tuple[str, int], ...]
    output_state: tuple[tuple[str, int], ...]
    local_state: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        _validate_assignment(self.input_state, "witness input")
        _validate_assignment(self.output_state, "witness output")
        _validate_assignment(self.local_state, "witness local", allow_empty=True)
        sections = (
            {name for name, _ in self.input_state},
            {name for name, _ in self.output_state},
            {name for name, _ in self.local_state},
        )
        if sections[0] & sections[1] or sections[0] & sections[2] or sections[1] & sections[2]:
            raise ValueError("witness sections must be disjoint")

    def to_payload(self) -> dict[str, object]:
        return {
            "input_state": dict(self.input_state),
            "output_state": dict(self.output_state),
            "local_state": dict(self.local_state),
        }


_SOURCE_DIGEST_NAMES = {
    "equations",
    "frontier",
    "provenances",
    "t27_evidence",
    "t28_evidence",
    "t28_independent",
}


def _validate_digest(value: object, context: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{context} must be a lowercase SHA-256")


@dataclass(frozen=True)
class SeparatorCertificate:
    schema: str
    base: int
    removed: str
    source_digests: tuple[tuple[str, str], ...]
    trace_sha256: str
    dataset_sha256: str
    predicate: LayerPredicate
    finite_status: str
    semantic_status: str
    semantic_witness: SemanticWitness | None

    def __post_init__(self) -> None:
        if self.schema != "t29-base19-reachability-separator-certificate-v1":
            raise ValueError(f"unsupported separator certificate schema: {self.schema}")
        if self.base != 19:
            raise ValueError("separator certificate is frozen to base 19")
        if not isinstance(self.removed, str) or not self.removed:
            raise ValueError("removed coordinate must be nonempty")
        if (
            len(self.source_digests) != len(_SOURCE_DIGEST_NAMES)
            or tuple(sorted(self.source_digests)) != self.source_digests
            or set(dict(self.source_digests)) != _SOURCE_DIGEST_NAMES
        ):
            raise ValueError("certificate source digest names differ")
        for name, digest in self.source_digests:
            _validate_digest(digest, f"source digest {name}")
        _validate_digest(self.trace_sha256, "trace digest")
        _validate_digest(self.dataset_sha256, "dataset digest")
        if self.predicate.layer != 31:
            raise ValueError("separator predicate must be at layer 31")
        if self.finite_status != "PASS":
            raise ValueError("a separator certificate requires finite PASS")
        if self.semantic_status not in {"NOT_RUN", "SAT", "UNSAT"}:
            raise ValueError("unsupported semantic certificate status")
        if self.semantic_status == "SAT" and self.semantic_witness is None:
            raise ValueError("SAT certificate requires a witness")
        if self.semantic_status != "SAT" and self.semantic_witness is not None:
            raise ValueError("only SAT certificates carry a witness")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "base": self.base,
            "removed": self.removed,
            "source_digests": dict(self.source_digests),
            "trace_sha256": self.trace_sha256,
            "dataset_sha256": self.dataset_sha256,
            "predicate": self.predicate.to_payload(),
            "finite_status": self.finite_status,
            "semantic_status": self.semantic_status,
            "semantic_witness": (
                None if self.semantic_witness is None else self.semantic_witness.to_payload()
            ),
        }


def _atom_holds(atom: LinearAtom, assignment: Mapping[str, int]) -> bool:
    total = sum(coefficient * assignment[name] for name, coefficient in atom.terms)
    if atom.relation == "eq":
        return total == atom.constant
    if atom.relation == "le":
        return total <= atom.constant
    assert atom.modulus is not None
    return (total - atom.constant) % atom.modulus == 0


def evaluate_predicate(
    predicate: LayerPredicate,
    assignment: Mapping[str, int],
) -> bool:
    """Evaluate a bounded DNF predicate using exact integer arithmetic."""
    if set(assignment) != set(predicate.variables) or any(
        not _is_int(value) for value in assignment.values()
    ):
        raise ValueError("assignment must exactly match the predicate scope")
    return any(
        all(_atom_holds(atom, assignment) for atom in clause.atoms)
        for clause in predicate.clauses
    )


def finite_separation_failures(
    predicate: LayerPredicate,
    dataset: SeparatorDataset,
) -> tuple[tuple[str, tuple[int, ...]], ...]:
    """Return every finite example on which the separator claim fails."""
    if predicate.variables != dataset.variables:
        raise ValueError("predicate and dataset scopes differ")

    def holds(state: tuple[int, ...]) -> bool:
        return evaluate_predicate(
            predicate,
            dict(zip(dataset.variables, state, strict=True)),
        )

    failures = [
        ("positive", state) for state in dataset.positives if not holds(state)
    ]
    failures.extend(
        ("trace_negative", state)
        for state in dataset.trace_negatives
        if holds(state)
    )
    failures.extend(
        ("live_control", state) for state in dataset.live_controls if holds(state)
    )
    return tuple(failures)


def _require_keys(
    value: Mapping[str, object],
    expected: set[str],
    context: str,
) -> None:
    if set(value) != expected:
        raise ValueError(f"{context} keys differ")


def _parse_assignment(
    value: object,
    context: str,
    *,
    allow_empty: bool = False,
) -> tuple[tuple[str, int], ...]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{context} assignment must be an object")
    assignment = tuple(sorted(value.items()))
    _validate_assignment(assignment, context, allow_empty=allow_empty)  # type: ignore[arg-type]
    return assignment  # type: ignore[return-value]


def parse_counterexample_trace(payload: object) -> CounterexampleTrace:
    if not isinstance(payload, Mapping):
        raise ValueError("trace must be an object")
    _require_keys(
        payload,
        {"schema", "variables", "steps", "terminal_iteration", "stop_reason"},
        "trace",
    )
    variables = payload["variables"]
    steps = payload["steps"]
    if not isinstance(variables, list) or not all(
        isinstance(variable, str) for variable in variables
    ):
        raise ValueError("trace variables must be a string list")
    if not isinstance(steps, list):
        raise ValueError("trace steps must be a list")
    parsed_steps = []
    for step in steps:
        if not isinstance(step, Mapping):
            raise ValueError("trace step must be an object")
        _require_keys(
            step,
            {
                "iteration",
                "input_state",
                "rejected_class",
                "obligation",
                "candidate_atom_count",
                "node_count",
                "path_depth",
            },
            "trace step",
        )
        parsed_steps.append(
            TraceStep(
                iteration=step["iteration"],  # type: ignore[arg-type]
                input_state=_parse_assignment(step["input_state"], "trace input"),
                rejected_class=step["rejected_class"],  # type: ignore[arg-type]
                obligation=step["obligation"],  # type: ignore[arg-type]
                candidate_atom_count=step["candidate_atom_count"],  # type: ignore[arg-type]
                node_count=step["node_count"],  # type: ignore[arg-type]
                path_depth=step["path_depth"],  # type: ignore[arg-type]
            )
        )
    return CounterexampleTrace(
        schema=payload["schema"],  # type: ignore[arg-type]
        variables=tuple(variables),
        steps=tuple(parsed_steps),
        terminal_iteration=payload["terminal_iteration"],  # type: ignore[arg-type]
        stop_reason=payload["stop_reason"],  # type: ignore[arg-type]
    )


def _parse_atom(payload: object) -> LinearAtom:
    if not isinstance(payload, Mapping):
        raise ValueError("predicate atom must be an object")
    expected = {"relation", "terms", "constant"}
    if payload.get("relation") == "congruent":
        expected.add("modulus")
    _require_keys(payload, expected, "predicate atom")
    terms = payload["terms"]
    if not isinstance(terms, list):
        raise ValueError("predicate terms must be a list")
    parsed_terms = []
    for term in terms:
        if not isinstance(term, list) or len(term) != 2:
            raise ValueError("predicate term must be a two-item list")
        parsed_terms.append((term[0], term[1]))
    return LinearAtom(
        relation=payload["relation"],  # type: ignore[arg-type]
        terms=tuple(parsed_terms),  # type: ignore[arg-type]
        constant=payload["constant"],  # type: ignore[arg-type]
        modulus=payload.get("modulus"),  # type: ignore[arg-type]
    )


def _parse_predicate(payload: object) -> LayerPredicate:
    if not isinstance(payload, Mapping):
        raise ValueError("predicate must be an object")
    _require_keys(payload, {"layer", "variables", "clauses"}, "predicate")
    variables = payload["variables"]
    clauses = payload["clauses"]
    if not isinstance(variables, list) or not all(
        isinstance(variable, str) for variable in variables
    ):
        raise ValueError("predicate variables must be a string list")
    if not isinstance(clauses, list):
        raise ValueError("predicate clauses must be a list")
    parsed_clauses = []
    for clause in clauses:
        if not isinstance(clause, Mapping):
            raise ValueError("predicate clause must be an object")
        _require_keys(clause, {"atoms"}, "predicate clause")
        atoms = clause["atoms"]
        if not isinstance(atoms, list):
            raise ValueError("predicate atoms must be a list")
        parsed_clauses.append(Conjunction(tuple(_parse_atom(atom) for atom in atoms)))
    return LayerPredicate(
        layer=payload["layer"],  # type: ignore[arg-type]
        variables=tuple(variables),
        clauses=tuple(parsed_clauses),
    )


def _parse_witness(payload: object) -> SemanticWitness:
    if not isinstance(payload, Mapping):
        raise ValueError("semantic witness must be an object")
    _require_keys(
        payload,
        {"input_state", "output_state", "local_state"},
        "semantic witness",
    )
    return SemanticWitness(
        input_state=_parse_assignment(payload["input_state"], "witness input"),
        output_state=_parse_assignment(payload["output_state"], "witness output"),
        local_state=_parse_assignment(
            payload["local_state"], "witness local", allow_empty=True
        ),
    )


def parse_separator_certificate(payload: object) -> SeparatorCertificate:
    if not isinstance(payload, Mapping):
        raise ValueError("separator certificate must be an object")
    _require_keys(
        payload,
        {
            "schema",
            "base",
            "removed",
            "source_digests",
            "trace_sha256",
            "dataset_sha256",
            "predicate",
            "finite_status",
            "semantic_status",
            "semantic_witness",
        },
        "separator certificate",
    )
    source_digests = payload["source_digests"]
    if not isinstance(source_digests, Mapping):
        raise ValueError("certificate source digests must be an object")
    witness = payload["semantic_witness"]
    return SeparatorCertificate(
        schema=payload["schema"],  # type: ignore[arg-type]
        base=payload["base"],  # type: ignore[arg-type]
        removed=payload["removed"],  # type: ignore[arg-type]
        source_digests=tuple(sorted(source_digests.items())),  # type: ignore[arg-type]
        trace_sha256=payload["trace_sha256"],  # type: ignore[arg-type]
        dataset_sha256=payload["dataset_sha256"],  # type: ignore[arg-type]
        predicate=_parse_predicate(payload["predicate"]),
        finite_status=payload["finite_status"],  # type: ignore[arg-type]
        semantic_status=payload["semantic_status"],  # type: ignore[arg-type]
        semantic_witness=None if witness is None else _parse_witness(witness),
    )
