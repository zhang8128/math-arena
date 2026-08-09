# Base-19 radial preprint release checklist

Acceptance was performed on 2026-08-08 (UTC) from preprint commit
`34d06b006ba4879d5aa1a9c0d58f021c2bbd253a`.  The release record changes only
metadata and this checklist; it does not change the frozen equations,
certificates, witnesses, Lean definitions, or manuscript.

## Required gates

| Gate | Status | Fresh result |
| --- | --- | --- |
| Full exploratory/publication pytest matrix | PASS | 62 passed in 594.43 s; exit 0; maximum RSS 738,361,344 bytes |
| reproduce.sh quick | PASS | completed in 244.95 s; exit 0; maximum RSS 7,542,259,712 bytes |
| Forbidden-proof source scan | PASS | no `sorry`, `native_decide`, line-leading `unsafe`, or line-leading `axiom` match |
| Offline PDF rebuild | PASS | digest-pinned TeX Live image; `--network none`; five pages; final log has no undefined reference, missing citation, or overfull box |
| Deterministic PDF rebuild | PASS | two clean offline builds compared byte-for-byte |
| No-hardlinks clean-clone reproduction | PASS | commit `34d06b0`; 246.82 s; exit 0; maximum RSS 7,492,141,056 bytes |
| Checksum inventory | PASS | every entry in `SHA256SUMS` verified after the final PDF build |
| Claim-to-evidence audit | PASS | abstract, theorem, proposition, table, related work, and limitations checked against `artifact-manifest.json` |

The exact mandatory test command was:

```sh
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_interface_cores.py \
  publication/base19-radial/tests/test_publication_artifact.py -q
```

The independent reproduction command was:

```sh
./publication/base19-radial/reproduce.sh quick
```

The proof-source gate was:

```sh
if rg -n 'sorry|native_decide|^unsafe|^axiom' \
  publication/base19-radial/lean/Base19Radial; then exit 1; fi
```

The paper was rebuilt with:

```sh
docker build --platform linux/amd64 \
  -f publication/base19-radial/Dockerfile.paper \
  -t base19-radial-paper publication/base19-radial
docker run --rm --platform linux/amd64 --network none \
  -v "$PWD/publication/base19-radial/paper:/paper" \
  base19-radial-paper
```

## Frozen identities

- Candidate frontier:
  `1ce1b3c59bd95264e5338f7fba5bdffa15fb7635917964980057615395cf138c`.
- Deletion-minimal core frontier:
  `7635e7188197021cfc15cbad6d087f6fdbfa7a8bbfe4e4ed9b91a15a89498c67`.
- Complete deletion audit:
  `0566f6e2025aec28fe0d2f824f1f6b343cf912e9191a9036629a2a1d4ef03325`.
- Preprint PDF:
  `e56dd14235a72821d407d106c259902c267be6f7ed5a2abaa5ccffeac61ac47e`.
- TeX Live image:
  `ghcr.io/xu-cheng/texlive-full@sha256:1a2027fd03aa64455cf36c927c1dfccffc8fc8a3cb11012333be815f8b33e956`.

## Assurance boundary audit

- `Base19Radial.unsat_of_closed_empty_frontier` is the Lean-kernel-checked
  generic theorem.
- `Base19Radial.radialTinyProblemUnsat` is a kernel-checked tiny application;
  `#print axioms` reports `[propext]`.
- `Base19Radial.deleteP0C0Sat` is the kernel-checked concrete SAT neighbor;
  `#print axioms` reports `[propext]`.
- The concrete 409-equation candidate UNSAT and 408-equation core UNSAT are
  exact computational replays and are not Lean kernel-checked.
- The 408-equation core is deletion-minimal relative to the frozen candidate;
  this is not a minimum-cardinality statement.
- No all-base or general Lychrel theorem is claimed.
- Literature-wide novelty is not established.

## Optional and deliberately omitted gates

- SAT/DRAT/FRAT/LRAT cross-check: **NOT REQUIRED — not part of the trusted proof**.
  No proof-producing Boolean translation is promoted.
- Concrete Lean UNSAT theorem: **NOT ACHIEVED** within the published resource
  gate.  The failure and measured attempts are retained in
  `LEAN-FEASIBILITY.md`; the manuscript does not imply otherwise.
- `reproduce.sh full`: **NOT RE-RUN FOR RELEASE**.  It is an overnight
  regeneration path.  The promoted complete audit is checksum-bound, all 409
  records are replayed by `quick`, and both frontiers were reconstructed in
  the fresh release run.

## Clean-checkout gate

Preprint commit `34d06b0` was cloned with `git clone --no-hardlinks` into a
fresh temporary directory.  `reproduce.sh quick` passed there in 246.82
seconds with maximum RSS 7,492,141,056 bytes.  The clone regenerated its own
virtual environment and had no access to the source worktree's untracked
files.
