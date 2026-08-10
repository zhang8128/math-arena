# lychrel-bases

For base `b`, iterate `T_b(n) = n + reverse_b(n)`. The target is a finite,
inductive certificate for an orbit that never reaches a palindrome, preferably
in a base where no such number is presently proved.

## STATUS

`open`

No new proved Lychrel base was found. One important proof grammar is now
calibrated and computationally classified over a nontrivial base range, and its
exact boundary is known.

## SEARCHED

### Prism framing

Math Prism was run with engine prompt version 2, model `qwen3.6:27b-mlx`, deep
32K disposition generation, deterministic serialization, seed `20260804`, and
four frames:

- dynamical orbits;
- algebraic lifting;
- computational experiment;
- a trial composition of information encoding with modular/local-global
  reasoning.

Prism altered the search disposition toward finite carry automata, affine
lifting, and falsifiable bounded probes. Its concrete numerical suggestions
were treated only as hypotheses: the proposed base-3 small seed was refuted by
exact enumeration (every seed `1..50` reaches a palindrome within four steps),
and the suggested base-12 seed `2486_12` reaches `67276_12` at step 3.

### Primary-source recovery and exact port

The primary MathPages construction shows that the useful certificate is not a
whole-word RLE cycle. It consists of fixed inner and outer digit words separated
by growing blocks of `0` and `b-1`, with a finite carry connector joining the
two halves. The public-domain school package supplies the corresponding Haskell
search program.

Because this machine has no GHC, `search.hs` was ported literally to
`.timeloop/lib/lychrel_templates.py`. The port was calibrated before exploration:

- base 26 exterior and interior output matches the four published lines
  byte-for-byte;
- the published base-26 `2+2` connector is recovered at minimal depths 8 and 2;
- the published base-11 `3+3` connector is recovered at minimal depths 7 and 21;
- `.timeloop/tests/test_lychrel_templates.py` passes all four regression tests.

The reachability search deduplicates the six-field carry state. This preserves
connector existence because every future transition depends only on that state.
It reports graph exhaustion separately from a depth cutoff. Matching uses the
full connector `(leading-bit, upper carries, lower carries)`; the reference
program's display function accidentally prints the upper carries twice, so its
text prefix alone is not used for equality.

### Exact finite-graph result: symmetric four-step grammar

For every base `3..40`, both the exterior and interior `2+2` carry graphs were
exhausted. Base 26 is the **only** base with a matching connector. Thus this
specific four-step grammar cannot prove a new Lychrel base in `3..40`.

Base 38 was the strongest near miss: 7,939 exterior states and 10,762 interior
states, but its exterior connector is `T:(10):(10)` while its interior
connectors are `T:(00):(11)` and `F:(11):(00)`.

### Six-step and asymmetric extensions

For the symmetric `3+3` grammar, complete exterior and interior graphs were
checked for bases 7, 11, 20, 24, 30, and 35. Only the published base 11 matches.
The search also reached depth 80 and 111,734 interior states in base 39 without
a match, but that graph did **not** exhaust, so this is a bounded negative only.

Asymmetric splits were also tested:

- positive `pa != pb`, `pa+pb <= 6`, bases `3..40`, exterior depth 50;
- `pa+pb = 7`, bases `3..30`, exterior depth 60;
- asymmetric `pa+pb = 8`, bases `3..30`, exterior depth 70.

The only non-power-of-two exterior candidates for total at most 6 were
`(b,pa,pb)=(6,2,3),(14,2,3),(9,4,1),(11,4,1)`; none found an interior match
through depth 100. Total 7 and asymmetric total 8 produced no accepting
exterior connector in the stated ranges. A symmetric `4+4` base-20 search
found several exterior and interior connectors through depth 120 but none
matched; this was bounded, not an exhaustion claim.

Exact summary: `.timeloop/runs/t20_lychrel_template_summary.json`.

## RULED OUT

- Small-seed survival is not a useful proxy for a certificate. Bases 3, 4, and
  5 have no seed `<=50` surviving 400 steps, while binary 22 does; a Prism seed
  suggestion can fail in only three steps.
- Whole-word affine RLE is too rigid. It recognizes binary 22 and the published
  base-4 construction but misses the published non-power-of-two templates.
- More depth in the symmetric `2+2` grammar cannot help for bases `3..40`: the
  finite carry graphs are exhausted.
- A partial exterior or interior connector is not evidence of a Lychrel
  certificate. Base 38 demonstrates the failure vividly.
- Do not continue the `3+3` base-59 interior enumeration in its current form.
  It was stopped after more than six minutes and roughly 943 MB RSS without
  completing even the useful audit; connector-directed or symbolic search is
  required first.

## STRUCTURE

A certificate is a finite-state transducer invariant, not merely an observed
digit pattern. Fixed boundary words and growing homogeneous blocks communicate
through carry vectors. The proof obligation splits naturally into:

1. an exterior path fixed by the leading-digit/growth condition;
2. an interior path fixed by central reversal symmetry;
3. equality of the complete carry connector;
4. a direct palindrome check for every phase of the finite cycle.

The negative results localize the missing expressivity. The published base-17
certificate has two independently growing homogeneous blocks embedded in a much
larger fixed word, and the base-20 construction has more than 200 digits. Neither
is recovered by the paired single-connector grammar even though both bases are
known positive. Therefore the next proof grammar must allow multiple block
interfaces or a composition of connector transducers; increasing search depth
inside the present grammar attacks the wrong variable.

## TECHNIQUE

- Prism was useful as a disposition generator: the algebraic-lifting and
  information-encoding views led to primary-source carry automata. Its concrete
  candidate seeds were false and contributed no evidence.
- Calibrate a translated mathematical search against multiple published outputs
  before using its negatives. Base 26 tests a four-step short interior; base 11
  tests a six-step depth-21 interior.
- Search accepting exterior states first. Most bases die cheaply, so only bases
  with an exterior connector should pay for the large interior graph.
- Deduplicate complete carry states and expose `exhausted` explicitly. A depth
  cutoff and a finite-graph classification are different results.
- Cache half-block transitions. This reduced the published regression suite from
  3.3 seconds to about 0.2 seconds and made exact graph audits practical.

## NOVELTY

`superseded` for the positive constructions; `not found` for the bounded grammar
classification, which is not promoted as a new mathematical theorem.

Primary/public sources checked on 2026-08-04:

- MathPages, “Digit Reversal Sums Leading to Palindromes”:
  <https://www.mathpages.com/home/kmath004/kmath004.htm>
- MathPages, “Self-Similar Reverse-Sum Sequences”:
  <https://www.mathpages.com/home/kmath312/kmath312.htm>
