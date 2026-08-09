# Base-19 radial obstruction artifact

This directory freezes one bounded reverse-and-add digit/carry constraint
system and the evidence currently justified for it.

The strongest concrete result is a 408-equation deletion-minimal UNSAT core
inside the fixed 409-equation candidate.  Exact frontier enumeration proves
the core UNSAT, and 408 explicit assignments prove that deleting any remaining
equation makes it SAT. Both concrete UNSAT results are independently replayed
from the frozen equation JSON. A generated Lean theorem now also checks an
exact finite encoding of the 408-equation core with a proof-producing LRAT
path, but it uses `bv_decide`'s native certificate-evaluation axiom and is
therefore **not a kernel-reduction-only proof**.
The bridge from the frozen `Problem.Satisfies` equations to that packed
proposition is **generated and audited computationally, not formalized in
Lean**.
This is not a minimum-cardinality claim.

Lean 4.32.2 checks the generic radial soundness theorem
`Base19Radial.unsat_of_closed_empty_frontier`, a tiny worked UNSAT instance,
and the concrete satisfying-neighbor theorem `Base19Radial.deleteP0C0Sat`.
The last theorem uses ordinary `decide`. The additional theorem
`Base19Radial.packedMinimalCoreUnsat` uses `bv_decide`; its larger trust base
and exact axiom report are recorded in `LEAN-BV-CHECK.md`. No artifact source
uses `sorry`, `unsafe`, or `native_decide`.

## Reproduce

From the repository root:

```sh
./publication/base19-radial/reproduce.sh quick
```

`quick` verifies all promoted hashes, regenerates the equation and Lean data,
independently replays both empty frontiers, replays every promoted SAT witness,
runs the publication tests, cleans and rebuilds Lean, compares Lean's exported
statement to the independent Python statement, and prints the theorem axioms.
It needs Python 3.13.5, Z3 5.0.0, Lean 4.32.2, Lake 5.0.0, and `uv` 0.8.3.
The Lean witness check peaked near 7.51 GB on the development machine.

For a complete regeneration, including the 409-way deletion audit:

```sh
./publication/base19-radial/reproduce.sh full
```

`full` first runs `quick`, then regenerates the deletion audit and all three
solver certificates in a temporary directory and byte-compares them with the
promoted files.  The completed six-worker audit took about 9 hours when
resumed from 33 already validated records; a fresh run should be budgeted as
an overnight computation.  `BASE19_WORKERS` may reduce the worker count, but
changing it does not change canonical output order.

## Evidence map

- `instance/` contains the frozen topology and canonical 409-equation JSON.
- `certificates/frontier.json` is the 409-equation empty frontier.
- `certificates/minimal-core-frontier.json` is the independently replayed
  408-equation empty frontier after removing phase 0, column 82.
- `certificates/deletions.jsonl` contains all 409 deletion outcomes; 408 lines
  carry complete SAT assignments and exact arithmetic replay metadata.
- `lean/` contains the transparent model, generic soundness theorem, generated
  statement data, kernel-checked phase-0-column-0 SAT witness, and the
  proof-producing packed-core check with its explicit native-evaluation
  boundary.
- `artifact-manifest.json` maps every promoted claim and quantitative value to
  JSON or a Lean theorem. `SHA256SUMS` binds the promoted evidence.

The scope and failed concrete-Lean feasibility experiments are recorded in
`LEAN-FEASIBILITY.md`; the successful bounded bit-vector check and its trust
boundary are recorded in `LEAN-BV-CHECK.md`.

## Preprint

The released conservative manuscript remains `paper/main.tex`; its tracked
PDF is `paper/main.pdf`, built from a digest-pinned TeX Live image using
`Dockerfile.paper`.  Quantitative claims in that manuscript are generated from
promoted evidence into `paper/generated-results.tex`, and `reproduce.sh quick`
rejects any drift.

An unreleased textbook-style review candidate is available separately at
`preprint-v2/main.pdf`, with sources and candidate-local checksums in
`preprint-v2/`.  It is provided for explicit review and does not replace or
rename the released paper.

After the pinned image is available locally, build without network access:

```sh
docker build -f publication/base19-radial/Dockerfile.paper \
  -t base19-radial-paper publication/base19-radial
docker run --rm --network none \
  -v "$PWD/publication/base19-radial/paper:/paper" \
  base19-radial-paper
```

The released paper deliberately labels the concrete UNSAT results as exact
computational replays rather than kernel-reduction-only Lean theorems. The new
bit-vector theorem does not silently change that published assurance label.
No DOI or repository URL is claimed before an external deposit exists.

`RELEASE_CHECKLIST.md` records the fresh publication gates, measured resource
use, immutable certificate and PDF identities, clean-clone result, and every
deliberately omitted optional assurance layer.
