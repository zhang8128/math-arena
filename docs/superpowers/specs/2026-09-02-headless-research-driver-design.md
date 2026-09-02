# Headless Research Driver Design

**Date:** 2026-09-02
**Status:** Approved design (in-chat, Kairos); implementation not started
**Relation to prior designs:** This is the first driver lane for the time
loop room. It takes the place of the runner portion of
`2026-08-15-continuous-ollama-researcher-design.md` for now. That
document's Ollama lifecycle, local provider, and zero-dollar boundary are
deferred, not rejected; the dispatcher here is written so a local runner
backend can be added later without touching selection. Where the two
documents differ on run semantics, this one is authoritative.

## Purpose

One command runs the time loop room autonomously: it looks for ideas
online, tries papers, tries ideas, tries combinations of ideas, and never
stays on one thing for long. Like sudoku, when one angle stalls it changes
angle before it changes puzzle, and it changes puzzle before it grinds.

The thinking inside a turn comes from Claude Code running headless on the
operator's subscription. Selection of what to do next never comes from the
model. A small deterministic dispatcher owns it, so the anti-stuck rule is
code with tests, not a prompt instruction the model can drift from.

The room protocol in `.timeloop/README.md` is unchanged. A driver turn is a
room turn: orient, pull, attack, novelty-check, record, log. The driver
adds the parts the protocol assumed a human would supply: choosing the
next target and angle, noticing a stall, foraging for new angles, and
keeping the loop honest about its own yield.

## Scope

Included:

- `bin/research` at the repository root: preflight, lease, `caffeinate`,
  the continuous loop, and `status` / `stop` subcommands usable from another
  terminal;
- a pure, seeded dispatcher that selects turn kind, target, and frames,
  detects stalls, parks and revives targets, and enforces rotation;
- a turn runner that executes one brief through `claude -p` with a fixed
  tool allowlist, a wall-clock timeout, and a JSON result schema;
- a recorder that validates the result against what changed on disk,
  appends the turn log, runs lint and exam, reverts disallowed writes, and
  commits;
- a frames registry, the idea store that foraging fills and attack and
  combine turns draw from;
- a generated one-line-per-target index so turns orient without opening
  notebooks;
- a yield report;
- unit tests, integration tests against a fake `claude` binary, two new
  blind exam items, and a staged rollout with a numeric soak gate.

Excluded:

- the Ollama lane, SearXNG, and any local-model work;
- PostgreSQL, the production `mathloop` scheduler, and concurrency above one
  turn at a time;
- any change to the human publication gate; the driver never writes under
  `publication/`;
- pushes to any remote;
- model-authored commits.

## Components

Five units, each with one job. Code lives in `.timeloop/driver/` as a small
stdlib-only package beside the room's existing `bin/` and `lib/`. Production
`src/mathloop` is untouched.

| Unit | File | Job |
|---|---|---|
| entry | `bin/research` | preflight, lease, `caffeinate`, loop, `status`, `stop` |
| dispatcher | `.timeloop/driver/dispatcher.py` | choose the next turn from state and seed; write the brief |
| runner | `.timeloop/driver/runner.py` | run one brief through `claude -p`; enforce timeout; capture the result |
| recorder | `.timeloop/driver/recorder.py` | validate, log, lint, exam, revert, commit |
| index | `bin/lint --index` | regenerate `.timeloop/index.md` |

`status.py` computes the yield report from the turn log and is shared by
`bin/research status` and an exam item.

### Dispatcher

A pure function `select(state, config, turn_index) -> Brief`. `state` is
the pool, the frames registry, the turn log, and the ledger tail, all read
from disk before the call. Randomness comes from
`random.Random(f"{seed}:{turn_index}")`, so the choice for a given turn is
a function of the files and the configuration and nothing else. Replaying
a run with the same files reproduces the same briefs.

The dispatcher writes `.timeloop/driver/briefs/<turn_id>.md` and returns
the brief record. It never runs a model and never touches the network.

### Runner

Runs exactly:

```text
claude -p --output-format json --json-schema <result schema> \
  --permission-mode bypassPermissions \
  --allowedTools Bash Read Write Edit Glob Grep WebSearch WebFetch \
  --no-session-persistence [--model M] [--effort E] \
  --append-system-prompt-file .timeloop/driver/templates/system.md \
  < brief
```

