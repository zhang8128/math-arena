#!/usr/bin/env python3
"""Certify a reachability-side refinement of the base-19 T29 separator."""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from lychrel_invariant_certificate import (  # noqa: E402
    Conjunction,
    LayerPredicate,
    LinearAtom,
    canonical_bytes,
)
from lychrel_reachability_separator import (  # noqa: E402
    SeparatorCertificate,
    SeparatorDataset,
    parse_counterexample_trace,
    parse_separator_certificate,
)
from t29_base19_reachability_separator import (  # noqa: E402
    T29Inputs,
    build_separator_dataset,
    dataset_payload,
    load_t29_inputs,
    trace_payload,
)

_REMOVED = "phase=0,n=0,column=82"
_SOURCE_DIGESTS = (
    ("equations", "ff79f31cbc55d7c463e6a14faedaad58d880509d5769e56b9a4bd06ebacd9040"),
    ("frontier", "0d25cf4645b3c187c74511b0677ea1481c4ba6c923a726ffea9747ee1b4a64c0"),
    ("provenances", "cac34c9317e8209bfea6a4e4fb37ef204346ccde54424f8c93dd8a8e40619302"),
    ("t27_evidence", "32324c40903b78aec4d787b7e64a6d73d0999e3846d91ca1340c99f8ac2d8686"),
    ("t28_evidence", "b0904f68fda4ad7990ac1d474ec157cf671567cdf02869d9ae2cceebe1814e47"),
    ("t28_independent", "7f095af25afc02ff48fe4d2ee53b4827ba99fa1548a5d970e475780fdaa1639e"),
)
T29_ARTIFACT_DIGESTS = {
    "certificate": "1c234891f001cb3a59e5670560ab26e3cb248a943e249aee049aac7d32c7db5a",
    "dataset": "6603e381805db845ef9388d234e36f31eba510d838ac98c143c238c2ff144995",
    "evidence": "c1e3dc4bc4ab07207a6ab49d6a9c9fd86486013abeaf016b6ecd59c9755e1d32",
    "independent": "9f926208cc7416e24d811f6cd54485d19741b6f8ffe44f3b365b2f816e579644",
    "trace": "c56877975293c10575009a691b1d1bbde376838f805d232a2c18a4d00b2c4715",
}


class EvidenceError(RuntimeError):
    """Frozen T30 input evidence is malformed, changed, or inconsistent."""


@dataclass(frozen=True)
class T30Inputs:
    t29_inputs: T29Inputs
    t29_certificate: SeparatorCertificate
    dataset: SeparatorDataset
    variables: tuple[str, ...]
    t29_leak: tuple[tuple[str, int], ...]
    source_digests: tuple[tuple[str, str], ...]
    t29_artifact_digests: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if self.source_digests != _SOURCE_DIGESTS:
            raise ValueError("T30 source digests differ")
        if self.t29_artifact_digests != tuple(sorted(T29_ARTIFACT_DIGESTS.items())):
            raise ValueError("T30 T29 artifact digests differ")
        if self.variables != self.dataset.variables or len(self.variables) != 14:
            raise ValueError("T30 variable scope differs")
        if tuple(name for name, _ in self.t29_leak) != self.variables:
            raise ValueError("T30 leak scope differs")


def _read_mapping(path: Path, context: str) -> tuple[bytes, Mapping[str, object]]:
    try:
        raw = path.read_bytes()
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError, UnicodeError) as error:
        raise EvidenceError(f"cannot read {context}: {error}") from error
    if not isinstance(payload, Mapping):
        raise EvidenceError(f"{context} must be a JSON object")
    return raw, payload


def _read_bound_mapping(
    path: Path, expected_sha256: str, context: str
) -> Mapping[str, object]:
    raw, payload = _read_mapping(path, context)
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected_sha256:
        raise EvidenceError(
            f"{context} raw SHA-256 changed: expected {expected_sha256}, got {actual}"
        )
    return payload