- David Seal's published sporadic base-4, 11, 17, 20, and 26 constructions:
  <https://www.mathpages.com/home/dseal.htm>
- “Search for and classification of Lychrel numbers” and its public-domain
  source package: <https://p196.org/files/lychrel842.zip>
- OEIS A075153 (base-4 six-step formula): <https://oeis.org/A075153>
- OEIS A060382 (smallest candidates by base): <https://oeis.org/A060382>

Web/OEIS queries included `Lychrel numbers arbitrary bases proof base 17 base
20 base 26 self similar reverse add`, exact searches for base 38, and the named
paper/package. The established literature still lists proved Lychrel numbers in
bases 11, 17, 20, 26, and powers of two; no source found a proof in a new base.

## NEXT

Use the published base-17 certificate as the next calibration target for a
**multi-interface connector grammar**: extract each growing `0`/`(b-1)` block as
its own transducer, compose the interfaces, and require the generalized engine
to reconstruct base 17 before scanning unknown bases. Do not extend the current
single-connector `2+2` or `3+3` graphs.

## COST

Roughly four hours of research and exact computation. This included primary
source recovery, two false Prism leads, an independently checked candidate-orbit
census, a literal public-domain port, four regression tests, complete `2+2`
graphs for 38 bases, complete `3+3` audits for six candidate bases, bounded
asymmetric searches, and two consciously terminated resource-heavy searches.

## T21 STATUS — MULTI-INTERFACE VERIFIER WORKS; NO NEW BASE

The multi-interface grammar requested by T20 is now implemented and calibrated.
It reconstructs David Seal's published base-17 period-six family with two
independently growing homogeneous blocks and proves the complete recurrence by
exact coefficient identities. A bounded scan of the first 1,200-step survivor
in every base `3..40` found no additional recurrence in the searched grammar.

### SEARCHED

Math Prism was run on the immutable problem
`lychrel-bases:base17-multi-interface` with engine prompt version 2, model
`qwen3.6:27b-mlx`, 32K deep disposition generation, deterministic
serialization, and seed `20260805`. Algebraic-lifting and graph/hypergraph
frames completed; information-encoding and induction/recursion timed out during
serialization. The algebraic frame's useful prediction was a two-interface
six-step closure. Its proposed quotient-ring invariant, `GL_2` carry maps, rank
minimality, and parity register were not accepted as evidence. Prism records a
scope-limited `computationally_supported` outcome only for the independently
checked two-interface closure. The graph frame's three-port-color prediction
remains untested and received no positive outcome.

The exact search then:

- inferred parametric templates from two adjacent numerical cycles by deleting
  only inserted `0` or `b-1` digits;
- accepted a candidate only when all reverse-add identities held coefficient by
  coefficient;
- required a fixed outer-digit mismatch in every phase, proving every member of
  the family non-palindromic;
- calibrated on Seal's base-17 word starting at published parameter `n=2`;
- checked 54 additional direct integer additions over nine parameter values;
- scanned bases `3..40`, seed bound 5,000, 1,200 reverse-add steps, periods
  `2..12`, and at most four homogeneous interfaces.

For each base, the scan used the least non-palindromic seed at most 5,000 that
survived all 1,200 steps. These seeds exactly reproduce the corresponding OEIS
A060382 entries in this range. None of their bounded orbits contained an exact
cycle in the searched grammar. Durable evidence is in
`.timeloop/runs/t21_lychrel_multi_interface.json`.

### RULED OUT

- The failure of T20 was representational, not an absence of finite structure:
  two growing blocks are sufficient to express the published base-17 proof.
- The first 1,200-step survivor in each base `3..40` has no recurrence with
  period `2..12` that is visible in two adjacent cycles as one to four inserted
  homogeneous `0`/`(b-1)` blocks and passes the exact polynomial verifier.
- This does **not** rule out other seeds, onset after step 1,200, longer periods,
  five or more interfaces, non-extreme repeated digits, unequal growth rates,
  or certificates not discoverable by adjacent-cycle deletion alignment.
- Prism's quotient-ring formula and three-color hypergraph are not established
  facts. Only the narrower two-interface closure survived independent checking.

### STRUCTURE

For a parametric word

`W(n) = F_0 d_1^n F_1 ... d_k^n F_k`, where `d_i` is `0` or `b-1`,

set `q=b^n`. Appending a fixed fragment sends
`P -> b^len(F) P + value(F)`; appending `0^n` sends `P -> qP`; and appending
`(b-1)^n` sends `P -> qP+q-1`. Hence the value of `W(n)` is an integer
polynomial in `q`. Reversal is exactly token reversal. Every ordinary phase is
therefore the polynomial identity
`P_W(q)+P_rev(W)(q)=P_next(q)`, while the wrap phase substitutes `q -> bq`.
Coefficient equality proves all `n>=0` at once, without simulating carries or
guessing a finite cutoff.

This cleanly separates discovery from certification. Two observed cycles may
suggest deletion alignments, but no sampled orbit is part of the acceptance
rule. The certificate consists only of immutable digit fragments, repeat
tokens, exact integer coefficients, and phase-wise non-palindrome witnesses.

### TECHNIQUE

- Use adjacent cycles to infer where homogeneous interfaces grow, while
  enumerating ambiguous deletion alignments rather than choosing greedily.
- Compile the resulting word grammar into polynomials in `b^n`; exact arithmetic
  is a smaller and stronger verifier than a hand-built carry-state machine for
  this class of certificates.
- Keep the positive control in every scan. The base-17 reconstruction catches
  transcription, phase-rotation, and wraparound errors before any negative
  census is trusted.
- Canonicalize a recurrence by earliest start and then shortest period; phase
  rotations of one cycle are not distinct discoveries.

### NOVELTY

`published_prior_art_found` for the positive control and `novelty_not_found` for
the scan. The base-17 family is Seal's published construction, and every bounded
survivor seed is already in OEIS A060382. No new Lychrel base or theorem is
claimed. The exact multi-interface polynomial verifier is a research-method
advance inside this arena.

Sources rechecked on 2026-08-05:

- David Seal's construction: <https://www.mathpages.com/home/dseal.htm>
- OEIS A060382: <https://oeis.org/A060382>

### NEXT

Lift the verified base-17 topology symbolically across the base parameter:
retain its fragment lengths and phase/carry topology, replace literal digits by
base-dependent variables, and solve the coefficient identities together with
digit-range constraints. Calibrate the symbolic system at base 17, then test
unknown bases. This attacks construction space directly instead of waiting for
the least empirical survivor to reveal a short recurrence.

