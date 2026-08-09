# Textbook-Style Base-19 Preprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a reproducible, citation-complete, 10--12 page preprint candidate by author `8128` that explains the base-19 obstruction and its Lean/LRAT trust boundary with textbook-style organization and visuals.

**Architecture:** Preserve `publication/base19-radial/paper/` as the released paper and build the candidate in `publication/base19-radial/preprint-v2/`. A dedicated Python renderer reads only frozen artifact evidence and emits LaTeX macros; the hand-written paper consumes those macros, a verified bibliography, and two inline TikZ diagrams. Candidate-specific tests and checksums validate the build without promoting it over the released PDF.

**Tech Stack:** Python 3.13.5, pytest, Lean 4.32.2, `bv_decide`, CaDiCaL/LRAT, LaTeX/latexmk, BibTeX, TikZ, tcolorbox, booktabs, microtype, pinned TeX Live Docker image, Poppler PDF inspection tools.

## Global Constraints

- Author and PDF metadata must use the pseudonym `8128`.
- Target 10--12 pages; up to 14 pages is acceptable when required for readability.
- Do not modify or replace `publication/base19-radial/paper/main.pdf` during candidate development.
- The headline Lean theorem is `Base19Radial.packedMinimalCoreUnsat` and concerns the exact packed encoding.
- Never describe the packed theorem as kernel-reduction-only.
- State the native certificate-evaluation axiom and the unformalized integer-to-packed bridge explicitly.
- Keep deletion minimality computationally qualified and distinguish it from minimum cardinality.
- Do not claim a base-19 Lychrel number, an OEIS A060382 resolution, uniqueness, an all-base theorem, or an unbounded-process theorem.
- Cite every non-original theorem, algorithm, implementation, and historical claim nearby using primary or authoritative sources.
- Generate quantitative claims from frozen evidence where practical.
- Reuse the existing digest-pinned TeX Live image; add no unpinned TeX dependency.
- Fail builds on missing citations, unresolved references, overfull boxes, or an empty PDF.
- Use grayscale-safe navy/teal accents and do not encode meaning by color alone.

---

## File Structure

### Existing proof-evidence files to stabilize

- `publication/base19-radial/lean/Base19Radial/Generated/CoreBV.lean`: generated packed theorem.
- `publication/base19-radial/scripts/render_lean_bv_core.py`: deterministic packed-theorem renderer.
- `publication/base19-radial/LEAN-BV-CHECK.md`: exact trust-boundary note.
- `publication/base19-radial/artifact-manifest.json`: claim and measured-run registry.
- `publication/base19-radial/SHA256SUMS`: promoted evidence inventory.

### Candidate-preprint files to create

- `publication/base19-radial/preprint-v2/main.tex`: complete article and inline diagrams.
- `publication/base19-radial/preprint-v2/references.bib`: verified bibliography.
- `publication/base19-radial/preprint-v2/citation-matrix.md`: sentence-level source audit.
- `publication/base19-radial/preprint-v2/generated-results.tex`: renderer output; never hand edited.
- `publication/base19-radial/preprint-v2/build.sh`: deterministic fail-closed PDF build.
- `publication/base19-radial/preprint-v2/README.md`: exact regeneration and inspection commands.
- `publication/base19-radial/preprint-v2/SHA256SUMS`: candidate-local source and PDF hashes.
- `publication/base19-radial/preprint-v2/main.pdf`: built candidate for user review.
- `publication/base19-radial/scripts/render_preprint_v2_data.py`: frozen-evidence-to-LaTeX renderer.
- `publication/base19-radial/tests/test_preprint_v2.py`: focused candidate tests.

### Existing files to modify

- `publication/base19-radial/artifact-manifest.json`: add the measured packed-core run if absent.
- `publication/base19-radial/SHA256SUMS`: bind the stabilized proof evidence, not the unaccepted candidate PDF.
- `publication/base19-radial/README.md`: point readers to the candidate without calling it released.

---

### Task 1: Stabilize the Packed-Core Evidence Layer