The runner enforces the 30-minute turn timeout itself, with SIGTERM then
SIGKILL, because the model's own budget is advisory. It captures stdout,
stderr, exit code, and wall-clock seconds to
`.timeloop/driver/results/<turn_id>.json`. It parses the structured result
if the process exited cleanly and the output validates; otherwise it
returns an `invalid` result with the reason.

### Recorder

Before the turn the recorder snapshots `git status --porcelain`. After the
turn it computes the delta: files that appeared, changed, or vanished
during the turn. Pre-existing uncommitted changes are never touched. This
matters because the working tree is routinely dirty with human work in
progress.

On the delta the recorder:

1. reverts any path outside the allowed write set (below) and always
   reverts anything under `publication/`;
2. checks that a productive outcome class is backed by a new ledger line
   beginning with the turn id, otherwise downgrades the outcome to
   `invalid` with reason `no_ledger_line`;
3. checks that files named in `files_changed` match the delta, otherwise
   downgrades to `invalid` with reason `files_mismatch`;
4. appends filed frames to `frames.jsonl` after validating each against the
   frame schema and rejecting duplicate slugs;
5. runs `bin/lint --report` and `bin/exam --report`; a lint failure
   downgrades the outcome to `invalid` with reason `lint`; an exam failure
   is recorded on the turn and halts the run, since a failing instrument
   means later verdicts cannot be trusted;
6. runs `bin/reap --kill`;
7. regenerates `index.md`;
8. appends one line to `.timeloop/driver/turns.jsonl`;
9. stages only the delta paths that survived step 1 plus the driver's own
   files for this turn, and commits with message
   `turn: <turn_id> <kind> <target> <outcome>`.

An invalid turn is still committed, so the turn log and git history never
disagree. Its brief and raw result stay on disk.

Allowed write set for a turn: `.timeloop/ledger.md`,
`.timeloop/notebook/`, `.timeloop/pool.jsonl`, `.timeloop/lib/`,
`.timeloop/runs/`, `.timeloop/tests/`, `.timeloop/lean/arena/`, and
`.timeloop/driver/results/`. Frames are filed through the result JSON, not
by writing `frames.jsonl` directly, so the recorder is the only writer of
the registry and the turn log.

### Index

`bin/lint --index` writes `.timeloop/index.md`: one line per pool target
with slug, status, a one-line summary of RULED OUT, and the current NEXT,
all extracted from the notebook. Targets without a notebook get their pool
`statement` truncated. Lint flags a pool target with no `tags` field, since
the dispatcher needs tags to match frames.

## Turn kinds

Six kinds. Shares are configuration; the defaults are below.

| Kind | Selection | What the turn does |
|---|---|---|
| attack | remainder | one target, one frame, bounded compute, record what it ruled out or found |
| combine | 15% | one target, two frames that have each been productive somewhere and have not been paired on this target; the brief asks for the interaction, not two attacks |
| forage-target | 10% | web search for methods matching a stalled or underused target's shape; file frames with sources |
| forage-frontier | 10% | read recent arXiv listings in configured categories; file transplantable methods as frames, target optional |
| adversarial | every 10th turn | pick a prior productive ledger claim, least recently re-verified first, and try to break it with an independent code path |
| patrol | every 25th turn | re-run recorded NOVELTY queries for the oldest-checked targets plus all parked and superseded ones; append corrections |

Forging conjectures is not a separate kind. An attack or combine turn may
end by adding a forge-track record to the pool, which is how the forge
track already works.

Scheduled kinds are checked first by turn index. When both fall on the same
index, patrol wins and adversarial fires on the next turn.

## Outcome classes

Every turn ends in exactly one class, reported by the model in the result
JSON and then checked by the recorder against the disk delta.

| Class | Meaning | Productive |
|---|---|---|
| negative | ruled something out with a stated range | yes |
| structure | a transferable insight recorded under STRUCTURE | yes |
| correction | overturned a prior recorded claim, with the reason | yes |
| verified | an adversarial turn re-derived a prior claim independently, with stated range | yes |
| counterexample | independently re-verified by a second code path before recording | yes |
| frames | a forage turn filed at least one new frame with a source | yes |
| nothing | ran, found nothing, wrote what was tried | no |
| invalid | schema failure, timeout, lint failure, missing ledger line, or a disallowed write | no |

