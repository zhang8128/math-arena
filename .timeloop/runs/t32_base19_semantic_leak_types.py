#!/usr/bin/env python3
"""Synthesize and certify structural base-19 semantic-leak mechanisms."""

from __future__ import annotations

import hashlib
import itertools
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from lychrel_invariant_certificate import LayerPredicate  # noqa: E402
from lychrel_reachability_separator import SemanticWitness  # noqa: E402
from lychrel_semantic_leak_types import (  # noqa: E402
    LeakType,
    StructuralLiteral,
    evaluate_leak_type,
    evaluate_literal,
    generate_literal_pool,
    type_objective,
)
from t31_base19_bad_image_projection import (  # noqa: E402
    T31Inputs,
    build_layer30_relation,
    load_t31_inputs,
    project_bad_image_atoms,
    replay_bad_image_witness,
    synthesize_p30,
)

_REMOVED = "phase=0,n=0,column=82"
_DESIGN_SHA256 = "93cecb3d3ce2c6a2610454f63302e26e2bbe57c7eba1825474bc808ad9ff76bd"
T31_SOURCE_DIGESTS = {
    "library": "62e46be94c8ce27f538257fd8d1a61fb5e582fa23b80ccfbf9b8bdd6ac3375e1",
    "runner": "da4ceebd20cf11e164a1e3228d96c53136fcbce8071055867a72d3869b60a732",
    "test": "3b88dadc423f41ec1ca81a2aea4df60071ad0d1a1165fc229c902012babc6b3e",
}
T31_COMMITS = ("69022cb", "adc6986", "619b737", "6835036")
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class EvidenceError(RuntimeError):
    """Frozen T32 input evidence changed or is internally inconsistent."""


@dataclass(frozen=True)
class PhaseLayout:
    phase: int
    a_original: str
    b_original: str
    lin_original: str
    rin_original: str
    lout_original: str
    rout_original: str

    def __post_init__(self) -> None:
        if not isinstance(self.phase, int) or isinstance(self.phase, bool):
            raise ValueError("phase index must be an integer")
        if not 0 <= self.phase < 6:
            raise ValueError("phase index must be in 0..5")
        names = (
            self.a_original,
            self.b_original,
            self.lin_original,
            self.rin_original,
            self.lout_original,
            self.rout_original,
        )
        if any(not isinstance(name, str) or not name for name in names):
            raise ValueError("phase layout names must be nonempty")


@dataclass(frozen=True)
class T32Inputs:
    t31_inputs: T31Inputs
    q0: LayerPredicate
    phases: tuple[PhaseLayout, ...]
    t31_witness: SemanticWitness
    t31_status: str
    t31_projected_atom_count: int
    t31_stop_detail: str
    t31_replay_residuals: tuple[int, ...]
    t31_q0_holds: bool
    source_digests: tuple[tuple[str, str], ...]
    t29_artifact_digests: tuple[tuple[str, str], ...]
    t30_artifact_digests: tuple[tuple[str, str], ...]
    t31_source_digests: tuple[tuple[str, str], ...]
    t31_commits: tuple[str, ...]
    design_sha256: str

    def __post_init__(self) -> None:
        if tuple(layout.phase for layout in self.phases) != tuple(range(6)):
            raise ValueError("T32 requires six ordered phase layouts")
        if self.t31_status != "NO_CANDIDATE":
            raise ValueError("T31 status boundary differs")
        if self.t31_projected_atom_count != 26:
            raise ValueError("T31 projected atom count differs")
        if self.t31_stop_detail != (
            "no projected atom excludes the first exact bad image"
        ):
            raise ValueError("T31 stop detail differs")
        if self.t31_replay_residuals != (0,) * 12 or self.t31_q0_holds:
            raise ValueError("T31 witness replay boundary differs")
        if self.source_digests != self.t31_inputs.source_digests:
            raise ValueError("T32 source digests differ")
        if self.t29_artifact_digests != self.t31_inputs.t29_artifact_digests:
            raise ValueError("T32 T29 artifact digests differ")
        if self.t30_artifact_digests != self.t31_inputs.t30_artifact_digests:
            raise ValueError("T32 T30 artifact digests differ")
        if self.t31_source_digests != tuple(sorted(T31_SOURCE_DIGESTS.items())):
            raise ValueError("T32 T31 source digests differ")
        if self.t31_commits != T31_COMMITS:
            raise ValueError("T32 T31 commits differ")
        if self.design_sha256 != _DESIGN_SHA256:
            raise ValueError("T32 design digest differs")


