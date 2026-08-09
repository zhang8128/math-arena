import hashlib
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[3]
ARTIFACT = ROOT / "publication" / "base19-radial"
PREPRINT = ARTIFACT / "preprint-v2"
CANDIDATE_CHECKSUM_PATHS = (
    "main.tex",
    "references.bib",
    "citation-matrix.md",
    "generated-results.tex",
    "build.sh",
    "README.md",
    "main.pdf",
)

BIBTEX_ENTRY = re.compile(
    r"^[ \t]*@(?P<entry_type>[A-Za-z]+)[ \t\r\n]*[({][ \t\r\n]*"
    r"(?P<key>[^,\s{}()]+)[ \t\r\n]*,",
    flags=re.MULTILINE,
)
NON_ENTRY_BIBTEX_TYPES = {"comment", "preamble", "string"}
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]\n]*\]\(([^)\n]+)\)")


def bibtex_entry_keys(source: str) -> tuple[str, ...]:
    keys = tuple(
        match.group("key")
        for match in BIBTEX_ENTRY.finditer(source)
        if match.group("entry_type").lower() not in NON_ENTRY_BIBTEX_TYPES
    )
    duplicates = sorted(key for key, count in Counter(keys).items() if count > 1)
    if duplicates:
        raise ValueError(f"duplicate BibTeX entry keys: {', '.join(duplicates)}")
    return keys


def tex_citation_keys(source: str) -> set[str]:
    groups = re.findall(
        r"\\cite(?:\s*\[[^\]]*\]){0,2}\s*\{([^{}]+)\}",
        source,
    )
    return {key.strip() for group in groups for key in group.split(",") if key.strip()}


def matrix_citation_keys(source: str) -> set[str]:
    keys: set[str] = set()
    in_citation_table = False
    for line in source.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells[-1] in {"Citation key", "Citation"}:
            in_citation_table = True
            continue
        if not in_citation_table or re.fullmatch(r":?-+:?", cells[-1]):
            continue
        keys.update(
            key
            for key in re.findall(r"`([^`]+)`", cells[-1])
            if re.fullmatch(r"[A-Za-z][A-Za-z0-9:._-]*", key)
        )
    return keys


def repository_relative_matrix_paths(source: str) -> tuple[Path, ...]:
    paths: list[Path] = []
    for raw_destination in MARKDOWN_LINK.findall(source):
        destination = raw_destination.split(maxsplit=1)[0]
        parsed = urlsplit(destination)
        if (
            parsed.scheme
            or parsed.netloc
            or destination.startswith(("/", "#", "//"))
            or not parsed.path
        ):
            continue
        paths.append(Path(unquote(parsed.path)))
    return tuple(paths)


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


def extracted_pdf_text(tmp_path: Path) -> str:
    output = tmp_path / "preprint.txt"
    subprocess.run(
        ("pdftotext", str(PREPRINT / "main.pdf"), str(output)),
        check=True,
    )
    return output.read_text(encoding="utf-8")


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


def test_bibtex_key_parser_reads_entries_and_rejects_duplicates() -> None:
    source = """
This prose mentions `incidentalKey`, but it is not a bibliography entry.
@comment{ignoredDirective, even though it contains a comma}
@string{journalName = "Journal"}
@article{
  firstKey,
  title = {First}
}
@misc( secondKey,
  title = {Second}
)
"""
    assert bibtex_entry_keys(source) == ("firstKey", "secondKey")

    with pytest.raises(ValueError, match="duplicate BibTeX entry keys: firstKey"):
        bibtex_entry_keys(source + "\n@book{firstKey, title = {Duplicate}}\n")


def test_defined_used_and_matrix_citation_key_sets_are_exactly_equal() -> None:
    tex = (PREPRINT / "main.tex").read_text(encoding="utf-8")
    bib = (PREPRINT / "references.bib").read_text(encoding="utf-8")
    matrix = (PREPRINT / "citation-matrix.md").read_text(encoding="utf-8")

    defined = set(bibtex_entry_keys(bib))
    used = tex_citation_keys(tex)
    matrix_keys = matrix_citation_keys(matrix)
    assert defined == used == matrix_keys


