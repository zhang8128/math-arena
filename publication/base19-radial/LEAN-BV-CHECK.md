# Concrete bit-vector Lean check

`Base19Radial.packedMinimalCoreUnsat` is a proof-producing Lean check of an
exact six-bit encoding of the frozen 408-equation minimal core.

The renderer reads `instance/equations.json`, validates its content digest,
removes exactly `phase=0,n=0,column=82`, and rejects any change to the expected
409 digit variables, 410 carry variables, 408 retained equations, or 1,233
finite constraints. It emits one 4,914-bit packed assignment: each six-bit
slot is constrained to be a digit below 19 or a carry below 2, the six leading
digits are nonzero, and all retained column equations are asserted. Under
these bounds every side of a column equation is at most 37, so six-bit
addition does not wrap; the finite equations therefore have their ordinary
integer meaning.

The bridge from the frozen `Problem.Satisfies` equations to this packed
bit-vector proposition is **generated and audited computationally, not
formalized in Lean**. `CoreBV.lean` contains the resulting numeric constraints
and manifest-digest metadata, but no Lean theorem proves that correspondence.
The generated theorem consequently proves unsatisfiability of the emitted
packed proposition, conditional on that external bridge.

Lean 4.32.2 checks the generated theorem with `bv_decide`. One
development-machine run took 51.01 seconds and reached 1,280,688,128 bytes
maximum RSS; those exact measurements are recorded as `lean_packed_core_bv` in
`artifact-manifest.json`. CaDiCaL searches for an LRAT certificate, and Lean's
proved-sound LRAT checker checks it.

This is a substantial assurance upgrade over accepting Z3's `unsat` result,
but it is not the paper's strict kernel-only endpoint. `#print axioms` reports:

```text
[propext, Classical.choice, Quot.sound,
 packedMinimalCoreUnsat._native.bv_decide.ax_1_5]
```

The last item records that Lean evaluated the LRAT checker through native
code. Consequently the trusted base includes Lean's compiler/code generator
and runtime for that evaluation. The theorem does not justify replacing the
paper's existing statement that the concrete frontier closure is not checked
by kernel reduction alone.

Reproduce the generated source and check it directly:

```sh
uv run --frozen python \
  publication/base19-radial/scripts/render_lean_bv_core.py \
  publication/base19-radial/instance/equations.json \
  publication/base19-radial/lean/Base19Radial/Generated/CoreBV.lean

cd publication/base19-radial/lean
lake env lean Base19Radial/Generated/CoreBV.lean
```
