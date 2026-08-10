#!/usr/bin/env python3
"""Synthesize and certify a compact base-19 layer-30 safe-region cover."""

from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from lychrel_bad_image_projection import P30_VARIABLES, ProjectionAtom  # noqa: E402
from lychrel_invariant_certificate import canonical_bytes  # noqa: E402
from lychrel_reachability_separator import SemanticWitness  # noqa: E402
from lychrel_safe_region_cover import SafeRegionClause  # noqa: E402
from lychrel_semantic_leak_types import LeakType, StructuralLiteral  # noqa: E402
from t31_base19_bad_image_projection import (  # noqa: E402
    build_layer30_relation,
    replay_bad_image_witness,
)
from t32_base19_semantic_leak_types import (  # noqa: E402
    T32Inputs,
    find_first_leak_type,
    load_t32_inputs,
    synthesize_leak_family,
)

_REMOVED = "phase=0,n=0,column=82"
_T33_DESIGN_SHA256 = (
    "dadd1fe42f32d6f61b72609394f2172ca4fac3a6979660d03453058a221322a0"
)
_T32_DESIGN_SHA256 = (
    "93cecb3d3ce2c6a2610454f63302e26e2bbe57c7eba1825474bc808ad9ff76bd"
)
T32_SOURCE_DIGESTS = {
    "library": "cf6ad87c8edf3ffa2c86449b9762f8c9d4254645eb71b7f88963a688a1bded11",
    "runner": "d9c90e0dc4ce910a6ddef66233b03bff31449a46662fba75628a44dca3ed9e57",
    "independent": "fb520b513dd5673e145b583ee8a5025c8113890fdb89139a48b528655ed506b5",
    "test": "a6ee921a8ba6304d3a48b0db0b893b6bd8077576acc27146b91d626ac00858bd",
}
T32_COMMITS = ("df191a5", "515bbdd", "b5ff122", "e4bc16d", "9d17f77")


class EvidenceError(RuntimeError):
    """Frozen T33 input evidence changed or is internally inconsistent."""


@dataclass(frozen=True)
class BadInputQueryResult:
    status: str
    witness: SemanticWitness | None
    equation_residuals: tuple[int, ...]
    q0_holds: bool | None

    def __post_init__(self) -> None:
        if self.status == "UNSAT":
            if self.witness is not None or self.equation_residuals or self.q0_holds is not None:
                raise ValueError("UNSAT bad-input result cannot carry a witness")
        elif self.status == "SAT":
            if (
                self.witness is None
                or self.equation_residuals != (0,) * 12
                or self.q0_holds is not False
            ):
                raise ValueError("SAT bad-input result requires an exact non-Q0 witness")
        else:
            raise ValueError("bad-input result status must be SAT or UNSAT")


@dataclass(frozen=True)
class T33Inputs:
    t32_inputs: T32Inputs
    promoted_rows: tuple[tuple[int, ...], ...]
    t32_first_type: LeakType
    t32_first_type_status: str
    t32_first_type_sha256: str
    t32_first_type_inspected_witness_count: int
    t32_first_type_tested_candidate_count: int
    t32_family_status: str
    t32_family_inspected_witness_count: int
    t32_family_tested_candidate_count: int
    source_digests: tuple[tuple[str, str], ...]
    t29_artifact_digests: tuple[tuple[str, str], ...]
    t30_artifact_digests: tuple[tuple[str, str], ...]
    t32_source_digests: tuple[tuple[str, str], ...]
    t32_commits: tuple[str, ...]
    t32_design_sha256: str
    t33_design_sha256: str

    def __post_init__(self) -> None:
        if len(self.promoted_rows) != 18 or len(set(self.promoted_rows)) != 18:
            raise ValueError("T33 requires 18 distinct promoted rows")
        if self.promoted_rows != self.t32_inputs.t31_inputs.promoted_rows:
            raise ValueError("T33 promoted rows differ from T32")
        expected_type = LeakType(
            (
                StructuralLiteral(0, "digit_order", "eq"),
                StructuralLiteral(0, "digit_sum", "lt19"),
            )
        )
        if self.t32_first_type != expected_type:
            raise ValueError("T32 first type differs")
        if (
            self.t32_first_type_status != "PASS"
            or self.t32_first_type_inspected_witness_count != 3
            or self.t32_first_type_tested_candidate_count != 31
        ):
            raise ValueError("T32 first-type milestone boundary differs")
        expected_digest = hashlib.sha256(
            canonical_bytes(self.t32_first_type.to_payload())
        ).hexdigest()
        if self.t32_first_type_sha256 != expected_digest:
            raise ValueError("T32 first-type digest differs")
        if (
            self.t32_family_status != "CANDIDATE_BUDGET_EXHAUSTED"
            or self.t32_family_inspected_witness_count != 8
            or self.t32_family_tested_candidate_count != 10_000
        ):
            raise ValueError("T32 family STOP boundary differs")
        if self.source_digests != self.t32_inputs.source_digests:
            raise ValueError("T33 source digests differ")
        if self.t29_artifact_digests != self.t32_inputs.t29_artifact_digests:
            raise ValueError("T33 T29 artifact digests differ")
        if self.t30_artifact_digests != self.t32_inputs.t30_artifact_digests:
            raise ValueError("T33 T30 artifact digests differ")
        if self.t32_source_digests != tuple(sorted(T32_SOURCE_DIGESTS.items())):
            raise ValueError("T33 T32 source digests differ")
        if self.t32_commits != T32_COMMITS:
            raise ValueError("T33 T32 commits differ")
        if self.t32_design_sha256 != _T32_DESIGN_SHA256:
            raise ValueError("T33 T32 design digest differs")
        if self.t33_design_sha256 != _T33_DESIGN_SHA256:
            raise ValueError("T33 design digest differs")


