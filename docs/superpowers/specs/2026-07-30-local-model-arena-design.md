# Local-Model Arena and Mathloop Provider Design

**Date:** 2026-07-30  
**Status:** Approved design; implementation not started

## Purpose

Add a first-class local-model execution path shared by the `.timeloop`
research arena and the production `mathloop` solver ecology. The default
runtime is LM Studio with Qwen3.6 35B A3B. Local operation must be genuinely
free of metered inference: it may not silently register, invoke, or fall back
to OpenAI API or Codex execution.

The local model supplies fallible cognition. It may propose targets, frames,
experiments, tool calls, proof sketches, and durable updates. It never supplies
verification authority, self-promotion authority, publication authority, or
its own fitness label.

## Scope

This design includes:

- one provider-neutral local-model implementation used by both execution
  surfaces;
- an LM Studio lifecycle controller that starts the server and loads an
  already-installed model;
- a bounded, tool-using `.timeloop` agent;
- a local proof-strategy method in production `mathloop`;
- a hard local-only process boundary;
- zero-dollar but fully attributed billing and usage receipts;
- curated read-only research tools;
- durable turn events, independent verification, and held-out evaluation;
- operator CLI commands, automated tests, and a real-model acceptance canary.

This design does not include:

- downloading models;
- paid fallback or mixed paid/local batches;
- unrestricted shell or network access;
- continuous daemon operation;
- model-authored commits or direct canonical-file mutation;
- treating a local model assertion as proof;
- automatic public claims;
- changing the existing human publication gate.

## Approved operating profile

The initial profile is:

| Field | Value |
|---|---|
| Runtime | LM Studio |
| Model selector | `qwen3.6-35b-a3b` |
| Endpoint | `http://127.0.0.1:1234` |
| Context length | 32,768 tokens |
| Model concurrency | 1 |
| Turn timeout | 30 minutes |
| Idle unload TTL | 15 minutes |
| Launch mode | bounded batches |
| Network | curated read-only research tools |
| Paid fallback | forbidden |

The selector is a logical identifier, not a guessed file path. Startup resolves
it against `lms ls --json` after the download has completed. Resolution must
produce exactly one compatible local model. An absent or ambiguous match is a
bounded preflight failure.

Ollama remains a future-compatible transport option and an explicit fallback
runtime, but it is not the default and is not required for the first delivery.
The shared provider contract must not contain LM Studio-specific types so a
later Ollama transport can be added without changing either consumer.

## Architecture

```text
LMStudioLifecycle
  server status/start -> installed-model resolution -> estimate/load -> health
                                      |
                                      v
LocalModelProvider
  structured output | tool calls | usage | zero-dollar receipt | provenance
                    /                                      \
                   v                                        v
LocalArenaRunner                                  LocalProofStrategy
  problem/frame selection                          production scheduling
  bounded tool loop                                existing repository/evolution
  durable turn events                              existing verification kernel
                    \                                      /
                     v                                    v
                  independent computation and Lean verification
```

The components are intentionally separate:

### `LMStudioLifecycle`

Owns runtime discovery and readiness, not inference semantics. It:

1. verifies that `lms` is available;
2. checks `lms server status --json --quiet`;
3. enumerates locally installed models with `lms ls --json`;
4. resolves one installed Qwen3.6 35B A3B revision;
5. starts the server when it is not running;
6. estimates and loads the model with the configured context length, identifier,
   and TTL;
7. checks the loopback API and requested model;
8. returns an immutable runtime identity.

It may execute `lms server start`, `lms load`, status, listing, estimation, and
health commands. It must never execute `lms get`, invoke a download endpoint,
or accept a non-loopback default endpoint.

LM Studio documents programmatic server startup, local model loading,
context-length configuration, GPU offload, and TTL unloading:

- <https://lmstudio.ai/docs/cli/local-models/load>
- <https://lmstudio.ai/docs/developer/core/headless>

### `LocalModelProvider`

Implements the existing provider-neutral `ModelProvider` contract while
remaining separate from `OpenAIProvider`. It uses LM Studio's local compatible
API for structured responses and tool calls but does not inherit OpenAI
pricing, exact-count authorization, model catalogs, or paid-provider retry
assumptions.

