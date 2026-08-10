#!/usr/bin/env python3
"""Synthesize and certify a compact layer-30 bad-image exclusion predicate."""

from __future__ import annotations

import hashlib
import itertools
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from lychrel_bad_image_projection import (  # noqa: E402
    P30_VARIABLES,
    Layer30Predicate,
    ProjectionAtom,
    ProjectionClause,
    ProjectionOrigin,
    compactness_bytes,
    evaluate_p30,
)
from lychrel_exact_image_refinement import (  # noqa: E402
    ExactImageRefinementCertificate,
    parse_exact_image_refinement_certificate,
)
from lychrel_invariant_certificate import (  # noqa: E402
    LayerPredicate,
    canonical_bytes,
    evaluate_predicate,
)
from lychrel_reachability_separator import SemanticWitness  # noqa: E402
from t27_base19_invariant_lift import (  # noqa: E402
    canonical_variable,
    canonicalize_state,
)
from t30_base19_exact_image_refinement import (  # noqa: E402
    T29_ARTIFACT_DIGESTS,
    T30Inputs,
    build_q0,
    load_t30_inputs,
)
from t30_base19_exact_image_refinement import (  # noqa: E402
    EvidenceError as T30EvidenceError,
)

_REMOVED = "phase=0,n=0,column=82"
T30_ARTIFACT_DIGESTS = {
    "evidence": "4b327e826a8b2462eedffa2cf572b77155fc95d8e7b94a4430d7f0331f75bd2a",
    "certificate": "3ac0b6ae254ad8bb7c7b19754335ea6a81bea77a0dc808e7eda1cd8994839892",
    "independent": "56037d658f628ffa526f9adb710746231806450717f7bde5c0655f4ed6388639",
    "report": "3ea55f8410887d3a522436be38bf3d9b5c010ac3c412d48405cd69f19828b95c",
}


class EvidenceError(RuntimeError):
    """Frozen T31 input evidence is malformed, changed, or inconsistent."""


@dataclass(frozen=True)
class T31Inputs:
    t30_inputs: T30Inputs
    t30_certificate: ExactImageRefinementCertificate
    q0: LayerPredicate
    p30_variables: tuple[str, ...]
    promoted_rows: tuple[tuple[int, ...], ...]
    source_digests: tuple[tuple[str, str], ...]
    t29_artifact_digests: tuple[tuple[str, str], ...]
    t30_artifact_digests: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if self.p30_variables != P30_VARIABLES:
            raise ValueError("T31 layer-30 variable scope differs")
        if len(self.promoted_rows) != 18 or len(set(self.promoted_rows)) != 18:
            raise ValueError("T31 requires 18 distinct promoted rows")
        if any(len(row) != len(P30_VARIABLES) for row in self.promoted_rows):
            raise ValueError("T31 promoted row width differs")
        if self.source_digests != self.t30_inputs.source_digests:
            raise ValueError("T31 source digests differ")
        if self.t29_artifact_digests != self.t30_inputs.t29_artifact_digests:
            raise ValueError("T31 T29 artifact digests differ")
        if self.t30_artifact_digests != tuple(sorted(T30_ARTIFACT_DIGESTS.items())):
            raise ValueError("T31 T30 artifact digests differ")
        if self.q0 != self.t30_certificate.q0:
            raise ValueError("T31 Q0 differs from the T30 certificate")


@dataclass(frozen=True)
class Layer30Relation:
    z3: object
    assertions: tuple[object, ...]
    variables: Mapping[str, object]
    transfer: object
    equations: tuple[object, ...]
    input_mapping: Mapping[str, str]
    output_mapping: Mapping[str, str]


@dataclass(frozen=True)
class ProjectionAtomRecord:
    atom: ProjectionAtom
    origin: ProjectionOrigin
    holds_on_all_promoted: bool

    def to_payload(self) -> dict[str, object]:
        return {
            "atom": self.atom.to_payload(),
            "origin": self.origin.to_payload(),
            "holds_on_all_promoted": self.holds_on_all_promoted,
        }