### COST

Roughly two additional hours: four deep Prism frames (two completed, two
serialization timeouts), a TDD exact-algebra and inference module, nine focused
tests, published base-17 reconstruction, 54 independent integer checks, and a
38-base bounded scan. The complete scan took about 11 seconds once the exact
compiler and subsequence prefilter were in place.

## T22 STATUS — BASE-17 TOPOLOGY HAS NO GLOBAL AFFINE LIFT

The exact T21 base-17 word topology cannot be lifted to every base `b>=17` by
making each fixed digit an integer affine function of `b`, even when carries are
allowed to change with the base. This is an exact negative classification of a
natural construction class, not a new Lychrel base.

### SEARCHED

Math Prism ran two deep frames on the immutable problem
`lychrel-bases:base17-symbolic-lift`, using prompt version 2, model
`qwen3.6:27b-mlx`, seed `20260805`, and the full 32K disposition budget:

- modular/local-global proposed column-wise anchor constraints;
- duality proposed treating feasibility failure as a compact obstruction.

Both useful dispositions were independently supported with narrowly scoped
Prism outcomes. Their proposed modular carry-period invariant, `Omega`
invariant, anchor-sign rule, threshold formula, and two-base probes remain
unverified and received no support.

For a base-17 digit `d`, every integer affine digit function valid for all
`b>=17` and specializing to `d` has one of exactly two forms:

`d` or `d+(b-17)=b-(17-d)`.

Indeed, if `f(b)=ab+c` remains between `0` and `b-1` for unbounded `b`, then the
integer slope satisfies `0<=a<=1`; specializing at 17 fixes `c`. Thus the 497
fixed digit occurrences give 497 Boolean lower/upper anchors. The repeat tokens
remain `0` and `b-1`.

The first solver preserved the observed base-17 carries for `n=0..3`. Its 2,068
equations reduced to 572 unique constraints and an irreducible two-equation
contradiction. Because carry preservation was an avoidable assumption, this was
treated only as a diagnostic.

The decisive solver compiled all six identities directly in `Z[b,q]`, with
`q=b^n`, and linearized every coefficient in the 497 anchors. Its 544 exact
Boolean equations have no solution. Deletion minimization again produced two
equations, now with no carry assumption. Writing their eight anchor variables
as `a,b,c,d,e,f,u,v`, the core is

`-17a + 2b - 17c + 17u - v = -16`,

`17d - e - 17u + 2v - 17f = 0`.

All variables are in `{0,1}`. Modulo 17, the first equation becomes
`2b-v=1`, forcing `b=v=1`; the second becomes `-e+2v=0`, forcing `e=v=0`.
Hence the shared anchor `v` must be both 1 and 0. This proves infeasibility.

The independent audit does not import the affine compiler or CSP module. It
rebuilds both coefficient equations from the saved T21 fragments, brute-forces
all `2^8` core assignments, finds zero joint solutions, and finds 24 solutions
after deleting either equation. Exact evidence is in
`.timeloop/runs/t22_lychrel_affine_lift.json`.

### RULED OUT

- No assignment of lower/upper affine anchors makes the exact T21 six-phase,
  two-repeat-block topology a reverse-add certificate for every integer base
  `b>=17`.
- This conclusion allows carries to change with `b`; it is stronger than the
  initial carry-skeleton obstruction.
- It does **not** rule out certificates valid only in selected bases, piecewise
  digit functions, nonlinear digit functions, different repeat placement or
  lengths, different periods, or entirely different word topologies.

### STRUCTURE

The natural base lift is a finite Boolean problem because digit boundedness
forces affine slopes to zero or one. The reverse-add induction is a bivariate
polynomial identity: `b` controls digit values and place values, while
`q=b^n` controls the growing blocks. Each coefficient is linear in the anchor
bits. This converts a seemingly large symbolic-number problem into exact sparse
Boolean equations, and an unsatisfiable core can be read as elementary modular
arithmetic.

The carry and polynomial formulations serve different purposes. Carries give a
local diagnostic; global coefficients give the complete classification. The
second must be run whenever preserving the reference carry skeleton fails.

### TECHNIQUE

- Prove the allowed affine digit forms before searching them; boundedness turns
  an infinite functional choice into one Boolean bit per occurrence.
- Use one-at-a-time anchor flips to extract exact global coefficient equations.
  Linearity makes this exhaustive, not numerical interpolation.
- Minimize negative systems to an irreducible core and then look for a human
  quotient. Here reduction modulo 17 exposes the contradiction immediately.
- Audit the final core with a separately implemented polynomial dictionary and
  exhaustive `2^8` enumeration.

### NOVELTY

`not found`, with no publication claim. David Seal's page publishes the fixed
base-17 construction, and the Lychrel classification literature develops carry
searches, but searches found no prior affine-in-base lift or this obstruction.
Queries included exact searches for `base-17 Lychrel affine lift`, `variable
base carry equations David Seal`, the two core equations, and the shared anchor
formulation. This remains a scoped internal negative result pending expert
review.

Sources checked on 2026-08-05:

- David Seal's published construction: <https://www.mathpages.com/home/dseal.htm>
- “Search for and classification of Lychrel numbers”:
  <https://cocalc.com/share/download/00ae14310fa0520ec7b59482b0807d8082d2c891/ReverseAndAddPDF.pdf>
- OEIS A060382: <https://oeis.org/A060382>

### NEXT

Relax global validity while retaining the learned topology: for each fixed base
`18..100`, solve lower/upper anchors with fresh carry variables and require an
exact polynomial identity in `q=b^n`. This tests whether the base-17 topology
transplants to isolated bases even though no single affine mask works for all
bases. Calibrate at base 17 and include known bases 20 and 26 as controls, while
keeping their different published topologies conceptually separate.

### COST

Roughly one additional hour: two deep 27B Prism frames, comparison of three
lift methods, exact affine and bivariate arithmetic, a provenance-bearing
Boolean solver, carry and global coefficient classifications, two independent
two-equation cores, an independent polynomial reimplementation, exhaustive
core audits, and current literature searches.

## T23 STATUS — NO FIXED-BASE LOWER/UPPER TRANSPLANTS IN BASES 18..100

The exact T21 base-17 topology has no lower/upper occurrence transplant in any
fixed base `18..100`, even when every base receives an independent mask and
completely fresh carries.  The failure is stronger than expected: every base is
already impossible in the finite `n=0` member, before either growing interface
appears.

### SEARCHED

For a fixed base `B`, every one of the 497 fixed base-17 digit occurrences `d`
was independently allowed to be

`d` or `d+(B-17)`.

