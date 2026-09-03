# rh-turing-golf — reduce the 744-state RH Turing machine

Target: a small 2-symbol TM that halts iff RH is false. Committed record in
`sorear/metamath-turing-machines` is **744 states**
(`machines/2016-riemann-matiyasevich-aaronson-744/`, Matiyasevich + Aaronson,
compiled from 54 lines of NQL).

- **STATUS** — open (one candidate reduction built and internally verified;
  novelty NOT settled — see NOVELTY, which is the blocking item)

## What the 744-state machine actually computes (T27)

Decoded from `riemann.nql`. Registers are non-negative integers; `-` is **monus**
(clamps at 0) and `/` is floor division.

| program fragment | meaning |
|---|---|
| inner `while (lcm != (lcm/l)*l \|\| lcm != (lcm/x)*x)` | `lcm = L := lcm(1..x)`, found by incrementing one at a time |
| `while (i <= lcm) { num = num*i + denom; denom = denom*i; ... }` | `num/denom = H_L` exactly, as a fraction (`denom = L!`) |
| `while (i <= x)  { c = c*i + d;       d = d*i;         ... }` | `c/d = H_x` exactly |
| `a = num - denom*x; a = a*a; b = denom*denom` | `a/b = ((H_L - x)_+)^2` — monus already took the positive part |
| `c = c*c; c = c*c*x; d = d*d; d = d*d` | `c/d = x * H_x^4` |
| `if (a*d > b*c)` | **halt iff `H_L - x > sqrt(x) * H_x^2`** |

Since `L = lcm(1..x) = e^{psi(x)}` and `H_L = log L + gamma + O(1/L)`, the halt
test is `psi(x) + gamma - x > sqrt(x) * H_x^2`, i.e. a Schoenfeld-style criterion:
RH implies `|psi(x) - x| < (1/8pi) sqrt(x) log^2 x` for `x >= 73.2`, and RH false
implies `psi(x) - x = Omega_+(x^Theta)` for some `Theta > 1/2`. The squaring on
both sides is there to avoid a square root, **not** to take an absolute value —
the monus already discarded the negative branch, and Landau's oscillation theorem
(`Omega_+`) is what makes the one-sided test sound.

- **SEARCHED** — (1) Reproduced the build: toolchain pinned at HEAD
  `0b8032c35bfb2107d94023f6ca2c2ffe6067faa8`, compiled `riemann.nql`, got a
  **byte-identical** 744-line `.tm` (sha256 prefix `de0084433909`). Compile time
  0.08 s, so differential recompilation is a free measuring instrument.
  (2) Attributed all 744 states by name prefix. (3) Differential ablation table
  below. (4) Compiled 4 variants of the threshold function. (5) Verified the
  variant's predicate by an independent statement-level re-execution under NQL
  semantics for `x = 1..12` (bounded by `L = lcm(1..12) = 27720`, the machine's
  own loop length), and range-checked `k >= H_x` for `4 <= x <= 10^7`.

## STRUCTURE

**(a) Where the 744 states live** — by state-name prefix in `riemann.tm`:

| region | states | what it is |
|---|---|---|
| `main()` | 488 | the BDD-compressed dispatch tree over the program counter (11 bits) |
| `transfer(...)` | 194 | one subroutine per **distinct** (src, dst...) register-move signature |
| `dispatch`/`reg_incr`/`reg_decr`/`dec`/`inc`/`return`/`init`/`noop` | 62 | fixed runtime |

**(b) Marginal state cost, measured by deleting a construct and recompiling**
(`runs/t27_rh744_state_inventory.py`; the ablated programs are cost probes, they
do **not** decide RH):

| construct removed | states | delta |
|---|---|---|
| — (baseline) | 744 | |
| `lcm` incremental search | 620 | **−124** |
| `H_x` loop | 692 | −52 |
| final squarings `c=c*c; ...` | 692 | −52 |
| `H_L` loop | 696 | −48 |
| `if (x > 253)` guard | 743 | **−1** |

The point of the table is the ranking, and it is not the source-line ranking:
the RH-specific guard costs **1 state**; the humble `lcm` search costs **124**,
more than the two harmonic loops combined. State count after BDD compression is
uncorrelated with source size, so no golf proposal can be ranked by reading it.