@dataclass(frozen=True)
class CandidateSearchResult:
    status: str
    p30: Layer30Predicate | None
    origins: tuple[ProjectionOrigin, ...]
    counterexamples: tuple[SemanticWitness, ...]
    predicate_bytes: int | None
    state_table_bytes: int
    stop_detail: str | None

    def __post_init__(self) -> None:
        if self.status not in {
            "UNSAT",
            "NO_CANDIDATE",
            "NON_COMPACT",
            "BUDGET_EXHAUSTED",
        }:
            raise ValueError("unsupported candidate-search status")
        if not self.counterexamples or len(self.counterexamples) > 64:
            raise ValueError("candidate search requires 1..64 counterexamples")
        if self.state_table_bytes < 1:
            raise ValueError("candidate search requires a state-table byte count")
        if self.p30 is None:
            if self.origins or self.predicate_bytes is not None:
                raise ValueError("missing P30 cannot carry origins or predicate bytes")
        elif not self.origins or self.predicate_bytes is None:
            raise ValueError("P30 requires origins and a predicate byte count")
        if self.status == "UNSAT" and (self.p30 is None or self.stop_detail is not None):
            raise ValueError("candidate UNSAT requires P30 and no stop detail")
        if self.status != "UNSAT" and not self.stop_detail:
            raise ValueError("candidate STOP requires a detail")

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "p30": None if self.p30 is None else self.p30.to_payload(),
            "origins": [origin.to_payload() for origin in self.origins],
            "counterexamples": [
                witness.to_payload() for witness in self.counterexamples
            ],
            "predicate_bytes": self.predicate_bytes,
            "state_table_bytes": self.state_table_bytes,
            "stop_detail": self.stop_detail,
        }


@dataclass(frozen=True)
class BadImageWitnessReplay:
    equation_residuals: tuple[int, ...]
    q0_holds: bool

    def __post_init__(self) -> None:
        if len(self.equation_residuals) != 12 or any(
            not isinstance(residual, int) or isinstance(residual, bool)
            for residual in self.equation_residuals
        ):
            raise ValueError("bad-image replay requires 12 integer residuals")
        if not isinstance(self.q0_holds, bool):
            raise ValueError("bad-image replay Q0 result must be Boolean")


def _raw_digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_bound_json(path: Path, expected: str, context: str) -> Mapping[str, object]:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise EvidenceError(f"cannot read {context}: {error}") from error
    actual = _raw_digest(raw)
    if actual != expected:
        raise EvidenceError(f"{context} raw SHA-256 changed: {actual}")
    try:
        payload = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise EvidenceError(f"{context} is not valid JSON: {error}") from error
    if not isinstance(payload, Mapping):
        raise EvidenceError(f"{context} must be an object")
    return payload


def _bind_raw_file(path: Path, expected: str, context: str) -> bytes:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise EvidenceError(f"cannot read {context}: {error}") from error
    actual = _raw_digest(raw)
    if actual != expected:
        raise EvidenceError(f"{context} raw SHA-256 changed: {actual}")
    return raw