Repeat tokens were mapped rigidly as `0 -> 0` and `16 -> B-1`.  Carries were
fresh Boolean variables for every base, phase, parameter, and column; no
base-17 carry skeleton was preserved.

The exact decision method used the column identity

`left + right + carry_in = output + B*carry_out`.

Because the topology has two repeat interfaces, every transition residual has
degree at most two in `q=B^n`.  Satisfaction at `n=0,1,2`, hence at the three
distinct values `q=1,B,B^2`, forces the residual polynomial to vanish
identically.  The local carry system is therefore a complete infinite-family
decision, not a sampled heuristic.  Every positive would additionally have
passed the pre-existing exact `Z[q]` verifier and six fixed non-palindrome
witnesses.

The base-17 calibration passes all three interpolation parameters and the exact
polynomial verifier.  Each target base `18..100` is infeasible already in its
499-equation, 990-variable `n=0` system.  There are zero hits.  Deterministic
evidence is in `.timeloop/runs/t23_lychrel_fixed_base.json`.

### RULED OUT

- No per-occurrence lower/upper mask transplants the exact T21 six-phase,
  two-interface base-17 topology to any base `18..100`.
- This conclusion permits the mask and all carries to change independently in
  every base.
- The known base-20 and base-26 Lychrel constructions are not counterexamples:
  they use different published topologies.
- This does **not** rule out arbitrary fixed digits, different phase lengths or
  interface locations, other periods, other proof grammars, or Lychrel numbers
  in the tested bases.

### STRUCTURE

The 83 large CSP failures collapse to three tiny obstruction families.  The
same three columns

`(phase 1, column 40), (phase 1, column 41), (phase 2, column 41)`

are jointly infeasible in 81 bases.  That core becomes feasible only at bases
33 and 34.  Base 33 is blocked by columns `(1,41), (2,40), (2,41)`; base 34 by
`(1,41), (2,41), (2,42)`.  All are `n=0` columns.  The generic three-row family
is deletion-irreducible at base 18; at other bases some two-row subset already
suffices.  The exceptional cores are deletion-irreducible in their respective
bases.

The standalone audit imports neither the fixed-base compiler nor the Boolean
solver.  It reads the saved T21 fragments, independently reconstructs these
columns, and exhausts every Boolean assignment for every covered base.  All 83
joint solution counts are zero.  Its canonical equation digest is
`8cddc4593291c135f01ac009a29ee5d080b6a4119d9afad45305aa50652d476a`.

### TECHNIQUE

- Turn fixed-base digit choices and fresh carries into sparse local equations;
  avoid the high-arity rows produced when place-value coefficients are
  collapsed too early.
- Use interpolation at three `q` values to prove an all-parameter identity for
  a two-interface grammar, then retain a separate exact polynomial verifier as
  the acceptance oracle.
- Short-circuit a universal family at `n=0` when possible: one impossible
  member disproves the whole certificate.
- Minimize the explanation, not merely runtime.  A uniform three-column core
  plus two exceptional cores is independently auditable in a way 83 solver
  exits are not.

### PRISM

Math Prism applied symmetry/group-action and extremal-principle frames to the
immutable problem `lychrel-bases:base17-fixed-base-transplants`, version 1,
using prompt version 2, model `qwen3.6:27b-mlx`, seed `20260806`, and the 32K
disposition budget.

The useful disposition was to seek quotient-sized explanations and a boundary
obstruction.  The proposed reversal-carry signature, group action, asymptotic
elevation parity, zero-carry limit, and predicted positive representatives were
not accepted.  After the standalone audit, both concrete artifacts were
recorded as independently falsified Prism outcomes; the exact negative result,
not the model narrative, controls the frame feedback.

### NOVELTY

`not found`, with no publication claim.  Current searches found the published
base-17 construction, the public-domain carry search/classification work, the
known base list, and recent numerical-thread experiments, but no prior
base-by-base lower/upper transplant of Seal's topology or these obstruction
cores.  Queries included exact searches for `base-17 Lychrel affine digits`,
`reverse and add variable base carry equations`, `Lychrel topology transplant
base 17`, and the distinguishing core coordinates.

Sources rechecked on 2026-08-06:

- David Seal's construction: <https://www.mathpages.com/home/dseal.htm>
- Public-domain “Search for and classification of Lychrel numbers” archive:
  <https://p196.org/files/lychrel842.zip>
- OEIS A060382: <https://oeis.org/A060382>
- 2024 numerical-experiments abstract:
  <https://canum2024.math.cnrs.fr/programme/soumission/3a00c64b-9099-4c01-a7fc-367cfc8e04b4/abstract.pdf>

### NEXT

Decide whether the topology itself, rather than the two-anchor digit alphabet,
is the obstruction.  Retain the six phases and repeat layout but allow every
fixed occurrence to be an arbitrary digit `0..B-1`; solve the exact
`n=0,1,2` carry CSP first in bases `18..40`.  If feasible, minimize how many
occurrences must leave the lower/upper alphabet and verify the resulting cycle
exactly.  If infeasible, extract a topology-only core before changing interface
placement.

### COST

Roughly two additional hours: two deep 27B Prism frames, three method designs,
six TDD acceptance tests, a complete 83-base exact scan, three compact core
families, a standalone exhaustive reimplementation, deterministic replay,
current literature searches, and two independently falsified Prism outcomes.

## T24 STATUS — THE FIXED T21 TOPOLOGY ITSELF FAILS IN BASES 18..40

The exact T21 six-phase fragment lengths, repeat locations, and repeat digits
have no realization in any base `18..40`, even when all 497 fixed digit
occurrences are arbitrary independent values in `0..B-1` and every carry is
fresh. Every target base is impossible already at `n=0`; therefore no
`n=1,2` interpolation solve or lower/upper-deviation minimization is reached.

### SEARCHED

For each base `B`, fixed occurrences were represented by unrestricted finite
domain variables. Repeat token `0` remained zero and token `16` became `B-1`.
Each least-significant-first column enforced exactly

`left + right + carry_in = target + B*carry_out`,

with Boolean carries. The six `n=0` transitions contain 499 output columns.
The final transition targets phase zero at `n=1`, so both repeat insertions
remain active constraints in the wrap even though they vanish from the five
earlier `n=0` sources.

The primary one-hot CNF was solved by PicoSAT through pycosat 0.6.3. Base 18
has 9,439 Boolean variables and 715,404 clauses (DIMACS digest
`975f6e5adcc9218af5ca42dc3dfc6a10988922038e701eb1df46c809eeaed490`);
base 40 has 20,373 variables and 3,543,207 clauses (digest
`9344698f42d7730bee39c2fb7e5618bf79365a7e632eff443b2fa7d5adeaf199`).
All 23 formulas are UNSAT.