`verified` was added after the in-chat approval of the class list so that
an adversarial turn that confirms a claim is not forced to report
`nothing`. It counts toward yield but never toward a target's stall count,
because confirming old work is not progress on the target.

A productive class also carries `refinement: true|false`. Refinement means
the ledger line only sharpens a fact an earlier line already stated, for
example a larger range for the same negative. The model sets it and the
brief defines it; the recorder cannot check it and does not try.

## Selection and the sudoku rule

### Stall

A target is stalled when, over its last three attack or combine turns:

- all three were non-productive, or
- all three were productive with `refinement: true`.

Forage, adversarial, and patrol turns never count toward a stall. A stalled
target is parked: the dispatcher writes `status: parked` and a
`parked_reason` into its pool record with the three turn ids, and sets
`cooldown_until` to the current turn index plus 20. A parked target becomes
eligible again after the cooldown only with a frame it has not seen.

Parking is a dispatcher action, not a model action. The model may also park
a target during a turn by writing STATUS `parked` with a reason, which the
dispatcher honours the same way.

### Angle first

Consecutive turns on one target must use different frames. The third
consecutive turn on a target must use a frame that has never been applied
to it. No target receives a fourth consecutive turn; the rotation cap is
three, and a concrete NEXT does not override it. After rotation the target
is eligible again on the next selection.

A frame is eligible for a target when the frame's `shape` tags intersect
the target's `tags`, or the frame carries the tag `*`. A frame already
applied to a target with a productive outcome is eligible again only
through combine or after a correction turn on that target.

### Order of selection

1. If the turn index is a multiple of 25, patrol. Else if a multiple of
   10, adversarial.
2. Otherwise draw the kind by share.
3. Within attack: with probability 0.2 draw uniformly from all eligible
   targets (the exploration floor); otherwise prefer, in order, a target
   whose notebook NEXT is concrete and whose last turn was productive, then
   the eligible target with the fewest driver turns, then a parked target
   whose cooldown has expired. Ties break by seeded draw.
4. Within combine: choose a target as in step 3, then two frames that each
   have at least one productive application anywhere, are both eligible for
   the target, and have not been paired on it. If no such pair exists, the
   turn becomes an attack.
5. Within forage-target: choose the most recently parked target, else the
   target with the fewest eligible frames.
6. Within forage-frontier: choose a category by rotation through the
   configured list.

The exploration floor guarantees that no single target absorbs the loop
even when it keeps producing.

## Data

All new files live under `.timeloop/`.

### `frames.jsonl`

Append-only registry of ideas. One JSON object per line:

```json
{
  "slug": "carry-transducer-frontier",
  "title": "Treat reverse-and-add as a finite carry transducer and eliminate radially",
  "statement": "One paragraph. What the method does, what shape of problem it fits, what it produces.",
  "shape": ["digit-dynamics", "finite-automata", "csp"],
  "source": {"kind": "arxiv", "id": "2504.08617", "url": "https://arxiv.org/abs/2504.08617"},
  "filed_by": "T31",
  "applied_to": [{"target": "lychrel-bases", "turn": "T33", "outcome": "negative"}],
  "superseded_by": null
}
```

`source.kind` is one of `arxiv`, `doi`, `oeis`, `web`, `pool`, `own`.
`pool` marks the one-time seeding from the pool's existing `forges`
entries, done by hand during implementation. `own` marks a frame the loop
derived from its own STRUCTURE field. Every other kind requires a URL.
Duplicates are never deleted; a later frame that subsumes an earlier one
sets `superseded_by` on the earlier record through a correction turn.

The recorder is the only writer. `applied_to` is appended by the recorder
after every attack or combine turn that used the frame.

### Pool additions

Each pool record gains `tags: [...]`, a list of shape tags in the same
vocabulary as frames. Lint flags records without tags. Parked records gain
`parked_reason`, `parked_turns`, and `cooldown_until`.

### `driver/turns.jsonl`

One line per turn, the ground truth for yield and stall detection:

```json
{
  "turn_id": "T31",
  "kind": "attack",
  "target": "lychrel-bases",
  "frames": ["carry-transducer-frontier"],
  "outcome": "negative",
  "refinement": false,
  "ledger_line": "T31 | lychrel-bases | ...",
  "files_changed": [".timeloop/ledger.md", ".timeloop/notebook/lychrel-bases.md", ".timeloop/runs/t31_probe.py"],
  "frames_filed": [],
  "started": "2026-09-03T02:14:09Z",
  "seconds": 1043.2,
  "base_commit": "abc1234",
  "exit_reason": "completed",
  "invalid_reason": null,
  "brief_digest": "sha256:...",
  "template_digest": "sha256:..."
}
```