def load_t31_inputs(
    root: Path,
    *,
    t29_evidence_path: Path | None = None,
    t29_trace_path: Path | None = None,
    t29_dataset_path: Path | None = None,
    t29_certificate_path: Path | None = None,
    t29_independent_path: Path | None = None,
    t30_evidence_path: Path | None = None,
    t30_certificate_path: Path | None = None,
    t30_independent_path: Path | None = None,
    t30_report_path: Path | None = None,
) -> T31Inputs:
    """Load and cross-check the complete frozen T29/T30 boundary."""
    root = Path(root)
    run_dir = root / ".timeloop" / "runs"
    try:
        t30_inputs = load_t30_inputs(
            root,
            evidence_path=t29_evidence_path,
            trace_path=t29_trace_path,
            dataset_path=t29_dataset_path,
            certificate_path=t29_certificate_path,
            independent_path=t29_independent_path,
        )
    except (T30EvidenceError, RuntimeError, ValueError) as error:
        raise EvidenceError(f"cannot bind T29 boundary: {error}") from error

    paths = {
        "evidence": t30_evidence_path
        or run_dir / "t30_base19_exact_image_refinement.json",
        "certificate": t30_certificate_path
        or run_dir / "t30_base19_exact_image_refinement_certificate.json",
        "independent": t30_independent_path
        or run_dir / "t30_base19_exact_image_refinement_independent.json",
        "report": t30_report_path
        or run_dir / "t30_base19_exact_image_refinement_report.md",
    }
    evidence = _read_bound_json(
        paths["evidence"], T30_ARTIFACT_DIGESTS["evidence"], "T30 evidence"
    )
    certificate_payload = _read_bound_json(
        paths["certificate"],
        T30_ARTIFACT_DIGESTS["certificate"],
        "T30 certificate",
    )
    independent = _read_bound_json(
        paths["independent"],
        T30_ARTIFACT_DIGESTS["independent"],
        "T30 independent audit",
    )
    report = _bind_raw_file(
        paths["report"], T30_ARTIFACT_DIGESTS["report"], "T30 report"
    )
    try:
        certificate = parse_exact_image_refinement_certificate(certificate_payload)
    except ValueError as error:
        raise EvidenceError(f"T30 certificate is malformed: {error}") from error

    q0 = build_q0(t30_inputs.variables)
    expected_t29 = dict(t30_inputs.t29_artifact_digests)
    if (
        evidence.get("schema") != "t30-base19-exact-image-refinement-evidence-v1"
        or evidence.get("status") != "EXACT_IMAGE_REFINEMENT_PASS"
        or evidence.get("stop_reason") is not None
        or evidence.get("base") != 19
        or evidence.get("removed") != _REMOVED
        or evidence.get("source_digests") != dict(t30_inputs.source_digests)
        or evidence.get("t29_artifact_digests") != expected_t29
        or evidence.get("q0") != q0.to_payload()
        or evidence.get("implication", {}).get("status") != "UNSAT"  # type: ignore[union-attr]
        or evidence.get("finite", {}).get("status") != "PASS"  # type: ignore[union-attr]
        or evidence.get("semantic", {}).get("status") != "UNSAT"  # type: ignore[union-attr]
    ):
        raise EvidenceError("T30 primary boundary changed")
    if (
        certificate.status != "EXACT_IMAGE_REFINEMENT_PASS"
        or certificate.base != 19
        or certificate.removed != _REMOVED
        or certificate.source_digests != t30_inputs.source_digests
        or certificate.t29_artifact_digests != t30_inputs.t29_artifact_digests
        or certificate.q0 != q0
        or certificate.implication_status != "UNSAT"
        or certificate.finite_status != "PASS"
        or certificate.semantic_status != "UNSAT"
        or certificate.to_payload() != certificate_payload
    ):
        raise EvidenceError("T30 certificate boundary changed")
    if (
        independent.get("schema")
        != "t30-base19-exact-image-refinement-independent-v1"
        or independent.get("status") != "EXACT_IMAGE_REFINEMENT_PASS"
        or independent.get("repository_imports") != []
        or independent.get("primary_evidence_sha256")
        != T30_ARTIFACT_DIGESTS["evidence"]
        or independent.get("certificate_file_sha256")
        != T30_ARTIFACT_DIGESTS["certificate"]
        or independent.get("predecessor_obligation_count") != 18
        or independent.get("exact_model_count") != 18
        or independent.get("distinct_output_count") != 18
        or independent.get("semantic_status") != "UNSAT"
        or independent.get("source_digests") != dict(t30_inputs.source_digests)
        or independent.get("t29_artifact_digests") != expected_t29
    ):
        raise EvidenceError("T30 independent boundary changed")
    if b"EXACT_IMAGE_REFINEMENT_PASS" not in report:
        raise EvidenceError("T30 report boundary changed")

    layer = t30_inputs.t29_inputs.t28_inputs.frontier.layers_by_number[31]
    if len(layer.transitions) != 18 or len(layer.equation_provenances) != 12:
        raise EvidenceError("layer-30 frontier boundary changed")
    promoted_rows = tuple(
        tuple(
            canonicalize_state(layer, "input", transition.input_state)[name]
            for name in P30_VARIABLES
        )
        for transition in layer.transitions
    )
    return T31Inputs(
        t30_inputs=t30_inputs,
        t30_certificate=certificate,
        q0=q0,
        p30_variables=P30_VARIABLES,
        promoted_rows=promoted_rows,
        source_digests=t30_inputs.source_digests,
        t29_artifact_digests=tuple(sorted(T29_ARTIFACT_DIGESTS.items())),
        t30_artifact_digests=tuple(sorted(T30_ARTIFACT_DIGESTS.items())),
    )