The base-17 control was not entrusted to search. Its 497 published digits and
all actual carries were encoded as a complete assignment and satisfy every one
of 637,939 generated clauses (digest
`ed3f866d0cd1d6ca293fd641c577816d9fdb2c2aff40517d8242af7981c41adc`).
The existing exact `Z[q]` verifier and 54 direct integer additions also pass.

### INDEPENDENT AUDIT

A standalone script imports no T24 production code. It reads only the saved
T21 JSON, represents every digit in binary, and builds ripple full-adders for
both sides of each column identity. CaDiCaL 3.0.1 accepts the fixed-digit
base-17 control and independently reports UNSAT for all bases `18..40`.

This is structurally different from the one-hot truth-table compiler. In base
18 the audit has 12,958 variables and 78,504 clauses (digest
`8ed10a48b4e62f57272a88d78fc5607448cf8c4970ad0dc461edb48ee602ad4e`);
in base 40 it has 15,451 variables and 96,416 clauses (digest
`70e12e371c5b5ecb10f445cb41f8414c4b0d5c410578b9b5009e8c53c83e8e81`).
The isolated-copy pytest proves the audit can run with only its script and the
T21 JSON. Both complete evidence generations are byte-deterministic.

This dual result is strong computational evidence, not a checked DRAT/LRAT
proof trace. The full 499-column `n=0` system is the topology-only obstruction;
no minimal column core is claimed.

### RULED OUT

- No arbitrary fixed-digit realization of this exact six-phase, two-interface
  topology exists in bases `18..40`.
- The result is strictly stronger than T23's lower/upper-alphabet negative on
  this base range.
- It does not rule out moving an interface, changing fragment lengths or
  period, using another proof grammar, or Lychrel numbers in these bases.
- The known base-20 and base-26 certificates remain outside this topology.

### TECHNIQUE

- Encode the larger finite alphabet and the two-state carry process at
  different levels: one-hot digits give strong local propagation; binary
  full-adders provide a compact independent audit.
- Calibrate a negative encoder by satisfying every clause with a known exact
  positive assignment before trusting any UNSAT result.
- Stop a purported all-parameter family at one impossible member. Here `n=0`
  avoids an unnecessary `n=1,2` system without weakening the negative logic.
- Keep deterministic DIMACS digests and solver identities, while stating
  plainly that solver agreement is not a proof-trace checker.

### PRISM

Math Prism applied graph/hypergraph and algebraic-lifting frames to immutable
problem `lychrel-bases:base17-arbitrary-digit-topology`, version 1, with prompt
version 2, model `qwen3.6:27b-mlx` for both frames, and seed `20260806`.

The useful dispositional change was to view carries as layered finite state and
seek a topology cut rather than continue base scanning. The proposed
carry-flux, determinant/resultant `Omega(B)`, and bounded-treewidth claims have
no derivation and were not used. Its claim that larger bases might require
multi-bit carries is false for two base-`B` digits plus a Boolean input carry:
the output carry is always in `{0,1}`.

After the binary/CaDiCaL audit, Prism recorded the graph artifact as
`falsified` because its base-18 closed-walk expectation fails, and recorded the
algebraic artifact as `bounded_no_counterexample` for the empty projected
systems in bases `18..40`. Exactly one outcome was fitness-eligible; no frame
lifecycle event fired.

### NOVELTY

`not found`, with no publication claim. Searches found Seal's published
base-17 construction, the public-domain carry classification, OEIS's base
table, general finite-domain-to-SAT methodology, and recent arbitrary-base
thread experiments, but no prior arbitrary-digit realization test for this
specific topology or this 23-base obstruction. Exact queries included
`base 17 Lychrel topology arbitrary digits`, `Lychrel carry equations variable
base`, `reverse and add SAT encoding`, and the distinguishing six-phase scope.

Sources rechecked on 2026-08-06:

- David Seal's construction: <https://www.mathpages.com/home/dseal.htm>
- Public-domain classification paper/code:
  <https://cocalc.com/share/download/00ae14310fa0520ec7b59482b0807d8082d2c891/ReverseAndAddPDF.pdf>
- OEIS A060382: <https://oeis.org/A060382>
- Metodi and Codish, finite-domain constraints to SAT:
  <https://arxiv.org/abs/1206.3883>
- 2024 arbitrary-base numerical experiments:
  <https://canum2024.math.cnrs.fr/programme/soumission/3a00c64b-9099-4c01-a7fc-367cfc8e04b4/abstract.pdf>

### NEXT

Relax topology rather than digits. Retain six phases and the repeat digits but
move exactly one repeat interface by at most two fixed columns in one phase.
Use the dual `n=0` encodings as a bounded filter in bases `18..40`; only a
survivor earns the `n=0,1,2` interpolation solve and exact `Z[q]` verification.
This is the smallest change that directly tests whether interface placement is
the obstruction without reopening unconstrained topology search.

### COST

Roughly four additional hours: two deep 27B Prism frames, literature and solver
method comparison, two failed MILP diagnostics, a base-17 carry-skeleton test,
TDD for the topology and one-hot compiler, 23 primary exact solves, a standalone
binary full-adder implementation, 23 CaDiCaL audits, two positive calibrations,
four deterministic full replays, and 10 focused acceptance tests.

## T25 STATUS — EVERY ONE-INTERFACE MOVE BY AT MOST TWO COLUMNS FAILS

The topology obstruction is stable under the smallest local layout changes.
Starting from T21's six-phase construction, exactly one of the two repeat
interfaces in exactly one phase was moved left or right by one or two fixed
columns. The flattened fixed-digit order, repeat order, successor relation,
arbitrary digit domains, and fresh Boolean carries were preserved. No such
topology has a realization in any base `18..40`, already at `n=0`.

### EXACT REDUCTION

There are 48 admissible moves: six phases, two interfaces, and four signed
shifts. At `n=0`, repeats vanish from every source and from the outputs of the
first five transitions. The only repeated output is the wrap from phase five
at `n=0` to phase zero at `n=1`. Consequently, moving an interface in phases
one through five leaves the canonical `n=0` column system unchanged and
inherits T24's independently audited obstruction. This accounts for 40 moves
without new solver calls.

Only phase-zero placement can affect the necessary condition. Its fragment
lengths `(28,23,31)` produce the eight new layouts

`(26,25,31), (27,24,31), (29,22,31), (30,21,31),`
`(28,21,33), (28,22,32), (28,24,30), (28,25,29)`.