The class satisfies two explicit provider-neutral protocols over one local
transport:

- the existing `ModelProvider.generate(request, schema)` protocol for strict
  one-shot structured generation used by production methods;
- a new `ToolCallingModelProvider.next_action(request)` protocol that returns
  either bounded assistant content or typed tool calls for the arena loop.

The arena depends on the tool-calling protocol and production `mathloop`
depends on the existing structured protocol. Neither consumer imports LM
Studio lifecycle or wire-format types.

Each response records:

- runtime and transport type;
- endpoint origin;
- resolved model key, revision/path identity, format, and quantization when
  reported;
- context length and generation configuration;
- prompt/schema/tool-catalog digests;
- provider response ID;
- input, output, and cached token counts when the runtime supplies them;
- wall-clock duration;
- a zero-dollar authorization and receipt under a versioned
  `local-compute-v1` accounting policy.

Zero-dollar receipts preserve the existing invariant that external cognition
has an auditable authorization and settlement record. They do not pretend
local computation has no resource cost.

LM Studio documents host-executed tool loops and compatible structured output:

- <https://lmstudio.ai/docs/developer/openai-compat/tools>
- <https://lmstudio.ai/docs/developer/openai-compat/responses>

### `LocalArenaRunner`

Consumes `LocalModelProvider` and the host tool registry. It operates only in
bounded batches. A turn cannot directly edit canonical arena state.

### `LocalProofStrategy`

Consumes the same provider inside production `mathloop`. It is a separate
method family from paid `proof_sketch` and Codex strategies so results can be
compared without conflating their provenance.

## Local-only authority boundary

Local mode is a separate runtime authority mode, not another boolean that can
accidentally coexist with the existing modes. Exactly one external cognition
mode may be active:

- none;
- local;
- OpenAI API;
- Codex.

When local mode is active:

- OpenAI and Codex methods refuse registration;
- non-loopback inference endpoints are rejected by default;
- `OPENAI_API_KEY`, `CODEX_API_KEY`, and other configured paid-provider
  credentials are removed from every model/tool child environment;
- the runtime cannot construct a paid client;
- no error path may fall back to an external provider;
- local-provider receipts must settle at exactly zero database USD;
- the source and verifier authority rules remain unchanged.

Curated research tools are allowed to access approved public services. They
receive only explicit query strings or public identifiers, never the full
notebook, system prompt, unpublished proof text, environment, or credentials.
Local-only mode registers only unmetered research backends: public
unauthenticated endpoints, direct URL retrieval, or a configured local search
service. A backend requiring a paid API key, prepaid credits, or usage billing
is rejected rather than silently consuming a non-inference budget.

## Arena turn data flow

Each turn performs these phases:

1. **Snapshot.** Read an immutable view of the problem pool, ledger tail,
   selected notebooks, prior attempts, unresolved verification work, and
   method/frame metrics.
2. **Select.** Choose both a target and a method/frame portfolio from a seeded
   policy. A nonzero fair lane samples underused problems and frames.
3. **Orient.** Construct a bounded prompt from the selected durable state.
4. **Act.** Ask the model for one structured action at a time and execute only
   registered host tools.
5. **Observe.** Hash and return bounded tool results to the model.
6. **Conclude.** Require a strict final turn record rather than free-form prose.
7. **Verify.** Independently evaluate every positive mathematical claim.
8. **Materialize.** The host validates and writes accepted durable state.
9. **Learn.** Feed independently classified outcomes into problem and
   method/frame selection.

The maximum model steps, output tokens, wall-clock time, subprocess count,
subprocess time, artifact bytes, research queries, and context bytes are
configured and enforced by the host.

## Host tool registry

The initial allowlist contains:

- bounded reads from approved repository and `.timeloop` paths;
- durable-artifact and prior-receipt inspection;
- bounded Python experiments in a temporary task directory;
- Lean compilation against the arena toolchain;
- existing safe mathematical search libraries;
- OEIS lookup;
- arXiv/Crossref lookup;
- selected web search and URL fetch through a host adapter;
- staging of a proposed turn record and notebook update.