**(c) The knife-edge forbids the cheap threshold.** The obvious golf is to
replace `sqrt(x)*H_x^2` with a monomial `x^r`, `r > 1/2`, deleting a whole loop.
It is **wrong**, not merely weaker: if the supremum `Theta` of real parts of
off-line zeros satisfies `1/2 < Theta < r`, the oscillation `Omega_+(x^Theta)`
never reaches `x^r` and the machine fails to halt although RH is false. Since
`Theta` is unknown and may be `1/2 + eps`, the threshold must be
`sqrt(x) * F(x)` with `log^2 x << F(x) << x^{o(1)}`: **`F` must be
sub-polynomial**. This is the same zero-slack phenomenon `riemann-frames.md`
records across all ten RH frames ("RH exactly critical with zero slack"), now
appearing as a *descriptive-complexity* constraint: the state count cannot be
bought down past the point where the threshold stops being sub-polynomial.

**(d) The frame combine.** `sharper-subquestion` says a halting witness must
satisfy two conditions at once — a large positive `psi(x)-x` excursion **and**
clearing a knife-edge-at-exponent-1/2 threshold — and (c) is what that
intersection rules out: it prunes the candidate threshold menu down to
`sqrt(x) * (sub-polynomial)`. `tabulate-the-right-invariant` supplies the only
thing that can rank the survivors, since (b) shows source reading cannot.
Neither frame reaches the result alone: the sub-question frame alone proposes
`x^{3/5}` and produces a machine that is *incorrect*; the tabulate frame alone
prices a fixed program with no legal substitution to price.

The cheapest surviving `F` found: `F(x) = k^2` with `k = bit_length(x)`, computed
by a halving loop. It replaces the `H_x` fraction (two registers, two
multiplications per iteration) with an integer (one register, one division).

## The candidate: 683 states

`runs/t27_riemann_bitlen.nql`, sha256 prefix `70ed7bfae06d`, compiled with the
same pinned toolchain. Halt test `(H_L - x)^2 > x * k^4`, i.e.
`H_L - x > sqrt(x) * k^2`. Register file drops from 10 globals to 8 (`b` folded
into the comparison, `i` reused as the shift temporary, `d` eliminated).

| machine | states |
|---|---|
| committed 744 | 744 |
| bitlen, 10 globals | 688 |
| bitlen, `b` folded, 9 globals | 691 |
| bitlen, `b` folded + `l` as temp, 8 globals | 685 |
| **bitlen, `b` folded + `i` as temp, 8 globals** | **683** |

Note the non-monotonicity: folding `b` alone *costs* 3 states (688 → 691) and
only pays once a register also leaves the file. Another instance of (b).

**Correctness argument (both directions).**
`k = floor(log2 x) + 1 > log x / log 2` and `H_x <= log x + gamma + 1/(2x)`, so
`k > H_x` for all `x >= 5` — checked with no failures for `4 <= x <= 10^7`,
tightest margin `0.407` at `x = 7`. Hence `sqrt(x) k^2 >= sqrt(x) H_x^2`: the
variant is **strictly harder to trip** than the 744 machine at every `x`, so
- RH true `=>` 744 never halts `=>` 683 never halts (the `x > 253` guard is
  inherited unchanged, which is the only part of the original's soundness that
  depends on small `x`);
- RH false `=>` `psi(x) - x = Omega_+(x^Theta)`, `Theta > 1/2`, while
  `sqrt(x) k^2 = O(sqrt(x) log^2 x) = o(x^Theta)`, so 683 halts.

**Independent check** (`runs/t27_verify_bitlen.py`): the NQL statement list was
re-executed under exact integer monus/floor-div semantics for `x = 1..12` and
agreed with the closed forms `(H_L-x)^2 > x H_x^4` and `(H_L-x)^2 > x k^4`
(computed with `Fraction`) at every `x`, and `bitlen-halt => original-halt` held
at every `x`. **Limits of this check, stated plainly:** it validates the
*algebra of the source*, not the *compiler*. The generated Turing machine itself
was NOT executed — the built-in `--run-tm` executor did not finish a probe in
2 minutes, and the real machine's first test is at `x = 254` with
`L = lcm(1..254)`, so direct execution is not available at any budget. The
compiler is trusted here because it reproduces the committed 744 machine
byte-for-byte.