def _content_digest(payload: object) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def build_q0(variables: tuple[str, ...]) -> LayerPredicate:
    """Return the frozen five-equation layer-31 refinement candidate."""
    return LayerPredicate(
        layer=31,
        variables=variables,
        clauses=(
            Conjunction(
                (
                    LinearAtom(
                        "eq",
                        (("L1", 1), ("L4", -1), ("L5", 1), ("R4", -1)),
                        0,
                    ),
                    LinearAtom(
                        "eq",
                        (
                            ("L1", 1),
                            ("L2", -2),
                            ("L4", -2),
                            ("L5", -2),
                            ("R1", -3),
                            ("R2", 3),
                            ("R3", 2),
                            ("R4", 1),
                        ),
                        0,
                    ),
                    LinearAtom(
                        "eq",
                        (
                            ("L0", 3),
                            ("L1", 1),
                            ("L2", 2),
                            ("L5", -2),
                            ("R1", -3),
                            ("R3", 1),
                        ),
                        3,
                    ),
                    LinearAtom(
                        "eq",
                        (
                            ("D1", 1),
                            ("L0", 3),
                            ("L1", -2),
                            ("L2", -3),
                            ("L3", 1),
                            ("L4", 1),
                            ("R0", -1),
                            ("R1", -3),
                            ("R2", -3),
                            ("R3", 3),
                            ("R4", -1),
                        ),
                        9,
                    ),
                    LinearAtom(
                        "eq",
                        (
                            ("D0", 1),
                            ("D1", -1),
                            ("L0", -1),
                            ("R0", 1),
                            ("R5", 1),
                        ),
                        1,
                    ),
                )
            ),
        ),
    )


def _parse_dataset(payload: Mapping[str, object]) -> SeparatorDataset:
    expected = {
        "schema",
        "source_digests",
        "variables",
        "positives",
        "trace_negatives",
        "live_controls",
        "counts",
    }
    if set(payload) != expected:
        raise EvidenceError("T29 dataset keys differ")
    variables = payload["variables"]
    positives = payload["positives"]
    trace_negatives = payload["trace_negatives"]
    live_controls = payload["live_controls"]
    if not isinstance(variables, list) or not all(
        isinstance(variable, str) for variable in variables
    ):
        raise EvidenceError("T29 dataset variables are malformed")
    if any(not isinstance(rows, list) for rows in (positives, trace_negatives, live_controls)):
        raise EvidenceError("T29 dataset rows are malformed")
    try:
        return SeparatorDataset(
            variables=tuple(variables),
            positives=tuple(tuple(row) for row in positives),  # type: ignore[arg-type]
            trace_negatives=tuple(tuple(row) for row in trace_negatives),  # type: ignore[arg-type]
            live_controls=tuple(tuple(row) for row in live_controls),  # type: ignore[arg-type]
        )
    except (TypeError, ValueError) as error:
        raise EvidenceError(f"T29 dataset is malformed: {error}") from error


def _parse_t29_leak(payload: Mapping[str, object]) -> tuple[tuple[str, int], ...]:
    witness = payload.get("semantic_counterexample")
    if not isinstance(witness, Mapping):
        raise EvidenceError("T29 semantic leak is missing")
    input_state = witness.get("input_state")
    if not isinstance(input_state, Mapping):
        raise EvidenceError("T29 semantic leak input is malformed")
    leak = []
    for prefixed, value in input_state.items():
        if (
            not isinstance(prefixed, str)
            or not prefixed.startswith("input:")
            or not isinstance(value, int)
            or isinstance(value, bool)
        ):
            raise EvidenceError("T29 semantic leak input is malformed")
        leak.append((prefixed.removeprefix("input:"), value))
    return tuple(sorted(leak))


