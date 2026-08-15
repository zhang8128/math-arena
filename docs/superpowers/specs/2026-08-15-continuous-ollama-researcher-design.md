# Continuous Ollama Researcher Design

**Date:** 2026-08-15
**Status:** Approved design (in-chat, Kairos); implementation not started
**Supersedes:** `2026-07-30-local-model-arena-design.md` where the two differ.
That document remains the reference for rationale it shares with this one;
this document is authoritative for runtime, model, run semantics, topic
diversity, literature patrol, and research backends.

## Purpose

A single command launches a continuous, locally-hosted recursive researcher
that runs `.timeloop` room turns indefinitely: pick a target, attack it with
bounded tools, novelty-check against the live literature, record durable
findings, repeat. The operator probes it in real time from other sessions
(read-only status, tailing turn records) and stops it cleanly at will.

The runtime is Ollama serving `qwen3.8:27b-mlx`. Local operation must be
genuinely free of metered inference: it may not silently register, invoke, or
fall back to OpenAI API, Codex, or any paid provider.

The local model supplies fallible cognition. It may propose targets, frames,
experiments, tool calls, proof sketches, and durable updates. It never
supplies verification authority, self-promotion authority, publication
authority, or its own fitness label.

## Scope

Included:

- an Ollama lifecycle controller that starts the server if absent and
  preloads an already-installed model — never downloads one;
- one provider-neutral local-model implementation shared by the `.timeloop`
  arena and production `mathloop`;
- a **continuous** foreground arena runner with lease/heartbeat, clean stop,
  circuit breaker, and cumulative resource ceilings;
- topic-diversity selection (rotation cap + exploration lanes);
- a scheduled **literature patrol** that re-compares recorded findings
  against the live literature;
- curated unmetered research tools including local SearXNG web search;
- a local proof-strategy method in production `mathloop`;
- a hard local-only process boundary, zero-dollar receipts, durable turn
  events, independent verification;
- `bin/research` single-command operator entry point plus `mathloop local`
  CLI; automated tests and a real-model acceptance canary plus a supervised
  soak gate.

Excluded:

- downloading models (`ollama pull` and any download endpoint are forbidden);
- paid fallback or mixed paid/local operation;
- launchd/auto-restart daemonization (foreground under tmux is the delivery;
  a service wrapper is a possible later delivery);
- a status dashboard (files + read-only CLI are the probe surface);
- unrestricted shell or network access;
- model-authored commits or direct canonical-file mutation;
- treating a local model assertion as proof;
- automatic public claims or changes to the human publication gate;
- LM Studio support (demoted to a possible future transport; the provider
  contract must stay free of runtime-specific types so it could return).

## Approved operating profile

| Field | Value |
|---|---|
| Runtime | Ollama (>= 0.32.12, native MLX support) |
| Model selector | `qwen3.8:27b-mlx` (27.8B, nvfp4, tools + thinking) |
| Endpoint | `http://127.0.0.1:11434` |
| Context length | 65,536 tokens (model supports 262,144; 64k chosen for KV headroom on the 128 GB host) |
| Model concurrency | 1 |
| Turn timeout | 30 minutes |
| Idle unload | `keep_alive` 900 s |
| Run mode | continuous foreground (tmux), clean-stop signals |
| Circuit breaker | 5 consecutive failed turns halts the loop |
| Rotation cap | max 3 consecutive turns on one target |
| Exploration lane | >= 20% of turns |
| Literature patrol | every 25th turn |
| Network | curated read-only research tools (OEIS, arXiv, Crossref, Wikipedia, loopback SearXNG) |
| Paid fallback | forbidden |

The selector is a logical identifier resolved against Ollama's installed-model
listing (`/api/tags`). Resolution must produce exactly one match. An absent or
ambiguous match is a bounded preflight failure — never a download.

## Architecture

