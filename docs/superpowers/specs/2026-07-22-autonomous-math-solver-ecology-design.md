# Autonomous Mathematics Solver Ecology

**Date:** 2026-07-22
**Status:** Approved design
**Scope:** A local-first system that continuously discovers mathematical conjectures, attacks many of them with diverse methods, verifies candidate results, and improves both problem selection and solving methods over time.

## 1. Purpose

Build an autonomous research system that treats each solver run as a disposable worker and the persistent computer as the continuous agent. The system must:

- Continuously acquire and revisit real mathematical problems.
- Try many bounded, substantially different approaches.
- Preserve exact evidence and negative results across runs.
- Promote claims only through independent machine verification.
- Evolve problem-selection policies and solving methods over time.
- Demonstrate improvement on newly arriving or held-out problems rather than only increasing output volume.

The design is inspired by the time-loop thought experiment: a worker loses all internal state after a bounded interval, while a computer outside the loop retains the task definition, notes, artifacts, programs, and experiment history. The persistent system is therefore the actual long-lived intelligence.

## 2. Governing Principle

The system is not one optimal mathematics agent. It is a persistent computational ecology governed by a small set of stable rules.

The immutable rules preserve truth, evidence, continuity, diversity, resource limits, and fair access to compute. Prompts, models, tools, decompositions, search procedures, and scheduling preferences remain replaceable and evolvable.

This is the wing-flapping lesson: preserve the required function and measurable feedback loop without assuming in advance what a successful solver must look like. Do not optimize mechanisms whose effects cannot yet be measured.

## 3. Goals and Non-Goals

### Goals

- Maximize verified mathematical progress per unit of compute while retaining broad exploration.
- Maintain a nonstationary population of sourced conjectures.
- Maintain a versioned population of executable solving methods.
- Find exact counterexamples, proofs, corrected statements, useful lemmas, and well-supported partial results.
- Make every important result reproducible from stored artifacts.
- Recover cleanly from worker, model, tool, and host interruptions.
- Support local exact tools first and external services through optional adapters.
- Produce a human-review queue for externally publishable claims.

### Non-goals for the first version

- Automatically publish papers, contact researchers, or make public novelty claims.
- Claim that numerical evidence is a proof.
- Solve arbitrary undecidable, unverifiable, or physically nonpersistent tasks.
- Build a large unrestricted agent swarm before the core learning and verification loop is validated.
- Treat model confidence, eloquence, or consensus as mathematical verification.
- Make Prism or Engram the canonical evidence store.

## 4. Completion Guarantee and Its Limits

For tasks with finitely representable candidates, a terminating deterministic verifier, at least one valid candidate, durable storage, and fair allocation of unbounded cumulative compute, exhaustive enumeration eventually finds a solution.

The production system combines:

1. A **heuristic engine** that uses models, tools, retrieval, learned routing, and domain-specific search for practical speed.
2. A **completeness engine** that reserves a fixed nonzero compute share for fair dovetailing over candidates, programs, proof terms, or bounded search branches.

The completeness claim does not cover tasks without solutions, changing or noisy success conditions, uncomputable properties, truths not expressible or provable in the selected formal system, finite resource exhaustion, or physical progress erased by the environment.

## 5. System Architecture

```text
Problem sources
      |
      v
Discover -> Normalize -> Triage -> Schedule bounded experiments
   ^                                      |
   |                                      v
Revisit <- Learn <- Record <- Verify <- Execute in sandbox
                                  |
                                  v
                     Candidate and human-review queues
```

### 5.1 Kernel responsibilities

The stable kernel owns:

- The append-only event log and state projections.
- Immutable source snapshots and versioned normalized statements.
- Durable experiment leases and recovery.
- Resource and monetary budgets.
- Artifact hashing and provenance.
- Method registration and versioning.
- Scheduler policy boundaries, including diversity and completeness allocations.
- Claim state transitions and verifier authority.
- Audit logs for external actions.

The orchestrator may schedule work but may not mark mathematical claims verified.

### 5.2 Stateless workers

Workers are replaceable and bounded. Each worker:

1. Validates its runtime and task lease.
2. Reads the exact problem version, method version, dependencies, and budget.
3. Executes one independently finishable experiment.
4. Writes checkpoints during the run.
5. Commits structured outcomes, logs, code, and artifacts.
6. Releases or expires its lease without retaining private state.