def test_citation_parsers_handle_groups_without_incidental_code_spans() -> None:
    assert tex_citation_keys(r"Text \cite[see][p.~4]{firstKey, secondKey}.") == {
        "firstKey",
        "secondKey",
    }
    matrix = """\
| Claim with `incidentalKey` and `scripts/not-a-citation.py` | Citation |
| --- | --- |
| Supported by two sources | `firstKey`, `secondKey` plus artifact evidence |
"""
    assert matrix_citation_keys(matrix) == {"firstKey", "secondKey"}


def test_every_repository_relative_matrix_artifact_path_resolves() -> None:
    matrix_path = PREPRINT / "citation-matrix.md"
    matrix = matrix_path.read_text(encoding="utf-8")
    paths = repository_relative_matrix_paths(matrix)
    assert paths
    for relative_path in paths:
        resolved = (matrix_path.parent / relative_path).resolve()
        assert resolved.is_relative_to(ROOT.resolve())
        assert resolved.exists(), f"citation-matrix artifact path does not exist: {relative_path}"


def test_matrix_path_audit_ignores_nonlinks_and_external_links() -> None:
    matrix = """\
`Lean/Meta/Tactic/BVDecide/Reflect.lean`, `lake env lean`, and prose/path are not links.
[External source](https://example.test/source) and [section](#scope) are not artifacts.
[Artifact](../scripts/build_manifest.py) is repository-relative.
"""
    assert repository_relative_matrix_paths(matrix) == (
        Path("../scripts/build_manifest.py"),
    )


def test_cadical_citation_matches_the_pinned_lean_binary(tmp_path: Path) -> None:
    bib = (PREPRINT / "references.bib").read_text(encoding="utf-8")
    matrix = (PREPRINT / "citation-matrix.md").read_text(encoding="utf-8")
    pdf_text = extracted_pdf_text(tmp_path)

    assert "@misc{cadical212," in bib
    assert "cadical301" not in bib
    for required_fact in (
        "rel-2.1.2",
        "3ff42f04384489916f017acd6d5e7cbfa7257be7",
        "lake env cadical --version",
        "2.1.2",
        "Lean/Meta/Tactic/BVDecide/TacticContext.lean#L49-L57",
        "Lean/Meta/Tactic/BVDecide/External.lean#L140-L166",
        "`cadical212`",
    ):
        assert required_fact in matrix
    assert "cadical301" not in matrix
    assert "CaDiCaL 2.1.2" in pdf_text
    assert "lake env cadical --version" in pdf_text


def test_reproducibility_lean_commands_restore_repository_root() -> None:
    lean_sequence = """(cd publication/base19-radial/lean &&
  lake env cadical --version &&
  lake env lean Base19Radial/Generated/CoreBV.lean)"""
    for path in (PREPRINT / "README.md", PREPRINT / "main.tex"):
        source = path.read_text(encoding="utf-8")
        assert lean_sequence in source
        assert "Run the Docker commands from the repository root" in source


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


def test_preprint_build_script_rejects_overfull_hboxes_and_vboxes() -> None:
    source = (PREPRINT / "build.sh").read_text(encoding="utf-8")
    assert r"Overfull \\[hv]box" in source


def test_preprint_reader_visible_claims_and_radial_figure(tmp_path: Path) -> None:
    text = extracted_pdf_text(tmp_path)
    for phrase in (
        "deletion-minimal",
        "not minimum-cardinality",
        "does not establish a base-19 Lychrel number",
        "closed empty frontier",
        "radial frontier",
    ):
        assert phrase in text

    source = (PREPRINT / "main.tex").read_text(encoding="utf-8")
    assert r"\begin{tikzpicture}" in source
    assert r"\label{fig:radial-frontier}" in source


