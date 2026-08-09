# Base-19 textbook-style preprint candidate

This directory contains the unreleased candidate preprint.  It consumes the
tracked `generated-results.tex` evidence macros and `references.bib`; it does
not replace `../paper/main.pdf` or the released paper sources.

## Rebuild

After the digest-pinned TeX base image is available in the local Docker cache,
build the image and then the candidate without network access:

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

The PDF is a candidate for review only.  Do not promote it over the released
paper without explicit acceptance.
