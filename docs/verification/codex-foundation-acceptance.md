# Codex Supervisor Foundation Acceptance

Evidence recorded on 2026-07-24/25 from the `worktree-codex-foundation`
worktree (branch base `689fe6e`) on macOS arm64 with Python 3.13.
`OPENAI_API_KEY`/`CODEX_API_KEY` were absent from the test process
throughout, and the offline suite never contacts a real Codex or OpenAI
endpoint.

This document covers Task 8 of
`docs/superpowers/plans/2026-07-23-codex-supervisor-foundation.md`: the
end-to-end verification of the complete Codex path (policy/accounting types,
JSONL event parsing, disposable worktree isolation, the transactional turn
ledger, the supervised CLI client, the Codex proof-strategy method and
scheduling, and the runtime composition/operator commands built in Tasks
1-7), plus the credit-consuming canary gate. It reflects the state after two
review rounds and their fixes (see "Fix round 1" and "Fix round 2" below) —
a prior version of this document, superseded, described a design where
every `thread.started` event was assumed to carry `cli_version`; direct
inspection of the real, installed Codex CLI (0.145.0) found this assumption
false, and the fix sections below record exactly what changed as a result.
Fix round 1's own I2 fix (asserting `"ChatGPT" in login_detail`) was itself
found inert in round 2 — see that section for why, and for the actual fix.

## Offline end-to-end coverage

`tests/e2e/test_codex_canary.py::test_codex_supervisor_foundation_offline_end_to_end`
drives every real component except the genuine Codex CLI (stood in for by a
small fake script that itself enforces authentication, forbidden-API-key
absence, and `--output-schema` file honesty, rather than merely emitting
plausible JSONL): a real, session-scoped PostgreSQL, the real calibration
corpus, the real production method-registration entry point
(`register_baseline_methods`), a real disposable git worktree, a real
fork-boundary process/pipe, and the real transactional turn ledger.

It proves, against persisted database rows rather than in-memory objects:

1. **Real PostgreSQL** — `repository.ping()` succeeds against the real
   testcontainers-backed instance before anything else runs.
2. **Calibration corpus ingestion** — all 6 rows of
   `data/calibration/problems.jsonl` are ingested and independently visible
   via `repository.list_eligible_problems()`.
3. **Codex method registration** — the real `register_baseline_methods()`
   entry point registers `codex_proof_strategy`. This `Runtime` is built
   with `api_enabled=False`, so `proof_sketch` is never attempted regardless
   of any `OPENAI_API_KEY` in the ambient environment (which is additionally
   removed for this test process, as a redundant, defense-in-depth measure,
   not the actual gate).
4. **One development proof-strategy experiment scheduled** — built via the
   real scheduler's own `RuntimeScheduler._config` constructor and enqueued
   directly, keeping the count of Codex experiments in this test exactly
   one and deterministic (the scheduler's own holdout-exclusion and
   multi-lane allocation behavior is Task 6's own, separately covered,
   concern).
5. **A real subprocess, real worktree edit, real schema-valid response** —
   `Worker.run_once` claims the experiment, forks a real execution-boundary
   child, and the fake Codex CLI edits its disposable worktree and emits a
   `ProofSketch`-schema-valid final message.
6. **Every event and a bound usage receipt persisted** — `codex_turn_events`
   holds exactly the four emitted event types in sequence
   (`thread.started`, `turn.started`, `item.completed`, `turn.completed`),
   and `codex_turns` holds one `completed` row bound to the same
   reservation/experiment id, with the exact token counts the fake CLI
   reported and a `cli_version` sourced from `CodexClient`'s
   `codex --version` fallback query (the fake's `thread.started` event
   deliberately omits the field, matching the real CLI — see "Fix round 1").