def _bind_raw(path: Path, expected: str, context: str) -> None:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise EvidenceError(f"cannot read {context}: {error}") from error
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected:
        raise EvidenceError(f"{context} raw SHA-256 changed: {actual}")


def _digit_key(atom: object) -> str | None:
    return atom.key


def _derive_phase_layouts(inputs: T31Inputs) -> tuple[PhaseLayout, ...]:
    relation = build_layer30_relation(inputs)
    equations = relation.equations
    if len(equations) != 12:
        raise EvidenceError("T32 relation no longer has 12 equations")
    layouts: list[PhaseLayout] = []
    for phase in range(6):
        left_equation = equations[2 * phase]
        right_equation = equations[2 * phase + 1]
        if left_equation.phase_column[0] != phase:
            raise EvidenceError(f"left equation phase differs at phase {phase}")
        if right_equation.phase_column[0] != phase:
            raise EvidenceError(f"right equation phase differs at phase {phase}")
        a_original = _digit_key(left_equation.left)
        b_original = _digit_key(left_equation.right)
        if a_original is None or b_original is None:
            raise EvidenceError(f"phase {phase} summands are no longer variables")
        if {_digit_key(right_equation.left), _digit_key(right_equation.right)} != {
            a_original,
            b_original,
        }:
            raise EvidenceError(f"phase {phase} paired summands differ")
        expected = {
            "lin": relation.input_mapping[f"L{phase}"],
            "rin": relation.input_mapping[f"R{phase}"],
            "lout": relation.output_mapping[f"L{phase}"],
            "rout": relation.output_mapping[f"R{phase}"],
        }
        actual = {
            "lin": left_equation.carry_in,
            "rin": right_equation.carry_out,
            "lout": left_equation.carry_out,
            "rout": right_equation.carry_in,
        }
        if actual != expected:
            raise EvidenceError(f"phase {phase} carry orientation differs")
        layouts.append(
            PhaseLayout(
                phase,
                a_original,
                b_original,
                expected["lin"],
                expected["rin"],
                expected["lout"],
                expected["rout"],
            )
        )

    if layouts[0].b_original != relation.output_mapping["D0"]:
        raise EvidenceError("phase-0 output digit orientation differs")
    if layouts[1].a_original != relation.input_mapping["D0"]:
        raise EvidenceError("phase-1 input digit orientation differs")
    for phase in range(1, 5):
        left_target = _digit_key(equations[2 * phase].target)
        right_target = _digit_key(equations[2 * phase + 1].target)
        if (left_target, right_target) != (
            layouts[phase + 1].b_original,
            layouts[phase + 1].a_original,
        ):
            raise EvidenceError(f"phase {phase} target chain differs")
    if equations[10].target.literal != 18:
        raise EvidenceError("phase-5 literal target differs")
    if _digit_key(equations[11].target) != layouts[0].a_original:
        raise EvidenceError("phase-5 closing target differs")
    if _digit_key(equations[0].target) != layouts[1].b_original:
        raise EvidenceError("phase-0 left target differs")
    if _digit_key(equations[1].target) != relation.output_mapping["D1"]:
        raise EvidenceError("phase-0 right target differs")
    return tuple(layouts)


