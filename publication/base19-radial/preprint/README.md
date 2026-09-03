# Base-19 textbook-style preprint review candidate

This directory contains the unreleased review candidate.  It consumes the
tracked `generated-results.tex` evidence macros and `references.bib`; it does
not replace `../paper/main.pdf`, the released paper sources, or the released
paper's identity.

The candidate reports the exact packed theorem
`Base19Radial.packedMinimalCoreUnsat` under Lean 4.32.2.  Its frozen equation
manifest is SHA-256
`18ca75da64c84859d2373ae3e61da81e3ac75a68a33af448b57220e23dfbfa9e`.
The theorem uses the native certificate-evaluation axiom recorded in
`../LEAN-BV-CHECK.md`; the integer-to-packed bridge is generated and audited
but not formalized in Lean.

## Regenerate evidence-bound sources

From the repository root:

```sh
uv run --frozen python \
  publication/base19-radial/scripts/render_preprint_v2_data.py \
  --artifact-dir publication/base19-radial \
  --output publication/base19-radial/preprint-v2/generated-results.tex

uv run --frozen python \
  publication/base19-radial/scripts/render_lean_bv_core.py \
  publication/base19-radial/instance/equations.json \
  publication/base19-radial/lean/Base19Radial/Generated/CoreBV.lean

(cd publication/base19-radial/lean &&
  lake env cadical --version &&
  lake env lean Base19Radial/Generated/CoreBV.lean)
```

The CaDiCaL command prints `2.1.2`; this pinned-toolchain output identifies the
binary used by Lean's default `bv_decide` route.  The official `rel-2.1.2`
release is cited in the manuscript, but the release page alone does not prove
which bundled binary ran.  The final command checks the packed theorem and
prints its exact axiom report.  The subshell returns the caller to the
repository root for the commands below.
The 51.01-second, 1,280,688,128-byte maximum-RSS record is one development-
machine run, not a performance guarantee.  The broader artifact replay is
documented in `../README.md`.

## Build the PDF

After the digest-pinned TeX base image is available in the local Docker cache,
build the image and then the candidate without network access.  Run the Docker commands from the repository root:

```sh
docker build --platform linux/amd64 --network none \
  -f publication/base19-radial/Dockerfile.paper \
  -t base19-radial-paper publication/base19-radial
docker run --rm --platform linux/amd64 --network none \
  -v "$PWD/publication/base19-radial/preprint-v2:/paper" \
  base19-radial-paper
```

The container runs `build.sh`.  The script sets `SOURCE_DATE_EPOCH=1786147200`,
`FORCE_SOURCE_DATE=1`, and `TZ=UTC`; it fails on unresolved citations or
references, overfull boxes, or an empty `main.pdf`.

To check the required visual packages in the pinned image before building:

```sh
docker run --rm --platform linux/amd64 --network none --entrypoint bash \
  base19-radial-paper:latest -c \
  'kpsewhich newtxtext.sty && kpsewhich tcolorbox.sty && kpsewhich tikz.sty'
```

Inspect the result from the repository root with:

```sh
pdfinfo publication/base19-radial/preprint-v2/main.pdf
pdffonts publication/base19-radial/preprint-v2/main.pdf
pdftotext publication/base19-radial/preprint-v2/main.pdf -
```

Verify the candidate-local source and PDF inventory with:

```sh
(cd publication/base19-radial/preprint-v2 && shasum -a 256 -c SHA256SUMS)
```

`SHA256SUMS` is local to this review candidate.  It is not part of the
authoritative promoted-evidence inventory in `../SHA256SUMS`.

`citation-matrix.md` maps every external methodological or historical claim
to a verified source and maps artifact-specific results to frozen repository
paths.  `../SHA256SUMS` is the authoritative promoted-evidence inventory.

The PDF is an unreleased candidate for review only.  Do not promote it over
the released paper without explicit acceptance.