7. **The patch stored as non-authoritative artifact evidence** — the
   canonical JSON artifact (the only thing ever committed for this
   experiment) embeds both `patch_sha256` and the actual patch bytes
   (`patch_base64`). The test independently reconstructs the expected patch
   (a fresh clone at the same `base_sha`, the identical file edit, the
   identical `git add -A` + `git diff --binary --no-ext-diff` sequence
   `CodexWorktreeManager` itself uses) rather than trusting a live spy on
   the production diff call — which is structurally impossible here anyway,
   since `CodexClient.execute` runs inside the forked execution-boundary
   child, a different process a parent-process monkeypatch cannot reach —
   and confirms the reconstructed bytes are byte-identical to what was
   persisted, and that both digests agree. `reporting.review_queue()` is
   empty: there is no claim, and therefore no path from this evidence to
   publication.
8. **One consumed Codex turn, zero API dollars** — `codex_turns` has exactly
   one row; `experiments.cost_usd` for this experiment is `0`;
   `budget_reservations` has zero rows for it (proving no API-dollar
   reservation was ever *attempted*, not merely that its amount happened to
   be zero); `codex_usage_status` reports `daily_reserved=1`, one Luna role
   reservation, zero active leases; the accounting payload never carries a
   dollar-denominated field.
9. **No claim was machine-verified from the proof sketch** — proved
   structurally, not merely `status == "lead"`: the `claims` table has zero
   rows, `list_candidate_claim_ids()` is empty, `Worker.verify_pending()`
   performed zero verifications, and the fixed independent
   `CalibrationVerificationKernel.verify` method itself — spied directly at
   the class level, safe here because it runs in this same process, unlike
   `CodexClient.execute` — was never entered. That spy covers every call
   site in `src/`, not only `Worker.verify_pending()`/
   `_verify_persisted_candidate`: `repository.py`'s own
   `evaluate_and_record_claim` and `reporting.py`'s `reproduce` also call
   it, and the assertion holds across all of them, not just the one path
   this test happens to exercise.
10. **Source checkout unchanged, worktree cleanup completed** — `git
    status --porcelain` and `git rev-parse HEAD` on the synthetic "source
    main" checkout are byte-identical before and after the turn; the
    worktree directory and its `.git/worktrees/<turn-id>` administrative
    directory are both gone; `git worktree list` shows only the original
    checkout.

A deliberate mutation check was run and reverted before this evidence was
recorded: temporarily reintroducing the historical defect class this plan's
Task 5 review found and fixed (unlinking the `--output-schema` file
immediately after `Popen` returns, before the child can read it) turned this
test red (`ExperimentStatus.FAILED` instead of `SUCCEEDED`), confirming the
fake CLI's schema-honesty check is load-bearing rather than decorative. A
second mutation check (disabling the `codex --version` fallback introduced
in the fix round below) also turned this test red the same way, confirming
that fix is load-bearing too. Both mutations were reverted;
`git diff --stat` against `src/mathloop/codex/client.py` is empty.

### Command output

```text
$ uv run pytest -q tests/e2e/test_codex_canary.py -m "not live_codex"
2 passed, 1 deselected in 2.74s

$ uv run pytest -q
749 passed, 1 skipped in 123.60s (0:02:03)

$ uv run pytest -q -rs
SKIPPED [1] tests/e2e/test_codex_canary.py:584: spends one real,
credit-consuming ChatGPT Codex Luna turn against the operator's own
subscription; set MATHLOOP_RUN_LIVE_CODEX=1 immediately before an explicitly
approved run
749 passed, 1 skipped in 122.33s (0:02:02)

$ uv run ruff check src tests
All checks passed!

$ uv run mypy src
Success: no issues found in 47 source files

$ uv lock --check
Resolved 50 packages in 0.73ms

$ git diff --check
(no output; exit 0)

$ echo "MATHLOOP_RUN_LIVE_CODEX='${MATHLOOP_RUN_LIVE_CODEX}'"
MATHLOOP_RUN_LIVE_CODEX=''
```

Also, per round 2's specific request — the exact, zero-quota check the
round exists to make pass (`codex --version`/`login status` only, never
`codex exec`), run directly against this machine's real, installed CLI:

```text
$ uv run python3 -c "
from mathloop.cli import _codex_login_status
from mathloop.codex.launch import CodexLaunchPolicy
from mathloop.config import Settings
settings = Settings()
policy = CodexLaunchPolicy(codex_binary=settings.codex_cli_path, codex_home=settings.codex_home)
print(_codex_login_status(policy))
"
(True, 'Logged in using ChatGPT')
```