## RULED OUT

- **Monomial thresholds `x^r`, `r > 1/2`, are not a legal golf** for this machine
  family, at any state saving. Reason in STRUCTURE (c). This closes the most
  obvious ~50-state saving permanently; do not re-propose it.
- **The `x > 253` guard is not a golf target**: it costs 1 state. Any effort
  spent tightening or removing the small-`x` bound buys at most 1 state and
  risks soundness.
- **The two harmonic loops are not the dominant cost.** `H_L` = 48 states,
  `H_x` = 52 states; the `lcm(1..x)` incremental search alone is 124. A golf
  program that only attacks the RH criterion is attacking a minority of the
  budget.

## TECHNIQUE

- The compiler is a free measuring instrument: 0.08 s per compile means an
  ablation table over a whole program costs seconds. Any golf target with a
  compiler should be inventoried this way **before** any hand analysis.
- Reproduce-then-diff: byte-identical reproduction of the committed artifact is
  what licenses trusting the compiler for the variant. Do this first.
- `--run-tm` is unusable for these machines (no probe finished in 2 min);
  verification has to be at the source-semantics level.
- Cost: ~30 min wall clock, ~20 compiles, all sub-second.

## NOVELTY — **unresolved, and this is the blocking item**

- The 744 machine is `published`: Yedidia–Aaronson, *A Relatively Small Turing
  Machine Whose Behavior Is Independent of Set Theory*, arXiv:1605.04343 (the
  5372-state original); the 744-state version is Matiyasevich + Aaronson +
  O'Rear, committed at
  `machines/2016-riemann-matiyasevich-aaronson-744/`.
- Searched: `bbchallenge smallest Turing machine Riemann Hypothesis 744 states
  record` and `"Riemann" Turing machine states 744 636 O'Rear improvement`.
  The **first** search's summary asserted "known further improvements to 636
  states, and even 432 states, pending verification". The **second**, targeted
  at exactly that, found no source for 636; and 432 is the state count of the
  *Goldbach* machine in this same repository
  (`machines/2016-goldbach-yedidia-432/`), so that half of the claim is very
  likely a conflation by the search summariser.
- **Therefore: do NOT claim 683 as a record.** What is established is that 683
  beats the smallest *committed* Riemann machine in the canonical repository at
  pinned HEAD `0b8032c`, which is the artifact the target names. Whether the
  bbchallenge community has gone below 744 is unverified.

## NEXT

1. **Settle the record before anything else.** Fetch
   `https://wiki.bbchallenge.org/` search for "Riemann", and the
   bbchallenge Discord/forum archive, for any Riemann machine below 744.
   Stop condition: if a machine below 683 exists, the variant is `superseded`
   and this notebook says so; if not, submit
   `runs/t27_riemann_bitlen.nql` as a new `machines/` subdirectory per the
   repo README (new machine = new subdirectory).
2. Attack the **`lcm` incremental search (124 states)**, the actual cost centre,
   which T27 did not touch. It increments `lcm` by 1 until divisible by both
   `l` and `x` — the `|| ` in that condition compiles to a second full
   divisibility test. Ablation to price: replace the two-clause test with
   `lcm != (lcm/(l*x/gcd))*...`, or restructure so `lcm` is multiplied by the
   prime-power part of `x` instead of searched. Time is free in this machine, so
   any construction is admissible; only states count.
3. Re-run the variant menu against `F(x) = k^3` and `F(x) = k*k` with `k` the
   base-3 or base-4 length (fewer loop iterations, same register shape) — the
   `c=c*c; c=c*c*x` chain is 52 states and may itself be shortenable now that
   `F` is an integer rather than a fraction.

## COST

~30 min wall clock. 1 reproduction (byte-identical), ~20 compiles (0.08 s each),
1 state-name attribution, 1 five-row ablation table, 4 variant compiles,
2 verification runs (`x <= 12` exact-fraction predicate check; `k >= H_x` over
`4 <= x <= 10^7`), 2 web searches.
