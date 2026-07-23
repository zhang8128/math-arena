# Codex Dual-Plane Supervisor Design

**Date:** 2026-07-23  
**Status:** Approved design  
**Project:** Mathloop autonomous mathematics solver ecology

## Objective

Run Mathloop's model-driven research through the locally authenticated Codex
CLI and ChatGPT/Codex usage allowance instead of metered OpenAI API requests.
Codex agents may research the open web, use local mathematics tools, edit the
repository in disposable worktrees, and propose self-improvements. Safe code
changes may merge automatically only after deterministic gates, a fresh
independent review, and a held-out canary.

The system must preserve Mathloop's existing hard boundaries:

- Generated mathematics is non-authoritative until independently verified.
- No autonomous action publishes a mathematical claim.
- Research agents never write directly to the live `main` checkout.
- A mathematical result cannot modify or authorize its own verifier.
- Credit, process, provenance, and promotion state remain durable across
  crashes and restarts.

## Selected Operating Profile

- Agent mode: full tool-using Codex agents.
- Workspace: disposable Git worktree containing the Mathloop repository.
- Research access: Codex live open-web search.
- Code promotion: automatic after tests, independent review, and canary.
- Daily envelope: 100 started Codex turns, four concurrent turns, 30 minutes
  per turn, and at most five successful code promotions.
- Problem mix: balanced allocation across computational targets,
  proof-oriented targets, and moonshots.
- Default model roles:
  - 40 Luna turns for discovery and formalization.
  - 40 Terra turns for solving and method development.
  - 20 Sol turns for escalation and independent code review.
- At least ten Sol turns remain reserved for the review and safety lane.

These are local policy defaults, not claims about exact ChatGPT credit
conversion. Codex reports token usage but does not expose an exact real-time
ChatGPT-credit balance. Mathloop therefore enforces turns, tokens, concurrency,
deadlines, and promotion counts rather than invented dollar equivalents.

## Non-Goals

- Automatically publishing claims, papers, issues, or social posts.
- Treating a proof sketch or confident model statement as a proof.
- Automatically merging changes to Mathloop's trust root.
- Giving model-generated shell commands general network access.
- Copying Codex authentication material into worktrees, artifacts, logs, or
  child environments.
- Guaranteeing novelty merely because a problem came from a newly retrieved
  page. Novelty remains `unchecked` until separately established.
- Building persistent app-server conversations in the first release.

## Architecture

```text
Open web sources
      |
      v
Quarantined problem intake
      |
      v
Balanced portfolio scheduler
      |
      v
Codex supervisor -----> disposable worktree per agent
      |                            |
      v                            v
Structured math result        optional code patch
      |                            |
      v                            v
Independent verifier          promotion queue
      |                            |
      v                            v
Review/reporting             fresh Sol review + tests
                                   |
                                   v
                           held-out canary and merge
                                   |
                                   v
                         new provenance epoch or revert
```

The design has two authority planes:

1. **Research plane.** Discovers, formalizes, solves, tests, and proposes.
   Everything produced here is evidence or a lead.
2. **Promotion plane.** Owns protected-path classification, deterministic
   checks, independent code review, canaries, serialization, merge, restart,
   and rollback. Research-plane output cannot bypass this plane.

The existing fixed verification kernel remains a separate mathematical
authority. A Codex reviewer is independent from a patch author for code-review
purposes, but is not a substitute for exact mathematical verification.

## Components

### Codex Supervisor

The supervisor owns every noninteractive Codex invocation. It:

- Reserves a durable turn and concurrency slot before process start.
- Creates a clean worktree from the recorded base commit.
- Selects a task schema, prompt, model role, and tool policy.
- Starts one supervised process group with an absolute deadline.
- Parses and persists Codex JSONL events incrementally.
- Captures the final schema-constrained result and the worktree diff.
- Cleans up all descendants and releases the lease transactionally.
- Routes mathematical artifacts and code patches into different queues.

