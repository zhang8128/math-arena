#!/usr/bin/env python3
"""Synthesize and certify structural base-19 semantic-leak mechanisms."""

from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from lychrel_invariant_certificate import LayerPredicate  # noqa: E402
from lychrel_reachability_separator import SemanticWitness  # noqa: E402
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
