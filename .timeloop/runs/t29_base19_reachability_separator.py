#!/usr/bin/env python3
"""Synthesize and verify a reachability-aware base-19 separator."""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from lychrel_reachability_separator import (  # noqa: E402
    CounterexampleTrace,
    SeparatorDataset,
)
from t27_base19_invariant_lift import EvidenceError  # noqa: E402
from t28_base19_tail_quotient import (  # noqa: E402
    CandidatePartition,
    T28Inputs,
    discover_reachable_quotient,
    load_t28_inputs,
)

_SOURCE_DIGESTS = (
    (
        "equations",
        "ff79f31cbc55d7c463e6a14faedaad58d880509d5769e56b9a4bd06ebacd9040",
    ),
    (
        "frontier",
        "0d25cf4645b3c187c74511b0677ea1481c4ba6c923a726ffea9747ee1b4a64c0",
    ),
    (
        "provenances",
        "cac34c9317e8209bfea6a4e4fb37ef204346ccde54424f8c93dd8a8e40619302",
    ),
    (
        "t27_evidence",
        "32324c40903b78aec4d787b7e64a6d73d0999e3846d91ca1340c99f8ac2d8686",
    ),
    (
        "t28_evidence",
        "b0904f68fda4ad7990ac1d474ec157cf671567cdf02869d9ae2cceebe1814e47",
    ),
    (
        "t28_independent",
        "7f095af25afc02ff48fe4d2ee53b4827ba99fa1548a5d970e475780fdaa1639e",
    ),
)
_EXPECTED_CLASS_FAMILIES = {
    "DEAD": (),
    "Q00": ("T_HIGH_DIGIT",),
    "Q01": ("T_PHASE_ZERO",),
    "Q02": ("T_RESIDUE",),
}
_EXPECTED_CLASS_SIZES = {"DEAD": 12, "Q00": 2, "Q01": 1, "Q02": 3}


@dataclass(frozen=True)
class SeparatorLimits:
    coefficients: tuple[int, ...] = tuple(range(-3, 4))
    moduli: tuple[int, ...] = tuple(range(2, 21))
    max_clauses: int = 3
    max_atoms_per_clause: int = 12
    max_candidate_atoms: int = 512

    def __post_init__(self) -> None:
        if self.coefficients != tuple(range(-3, 4)):
            raise ValueError("separator coefficients must remain frozen at -3..3")
        if self.moduli != tuple(range(2, 21)):
            raise ValueError("separator moduli must remain frozen at 2..20")
        if self.max_clauses != 3:
            raise ValueError("separator clause ceiling must remain three")
        if self.max_atoms_per_clause != 12:
            raise ValueError("separator clause width must remain twelve")
        if self.max_candidate_atoms < 1 or self.max_candidate_atoms > 512:
            raise ValueError("candidate atom ceiling must lie in 1..512")


@dataclass(frozen=True)
class T29Inputs:
    t28_inputs: T28Inputs
    partition: CandidatePartition
    source_digests: tuple[tuple[str, str], ...]
    removed: str
    final_counterexample: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        if self.partition.layer != 31:
            raise ValueError("T29 requires the layer-31 partition")
        if self.source_digests != _SOURCE_DIGESTS:
            raise ValueError("T29 source digests differ from the frozen identities")
        if self.removed != "phase=0,n=0,column=82":
            raise ValueError("T29 removed-coordinate identity changed")


def _read_mapping(path: Path, context: str) -> tuple[bytes, Mapping[str, object]]:
    try:
        raw = path.read_bytes()
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError) as error:
        raise EvidenceError(f"cannot read frozen {context}: {error}") from error
    if not isinstance(payload, Mapping):
        raise EvidenceError(f"frozen {context} must be a JSON object")
    return raw, payload


def _require_digest(raw: bytes, expected: str, context: str) -> None:
    if hashlib.sha256(raw).hexdigest() != expected:
        raise EvidenceError(f"T29 frozen {context} digest changed")


def _parse_final_counterexample(payload: Mapping[str, object]) -> tuple[tuple[str, int], ...]:
    counterexample = payload.get("counterexample")
    if not isinstance(counterexample, Mapping):
        raise EvidenceError("T28 evidence omitted its final counterexample")
    if (
        counterexample.get("rejected_class") != "DEAD"
        or counterexample.get("obligation") != "dead_has_no_successor"
    ):
        raise EvidenceError("T28 final counterexample identity changed")
    state = counterexample.get("state")
    if not isinstance(state, Mapping) or any(
        not isinstance(name, str)
        or not isinstance(value, int)
        or isinstance(value, bool)
        for name, value in state.items()
    ):
        raise EvidenceError("T28 final counterexample state is malformed")
    assignment = tuple(sorted((name, value) for name, value in state.items()))
    if len(assignment) != 14:
        raise EvidenceError("T28 final counterexample scope changed")
    return assignment


def _validate_partition(partition: CandidatePartition) -> None:
    if len(partition.variables) != 14 or len(set(partition.variables)) != 14:
        raise EvidenceError("T29 layer-31 variable scope changed")
    families = {item.label: item.allowed_next for item in partition.classes}
    sizes = {item.label: len(item.members) for item in partition.classes}
    if families != _EXPECTED_CLASS_FAMILIES:
        raise EvidenceError("T29 layer-31 class families changed")
    if sizes != _EXPECTED_CLASS_SIZES:
        raise EvidenceError("T29 layer-31 class sizes changed")