Target experiment duration is materially shorter than the worker lifetime so artifacts can be committed safely.

### 5.3 Optional Prism and Engram roles

- **Prism** may propose attention allocation, maintain approach diversity, and expose search-family coverage.
- **Engram** may retrieve cross-task strategies, compressed lessons, and relevant prior context.
- The **canonical ledger and artifact store** remain authoritative for tasks, experiments, evidence, and claim status.
- A verifier never accepts an Engram memory or Prism score as mathematical evidence.

The first implementation must function correctly without either optional integration. Their currently incomplete live routing must not block the core system.

## 6. Canonical Data Model

### Problem

- Stable identifier and version.
- Original source URI, citation, timestamp, and immutable source snapshot hash.
- Verbatim source statement within copyright limits or an exact location reference.
- Normalized, quantifier-complete statement.
- Assumptions, definitions, domain, and known dependencies.
- Formalization and executable-checker status.
- Feature vector used for routing.
- Status, priority, and quarantine reason when applicable.

### Approach

- Stable family identifier and immutable version.
- Executable workflow definition, not only a prompt.
- Model, tool, decomposition, and search configuration.
- Applicability predicates over problem features.
- Parent versions and composition lineage.
- Resource envelope and required verifier type.
- Performance history separated into development and held-out evaluations.

### Experiment

- Problem version and approach version.
- Deterministic configuration, seed, environment, and dependency hashes.
- Lease owner, checkpoints, resource use, and cost.
- Input and output artifacts.
- Structured outcome classification.
- Infrastructure-failure status distinct from mathematical failure.

### Artifact

- SHA-256 content address.
- Media/type classification.
- Producer experiment and dependency lineage.
- Reproduction command and environment description.
- Integrity and retention status.

### Claim

- Type: proof, disproof, corrected statement, partial lemma, bound, or negative result.
- Exact claim statement and relation to the source problem.
- Supporting artifacts.
- Verification level and independent evaluation history.
- Novelty and human-review status.

### Evaluation

- Evaluator and verifier versions.
- Inputs, outputs, and exact acceptance criteria.
- Reproducibility result.
- Statement-fidelity result.
- Literature and novelty findings.
- Human review when present.

## 7. Problem Lifecycle

```text
discovered
  -> normalized
  -> eligible
  -> active
  -> candidate_result
  -> machine_verified
  -> novelty_checked
  -> human_reviewed
  -> release_ready
```

Side states include `quarantined`, `duplicate`, `known_resolved`, `statement_defect`, `budget_exhausted`, and `revisit_later`.

Ambiguous, under-specified, or unfaithfully formalized statements are quarantined. Discovering a missing assumption creates a statement-defect claim rather than silently weakening the problem.

## 8. Co-Evolving Problem Population

The problem set is a stream rather than a fixed benchmark.

### 8.1 External sources

Initial adapters target:

- OpenConjecture exports.
- DeepMind Formal Conjectures.
- OEIS conjecture and sequence records where licensing and access permit.
- Curated arXiv or journal sources.
- Manually supplied calibration suites.

Every import is snapshotted, attributed, deduplicated, and versioned. Source changes never overwrite prior versions.

### 8.2 Internal derived work

The system may create clearly labeled child problems:

- Lemmas required by a proof plan.
- Small and boundary cases.
- Hypothesis-removal mutations.
- Finite restrictions suitable for exhaustive testing.
- Corrected formulations suggested by counterexamples.

Derived problems may guide search but cannot be misrepresented as the original conjecture.

### 8.3 Scheduling portfolio

The scheduler maintains configurable allocations across:

- High expected verified progress.
- Newly ingested conjectures.
- Underexplored mathematical domains.
- Previously failed problems reopened by new capabilities.
- Random or novelty-selected problems that counter scheduler bias.
- A rolling unseen evaluation cohort excluded from method tuning.

No static benchmark becomes the whole operating environment.

## 9. Co-Evolving Method Population

A method is a versioned program or workflow that may contain prompts but is not reducible to them.

### 9.1 Initial method families

- Small-case and boundary enumeration.
- Counterexample and minimal-witness search.
- Hypothesis attack and statement-audit procedures.
- SageMath exact symbolic and algebraic computation.
- SAT, SMT, constraint, and MILP encodings.
- Graph generation and finite-structure search.
- Model-generated proof sketches and lemma decomposition.
- Lean formal proof search and proof repair.
- Independent critic and artifact reproducer.
- Literature retrieval and novelty audit.

