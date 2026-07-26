# experiment-blind-vs-informed

Does prior knowledge help when attacking a formal statement, and when?

## STATUS
`resolved` — for the question asked. All four targets were out of reach, which is
itself the finding.

## DESIGN
Four `research solved` statements (known true, awaiting formalisation) drawn with
a **fixed seed from the 40 smallest**, arms shuffled — both *before* seeing any
difficulty signal. Two arms:

- **blind** — code only. Docstrings, comments and references stripped. No lookup.
- **informed** — full file including references, plus literature search allowed.

Two targets came from the same file with opposite arms, so the blind one had to
be completed first or it would be contaminated. It was.

## RESULT

| target | arm | verdict | what the arm contributed |
|---|---|---|---|
| `W 3 15 = 218` | blind | infeasible — SAT-scale | **nothing missing**; structure alone gave the verdict |
| `W 3 8 = 58` | informed | infeasible — same | a citation (Ahmed–Kullmann–Snevily 2014) and confirmation it was SAT-computed. **Nothing actionable.** |
| `F 3 = 7` | blind | multi-hour; `chromaticNumber` is an `sInf` over colourings, and the lower bound needs all `p ≤ 6` ruled out | **nothing missing** |
| `ExistsAME 5 2` | informed | needs an explicit 32-amplitude witness plus partial traces over tensor factors | **decisive** — told me a witness exists and what it is (the 5-qubit code). Blind I would not have known one existed at all. |

## THE FINDING

**Prior knowledge contributed nothing where the structure was readable, and the
decisive fact where the domain was unfamiliar.**

For the van der Waerden numbers, reading the definition
(`W k r = sInf { N | every 2-colouring of [1,N] has a 0-coloured k-AP or a
1-coloured r-AP }`) was enough to conclude: the upper bound quantifies over
`2^218` colourings, the lower bound is a finite witness, and this smells like
SAT. The informed arm confirmed exactly that and named the paper. Same verdict,
same reasoning, no advantage.

For AME states, the definition alone would have told me *what* to prove but not
*that it is provable* — the informed arm supplied the existence of an explicit
witness. In an unfamiliar domain the literature carries the thing structure
cannot: whether anyone has ever found the object.

**Rule extracted:** look it up when you cannot tell from the statement whether a
witness exists. Do not look it up to decide whether something is hard — you can
usually read that off the quantifiers.

## RULED OUT — and a repeat offence

All four targets are out of reach in a session. But the more useful negative:

**I selected by statement length again.** T12 established that statement size is a
bad tractability proxy — `BB_1`, `τ_two`, `P_subset_NP` are all short and hard.
I recorded that lesson, then built this experiment's selection on exactly that
proxy, and drew `W 3 15 = 218`: thirty characters, SAT-scale.

Knowing a heuristic is bad did not stop me using it, because it was the
convenient one available. That is a different failure from the day's others —
not a limit mistaken for a property, but a **known-bad shortcut reached for under
mild convenience pressure.**

## NEXT
A tractability proxy that is not length. Candidates, cheapest first:
1. **Quantifier shape** — a statement whose head is `∃` over a finite type is a
   witness hunt; one with `∀` over an infinite type is not. Mechanically
   extractable from the Lean syntax tree.
2. **Dependency depth** — how many local definitions the statement unfolds
   through. `W 3 15` bottoms out in `sInf` over colourings; `a 1 = 1` unfolds to
   a literal.
3. Whether mathlib already has the surrounding theory.

Only (1) and (2) are cheap. Both are better than counting characters.

## COST
~20 minutes. Zero proofs. One method result and one repeat offence, both durable.

## NOVELTY
`n/a` — this is an experiment about the arena's own process, not a mathematical
claim.