**Files:**
- Modify: `publication/base19-radial/artifact-manifest.json`
- Modify: `publication/base19-radial/SHA256SUMS`
- Modify: `publication/base19-radial/README.md`
- Verify: `publication/base19-radial/lean/Base19Radial/Generated/CoreBV.lean`
- Verify: `publication/base19-radial/scripts/render_lean_bv_core.py`
- Test: `publication/base19-radial/tests/test_publication_artifact.py`

**Interfaces:**
- Consumes: frozen `instance/equations.json` and theorem output from Lean 4.32.2.
- Produces: `artifact-manifest.json.measured_runs.lean_packed_core_bv`, used by the preprint-data renderer in Task 3.

- [ ] **Step 1: Add a failing assertion for the measured run**

Extend `test_artifact_manifest_maps_claims_and_quantities_to_evidence` with literal expectations:

```python
run = manifest["measured_runs"]["lean_packed_core_bv"]
assert run["wall_seconds"] == 51.01
assert run["max_rss_bytes"] == 1_280_688_128
assert run["lean_version"] == "4.32.2"
assert run["theorem"] == "Base19Radial.packedMinimalCoreUnsat"
assert run["manifest_sha256"] == hashlib.sha256(
    (ARTIFACT / "instance" / "equations.json").read_bytes()
).hexdigest()
assert run["axioms"] == [
    "propext",
    "Classical.choice",
    "Quot.sound",
    "packedMinimalCoreUnsat._native.bv_decide.ax_1_5",
]
```

- [ ] **Step 2: Run the assertion and verify the expected failure**

Run:

```bash
uv run --frozen --extra exact --extra dev pytest \
  publication/base19-radial/tests/test_publication_artifact.py \
  -q -k artifact_manifest_maps
```

Expected: FAIL because `lean_packed_core_bv` is absent or incomplete.

- [ ] **Step 3: Add the exact measured record**

Insert this object under `measured_runs` in `artifact-manifest.json`:

```json
"lean_packed_core_bv": {
  "command": "lake env lean Base19Radial/Generated/CoreBV.lean",
  "lean_version": "4.32.2",
  "theorem": "Base19Radial.packedMinimalCoreUnsat",
  "manifest_sha256": "18ca75da64c84859d2373ae3e61da81e3ac75a68a33af448b57220e23dfbfa9e",
  "wall_seconds": 51.01,
  "max_rss_bytes": 1280688128,
  "axioms": [
    "propext",
    "Classical.choice",
    "Quot.sound",
    "packedMinimalCoreUnsat._native.bv_decide.ax_1_5"
  ]
}
```

Label the time and memory as one development-machine run in surrounding documentation.

- [ ] **Step 4: Regenerate and recheck the packed theorem**

Run:

```bash
uv run --frozen python \
  publication/base19-radial/scripts/render_lean_bv_core.py \
  publication/base19-radial/instance/equations.json \
  /tmp/CoreBV.lean
cmp /tmp/CoreBV.lean \
  publication/base19-radial/lean/Base19Radial/Generated/CoreBV.lean
cd publication/base19-radial/lean
lake env lean Base19Radial/Generated/CoreBV.lean
```

Expected: byte comparison succeeds; Lean reports the exact native axiom listed above.

- [ ] **Step 5: Update hashes and rerun focused tests**

Update only changed promoted entries in `SHA256SUMS`, then run:

```bash
cd publication/base19-radial
shasum -a 256 -c SHA256SUMS
cd ../../..
uv run --frozen --extra exact --extra dev pytest \
  publication/base19-radial/tests/test_publication_artifact.py \
  -q -k 'bv_core_renderer or artifact_manifest_maps or checksum_inventory or readme_states'
```

Expected: all selected tests pass and every checksum reports `OK`.

- [ ] **Step 6: Commit the evidence layer**

```bash
git add publication/base19-radial
git commit -m "proof: add proof-producing base19 core check"
```

---

### Task 2: Verify Primary Sources and Build the Citation Matrix