`exit_reason` is one of `completed`, `timeout`, `nonzero_exit`,
`schema`, `interrupted`. `base_commit` is HEAD before the turn's commit;
the record cannot hold its own commit hash because writing the hash would
change the commit. The turn's commit is the child of `base_commit` whose
message begins with `turn: <turn_id>`. Lines in the turn log that carry an
`event` field instead of `turn_id` are run events (`halt`, `lease_expired`,
`interrupted`) and are skipped when computing yield. `turn_id` continues the ledger's `T<n>`
numbering: the dispatcher takes one plus the largest `T<n>` present in
either the ledger or the turn log. The ledger line a productive turn
appends must begin with that id.

### `driver/briefs/<turn_id>.md` and `driver/results/<turn_id>.json`

The exact prompt each turn received and the raw process capture. Both are
committed with the turn so any turn can be replayed by hand.

### `driver/lease.json`

`{"pid", "started", "seed", "heartbeat", "turn_id"}`. Written at start,
heartbeat refreshed at every turn boundary. Removed on clean exit.

### `driver/config.json`

Shares per kind, rotation cap, stall window, cooldown, exploration floor,
patrol and adversarial periods, arXiv categories (default `math.NT`,
`math.CO`, `cs.LO`), turn timeout, model, effort, tool allowlist, and
seed. Every value has a default in code; the file overrides.

### `index.md`

Generated by `bin/lint --index`. One line per target. Not hand-edited.

## The brief

About one page. Assembled from a versioned template at
`.timeloop/driver/templates/brief.md`, whose digest is recorded on the
turn. It contains, in order:

1. the turn id, kind, and the rules for that kind;
2. the target's pool record and its `index.md` line;
3. the last three ledger lines mentioning the target;
4. the chosen frames in full, or for forage turns the search intent;
5. the outcome-class definitions and the definition of refinement;
6. the result JSON schema;
7. the room's honesty rules and novelty-check rule, verbatim from the
   README;
8. the allowed write set, the rule that the ledger line must begin with the
   turn id, the 30-minute budget, and the rule to prefer a smaller verified
   range over a larger unverified one.

It does not contain the notebook. It tells the model the notebook path and
that opening it is allowed when the index line is not enough.

The system prompt file `.timeloop/driver/templates/system.md` states that
the session is one amnesiac turn of the time loop room, that git is not to
be used, that nothing outside the allowed write set may be written, and
that a long computation is recorded as NEXT rather than run.

### Result schema

```json
{
  "type": "object",
  "required": ["outcome", "refinement", "ledger_line", "files_changed", "frames_filed", "next_action", "notes"],
  "properties": {
    "outcome": {"enum": ["negative", "structure", "correction", "verified", "counterexample", "frames", "nothing"]},
    "refinement": {"type": "boolean"},
    "ledger_line": {"type": ["string", "null"]},
    "files_changed": {"type": "array", "items": {"type": "string"}},
    "frames_filed": {"type": "array", "items": {"$ref": "#/$defs/frame"}},
    "$comment": "frame is the frames.jsonl record without filed_by, applied_to, or superseded_by; the recorder fills those",
    "next_action": {"type": ["string", "null"]},
    "notes": {"type": "string"}
  }
}
```

`invalid` is never self-reported; only the recorder assigns it.

## Safety and limits

**Per turn.** Thirty minutes wall clock, enforced by the runner.
Tool allowlist as above; no MCP servers; `--no-session-persistence`. Git is
denied by the system prompt and made moot by the recorder's delta logic.
Writes outside the allowed set are reverted. `publication/` is always
reverted. No pushes.

**Per run.** One lease. A second `bin/research` refuses to start while a
live lease exists. A lease whose heartbeat is older than 45 minutes is
stale; the next start expires it, records a `lease_expired` line in the
turn log, and proceeds. `--max-hours` and `--max-turns` are clean halts.
`caffeinate -i` wraps the loop. First SIGINT or SIGTERM lets the current
turn finish and records it, or records it as `interrupted` if the runner's
timeout fires first, then exits 0. A second signal kills the child and
exits.