@cache
def load_t32_inputs(
    root: Path,
    *,
    t31_library_path: Path | None = None,
    t31_runner_path: Path | None = None,
    t31_test_path: Path | None = None,
    design_path: Path | None = None,
) -> T32Inputs:
    """Bind frozen T29--T31 inputs and replay the exact T31 STOP witness."""
    root = Path(root)
    t31_paths = {
        "library": t31_library_path
        or root / ".timeloop/lib/lychrel_bad_image_projection.py",
        "runner": t31_runner_path
        or root / ".timeloop/runs/t31_base19_bad_image_projection.py",
        "test": t31_test_path
        or root / ".timeloop/tests/test_lychrel_bad_image_projection.py",
    }
    for name, path in t31_paths.items():
        _bind_raw(path, T31_SOURCE_DIGESTS[name], f"T31 {name}")
    _bind_raw(
        design_path
        or root
        / "docs/superpowers/specs/2026-08-10-base19-semantic-leak-types-restart-design.md",
        _DESIGN_SHA256,
        "T32 design",
    )

    try:
        t31_inputs = load_t31_inputs(root)
        records = project_bad_image_atoms(t31_inputs)
        result = synthesize_p30(t31_inputs, records)
    except (RuntimeError, ValueError) as error:
        raise EvidenceError(f"cannot replay T31 boundary: {error}") from error
    if (
        len(records) != 26
        or result.status != "NO_CANDIDATE"
        or result.p30 is not None
        or result.origins
        or result.predicate_bytes is not None
        or result.state_table_bytes != 616
        or len(result.counterexamples) != 1
        or result.stop_detail
        != "no projected atom excludes the first exact bad image"
    ):
        raise EvidenceError("T31 bounded synthesis boundary changed")
    witness = result.counterexamples[0]
    replay = replay_bad_image_witness(t31_inputs, witness)
    phases = _derive_phase_layouts(t31_inputs)
    return T32Inputs(
        t31_inputs=t31_inputs,
        q0=t31_inputs.q0,
        phases=phases,
        t31_witness=witness,
        t31_status=result.status,
        t31_projected_atom_count=len(records),
        t31_stop_detail=result.stop_detail,
        t31_replay_residuals=replay.equation_residuals,
        t31_q0_holds=replay.q0_holds,
        source_digests=t31_inputs.source_digests,
        t29_artifact_digests=t31_inputs.t29_artifact_digests,
        t30_artifact_digests=t31_inputs.t30_artifact_digests,
        t31_source_digests=tuple(sorted(T31_SOURCE_DIGESTS.items())),
        t31_commits=T31_COMMITS,
        design_sha256=_DESIGN_SHA256,
    )


def reconstruct_witness_assignment(
    inputs: T32Inputs, witness: SemanticWitness
) -> dict[str, int]:
    """Reconstruct and replay one complete original-variable assignment."""
    relation = build_layer30_relation(inputs.t31_inputs)
    assignment: dict[str, int] = {}

    def bind(original: str, value: int) -> None:
        if original in assignment:
            raise EvidenceError(f"semantic witness repeats variable: {original}")
        assignment[original] = value

    for prefixed, value in witness.input_state:
        canonical = prefixed.removeprefix("input:")
        if f"input:{canonical}" != prefixed or canonical not in relation.input_mapping:
            raise EvidenceError(f"semantic witness input is unknown: {prefixed}")
        bind(relation.input_mapping[canonical], value)
    for prefixed, value in witness.output_state:
        canonical = prefixed.removeprefix("output:")
        if f"output:{canonical}" != prefixed or canonical not in relation.output_mapping:
            raise EvidenceError(f"semantic witness output is unknown: {prefixed}")
        bind(relation.output_mapping[canonical], value)
    for prefixed, value in witness.local_state:
        original = prefixed.removeprefix("local:")
        if f"local:{original}" != prefixed:
            raise EvidenceError(f"semantic witness local is malformed: {prefixed}")
        bind(original, value)
    expected = set(relation.variables)
    actual = set(assignment)
    if actual != expected:
        raise EvidenceError(
            "semantic witness variables differ: "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )
    for name, value in assignment.items():
        if name.startswith("c:"):
            valid = value in {0, 1}
        else:
            lower = 1 if name.startswith("digit:p") and ":f0:d0" in name else 0
            valid = lower <= value < 19
        if not valid:
            raise EvidenceError(f"semantic witness domain failure: {name}={value}")
    residuals = tuple(
        equation.residual(assignment, 19) for equation in relation.equations
    )
    if residuals != (0,) * 12:
        raise EvidenceError(f"semantic witness residuals differ: {residuals}")
    return assignment