**Files:**
- Create: `publication/base19-radial/preprint-v2/references.bib`
- Create: `publication/base19-radial/preprint-v2/citation-matrix.md`
- Test: `publication/base19-radial/tests/test_preprint_v2.py`

**Interfaces:**
- Consumes: the existing `paper/references.bib` and `paper/literature-matrix.md` as leads, never as independent verification.
- Produces: stable BibTeX keys and supported-claim rows consumed by `main.tex` in Tasks 5 and 6.

- [ ] **Step 1: Write the failing bibliography-contract test**

Create `test_preprint_v2.py` with:

```python
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ARTIFACT = ROOT / "publication" / "base19-radial"
PREPRINT = ARTIFACT / "preprint-v2"


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
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
uv run --frozen --extra dev pytest \
  publication/base19-radial/tests/test_preprint_v2.py \
  -q -k bibliography
```

Expected: FAIL because the candidate bibliography does not exist.

- [ ] **Step 3: Verify each source against a primary or authoritative page**

Use DOI landing pages, publisher records, official project repositories, the official Z3 guide, the official Lean 4 repository at the frozen toolchain commit, OEIS, and Brown's transcription. Record for every source:

```markdown
| Claim | Status | Primary source | Supporting location | Citation key |
```

The `leanBVDecide432` row must identify Lean commit
`f3b06c705e6c85f5314019d5d3baab0fec5b580c` and the files
`Std/Tactic/BVDecide/Reflect.lean`,
`Std/Tactic/BVDecide/LRAT/Checker.lean`, and
`Lean/Meta/Tactic/BVDecide/Prover/Bitblast.lean`.

- [ ] **Step 4: Create the bibliography with verified metadata**

Copy verified existing entries, correct metadata where primary records differ,
and add:

```bibtex
@misc{leanBVDecide432,
  author       = {{Lean FRO and contributors}},
  title        = {{Lean 4.32.2}: Proof-Producing Bit-Vector Decision Procedure and {LRAT} Checker},
  year         = {2026},
  howpublished = {Lean 4 source tree, commit f3b06c705e6c85f5314019d5d3baab0fec5b580c},
  url          = {https://github.com/leanprover/lean4/tree/f3b06c705e6c85f5314019d5d3baab0fec5b580c/src/lean/Std/Tactic/BVDecide},
  note         = {Accessed 8 August 2026}
}
```

- [ ] **Step 5: Run the bibliography test**

Run the Step 2 command. Expected: PASS.

- [ ] **Step 6: Commit the source audit**

```bash
git add publication/base19-radial/preprint-v2/references.bib \
  publication/base19-radial/preprint-v2/citation-matrix.md \
  publication/base19-radial/tests/test_preprint_v2.py
git commit -m "docs: verify sources for base19 preprint"
```

---

### Task 3: Generate Candidate Quantitative Macros from Frozen Evidence

**Files:**
- Create: `publication/base19-radial/scripts/render_preprint_v2_data.py`
- Create: `publication/base19-radial/preprint-v2/generated-results.tex`
- Modify: `publication/base19-radial/tests/test_preprint_v2.py`

**Interfaces:**
- Consumes: `render(artifact_dir: Path) -> str` inputs from frozen JSON, hashes, and `measured_runs.lean_packed_core_bv`.
- Produces: LaTeX commands `\BaseValue`, `\CoreEquationCount`, `\PackedWidth`, `\PackedSlotWidth`, `\PackedConstraintCount`, `\PackedLeanSeconds`, `\PackedLeanMaxRSS`, `\PackedTheorem`, `\PackedManifestSha`, and existing frontier/deletion macros.

- [ ] **Step 1: Write the failing renderer test**

Add:

```python
def test_generated_results_are_deterministic_and_bound_to_evidence(tmp_path: Path) -> None:
    output = tmp_path / "generated-results.tex"
    subprocess.run(
        (
            sys.executable,
            str(ARTIFACT / "scripts" / "render_preprint_v2_data.py"),
            "--artifact-dir",
            str(ARTIFACT),
            "--output",
            str(output),
        ),
        check=True,
    )
    assert output.read_bytes() == (PREPRINT / "generated-results.tex").read_bytes()
    source = output.read_text(encoding="utf-8")
    assert r"\newcommand{\PackedWidth}{4914}" in source
    assert r"\newcommand{\PackedSlotWidth}{6}" in source
    assert r"\newcommand{\PackedConstraintCount}{1233}" in source
    assert r"\newcommand{\PackedLeanSeconds}{51.01}" in source
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
uv run --frozen --extra dev pytest \
  publication/base19-radial/tests/test_preprint_v2.py \
  -q -k generated_results
```

Expected: FAIL because the renderer does not exist.

- [ ] **Step 3: Implement the renderer with strict input validation**

Implement:

```python
def render(artifact_dir: Path) -> str:
    manifest = load_object(artifact_dir / "artifact-manifest.json")
    equations = load_object(artifact_dir / "instance" / "equations.json")
    core = load_object(artifact_dir / "certificates" / "minimal-core-frontier.json")
    run = manifest["measured_runs"]["lean_packed_core_bv"]
    if equations["base"] != 19 or equations["equation_count"] != 409:
        raise ValueError("equation manifest is not the frozen base-19 instance")
    if core["status"] != "UNSAT" or core["equation_count"] != 408:
        raise ValueError("minimal-core certificate changed")
    if run["manifest_sha256"] != file_sha(artifact_dir / "instance" / "equations.json"):
        raise ValueError("packed Lean run is not bound to the equation manifest")
    values = {
        "BaseValue": 19,
        "CoreEquationCount": 408,
        "PackedWidth": 4914,
        "PackedSlotWidth": 6,
        "PackedConstraintCount": 1233,
        "PackedLeanSeconds": f'{run["wall_seconds"]:.2f}',
        "PackedLeanMaxRSS": "1.28\\,GB",
        "PackedTheorem": r"\texttt{Base19Radial.packedMinimalCoreUnsat}",
        "PackedManifestSha": r"\texttt{" + run["manifest_sha256"] + "}",
    }
    return "% Generated; do not edit.\n" + "\n".join(
        command(name, value) for name, value in values.items()
    ) + "\n"
```

Reuse and validate the existing frontier/deletion quantities rather than importing the old renderer.

- [ ] **Step 4: Render the tracked file and run tests**

Run:

```bash
uv run --frozen python \
  publication/base19-radial/scripts/render_preprint_v2_data.py \
  --artifact-dir publication/base19-radial \
  --output publication/base19-radial/preprint-v2/generated-results.tex
uv run --frozen --extra dev pytest \
  publication/base19-radial/tests/test_preprint_v2.py -q
```

Expected: all candidate tests pass.

- [ ] **Step 5: Commit the data boundary**

```bash
git add publication/base19-radial/scripts/render_preprint_v2_data.py \
  publication/base19-radial/preprint-v2/generated-results.tex \
  publication/base19-radial/tests/test_preprint_v2.py
git commit -m "feat: generate evidence-bound preprint data"
```

---

### Task 4: Build the Textbook-Style LaTeX Skeleton

**Files:**
- Create: `publication/base19-radial/preprint-v2/main.tex`
- Create: `publication/base19-radial/preprint-v2/build.sh`
- Create: `publication/base19-radial/preprint-v2/README.md`
- Modify: `publication/base19-radial/tests/test_preprint_v2.py`

**Interfaces:**
- Consumes: `generated-results.tex` and `references.bib`.
- Produces: a buildable article shell with reusable environments `keyidea`, `trustboundary`, and `nonclaim`.

- [ ] **Step 1: Add a failing source-contract test**

Add:

```python
def test_preprint_source_has_submission_metadata_and_trust_boxes() -> None:
    source = (PREPRINT / "main.tex").read_text(encoding="utf-8")
    assert r"\author{8128}" in source
    assert "A Proof-Producing Base-19 Obstruction" in source
    assert r"\newtcolorbox{keyidea}" in source
    assert r"\newtcolorbox{trustboundary}" in source
    assert r"\newtcolorbox{nonclaim}" in source
    assert r"\hypersetup" in source
    assert "pdfauthor={8128}" in source
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
uv run --frozen --extra dev pytest \
  publication/base19-radial/tests/test_preprint_v2.py \
  -q -k submission_metadata
```