```text
OllamaLifecycle
  server probe/start -> installed-model resolution -> preload(keep_alive) -> health
                                      |
                                      v
LocalModelProvider
  structured output | tool calls | usage | zero-dollar receipt | provenance
  (OpenAI SDK against the loopback /v1 compatibility endpoint)
                    /                                      \
                   v                                        v
ContinuousArenaRunner                              LocalProofStrategy
  lease + heartbeat + signals                       production scheduling
  selection: rotation cap, lanes, patrol            existing repository/evolution
  bounded tool loop per turn                        existing verification kernel
  circuit breaker + ceilings
  durable turn events
                    \                                      /
                     v                                    v
                  independent computation and Lean verification
```

### `OllamaLifecycle`

Owns runtime discovery and readiness, not inference semantics. Via the native
loopback HTTP API and at most one spawned process:

1. probe `GET /api/version`; if unreachable, spawn `ollama serve` (detached,
   scrubbed environment) and wait bounded for readiness — it never stops a
   server it did not start, and never stops one it did start either (the TTL
   releases memory; the server is cheap to leave up);
2. enumerate installed models with `GET /api/tags`;
3. resolve exactly one `qwen3.8:27b-mlx`; nearby families, parameter counts,
   or quantizations must not satisfy the selector;
4. preload with the configured `keep_alive` and verify via `GET /api/ps` and
   the compatibility `GET /v1/models`;
5. return an immutable runtime identity (endpoint, model name, digest, size,
   quantization, context length, ollama version, identity SHA-256).

It must never invoke `ollama pull`, `POST /api/pull`, or any download path.
A model missing after preflight is a capability-unavailable event, not a
reason to download it.

### `LocalModelProvider`

Implements the existing provider-neutral `ModelProvider.generate(request,
schema)` protocol and the `ToolCallingModelProvider.next_action(request)`
protocol over one local transport: the pinned OpenAI SDK pointed at the
validated loopback `/v1` endpoint. It does not import OpenAI pricing, model
catalogs, or paid-provider retry assumptions. Neither consumer imports
lifecycle or wire-format types.

Thinking: the model advertises the `thinking` capability. The provider passes
the think toggle through `extra_body`; whether the compatibility endpoint
honors it is verified by the live canary, and each response records whether
thinking was requested and whether reasoning content came back. If the
compatibility endpoint proves unable to control thinking, the provider may
route that single concern through the native `/api/chat` endpoint without
changing either consumer-facing protocol.

Each response records runtime/transport identity, endpoint origin, resolved
model identity, generation config, prompt/schema/tool-catalog digests,
response ID, token usage, wall-clock duration, and a zero-dollar
authorization + receipt under the `local-compute-v1` accounting policy
(provider string: `local-ollama`).

### `ContinuousArenaRunner`

Consumes `LocalModelProvider` and the host tool registry. Runs turns
back-to-back until stopped. A turn cannot directly edit canonical arena
state. Bounded-batch execution (`run_batch`) is retained for tests, smoke
runs, and the controlled first batch.

### `LocalProofStrategy`

Consumes the same provider inside production `mathloop`, as a separate method
family (`local_proof_sketch`) from paid strategies so provenance never
conflates them. Unchanged from the superseded design.

## Continuous operation semantics

This section is new relative to the superseded design, which excluded
continuous operation. The 2026-07-25 orphaned-jobs incident (two arena jobs
pinning cores for hours, producing nothing) is the cautionary baseline: a
continuous researcher must be deliberately managed, visible, and
self-limiting.

- **Lease + heartbeat.** One researcher at a time. A lease file under
  `.timeloop/local/` records pid, start time, seed, and a heartbeat timestamp
  refreshed at every turn boundary and at least every 60 s inside a turn. A
  lease without a heartbeat for 10 minutes is stale; startup expires it,
  records one transition event, and proceeds. `status` reports lease state
  verbatim.
- **Clean stop.** First SIGINT/SIGTERM: finish or abort the current turn as a
  recorded event (`interrupted` status), release the lease, exit 0. Second
  signal: exit immediately (the lease goes stale and the next start records
  the expiry). `bin/research stop` sends SIGTERM to the lease pid from any
  session.
- **Circuit breaker.** Five consecutive failed turns (invalid model output,
  tool failure, timeout, transport failure — verified negative results are
  successes, not failures) halt the loop with a durable halt event and a
  nonzero exit. The breaker threshold is configuration, not hope.