def load_t29_inputs(
    root: Path,
    *,
    t27_evidence_path: Path | None = None,
    t28_evidence_path: Path | None = None,
    t28_independent_path: Path | None = None,
) -> T29Inputs:
    """Load and bind every frozen source used by the T29 finite question."""
    root = Path(root)
    primary_path = t28_evidence_path or (
        root / ".timeloop" / "runs" / "t28_base19_tail_quotient.json"
    )
    independent_path = t28_independent_path or (
        root / ".timeloop" / "runs" / "t28_base19_tail_quotient_independent.json"
    )
    primary_raw, primary = _read_mapping(primary_path, "T28 evidence")
    independent_raw, independent = _read_mapping(
        independent_path,
        "T28 independent audit",
    )
    source = dict(_SOURCE_DIGESTS)
    _require_digest(primary_raw, source["t28_evidence"], "T28 evidence")
    _require_digest(
        independent_raw,
        source["t28_independent"],
        "T28 independent audit",
    )
    if (
        primary.get("schema") != "t28-base19-tail-quotient-evidence-v1"
        or primary.get("status") != "STOP"
        or primary.get("stop_reason") != "decision_depth_exceeded"
    ):
        raise EvidenceError("T28 primary boundary changed")
    if primary.get("frozen_hashes") != dict(_SOURCE_DIGESTS[:4]):
        raise EvidenceError("T28 primary source identities changed")
    if (
        independent.get("schema")
        != "t28-base19-tail-quotient-independent-v1"
        or independent.get("status") != "STOP"
        or independent.get("primary_evidence_sha256") != source["t28_evidence"]
        or independent.get("counterexample_successor_exists") is not True
    ):
        raise EvidenceError("T28 independent boundary changed")

    t28_inputs = load_t28_inputs(root, t27_evidence_path=t27_evidence_path)
    partition = discover_reachable_quotient(t28_inputs, 31, 32)[0]
    _validate_partition(partition)
    if primary.get("layer31_variables") != list(partition.variables):
        raise EvidenceError("T28 serialized layer-31 scope changed")
    return T29Inputs(
        t28_inputs=t28_inputs,
        partition=partition,
        source_digests=_SOURCE_DIGESTS,
        removed=str(primary.get("removed")),
        final_counterexample=_parse_final_counterexample(primary),
    )


def _project_state(
    state: tuple[int, ...],
    source_variables: tuple[str, ...],
    target_variables: tuple[str, ...],
) -> tuple[int, ...]:
    assignment = dict(zip(source_variables, state, strict=True))
    return tuple(assignment[variable] for variable in target_variables)


def build_separator_dataset(
    inputs: T29Inputs,
    trace: CounterexampleTrace,
) -> SeparatorDataset:
    """Build the exact finite T29 classification question."""
    variables = tuple(sorted(inputs.partition.variables))
    if trace.variables != variables:
        raise EvidenceError("T29 trace variable scope changed")
    if (
        len(trace.steps) != 221
        or trace.terminal_iteration != 222
        or trace.stop_reason != "decision_depth_exceeded"
    ):
        raise EvidenceError("T29 trace boundary changed")
    if any(
        step.rejected_class != "DEAD"
        or step.obligation != "dead_has_no_successor"
        for step in trace.steps
    ):
        raise EvidenceError("T29 trace obligation identity changed")
    if trace.steps[-1].input_state != inputs.final_counterexample:
        raise EvidenceError("T29 trace final state disagrees with T28 evidence")

    classes = {item.label: item for item in inputs.partition.classes}
    positives = tuple(
        sorted(
            _project_state(member, inputs.partition.variables, variables)
            for member in classes["DEAD"].members
        )
    )
    live_controls = tuple(
        sorted(
            _project_state(member, inputs.partition.variables, variables)
            for label in ("Q00", "Q01", "Q02")
            for member in classes[label].members
        )
    )
    trace_negatives = tuple(
        sorted(tuple(value for _, value in step.input_state) for step in trace.steps)
    )
    return SeparatorDataset(
        variables=variables,
        positives=positives,
        trace_negatives=trace_negatives,
        live_controls=live_controls,
    )


def trace_payload(trace: CounterexampleTrace) -> dict[str, object]:
    """Serialize a trace with its frozen source identities and exact count."""
    payload = trace.to_payload()
    payload["source_digests"] = dict(_SOURCE_DIGESTS)
    payload["counts"] = {"counterexamples": len(trace.steps)}
    return payload


def dataset_payload(dataset: SeparatorDataset) -> dict[str, object]:
    """Serialize the exact finite dataset canonically."""
    return {
        "schema": "t29-base19-reachability-separator-dataset-v1",
        "source_digests": dict(_SOURCE_DIGESTS),
        **dataset.to_payload(),
        "counts": {
            "positives": len(dataset.positives),
            "trace_negatives": len(dataset.trace_negatives),
            "live_controls": len(dataset.live_controls),
        },
    }
