#!/usr/bin/env python3
"""Render preprint-v2 macros from validated frozen artifact evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

EQUATION_SCHEMA = "base19-radial-equations-v1"
FRONTIER_SCHEMA = "base19-radial-frontier-v1"
CORE_SCHEMA = "base19-radial-minimal-core-frontier-v1"
WITNESS_SCHEMA = "base19-radial-witness-v1"
DELETION_SCHEMA = "base19-radial-deletion-v1"
PACKED_THEOREM = "Base19Radial.packedMinimalCoreUnsat"
PACKED_COMMAND = "lake env lean Base19Radial/Generated/CoreBV.lean"
PACKED_LEAN_VERSION = "4.32.2"
PACKED_AXIOMS = [
    "propext",
    "Classical.choice",
    "Quot.sound",
    "packedMinimalCoreUnsat._native.bv_decide.ax_1_5",
]
LATEX_TEXT_ESCAPES = {
    "\\": r"\textbackslash{}",
    "{": r"\{",
    "}": r"\}",
    "#": r"\#",
    "$": r"\$",
    "%": r"\%",
    "&": r"\&",
    "_": r"\_",
    "^": r"\^{}",
    "~": r"\~{}",
}


def canonical_bytes(payload: object) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def validate_content_digest(payload: dict[str, Any], label: str) -> None:
    unsigned = dict(payload)
    expected = unsigned.pop("content_sha256", None)
    actual = hashlib.sha256(canonical_bytes(unsigned)).hexdigest()
    if not isinstance(expected, str) or expected != actual:
        raise ValueError(f"{label} content digest mismatch")


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(name: str, value: object) -> str:
    return rf"\newcommand{{\{name}}}{{{value}}}"


def latex_texttt(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("LaTeX text value must be a string")
    return r"\texttt{" + "".join(LATEX_TEXT_ESCAPES.get(char, char) for char in value) + "}"


def require_int(value: object, label: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{label} must be an integer")
    return value


def require_number(value: object, label: str) -> float:
    if type(value) not in (int, float):
        raise ValueError(f"{label} must be a number")
    return float(value)


def validate_promoted_checksum(artifact_dir: Path, relative_path: str) -> None:
    checksum_path = artifact_dir / "SHA256SUMS"
    expected: str | None = None
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            raise ValueError("SHA256SUMS has an invalid entry")
        digest, path = match.groups()
        if path == relative_path:
            if expected is not None:
                raise ValueError(f"SHA256SUMS has duplicate {relative_path} entries")
            expected = digest
    if expected is None:
        raise ValueError(f"SHA256SUMS does not bind {relative_path}")
    if file_sha(artifact_dir / relative_path) != expected:
        raise ValueError(f"{Path(relative_path).name} checksum mismatch")


def atom_variable(atom: object, base: int) -> str | None:
    if not isinstance(atom, dict):
        raise ValueError("equation atom is malformed")
    if set(atom) == {"variable"} and isinstance(atom["variable"], str):
        return atom["variable"]
    if set(atom) == {"literal"} and type(atom["literal"]) is int:
        if not 0 <= atom["literal"] < base:
            raise ValueError("equation literal is outside the digit range")
        return None
    raise ValueError("equation atom is malformed")


def append_unique(items: list[str], value: str | None) -> None:
    if value is not None and value not in items:
        items.append(value)


def packed_shape(
    equations: dict[str, Any], core: dict[str, Any], core_source: str
) -> tuple[int, int, int]:
    base = require_int(equations.get("base"), "equation base")
    all_equations = equations.get("equations")
    removed = core.get("removed")
    if not isinstance(all_equations, list) or not isinstance(removed, str):
        raise ValueError("equation/core structure is malformed")
    retained = [
        equation
        for equation in all_equations
        if isinstance(equation, dict) and equation.get("provenance") != removed
    ]
    if len(retained) != require_int(core.get("equation_count"), "core equation count"):
        raise ValueError("packed core retention does not match the core certificate")

    digits: list[str] = []
    carries: list[str] = []
    for equation in retained:
        if not isinstance(equation.get("provenance"), str):
            raise ValueError("equation provenance is malformed")
        for key in ("left", "right", "target"):
            append_unique(digits, atom_variable(equation.get(key), base))
        for key in ("carry_in", "carry_out"):
            carry = equation.get(key)
            if carry is not None and (not isinstance(carry, str) or not carry.startswith("c:")):
                raise ValueError("equation carry is malformed")
            append_unique(carries, carry)

    if len(digits) != require_int(core.get("active_digit_count"), "core digit count"):
        raise ValueError("packed core digit count changed")
    if len(carries) != require_int(core.get("active_carry_count"), "core carry count"):
        raise ValueError("packed core carry count changed")

    slot_definition = re.search(
        r"def packedSlot\s+\(assignment : BitVec (\d+)\) \(index : Nat\) "
        r": BitVec (\d+) :=\s+assignment\.extractLsb' \(index \* (\d+)\) (\d+)",
        core_source,
    )
    if slot_definition is None:
        raise ValueError("packed Lean source has no packed-slot definition")
    packed_width, slot_width, extraction_width, extraction_length = map(
        int, slot_definition.groups()
    )
    if slot_width != extraction_width or slot_width != extraction_length:
        raise ValueError("packed Lean slot widths disagree")
    if packed_width != (len(digits) + len(carries)) * slot_width:
        raise ValueError("packed Lean width disagrees with the frozen core")

    leading_digits = [name for name in digits if re.fullmatch(r"p\d+:f0:d0", name) is not None]
    theorem = re.search(
        r"theorem packedMinimalCoreUnsat .*?: ¬ \(\n(?P<constraints>.*?)\n\) := by",
        core_source,
        flags=re.DOTALL,
    )
    if theorem is None:
        raise ValueError("packed Lean UNSAT theorem is missing")
    constraint_count = len(theorem.group("constraints").splitlines())
    expected_constraints = len(digits) + len(leading_digits) + len(carries) + len(retained)
    if constraint_count != expected_constraints:
        raise ValueError("packed Lean constraint count disagrees with the frozen core")
    return packed_width, slot_width, constraint_count


def validated_deletions(
    path: Path, equations: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    records = path.read_bytes().splitlines()
    if len(records) != len(equations):
        raise ValueError("deletion audit record count changed")
    records_by_removal: dict[str, dict[str, Any]] = {}
    for index, (line, equation) in enumerate(zip(records, equations, strict=True)):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError("deletion audit contains invalid JSON") from error
        if not isinstance(record, dict):
            raise ValueError("deletion audit record is not an object")
        validate_content_digest(record, "deletion audit record")
        if (
            record.get("schema") != DELETION_SCHEMA
            or record.get("candidate_index") != index
            or record.get("removed") != equation.get("provenance")
            or record.get("equation_count") != len(equations) - 1
        ):
            raise ValueError("deletion audit record is not bound to the equation manifest")
        status = record.get("status")
        if status not in {"SAT", "UNSAT"}:
            raise ValueError("deletion audit status is not exact")
        removed = record["removed"]
        if not isinstance(removed, str) or removed in records_by_removal:
            raise ValueError("deletion audit removal records are invalid")
        records_by_removal[removed] = record
    return records_by_removal


def measured_run(manifest: dict[str, Any], name: str) -> dict[str, Any]:
    runs = manifest.get("measured_runs")
    if not isinstance(runs, dict) or not isinstance(runs.get(name), dict):
        raise ValueError(f"measured run {name} is missing")
    return runs[name]


def formatted_run_seconds(manifest: dict[str, Any], name: str, label: str) -> str:
    run = measured_run(manifest, name)
    return f"{require_number(run.get('wall_seconds'), label):.2f}"


def validate_packed_run(run: dict[str, Any], equation_sha: str) -> None:
    if (
        run.get("command") != PACKED_COMMAND
        or run.get("lean_version") != PACKED_LEAN_VERSION
        or run.get("theorem") != PACKED_THEOREM
        or run.get("manifest_sha256") != equation_sha
        or run.get("axioms") != PACKED_AXIOMS
    ):
        raise ValueError("packed Lean run context changed")
    if not math.isfinite(require_number(run.get("wall_seconds"), "packed Lean wall seconds")) or (
        require_number(run.get("wall_seconds"), "packed Lean wall seconds") <= 0
    ):
        raise ValueError("packed Lean wall seconds must be positive and finite")
    if require_int(run.get("max_rss_bytes"), "packed Lean maximum RSS") <= 0:
        raise ValueError("packed Lean maximum RSS must be positive")


def validate_certificate_summary(payload: dict[str, Any], base: int, label: str) -> None:
    if require_int(payload.get("base"), f"{label} base") != base:
        raise ValueError(f"{label} base changed")
    layers = payload.get("layers")
    if not isinstance(layers, list) or not layers:
        raise ValueError(f"{label} layers are missing")
    if not all(isinstance(layer, dict) for layer in layers):
        raise ValueError(f"{label} layer is malformed")
    maximums = {
        "max_reachable_state_count": "output_state_count",
        "max_frontier_digit_count": "output_frontier_digit_count",
        "max_frontier_carry_count": "output_frontier_carry_count",
    }
    for summary_key, layer_key in maximums.items():
        if require_int(payload.get(summary_key), f"{label} {summary_key}") != max(
            require_int(layer.get(layer_key), f"{label} layer {layer_key}")
            for layer in layers
        ):
            raise ValueError(f"{label} {summary_key} disagrees with its layers")


def claim_theorem(manifest: dict[str, Any], identifier: str) -> str:
    claims = manifest.get("claims")
    if not isinstance(claims, list):
        raise ValueError("manifest claims are missing")
    for claim in claims:
        if isinstance(claim, dict) and claim.get("id") == identifier:
            theorem = claim.get("lean_theorem")
            if isinstance(theorem, str):
                return theorem
    raise ValueError(f"manifest claim {identifier} has no Lean theorem")


def render(artifact_dir: Path) -> str:
    certificates = artifact_dir / "certificates"
    equation_path = artifact_dir / "instance" / "equations.json"
    deletion_path = certificates / "deletions.jsonl"
    core_bv_path = artifact_dir / "lean" / "Base19Radial" / "Generated" / "CoreBV.lean"
    manifest = load_object(artifact_dir / "artifact-manifest.json")
    equations = load_object(equation_path)
    frontier = load_object(certificates / "frontier.json")
    core = load_object(certificates / "minimal-core-frontier.json")
    witness = load_object(certificates / "delete-p0-c0.json")
    for payload, label in (
        (equations, "equation manifest"),
        (frontier, "frontier certificate"),
        (core, "minimal-core certificate"),
        (witness, "deletion witness"),
    ):
        validate_content_digest(payload, label)

    equation_sha = file_sha(equation_path)
    base = require_int(equations.get("base"), "equation base")
    all_equations = equations.get("equations")
    if (
        equations.get("schema") != EQUATION_SCHEMA
        or base != 19
        or equations.get("equation_count") != 409
        or not isinstance(all_equations, list)
        or len(all_equations) != 409
    ):
        raise ValueError("equation manifest is not the frozen base-19 instance")
    if not all(isinstance(equation, dict) for equation in all_equations):
        raise ValueError("equation manifest contains a malformed equation")

    if (
        frontier.get("schema") != FRONTIER_SCHEMA
        or frontier.get("status") != "UNSAT"
        or frontier.get("equation_count") != len(all_equations)
        or frontier.get("equations_sha256") != equation_sha
    ):
        raise ValueError("candidate frontier is not bound to the equation manifest")
    validate_certificate_summary(frontier, base, "candidate frontier")
    if (
        core.get("schema") != CORE_SCHEMA
        or core.get("status") != "UNSAT"
        or core.get("equations_sha256") != equation_sha
        or core.get("deletions_sha256") != file_sha(deletion_path)
    ):
        raise ValueError("minimal-core certificate is not bound to frozen evidence")
    validate_certificate_summary(core, base, "minimal-core certificate")
    if (
        witness.get("schema") != WITNESS_SCHEMA
        or witness.get("status") != "SAT"
        or witness.get("equations_sha256") != equation_sha
        or witness.get("equation_count") != core.get("equation_count")
    ):
        raise ValueError("known deletion witness is not bound to frozen evidence")
    validate_certificate_summary(witness, base, "known deletion witness")
    if (
        witness.get("active_digit_count") != core.get("active_digit_count")
        or witness.get("active_carry_count") != core.get("active_carry_count")
    ):
        raise ValueError("known deletion witness variable counts changed")
    replay = witness.get("witness_replay")
    expected_replay = {
        "status": "valid",
        "equation_count": core["equation_count"],
        "digit_count": core["active_digit_count"],
        "carry_count": core["active_carry_count"],
    }
    if replay != expected_replay:
        raise ValueError("known deletion witness replay metadata changed")

    deletion_records = validated_deletions(deletion_path, all_equations)
    sat_deletions = sum(record["status"] == "SAT" for record in deletion_records.values())
    unsat_deletions = sum(
        record["status"] == "UNSAT" for record in deletion_records.values()
    )
    if (sat_deletions, unsat_deletions) != (core["equation_count"], 1):
        raise ValueError("deletion audit status counts changed")
    core_removal = core.get("removed")
    if (
        not isinstance(core_removal, str)
        or deletion_records.get(core_removal, {}).get("status") != "UNSAT"
    ):
        raise ValueError("core removal is not the audit's unique UNSAT deletion")
    witness_removal = witness.get("removed")
    if (
        not isinstance(witness_removal, str)
        or deletion_records.get(witness_removal, {}).get("status") != "SAT"
    ):
        raise ValueError("known deletion witness removal is not SAT in the audit")

    packed_run = measured_run(manifest, "lean_packed_core_bv")
    validate_packed_run(packed_run, equation_sha)
    validate_promoted_checksum(
        artifact_dir, "lean/Base19Radial/Generated/CoreBV.lean"
    )
    core_source = core_bv_path.read_text(encoding="utf-8")
    packed_theorem_name = packed_run["theorem"].rsplit(".", maxsplit=1)[-1]
    if (
        f'def packedCoreManifestSha256 : String := "{equation_sha}"' not in core_source
        or f'def packedCoreRemovedProvenance : String := "{core["removed"]}"' not in core_source
        or "namespace Base19Radial" not in core_source
        or f"theorem {packed_theorem_name}" not in core_source
    ):
        raise ValueError("packed Lean source is not bound to the frozen core")
    packed_width, slot_width, constraint_count = packed_shape(equations, core, core_source)
    packed_max_rss = require_int(packed_run.get("max_rss_bytes"), "packed Lean maximum RSS")

    values = [
        ("BaseValue", base),
        ("CandidateEquationCount", frontier["equation_count"]),
        ("CoreEquationCount", core["equation_count"]),
        ("RadialLayerCount", len(core["layers"])),
        ("TerminalLayer", core["layers"][-1]["layer"]),
        ("PeakReachableStates", core["max_reachable_state_count"]),
        ("MaximumFrontierDigits", core["max_frontier_digit_count"]),
        ("MaximumFrontierCarries", core["max_frontier_carry_count"]),
        ("ActiveDigitCount", core["active_digit_count"]),
        ("ActiveCarryCount", core["active_carry_count"]),
        ("DeletionAuditCount", sat_deletions + unsat_deletions),
        ("SatDeletionCount", sat_deletions),
        ("UnsatDeletionCount", unsat_deletions),
        ("RemovedCoreEquation", latex_texttt(core["removed"])),
        ("KnownSatRemovedEquation", latex_texttt(witness["removed"])),
        (
            "CoreReplaySeconds",
            formatted_run_seconds(
                manifest, "independent_minimal_core_replay", "core replay wall seconds"
            ),
        ),
        (
            "CertificateGenerationSeconds",
            formatted_run_seconds(
                manifest,
                "three_certificate_regeneration",
                "certificate generation wall seconds",
            ),
        ),
        (
            "DeletionAuditSeconds",
            formatted_run_seconds(
                manifest,
                "deletion_audit_successful_resume",
                "deletion audit wall seconds",
            ),
        ),
        (
            "CleanCloneSeconds",
            formatted_run_seconds(
                manifest,
                "clean_clone_quick_reproduction",
                "clean-clone wall seconds",
            ),
        ),
        (
            "LeanWitnessSeconds",
            formatted_run_seconds(
                manifest,
                "lean_delete_p0_c0_witness",
                "Lean witness wall seconds",
            ),
        ),
        ("CandidateCertificateSha", latex_texttt(file_sha(certificates / "frontier.json"))),
        (
            "CoreCertificateSha",
            latex_texttt(file_sha(certificates / "minimal-core-frontier.json")),
        ),
        ("DeletionAuditSha", latex_texttt(file_sha(deletion_path))),
        (
            "GenericSoundnessTheorem",
            latex_texttt(claim_theorem(manifest, "generic_radial_soundness")),
        ),
        (
            "ConcreteSatTheorem",
            latex_texttt(claim_theorem(manifest, "delete_p0_c0_sat")),
        ),
        ("PackedWidth", packed_width),
        ("PackedSlotWidth", slot_width),
        ("PackedConstraintCount", constraint_count),
        (
            "PackedLeanSeconds",
            f"{require_number(packed_run.get('wall_seconds'), 'packed Lean wall seconds'):.2f}",
        ),
        ("PackedLeanMaxRSS", f"{packed_max_rss / 1_000_000_000:.2f}\\,GB"),
        ("PackedTheorem", latex_texttt(packed_run["theorem"])),
        ("PackedManifestSha", latex_texttt(packed_run["manifest_sha256"])),
    ]
    return (
        "% Generated; do not edit.\n"
        + "\n".join(command(name, value) for name, value in values)
        + "\n"
    )


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
