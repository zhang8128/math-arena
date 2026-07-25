# The Time Loop Room

An arena for attacking many mathematical conjectures across bounded, amnesiac turns.

## The premise

A turn does not remember the turn before it. Everything that survives lives in
this directory. So the measure of a good turn is not "did it make progress" but
**"did it leave the next turn smarter than it found it."**

That is a harder bar than it sounds, and it is the whole point. A turn that
spends four hours confirming `n^2+n+41` is composite at `n=40` and writes down
`false, witness n=40` has consumed real compute and left nothing reusable — the
next turn could have guessed that. A turn that writes down *"this family is
exhausted: full prime runs correspond to class-number-1 discriminants, and 163
is the largest, so stop searching"* has permanently retired a search space.

**Verified outcomes are what a ledger holds. Reusable structure is what a loop
needs.** This directory holds the second kind.

## Layout

```
pool.jsonl          the conjecture pool — what can be pulled
notebook/<slug>.md  durable findings, one file per target
ledger.md           append-only turn log: what was attempted, what changed
lib/                reusable search code, verified once and reused
runs/               raw compute output, referenced from the notebook
```

## What a turn does

1. **Orient.** Read `ledger.md`'s tail and `pool.jsonl`. Do not read every
   notebook file — read the ones for targets you are considering.
2. **Pull.** Choose a target. The selection heuristic is in `pool.jsonl`'s
   `priority`, but override it when the ledger suggests something better.
   Prefer a target with a concrete `next_action` from a prior turn over a cold
   start — resuming is cheaper than beginning.
3. **Attack.** Bounded compute. Write search code into `lib/` if it is reusable;
   throwaway probes go in `runs/`.
4. **Record.** Update `notebook/<slug>.md` using the schema below. This is the
   only part of the turn that matters after the turn ends.
5. **Log.** Append one line to `ledger.md`.

## Notebook schema — every entry must carry these

A finding is only durable if the next turn can *act* on it without redoing the
work. Each notebook file carries:

- **STATUS** — `open` | `counterexample` | `resolved` | `exhausted` | `parked`
- **SEARCHED** — exactly what space was covered, precisely enough that the next
  turn knows not to re-walk it. "n up to 10^7, all residues mod 9" not "searched a lot".
- **RULED OUT** — what the answer cannot be, and the reason. Negative results are
  the highest-value thing a loop produces, because they are what nobody bothers
  to write down.
- **STRUCTURE** — mathematical insight that transfers to other targets. This is
  the field that makes the arena more than parallel brute force.
- **TECHNIQUE** — what worked, what failed, and the cost. So the next turn picks
  a better tool.
- **NEXT** — one concrete action. Not "think harder" — an actual next step.
- **COST** — wall-clock and what was computed, so effort can be compared.

## Honesty rules

These exist because the failure mode of an autonomous math loop is producing
confident-sounding output that is wrong or vacuous.

1. **A conjecture is not "verified" because a search found no counterexample.**
   Say the range searched. `no counterexample for n < 10^8` is a fact;
   `probably true` is not a finding.
2. **Rediscovery is fine; claiming novelty is not.** If a result is classical,
   name it. The arena's value is the search space it retires, not credit.
3. **A counterexample must be independently re-verified** by a separate code path
   before it is recorded as one. Search code has bugs; that is the normal case.
4. **Record the dead ends.** A turn that found nothing must still write what it
   ruled out. Silence looks identical to "not attempted" to the next turn.
5. **Never delete a prior turn's finding to make room.** Contradict it explicitly
   if it was wrong, and say why.

## Tracks

**`open`** — known conjectures. Realistic goal is not to solve them but to retire
search space, find structure, and confirm ranges. Famous problems have been
searched far past what hours of compute reach; the honest contribution is
structural.

**`forge`** — conjectures the arena generates from its own computation, then
attacks. This is where a counterexample is actually likely, because nobody has
looked. A forged conjecture that survives scrutiny is a small real result; one
that breaks in ten minutes cost ten minutes.