The tested local integration target is Codex CLI `0.145.0`. Every invocation
records the actual CLI version; unsupported versions fail closed.

### Problem Intake

Discovery agents use live Codex web search to locate candidate problems. Intake
stores:

- Canonical URL and source title.
- Retrieval time and content digest.
- Attribution and any available publication metadata.
- The exact quoted mathematical statement.
- A normalized candidate statement.
- Source excerpts used by the agent.
- Initial category, testability assessment, and known-status assessment.

Retrieved material is untrusted data. It is delimited from task instructions,
cannot alter system policy, and cannot enter scheduling until a separate
formalization job validates its shape.

Formalization produces an immutable Mathloop problem and, when possible, an
exact checker contract. Duplicate detection uses normalized statements,
checker identity, source identity, and semantic similarity. Suspected
duplicates remain auditable but are not scheduled as new work.

### Portfolio Scheduler

The scheduler maintains approximately equal long-run allocation across:

- Computational conjectures with finite or bounded counterexample searches.
- Proof-oriented statements that may admit supported certificates.
- Moonshots whose output is expected to remain exploratory.

Allocation adapts from verified outcomes, cost in turns/tokens/time, novelty of
approach, and method diversity. Minimum exploration and completeness
allocations prevent a high-scoring family from starving other approaches.
Evaluation holdouts are scheduler-unseen; they are not claimed to be absent
from model training data.

### Codex Agent Runner

Each invocation is equivalent to:

```text
codex exec
  --ephemeral
  --json
  --output-schema <task-schema>
  --sandbox workspace-write
  --ignore-user-config
  --ignore-rules
  --model <role-model>
  --cd <disposable-worktree>
  <explicit-task-prompt>
```

The generated launch configuration enables Codex live web search while keeping
model-generated shell commands offline. User MCP servers, plugins, hooks,
rules, and repository-local Codex configuration are not loaded. Model and
reasoning settings are supplied explicitly.

The child environment is an allowlist containing only values required for the
worktree and runtime. It excludes OpenAI API keys, database credentials,
unrelated secrets, inherited provider configuration, and Docker control
sockets. The saved Codex login remains in the host Codex credential store and
is never copied into a worktree or artifact.

### Restricted Mathematics Tools

Agents may run ordinary workspace-local Python, tests, and SymPy. Privileged
Sage operations are exposed through a generated Mathloop MCP configuration
whose server executable comes from the trusted `main` provenance epoch, not
from the candidate worktree.

The MCP surface offers only bounded, typed mathematical operations. It invokes
the exact pinned, networkless Sage image under the existing memory, CPU, PID,
filesystem, and timeout restrictions. It does not expose a generic shell,
Docker socket, database connection, or arbitrary host path.

### Mathematical Result Router

Task schemas distinguish:

- Candidate counterexample or witness.
- Supported proof certificate.
- Proof strategy and lemmas.
- Negative search result with explicit bounds.
- Problem formalization.
- Research/source report.

Codex confidence has no authority. Exact witnesses and supported certificates
enter the existing independent verification path. Unsupported proofs and
moonshot results remain `lead`, even when the agent labels them complete.

### Code Promotion Controller

Repository changes remain isolated in their originating worktree. The
controller:

1. Captures the diff, base commit, agent transcript digest, and task identity.
2. Rejects binary, oversized, generated, secret-bearing, or policy-widening
   patches.
3. Applies the protected-path policy.
4. Rebases onto the current `main`.
5. Reruns all gates after the rebase.
6. Requests a fresh ephemeral read-only Sol review with no shared thread.
7. Runs an equal-budget parent-versus-candidate held-out canary.
8. Acquires the single merge lock and confirms `main` is unchanged.
9. Creates an auditable merge commit and drains active workers.
10. Restarts at the new executable-provenance epoch.
11. Monitors health and automatically creates a revert commit on regression.

Automatic rollback is a normal Git revert. The controller never uses
destructive reset or deletes evidence.

## Auto-Promotion Boundary

