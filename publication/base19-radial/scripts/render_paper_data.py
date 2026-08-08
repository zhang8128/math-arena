#!/usr/bin/env python3
"""Render paper-facing numerical claims from promoted artifact data."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def command(name: str, value: object) -> str:
    return rf"\newcommand{{\{name}}}{{{value}}}"


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render(artifact_dir: Path) -> str:
    certificates = artifact_dir / "certificates"
    manifest = load_object(artifact_dir / "artifact-manifest.json")
    equations = load_object(artifact_dir / "instance" / "equations.json")
    frontier = load_object(certificates / "frontier.json")
    core = load_object(certificates / "minimal-core-frontier.json")
    witness = load_object(certificates / "delete-p0-c0.json")
    deletion_path = certificates / "deletions.jsonl"
    deletions = [
        json.loads(line)
        for line in deletion_path.read_text(encoding="utf-8").splitlines()
    ]
    if equations.get("base") != 19 or equations.get("equation_count") != 409:
        raise ValueError("equation manifest is not the frozen base-19 instance")
    if frontier.get("status") != "UNSAT" or frontier.get("equation_count") != 409:
        raise ValueError("candidate frontier is not the promoted UNSAT certificate")
    if core.get("status") != "UNSAT" or core.get("equation_count") != 408:
        raise ValueError("minimal-core frontier is not the promoted UNSAT certificate")
    if witness.get("status") != "SAT" or witness.get("equation_count") != 408:
        raise ValueError("known deletion witness is not the promoted SAT certificate")
    sat_deletions = sum(item.get("status") == "SAT" for item in deletions)
    unsat_deletions = sum(item.get("status") == "UNSAT" for item in deletions)
    if len(deletions) != 409 or (sat_deletions, unsat_deletions) != (408, 1):
        raise ValueError("deletion audit status counts changed")
    measured = manifest.get("measured_runs")
    if not isinstance(measured, dict):
        raise ValueError("artifact manifest measured runs are missing")

    values = [
        ("BaseValue", equations["base"]),
        ("CandidateEquationCount", frontier["equation_count"]),
        ("CoreEquationCount", core["equation_count"]),
        ("RadialLayerCount", len(core["layers"])),
        ("TerminalLayer", core["layers"][-1]["layer"]),
        ("PeakReachableStates", core["max_reachable_state_count"]),
        ("MaximumFrontierDigits", core["max_frontier_digit_count"]),
        ("MaximumFrontierCarries", core["max_frontier_carry_count"]),
        ("ActiveDigitCount", core["active_digit_count"]),
        ("ActiveCarryCount", core["active_carry_count"]),
        ("DeletionAuditCount", len(deletions)),
        ("SatDeletionCount", sat_deletions),
        ("UnsatDeletionCount", unsat_deletions),
        ("RemovedCoreEquation", r"\texttt{phase=0,n=0,column=82}"),
        ("KnownSatRemovedEquation", r"\texttt{phase=0,n=0,column=0}"),
        (
            "CoreReplaySeconds",
            f"{measured['independent_minimal_core_replay']['wall_seconds']:.2f}",
        ),
        (
            "CertificateGenerationSeconds",
            f"{measured['three_certificate_regeneration']['wall_seconds']:.2f}",
        ),
        (
            "DeletionAuditSeconds",
            f"{measured['deletion_audit_successful_resume']['wall_seconds']:.2f}",
        ),
        (
            "CleanCloneSeconds",
            f"{measured['clean_clone_quick_reproduction']['wall_seconds']:.2f}",
        ),
        (
            "LeanWitnessSeconds",
            f"{measured['lean_delete_p0_c0_witness']['wall_seconds']:.2f}",
        ),
        (
            "CandidateCertificateSha",
            r"\texttt{" + file_sha(certificates / "frontier.json") + "}",
        ),
        (
            "CoreCertificateSha",
            r"\texttt{" + file_sha(certificates / "minimal-core-frontier.json") + "}",
        ),
        (
            "DeletionAuditSha",
            r"\texttt{" + file_sha(deletion_path) + "}",
        ),
        (
            "GenericSoundnessTheorem",
            r"\texttt{Base19Radial.unsat\_of\_closed\_empty\_frontier}",
        ),
        (
            "ConcreteSatTheorem",
            r"\texttt{Base19Radial.deleteP0C0Sat}",
        ),
    ]
    return "% Generated; do not edit.\n" + "\n".join(
        command(name, value) for name, value in values
    ) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(args.artifact_dir), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
