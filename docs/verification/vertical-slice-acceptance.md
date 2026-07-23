# Autonomous Mathematics Vertical Slice Acceptance

Evidence recorded on 2026-07-22 from the `feature/autonomous-math` worktree on
macOS arm64 with Python 3.13.5. Model access was disabled and
`OPENAI_API_KEY` was absent, so no live API call is represented as evidence.

## Automated verification

```text
$ uv run pytest -q
555 passed in 90.93s

$ uv run ruff check src tests
All checks passed!

$ uv run mypy src
Success: no issues found in 39 source files
```

The suite uses real PostgreSQL transactions and covers leases, idempotent
events, retry and billing recovery, concurrent schedulers, atomic paired
evaluations, provenance migration, independent verification, reporting, and
reproduction.

The Sage sandbox was rebuilt explicitly for `linux/amd64` from the Dockerfile's
pinned upstream digest. The runtime invokes the inspected immutable local image
ID, never the mutable build tag:

```text
$ docker image inspect mathloop-sage:10.9 \
    --format '{{.Id}} {{.Architecture}} {{json .RepoDigests}}'
sha256:6d0efd1d82d33eb5f6450af740d080a550c2b52948c0c5a34849c6d3c5004251 amd64 \
["mathloop-sage@sha256:6d0efd1d82d33eb5f6450af740d080a550c2b52948c0c5a34849c6d3c5004251"]

$ uv run pytest -q tests/integration/test_sage_sandbox.py
1 passed

$ uv run pytest -q tests/e2e/test_autonomous_cycle.py
1 passed
```

Through that exact ID, Sage produced Euler's counterexample
`{"n": 40, "value": 1681}` and independently checked both the sum-of-odds and
sum-of-integers induction certificates. Its bounded-search predicates also
evaluate the finite sums before comparing them with their closed forms. The
operator preflight inspects this same exact image ID. The sandbox remains
networkless, read-only, capability-dropped, PID/memory/CPU limited, and time
bounded.

## Offline operator outcome

The deterministic corpus now contains three development problems and three
unseen holdout problems. Generic exploitation, novelty, and completeness lanes
cannot consume holdout rows; only explicit evaluation lanes can access them.

Three default offline cycles produce canonical, executed comparison rows:

- Method evolution evaluates `fixed_parent` and `candidate_method` on the same
  two unseen quadratic problems. Both receive two experiments, two attempts,
  200 allocated search work units, and zero cost. The fixed parent verifies
  `0/2`; the boundary-first candidate verifies `2/2` and is promoted.
- Routing evaluation compares `static_routing` with development-informed
  contextual-UCB routing on the same unseen sum-of-integers identity. Both
  receive one allocation unit, one attempt, and zero cost. Static routing sends
  bounded integer search and verifies `0/1`; adaptive routing selects symbolic
  induction and verifies `1/1`.
- `static_vs_adaptive_routing_holdout.observed_lift` reports
  `verified_per_attempt`: fixed `0`, adaptive `1`, absolute lift `1`.

These values come from persisted experiment, claim, evaluation, work, and cost
rows. No score or outcome is injected by the acceptance test. Method-evolution
evidence is reported separately from policy-routing evidence.

The review queue contains independently verified Euler and Fermat
counterexamples, a Sage-verified sum-of-odds proof, and a Sage-generated Euler
claim that the independent Python verifier accepts. Every review item includes
the exact experiment config and seed, method and verifier provenance, artifact
digest, immutable source identity, and a local reproduction command.
Reproduction checks the artifact digest and the entire
method → experiment → artifact provenance chain before rerunning the fixed
verification kernel.

## Security and recovery acceptance

- Generator and verifier predicate registries are independent. Fault injection
  into either side cannot cause the same defect to manufacture and approve a
  claim.
- No repository promotion sink accepts a caller-computed `Verification` or
  transferable attestation. The promotion entrypoint reloads the canonical
  claim and problem and constructs the parameterless fixed kernel internally.
  The kernel constructs its fixed registry and exact immutable Sage runner;
  caller-configured solver runners cannot reach verification. The repository
  validates the fixed verifier/version and current verifier provenance before
  persisting the result.
- External-capable children block at a dispatch gate. The parent commits the
  durable dispatch marker before acknowledging and releasing the provider
  boundary. Process-start and marker-transaction failures remain confirmed
  pre-dispatch zero-cost retries; committed or ambiguous dispatches are
  conservatively settled and never automatically re-executed.
- Spawn authorization is thread-local. A legitimate supervised `Popen` in one
  thread cannot authorize raw fork, spawn, multiprocessing, shell, or aliased
  process creation in another.
- Execution provenance hashes every `src/mathloop/**/*.py` path and byte
  sequence, `uv.lock`, runtime environment identity, and—where applicable—the
  Dockerfile, Sage runner, pinned base, and exact image ID. The worker rejects a
  missing, malformed, stale, or mismatched identity before budget reservation
  or solver execution.
- Existing unstamped or superseded stamped method epochs are never relabeled
  with current provenance. Under the family advisory lock, startup archives
  stale active/candidate versions, permanently fails their queued/leased work,
  resets family completeness cursors, and rebuilds them only from active
  exact-identity executions. Registration then allocates the next free family
  version; a stale v1 parent plus v2 candidate upgrades safely to v3, and a
  restart is idempotent. Reports expose unstamped methods, experiments, and
  claims as `legacy_unreproducible`, while excluding them from scheduling,
  resolution suppression, scoring, promotion, pending verification, and
  review. Those operational paths require an active method and exact
  method/experiment/artifact provenance identity chain.
- Paired evolution and routing experiments are enqueued transactionally. Their
  policy identity, selected method, common problem, allocation, work, attempts,
  and spend remain separately auditable and do not inflate ordinary duplicate
  work metrics.
- Content-addressed artifact writes fsync the file, containing shard directory,
  and each newly created ancestor directory entry before publication. Ingest
  output derives processed, inserted, and already-existing counts from the
  invocation's per-snapshot transactional result.

## Remaining limitations

Novelty remains explicitly `unchecked`; there is no publication action or
human-review workflow in this slice. API-backed proof sketches remain
credential- and flag-gated. The pinned Sage image is amd64 and runs through
Docker emulation on this arm64 acceptance host.
