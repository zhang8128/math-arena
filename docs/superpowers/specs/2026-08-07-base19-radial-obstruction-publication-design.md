# Base-19 Radial Obstruction — Publication-Grade Certification Design

## Purpose

Turn the measured T26 base-19 radial obstruction into a conservative,
reproducible preprint and a machine-checked supplementary artifact.  The
primary result is a finite theorem about one explicitly defined system of
bounded integer equations.  It is not a theorem about the general behavior of
Lychrel numbers, all reverse-and-add topologies, or all bases.

The preferred trust endpoint is a Lean 4 theorem checked by ordinary kernel
reduction or explicit proof terms.  A secondary SAT proof may strengthen the
artifact if it remains independently reproducible and reasonably sized, but
publication readiness does not depend on that optional layer.

## Claim boundary

Let `C` be the fixed 409-equation system obtained from the recorded six-phase
base-19 topology after removing phase-five column 82 from the 410-column
failed-assumption seed.  Every digit ranges over `0..18`; carries and boundary
conditions have their recorded exact domains; and every equation has the
standard column form

`left + right + carry_in = target + 19 * carry_out`.

The required primary theorem is:

> The bounded integer system `C` has no satisfying assignment.

The required complementary theorem is:

> The system obtained from `C` by additionally deleting phase-zero column 0
> has the published complete satisfying assignment.

Deletion-minimal unsatisfiability may be added only if every one of the 409
single-equation deletions has an explicit satisfying witness and every witness
passes the formal checker.  A sampled deletion audit, solver statuses, or a
single reconstructed path is insufficient for that claim.

The paper must not infer a broader Lychrel theorem from these finite results.
Broader symbolic patterns may be reported only as conjectures unless they
receive their own proof and independent validation.

## Immutable mathematical statement

The fixed topology, base, digit and carry domains, boundary conditions, column
construction, and removed equation are part of the mathematical statement.
The Lean development defines these objects directly and constructs `C` from
them.  The final theorem is about that Lean object rather than an opaque solver
file or an unverified imported Boolean formula.

A separately implemented Python builder serializes the same equations into a
canonical manifest.  The Lean development exports its canonical rendering,
and the reproduction workflow requires the two renderings and digests to
agree.  This comparison does not prove the theorem, but it detects statement
translation drift between discovery code and the formal statement.

The canonical manifest records, in stable order:

- phase and column provenance;
- all variable identities and domains;
- coefficients, constants, and boundary conditions;
- the base and topology identifier;
- the selected and removed equations; and
- a format version and cryptographic digest.

Any manifest mismatch is a fail-closed artifact error.

## Lean proof architecture

The Lean development separates generic mathematics from the concrete
instance.

### Formal model

Define finite digit and carry types, column equations, assignments, and exact
equation satisfaction.  Define the fixed topology and its 409 selected
equations using small auditable functions.  Prove or compute the basic
well-formedness facts: variable domains are finite, every referenced variable
exists, radial layers partition the selected equations, and each cut exposes
only its declared interface variables.

### Generic radial certificate

Formalize a layered finite constraint system with interface states.  For a
frontier sequence `F_0, ..., F_n`, the generic soundness theorem establishes
unsatisfiability from three checked conditions:

1. every permitted initial interface state belongs to `F_0`;
2. every locally satisfying extension of every state in `F_i` projects to a
   state in `F_(i+1)`; and
3. the terminal frontier is empty.

The frontiers may be exact reachable sets or conservative over-approximations.
Soundness relies only on transition closure and terminal emptiness.  Lean
recomputes the required finite local transition checks; it does not trust a
Python claim that all successors were enumerated.

The concrete certificate contains the radial layer descriptions and the
frontier state sets.  Current measurements predict 34 layers, at most 12 live
carry bits and two live base-19 digits per cut, a peak of 314 reachable states,
and emptiness at layer 33.  These are expectations to be re-established by the
formal checker, not constants accepted as evidence.

### Satisfying witnesses

Define a generic witness checker that evaluates variable bounds, boundary
conditions, and every retained equation.  The known 408-equation witness is
embedded or imported as transparent data and produces a theorem that the
neighboring system is satisfiable.

If the full deletion audit succeeds, index a witness by every equation of `C`
and formally check the corresponding deletion.  The minimality theorem then
follows by finite enumeration.  A failed, missing, or malformed witness omits
the theorem rather than weakening its meaning.

### Kernel boundary

The desired final build uses ordinary Lean kernel reduction or explicit proof
terms.  The project contains no `sorry`, project-specific axiom, unchecked
solver oracle, or `unsafe` declaration in the proof dependency graph.  It
reports `#print axioms` output for the main theorems and distinguishes Lean's
standard logical axioms from any artifact-specific assumption.

`native_decide` is not silently described as full kernel verification.  If
ordinary reduction is initially too expensive, the escalation order is:

1. improve the data structures and generic checker without changing the
   theorem;
2. generate explicit proof terms whose types are checked by the kernel; and
3. if still impractical, publish the strongest accurately described checked
   artifact and state that full Lean kernel checking was not achieved.

## Independence and trust chain

The durable evidence path is:

```text
fixed topology --> Lean equation builder ------------------+
       |                                                   |
       +--> independent Python builder                     |
       |                 +--> canonical digest match       |
       |                 +--> radial certificate ----------+--> Lean kernel
       |                                                   |
       +-----------------------> deletion witnesses -------+
```

The Python radial program is a certificate generator, not part of the trusted
proof.  The Lean checker is written against the mathematical definition and
checks certificate completeness locally.  Shared serialized outputs are data,
not trusted status assertions.

