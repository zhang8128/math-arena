# Lean feasibility boundary

This artifact does **not** claim a kernel-checked proof that the concrete
409-equation base-19 instance is unsatisfiable.

The generic radial soundness theorem is checked by Lean as
`Base19Radial.unsat_of_closed_empty_frontier`, and
`Base19Radial.radialTinyProblemUnsat` exercises that theorem on a hand-written
two-layer contradiction.  The concrete frontier JSON is instead an exact
computational certificate produced and replayed by the fail-closed Python/Z3
pipeline.

## Approved gate

The concrete Lean route had to check the overflow layer, the largest-frontier
layer, and the terminal layer in at most 10 minutes wall time and below 8 GiB
peak resident memory on the development machine.  Generated proofs could use
ordinary `omega`, but not `sorry`, `axiom`, `unsafe`, or `native_decide`.

## Result

The gate failed.

| Attempt | Outcome |
| --- | --- |
| One direct `omega` closure lemma per incoming state | Exceeded 10 minutes. |
| Coordinate-trie frontier with 277 per-state arithmetic lemmas | Terminated after 680.41 seconds with exit 137; observed peak RSS was 87,985,389,568 bytes. |
| One universal transition over the global input trie | Did not finish within the gate. |
| Sixteen-state shared arithmetic groups | Hit Lean's deterministic heartbeat limit. |
| Eight-state shared arithmetic groups | Hit the 200,000-heartbeat default on multiple groups. |
| Eight-state groups with the project's intended 2,000,000-heartbeat allowance | Stopped after the Lean child reached 22,224,560 KiB RSS at 35 seconds, already above the 8 GiB gate. |

The last memory value was read directly from `ps` for the Lean child.  On this
macOS setup, `/usr/bin/time -l` attached to `lake env lean` reported the small
Lake wrapper's resident set rather than the child Lean process, so its RSS
field is not used for that run.

## Consequence

The experimental renderer remains available only behind
`--experimental-frontier-proofs`; normal artifact generation does not emit or
compile those proofs.  No theorem named `candidateUnsat` is exposed.  Any
paper-facing statement must describe the concrete UNSAT result as exactly
computed and independently replayed, not kernel checked.

## Computationally certified deletion-minimal core

The complete 409-way deletion audit identifies exactly one equation whose
removal leaves an UNSAT system:
`phase=0,n=0,column=82`.  The resulting 408-equation set is deletion-minimal
UNSAT in the computational certificate model:

1. `minimal-core-frontier.json` has an empty terminal frontier after 35
   layers for those 408 equations.  The standalone `verify_frontier.py`
   checker imports no exploratory T26 module; it reads the frozen equation
   manifest, rebuilds every layer independently in finite QF_LIA, enumerates
   every output projection, and compares every transition exactly.  The
   promoted file has SHA-256
   `7635e7188197021cfc15cbad6d087f6fdbfa7a8bbfe4e4ed9b91a15a89498c67`.
2. For each equation `f` in that 408-equation set, the deletion-audit witness
   for the stronger system obtained from the original candidate by deleting
   only `f` replays all 408 remaining equations exactly.  The same assignment
   therefore satisfies the weaker system obtained by deleting both `f` and
   `phase=0,n=0,column=82`.  The 409-record audit has SHA-256
   `0566f6e2025aec28fe0d2f824f1f6b343cf912e9191a9036629a2a1d4ef03325`.

On the development machine, full three-certificate regeneration took 172.90
seconds and 621,477,888 bytes peak RSS.  Independent replay of the minimal
core took 34.53 seconds and 72,138,752 bytes peak RSS.  These are exact
computational checks, not Lean kernel checks, not proof-producing SMT traces,
and not a minimum-cardinality-core claim.  “Unique” refers only to the single
408-equation subset of this fixed 409-equation candidate that remained UNSAT
under the complete one-deletion audit.

## Kernel-checked deletion witness

The neighboring instance obtained by deleting
`phase=0,n=0,column=0` is separately kernel checked. The generated theorem
`Base19Radial.deleteP0C0Sat` uses an inline 819-value assignment in fixed
variable-ID order and ordinary `by decide`; it does not use `native_decide`.
A clean sequential module build checked the theorem in 37.60 seconds with
7,507,558,400 bytes peak RSS. `#print axioms` reports only `propext`.

## Proof-producing bit-vector endpoint

A later bounded experiment found a practical intermediate endpoint. The
renderer `scripts/render_lean_bv_core.py` converts the exact 408-equation core
to 819 six-bit slots and 1,233 constraints. The generated theorem
`Base19Radial.packedMinimalCoreUnsat` was accepted by Lean 4.32.2 in 51.0
seconds with about 1.28 GB maximum RSS.

The encoding is exact at the mathematical level: digit slots are below 19,
carry slots are below 2, the six leading digits are nonzero, and bounded
column sums are at most 37, below the six-bit modulus 64. The source records
the SHA-256 of the frozen equation manifest and is regenerated and compared
byte-for-byte by the artifact test.

This route uses `bv_decide`, which asks CaDiCaL for an LRAT certificate and
passes that certificate through Lean's proved-sound LRAT checker. It is not a
strict kernel-reduction-only result because Lean evaluates the checker through
native code. The exact axiom report is
`[propext, Classical.choice, Quot.sound,
packedMinimalCoreUnsat._native.bv_decide.ax_1_5]`. See
`LEAN-BV-CHECK.md` for the command and trust boundary. The original failed
`omega` gate and the conservative paper claim therefore remain unchanged.