749 passed, 0 failed — 746 after fix round 1 + 3 new tests this round (the
`_codex_login_status` stderr-fallback-on-success regression test in
`tests/unit/test_cli.py`, the fake-CLI/real-function agreement test in
`tests/e2e/test_codex_canary.py`, and the both-sources-fail sentinel test in
`tests/unit/test_codex_client.py`). The live test is defined, collected, and
genuinely **skipped** by two independent guards (the `live_codex` marker and
a `skipif` on `MATHLOOP_RUN_LIVE_CODEX`) whether the suite is run with or
without `-m` filtering.

## Fix round 1: the review findings, and what changed

The first review of this task found the offline test itself sound but
identified defects the fake CLI concealed, discovered by direct, read-only
inspection of the real, installed Codex CLI (0.145.0) rather than by running
it (running it would have spent quota, which this task must never do).

**C1 (Critical) — `cli_version` is not reliably present on `thread.started`.**
Every fake CLI in this plan emitted `cli_version` on `thread.started`, and
`CodexClient` required it unconditionally, raising `CodexClientError`
otherwise. Binary inspection of the real CLI found no such field anywhere
near its real `thread.started` serialization. Left unfixed, every real turn
would reach `turn.completed` (spending quota) and then fail non-retryably —
the whole Codex lane would have been inoperative on the operator's first
live turn, and `reconcile_codex_turns` is deliberately never called, so
nothing would ever revisit the failure. **Fix**: `CodexClient` now falls
back to a separate, zero-turn-cost `codex --version` query
(`_query_cli_version` in `src/mathloop/codex/client.py`) when the event
omits the field, rather than treating its absence as fatal. Verified with a
real mutation test (disabling the fallback reproduces the original failure
mode) and with the offline canary test's own fake CLI now deliberately
omitting `cli_version`, exercising the fallback through the complete real
worker/ledger path, not only in an isolated unit test
(`tests/unit/test_codex_client.py::test_codex_client_falls_back_to_codex_version_when_thread_started_omits_it`).

**I1 (Important) — the event parser rejected a second `agent_message`.**
Real Codex turns routinely emit short assistant preambles, and the
production prompt explicitly invites the model to inspect the repository
and run tests first, which only increases how often a preamble precedes the
final answer. **Fix**: `CodexEventParser` now keeps the *last* agent message
seen before the terminal event, not the first, without weakening the
existing protection against an agent message arriving *after* the terminal
event (still rejected). New tests in both `tests/unit/test_codex_events.py`
and `tests/unit/test_codex_client.py` exercise a genuine multi-message
stream.

**I2 (Important) — the live test asserted *a* login, not a *ChatGPT* login.**
`codex login status` exits `0` for either a ChatGPT session or an API-key
credential; only asserting `returncode == 0` would silently let a real turn
bill metered OpenAI API dollars if the operator's `auth.json` ever held an
API-key credential instead — exactly what this plan forbids. **Fix**: the
live test now asserts `"ChatGPT" in login_detail` explicitly.

**I3 (Important) — assertion #7 committed to a patch nobody could ever
produce.** `CodexProofStrategyMethod.run` recorded only `patch_sha256`, never
the diff bytes; the disposable worktree that produced them is destroyed
before the artifact is committed, so the digest was a commitment to
unreproducible bytes. **Fix**: the artifact now also embeds the actual patch,
base64-encoded (`patch_base64`), bounded by the same `max_patch_bytes` cap
`CodexWorktreeManager.diff` already enforces (4 MiB by default) — still
clearly non-authoritative evidence, never an input to verification.

**Minors**: the acceptance-doc claim that `Worker.verify_pending()` is the
*sole* call site of the verification kernel was corrected (see item 9
above — the spy's own coverage was always broader than documented, which is
stronger, not weaker, evidence); the live test's tautological
`"OPENAI_API_KEY" not in launch_policy.environment(...)` assertion was
replaced with the meaningful ambient-environment check
(`cli._codex_launch_environment_clean()`, the same one `mathloop codex init`
runs); the live test's dead `deadline_seconds=100` (silently overridden by
`CodexClient`'s own `timeout_seconds=120.0`) was reconciled into one
120-second value sourced from the reservation, matching how
`CodexClient.execute` actually resolves its timeout in production; a
misleading comment attributing `proof_sketch` non-registration to the
absent `OPENAI_API_KEY` (the actual gate is `api_enabled=False`) was
corrected.