def build_layer30_relation(inputs: T31Inputs) -> Layer30Relation:
    """Reconstruct the exact layer-30-to-31 relation from frozen sources."""
    try:
        import z3  # type: ignore[import-not-found]
    except ImportError as error:
        raise EvidenceError("bad-image projection requires z3-solver") from error
    transfer = inputs.t30_inputs.t29_inputs.t28_inputs.frontier.layers_by_number[31]
    manifest = inputs.t30_inputs.t29_inputs.t28_inputs.manifest
    equations = tuple(
        manifest.by_provenance[provenance]
        for provenance in transfer.equation_provenances
    )
    names = tuple(
        sorted(
            set(transfer.input_variables)
            | set(transfer.output_variables)
            | {name for equation in equations for name in equation.variables}
        )
    )
    variables = {
        name: z3.Int(
            "t31_layer30_"
            + "".join(character if character.isalnum() else "_" for character in name)
        )
        for name in names
    }
    assertions = []
    for name, variable in variables.items():
        if name.startswith("c:"):
            assertions.extend((variable >= 0, variable <= 1))
        else:
            lower = 1 if name.startswith("digit:p") and ":f0:d0" in name else 0
            assertions.extend((variable >= lower, variable < manifest.base))
    assertions.extend(
        equation.residual(variables, manifest.base) == 0 for equation in equations
    )
    input_mapping = {
        canonical_variable(name, transfer, "input"): name
        for name in transfer.input_variables
    }
    output_mapping = {
        canonical_variable(name, transfer, "output"): name
        for name in transfer.output_variables
    }
    if tuple(input_mapping) != P30_VARIABLES:
        raise EvidenceError("layer-30 canonical input mapping changed")
    if tuple(sorted(output_mapping)) != inputs.q0.variables:
        raise EvidenceError("layer-31 canonical output mapping changed")
    return Layer30Relation(
        z3=z3,
        assertions=tuple(assertions),
        variables=variables,
        transfer=transfer,
        equations=equations,
        input_mapping=input_mapping,
        output_mapping=output_mapping,
    )


def _linear_form(
    z3: object,
    expression: object,
    reverse_input_mapping: Mapping[str, str],
) -> tuple[dict[str, int], int] | None:
    if z3.is_var(expression):
        return None
    if z3.is_int_value(expression):
        return {}, expression.as_long()
    if z3.is_const(expression) and expression.decl().kind() == z3.Z3_OP_UNINTERPRETED:
        canonical = reverse_input_mapping.get(str(expression))
        return None if canonical is None else ({canonical: 1}, 0)
    kind = expression.decl().kind()
    children = expression.children()
    if kind == z3.Z3_OP_UMINUS and len(children) == 1:
        parsed = _linear_form(z3, children[0], reverse_input_mapping)
        if parsed is None:
            return None
        coefficients, constant = parsed
        return {name: -value for name, value in coefficients.items()}, -constant
    if kind in {z3.Z3_OP_ADD, z3.Z3_OP_SUB}:
        result: dict[str, int] = {}
        constant = 0
        for index, child in enumerate(children):
            parsed = _linear_form(z3, child, reverse_input_mapping)
            if parsed is None:
                return None
            coefficients, child_constant = parsed
            sign = -1 if kind == z3.Z3_OP_SUB and index > 0 else 1
            constant += sign * child_constant
            for name, value in coefficients.items():
                result[name] = result.get(name, 0) + sign * value
        return {name: value for name, value in result.items() if value}, constant
    if kind == z3.Z3_OP_MUL and len(children) == 2:
        if z3.is_int_value(children[0]):
            scalar, other = children[0].as_long(), children[1]
        elif z3.is_int_value(children[1]):
            scalar, other = children[1].as_long(), children[0]
        else:
            return None
        parsed = _linear_form(z3, other, reverse_input_mapping)
        if parsed is None:
            return None
        coefficients, constant = parsed
        return {name: scalar * value for name, value in coefficients.items()}, scalar * constant
    return None


