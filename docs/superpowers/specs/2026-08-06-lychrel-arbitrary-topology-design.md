# T24 Arbitrary-Digit Lychrel Topology — Design

## Goal and claim boundary

Retain the exact six-phase fragment lengths, repeat locations, and repeat
digits from the T21 base-17 certificate, but replace all 497 fixed digit
occurrences independently by arbitrary digits in `0..B-1`. Classify bases
`18..40`. Repeat token `0` remains `0`; repeat token `16` becomes `B-1`.
Carries are fresh Boolean variables in every phase, parameter, and column.

A positive must satisfy the six reverse-add identities for every `n >= 0`,
have canonical leading digits, and be non-palindromic in all phases. A
negative at `n=0` is decisive because every infinite family contains its
`n=0` member. The claim says nothing about other fragment layouts, repeat
locations, periods, or reverse-add families.

## Exact finite-domain model

For each fixed occurrence create one digit variable `z` with domain
`0..B-1`. Render one transition at a concrete parameter and read columns
least-significant first. Each column is exactly

```text
left + right + carry_in = target + B*carry_out,
```

where both carries are Boolean and missing boundary carries are zero. This is
necessary and sufficient for ordinary base-`B` addition. At `n=0`, the six
transitions contain 499 output columns. The final transition targets phase
zero at `n=1`, so the two fixed repeat digits still constrain the wrap even
though the five earlier `n=0` source words contain no repeat tokens.

The primary CNF uses one-hot digit domains. For every possible pair of input
digits and incoming carry, implication clauses force the unique target digit
and outgoing carry. Domain, leading-nonzero, and boundary clauses complete an
equisatisfiable encoding. Variable allocation and clause ordering are
deterministic, permitting a stable SHA-256 digest.

Base 17 is calibrated without asking the solver to rediscover a hard positive:
extract the published T21 digits and their actual carries, encode them as a
complete assignment, and require that assignment to satisfy every generated
clause. The existing exact `Z[q]` verifier and 54 direct integer replays remain
the mathematical positive control.

## Independent negative audit

The standalone audit reads the saved T21 JSON and imports neither the primary
compiler nor its word/topology helpers. It allocates binary digit bits, forbids
bit patterns outside `0..B-1`, and independently emits transition-table
implications for target bits and carries. Thus a shared error in one-hot domain
logic, variable allocation, or topology rendering cannot make both encodings
agree automatically.

Run the primary one-hot CNF with Sage's bundled PicoSAT binding and the binary
CNF with CaDiCaL. For every UNSAT result, store the variable count, clause
count, DIMACS digest, and solver identity. Wall times may be printed as
diagnostics but are excluded from the deterministic evidence. The durable
obstruction is the complete `n=0` topology system; no minimal-core claim is
made unless a separately checked smaller core is actually found. If proof
tracing and a DRAT checker are available, validate the proof during evidence
generation and record that separately; solver agreement is not mislabeled as
a formal proof trace.

## Method comparison

### Selected: finite-domain SAT with two encodings

The constraints are Boolean after digit encoding, have no numerical
conditioning, and preserve the local carry hypergraph that Prism highlighted.
One-hot clauses propagate strongly; the binary audit changes both the domain
representation and executable implementation. Any positive is decoded and
checked arithmetically, so solver trust only matters for negative results.

### Rejected as primary: monolithic MILP

Sage/Coin did not find a feasible point in a bounded exploratory run, and GLPK
reported a singular LP basis on the redundant 499-row `n=0` system. Neither
failure is mathematical evidence. MILP remains a diagnostic, not acceptance.

### Rejected: fixed base-17 carry skeleton

Holding every carry to the published base-17 trace makes the 497-digit linear
system immediately infeasible in base 18. That is useful pruning but does not
cover fresh carry behavior and therefore cannot classify the requested class.

### Rejected: Gröbner/resultant elimination

Prism proposed determinant, resultant, and syzygy invariants but supplied no
defined transition matrices or derivations. A 497-digit Boolean/integer ideal
also discards the bounded-domain propagation that makes SAT tractable. These
proposals remain unverified hypotheses.

## Prism disposition

Prism problem `lychrel-bases:base17-arbitrary-digit-topology`, version 1, used
seed `20260806`, prompt version 2, and `qwen3.6:27b-mlx` for both the
graph/hypergraph and algebraic-lifting frames. The accepted disposition is to
treat carries as layered finite state, search locally, and demand a cut/core or
independently checkable certificate. Its claimed carry-flux, determinant,
resultant, `Omega(B)`, bounded-treewidth, and positive-component predictions do
not enter the proof. Its statement that larger bases may require multi-bit
carries is false here: adding two base-`B` digits and a Boolean incoming carry
always produces an outgoing carry in `{0,1}`.

## Evidence and stop conditions

The deterministic JSON records the immutable scope; base-17 clause-assignment
calibration; primary results for every base `18..40`; independent binary audit
results; exact agreement; Prism provenance; and explicit limitations. Stop at
`n=0` only when it is UNSAT. If any base is SAT, compile `n=0,1,2`, decode the
digits, verify exact `Z[q]` identities and non-palindrome witnesses, then
minimize deviations from the T23 lower/upper alphabet. No optimization claim
is made when all bases fail the necessary `n=0` test.