## Fix round 2: the review findings, and what changed

Round 1 closed C1, I1, I3, and the M2/M4/M5 minors — the reviewer
independently re-verified the C1 fallback in detail (a real version from a
real source, ~51ms under the exact restricted 7-key environment, once per
turn, never `codex exec`, its own timeout budget, no `communicate()`
deadlock risk, spawn-guard safe, and the canary's fake genuinely driving the
omitted-field path through the full pipeline to a persisted
`codex_turns.cli_version` value only the fallback could have produced) and
confirmed it closed. I1 was also independently re-verified sound:
`_apply_item_completed` still calls `_require_not_terminal` first (an
after-terminal message is still rejected), and "last wins" cannot silently
discard a structured answer, since a non-JSON *last* message still fails at
`model_validate_json` — the same outcome the old unconditional `raise` gave,
never worse.

**I2 — NOT actually addressed in round 1; the fix was inert.** The real
CLI writes its success message to **stderr** (`"Logged in using ChatGPT"`),
never stdout. `cli._codex_login_status`'s success branch
(`return True, completed.stdout.strip() or "authenticated"`) never fell back
to stderr the way its own failure branch already did, so on a genuinely,
correctly ChatGPT-authenticated machine, `completed.stdout.strip()` is
empty and the function returned the literal string `"authenticated"` —
which does not contain `"ChatGPT"`. Round 1's new assertion
(`assert "ChatGPT" in login_detail`) therefore failed **deterministically**
on a correctly authenticated machine, making the canary unrunnable — this
was the actual canary blocker, verified directly against the real 0.145.0
binary (see the command output above).

**Fix** (`src/mathloop/cli.py`, `_codex_login_status`): the success branch
now falls back to stderr exactly like the failure branch already did —
`return True, completed.stdout.strip() or completed.stderr.strip() or "authenticated"`.
This makes the assertion genuinely discriminating: the real binary's actual
strings are `"Logged in using ChatGPT"` versus `"Logged in using an API
key"` / an access-token / Bedrock variant — no alternative contains
`"ChatGPT"`.