def structural_view(inputs: T32Inputs, witness: SemanticWitness) -> dict[str, int]:
    """Map one exact relation witness to the frozen structural feature names."""
    assignment = reconstruct_witness_assignment(inputs, witness)
    result: dict[str, int] = {}
    for layout in inputs.phases:
        phase = layout.phase
        result[f"a{phase}"] = assignment[layout.a_original]
        result[f"b{phase}"] = assignment[layout.b_original]
        result[f"Lin{phase}"] = assignment[layout.lin_original]
        result[f"Rin{phase}"] = assignment[layout.rin_original]
        result[f"Lout{phase}"] = assignment[layout.lout_original]
        result[f"Rout{phase}"] = assignment[layout.rout_original]
    return result


def q0_residuals(inputs: T32Inputs, witness: SemanticWitness) -> tuple[int, ...]:
    """Return the five signed Q0 equality residuals for one exact witness."""
    output = {
        name.removeprefix("output:"): value for name, value in witness.output_state
    }
    if set(output) != set(inputs.q0.variables):
        raise EvidenceError("semantic witness Q0 output scope differs")
    return tuple(
        sum(coefficient * output[name] for name, coefficient in atom.terms)
        - atom.constant
        for atom in inputs.q0.clauses[0].atoms
    )


def failure_mask(
    inputs: T32Inputs, witness: SemanticWitness
) -> tuple[bool, bool, bool, bool, bool]:
    residuals = q0_residuals(inputs, witness)
    if len(residuals) != 5:
        raise EvidenceError("Q0 no longer has five equations")
    return tuple(value != 0 for value in residuals)  # type: ignore[return-value]


@dataclass(frozen=True)
class FirstTypeMilestoneResult:
    status: str
    leak_type: LeakType | None
    witnesses: tuple[SemanticWitness, ...]
    failure_masks: tuple[tuple[bool, ...], ...]
    inspected_witness_count: int
    tested_candidate_count: int
    soundness_status: str | None
    independent_status: str | None
    stop_detail: str | None

    def __post_init__(self) -> None:
        statuses = {
            "PASS",
            "NO_SOUND_TYPE",
            "NO_DIVERSE_TYPE",
            "WITNESS_BUDGET_EXHAUSTED",
            "CANDIDATE_BUDGET_EXHAUSTED",
            "INDEPENDENT_DISAGREEMENT",
        }
        if self.status not in statuses:
            raise ValueError("unsupported first-type milestone status")
        if not 1 <= self.inspected_witness_count <= 128:
            raise ValueError("first-type inspected witness count is outside 1..128")
        if not 0 <= self.tested_candidate_count <= 2_000:
            raise ValueError("first-type tested candidate count is outside 0..2,000")
        if self.status == "PASS":
            if (
                self.leak_type is None
                or len(self.witnesses) != 2
                or len(self.failure_masks) != 2
                or self.failure_masks[0] == self.failure_masks[1]
                or self.soundness_status != "UNSAT"
                or self.independent_status != "PASS"
                or self.stop_detail is not None
            ):
                raise ValueError("first-type PASS gates differ")
        elif self.leak_type is not None or not self.stop_detail:
            raise ValueError("first-type STOP must omit the type and include detail")

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "leak_type": (
                None if self.leak_type is None else self.leak_type.to_payload()
            ),
            "witnesses": [witness.to_payload() for witness in self.witnesses],
            "failure_masks": [list(mask) for mask in self.failure_masks],
            "inspected_witness_count": self.inspected_witness_count,
            "tested_candidate_count": self.tested_candidate_count,
            "soundness_status": self.soundness_status,
            "independent_status": self.independent_status,
            "stop_detail": self.stop_detail,
        }


def _solver_status(relation: object, solver: object, context: str) -> str:
    status = solver.check()
    if status == relation.z3.unknown:
        raise EvidenceError(f"{context} returned UNKNOWN: {solver.reason_unknown()}")
    return "SAT" if status == relation.z3.sat else "UNSAT"


def _q0_expression(inputs: T32Inputs, relation: object) -> object:
    z3 = relation.z3
    return z3.And(
        *(
            sum(
                coefficient * relation.variables[relation.output_mapping[name]]
                for name, coefficient in atom.terms
            )
            == atom.constant
            for atom in inputs.q0.clauses[0].atoms
        )
    )


