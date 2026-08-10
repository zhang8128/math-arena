# T28 base-19 tail quotient: primary layer-31 gate

Status: **STOP**
Claim boundary: base 19, layer 31 to 32, frozen radial obstruction.

## Verified terminal seed

- Classes: T_HIGH_DIGIT, T_PHASE_ZERO, T_RESIDUE
- Decision nodes: 32
- Exact terminal obligations: 3

## Attempted layer 31

The four-class partition below is a reachable-state hypothesis, not a theorem.

- `DEAD` (dead), members=12, edges=none
- `Q00` (live), members=2, edges=T_HIGH_DIGIT
- `Q01` (live), members=1, edges=T_PHASE_ZERO
- `Q02` (live), members=3, edges=T_RESIDUE

No candidate decision DAG is serialized because the synthesis gate stopped.

## Outcome

STOP at layer 31: `decision_depth_exceeded`.

Rejected class: `DEAD`
Failed obligation: `dead_has_no_successor`
Exact counterexample: `{"D0": 18, "D1": 6, "L0": 0, "L1": 1, "L2": 1, "L3": 0, "L4": 0, "L5": 0, "R0": 0, "R1": 0, "R2": 1, "R3": 0, "R4": 0, "R5": 1}`

## Limitations

- A STOP is not an impossibility theorem for human-readable invariants.
- No lower layer, other base, or other topology is classified.
- No Lean theorem is claimed or required by this gate.
- Prism produced no usable frame artifact and supplied no premise.
- The attempted layer-31 partition is a repository-derived hypothesis, not a theorem.
