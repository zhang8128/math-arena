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