def _comparison_atom(
    z3: object,
    expression: object,
    reverse_input_mapping: Mapping[str, str],
) -> ProjectionAtom | None:
    children = expression.children()
    if len(children) != 2:
        return None
    relation = None
    strict_adjustment = 0
    if z3.is_eq(expression):
        relation = "eq"
    elif z3.is_le(expression):
        relation = "le"
    elif z3.is_lt(expression):
        relation = "le"
        strict_adjustment = -1
    elif z3.is_ge(expression):
        relation = "le"
        children = (children[1], children[0])
    elif z3.is_gt(expression):
        relation = "le"
        children = (children[1], children[0])
        strict_adjustment = -1
    else:
        return None
    left = _linear_form(z3, children[0], reverse_input_mapping)
    right = _linear_form(z3, children[1], reverse_input_mapping)
    if left is None or right is None:
        return None
    coefficients = dict(left[0])
    for name, value in right[0].items():
        coefficients[name] = coefficients.get(name, 0) - value
    coefficients = {name: value for name, value in coefficients.items() if value}
    if not coefficients:
        return None
    constant = right[1] - left[1] + strict_adjustment
    try:
        return ProjectionAtom(relation, tuple(coefficients.items()), constant)
    except ValueError:
        return None


def _complement(atom: ProjectionAtom) -> ProjectionAtom | None:
    if atom.relation == "le":
        return ProjectionAtom(
            "le",
            tuple((name, -coefficient) for name, coefficient in atom.terms),
            -atom.constant - 1,
        )
    if atom.relation == "congruent" and atom.modulus == 2:
        return ProjectionAtom("congruent", atom.terms, atom.constant + 1, 2)
    return None


def _walk_projection_atoms(
    z3: object,
    expression: object,
    reverse_input_mapping: Mapping[str, str],
    path: tuple[int, ...] = (),
) -> tuple[tuple[ProjectionAtom, tuple[int, ...], str], ...]:
    direct = _comparison_atom(z3, expression, reverse_input_mapping)
    if direct is not None:
        result = [(direct, path or (0,), "direct")]
        complement = _complement(direct)
        if complement is not None:
            result.append((complement, path or (0,), "complement"))
        return tuple(result)
    records = []
    for index, child in enumerate(expression.children()):
        records.extend(
            _walk_projection_atoms(
                z3,
                child,
                reverse_input_mapping,
                (*path, index),
            )
        )
    return tuple(records)


def _q0_atom_expression(
    relation: Layer30Relation,
    atom: object,
) -> object:
    total = sum(
        coefficient * relation.variables[relation.output_mapping[name]]
        for name, coefficient in atom.terms
    )
    if atom.relation != "eq":
        raise EvidenceError("T30 Q0 is no longer equality-only")
    return total == atom.constant


def project_bad_image_atoms(inputs: T31Inputs) -> tuple[ProjectionAtomRecord, ...]:
    """Project the five exact Q0-failure relations into candidate input atoms."""
    relation = build_layer30_relation(inputs)
    z3 = relation.z3
    reverse_input_mapping = {
        str(relation.variables[original]): canonical
        for canonical, original in relation.input_mapping.items()
    }
    quantified = [
        variable
        for name, variable in sorted(relation.variables.items())
        if name not in set(relation.transfer.input_variables)
    ]
    promoted = tuple(
        dict(zip(P30_VARIABLES, row, strict=True)) for row in inputs.promoted_rows
    )
    selected: dict[bytes, ProjectionAtomRecord] = {}
    q0_atoms = inputs.q0.clauses[0].atoms
    for equation_index, q0_atom in enumerate(q0_atoms):
        formula = z3.Exists(
            quantified,
            z3.And(
                *relation.assertions,
                z3.Not(_q0_atom_expression(relation, q0_atom)),
            ),
        )
        goal = z3.Goal()
        goal.add(formula)
        result = z3.Then("qe-light", "simplify")(goal)
        if len(result) != 1:
            raise EvidenceError("bad-image projection returned multiple subgoals")
        projected = z3.And(*result[0])
        formula_sha256 = hashlib.sha256(projected.sexpr().encode()).hexdigest()
        for atom, path, polarity in _walk_projection_atoms(
            z3, projected, reverse_input_mapping
        ):
            holds = all(evaluate_p30_atom(atom, assignment) for assignment in promoted)
            if not holds:
                continue
            atom_bytes = canonical_bytes(atom.to_payload())
            origin = ProjectionOrigin(
                atom_sha256=hashlib.sha256(atom_bytes).hexdigest(),
                failed_q0_equation=equation_index,
                qe_formula_sha256=formula_sha256,
                expression_path=path,
                polarity=polarity,
            )
            record = ProjectionAtomRecord(atom, origin, True)
            previous = selected.get(atom_bytes)
            if previous is None or canonical_bytes(origin) < canonical_bytes(previous.origin):
                selected[atom_bytes] = record
    records = tuple(selected[key] for key in sorted(selected))
    if not records:
        raise EvidenceError("bad-image projection produced no admissible atoms")
    return records