def test_preprint_reader_visible_packed_trust_boundary_and_assurance_figure(
    tmp_path: Path,
) -> None:
    text = extracted_pdf_text(tmp_path)
    for phrase in (
        "packedMinimalCoreUnsat",
        "packedMinimalCoreUnsat._native.bv_decide.ax_1_5",
        "native certificate-evaluation axiom",
        "not kernel-reduction-only",
        "Classical.choice",
        "Quot.sound",
        "37<64",
        "unformalized bridge",
    ):
        assert phrase in text

    source = (PREPRINT / "main.tex").read_text(encoding="utf-8")
    assert r"\label{fig:assurance-ladder}" in source


def test_preprint_bibliography_preserves_suffixes_and_identifiers(
    tmp_path: Path,
) -> None:
    bib = (PREPRINT / "references.bib").read_text(encoding="utf-8")
    assert bib.count("Hunt, Jr., Warren A.") == 2
    assert "{SAT} Solver" in bib
    assert "{SAT} 2014" in bib
    assert "{A060382}" in bib

    text = " ".join(extracted_pdf_text(tmp_path).split())
    assert text.count("Warren A. Hunt, Jr.") == 2
    assert "CaDiCaL SAT solver" in text
    assert "sequences, A060382" in text


def test_preprint_states_the_exact_packed_slot_traversal(tmp_path: Path) -> None:
    text = " ".join(extracted_pdf_text(tmp_path).split())
    for phrase in (
        "canonical retained-equation order",
        "left, right, target",
        "carry_in, carry_out",
        "digit-slot list before the carry-slot list",
    ):
        assert phrase in text


def test_preprint_extracts_ascii_extract_lsb_prime(tmp_path: Path) -> None:
    text = extracted_pdf_text(tmp_path)
    assert "extractLsb'" in text


def test_assurance_figure_follows_section_intro_in_pdf_page_order(
    tmp_path: Path,
) -> None:
    pages = [" ".join(page.split()) for page in extracted_pdf_text(tmp_path).split("\f")]
    figure_pages = [page for page in pages if "Exact Z3 frontier replay" in page]
    assert len(figure_pages) == 1
    page = figure_pages[0]
    assert page.index("7 Assurance ladder") < page.index(
        "The preceding distinctions can be arranged"
    ) < page.index("Exact Z3 frontier replay")


def test_preprint_explains_word_orientation_and_growth_boundary(
    tmp_path: Path,
) -> None:
    text = " ".join(extracted_pdf_text(tmp_path).split())
    for phrase in (
        "most-significant digit first",
        "least-significant target column",
        "initial and final boundary carries are zero",
        "phase-5 column 83",
        "both source atoms are literal zero",
    ):
        assert phrase in text


def test_preprint_reader_visible_reproducibility_identifiers(tmp_path: Path) -> None:
    text = extracted_pdf_text(tmp_path)
    for identifier in (
        "Base19Radial.unsat_of_closed_empty_frontier",
        "Base19Radial.deleteP0C0Sat",
        "Base19Radial.packedMinimalCoreUnsat",
        "18ca75da64c84859d2373ae3e61da81e3ac75a68a33af448b57220e23dfbfa9e",
        "1ce1b3c59bd95264e5338f7fba5bdffa15fb7635917964980057615395cf138c",
        "7635e7188197021cfc15cbad6d087f6fdbfa7a8bbfe4e4ed9b91a15a89498c67",
        "0566f6e2025aec28fe0d2f824f1f6b343cf912e9191a9036629a2a1d4ef03325",
    ):
        assert identifier in text


def test_candidate_pdf_and_local_checksums_are_current() -> None:
    pdf = PREPRINT / "main.pdf"
    assert pdf.stat().st_size > 100_000

    entries = [
        line.split("  ", 1)
        for line in (PREPRINT / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    ]
    assert tuple(relative for _, relative in entries) == CANDIDATE_CHECKSUM_PATHS
    for expected, relative in entries:
        actual = hashlib.sha256((PREPRINT / relative).read_bytes()).hexdigest()
        assert actual == expected


def test_offline_build_lead_in_stays_with_command_block(tmp_path: Path) -> None:
    pages = [
        " ".join(page.split())
        for page in extracted_pdf_text(tmp_path).split("\f")
    ]
    assert any(
        "the exact AMD64, network-disabled build is:" in page
        and "docker build --platform linux/amd64 --network none" in page
        for page in pages
    )