- **Ceilings.** Per-turn budgets are unchanged from the superseded design
  (12 model actions, 4,096 output tokens per action, 12 tool invocations,
  6 subprocesses, 120 s per subprocess, 16 MiB artifacts, 6 research queries,
  2 MiB assembled context). Cumulative per-run: artifact disk cap (default
  2 GiB) and an optional `--max-hours` wall-clock ceiling; hitting either is
  a clean recorded halt.
- **Sleep prevention.** `bin/research` wraps the loop in `caffeinate -i`.
- **Foreground.** The process runs in the operator's tmux/terminal. Nothing
  auto-restarts; a crash is visible and `status` says so.

## Topic diversity

Selection must not grind one target all night:

- **Rotation cap:** after 3 consecutive turns on one target, that target is
  ineligible for the next selection (resumable `next_action` does not
  override the cap; it resumes after rotation).
- **Exploration lane:** at least 20% of deterministic selections sample
  underused pool targets, parked targets eligible for revival, and
  forge-track generation; at least 15% sample underused methods/frames (as
  in the superseded design).
- **Held-out partition:** unchanged — never used for online promotion.

## Literature patrol

Per-finding novelty checking (protocol step 4, mandatory since T13) fires
when a finding is recorded. A continuous researcher additionally re-compares
on a schedule, because the literature drifts under long-lived state:

- Every 25th turn is a **patrol turn** instead of an attack turn.
- The patrol selects targets with the oldest NOVELTY timestamps, plus all
  `parked` and `superseded` targets.
- It re-runs their recorded novelty queries through the research adapters and
  diffs results against the stored NOVELTY entries.
- Differences append correction events with provenance; nothing is
  overwritten or deleted (room rule 5).
- Patrol turns are pure research-tool turns (no proving, no Python
  experiments required) and carry `turn_kind: "patrol"` in their records.

## Web research

All research goes through the host adapter; the model never touches the
network directly. Unmetered backends only:

- OEIS, arXiv export API, Crossref REST, Wikipedia API — public,
  unauthenticated;
- `search_web` via a **loopback SearXNG** instance, added as a service in
  `compose.yaml` (SearXNG is self-hosted metasearch; no API key, no
  metering). `bin/research` starts it via Docker when available; if it is
  unreachable the run continues with the remaining backends and every turn
  record lists which backends were actually available, so a `not found`
  NOVELTY claim is scoped to the search breadth that produced it. A
  `--require-web` flag makes SearXNG absence a preflight failure instead.

Backends receive only explicit query strings or public identifiers — never
notebook text, prompts, proof drafts, environment, or credentials. Queries,
URLs, response digests, and bounded source metadata are persisted per query.

## Local-only authority boundary

Carried over unchanged from the superseded design: exactly one external
cognition mode (`none` | `local` | `openai` | `codex`); local mode refuses
paid-method registration, rejects non-loopback inference endpoints, scrubs
paid credentials from every child environment, cannot construct a paid
client, has no fallback path to an external provider, and settles every
receipt at exactly zero database USD. Source and verifier authority rules
are unchanged. Verified outcomes are the only fitness evidence; model
self-assessment never is.

## Turn data flow, records, evolution, failure semantics

Carried over from the superseded design with these deltas:

- turn records gain `turn_kind` (`attack` | `patrol`) and
  `research_backends_available`;
- the runner loops turns continuously between the lease/breaker/ceiling
  checks instead of stopping at a batch boundary;
- everything else — snapshot/select/orient/act/observe/conclude/verify/
  materialize/learn phases, strict final records, append-only events,
  content-addressed artifacts, correction-not-deletion, lease-per-turn,
  invocation-ID replay, no post-side-effect provider retries — is unchanged.

## Operator interface

Single command, plus probes:

```text
bin/research                 # preflight + caffeinate + continuous run (foreground)
bin/research --max-hours 8   # same with a wall-clock ceiling
bin/research status          # read-only: lease, current turn, counts, uptime
bin/research stop            # SIGTERM to the lease pid

mathloop local init          # non-destructive readiness + canary checks
mathloop local status        # read-only
mathloop local research [--seed N] [--max-hours H] [--require-web]
mathloop local arena --turns 5 --seed 1    # bounded batch (tests, smoke, first batch)
mathloop local run --cycles 5 --workers 1  # production local method
```