No generic shell tool is exposed. Tool arguments are typed and validated.
Filesystem tools resolve paths before access and reject traversal, symlink
escape, hidden credentials, user-home paths outside the repository, and
canonical writes. Process tools use explicit argument arrays, a controlled
working directory, a scrubbed environment, timeouts, output limits, and
descendant cleanup.

The model cannot invoke Git, background a process, install dependencies, change
LM Studio state, start another model, mutate the database directly, or call a
paid provider.

## Durable turn record

Every attempted turn produces one append-only event, including failures. The
record contains:

- event and schema versions;
- batch, turn, seed, problem, method, and frame identities;
- exact model/runtime/configuration identity;
- prompt and tool-catalog digests;
- ordered model responses and tool calls;
- tool input/output artifact hashes and bounded previews;
- searched space and computational limits;
- hypotheses, negative results, candidate claims, and caveats;
- novelty queries and captured source metadata;
- independent verification receipts;
- final classification;
- wall time, token usage, and zero-dollar settlement;
- proposed durable changes;
- one concrete next action.

Raw large outputs live in content-addressed artifacts. The event refers to their
hashes. A malformed response, timeout, refusal, tool error, verifier rejection,
or interrupted turn is still a completed durable event with an explicit
failure class.

Canonical notebook and ledger updates are derived from validated turn records.
The model cannot overwrite or delete prior findings. Contradictions append a
correction with provenance.

## Problem and method/frame evolution

Both populations continue changing over time.

Problem selection combines:

- resumable `next_action` work;
- newly ingested problems;
- previously parked or failed targets eligible for revival;
- a nonzero fair exploration lane;
- a held-out evaluation partition never used for online promotion.

Method/frame selection combines:

- established techniques;
- Prism frame identities and compositions when available;
- model-proposed combinations that remain trial candidates;
- posterior performance on related but distinct problems;
- retirement for repeated invalid, redundant, or unproductive outcomes;
- revival when new evidence or tools change expected tractability;
- a nonzero fair exploration lane.

The model may propose a new frame or combination, but only the host can register
it. Promotion consumes independently verified downstream outcomes. Model
self-assessment, eloquence, token count, or agreement with another instance of
the same model is not fitness evidence.

## Failure semantics and recovery

- Preflight failures occur before a turn or durable problem claim.
- Transport failures may be retried only before a tool side effect and within
  the turn deadline.
- Tool calls use stable invocation IDs. Replay returns the existing receipt
  rather than re-running a completed side effect.
- After the first tool side effect, failures are recorded and the turn ends or
  resumes from its durable event; the provider request is not blindly retried.
- A lease marks the active turn. Startup expires stale leases and records one
  transition without inventing model or verifier evidence.
- Partial model output is never parsed as a final turn record.
- Invalid structured output receives bounded repair attempts, then becomes an
  invalid-model-output event.
- LM Studio crashes do not activate another provider.
- A model missing after preflight is a capability-unavailable event, not a
  reason to download it.

## Operator interface

The CLI surface is:

```text
mathloop local init
mathloop local status
mathloop local arena --turns 20 --seed 1
mathloop local run --cycles 5 --workers 1
```

`local init` is non-destructive with respect to arena state. It verifies the
CLI, installed model, server, loopback endpoint, structured output, tool-call
round trip, and zero-dollar receipt. It may start the server and load the
already-installed model.

The controller never stops a server that was already running. Batch completion
relies on the model TTL to release memory and leaves the LM Studio service
available. Server shutdown is outside this delivery.

`local status` is read-only.

`local arena` executes bounded `.timeloop` turns. The default model concurrency
is one regardless of `--turns`.

`local run` enables the local method inside production scheduling. Its worker
count governs verifier/tool work; local model generation remains serialized by
the configured concurrency gate.

There is no `--continuous` or paid-fallback option in this delivery.

## Configuration

Local settings use the existing `MATHLOOP_` configuration discipline and
include:

- external cognition mode;
- runtime name;
- `lms` executable path;
- logical model selector;
- local API base URL;
- stable loaded-model identifier;
- context length;
- idle TTL;
- model concurrency;
- generation and turn limits;
- curated research-service enablement and rate limits.

Settings validate the local-only invariants before constructing runtime
components. Secrets are not accepted as local-provider configuration.

## Verification strategy

### Unit tests

Cover:

- installed-model resolution and ambiguity;
- server status/start and model estimate/load command construction;
- the absence of any download command;
- loopback URL validation;
- external-mode mutual exclusion;
- credential scrubbing;
- zero-dollar authorization and settlement;
- model/config identity;
- structured response and tool-call parsing;
- usage normalization;
- deadlines, malformed output, refusal, and retry boundaries;
- tool path/process/network policies;
- deterministic selection and nonzero exploration;
- strict turn-record validation.

### Fake-server integration tests

Exercise:

- health and model discovery;
- structured output;
- multi-step host tool calls;
- duplicate invocation replay;
- transport failure before and after side effects;
- model timeout and cancellation;
- stale-turn recovery;
- artifact hashing and bounded previews;
- canonical-state materialization only after validation.

### Arena acceptance

Prove that:

- false proof claims are rejected;
- a positive control compiles in Lean;
- negative results survive a failed turn;
- the model cannot directly alter the notebook or ledger;
- novelty research is captured with query provenance;
- problem and frame exploration remain nonzero;
- repeated runs are bounded and resumable;
- the existing dirty `.timeloop/exam/results.jsonl` user change is preserved.

### Production integration

Prove that:

- local, OpenAI, and Codex modes cannot coexist;
- local receipts satisfy repository billing invariants at zero USD;
- local leads enter existing provenance and verification paths;
- promotion uses independently verified outcomes;
- local-provider failure cannot consume or reserve a paid budget.

### Real-model canary

After Qwen3.6 35B A3B finishes downloading:

1. run `mathloop local init`;
2. verify exact resolved model identity;
3. perform one read-only arena turn;
4. perform one bounded tool-using turn;
5. reject one deliberate false mathematical claim;
6. accept one machine-checkable positive control;
7. confirm no paid-provider event, authorization, or credential exposure;
8. confirm all durable changes and artifacts match their receipts.

The live canary is explicit because it consumes local compute and time even
though it incurs no metered inference charge.

## Measuring improvement

The online arena may adapt from live outcomes. Evaluation uses a frozen
held-out set plus a changing live set. Reported metrics include:

- valid structured-turn rate;
- tool-call validity and repair rate;
- verified lead rate;
- false-positive and verifier-rejection rates;
- distinct problems and frames explored;
- resumptions versus cold starts;
- negative-result reuse;
- wall time and tokens per verified outcome;
- performance on unseen held-out problems.

The grader cannot share an implementation with the examinee. Lean and
deterministic computation remain the principal positive controls. Model-based
critique is diagnostic only.

## Delivery sequence

1. Implement and verify the shared local lifecycle/provider and hard local-only
   boundary.
2. Implement the durable `.timeloop` agent, tool registry, and bounded CLI.
3. Register the production local method and repository accounting.
4. Complete fake-server and acceptance verification.
5. Run the real Qwen3.6 canary when the installed model is available.
6. Run an initial controlled arena batch and review its calibration before
   increasing turn count.

## Acceptance criteria

The work is complete when:

- both `.timeloop` and production `mathloop` consume the same local provider;
- LM Studio can be started and the installed Qwen3.6 model loaded without a
  download path;
- local mode has a mechanically enforced no-paid-provider boundary;
- bounded tool-using arena turns produce append-only, reproducible records;
- canonical state changes only after host validation;
- positive claims require independent verification;
- problem and method/frame populations retain nonzero exploration;
- zero-dollar receipts preserve usage and provenance;
- the full offline test suite passes;
- the real-model canary passes against the installed Qwen3.6 35B A3B revision.

If the approved model has not finished downloading, implementation may reach
code-complete status, but the feature is not release-ready and no successful
local-runtime claim may be made until the real-model canary passes.