Expected: FAIL because `main.tex` does not exist.

- [ ] **Step 3: Implement the preamble and article shell**

Use `article` at 11pt, `geometry`, `microtype`, `newtxtext`, `newtxmath`,
`amsmath`, `amssymb`, `amsthm`, `booktabs`, `enumitem`, `fancyhdr`, `xcolor`,
`tcolorbox`, `tikz`, `hyperref`, and `cleveref`. Define:

```latex
\definecolor{InkNavy}{HTML}{18324A}
\definecolor{MutedTeal}{HTML}{2F6F73}
\definecolor{WarmPaper}{HTML}{FBFAF6}
\definecolor{BoxTint}{HTML}{EDF4F2}
\pagecolor{WarmPaper}
\color{InkNavy!92!black}
\newtcolorbox{keyidea}{colback=BoxTint,colframe=MutedTeal,title=Key idea}
\newtcolorbox{trustboundary}{colback=InkNavy!4,colframe=InkNavy,title=Trust boundary}
\newtcolorbox{nonclaim}{colback=black!3,colframe=black!55,title=What this does not prove}
```

Add title metadata, table of contents, running headers, theorem environments, section stubs matching the approved specification, and `\bibliographystyle{alpha}`.

- [ ] **Step 4: Implement the fail-closed build script**

Build twice through `latexmk`, then reject warnings:

```bash
latexmk -C main.tex >/dev/null 2>&1 || true
latexmk -pdf -interaction=nonstopmode -halt-on-error -file-line-error main.tex
grep -Eq 'undefined citations|undefined references|Citation.*undefined|Reference.*undefined' main.log && exit 1
grep -F 'Overfull \\hbox' main.log && exit 1
test -s main.pdf
```

Set `SOURCE_DATE_EPOCH=1786147200`, `FORCE_SOURCE_DATE=1`, and `TZ=UTC` exactly as the released build does.

- [ ] **Step 5: Verify packages inside the pinned image and build**

Run:

```bash
docker run --rm --network none --entrypoint bash \
  base19-radial-paper:latest -lc \
  'kpsewhich newtxtext.sty && kpsewhich tcolorbox.sty && kpsewhich tikz.sty'
docker run --rm --network none \
  -v "$PWD/publication/base19-radial/preprint-v2:/paper" \
  base19-radial-paper:latest
```

Expected: every package resolves and a nonempty `main.pdf` is produced.

- [ ] **Step 6: Commit the visual/build shell**

```bash
git add publication/base19-radial/preprint-v2/main.tex \
  publication/base19-radial/preprint-v2/build.sh \
  publication/base19-radial/preprint-v2/README.md \
  publication/base19-radial/tests/test_preprint_v2.py
git commit -m "feat: add textbook-style preprint shell"
```

---

### Task 5: Write the Mathematical Narrative and Radial Diagram

**Files:**
- Modify: `publication/base19-radial/preprint-v2/main.tex`
- Modify: `publication/base19-radial/tests/test_preprint_v2.py`

**Interfaces:**
- Consumes: macros from Task 3 and citation keys from Task 2.
- Produces: self-contained Sections 1--4 and the first TikZ diagram.

- [ ] **Step 1: Add failing reader-visible semantic assertions**

Add a helper that extracts text from the built candidate and check the reader-visible wording. Keep only the TikZ label as a source-structure assertion:

```python
def extracted_pdf_text(tmp_path: Path) -> str:
    output = tmp_path / "preprint.txt"
    subprocess.run(
        ("pdftotext", str(PREPRINT / "main.pdf"), str(output)),
        check=True,
    )
    return output.read_text(encoding="utf-8")


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
```

- [ ] **Step 2: Run the semantic test and verify it fails**

Run the new test alone. Expected: FAIL on the missing narrative phrases.