**Circuit breaker.** Five consecutive `invalid` turns halt the run with a
`halt` line in the turn log and a nonzero exit. A usage-limit or
authentication error from `claude` halts immediately, since retrying only
burns the window. A single timeout is `invalid` but does not halt by
itself. A failing exam halts.

**Orphans.** `bin/reap --kill` runs after every turn. The Stop and
SessionEnd hooks in `.claude/settings.json` are unchanged and also fire
inside each headless session.

**Web.** Only the turn touches the network, through Claude Code's own
WebSearch and WebFetch. The runner and dispatcher never do. Every filed
frame must carry a source URL or identifier; the recorder rejects a frame
without one.

## Yield

`bin/research status` prints lease state, current turn id, kind, target,
and frames, elapsed time in the current turn, and productive share over
the last 10, the last 50, and all turns, broken down by kind. The same
numbers are the soak gate.

## Testing

**Unit, no model.** The dispatcher is a pure function of state and seed,
so each rule is a table-driven test:

- consecutive turns on a target use distinct frames; the third is fresh;
- no fourth consecutive turn on a target, even with a concrete NEXT;
- three non-productive turns park the target with the three ids recorded;
- three productive refinements park the target;
- forage, adversarial, and patrol turns never count toward a stall;
- cooldown expires at exactly 20 turns and revival requires an unseen frame;
- patrol fires at every multiple of 25, adversarial at every other
  multiple of 10, and a collision defers adversarial by one;
- the exploration floor holds within tolerance over 1,000 seeded draws;
- combine never repeats a pair on a target and degrades to attack when no
  pair exists;
- the same files and seed reproduce the same brief byte for byte.

The recorder is tested with fixture results and a temporary git
repository: each outcome class, downgrade to `invalid` for a missing ledger
line and for a files mismatch, revert of a write outside the allowed set,
revert under `publication/`, preservation of pre-existing dirty files, a
lint failure, duplicate frame slugs, and the commit message format.

**Integration, fake `claude`.** A stub binary placed first on PATH replays
canned JSON results and can sleep past the timeout, exit nonzero, print a
usage-limit error, or write a forbidden file. Tests cover the circuit
breaker at exactly five, the usage-limit halt, `--max-turns` and
`--max-hours` halts, lease contention, stale-lease expiry recorded once,
SIGINT during a turn, and agreement between the turn log and `git log`
after a run.

**Exam.** Two blind items in `.timeloop/exam/items.py`: the yield numbers
recomputed from `turns.jsonl` by an independent one-liner must equal the
`status` output, and a seeded 200-turn dispatcher simulation must never
place more than three consecutive turns on one target.

## Rollout

Gates in order. Each must pass before the next starts.

1. Offline suite green; `ruff` and `mypy` clean on the driver package.
2. One real turn by hand: `bin/research --max-turns 1`, with the operator
   reading the brief, the result, and the diff.
3. A supervised three-turn batch, `--max-turns 3`, that must include one
   forage turn; the operator reads every filed frame.
4. A two-hour supervised soak. The gate is numeric: at least one
   productive turn per five attempted, and zero `invalid` turns caused by
   runner bugs. Invalid turns caused by the model are reviewed but do not
   fail the gate.
5. First unattended overnight run, `--max-hours 8`.

## Open questions resolved

- Where does the driver code live? `.timeloop/driver/`, stdlib only,
  beside the room's existing tools. Production `mathloop` is not touched.
- Who numbers turns? The dispatcher, continuing the ledger's `T<n>` series.
- Who writes `frames.jsonl`? Only the recorder, from the result JSON.
- What if the working tree is dirty? The recorder acts only on the delta
  created during the turn, judged by content hash rather than git status
  code. A dirty file the turn does not touch is never staged or reverted. A
  dirty file the turn does edit, such as an uncommitted ledger, is committed
  whole with the turn, pending edits included; `bin/research` warns about
  dirty paths under `.timeloop/` before starting. The dispatcher's own
  writes (parking, the brief) are committed with the turn but are not held
  against the model in the files-changed check, which is why the recorder
  takes one snapshot before the dispatcher acts and one right before the
  model starts.
- What if a turn needs hours of compute? It records the plan as NEXT and
  stops. The room rule stands: a smaller verified range beats a larger
  unverified one.