The following areas may auto-promote when all gates pass:

- Solver method implementations.
- Prompt and tactic libraries.
- Routing and allocation policies.
- Problem-source adapters and formalizers.
- Evaluation features and non-authoritative reporting.
- Focused tests that strengthen the changed behavior.

The following trust-root areas always require human approval:

- Verification authority and verifier allowlists.
- Billing, Codex credit accounting, or settlement semantics.
- Process containment, sandboxing, environment filtering, or network policy.
- Provenance construction, reproduction, or migration.
- Promotion, protected-path, review, merge, restart, or rollback logic.
- Dependency locks, build definitions, Dockerfiles, or pinned image identities.
- Database migrations affecting authority or audit history.
- Deletion, weakening, skipping, or broad mocking of tests and security checks.
- Any change that expands filesystem, credential, MCP, network, or publication
  authority.

A patch touching both surfaces is entirely human-gated; it is never split and
partially auto-merged.

## Durable State and Lifecycle

Codex jobs follow:

```text
reserved -> starting -> dispatched -> running
         -> completed | failed | timed_out | ambiguous
```

Once a `turn.started` JSONL event is durably recorded, the turn consumes the
daily allowance. A process-start failure before dispatch may be retried.
Committed or ambiguous dispatch is never automatically replayed because doing
so could consume another Codex turn.

For each job, persist:

- Task, problem, method, model role, and prompt digest.
- Worktree base and final Git identities.
- Codex CLI version and generated policy.
- Structured JSONL lifecycle events.
- Input, cached-input, output, and reasoning-token usage when reported.
- Deadline, exit status, termination reason, and descendant cleanup result.
- Final response, schema version, artifacts, source citations, and hashes.
- Diff, test evidence, review result, canary result, promotion, and rollback.

States for discovered mathematics follow:

```text
discovered -> quarantined -> formalized -> scheduled
           -> codex_running -> artifact_committed
           -> independently_verified -> review/report
```

## Budget and Model Policy

The initial daily policy is:

- 100 started turns total.
- Four concurrent turns.
- 30-minute absolute deadline per turn.
- Five successful automatic promotions.
- 40 Luna, 40 Terra, and 20 Sol reservations.
- At least ten Sol reservations unavailable to ordinary scouting.

The supervisor also records and may cap total reported tokens. A rate-limit or
account-exhaustion response drains new dispatches until the next policy window
or operator intervention. It does not fall back silently to API-key billing.

The OpenAI API provider remains available as a separately configured provider,
but the Codex supervisor never sets `OPENAI_API_KEY` or `CODEX_API_KEY`. It
reuses the persisted ChatGPT-authenticated Codex CLI session.

## Web and Prompt-Injection Policy

Open-web access is intentionally broad at the Codex search-tool layer. Defense
does not rely on model obedience alone:

- Search content is treated as untrusted evidence.
- Shell network access remains disabled.
- No secrets or live database credentials enter the environment.
- Research runs occur only in disposable worktrees.
- User plugins, MCP servers, hooks, and configuration are excluded.
- Only the fixed restricted mathematics MCP server is available.
- Structured outputs and diffs are validated outside Codex.
- Protected paths and publication actions are enforced by non-model code.
- A source page can influence a proposal but cannot grant authority.

## Failure Handling

- **Malformed JSONL:** preserve raw bounded output, fail the job, consume the
  turn only if dispatch was confirmed.
- **Schema-invalid final response:** store as failed evidence; never infer
  missing fields.
- **Timeout or crash:** terminate the process group, verify descendant cleanup,
  and mark dispatched work non-retryable without an operator decision.
- **Rate limit or expired login:** pause new Codex dispatches and surface an
  operator action; local non-Codex lanes may continue.
- **Worktree conflict:** rebase once under promotion policy, rerun every gate,
  otherwise archive the candidate.
- **Review rejection:** return findings to a new fixer job if budget remains;
  the reviewer does not edit the candidate.