- [ ] **Step 3: Write Orientation and Frozen System**

Include one hand-computed base-10 example, then define:

```latex
\ell_{p,k}+r_{p,k}+c_{p,k-1}=t_{p,k}+19c_{p,k}.
```

State domains, six phases, block sizes, the growth step, retained bands, the 409-equation candidate, and the removal producing the 408-equation core. Cite Seal/Brown and OEIS only in the motivation paragraph.

- [ ] **Step 4: Write Radial Decomposition and Soundness**

Define `I_i`, `T_i(s)`, and `F_i`; state the closed-empty-frontier theorem and explain that Lean proves the generic implication. Cite bounded-width CSP work only for methodological context.

- [ ] **Step 5: Draw the radial frontier diagram**

Use a compact TikZ flow:

```latex
\node (start) {$F_{-1}=\{()\}$};
\node[right=of start] (l0) {$F_0$};
\node[right=of l0] (mid) {$\cdots$};
\node[right=of mid] (l33) {$F_{33}=\varnothing$};
\draw[->,thick,MutedTeal] (start) -- node[above] {$T_0$} (l0);
\draw[->,thick,MutedTeal] (l0) -- (mid);
\draw[->,thick,MutedTeal] (mid) -- node[above] {$T_{33}$} (l33);
```

Add callouts for at most two live digits, twelve live carries, and 314 reachable states; label the figure `fig:radial-frontier`.

- [ ] **Step 6: Write the Deletion-Minimal Result**

Separate the 409-equation empty frontier, 408-equation core replay, and 409-way deletion audit. Include a `nonclaim` box distinguishing deletion minimality from minimum cardinality.

- [ ] **Step 7: Build, run tests, and commit**

Run the semantic test and pinned PDF build. Commit:

```bash
git add publication/base19-radial/preprint-v2/main.tex \
  publication/base19-radial/tests/test_preprint_v2.py
git commit -m "docs: explain radial base19 obstruction"
```

---

### Task 6: Write the Packed-Encoding Proof and Assurance Ladder

**Files:**
- Modify: `publication/base19-radial/preprint-v2/main.tex`
- Modify: `publication/base19-radial/tests/test_preprint_v2.py`

**Interfaces:**
- Consumes: packed macros and exact axiom list.
- Produces: self-contained Sections 5--7, paper-level equivalence proof, Lean theorem statement, and second TikZ diagram.

- [ ] **Step 1: Add failing reader-visible trust-boundary assertions**

Add:

```python
text = extracted_pdf_text(tmp_path)
for phrase in (
    "packedMinimalCoreUnsat",
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
```

- [ ] **Step 2: Run the trust test and verify it fails**

Expected: FAIL because Sections 5--7 are still stubs.

- [ ] **Step 3: Define the packed model**

Explain the 4,914-bit word, 819 slots, six-bit extraction, 409 digit bounds, 410 carry bounds, six nonzero-leading constraints, 408 equations, and total 1,233 constraints.

- [ ] **Step 4: Prove the no-overflow equivalence on paper**

State and prove:

```latex
0\le \ell,r,t\le18,\qquad c_{\rm in},c_{\rm out}\in\{0,1\}
```

imply both sides of the column equation lie in `[0,37]`. Since `37<64`, equality in `\mathbb Z/64\mathbb Z` is equivalent to ordinary integer equality on those representatives. Explain packing/unpacking slotwise and explicitly label this as a paper proof rather than an existing Lean bridge theorem.

- [ ] **Step 5: State the Lean/LRAT result exactly**

Use a theorem box whose conclusion is the packed UNSAT theorem. Explain that CaDiCaL searches for an LRAT certificate, Lean's proved-sound checker validates the certificate, and native evaluation creates the named additional axiom dependency. Cite Lean source, LRAT, and CaDiCaL immediately.

- [ ] **Step 6: Draw the assurance ladder**

Draw three vertically separated boxes:

```text
Exact Z3 frontier replay
Lean/LRAT with native certificate evaluation  <- achieved
Kernel-reduction-only concrete proof           <- not claimed
```