### 9.2 Evolution operations

Methods may be:

- Parameter-mutated.
- Prompt-mutated.
- Tool-augmented.
- Composed with other methods.
- Specialized to problem niches.
- Compared against their parents.
- Retired, archived, revived, or promoted.

Promotions require measurable improvement on a rolling unseen cohort under comparable budgets. Method versions are immutable after evaluation.

### 9.3 Contextual routing

The router estimates:

```text
expected verified progress(problem features, method version, budget)
```

Performance is contextual rather than a single global ranking. The scheduler preserves distinct strategy niches and prevents winner-take-all allocation.

## 10. Scheduler Policy

The scheduler balances:

- Exploitation of promising problem-method pairs.
- Exploration of uncertain methods and domains.
- Novelty and strategy diversity.
- Independent verification and adversarial review.
- Guaranteed completeness-lane progress.
- Cost, runtime, and external API budgets.

Required controls:

- A nonzero minimum allocation for completeness search.
- A nonzero minimum allocation for novel methods and problem domains.
- Per-problem, per-method, per-provider, and global budgets.
- Backoff and quarantine for repeated infrastructure errors.
- Diminishing priority for duplicate or low-information experiments.
- Reopening triggers when a relevant tool, method, or formal library changes.

The first scheduler may use explicit portfolio weights and contextual bandit estimates. More complex evolutionary scheduling is added only after metrics show where it helps.

## 11. Tool and Provider Substrate

All integrations implement narrow plugin contracts:

```text
ProblemSource
SolverMethod
ToolBackend
Verifier
ModelProvider
SchedulerPolicy
```

### Local-first exact tools

- SageMath for algebra, number theory, combinatorics, and exact computation.
- SymPy for lightweight symbolic workflows.
- Lean and Mathlib for kernel-checked proof certificates.
- Z3, SAT solvers, and MILP solvers for finite and optimization problems.
- Graph enumeration libraries for finite combinatorics.

### Optional external tools

- Wolfram services for exploration, transformations, and independent cross-checks.
- Multiple model providers for proposal, formalization, criticism, and repair.
- Literature and metadata services for provenance and novelty checks.

External answers are evidence inputs, not automatic certificates. Important outputs are reduced to locally reproducible checks whenever possible.

## 12. Verification and Claim Promotion

### 12.1 Evidence levels

```text
lead
  -> computationally_supported
  -> reproducible_witness
  -> formally_verified
  -> novelty_checked
  -> human_reviewed
```

Not every valid result requires every level, but labels must accurately describe the evidence. Numerical experiments remain `computationally_supported`; they do not become proofs through repetition.

### 12.2 Independent verification

The verifier worker receives the source statement, candidate artifact, and reproduction instructions without the proposing model's persuasive narrative. It runs in a fresh environment.

Important results require two independent reproductions or a kernel-checked certificate plus an independent statement-fidelity review.

### 12.3 Statement integrity

- Source statements are immutable.
- Normalizations and formalizations are separately versioned.
- Equivalence between versions is an explicit auditable claim.
- Verifiers cannot be modified by the method under evaluation.
- A verifier change invalidates or requeues dependent evaluations.

### 12.4 Novelty and release

Machine verification establishes correctness relative to the encoded statement, not novelty or significance. Literature retrieval, source comparison, and human expert review remain separate gates before public release.

## 13. Safety and Authority Boundaries

Generated code executes with:

- CPU, memory, process, and wall-clock limits.
- Restricted filesystem mounts.
- Network disabled unless the experiment explicitly requires it.
- No mounted API credentials.
- Captured dependencies, random seeds, logs, and exit status.
- Killable leases and retry ceilings.

The autonomous system may discover, schedule, execute, verify, learn, and prepare reports. It may not autonomously:

- Change spending-policy ceilings.
- Publish results.
- Contact authors or third parties.
- Weaken canonical conjectures.
- Replace canonical verifiers.
- Grant itself new external authority.

## 14. Durability and Recovery

