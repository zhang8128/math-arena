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
