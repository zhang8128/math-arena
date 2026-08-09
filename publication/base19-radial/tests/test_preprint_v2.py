import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ARTIFACT = ROOT / "publication" / "base19-radial"
PREPRINT = ARTIFACT / "preprint-v2"


def render_preprint_data(
    artifact_dir: Path, output: Path, *, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        (
            sys.executable,
            str(ARTIFACT / "scripts" / "render_preprint_v2_data.py"),
            "--artifact-dir",
            str(artifact_dir),
            "--output",
            str(output),
        ),
        check=check,
        text=True,
        capture_output=not check,
    )


def copied_artifact(tmp_path: Path) -> Path:
    destination = tmp_path / "base19-radial"
    shutil.copytree(ARTIFACT, destination)
    return destination


def redigest(payload: dict[str, object]) -> dict[str, object]:
    unsigned = dict(payload)
    unsigned.pop("content_sha256", None)
    payload["content_sha256"] = hashlib.sha256(
        (json.dumps(unsigned, sort_keys=True, separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
    ).hexdigest()
    return payload


def update_checksum(artifact: Path, relative_path: str) -> None:
    checksum_path = artifact / "SHA256SUMS"
    digest = hashlib.sha256((artifact / relative_path).read_bytes()).hexdigest()
    lines = checksum_path.read_text(encoding="utf-8").splitlines()
    checksum_path.write_text(
        "\n".join(
            f"{digest}  {relative_path}" if line.endswith(f"  {relative_path}") else line
            for line in lines
        )
        + "\n",
        encoding="utf-8",
    )


def test_bibliography_contains_every_required_primary_source() -> None:
    source = (PREPRINT / "references.bib").read_text(encoding="utf-8")
    for key in (
        "brownSeal",
        "oeisA060382",
        "Freuder1990",
        "DechterPearl1989",
        "deMouraUllrich2021",
        "CruzFilipeEtAl2017",
        "BaekCarneiroHeule2022",
        "cadical301",
        "z3Arithmetic",
        "leanBVDecide432",
    ):
        assert f"{{{key}," in source


def test_lean_bv_citation_discloses_native_evaluation_boundary() -> None:
    source = (PREPRINT / "citation-matrix.md").read_text(encoding="utf-8")
    match = re.search(r"^\|.*\| `leanBVDecide432` \|$", source, flags=re.MULTILINE)
    assert match is not None
    row = match.group(0)
    for required_fact in (
        "proved-sound LRAT checker",
        "`nativeEqTrue`",
        "packedMinimalCoreUnsat._native.bv_decide.ax_1_5",
        "f3b06c705e6c85f5314019d5d3baab0fec5b580c",
        "Std/Tactic/BVDecide/Reflect.lean",
        "Std/Tactic/BVDecide/LRAT/Checker.lean",
        "Lean/Meta/Tactic/BVDecide/Prover/Bitblast.lean",
    ):
        assert required_fact in row
    assert "soundness reduces to the verified checker" not in row


def test_generated_results_are_deterministic_and_bound_to_evidence(
    tmp_path: Path,
) -> None:
    output = tmp_path / "generated-results.tex"
    render_preprint_data(ARTIFACT, output)
    assert output.read_bytes() == (PREPRINT / "generated-results.tex").read_bytes()
    source = output.read_text(encoding="utf-8")
    assert r"\newcommand{\PackedWidth}{4914}" in source
    assert r"\newcommand{\PackedSlotWidth}{6}" in source
    assert r"\newcommand{\PackedConstraintCount}{1233}" in source
    assert r"\newcommand{\PackedLeanSeconds}{51.01}" in source


def test_generated_results_escape_evidence_derived_latex_strings(tmp_path: Path) -> None:
    output = tmp_path / "generated-results.tex"
    render_preprint_data(ARTIFACT, output)

    source = output.read_text(encoding="utf-8")
    assert (
        r"\newcommand{\GenericSoundnessTheorem}"
        r"{\texttt{Base19Radial.unsat\_of\_closed\_empty\_frontier}}"
    ) in source
    assert (
        r"\newcommand{\PackedTheorem}"
        r"{\texttt{Base19Radial.packedMinimalCoreUnsat}}"
    ) in source


def test_generated_results_reject_packed_source_not_matching_promoted_checksum(
    tmp_path: Path,
) -> None:
    artifact = copied_artifact(tmp_path)
    source_path = artifact / "lean" / "Base19Radial" / "Generated" / "CoreBV.lean"
    source = source_path.read_text(encoding="utf-8")
    source_path.write_text(
        source.replace(
            "packedSlot assignment 0 < (19 : BitVec 6)",
            "packedSlot assignment 1 < (19 : BitVec 6)",
            1,
        ),
        encoding="utf-8",
    )

    completed = render_preprint_data(artifact, tmp_path / "tampered.tex", check=False)
    assert completed.returncode != 0
    assert "CoreBV.lean checksum mismatch" in completed.stderr


def test_generated_results_reject_altered_packed_run_context(tmp_path: Path) -> None:
    artifact = copied_artifact(tmp_path)
    manifest_path = artifact / "artifact-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    run = manifest["measured_runs"]["lean_packed_core_bv"]
    run["axioms"][-1] = "packedMinimalCoreUnsat._native.bv_decide.ax_9_9"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    completed = render_preprint_data(artifact, tmp_path / "tampered.tex", check=False)
    assert completed.returncode != 0
    assert "packed Lean run context changed" in completed.stderr


def test_generated_results_reject_terminal_layer_latex_injection(tmp_path: Path) -> None:
    artifact = copied_artifact(tmp_path)
    core_path = artifact / "certificates" / "minimal-core-frontier.json"
    core = json.loads(core_path.read_text(encoding="utf-8"))
    core["layers"][-1]["layer"] = r"}\input{owned}"
    core_path.write_text(json.dumps(redigest(core)), encoding="utf-8")

    completed = render_preprint_data(artifact, tmp_path / "tampered.tex", check=False)
    assert completed.returncode != 0
    assert "minimal-core certificate layer is invalid" in completed.stderr


def test_generated_results_reject_packed_source_with_matching_mutable_checksum(
    tmp_path: Path,
) -> None:
    artifact = copied_artifact(tmp_path)
    relative_source = "lean/Base19Radial/Generated/CoreBV.lean"
    source_path = artifact / relative_source
    source = source_path.read_text(encoding="utf-8")
    source_path.write_text(
        source.replace(
            "packedSlot assignment 0 < (19 : BitVec 6)",
            "packedSlot assignment 1 < (19 : BitVec 6)",
            1,
        ),
        encoding="utf-8",
    )
    update_checksum(artifact, relative_source)

    completed = render_preprint_data(artifact, tmp_path / "tampered.tex", check=False)
    assert completed.returncode != 0
    assert "CoreBV.lean does not match the deterministic renderer" in completed.stderr


def test_generated_results_reject_redigested_core_relabelled_as_known_sat_removal(
    tmp_path: Path,
) -> None:
    artifact = copied_artifact(tmp_path)
    witness = json.loads(
        (artifact / "certificates" / "delete-p0-c0.json").read_text(encoding="utf-8")
    )
    core_path = artifact / "certificates" / "minimal-core-frontier.json"
    core = json.loads(core_path.read_text(encoding="utf-8"))
    core["removed"] = witness["removed"]
    core_path.write_text(json.dumps(redigest(core)), encoding="utf-8")
    source_path = artifact / "lean" / "Base19Radial" / "Generated" / "CoreBV.lean"
    source_path.write_text(
        source_path.read_text(encoding="utf-8").replace(
            'def packedCoreRemovedProvenance : String := "phase=0,n=0,column=82"',
            'def packedCoreRemovedProvenance : String := "phase=0,n=0,column=0"',
        ),
        encoding="utf-8",
    )

    completed = render_preprint_data(artifact, tmp_path / "tampered.tex", check=False)
    assert completed.returncode != 0
    assert "core removal is not the audit's unique UNSAT deletion" in completed.stderr


def test_generated_results_reject_redigested_witness_relabelled_to_p0c1(
    tmp_path: Path,
) -> None:
    artifact = copied_artifact(tmp_path)
    witness_path = artifact / "certificates" / "delete-p0-c0.json"
    witness = json.loads(witness_path.read_text(encoding="utf-8"))
    witness["removed"] = "phase=0,n=0,column=1"
    witness_path.write_text(json.dumps(redigest(witness)), encoding="utf-8")

    completed = render_preprint_data(artifact, tmp_path / "tampered.tex", check=False)
    assert completed.returncode != 0
    assert "known deletion witness does not satisfy retained equations" in completed.stderr


def test_preprint_source_has_submission_metadata_and_trust_boxes() -> None:
    source = (PREPRINT / "main.tex").read_text(encoding="utf-8")
    assert r"\author{8128}" in source
    assert "A Proof-Producing Base-19 Obstruction" in source
    assert r"\newtcolorbox{keyidea}" in source
    assert r"\newtcolorbox{trustboundary}" in source
    assert r"\newtcolorbox{nonclaim}" in source
    assert r"\hypersetup" in source
    assert "pdfauthor={8128}" in source