- State changes are append-only events projected into queryable current-state tables.
- Large artifacts are immutable and content-addressed.
- Experiments use renewable leases and idempotency keys.
- Workers checkpoint before their time budget expires.
- Expired leases are safely reclaimed.
- Retries distinguish transient infrastructure errors from mathematical outcomes.
- Periodic snapshots accelerate recovery without replacing the event log.
- Database and artifact backups are verified by restoration tests.

## 15. Measuring Real Improvement

Primary metrics:

- Machine-verified results per compute and monetary cost.
- Independent reproduction rate.
- False-positive rate, treated as a hard quality constraint.
- Performance lift over fixed baseline methods.
- Performance on newly arriving and held-out problems.
- Time from discovery to first useful artifact.
- Duplicate-work rate.
- Reopened-problem success after method improvements.
- Domain coverage and method-population diversity.
- Useful partial results and eliminated search regions.

The system has not improved merely because it generated more tokens, attempts, or confident reports.

## 16. Technology Decisions

### Initial implementation

- Python 3.13 managed with `uv` for orchestration and plugins.
- PostgreSQL for events, projections, durable leases, and metrics.
- A content-addressed local artifact directory with a future object-store interface.
- Docker for sandboxed experiments.
- Database-backed work claiming rather than a separate message broker.
- SageMath as the first exact backend because it is already installed locally.
- Lean/Mathlib and Z3 installed as subsequent verifier backends.
- Wolfram integration remains optional and credential-gated.
- Model access is provider-neutral and budget-controlled.

### Rationale

PostgreSQL provides robust concurrent leases and transactional state transitions without requiring an additional queue service. A local content store keeps early operation inspectable. Plugin interfaces keep models and mathematical tools replaceable.

## 17. First Autonomous Vertical Slice

The first end-to-end release will:

1. Initialize the event ledger, projections, artifact store, and durable leases.
2. Import a controlled collection of real conjectures plus solved and deliberately falsified calibration problems.
3. Normalize, classify, version, and deduplicate them.
4. Implement bounded SageMath, small-case, boundary, counterexample, proof-sketch, critic, and reproduction methods.
5. Execute generated code in restricted Docker sandboxes.
6. Verify exact witnesses independently.
7. Run continuously under fixed local and API budgets.
8. Maintain a static baseline scheduler and an adaptive scheduler.
9. Evolve method parameters and routing policies.
10. Evaluate both schedulers on a rolling unseen cohort.
11. Reopen old problems when capability changes are relevant.
12. Produce review queues for verified candidates, statement defects, and useful partials.

### Acceptance criteria

- No planted false proof reaches `machine_verified`.
- Known counterexamples are rediscovered with exact witnesses.
- Selected known elementary results are reconstructed and reproduced.
- Worker termination and host restart do not corrupt state or lose committed evidence.
- Duplicate work decreases as the ledger accumulates evidence.
- Adaptive routing outperforms static baselines on unseen problems under comparable budgets.
- Compute and API ceilings are enforced.
- Every promoted claim can be reproduced from stored artifacts.

## 18. Deferred Capabilities

- Large CDC-style multi-agent swarms for selected high-value problems.
- Automatic translation across multiple proof assistants.
- Distributed workers across hosts.
- Learned conjecture generation as a primary source.
- Automated paper drafting and external collaboration workflows.
- Direct public release without human approval.

## 19. Research Basis

The architecture incorporates lessons from:

- [OpenAI's Cycle Double Cover proof artifacts](https://github.com/openai/cdc-lean): rigorous task contracts, diverse sustained search, and kernel checking.
- [DeepMind's formal proof-search study](https://arxiv.org/abs/2605.22763): autonomous open-problem search with formal verification.
- [OpenConjecture](https://github.com/davisrbr/conjectures-arxiv): continuous conjecture extraction, solver pilots, and audits exposing statement and verification failures.
- [Formal Conjectures](https://github.com/google-deepmind/formal-conjectures): the importance of formal-statement fidelity and correction tracking.
- [AlphaEvolve](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/): executable evaluators and evolutionary improvement over program populations.

## 20. Approved Design Decisions

- Use the persistent solver-ecology architecture.
- Continuously evolve both the problem population and method population.
- Optimize for broad autonomous search with verified progress per unit of compute.
- Keep a complete-search allocation alongside heuristic search.
- Use independent verification and immutable source statements.
- Allow autonomy through verified candidate production but require approval for public claims and expanded external authority.
- Build and validate a constrained vertical slice before large swarms.