def evaluate_p30_atom(atom: ProjectionAtom, assignment: Mapping[str, int]) -> bool:
    """Evaluate one projected atom through the public predicate evaluator."""
    from lychrel_bad_image_projection import Layer30Predicate, ProjectionClause

    return evaluate_p30(
        Layer30Predicate(30, P30_VARIABLES, (ProjectionClause((atom,)),)),
        assignment,
    )


def _row_assignment(row: tuple[int, ...]) -> dict[str, int]:
    return dict(zip(P30_VARIABLES, row, strict=True))


def _candidate_objective(predicate: Layer30Predicate) -> tuple[object, ...]:
    path_lengths = tuple(len(clause.atoms) for clause in predicate.clauses)
    atoms = tuple(atom for clause in predicate.clauses for atom in clause.atoms)
    return (
        len(predicate.clauses),
        max(path_lengths),
        len(atoms),
        sum(len(atom.terms) for atom in atoms),
        sum(abs(coefficient) for atom in atoms for _, coefficient in atom.terms),
        canonical_bytes(predicate.to_payload()),
    )


def _select_candidate(
    records: tuple[ProjectionAtomRecord, ...],
    witnesses: tuple[tuple[int, ...], ...],
    promoted_rows: tuple[tuple[int, ...], ...],
) -> tuple[
    Layer30Predicate,
    tuple[ProjectionOrigin, ...],
    int,
    int,
] | None:
    """Select the least compact conjunction hitting every recorded bad input."""
    candidates = []
    for size in range(1, min(6, len(records)) + 1):
        for selected in itertools.combinations(records, size):
            predicate = Layer30Predicate(
                30,
                P30_VARIABLES,
                (ProjectionClause(tuple(record.atom for record in selected)),),
            )
            if not all(
                evaluate_p30(predicate, _row_assignment(row)) for row in promoted_rows
            ):
                continue
            if not all(
                not evaluate_p30(predicate, _row_assignment(witness))
                for witness in witnesses
            ):
                continue
            predicate_bytes, state_table_bytes = compactness_bytes(
                predicate, promoted_rows
            )
            if predicate_bytes >= state_table_bytes:
                continue
            origins = tuple(
                record.origin
                for record in selected
                for atom in predicate.clauses[0].atoms
                if record.atom == atom
            )
            origins = tuple(sorted(set(origins), key=canonical_bytes))
            candidates.append(
                (
                    _candidate_objective(predicate),
                    predicate,
                    origins,
                    predicate_bytes,
                    state_table_bytes,
                )
            )
    if not candidates:
        return None
    _, predicate, origins, predicate_bytes, state_table_bytes = min(
        candidates, key=lambda item: item[0]
    )
    return predicate, origins, predicate_bytes, state_table_bytes


def _solver_status(z3: object, solver: object, context: str) -> object:
    status = solver.check()
    if status == z3.unknown:
        raise EvidenceError(f"{context} returned UNKNOWN: {solver.reason_unknown()}")
    return status