def _literal_expression(
    inputs: T32Inputs, relation: object, literal: StructuralLiteral
) -> object:
    layout = inputs.phases[literal.phase]
    variables = relation.variables
    names = {
        "a": variables[layout.a_original],
        "b": variables[layout.b_original],
        "Lin": variables[layout.lin_original],
        "Rin": variables[layout.rin_original],
        "Lout": variables[layout.lout_original],
        "Rout": variables[layout.rout_original],
    }
    if literal.kind == "digit_order":
        return {
            "eq": names["a"] == names["b"],
            "lt": names["a"] < names["b"],
            "gt": names["a"] > names["b"],
        }[literal.relation]
    if literal.kind == "digit_sum":
        total = names["a"] + names["b"]
        return {
            "lt19": total < 19,
            "eq18": total == 18,
            "ge19": total >= 19,
        }[literal.relation]
    pair = {
        "input_carry_pair": (names["Lin"], names["Rin"]),
        "output_carry_pair": (names["Lout"], names["Rout"]),
        "left_carry_flow": (names["Lin"], names["Lout"]),
        "right_carry_flow": (names["Rin"], names["Rout"]),
    }[literal.kind]
    return pair[0] == pair[1] if literal.relation == "eq" else pair[0] != pair[1]


def _type_expression(inputs: T32Inputs, relation: object, leak_type: LeakType) -> object:
    return relation.z3.And(
        *(
            _literal_expression(inputs, relation, literal)
            for literal in leak_type.literals
        )
    )


def _canonical_assignment(
    relation: object, solver: object, context: str
) -> tuple[tuple[str, int], ...]:
    if _solver_status(relation, solver, context) != "SAT":
        raise EvidenceError(f"cannot minimize non-SAT {context}")
    for name, variable in sorted(relation.variables.items()):
        domain = (
            range(2)
            if name.startswith("c:")
            else range(1 if name.startswith("digit:p") and ":f0:d0" in name else 0, 19)
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


def _witness_input(witness: SemanticWitness) -> tuple[int, ...]:
    return tuple(value for _, value in witness.input_state)


def _exact_witness(
    inputs: T32Inputs, relation: object, solver: object, context: str
) -> SemanticWitness:
    witness = _semantic_witness(relation, _canonical_assignment(relation, solver, context))
    assignment = reconstruct_witness_assignment(inputs, witness)
    if set(assignment) != set(relation.variables):
        raise EvidenceError(f"{context} witness scope differs")
    return witness


def _stop_result(
    status: str,
    inspected: int,
    tested: int,
    detail: str,
    *,
    soundness_status: str | None = None,
    independent_status: str | None = None,
) -> FirstTypeMilestoneResult:
    return FirstTypeMilestoneResult(
        status,
        None,
        (),
        (),
        inspected,
        tested,
        soundness_status,
        independent_status,
        detail,
    )


def _milestone_payload(
    inputs: T32Inputs,
    leak_type: LeakType,
    witnesses: tuple[SemanticWitness, SemanticWitness],
    masks: tuple[tuple[bool, ...], tuple[bool, ...]],
) -> dict[str, object]:
    return {
        "schema": "t32-base19-semantic-leak-type-milestone-v1",
        "leak_type": leak_type.to_payload(),
        "witnesses": [witness.to_payload() for witness in witnesses],
        "failure_masks": [list(mask) for mask in masks],
        "source_digests": dict(inputs.source_digests),
        "t29_artifact_digests": dict(inputs.t29_artifact_digests),
        "t30_artifact_digests": dict(inputs.t30_artifact_digests),
        "t31_source_digests": dict(inputs.t31_source_digests),
        "t31_commits": list(inputs.t31_commits),
        "design_sha256": inputs.design_sha256,
    }


def _run_independent_milestone(
    inputs: T32Inputs,
    leak_type: LeakType,
    witnesses: tuple[SemanticWitness, SemanticWitness],
    masks: tuple[tuple[bool, ...], tuple[bool, ...]],
) -> tuple[str, str | None]:
    run_dir = _REPOSITORY_ROOT / ".timeloop/runs"
    paths = (
        _REPOSITORY_ROOT / "publication/base19-radial/instance/equations.json",
        _REPOSITORY_ROOT
        / "publication/base19-radial/certificates/minimal-core-frontier.json",
        run_dir / "t27_base19_invariant_lift.json",
        run_dir / "t28_base19_tail_quotient.json",
        run_dir / "t28_base19_tail_quotient_independent.json",
        run_dir / "t29_base19_reachability_separator_trace.json",
        run_dir / "t29_base19_reachability_separator_dataset.json",
        run_dir / "t29_base19_reachability_separator.json",
        run_dir / "t29_base19_reachability_separator_certificate.json",
        run_dir / "t29_base19_reachability_separator_independent.json",
        run_dir / "t30_base19_exact_image_refinement.json",
        run_dir / "t30_base19_exact_image_refinement_certificate.json",
        run_dir / "t30_base19_exact_image_refinement_independent.json",
    )
    payload = _milestone_payload(inputs, leak_type, witnesses, masks)
    with tempfile.TemporaryDirectory(prefix="t32-milestone-") as directory:
        milestone_path = Path(directory) / "milestone.json"
        milestone_path.write_bytes(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
            + b"\n"
        )
        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                str(run_dir / "t32_base19_semantic_leak_types_independent.py"),
                "milestone",
                *(str(path) for path in paths),
                str(milestone_path),
            ],
            cwd=_REPOSITORY_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
    if completed.returncode != 0:
        return "REJECT", completed.stderr.strip()
    try:
        audit = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        return "REJECT", f"independent output is malformed: {error}"
    if (
        not isinstance(audit, dict)
        or audit.get("status") != "PASS"
        or audit.get("soundness_status") != "UNSAT"
        or audit.get("repository_imports") != []
    ):
        return "REJECT", "independent milestone gates differ"
    return "PASS", None