Each was classified in every base `18..40`: 184 genuinely new instances.

### DUAL EXACT RESULT

The primary one-hot/PicoSAT encoding reports UNSAT for all 184 systems. No
instance reaches `n=0,1,2` interpolation, exact `Z[q]` materialization, or
non-palindrome verification because none survives the necessary filter.

A separately isolated audit reparses T21 JSON, implements the boundary move
independently, encodes digits in binary, constructs ripple full-adders, and
uses CaDiCaL 3.0.1. It also reports UNSAT for all 184 systems. Every paired
status agrees and every paired DIMACS digest differs. Formula sizes remain the
same as T24 because only incidence positions change: at base 18 the primary
formulas have 9,439 variables and 715,404 clauses while the audit formulas
have 12,958 variables and 78,504 clauses; at base 40 the corresponding counts
are 20,373/3,543,207 and 15,451/96,416.

Two complete integrated generations run concurrently and produce identical
157,328-byte JSON, SHA-256
`bb3aef086a95c1e95e71c80d36b44b34ee908f5f92aac81d24755b8c9cf723bc`.
This is strong computational evidence, not a checked DRAT/LRAT proof trace.

### PRISM

Math Prism was invoked with `qwen3.6:27b-mlx`, long thinking, and
information-encoding, modular-local-global, and invariants-monovariants
dispositions on two immutable problem snapshots. All three applications
failed Prism's artifact schema. They produced zero valid artifacts and enter
neither the proof nor frame evolution. The dispositional question that
survives is useful: seek a boundary-local carry/residue certificate that
compresses these solver negatives. No such invariant was supplied by Prism.

### SIGNIFICANCE AND LIMITS

- T24 ruled out one isolated repeat layout. T25 rules out its complete
  one-interface radius-two neighborhood: all 48 local moves, not a sample.
- The structural reduction is reusable. Any future `n=0` topology search need
  vary only interfaces appearing in the incremented wrap target.
- This does not rule out two simultaneous moves, a displacement of three or
  more columns, changed repeat digits/order, another period, another proof
  grammar, or Lychrel numbers in these bases.
- The result is an internally new scoped negative, not a claimed publication
  or a new base construction.

### RESEARCH

`not found`, with no publication claim. A current recheck found Seal's exact
base-17 period-six construction, the public-domain classification/search for
other proof grammars, OEIS A060382's numerical smallest-candidate table, and
2024 arbitrary-base thread experiments, but no single-interface deformation
or arbitrary-digit SAT classification of Seal's topology. Queries included
`Lychrel repeat interface topology base 17`, `reverse and add SAT base
topology Lychrel`, and exact topology/deformation phrases.

Sources rechecked on 2026-08-06:

- David Seal's base-17 construction: <https://www.mathpages.com/home/dseal.htm>
- Public-domain search/classification: <https://cocalc.com/share/download/00ae14310fa0520ec7b59482b0807d8082d2c891/ReverseAndAddPDF.pdf>
- OEIS A060382: <https://oeis.org/A060382>
- 2024 arbitrary-base numerical experiments:
  <https://canum2024.math.cnrs.fr/programme/soumission/3a00c64b-9099-4c01-a7fc-367cfc8e04b4/abstract.pdf>

### NEXT

Move from classification to explanation. Extract a deletion-minimal `n=0`
UNSAT column core for each of the eight phase-zero variants and compare them
under fixed-occurrence renaming. If a shared boundary-window core exists,
rebuild it with a standalone exhaustive carry/digit eliminator and derive a
uniform symbolic obstruction in `B`. Only after that proof-compression attempt
should the search expand to two simultaneous interface moves.

### COST

Roughly two hours: three long-thinking 27B Prism attempts (all invalid), three
method comparisons, an exact structural reduction from 48 moves to eight,
TDD for perturbation semantics and isolation, 184 one-hot/PicoSAT solves, 184
independently implemented binary/CaDiCaL solves, one caught isolated-import
defect, current literature/OEIS rechecks, and two concurrent deterministic
integrated replays.

## T27 STATUS — A COMPACT TERMINAL INVARIANT EXISTS; THE INDUCTIVE LIFT STOPS

### STATUS

Gate A is `STOP` at `backward_extension_layer_31_not_found`. Gate B was not
authorized, so no base-`41..200` scan, topology transport, symbolic base lift,
or Lean bridge was attempted.

### CLAIM

For the frozen 408-equation base-19 radial obstruction with removed coordinate
`phase=0,n=0,column=82`, all 22 promoted reachable states at layer 32 lie in
the union of three closed-grammar conjunctions of sizes 11, 11, and 10. No
state in that union extends to a bounded model of the terminal 12 equations.

The three components expose actual digit/carry laws rather than enumerating
the 22 states. Representative laws include

`D1 = 13 + R0 + R2 - 3*R1`,

`D0 = 14 + 2*R3 - R5`, `D1 = R0 + R3`, and

`R0 - 3*R2 - D1 = 17 (mod 19)`.

This is a terminal tail lemma for the already verified obstruction. It is not
an inductive replacement for the promoted frontier proof.

### FALSIFIABLE MILESTONE

The approved milestone required predicates for layers 25 through 32,
initiation on 20 layer-25 states, seven exact consecution checks, terminal
exclusion, and at least tenfold canonical-JSON compression. The reachable
state counts are exactly `(20,12,12,17,16,18,18,22)`.

Terminal synthesis passes, but literal transport to layer 31 misses reachable
states. State CEGIS, equation-derived structural families, batched
counterexample scoring, a 12-atom global conjunction, and several three-way
component partitions produced no accepted layer-31 predicate within the
frozen grammar. This is a bounded search failure, not a proof that no compact
inductive invariant exists.

### INDEPENDENT CHECK

The primary checker proves initiation over all 22 promoted layer-32 states and
terminal exclusion over the full `2^12 * 19^2 = 1,478,656` frontier domain.

The isolated standard-library checker imports no repository module. It reads
the frozen equation manifest, promoted frontier, and T27 evidence; rebuilds
allowed tuples for the terminal equations; evaluates all 22 reachable states;
and proves each clause UNSAT by independent generalized arc consistency and
backtracking. It rejects a mutated predicate constant. Its durable PASS binds
to primary evidence SHA-256
`32324c40903b78aec4d787b7e64a6d73d0999e3846d91ca1340c99f8ac2d8686`.

### COMPRESSION

The three-clause predicate is 1,987 canonical bytes. The explicit state
payload for layers 25 through 32 is 4,802 bytes, only about 2.42 times larger.
The required tenfold threshold therefore fails even before accounting for the
missing layer-25-to-31 predicates. No renamed state table is reported as a
successful certificate.