def load_t30_inputs(
    root: Path,
    *,
    evidence_path: Path | None = None,
    trace_path: Path | None = None,
    dataset_path: Path | None = None,
    certificate_path: Path | None = None,
    independent_path: Path | None = None,
) -> T30Inputs:
    """Load and cross-check the complete frozen T29 boundary used by T30."""
    root = Path(root)
    run_dir = root / ".timeloop" / "runs"
    paths = {
        "evidence": evidence_path
        or run_dir / "t29_base19_reachability_separator.json",
        "trace": trace_path
        or run_dir / "t29_base19_reachability_separator_trace.json",
        "dataset": dataset_path
        or run_dir / "t29_base19_reachability_separator_dataset.json",
        "certificate": certificate_path
        or run_dir / "t29_base19_reachability_separator_certificate.json",
        "independent": independent_path
        or run_dir / "t29_base19_reachability_separator_independent.json",
    }
    payloads = {
        name: _read_bound_mapping(path, T29_ARTIFACT_DIGESTS[name], f"T29 {name}")
        for name, path in paths.items()
    }
    evidence = payloads["evidence"]
    trace_payload_raw = payloads["trace"]
    dataset_payload_raw = payloads["dataset"]
    certificate_payload = payloads["certificate"]
    independent = payloads["independent"]

    try:
        t29_inputs = load_t29_inputs(root)
    except (RuntimeError, ValueError) as error:
        raise EvidenceError(f"cannot bind T29 source inputs: {error}") from error
    if t29_inputs.source_digests != _SOURCE_DIGESTS or t29_inputs.removed != _REMOVED:
        raise EvidenceError("T29 source boundary changed")

    if (
        evidence.get("schema") != "t29-base19-reachability-separator-evidence-v1"
        or evidence.get("status") != "FINITE_SEPARATOR_PASS_SEMANTIC_STOP"
        or evidence.get("finite_status") != "PASS"
        or evidence.get("semantic_status") != "SAT"
        or evidence.get("stop_reason") != "semantic_successor_found"
        or evidence.get("base") != 19
        or evidence.get("removed") != _REMOVED
        or evidence.get("source_digests") != dict(_SOURCE_DIGESTS)
    ):
        raise EvidenceError("T29 primary boundary changed")

    trace_core = {
        key: trace_payload_raw[key]
        for key in ("schema", "variables", "steps", "terminal_iteration", "stop_reason")
        if key in trace_payload_raw
    }
    try:
        trace = parse_counterexample_trace(trace_core)
    except ValueError as error:
        raise EvidenceError(f"T29 trace is malformed: {error}") from error
    if trace_payload(trace) != trace_payload_raw:
        raise EvidenceError("T29 trace content changed")

    dataset = _parse_dataset(dataset_payload_raw)
    reconstructed_dataset = build_separator_dataset(t29_inputs, trace)
    if dataset != reconstructed_dataset or dataset_payload(dataset) != dataset_payload_raw:
        raise EvidenceError("T29 dataset content changed")

    try:
        certificate = parse_separator_certificate(certificate_payload)
    except ValueError as error:
        raise EvidenceError(f"T29 certificate is malformed: {error}") from error
    if (
        certificate.removed != _REMOVED
        or certificate.source_digests != _SOURCE_DIGESTS
        or certificate.finite_status != "PASS"
        or certificate.semantic_status != "SAT"
        or certificate.semantic_witness is None
        or certificate.to_payload() != certificate_payload
        or evidence.get("finite_predicate") != certificate.predicate.to_payload()
        or evidence.get("trace_sha256") != _content_digest(trace_payload_raw)
        or evidence.get("dataset_sha256") != _content_digest(dataset_payload_raw)
        or evidence.get("certificate_sha256") != _content_digest(certificate_payload)
    ):
        raise EvidenceError("T29 certificate cross-binding changed")

    if (
        independent.get("schema")
        != "t29-base19-reachability-separator-independent-v1"
        or independent.get("status") != "FINITE_SEPARATOR_PASS_SEMANTIC_STOP"
        or independent.get("repository_imports") != []
        or independent.get("primary_evidence_sha256")
        != T29_ARTIFACT_DIGESTS["evidence"]
        or independent.get("certificate_file_sha256")
        != T29_ARTIFACT_DIGESTS["certificate"]
        or independent.get("source_digests") != dict(_SOURCE_DIGESTS)
        or independent.get("trace_sha256") != evidence.get("trace_sha256")
        or independent.get("dataset_sha256") != evidence.get("dataset_sha256")
        or independent.get("semantic_successor_replayed") is not True
    ):
        raise EvidenceError("T29 independent boundary changed")

    counts = evidence.get("counts")
    if counts != {"positives": 12, "trace_negatives": 221, "live_controls": 6}:
        raise EvidenceError("T29 finite counts changed")
    leak = _parse_t29_leak(evidence)
    return T30Inputs(
        t29_inputs=t29_inputs,
        t29_certificate=certificate,
        dataset=dataset,
        variables=dataset.variables,
        t29_leak=leak,
        source_digests=_SOURCE_DIGESTS,
        t29_artifact_digests=tuple(sorted(T29_ARTIFACT_DIGESTS.items())),
    )