The existing radial generator must fail closed.  In particular, every solver
call distinguishes `sat`, `unsat`, and `unknown`; `unknown`, timeout, malformed
model data, or incomplete enumeration stops certificate generation.  The
current pattern that exits a `while solver.check() == sat` loop for both
`unsat` and `unknown` must be corrected before its output is retained as a
publication artifact.

## Optional independent SAT certificate

A second encoder may translate the fixed equation manifest to CNF and ask
CaDiCaL to emit DRAT, FRAT, or LRAT evidence.  The proof must be checked by a
documented checker, with exact commands, versions, digests, and results
archived.  Translation fidelity is tested against known satisfying instances
and canonical equation identities.

This layer is valuable as implementation diversity, but it is optional because
CNF translation and large traces can obscure the small radial argument.  It
must not replace the direct formalization or become an unreported trust
assumption.  If the trace is excessively large or the checker pipeline is not
cleanly reproducible, the preprint states that the attempted cross-check was
omitted.

## Reproducibility artifact

The repository will contain:

- the LaTeX manuscript and generated bibliography;
- the Lean project, generic soundness proof, instance, and certificates;
- the independent canonical-manifest builder;
- the radial certificate generator and exact witness generator;
- all promoted certificates and witnesses with cryptographic digests;
- one non-interactive clean-build entry point;
- locked dependency and tool versions;
- machine, operating-system, runtime, and peak-memory metadata;
- complete verification logs; and
- a concise artifact README mapping every paper claim to one command and one
  theorem or checked output.

Generated data and logs remain separate from hand-written definitions and
proofs.  A clean-checkout reproduction must not depend on untracked files,
ambient solver state, or the original exploratory worktree.

## Preprint structure

The manuscript should contain:

1. a precise finite statement and explicit limitation of scope;
2. enough reverse-and-add context to define the topology without implying a
   general Lychrel result;
3. the radial path decomposition and interface-width observation;
4. pseudocode and a mathematical proof of the generic frontier theorem;
5. concrete certificate statistics and the formally checked result;
6. the satisfiable-neighbor witness and, only if completed, deletion
   minimality;
7. an explicit trust and reproducibility account;
8. related work and careful novelty positioning; and
9. limitations and possible symbolic extensions.

Heuristic discovery, failed-assumption cores, Qwen/Prism framing, and solver
experiments are provenance, not proof.  The paper either places them in a
clearly labeled discovery section or omits them.

## Literature and publication positioning

Before claiming novelty, perform a focused review covering reverse-and-add and
Lychrel literature, David Seal's historical base results, the relevant OEIS
entry, finite-state and path-decomposition proof techniques, and recent
proof-carrying SAT/Lean work.  Search absence is not evidence of novelty.

The artifact follows the London Mathematical Society's current
computer-aided-proof guidance: the manuscript makes the role of computation
explicit, supplies surveyable code, and deposits supplementary code and data.
Relevant proof-tool references include CaDiCaL, DRAT-trim/LRAT checking, and
FRAT elaboration.  Method references justify the trust architecture but do not
establish the concrete theorem.

Initial primary sources:

- London Mathematical Society, “Policy on Computer Aided Proofs,” updated
  November 2024: <https://www.lms.ac.uk/publications/policies/computeraidedproofs>
- CaDiCaL repository and documentation: <https://github.com/arminbiere/cadical>
- DRAT-trim and LRAT checker sources: <https://github.com/marijnheule/drat-trim>
- Baek, Carneiro, and Heule, “A Flexible Proof Format for SAT Solver-Elaborator
  Communication,” FRAT: <https://arxiv.org/abs/2109.09665>

## Alternatives considered

### SAT trace as the primary proof

This is standardized and independently checkable, but it introduces a CNF
translation boundary and may generate a much larger, less explanatory
certificate.  It is retained as an optional cross-check.

### Standalone Python verification only

The exact radial algorithm is already strong computational evidence, but its
constraint builder and replay share implementation paths and its current
solver loop does not distinguish `unknown` from `unsat`.  It does not meet the
selected publication trust target by itself.

### Full direct symbolic derivation

A short algebraic contradiction would be preferable if found, but none has
been independently verified.  Symbolic lifting remains future work and cannot
delay or broaden the finite certified theorem.

## Prism disposition

Prism was asked to suggest conservative, independently checkable certificate
formulations for immutable problem
`t26_base19_publication_certificate`, version 1, seed `260819`.  Six allocated
frames ran through the requested Qwen-backed mathematical framing path, but all
six applications were schema-invalid and produced no artifacts.  No Prism
output influences the theorem, proof architecture, or evidence.

## Acceptance gates

The artifact may be called publication-ready only when all required gates pass:

- the mathematical statement is frozen and rendered identically by the two
  independent builders;
- the canonical manifest and promoted artifacts have stable digests;
- all solver outcomes used during certificate generation are exact and
  fail-closed;
- a clean Lean build checks the 409-equation unsatisfiability theorem;
- Lean checks the complete 408-equation satisfying witness;
- the theorem dependency graph contains no placeholder or unreported oracle;
- every number and status quoted in the manuscript is generated from archived
  checked output;
- the one-command reproduction succeeds from a clean checkout; and
- the literature review supports the wording of every historical or novelty
  claim.

The deletion-minimality and independent SAT layers have their own promotion
gates and are absent from the claims if incomplete.  Any disagreement between
builders, checkers, witnesses, or reported results stops publication packaging
rather than being resolved by majority vote.