def _bind_raw(path: Path, expected: str, context: str) -> None:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise EvidenceError(f"cannot read {context}: {error}") from error
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected:
        raise EvidenceError(f"{context} raw SHA-256 changed: {actual}")


def _load_t33_inputs_uncached(
    root: Path,
    *,
    t32_library_path: Path | None = None,
    t32_runner_path: Path | None = None,
    t32_independent_path: Path | None = None,
    t32_test_path: Path | None = None,
    design_path: Path | None = None,
) -> T33Inputs:
    """Bind frozen sources and replay the committed T32 PASS/STOP boundary."""
    root = Path(root)
    t32_paths = {
        "library": t32_library_path
        or root / ".timeloop/lib/lychrel_semantic_leak_types.py",
        "runner": t32_runner_path
        or root / ".timeloop/runs/t32_base19_semantic_leak_types.py",
        "independent": t32_independent_path
        or root / ".timeloop/runs/t32_base19_semantic_leak_types_independent.py",
        "test": t32_test_path
        or root / ".timeloop/tests/test_lychrel_semantic_leak_types.py",
    }
    for name, path in t32_paths.items():
        _bind_raw(path, T32_SOURCE_DIGESTS[name], f"T32 {name}")
    _bind_raw(
        design_path
        or root
        / "docs/superpowers/specs/2026-08-10-base19-safe-region-cover-restart-design.md",
        _T33_DESIGN_SHA256,
        "T33 design",
    )

    try:
        t32_inputs = load_t32_inputs(root)
        milestone = find_first_leak_type(t32_inputs)
        if milestone.status != "PASS" or milestone.leak_type is None:
            raise EvidenceError(f"T32 first-type replay stopped at {milestone.status}")
        family = synthesize_leak_family(t32_inputs, milestone)
    except (RuntimeError, ValueError) as error:
        if isinstance(error, EvidenceError):
            raise
        raise EvidenceError(f"cannot replay T32 boundary: {error}") from error

    inputs = T33Inputs(
        t32_inputs=t32_inputs,
        promoted_rows=t32_inputs.t31_inputs.promoted_rows,
        t32_first_type=milestone.leak_type,
        t32_first_type_status=milestone.status,
        t32_first_type_sha256=hashlib.sha256(
            canonical_bytes(milestone.leak_type.to_payload())
        ).hexdigest(),
        t32_first_type_inspected_witness_count=milestone.inspected_witness_count,
        t32_first_type_tested_candidate_count=milestone.tested_candidate_count,
        t32_family_status=family.status,
        t32_family_inspected_witness_count=family.inspected_witness_count,
        t32_family_tested_candidate_count=family.tested_candidate_count,
        source_digests=t32_inputs.source_digests,
        t29_artifact_digests=t32_inputs.t29_artifact_digests,
        t30_artifact_digests=t32_inputs.t30_artifact_digests,
        t32_source_digests=tuple(sorted(T32_SOURCE_DIGESTS.items())),
        t32_commits=T32_COMMITS,
        t32_design_sha256=t32_inputs.design_sha256,
        t33_design_sha256=_T33_DESIGN_SHA256,
    )
    statuses = replay_promoted_rows(inputs)
    if statuses != ("UNSAT",) * 18:
        raise EvidenceError(f"promoted bad-input replay differs: {statuses}")
    table = {
        "layer": 30,
        "variables": list(P30_VARIABLES),
        "states": [list(row) for row in inputs.promoted_rows],
    }
    if len(canonical_bytes(table)) != 616:
        raise EvidenceError("T31 promoted table is no longer 616 bytes")
    return inputs


@cache
def load_t33_inputs(root: Path) -> T33Inputs:
    """Load and cache the immutable T33 input boundary."""
    return _load_t33_inputs_uncached(Path(root))


def z3_safe_atom(relation: object, atom: ProjectionAtom) -> object:
    """Translate one canonical layer-30 atom to the exact relation variables."""
    expression = sum(
        coefficient * relation.variables[relation.input_mapping[name]]
        for name, coefficient in atom.terms
    )
    if atom.relation == "eq":
        return expression == atom.constant
    if atom.relation == "le":
        return expression <= atom.constant
    assert atom.modulus is not None
    return (expression - atom.constant) % atom.modulus == 0


def z3_safe_clause(relation: object, clause: SafeRegionClause) -> object:
    """Translate a strict safe-region conjunction."""
    return relation.z3.And(*(z3_safe_atom(relation, atom) for atom in clause.atoms))