Use solid outlines for achieved levels and a dashed outline for the unclaimed endpoint. Label `fig:assurance-ladder` and repeat in the caption that height indicates assurance scope, not mathematical generality.

- [ ] **Step 7: Build, run tests, and commit**

Run trust-boundary tests and the pinned build. Commit:

```bash
git add publication/base19-radial/preprint-v2/main.tex \
  publication/base19-radial/tests/test_preprint_v2.py
git commit -m "docs: explain Lean LRAT proof boundary"
```

---

### Task 7: Complete Related Work, Reproducibility, and Citation Audit

**Files:**
- Modify: `publication/base19-radial/preprint-v2/main.tex`
- Modify: `publication/base19-radial/preprint-v2/citation-matrix.md`
- Modify: `publication/base19-radial/preprint-v2/README.md`
- Modify: `publication/base19-radial/tests/test_preprint_v2.py`

**Interfaces:**
- Consumes: all verified citation keys and frozen identifiers.
- Produces: complete manuscript prose with no unsupported non-original claim.

- [ ] **Step 1: Add a failing citation/build audit test**

Add:

```python
def test_every_citation_key_is_defined_and_every_required_key_is_used() -> None:
    tex = (PREPRINT / "main.tex").read_text(encoding="utf-8")
    bib = (PREPRINT / "references.bib").read_text(encoding="utf-8")
    defined = set(re.findall(r"@[A-Za-z]+\{([^,]+),", bib))
    used = {
        key.strip()
        for group in re.findall(r"\\cite\{([^}]+)\}", tex)
        for key in group.split(",")
    }
    assert used <= defined
    assert {
        "brownSeal",
        "oeisA060382",
        "deMouraUllrich2021",
        "CruzFilipeEtAl2017",
        "cadical301",
        "z3Arithmetic",
        "leanBVDecide432",
    } <= used
```

- [ ] **Step 2: Run the audit and verify it fails**

Expected: FAIL because some required sources are not yet cited.

- [ ] **Step 3: Write Related Work and Conclusion**

Cover reverse-and-add context, bounded-width constraint processing, exact solver replay, Lean, LRAT, and CaDiCaL. Do not make a literature-wide priority claim. End with the bounded theorem and trust qualification, not the motivating conjecture.

- [ ] **Step 4: Write Reproducibility and Appendix**

Include exact theorem names, manifest SHA, certificate SHA values, Lean version, development-machine run qualification, generation command, Lean command, and pinned PDF build command. Do not print the entire LRAT certificate or 4,914-bit encoding.

- [ ] **Step 5: Complete the claim-level citation matrix**

For every historical or methodological paragraph, add a row giving the exact source location. Mark artifact results as `artifact evidence` with paths rather than external citations.

- [ ] **Step 6: Run the citation audit and clean build**

Run all candidate tests and the pinned build. Inspect `main.log` explicitly for undefined citations/references and overfull boxes.

- [ ] **Step 7: Commit the complete prose**

```bash
git add publication/base19-radial/preprint-v2 \
  publication/base19-radial/tests/test_preprint_v2.py
git commit -m "docs: complete cited base19 preprint"
```

---

### Task 8: Validate and Package the Candidate PDF

**Files:**
- Create: `publication/base19-radial/preprint-v2/main.pdf`
- Create: `publication/base19-radial/preprint-v2/SHA256SUMS`
- Modify: `publication/base19-radial/preprint-v2/README.md`
- Modify: `publication/base19-radial/tests/test_preprint_v2.py`
- Modify: `publication/base19-radial/README.md`

**Interfaces:**
- Consumes: complete candidate source and pinned build.
- Produces: user-reviewable PDF plus mechanical and visual validation evidence.

- [ ] **Step 1: Add failing PDF acceptance tests**

Add tests that run after the PDF exists:

