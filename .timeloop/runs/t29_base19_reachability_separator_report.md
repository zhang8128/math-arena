# T29 base-19 reachability separator

Status: **FINITE_SEPARATOR_PASS_SEMANTIC_STOP**

## Claim boundary

This result concerns only the frozen base-19 radial obstruction and its exact layer-31 to layer-32 relation.

## Finite separator

The serialized predicate is a finite-only separator.
It covers 12 promoted dead states and rejects 221 trace negatives plus 6 live controls.
Candidate atom pool: 83.

```json
{"clauses": [{"atoms": [{"constant": -1, "relation": "le", "terms": [["L1", -1], ["L3", -1]]}, {"constant": -1, "relation": "le", "terms": [["L2", -1], ["L3", -1]]}, {"constant": -4, "relation": "le", "terms": [["D1", -1], ["R2", 2]]}, {"constant": -6, "relation": "le", "terms": [["D0", -1], ["L4", -1]]}, {"constant": 0, "relation": "eq", "terms": [["L0", 1], ["L3", -1]]}, {"constant": 0, "relation": "le", "terms": [["R0", -1], ["R1", 1]]}, {"constant": 1, "relation": "le", "terms": [["R0", 1], ["R3", 1]]}, {"constant": 15, "relation": "le", "terms": [["D1", 1], ["R2", -3]]}, {"constant": 2, "relation": "le", "terms": [["D0", 1], ["D1", -1], ["R2", 1]]}, {"constant": 2, "relation": "le", "terms": [["L5", 1], ["R0", 1], ["R5", 1]]}]}], "layer": 31, "variables": ["D0", "D1", "L0", "L1", "L2", "L3", "L4", "L5", "R0", "R1", "R2", "R3", "R4", "R5"]}
```

## Semantic check

An exact semantic successor exists, so the finite predicate is not a universal dead region.

```json
{"input_state": {"input:D0": 5, "input:D1": 6, "input:L0": 0, "input:L1": 1, "input:L2": 1, "input:L3": 0, "input:L4": 1, "input:L5": 1, "input:R0": 0, "input:R1": 0, "input:R2": 1, "input:R3": 0, "input:R4": 0, "input:R5": 1}, "local_state": {"local:digit:p0:f1:d6": 4, "local:digit:p1:f1:d21": 4, "local:digit:p2:f1:d21": 11, "local:digit:p2:f1:d3": 10, "local:digit:p3:f1:d21": 3, "local:digit:p3:f1:d3": 2, "local:digit:p4:f1:d21": 5, "local:digit:p4:f1:d3": 6, "local:digit:p5:f1:d21": 12, "local:digit:p5:f1:d3": 11}, "output_state": {"output:D0": 0, "output:D1": 4, "output:L0": 0, "output:L1": 0, "output:L2": 1, "output:L3": 0, "output:L4": 0, "output:L5": 1, "output:R0": 0, "output:R1": 0, "output:R2": 0, "output:R3": 1, "output:R4": 0, "output:R5": 0}}
```

## Limitations

- Finite separation is not a reachability or inductive-invariant theorem.
- Semantic SAT prevents promotion to a universal dead-region theorem.
- No other base, topology family, lower layer, Lean bridge, or publication was changed.