def _z3_p30_atom(
    relation: Layer30Relation,
    atom: ProjectionAtom,
) -> object:
    total = sum(
        coefficient * relation.variables[relation.input_mapping[name]]
        for name, coefficient in atom.terms
    )
    if atom.relation == "eq":
        return total == atom.constant
    if atom.relation == "le":
        return total <= atom.constant
    assert atom.modulus is not None
    return (total - atom.constant) % atom.modulus == 0


def _z3_p30(relation: Layer30Relation, predicate: Layer30Predicate) -> object:
    z3 = relation.z3
    return z3.Or(
        *(
            z3.And(*(_z3_p30_atom(relation, atom) for atom in clause.atoms))
            for clause in predicate.clauses
        )
    )


def _lexicographic_assignment(
    relation: Layer30Relation,
    solver: object,
    context: str,
) -> tuple[tuple[str, int], ...]:
    z3 = relation.z3
    if _solver_status(z3, solver, context) != z3.sat:
        raise EvidenceError(f"cannot minimize a non-SAT {context}")
    base = 19
    for name, variable in sorted(relation.variables.items()):
        if name.startswith("c:"):
            domain = range(2)
        else:
            lower = 1 if name.startswith("digit:p") and ":f0:d0" in name else 0
            domain = range(lower, base)
        for value in domain:
            solver.push()
            solver.add(variable == value)
            status = _solver_status(z3, solver, f"{context} minimization")
            solver.pop()
            if status == z3.sat:
                solver.add(variable == value)
                break
        else:
            raise EvidenceError(f"{context} variable has no value: {name}")
    if _solver_status(z3, solver, f"{context} finalization") != z3.sat:
        raise EvidenceError(f"{context} became inconsistent during minimization")
    model = solver.model()
    return tuple(
        (name, model.eval(variable, model_completion=False).as_long())
        for name, variable in sorted(relation.variables.items())
    )


def _candidate_witness(
    relation: Layer30Relation,
    assignment: tuple[tuple[str, int], ...],
) -> SemanticWitness:
    values = dict(assignment)
    transfer = relation.transfer
    input_names = set(transfer.input_variables)
    output_names = set(transfer.output_variables)
    canonical_input = canonicalize_state(
        transfer,
        "input",
        tuple(values[name] for name in transfer.input_variables),
    )
    canonical_output = canonicalize_state(
        transfer,
        "output",
        tuple(values[name] for name in transfer.output_variables),
    )
    return SemanticWitness(
        input_state=tuple(
            sorted((f"input:{name}", value) for name, value in canonical_input.items())
        ),
        output_state=tuple(
            sorted(
                (f"output:{name}", value) for name, value in canonical_output.items()
            )
        ),
        local_state=tuple(
            (f"local:{name}", values[name])
            for name in sorted(set(values) - input_names - output_names)
        ),
    )


def replay_bad_image_witness(
    inputs: T31Inputs,
    witness: SemanticWitness,
) -> BadImageWitnessReplay:
    """Constructively replay one witness against the 12 equations and Q0."""
    relation = build_layer30_relation(inputs)
    assignment: dict[str, int] = {}

    def bind(original: str, value: int) -> None:
        if original in assignment:
            raise EvidenceError(f"bad-image witness repeats variable: {original}")
        assignment[original] = value

    for prefixed, value in witness.input_state:
        canonical = prefixed.removeprefix("input:")
        if f"input:{canonical}" != prefixed or canonical not in relation.input_mapping:
            raise EvidenceError(f"bad-image witness input is unknown: {prefixed}")
        bind(relation.input_mapping[canonical], value)
    for prefixed, value in witness.output_state:
        canonical = prefixed.removeprefix("output:")
        if f"output:{canonical}" != prefixed or canonical not in relation.output_mapping:
            raise EvidenceError(f"bad-image witness output is unknown: {prefixed}")
        bind(relation.output_mapping[canonical], value)
    for prefixed, value in witness.local_state:
        original = prefixed.removeprefix("local:")
        if f"local:{original}" != prefixed:
            raise EvidenceError(f"bad-image witness local is malformed: {prefixed}")
        bind(original, value)

    expected = set(relation.variables)
    actual = set(assignment)
    if actual != expected:
        raise EvidenceError(
            "bad-image witness variables differ: "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )
    output = {
        canonical: assignment[original]
        for canonical, original in relation.output_mapping.items()
    }
    return BadImageWitnessReplay(
        tuple(
            equation.residual(assignment, 19) for equation in relation.equations
        ),
        evaluate_predicate(inputs.q0, output),
    )


