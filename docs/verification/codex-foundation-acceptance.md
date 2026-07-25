# Codex Supervisor Foundation Acceptance

Evidence recorded on 2026-07-24 from the `worktree-codex-foundation` worktree
(branch base `689fe6e`, HEAD `beee5ef` before this task's commit) on macOS
arm64 with Python 3.13. `OPENAI_API_KEY`/`CODEX_API_KEY` were absent from the
test process throughout, and the offline suite never contacts a real Codex or
OpenAI endpoint.

This document covers Task 8 of
`docs/superpowers/plans/2026-07-23-codex-supervisor-foundation.md`: the
end-to-end verification of the complete Codex path (policy/accounting types,
JSONL event parsing, disposable worktree isolation, the transactional turn
ledger, the supervised CLI client, the Codex proof-strategy method and
scheduling, and the runtime composition/operator commands built in Tasks
1-7), plus the credit-consuming canary gate.

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
   entry point registers `codex_proof_strategy` and (with no
   `OPENAI_API_KEY` present) does not register `proof_sketch`.
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
   reported.
7. **The patch stored as non-authoritative artifact evidence** — the
   canonical JSON artifact (the only thing ever committed for this
   experiment) embeds `patch_sha256`. The test independently reconstructs
   the expected patch (a fresh clone at the same `base_sha`, the identical
   file edit, the identical `git add -A` + `git diff --binary --no-ext-diff`
   sequence `CodexWorktreeManager` itself uses) rather than trusting a live
   spy on the production diff call — which is structurally impossible here
   anyway, since `CodexClient.execute` runs inside the forked
   execution-boundary child, a different process a parent-process
   monkeypatch cannot reach — and confirms the two digests agree.
   `reporting.review_queue()` is empty: there is no claim, and therefore no
   path from this evidence to publication.
8. **One consumed Codex turn, zero API dollars** — `codex_turns` has exactly
   one row; `experiments.cost_usd` for this experiment is `0`;
   `budget_reservations` has zero rows for it; `codex_usage_status` reports
   `daily_reserved=1`, one Luna role reservation, zero active leases; the
   accounting payload never carries a dollar-denominated field.
9. **No claim was machine-verified from the proof sketch** — proved
   structurally, not merely `status == "lead"`: the `claims` table has zero
   rows, `list_candidate_claim_ids()` is empty, `Worker.verify_pending()`
   (the sole call site of the fixed independent `CalibrationVerificationKernel`)
   performed zero verifications, and the kernel's own `verify` method,
   spied directly (safe here because `_verify_persisted_candidate` runs in
   the same process as the test, unlike `CodexClient.execute`), was never
   entered.
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
fake CLI's schema-honesty check is load-bearing rather than decorative. The
mutation was reverted; `git diff --stat` against `src/mathloop/codex/client.py`
is empty.

### Command output

```text
$ uv run pytest -q tests/e2e/test_codex_canary.py -m "not live_codex"
1 passed, 1 deselected in 2.78s

$ uv run pytest -q
744 passed, 1 skipped in 121.66s (0:02:01)

$ uv run pytest -q -rs
SKIPPED [1] tests/e2e/test_codex_canary.py:518: spends one real,
credit-consuming ChatGPT Codex Luna turn against the operator's own
subscription; set MATHLOOP_RUN_LIVE_CODEX=1 immediately before an explicitly
approved run
744 passed, 1 skipped in 121.75s (0:02:01)

$ uv run ruff check src tests
All checks passed!

$ uv run mypy src
Success: no issues found in 47 source files

$ uv lock --check
Resolved 50 packages in 0.64ms

$ git diff --check
(no output; exit 0)
```

744 passed at HEAD `beee5ef` + 1 new offline end-to-end test = 744 passed, 0
failed — matching the required 743+/0 bar. The live test is defined,
collected, and genuinely **skipped** by two independent guards (the
`live_codex` marker and a `skipif` on `MATHLOOP_RUN_LIVE_CODEX`) whether the
suite is run with or without `-m` filtering.

## Live compatibility smoke test — defined, not yet run

`tests/e2e/test_codex_canary.py::test_live_codex_cli_compatibility_smoke` is
marked `@pytest.mark.live_codex` and additionally guarded by
`@pytest.mark.skipif(os.environ.get("MATHLOOP_RUN_LIVE_CODEX") != "1", ...)`.
It exercises `CodexClient` directly against the real, installed `codex`
binary and the real, operator-authenticated `~/.codex` store: one Luna turn,
`--ephemeral`, shell network disabled, no OpenAI/Codex API key variables, a
120-second test timeout, and a tiny deterministic structured prompt. It
asserts ChatGPT login, CLI version, `thread.started`, `turn.started`,
`turn.completed`, schema validity, non-negative usage, and that no
API-dollar billing row can exist (this call path never constructs a
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

- **The raw Codex worktree patch is never persisted, only its digest.**
  `CodexProofStrategyMethod.run` records `patch_sha256` in the artifact
  envelope but never the diff bytes themselves (the disposable worktree
  that produced them is destroyed by the time the artifact is committed).
  An operator who wants to inspect what a specific Codex turn actually
  changed has only a cryptographic commitment to compare against, never the
  content — sufficient for integrity, not for post-hoc review of *what* was
  proposed.
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
