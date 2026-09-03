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
4. **Novelty-check — MANDATORY before recording.** Turn the finding into
   something searchable (an integer sequence, a formula, a named object) and
   look it up: OEIS for sequences, web search for named theorems. Record the
   result in the `NOVELTY` field. This step is not optional and not a
   formality — it took 30 seconds on T13 and immediately (a) confirmed two
   results as published theorems, (b) revealed that published lower bounds for
   multiplicative persistence *exceed* what this arena found. Hedging a result
   as "probably classical" without checking is not honesty, it is laziness
   wearing honesty's clothes.
5. **Record.** Update `notebook/<slug>.md` using the schema below. This is the
   only part of the turn that matters after the turn ends.
6. **Log.** Append one line to `ledger.md`.

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
- **NOVELTY** — what the lookup found. One of: `published` (with the reference),
  `not found` (with the exact queries tried, so the next turn knows the search was
  shallow rather than the result new), or `superseded` (the literature is *ahead*
  of what this arena found — record their value).
- **NEXT** — one concrete action. Not "think harder" — an actual next step.
- **COST** — wall-clock and what was computed, so effort can be compared.

## Honesty rules

These exist because the failure mode of an autonomous math loop is producing
confident-sounding output that is wrong or vacuous.

1. **A conjecture is not "verified" because a search found no counterexample.**
   Say the range searched. `no counterexample for n < 10^8` is a fact;
   `probably true` is not a finding.
2. **Rediscovery is fine; claiming novelty is not — and *guessing* at either is
   also not.** Look it up. "Very likely classical" written five times without a
   single search is an untested assertion about the world, which is the same
   failure as reporting a search limit as a property of the problem. If a result
   is classical, name the reference. If the search found nothing, say what you
   searched.
3. **A counterexample must be independently re-verified** by a separate code path
   before it is recorded as one. Search code has bugs; that is the normal case.
4. **Record the dead ends.** A turn that found nothing must still write what it
   ruled out. Silence looks identical to "not attempted" to the next turn.
5. **Never delete a prior turn's finding to make room.** Contradict it explicitly
   if it was wrong, and say why.

## Cleaning up after yourself

On 2026-07-25 two arena jobs ran **4h21m** and **1h40m**, pinning a core each and
producing zero bytes, while the session had long moved on. The lesson recorded at
the time — *never cite a computation whose output you have not read* — fixed the
citation and did nothing about the process. Half a lesson.

Three layers now, so it cannot depend on remembering:

1. **Prefer foreground, reduced scope.** A validation that fits in one turn beats
   one that might not finish. A smaller verified range beats a larger unverified
   one — this is already the rule after T10, and it is also the cheapest way to
   never orphan anything.
2. **`Stop` hook → `bin/reap --report`.** After every turn, any arena process
   running past 5 minutes is named in a system message. Forgetting becomes
   visible instead of silent.
3. **`SessionEnd` hook → `bin/reap --kill`.** Nothing survives the session.

`bin/reap` is deliberately narrow: it only matches processes whose command line
references `.timeloop/runs/` **and** which belong to this repo (absolute path in
argv, or `cwd` under the repo). It cannot touch anything else. Verified against a
decoy outside the repo, which it correctly ignored.

Run it by hand any time: `.timeloop/bin/reap` lists, `--kill` reaps.

*(The cwd check exists because the first version matched only on argv and missed
relative launches — caught by the decoy test, not by reading the code. Testing
the janitor found a bug in the janitor.)*

## Choosing targets — what they forge, not what they teach

A person at a maths camp accumulates in their head; their kit is a convenience.
This arena's occupant resets between turns, so **the kit is the only thing that
carries**. That inverts how targets should be chosen.

Do not pick a target because the mathematics is interesting. Pick it for the
**capability it forces you to build**, and record that in the pool's `forges`
field. The theorem is the load; the technique is the product.

What the first six targets actually forged — none of it number theory:

- *tabulate the right invariant* — the answer was invisible until the discriminant
  sat beside the run length
- *reduce to a decidable family* — so results are theorems, not samples
- *group by a derived invariant*, not the raw parameter
- *exploit state-space collapse* — multiset instead of integer
- *sanity-check against a known value BEFORE trusting a method*
- *check the argmax against the search ceiling* — a maximiser pressed against the
  bound is not a record
- *reduce a search to the image of the map*
- *recognise a wall early and park with the reason*
- *reduce a conjecture to a sharper sub-question*; attack an intersection rather
  than filtering one set by the other

Every one of those would work on a biology dataset or a code review. That is the
test of whether a rep was worth doing.

## Tracks

**`open`** — known conjectures. Realistic goal is not to solve them but to retire
search space, find structure, and confirm ranges. Famous problems have been
searched far past what hours of compute reach; the honest contribution is
structural.

**`forge`** — conjectures the arena generates from its own computation, then
attacks. This is where a counterexample is actually likely, because nobody has
looked. A forged conjecture that survives scrutiny is a small real result; one
that breaks in ten minutes cost ten minutes.

## Running the room autonomously

`bin/research` runs turns back to back through headless Claude Code until
stopped. The dispatcher, not the model, chooses each turn: it rotates
angles before targets (a target gets at most three consecutive turns, each
with a different frame, the third with a frame it has never seen), parks a
target after three non-productive turns or three refinements, forages
online for new frames about one turn in five, combines productive frames,
re-verifies a prior claim every tenth turn, and re-checks novelty every
twenty-fifth.

```sh
bin/research --max-turns 3      # supervised batch
bin/research --max-hours 8      # overnight
bin/research status             # from another terminal
bin/research stop               # clean stop after the current turn
```

Every turn's brief is in `driver/briefs/`, its raw result in
`driver/results/`, and its record in `driver/turns.jsonl`. Frames live in
`frames.jsonl` and are written only by the recorder. `index.md` is the
one-line-per-target orientation the turn reads first; regenerate it with
`bin/lint --index`. The design is
`docs/superpowers/specs/2026-09-02-headless-research-driver-design.md`.

Start a run with the tree clean. The recorder commits only what a turn
changed, judged by file content, so a file that was already dirty and that
the turn also edits is committed whole, your pending edits included. Worse,
a dirty file *outside* the driver's write set that a turn touches is
reverted to HEAD, which would discard your work. So `bin/research` refuses
to start when anything is uncommitted outside that set: `ledger.md`,
`notebook/`, `pool.jsonl`, `lib/`, `runs/`, `tests/`, `lean/arena/`, and the
driver's own `driver/results/`, `driver/briefs/`, `driver/turns.jsonl`, and
`driver/lease.json`. Commit or stash anything else first. This refusal is
only a start-time check: if you edit a tracked file outside the driver's
write set while a run is already in progress, and a turn happens to touch
that same file, the recorder will revert it to HEAD and your edit is lost.

One Ctrl-C lets the current turn finish and then stops; a second kills the
turn. A failed `git commit` or a failing blind exam halts the run rather
than letting the damage compound into the next turn.