def _witness_input_row(witness: SemanticWitness) -> tuple[int, ...]:
    assignment = {
        name.removeprefix("input:"): value for name, value in witness.input_state
    }
    return tuple(assignment[name] for name in P30_VARIABLES)


def _bad_image_solver(
    inputs: T31Inputs,
    relation: Layer30Relation,
    predicate: Layer30Predicate | None,
) -> object:
    z3 = relation.z3
    solver = z3.Solver()
    solver.add(*relation.assertions)
    solver.add(
        z3.Not(
            z3.And(
                *(
                    _q0_atom_expression(relation, atom)
                    for atom in inputs.q0.clauses[0].atoms
                )
            )
        )
    )
    if predicate is not None:
        solver.add(_z3_p30(relation, predicate))
    return solver


def _state_table_size(inputs: T31Inputs) -> int:
    table = {
        "layer": 30,
        "variables": list(P30_VARIABLES),
        "states": [list(row) for row in inputs.promoted_rows],
    }
    return len(canonical_bytes(table))


def synthesize_p30(
    inputs: T31Inputs,
    records: tuple[ProjectionAtomRecord, ...],
    counterexample_limit: int = 64,
) -> CandidateSearchResult:
    """Run the bounded deterministic projected-atom CEGIS milestone."""
    if not 1 <= counterexample_limit <= 64:
        raise ValueError("counterexample limit must be in 1..64")
    if tuple(sorted(records, key=lambda item: canonical_bytes(item.atom))) != records:
        raise ValueError("projection records must be canonically ordered")
    relation = build_layer30_relation(inputs)
    counterexamples: list[SemanticWitness] = []
    state_table_bytes = _state_table_size(inputs)
    predicate: Layer30Predicate | None = None
    origins: tuple[ProjectionOrigin, ...] = ()
    predicate_bytes: int | None = None

    while True:
        solver = _bad_image_solver(inputs, relation, predicate)
        status = _solver_status(relation.z3, solver, "candidate bad-image query")
        if status == relation.z3.unsat:
            assert predicate is not None and predicate_bytes is not None
            return CandidateSearchResult(
                "UNSAT",
                predicate,
                origins,
                tuple(counterexamples),
                predicate_bytes,
                state_table_bytes,
                None,
            )
        assignment = _lexicographic_assignment(
            relation, solver, "candidate bad-image witness"
        )
        witness = _candidate_witness(relation, assignment)
        replay = replay_bad_image_witness(inputs, witness)
        if replay.equation_residuals != (0,) * 12 or replay.q0_holds:
            raise EvidenceError("candidate bad-image witness failed exact replay")
        if witness in counterexamples:
            raise EvidenceError("candidate search repeated a canonical witness")
        counterexamples.append(witness)
        if len(counterexamples) >= counterexample_limit:
            return CandidateSearchResult(
                "BUDGET_EXHAUSTED",
                predicate,
                origins,
                tuple(counterexamples),
                predicate_bytes,
                state_table_bytes,
                f"exact bad image remains after {counterexample_limit} counterexamples",
            )
        witness_rows = tuple(_witness_input_row(item) for item in counterexamples)
        selected = _select_candidate(records, witness_rows, inputs.promoted_rows)
        if selected is None:
            detail = (
                "no projected atom excludes the first exact bad image"
                if len(counterexamples) == 1
                and all(
                    evaluate_p30_atom(record.atom, _row_assignment(witness_rows[0]))
                    for record in records
                )
                else "no six-atom projected conjunction excludes all exact bad images"
            )
            return CandidateSearchResult(
                "NO_CANDIDATE",
                None,
                (),
                tuple(counterexamples),
                None,
                state_table_bytes,
                detail,
            )
        predicate, origins, predicate_bytes, _ = selected