_FIRST_TYPE_CACHE: dict[tuple[int, int, int], FirstTypeMilestoneResult] = {}


def find_first_leak_type(
    inputs: T32Inputs,
    witness_limit: int = 128,
    candidate_limit: int = 2_000,
) -> FirstTypeMilestoneResult:
    """Search the bounded 84-literal language for one sound diverse leak type."""
    if (
        not isinstance(witness_limit, int)
        or isinstance(witness_limit, bool)
        or not 1 <= witness_limit <= 128
    ):
        raise ValueError("witness limit must be in 1..128")
    if (
        not isinstance(candidate_limit, int)
        or isinstance(candidate_limit, bool)
        or not 1 <= candidate_limit <= 2_000
    ):
        raise ValueError("candidate limit must be in 1..2,000")
    cache_key = (id(inputs), witness_limit, candidate_limit)
    cached = _FIRST_TYPE_CACHE.get(cache_key)
    if cached is not None:
        return cached
    relation = build_layer30_relation(inputs.t31_inputs)
    z3 = relation.z3
    seed = inputs.t31_witness
    seed_assignment = reconstruct_witness_assignment(inputs, seed)
    seed_input = _witness_input(seed)
    seed_mask = failure_mask(inputs, seed)
    inspected = [seed]
    exclusions = [
        z3.Or(
            *(
                relation.variables[name] != value
                for name, value in sorted(seed_assignment.items())
            )
        )
    ]
    pool = generate_literal_pool()
    tested_bytes: set[bytes] = set()
    tested_count = 0

    while len(inspected) < witness_limit:
        bad_solver = z3.Solver()
        bad_solver.add(*relation.assertions, z3.Not(_q0_expression(inputs, relation)))
        bad_solver.add(*exclusions)
        try:
            if _solver_status(relation, bad_solver, "bad-image discovery") == "UNSAT":
                result = _stop_result(
                    "NO_DIVERSE_TYPE",
                    len(inspected),
                    tested_count,
                    "all exact bad images were exhausted before a diverse pair",
                )
                _FIRST_TYPE_CACHE[cache_key] = result
                return result
            witness = _exact_witness(inputs, relation, bad_solver, "bad-image discovery")
        except EvidenceError as error:
            result = _stop_result(
                "WITNESS_BUDGET_EXHAUSTED",
                len(inspected),
                tested_count,
                str(error),
            )
            _FIRST_TYPE_CACHE[cache_key] = result
            return result
        assignment = reconstruct_witness_assignment(inputs, witness)
        exclusions.append(
            z3.Or(
                *(
                    relation.variables[name] != value
                    for name, value in sorted(assignment.items())
                )
            )
        )
        if witness in inspected:
            raise EvidenceError("first-type search repeated a canonical witness")
        inspected.append(witness)
        mask = failure_mask(inputs, witness)
        if _witness_input(witness) == seed_input or mask == seed_mask:
            continue

        first_view = structural_view(inputs, seed)
        second_view = structural_view(inputs, witness)
        intersection = tuple(
            literal
            for literal in pool
            if evaluate_literal(literal, first_view)
            and evaluate_literal(literal, second_view)
        )
        candidates = []
        for size in range(1, min(6, len(intersection)) + 1):
            candidates.extend(
                LeakType(tuple(selected))
                for selected in itertools.combinations(intersection, size)
            )
            if len(candidates) >= candidate_limit - tested_count:
                break
        candidates.sort(key=type_objective)
        for leak_type in candidates:
            candidate_bytes = json.dumps(
                leak_type.to_payload(),
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            if candidate_bytes in tested_bytes:
                continue
            if tested_count >= candidate_limit:
                result = _stop_result(
                    "CANDIDATE_BUDGET_EXHAUSTED",
                    len(inspected),
                    tested_count,
                    f"no sound diverse type found after {candidate_limit} conjunctions",
                )
                _FIRST_TYPE_CACHE[cache_key] = result
                return result
            tested_bytes.add(candidate_bytes)
            tested_count += 1
            type_expression = _type_expression(inputs, relation, leak_type)
            diversity_solver = z3.Solver()
            diversity_solver.add(*relation.assertions, type_expression)
            diversity_solver.add(
                z3.Or(
                    *(
                        relation.variables[relation.input_mapping[name]] != value
                        for (prefixed, value) in seed.input_state
                        for name in (prefixed.removeprefix("input:"),)
                    )
                )
            )
            try:
                if _solver_status(relation, diversity_solver, "type diversity") != "SAT":
                    continue
                diversity_model = _exact_witness(
                    inputs, relation, diversity_solver, "type diversity"
                )
                if _witness_input(diversity_model) == seed_input:
                    raise EvidenceError("type diversity replay repeated the seed input")
                soundness_solver = z3.Solver()
                soundness_solver.add(
                    *relation.assertions,
                    type_expression,
                    _q0_expression(inputs, relation),
                )
                soundness = _solver_status(relation, soundness_solver, "type soundness")
                if soundness == "SAT":
                    _exact_witness(inputs, relation, soundness_solver, "type countermodel")
                    continue
            except EvidenceError as error:
                result = _stop_result(
                    "NO_SOUND_TYPE",
                    len(inspected),
                    tested_count,
                    str(error),
                )
                _FIRST_TYPE_CACHE[cache_key] = result
                return result
            witnesses = (seed, witness)
            masks = (seed_mask, mask)
            if not all(
                evaluate_leak_type(leak_type, structural_view(inputs, item))
                for item in witnesses
            ):
                raise EvidenceError("primary type witnesses failed structural replay")
            independent_status, detail = _run_independent_milestone(
                inputs, leak_type, witnesses, masks
            )
            if independent_status != "PASS":
                result = _stop_result(
                    "INDEPENDENT_DISAGREEMENT",
                    len(inspected),
                    tested_count,
                    detail or "independent milestone rejected the primary type",
                    soundness_status="UNSAT",
                    independent_status=independent_status,
                )
                _FIRST_TYPE_CACHE[cache_key] = result
                return result
            result = FirstTypeMilestoneResult(
                "PASS",
                leak_type,
                witnesses,
                masks,
                len(inspected),
                tested_count,
                "UNSAT",
                "PASS",
                None,
            )
            _FIRST_TYPE_CACHE[cache_key] = result
            return result

        if tested_count >= candidate_limit:
            result = _stop_result(
                "CANDIDATE_BUDGET_EXHAUSTED",
                len(inspected),
                tested_count,
                f"no sound diverse type found after {candidate_limit} conjunctions",
            )
            _FIRST_TYPE_CACHE[cache_key] = result
            return result

    result = _stop_result(
        "WITNESS_BUDGET_EXHAUSTED",
        len(inspected),
        tested_count,
        f"no sound diverse type found after {witness_limit} bad images",
    )
    _FIRST_TYPE_CACHE[cache_key] = result
    return result