```python
def test_candidate_pdf_and_local_checksums_are_current() -> None:
    pdf = PREPRINT / "main.pdf"
    assert pdf.stat().st_size > 100_000
    entries = dict(
        line.split("  ", 1)
        for line in (PREPRINT / "SHA256SUMS").read_text().splitlines()
    )
    for relative, expected in entries.items():
        assert hashlib.sha256((PREPRINT / relative).read_bytes()).hexdigest() == expected
```

- [ ] **Step 2: Run the test and verify it fails**

Expected: FAIL because candidate checksums are absent or stale.

- [ ] **Step 3: Build from a clean candidate directory**

Run the data renderer, remove only LaTeX-generated candidate outputs through `latexmk -C`, then build in the pinned container with network disabled. Confirm `paper/main.pdf` is unchanged by comparing its pre-build and post-build SHA-256.

- [ ] **Step 4: Run mechanical PDF inspection**

Run:

```bash
pdfinfo publication/base19-radial/preprint-v2/main.pdf
pdffonts publication/base19-radial/preprint-v2/main.pdf
pdftotext publication/base19-radial/preprint-v2/main.pdf /tmp/base19-preprint-v2.txt
```

Require author `8128`, the exact title, 10--14 pages, embedded fonts, and extracted occurrences of `packedMinimalCoreUnsat`, `not kernel-reduction-only`, and `phase=0,n=0,column=82`.

- [ ] **Step 5: Render and inspect every page visually**

Run:

```bash
mkdir -p /tmp/base19-preprint-v2-pages
pdftoppm -png -r 130 \
  publication/base19-radial/preprint-v2/main.pdf \
  /tmp/base19-preprint-v2-pages/page
```

Inspect every PNG for clipping, bad page breaks, illegible diagrams, orphan headings, sparse final pages, inconsistent boxes, and grayscale readability. Make only source-level layout corrections, rebuild, and repeat the mechanical checks after any correction.

- [ ] **Step 6: Generate candidate-local checksums**

Hash exactly:

```text
main.tex
references.bib
citation-matrix.md
generated-results.tex
build.sh
README.md
main.pdf
```

Write canonical `SHA256SUMS` entries in that order.

- [ ] **Step 7: Run final candidate and existing-artifact checks**

Run:

```bash
uv run --frozen --extra dev pytest \
  publication/base19-radial/tests/test_preprint_v2.py -q
uv run --frozen --extra exact --extra dev pytest \
  publication/base19-radial/tests/test_publication_artifact.py \
  -q -k 'bv_core_renderer or artifact_manifest_maps or checksum_inventory or preprint_manifest_binds'
cd publication/base19-radial/lean
lake build
```

Expected: all tests pass and Lean replays the disclosed axiom sets.

- [ ] **Step 8: Commit the review candidate without promoting it**

```bash
git add publication/base19-radial/preprint-v2 \
  publication/base19-radial/tests/test_preprint_v2.py \
  publication/base19-radial/README.md
git commit -m "docs: build textbook-style base19 preprint candidate"
```

Do not replace `paper/main.pdf`, alter the released preprint identity, or call the candidate released. Present `preprint-v2/main.pdf` to the user for explicit acceptance.

---

## Final Verification Checklist

- [ ] The released `paper/main.pdf` SHA-256 is unchanged.
- [ ] Candidate author and PDF metadata are `8128`.
- [ ] Candidate length is 10--14 pages.
- [ ] All fonts are embedded.
- [ ] No missing citation, missing reference, or overfull-box warning remains.
- [ ] Every non-original claim has a nearby verified citation.
- [ ] The packed theorem is stated only for the exact six-bit encoding.
- [ ] The paper proves the `37<64` no-overflow bridge and labels it as unformalized in Lean.
- [ ] The native certificate-evaluation axiom is printed exactly.
- [ ] Deletion minimality remains computationally qualified.
- [ ] Both TikZ diagrams are legible and grayscale safe.
- [ ] Generated macros reproduce byte-for-byte.
- [ ] Candidate-local checksums pass.
- [ ] Focused existing-artifact tests pass.
- [ ] Lean build succeeds with the expected axiom reports.
- [ ] Every candidate PDF page has been visually inspected.