**The fake that let this go unnoticed was also fixed.** The offline canary's
fake CLI printed `"Logged in with ChatGPT"` (wrong preposition) to **stdout**
(wrong stream) — a fiction the round-1 assertion was never actually run
against, since the offline test never calls `_codex_login_status` at all
(it drives `CodexClient` directly, never `codex_init`'s preflight). Fixed
the fake to write `"Logged in using ChatGPT"` to stderr, matching the real
CLI, and added a new test,
`test_offline_fake_codex_login_status_agrees_with_the_real_clis_actual_behavior`,
that calls the real `_codex_login_status` against this fake directly —
closing the gap where this property had no test coverage of its own at all.
Mutation-verified both fixes together: reverting `cli.py`'s stderr fallback
alone made both this new test and the analogous new unit test in
`test_cli.py` fail with `assert 'ChatGPT' in 'authenticated'`; restoring it
made both pass again.

**N1 (ordering, introduced by round 1's own C1 fix)** — the `cli_version`
fallback sat *between* the terminal event and
`self._worktree_manager.diff(...)`, itself a deadline-governed stage
(`worktrees._run` computes `max(0.0, deadline - now)`), so time spent on the
fallback could make `git add -A` time out instantly. Measured exposure was
small (~51ms of a 1800s budget) but real, and silently falsified the module
docstring's "no separate per-stage timeout stacked on top of it" invariant.
**Fix**: moved the fallback block to strictly *after* `patch = self.
_worktree_manager.diff(...)` — the true last deadline-governed stage — and
extended the module docstring to state this explicitly, the same way it
already documents worktree cleanup's own separate budget.

**N2 (Minor)** — a `None` fallback result (timeout, nonzero exit, unparseable
output) previously converted an otherwise fully successful, already
quota-spent turn into a non-retryable failure — C1's shape again, via a
narrower route. Decided, and justified in code: record a clearly-labeled
`"unknown"` sentinel instead of failing the turn when both `cli_version`
sources are unavailable — never fabricated to look like a real version,
never blank, and the receipt is still built entirely from data the turn
genuinely produced. This is different from "relax the field to optional and
store an empty string," which the round-1 review explicitly rejected. Also
added `errors="replace"` to the subprocess decode, since `capture_output=True,
text=True`'s strict decoding could otherwise raise an uncaught
`UnicodeDecodeError`. New test:
`tests/unit/test_codex_client.py::test_codex_client_uses_an_unknown_sentinel_when_both_cli_version_sources_fail`,
mutation-verified (reverting the sentinel to a raise reproduces a hard
failure; restoring it passes).

**N3 (Nit)** — `codex` is a Node wrapper spawning a vendored native binary
with inherited stdio; the fallback query previously used no process group,
so a timeout would have killed only the wrapper and orphaned the
grandchild. Fixed cheaply: `_query_cli_version` now runs the query with
`start_new_session=True` and kills the whole process group via `os.killpg`
on timeout.

**M1 leftover** — the offline test's own inline comment still claimed
`verify_pending()` was "the only call site" of the verification kernel,
the same inaccuracy round 1 had already corrected in this document but
missed in the test file itself. Fixed the comment to match: the class-level
spy covers all three real call sites (`Worker._verify_persisted_candidate`,
`repository.evaluate_and_record_claim`, `reporting.reproduce`), which is
why the assertion was never actually wrong, only its documented
justification.

## Live compatibility smoke test — defined, not yet run

`tests/e2e/test_codex_canary.py::test_live_codex_cli_compatibility_smoke` is
marked `@pytest.mark.live_codex` and additionally guarded by
`@pytest.mark.skipif(os.environ.get("MATHLOOP_RUN_LIVE_CODEX") != "1", ...)`.
It exercises `CodexClient` directly against the real, installed `codex`
binary and the real, operator-authenticated `~/.codex` store: one Luna turn,
`--ephemeral`, shell network disabled, no OpenAI/Codex API key variables, a
120-second timeout, and a tiny deterministic structured prompt. It asserts a
genuine ChatGPT login (not merely *a* login), CLI version, `thread.started`,
`turn.started`, `turn.completed`, schema validity, non-negative usage, and
that no API-dollar billing row can exist (this call path never constructs a
`Repository` or touches the OpenAI provider, and `CodexTurnReceipt` has no
dollar-denominated field to populate).

The operator has approved exactly one credit-consuming live run (recorded in
this plan's SDD ledger). Per this task's own scope, that run is deliberately
**not** executed here — it is the operator's own decision, made immediately
before execution, per:

```bash
MATHLOOP_RUN_LIVE_CODEX=1 uv run pytest -q tests/e2e/test_codex_canary.py -m live_codex
```

## Foundation-wide concerns carried forward (not fixed by this task)

Recorded here for completeness; none of these were introduced by, or in
scope for, Task 8:

- **`reconcile_codex_turns` is defined but deliberately never called from
  `src/`** — Task 4's accepted concurrency review depends on this premise
  holding; re-confirmed unchanged by this task (grepped directly).
- **Ten Sol turns are reserved and deliberately unconsumed** in this phase;
  the promotion plan's fresh review gate is their intended, still-unbuilt,
  consumer.
- Task 7's own carried-forward concerns (the `--workers` concurrency
  residual risk when a lease is held by a separate process, and the
  registry double-registration asymmetry) are unchanged by this task and
  remain recorded in that task's report.

## Remaining limitations

Novelty remains explicitly `unchecked`; there is no publication action or
human-review workflow reachable from Codex-authored leads (structurally
guaranteed, not merely policy). Codex work is scoped to the Luna role only
in this phase — Terra and Sol are wired into the domain/policy types but
have no registered consumer yet. The live compatibility smoke test above
remains unexecuted pending the operator's own separately-approved run.