def _q0_expression(inputs: T33Inputs, relation: object) -> object:
    return relation.z3.And(
        *(
            sum(
                coefficient
                * relation.variables[relation.output_mapping[name]]
                for name, coefficient in atom.terms
            )
            == atom.constant
            for atom in inputs.t32_inputs.q0.clauses[0].atoms
        )
    )


def build_bad_input_solver(
    inputs: T33Inputs, clause: SafeRegionClause | None = None
) -> tuple[object, object]:
    """Build a fresh exact solver for ``B30`` and an optional input clause."""
    relation = build_layer30_relation(inputs.t32_inputs.t31_inputs)
    solver = relation.z3.Solver()
    solver.set(random_seed=0, phase_selection=0)
    solver.add(*relation.assertions)
    solver.add(relation.z3.Not(_q0_expression(inputs, relation)))
    if clause is not None:
        solver.add(z3_safe_clause(relation, clause))
    return relation, solver


def _solver_status(relation: object, solver: object, context: str) -> str:
    status = solver.check()
    if status == relation.z3.unknown:
        raise EvidenceError(f"{context} returned UNKNOWN: {solver.reason_unknown()}")
    return "SAT" if status == relation.z3.sat else "UNSAT"


def _validate_input_row(row: tuple[int, ...]) -> None:
    if len(row) != len(P30_VARIABLES):
        raise ValueError("layer-30 row width differs")
    for name, value in zip(P30_VARIABLES, row, strict=True):
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"layer-30 row {name} must be an integer")
        if (name == "D0" and not 0 <= value < 19) or (
            name != "D0" and value not in {0, 1}
        ):
            raise ValueError(f"layer-30 row domain failure: {name}={value}")


def _canonical_assignment(
    relation: object, solver: object, context: str
) -> tuple[tuple[str, int], ...]:
    if _solver_status(relation, solver, context) != "SAT":
        raise EvidenceError(f"cannot minimize non-SAT {context}")
    for name, variable in sorted(relation.variables.items()):
        domain = (
            range(2)
            if name.startswith("c:")
            else range(
                1 if name.startswith("digit:p") and ":f0:d0" in name else 0,
                19,
            )
        )
        for value in domain:
            solver.push()
            solver.add(variable == value)
            status = _solver_status(relation, solver, f"{context} minimization")
            solver.pop()
            if status == "SAT":
                solver.add(variable == value)
                break
        else:
            raise EvidenceError(f"{context} variable has no domain value: {name}")
    if _solver_status(relation, solver, f"{context} finalization") != "SAT":
        raise EvidenceError(f"{context} became inconsistent")
    model = solver.model()
    return tuple(
        (name, model.eval(variable, model_completion=False).as_long())
        for name, variable in sorted(relation.variables.items())
    )


def _semantic_witness(
    relation: object, assignment: tuple[tuple[str, int], ...]
) -> SemanticWitness:
    values = dict(assignment)
    input_originals = set(relation.transfer.input_variables)
    output_originals = set(relation.transfer.output_variables)
    return SemanticWitness(
        input_state=tuple(
            sorted(
                (f"input:{canonical}", values[original])
                for canonical, original in relation.input_mapping.items()
            )
        ),
        output_state=tuple(
            sorted(
                (f"output:{canonical}", values[original])
                for canonical, original in relation.output_mapping.items()
            )
        ),
        local_state=tuple(
            (f"local:{name}", values[name])
            for name in sorted(set(values) - input_originals - output_originals)
        ),
    )


def query_bad_input(inputs: T33Inputs, row: tuple[int, ...]) -> BadInputQueryResult:
    """Decide one input and independently replay any exact SAT countermodel."""
    _validate_input_row(row)
    relation, solver = build_bad_input_solver(inputs)
    solver.add(
        *(
            relation.variables[relation.input_mapping[name]] == value
            for name, value in zip(P30_VARIABLES, row, strict=True)
        )
    )
    status = _solver_status(relation, solver, "exact bad-input query")
    if status == "UNSAT":
        return BadInputQueryResult("UNSAT", None, (), None)
    witness = _semantic_witness(
        relation,
        _canonical_assignment(relation, solver, "exact bad-input countermodel"),
    )
    replay = replay_bad_image_witness(inputs.t32_inputs.t31_inputs, witness)
    if replay.equation_residuals != (0,) * 12 or replay.q0_holds:
        raise EvidenceError("exact bad-input countermodel failed replay")
    return BadInputQueryResult(
        "SAT", witness, replay.equation_residuals, replay.q0_holds
    )


def exact_bad_input_status(inputs: T33Inputs, row: tuple[int, ...]) -> str:
    """Return the exact bad-input status after replaying any SAT witness."""
    return query_bad_input(inputs, row).status


def replay_promoted_rows(inputs: T33Inputs) -> tuple[str, ...]:
    """Replay all 18 promoted-input implications through fresh exact solvers."""
    return tuple(exact_bad_input_status(inputs, row) for row in inputs.promoted_rows)