### PRISM AND RESEARCH

Math Prism supplied invariant, modular/local-global, duality, and composed
frames as hypothesis generators. Its concrete invariant and base claims were
independently falsified before this implementation, and no Prism statement is
a mathematical premise here.

A primary-source recheck on 2026-08-09 confirms that proof-derived
interpolation and pseudo-Boolean cutting planes remain appropriate candidate
generators. Cimatti, Griggio, and Sebastiani give proof-based interpolation
procedures for linear-arithmetic SMT; VeriPB documents independently checked
cutting-plane proof logging; and PBLean now imports VeriPB certificates into
Lean 4. None supplies this reverse-add invariant, and PBLean does not remove
the missing semantic bridge from digit equations to the proposed predicates.
No novelty claim is made.

Sources:

- Cimatti, Griggio, and Sebastiani, “Efficient Generation of Craig
  Interpolants in Satisfiability Modulo Theories”:
  <https://arxiv.org/abs/0906.4492>
- VeriPB project and publications: <https://veripb.org/> and
  <https://veripb.org/publications.html>
- Szeider, “PBLean: Pseudo-Boolean Proof Certificates for Lean 4”:
  <https://arxiv.org/abs/2602.08692>
- David Seal's base-17 construction: <https://www.mathpages.com/home/dseal.htm>

### STOP CONDITION

The first failed gate is the missing layer-31 backward extension. The
sub-tenfold diagnostic is an additional failure. Per the approved plan, either
failure forbids Gate B; the grammar was not enlarged to four clauses, 13
atoms, coefficient magnitude four, or modulus 21.

### LIMITATIONS

- The tail lemma depends on the promoted frontier for its reachability premise.
- It proves nothing about other base-19 topologies or unbounded reverse-add
  orbits.
- It does not explain the base-17/base-19 topology difference symbolically.
- It does not show that another bounded grammar or partition cannot succeed.
- The independent audit covers the achieved tail lemma, not an inductive
  certificate that does not exist.

### NEXT

Do not resume undirected SAT scanning. The narrow next experiment is to derive
the layer-31 weakest preimage of the three terminal families directly from the
12 local equations, preserving disjunction structure during elimination
instead of separating sampled states. Its first milestone is one exact
layer-31 predicate with at most three 12-atom clauses that covers all 18
reachable states and passes universal consecution. Stop there if it fails;
only a PASS earns extension toward layer 25.

## T28 STATUS — THE REACHABLE FOUR-CLASS QUOTIENT IS NOT READABLE AT LAYER 31

### STATUS

STOP. Primary synthesis and isolated assurance agree on
`decision_depth_exceeded` at layer 31. No T28 quotient certificate exists, and
the mandatory checkpoint forbade attempts at layers 30 through 25.

### CLAIM

For the frozen base-19 radial obstruction, removed coordinate
`phase=0,n=0,column=82`, T28 tested one exact claim boundary: whether the 18
promoted layer-31 states' four successor-signature classes extend to semantic
classes over the complete bounded layer-31 domain using coefficients `-3..3`,
moduli `2..20`, at most eight classes, 64 decision nodes, and ten tests per
path. They did not pass that bounded test. This does not prove that no readable
invariant, different partition, or reachability-aware quotient exists.

### RELATION TO T27 AND PREPRINT

T28 builds on, but does not replace, the preprint and T27. The preprint's
35-layer certificate remains the authoritative obstruction proof. T27 proves
the compact three-family terminal lemma at layer 32. T28 asks a different,
explanatory question: can those terminal families be pulled back one layer as
a small semantic quotient? The answer for the approved grammar and readability
cap is STOP. Nothing here weakens or strengthens the preprint's obstruction
theorem.

### QUOTIENT

Reachable successor signatures propose four layer-31 classes with member sizes
`(12,2,1,3)`: `DEAD`, plus one live predecessor class for each of
`T_HIGH_DIGIT`, `T_PHASE_ZERO`, and `T_RESIDUE`. Across layers 25 through 32,
the hypothesis class counts are `(5,5,7,7,6,5,4,3)` on reachable-state counts
`(20,12,12,17,16,18,18,22)`. These counts are discovery hypotheses, not
semantic theorems.

CEGIS began from 14 bounded affine/congruence atoms and stopped on iteration
222 with 37 candidate atoms. All accepted intermediate DAGs stayed within 64
nodes and ten tests per path. The next reduced tree crossed the depth-10 cap;
it was not serialized as a certificate. The frozen layer-32 terminal seed has
32 nodes and path depth 32 and is explicitly exempt from the synthesized-layer
path cap.

### EXACT CHECK

Every candidate was checked against the original local integer equations, not
only against the 18 promoted states. The decisive counterexample was

`D0=18, D1=6, L0=0, R0=0, L1=1, R1=0, L2=1, R2=1, L3=0, R3=0, L4=0, R4=0, L5=0, R5=1`.

The candidate classified it as `DEAD`, but the exact layer-32 relation has a
successor, falsifying `dead_has_no_successor`. This repeated phenomenon is the
unifying obstruction uncovered by T28: equality of successor signatures on
the promoted reachable sample is not, by itself, a congruence over the full
bounded frontier domain.

### INDEPENDENT CHECK

The isolated standard-library checker imports no repository module or solver.
It recomputes equation and frontier content hashes, replays output-state
digests for layers 30 through 33 with counts `(18,18,22,0)`, fixes the 14
counterexample coordinates, rebuilds allowed tuples for the 12 local equations,
and proves by generalized arc consistency plus backtracking that a successor
exists. It rejects an out-of-domain counterexample mutation. Its durable status
is also STOP and binds primary evidence SHA-256
`b0904f68fda4ad7990ac1d474ec157cf671567cdf02869d9ae2cceebe1814e47`.

### COMPRESSION

No layer-31 certificate exists, so no explanatory-compression PASS is claimed
and no certificate/table byte ratio is reported. T27's terminal predicate and
its previously reported compression diagnostic remain unchanged.

### PRISM AND RESEARCH

The updated Math Prism failed closed with
`MathFrameStoreOfflineMigrationRequired`, reason
`unrecognized_structural_layout_exceeds_inline_cap`, generation 2, schema
cookie 150. No migration was authorized, no frame artifact was fabricated, and
Prism supplied no mathematical premise. The manual symbolic-automata,
Presburger-preimage, and phase-cyclic frames remained hypotheses only.