`bin/research` (repo root, executable) performs: Ollama server reachable (or
starts it), exact model resolved among installed models, Lean toolchain
present, SearXNG started via Docker when available (warn and continue
otherwise), then `exec caffeinate -i uv run mathloop local research "$@"`.

The probe surface for live sessions is deliberately lean: `mathloop local
status`, `tail -f .timeloop/local/turns.jsonl`, and the ledger/notebook
appends themselves.

## Configuration

`MATHLOOP_` settings as in the superseded design, re-based on Ollama defaults
(`local_api_base_url=http://127.0.0.1:11434`,
`local_model_selector=qwen3.8:27b-mlx`, `local_context_length=65536`) and
extended with: circuit-breaker threshold, rotation cap, exploration rate,
patrol interval, cumulative artifact disk cap, heartbeat/stale-lease
intervals, SearXNG URL (loopback-validated), and per-backend rate limits.
Settings validate the local-only invariants before constructing runtime
components. Secrets are not accepted as local-provider configuration.

## Verification strategy

The superseded design's test pyramid carries over re-targeted at Ollama
(unit tests for lifecycle resolution/ambiguity/no-download, loopback
validation, mode exclusion, credential scrubbing, receipts, tool policies,
strict records; fake-server integration tests against a stub of both the
native API and `/v1`). New continuous-semantics coverage:

- lease contention (second researcher refuses to start);
- stale-lease expiry recorded exactly once;
- SIGTERM mid-turn produces an `interrupted` durable event and a released
  lease (subprocess-based test);
- circuit breaker trips at exactly the threshold and emits a halt event;
- artifact disk ceiling halts cleanly;
- rotation cap and patrol scheduling are deterministic in selection tests;
- degraded-web mode records available backends and `--require-web` fails
  preflight.

Release gates, in order:

1. full offline suite green;
2. real-model canary against `qwen3.8:27b-mlx` (exact identity, structured
   output, tool round trip, false-claim rejection, positive control,
   zero-dollar settlement, no paid-provider event);
3. one controlled bounded batch (`local arena --turns 3`) reviewed by a
   human;
4. a **supervised soak**: `local research --max-hours 2` with the operator
   present, reviewing records afterward, before the first unattended
   overnight run.

The grader cannot share an implementation with the examinee. Lean and
deterministic computation remain the principal positive controls.

## Delivery sequence

1. Local-only mode boundary and settings (Ollama defaults).
2. Ollama lifecycle and exact installed-model resolution.
3. Shared structured + tool-calling local provider with zero-dollar receipts.
4. Durable arena domain, storage, and diversity-aware selection (rotation
   cap, patrol lane).
5. Bounded host tools and unmetered research (OEIS/arXiv/Crossref/Wikipedia/
   SearXNG), SearXNG compose service.
6. Independent arena verification.
7. Continuous runner: lease/heartbeat/signals/breaker/ceilings/patrol over
   the bounded turn core.
8. CLI (`local init/status/research/arena/run`), `bin/research` wrapper,
   production local method registration.
9. Documentation, offline release matrix, real-model canary, controlled
   batch, supervised soak.

## Acceptance criteria

The work is complete when:

- `bin/research` alone takes the machine from cold to a continuously
  researching foreground process, with Ollama started if needed and the
  installed `qwen3.8:27b-mlx` resolved without any download path;
- `bin/research status` / `stop` work from a separate session while turns
  are running;
- the loop rotates targets (cap respected), explores (lanes nonzero), and
  runs literature patrols on schedule, all visible in turn records;
- a stop signal, breaker trip, or ceiling produces a clean durable halt with
  no half-written records;
- local mode has a mechanically enforced no-paid-provider boundary and
  exact zero-dollar settlements;
- canonical state changes only after host validation; positive claims
  require independent verification;
- the full offline suite, the real-model canary, the controlled batch
  review, and the supervised soak have all passed, in that order, before
  any unattended overnight run.