- **Canary regression:** archive without merge.
- **Post-merge regression:** drain workers, create a revert commit, restart the
  previous provenance epoch, and retain all evidence.
- **Supervisor crash:** leases and process identities permit reconciliation;
  ambiguous external turns are conservatively settled.

## Operator Interface

Planned commands:

```text
mathloop codex init
mathloop codex start
mathloop codex status
mathloop codex pause
mathloop codex resume
mathloop codex drain
mathloop codex report
```

`start` launches the durable supervisor with the configured daily policy.
`pause` prevents new dispatch while allowing current turns to finish. `drain`
prevents dispatch, terminates only after the configured grace period, and
leaves recoverable state. `status` reports credit reservations, model
allocation, active process/worktree identities, queue depth, verifier outcomes,
promotion state, and any operator-required condition.

## Test Strategy

### Unit

- Codex JSONL parsing and event-state transitions.
- Pydantic output schemas and malformed/oversized output rejection.
- Turn, model-reservation, concurrency, token, deadline, and promotion budgets.
- Environment allowlisting and launch-argument construction.
- Protected-path classification and fail-closed mixed patches.
- Problem-source quarantine, deduplication, and portfolio floors.

### Fake-CLI Integration

- Pre-dispatch process failure.
- Durable `turn.started` boundary.
- Partial output, malformed events, refusal, rate limit, and schema failure.
- Deadline enforcement and full descendant cleanup.
- Ambiguous dispatch without automatic replay.
- Worktree creation, diff capture, conflict, and cleanup.
- Promotion serialization, restart, and revert.

### Real Local Integration

- One explicitly marked, credit-consuming ephemeral Codex call through saved
  ChatGPT authentication.
- Live JSONL and schema compatibility with the installed CLI.
- Built-in web search available while shell network remains blocked.
- Restricted Sage MCP operation succeeds without Docker or credential
  authority reaching the agent shell.

### End to End

- Codex proposes a mathematical witness that the independent kernel accepts.
- Codex proposes an invalid witness that the kernel rejects.
- A safe method patch passes review and canary, merges, and creates a new
  provenance epoch.
- A trust-root patch remains human-gated.
- A post-merge health regression triggers a revert and clean restart.

## Rollout and Acceptance

1. Run all offline unit, integration, security, and end-to-end tests.
2. Run one explicit live Codex compatibility smoke test.
3. Start a six-turn canary with no automatic merging.
4. Require correct accounting, cleanup, structured artifacts, and verifier
   behavior for all six turns.
5. Enable one automatic safe-surface promotion and verify merge/restart/revert
   controls.
6. Unlock the selected 100-turn daily envelope and five-promotion cap.

Acceptance requires:

- No OpenAI API key or API-dollar receipt used by the Codex path.
- ChatGPT-authenticated Codex invocation succeeds and records CLI/model usage.
- No research agent can write the live `main` checkout.
- No model-generated command has general shell network, Docker socket, database
  credential, or host-secret access.
- Mathematical promotion still requires the fixed independent kernel.
- Protected-path patches cannot auto-merge.
- Safe patches cannot merge without fresh review, full gates, and canary.
- Crashes, timeouts, rate limits, restarts, and rollbacks preserve exact audit
  and budget state.
- The problem and method populations both demonstrably change across cycles
  while balanced portfolio and completeness floors remain intact.

## Source Basis

The design uses the documented Codex noninteractive contract:

- `codex exec` reuses saved CLI authentication by default.
- `--ephemeral`, `--json`, `--output-schema`, explicit model selection, and
  sandbox selection are supported for automation.
- JSONL includes lifecycle events and token usage.
- ChatGPT-managed authentication uses Codex/ChatGPT usage limits rather than
  API-key token billing.

Official references:

- <https://learn.chatgpt.com/docs/non-interactive-mode>
- <https://learn.chatgpt.com/docs/pricing>
- <https://learn.chatgpt.com/docs/sandboxing>
- <https://learn.chatgpt.com/docs/app-server>