D'Antoni, Kincaid, and Wang provide symbolic-automata and
bisimulation-up-to-congruence precedent
(<https://arxiv.org/abs/1610.01722>). Cimatti, Griggio, and Sebastiani provide
the optional proof-based interpolation/preimage route
(<https://arxiv.org/abs/0906.4492>). Neither source proves this reverse-add
quotient or predicts the STOP.

### STOP CONDITION

The first mandatory gate failed when exact counterexamples still required a
decision path deeper than ten. The grammar, class cap, node cap, topology, and
claim boundary were not enlarged. No base lift, base-17/base-19 classification,
topology scan, lower-layer extension, or Lean bridge ran.

### LIMITATIONS

- The counterexample falsifies the learned semantic `DEAD` guard, not the
  promoted four-way partition on its 18 sampled reachable states.
- The independent checker audits the achieved STOP boundary, not nonexistent
  guard, edge, or compression claims.
- T28 does not prove that depth 11 suffices, that another partition succeeds,
  or that a human-readable invariant is impossible.
- The preprint's obstruction certificate and T27's terminal lemma remain the
  only positive mathematical certificates in this chain.

### NEXT

The coherent next program is reachability-aware weakest-preimage analysis:
explain which additional invariant distinguishes promoted `DEAD` states from
the exact successor-bearing counterexamples, before attempting another guard
synthesis. Its first falsifiable milestone is a single independently replayed
predicate that separates all 12 promoted `DEAD` states from the iteration-222
counterexample set while remaining implied by an exact earlier-layer
reachability condition. Stop if that requires an unbounded state table or
changes the frozen topology. Treat a symbolic lift in base `b`, other bases,
and Lean as separate later decisions.

## T29 STATUS — A COMPACT FINITE SEPARATOR EXISTS, BUT IT IS NOT A DEAD REGION

### STATUS

`FINITE_SEPARATOR_PASS_SEMANTIC_STOP`. Primary synthesis and isolated
assurance agree: one ten-atom conjunction separates the frozen finite dataset,
but the exact 12-equation query finds a semantic successor inside it.

### CLAIM

For the frozen base-19 radial obstruction and removed coordinate
`phase=0,n=0,column=82`, the following conjunction contains all 12 promoted
layer-31 `DEAD` states and excludes all 221 exact T28 counterexamples plus all
six promoted live controls:

`L1+L3 >= 1`, `L2+L3 >= 1`, `D1-2*R2 >= 4`, `D0+L4 >= 6`,
`L0=L3`, `R1 <= R0`, `R0+R3 <= 1`, `D1-3*R2 <= 15`,
`D0-D1+R2 <= 2`, and `L5+R0+R5 <= 2`.

This is an independently checked finite separator over 239 serialized states.
It is not a reachability invariant, inductive invariant, semantic congruence,
or universal no-successor theorem.

### RELATION TO PREPRINT, T27, AND T28

The preprint's 35-layer certificate remains the obstruction proof. T27's
three-family layer-32 predicate remains the positive terminal lemma. T28's
four-class quotient still stops at candidate 222. T29 explains more of that
STOP: the 221 exact counterexamples are highly structured enough to admit a
short common exclusion rule, but finite exclusion alone does not characterize
the complete semantic dead region.

### TRACE

T28 replay yields exactly 221 distinct `DEAD` / `dead_has_no_successor`
counterexamples at iterations 1 through 221. Candidate 222 fails during DAG
construction with `decision_depth_exceeded`; it does not produce a 222nd
model. The final trace state equals T28's durable counterexample. The trace
artifact raw SHA-256 is
`c56877975293c10575009a691b1d1bbde376838f805d232a2c18a4d00b2c4715`.

### FINITE SEPARATOR

The deterministic candidate pool has 83 atoms and reconstructs T28's 37-atom
final refinement pool before enrichment. The lexicographic optimum has one
clause, ten atoms, maximum width ten, coefficient support 22, absolute
coefficient sum 25, relation code 9, and modulus code 0. Direct replay passes
all `12/221/6` examples. The dataset raw SHA-256 is
`6603e381805db845ef9388d234e36f31eba510d838ac98c143c238c2ff144995`;
the certificate raw SHA-256 is
`1c234891f001cb3a59e5670560ab26e3cb248a943e249aee049aac7d32c7db5a`.

### SEMANTIC CHECK

The exact layer-31-to-32 successor query is SAT. Its lexicographically first
input inside the finite predicate is

`D0=5, D1=6, L0=0, L1=1, L2=1, L3=0, L4=1, L5=1, R0=0, R1=0, R2=1, R3=0, R4=0, R5=1`.

The full output and ten local digit values are serialized in the certificate.
All 12 original integer equations replay exactly. This witness is new evidence
that the compact conjunction captures a large finite pattern without being
the missing reachability condition.

### INDEPENDENT CHECK

The isolated standard-library checker imports no repository module. It
recomputes frozen source identities, checks the 221-step trace and
`12/221/6` dataset, evaluates the predicate directly on all 239 states, and
replays the complete SAT witness against the 12 serialized equations. It
rejects mutations to source digests, trace iterations, live controls,
predicate constants, and witness values. Its raw SHA-256 is
`9f926208cc7416e24d811f6cd54485d19741b6f8ffe44f3b365b2f816e579644`.

### PRISM AND RESEARCH

Math Prism was checked first but returned no usable artifact, so it supplied
no mathematical premise. CEGAR, symbolic-automata, and interpolation sources
motivated the falsifiable separator/preimage framing only: König et al.
<https://arxiv.org/abs/2504.08617>, D'Antoni, Kincaid, and Wang
<https://arxiv.org/abs/1610.01722>, and Cimatti, Griggio, and Sebastiani
<https://arxiv.org/abs/0906.4492>.

### STOP CONDITION

Semantic SAT is the approved stop. The finite grammar was not enlarged, and no
lower-layer extension, symbolic base lift, base-17/base-19 classification,
topology scan, publication change, or Lean work ran.

### LIMITATIONS

- The 221 counterexamples are solver-derived examples, not a complete
  characterization of all successor-bearing layer-31 states.
- The ten-atom predicate may still be useful as one component of a stronger
  reachable-state invariant, but T29 proves no such implication.
- The semantic witness falsifies universal deadness, not finite separation.
- No novelty or cross-base classification claim is made.

### NEXT

Use the new semantic witness as a positive counterexample to the separator and
ask for one additional predicate that is implied by exact earlier-layer
reachability, holds on the 12 promoted `DEAD` states, and excludes both the 221
trace models and this semantic leak. Stop if the added condition is merely a
state table or fails exact preimage replay. Only a semantic PASS should reopen
lower-layer extension or symbolic lifting in the base.
