# Codex Autonomous Promotion and Rollback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow Codex agents to propose, independently review, canary, and automatically promote safe solver/tactic/source-policy changes while keeping the stable supervisor, verification authority, credentials, host checkout, and rollback controller outside the self-modifying runtime.

**Architecture:** Automatic changes land only in a dedicated clean runtime clone and a narrow allowlisted surface. Autonomous Python methods execute in a networkless, read-only, capability-dropped container with no host home, database, Docker socket, or Codex credentials. A stable host supervisor classifies patches, runs fixed checks, requests a fresh read-only Sol review, performs equal-budget held-out canaries, serializes merges into the runtime clone's `main`, restarts runtime workers, and creates ordinary revert commits on regression.

**Tech Stack:** Python 3.13, Git/Git worktrees, Codex CLI, PostgreSQL 17, Pydantic 2, Docker, pytest, Ruff, mypy.

## Global Constraints

- Complete the supervisor-foundation and research-intake plans first.
- Initial autonomous-method image target is `linux/arm64` on the approved macOS arm64 host; another platform requires a separately inspected manifest and human-reviewed provenance update.
- Limit successful automatic promotions to five per budget day and serialize them one at a time.
- Never auto-promote changes to verification, accounting, containment, provenance, promotion, dependencies, locks, Docker definitions, migrations, existing tests, or authority configuration.
- Treat any mixed safe/trust-root patch as entirely human-gated.
- Auto-promotable Python lives only under `src/mathloop/autonomous_methods/` and runs only in the dedicated restricted container.
- Auto-promotable declarative files live only under `data/autonomous/`.
- Existing test edits/deletions are human-gated; new tests may live under `tests/autonomous/`.
- The operator checkout is never mutated by automatic promotion. The canonical self-modifying runtime uses a dedicated clean clone under `.mathloop/runtime-repo`.
- The stable supervisor/promotion controller always executes from the operator-approved installation, not from candidate/runtime code.
- Every merge requires fixed gates, a fresh read-only Sol review, an equal-budget canary, compare-and-swap confirmation of runtime `main`, and rollback metadata.
- Mathematical publication remains human-gated.

---

## File Structure

- `src/mathloop/promotion/domain.py` — immutable candidate, review, canary, promotion, and rollback models.
- `src/mathloop/promotion/policy.py` — exact path/change/AST/declarative allowlist.
- `src/mathloop/promotion/runtime_repo.py` — dedicated clone and compare-and-swap Git operations.
- `src/mathloop/promotion/checks.py` — fixed command gates and evidence capture.
- `src/mathloop/promotion/review.py` — fresh schema-constrained Sol review.
- `src/mathloop/promotion/canary.py` — equal-budget parent/candidate evaluation.
- `src/mathloop/promotion/controller.py` — durable serialized state machine.
- `src/mathloop/autonomous_methods/sdk.py` — narrow method input/output contract.
- `src/mathloop/autonomous_methods/runner.py` — container entrypoint.
- `docker/autonomous-method/Dockerfile` — pinned networkless runtime image.
- `src/mathloop/tools/autonomous_method.py` — exact-image host runner.
- `src/mathloop/storage/schema.sql` and `repository.py` — promotion projections.
- `src/mathloop/cli.py` and `reporting.py` — operator controls and audit output.

Tests:

- `tests/unit/test_promotion_domain.py`
- `tests/unit/test_promotion_policy.py`
- `tests/unit/test_runtime_repo.py`
- `tests/unit/test_promotion_checks.py`
- `tests/unit/test_promotion_review.py`
- `tests/unit/test_promotion_canary.py`
- `tests/unit/test_autonomous_method_runner.py`
- `tests/integration/test_promotion_repository.py`
- `tests/integration/test_autonomous_method_sandbox.py`
- `tests/integration/test_promotion_controller.py`
- `tests/e2e/test_autonomous_promotion.py`

---

### Task 1: Durable Promotion State Machine

**Files:**
- Create: `src/mathloop/promotion/__init__.py`
- Create: `src/mathloop/promotion/domain.py`
- Modify: `src/mathloop/storage/schema.sql`
- Modify: `src/mathloop/storage/repository.py`
- Test: `tests/unit/test_promotion_domain.py`
- Test: `tests/integration/test_promotion_repository.py`

**Interfaces:**
- Produces: `PatchCandidate`, `PromotionReview`, `CanaryDecision`,
  `PromotionStatus`, and `RollbackRecord`.
- Produces: repository create/transition/lease/evidence/reconcile methods.

- [ ] **Step 1: Write failing immutable-transition tests**

```python
def test_promotion_requires_ordered_gate_evidence(repository: Repository) -> None:
    candidate = repository.create_patch_candidate(candidate_payload)
    repository.record_policy_decision(candidate.id, approved_policy)
    with pytest.raises(InvalidPromotionTransition):
        repository.mark_promotion_ready(candidate.id)
    repository.record_check_run(candidate.id, passing_checks)
    repository.record_review(candidate.id, approving_review)
    repository.record_canary(candidate.id, passing_canary)
    ready = repository.mark_promotion_ready(candidate.id)
    assert ready.status is PromotionStatus.READY


def test_terminal_promotion_evidence_is_immutable(repository: Repository) -> None:
    merged = merged_candidate(repository)
    with pytest.raises(ImmutableProjectionConflict):
        repository.record_review(merged.id, different_review)
```

Also cover exact replay, concurrent lease acquisition, five-per-day limit,
single active promotion, expired pre-merge lease, merged-state reconciliation,
rollback-required state, revert completion, and no deletion.

- [ ] **Step 2: Verify red**

```bash
uv run pytest -q tests/unit/test_promotion_domain.py tests/integration/test_promotion_repository.py
```

Expected: promotion types/tables/methods are absent.

- [ ] **Step 3: Implement models and schema**

Statuses:

```python
class PromotionStatus(StrEnum):
    PROPOSED = "proposed"
    HUMAN_GATED = "human_gated"
    POLICY_APPROVED = "policy_approved"
    CHECKS_PASSED = "checks_passed"
    REVIEW_APPROVED = "review_approved"
    CANARY_PASSED = "canary_passed"
    READY = "ready"
    MERGING = "merging"
    MERGED = "merged"
    REJECTED = "rejected"
    ROLLBACK_REQUIRED = "rollback_required"
    REVERTED = "reverted"
```

`PatchCandidate` binds candidate ID, originating Codex turn, base SHA, patch
SHA-256, patch size, changed paths/change kinds, task, creation time, and
status. Reviews bind reviewer turn/model/CLI version, candidate/base/patch
identity, verdict, findings, and transcript digest. Canaries bind parent and
candidate commits, problem IDs, seeds, allocations, attempts, turn/token/time
cost, verified/rejected outcomes, and threshold decision.

Add `patch_candidates`, `promotion_evidence`, `promotion_leases`,
`promotion_merges`, and `promotion_rollbacks`. Every transition appends an
event in the same transaction and validates all prerequisite evidence by
candidate identity.

- [ ] **Step 4: Run focused gates**

```bash
uv run pytest -q tests/unit/test_promotion_domain.py tests/integration/test_promotion_repository.py
uv run ruff check src/mathloop/promotion/domain.py src/mathloop/storage/repository.py tests/unit/test_promotion_domain.py tests/integration/test_promotion_repository.py
uv run mypy src/mathloop/promotion/domain.py src/mathloop/storage/repository.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/mathloop/promotion src/mathloop/storage/schema.sql src/mathloop/storage/repository.py tests/unit/test_promotion_domain.py tests/integration/test_promotion_repository.py
git commit -m "feat: persist autonomous promotion state"
```

---

### Task 2: Exact Auto-Promotion Policy

**Files:**
- Create: `src/mathloop/promotion/policy.py`
- Test: `tests/unit/test_promotion_policy.py`

**Interfaces:**
- Produces: `PromotionPolicy.evaluate(base_tree, patch) -> PolicyDecision`.
- Produces: deterministic `human_gated`, `rejected`, or `auto_eligible` result.

- [ ] **Step 1: Write failing exhaustive path/change tests**

Allowed new/modified paths:

```text
src/mathloop/autonomous_methods/*.py
data/autonomous/prompts/*.json
data/autonomous/policies/*.json
data/autonomous/sources/*.json
tests/autonomous/test_*.py          # new files only
docs/autonomous/*.md
```

Tests must prove:

```python
def test_safe_method_and_new_test_are_auto_eligible() -> None:
    decision = policy.evaluate(
        base_tree,
        patch_with(
            "src/mathloop/autonomous_methods/boundary_search.py",
            "tests/autonomous/test_boundary_search.py",
        ),
    )
    assert decision.disposition == "auto_eligible"


@pytest.mark.parametrize(
    "path",
    [
        "src/mathloop/verification.py",
        "src/mathloop/worker.py",
        "src/mathloop/promotion/policy.py",
        "src/mathloop/storage/schema.sql",
        "pyproject.toml",
        "uv.lock",
        "docker/autonomous-method/Dockerfile",
        ".codex/config.toml",
        "tests/unit/test_verification.py",
    ],
)
def test_trust_root_paths_are_human_gated(path: str) -> None:
    assert policy.evaluate(base_tree, patch_with(path)).disposition == "human_gated"
```

Also reject path traversal, absolute paths, symlinks, submodules, binaries,
renames/copies, executable-bit changes, existing-test modifications, any
deletion, over-limit patches/files, NUL/control bytes, secret patterns, and
mixed eligible/human-gated patches.

- [ ] **Step 2: Verify red**

```bash
uv run pytest -q tests/unit/test_promotion_policy.py
```

Expected: policy module is absent.

- [ ] **Step 3: Implement Git-native change parsing and AST/declarative checks**

Read changes from:

```python
raw_argv = ("git", "diff", "--raw", "-z", "--no-renames", base_sha, candidate_sha)
numstat_argv = (
    "git",
    "diff",
    "--numstat",
    "-z",
    "--no-renames",
    base_sha,
    candidate_sha,
)
patch_argv = (
    "git",
    "diff",
    "--binary",
    "--no-ext-diff",
    base_sha,
    candidate_sha,
)
```

Never parse human-formatted filenames. Resolve all paths as POSIX relative
paths and require containment in the allowlist.

For autonomous Python, parse AST and reject imports outside:

```python
SAFE_IMPORT_ROOTS = frozenset(
    {
        "__future__",
        "collections",
        "dataclasses",
        "decimal",
        "fractions",
        "functools",
        "itertools",
        "math",
        "operator",
        "statistics",
        "sympy",
        "typing",
        "pydantic",
        "mathloop.autonomous_methods.sdk",
    }
)
```

Reject `eval`, `exec`, `compile`, `open`, `input`, `breakpoint`, `__import__`,
dunder attribute access, dynamic imports, global/nonlocal statements, and AST
nodes for async/generators when outside the narrow SDK contract. Container
isolation remains the security boundary; AST checks reduce accidental risk.

Validate JSON files with static Pydantic schemas and reject strings containing
code-bearing keys such as `command`, `shell`, `python`, `sql`, `docker`,
`network`, `credential`, or `environment`.

- [ ] **Step 4: Run focused gates**

```bash
uv run pytest -q tests/unit/test_promotion_policy.py
uv run ruff check src/mathloop/promotion/policy.py tests/unit/test_promotion_policy.py
uv run mypy src/mathloop/promotion/policy.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/mathloop/promotion/policy.py tests/unit/test_promotion_policy.py
git commit -m "feat: enforce autonomous patch boundaries"
```

---

### Task 3: Sandboxed Autonomous Method Runtime

**Files:**
- Create: `src/mathloop/autonomous_methods/__init__.py`
- Create: `src/mathloop/autonomous_methods/sdk.py`
- Create: `src/mathloop/autonomous_methods/runner.py`
- Create: `src/mathloop/tools/autonomous_method.py`
- Create: `docker/autonomous-method/Dockerfile`
- Modify: `src/mathloop/provenance.py`
- Modify: `src/mathloop/runtime.py`
- Test: `tests/unit/test_autonomous_method_runner.py`
- Test: `tests/integration/test_autonomous_method_sandbox.py`

**Interfaces:**
- Produces: `AutonomousMethodInput`, `AutonomousMethodOutput`, and
  `AutonomousMethodRunner.run(module_bytes, input)`.
- Registers only policy-approved modules by content digest.

- [ ] **Step 1: Write failing SDK and real sandbox tests**

```python
def test_sdk_round_trip_is_bounded_and_declarative() -> None:
    request = AutonomousMethodInput.model_validate(
        {
            "statement": "Find a counterexample below 100.",
            "checker": {"kind": "lead_only"},
            "seed": 7,
            "work_limit": 100,
        }
    )
    output = AutonomousMethodOutput.model_validate(
        {
            "status": "lead",
            "summary": "searched the boundary first",
            "witness": None,
            "claim": None,
            "metrics": {"work": 100},
        }
    )
    assert request.work_limit == output.metrics["work"]
```

The real sandbox test mounts a malicious policy-approved module that attempts
to read the host home, environment, database, network, Docker socket, and
repository outside its mount. Every attempt must fail. A valid method receives
one JSON request on stdin, returns one JSON response on stdout, and cannot
create a surviving process or writable host file.

- [ ] **Step 2: Verify red**

```bash
uv run pytest -q tests/unit/test_autonomous_method_runner.py tests/integration/test_autonomous_method_sandbox.py
```

Expected: SDK, runner, and image are absent.

- [ ] **Step 3: Implement the initial human-reviewed sandbox image**

The Dockerfile must:

- Use the inspected arm64 Python 3.13.14 slim manifest exactly:
  `FROM python:3.13-slim@sha256:800ac3fc34cb04346a5669cc677cb4d65e23be59e1b64a1efa60fe4b230263ff`.
- Install only the locked runtime wheel set required by the SDK, Pydantic, and
  SymPy.
- Create an unprivileged numeric user.
- Copy only the fixed runner/SDK into the image.
- Use the runner as a fixed entrypoint.

Host invocation must use:

```python
argv = (
    "docker",
    "run",
    "--rm",
    "--network",
    "none",
    "--read-only",
    "--cap-drop",
    "ALL",
    "--security-opt",
    "no-new-privileges",
    "--pids-limit",
    "64",
    "--memory",
    "512m",
    "--cpus",
    "1",
    "--tmpfs",
    "/tmp:rw,noexec,nosuid,size=64m",
    "--mount",
    f"type=bind,src={approved_module},dst=/method/method.py,readonly",
    exact_image_id,
)
```

Supply the request on stdin and capture bounded stdout/stderr. Do not mount the
repository, home, Codex state, database socket, Docker socket, or artifact
root. Validate output through `AutonomousMethodOutput` and require process
cleanup. Add Dockerfile, runner, SDK, dependency lock, exact local image ID,
and module digest to provenance.

- [ ] **Step 4: Run focused and adversarial gates**

```bash
docker build -t mathloop-autonomous-method:py313 docker/autonomous-method
uv run pytest -q tests/unit/test_autonomous_method_runner.py tests/integration/test_autonomous_method_sandbox.py
uv run ruff check src/mathloop/autonomous_methods src/mathloop/tools/autonomous_method.py tests/unit/test_autonomous_method_runner.py
uv run mypy src/mathloop/autonomous_methods src/mathloop/tools/autonomous_method.py
```

Expected: all pass and `docker image inspect` returns the exact configured ID.

- [ ] **Step 5: Commit**

```bash
git add src/mathloop/autonomous_methods src/mathloop/tools/autonomous_method.py docker/autonomous-method/Dockerfile src/mathloop/provenance.py src/mathloop/runtime.py tests/unit/test_autonomous_method_runner.py tests/integration/test_autonomous_method_sandbox.py
git commit -m "feat: sandbox autonomous solver methods"
```

---

### Task 4: Dedicated Runtime Repository and Fixed Check Runner

**Files:**
- Create: `src/mathloop/promotion/runtime_repo.py`
- Create: `src/mathloop/promotion/checks.py`
- Test: `tests/unit/test_runtime_repo.py`
- Test: `tests/unit/test_promotion_checks.py`

**Interfaces:**
- Produces: `RuntimeRepository.initialize`, `candidate_worktree`,
  `commit_candidate`, `compare_and_swap_main`, and `revert`.
- Produces: `PromotionCheckRunner.run(candidate_sha) -> CheckEvidence`.

- [ ] **Step 1: Write failing Git race and check tests**

Tests must prove:

```python
def test_compare_and_swap_refuses_moved_runtime_main(runtime_repo: RuntimeRepository) -> None:
    expected = runtime_repo.main_sha()
    runtime_repo.advance_main_with_operator_commit()
    with pytest.raises(RuntimeMainMoved):
        runtime_repo.compare_and_swap_main(expected, candidate_sha)


def test_check_runner_uses_fixed_commands_not_patch_configuration() -> None:
    evidence = runner.run(candidate_sha)
    assert [item.argv for item in evidence.commands] == [
        ("uv", "run", "pytest", "-q"),
        ("uv", "run", "ruff", "check", "src", "tests"),
        ("uv", "run", "mypy", "src"),
        ("uv", "lock", "--check"),
        ("git", "diff", "--check", parent_sha, candidate_sha),
    ]
```

Also prove the runtime clone has no writable remote, candidate worktrees are
detached/clean, source operator checkout is unchanged, stderr/stdout are
bounded, one absolute deadline applies, environment is allowlisted, patch
cannot supply commands, failures stop subsequent gates, and cleanup is exact.

- [ ] **Step 2: Verify red**

```bash
uv run pytest -q tests/unit/test_runtime_repo.py tests/unit/test_promotion_checks.py
```

Expected: modules are absent.

- [ ] **Step 3: Implement controlled Git and command execution**

`RuntimeRepository.initialize(source_sha)` creates a local clone at the exact
configured `.mathloop/runtime-repo`, removes every remote, checks out `main` at
the approved source SHA, and records an initialization event. All paths are
resolved and must remain beneath `.mathloop`.

Candidate patches apply with:

```python
apply_argv = (
    "git",
    "apply",
    "--index",
    "--binary",
    "--whitespace=error",
    str(validated_patch_path),
)
commit_argv = ("git", "commit", "--no-gpg-sign", "-m", generated_message)
```

Commit author/committer identity is a fixed Mathloop automation identity.
Before checks, rerun policy against actual base/candidate trees. The check
runner uses fixed argument arrays, an allowlisted environment, bounded output,
and the candidate worktree. It never invokes a shell or patch-provided script.

- [ ] **Step 4: Run focused gates**

```bash
uv run pytest -q tests/unit/test_runtime_repo.py tests/unit/test_promotion_checks.py
uv run ruff check src/mathloop/promotion/runtime_repo.py src/mathloop/promotion/checks.py tests/unit/test_runtime_repo.py tests/unit/test_promotion_checks.py
uv run mypy src/mathloop/promotion/runtime_repo.py src/mathloop/promotion/checks.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/mathloop/promotion/runtime_repo.py src/mathloop/promotion/checks.py tests/unit/test_runtime_repo.py tests/unit/test_promotion_checks.py
git commit -m "feat: verify patches in controlled runtime repo"
```

---

### Task 5: Fresh Sol Review Gate

**Files:**
- Create: `src/mathloop/promotion/review.py`
- Test: `tests/unit/test_promotion_review.py`

**Interfaces:**
- Produces: `PromotionReviewOutput` and `PromotionReviewer.review(candidate, evidence)`.

- [ ] **Step 1: Write failing isolation and binding tests**

```python
def test_reviewer_is_fresh_read_only_and_bound_to_exact_patch() -> None:
    review = reviewer.review(candidate, checks)
    command = fake_codex.last_command
    assert "--ephemeral" in command
    assert ("--sandbox", "read-only") == adjacent_pair(command, "--sandbox")
    assert "--model" in command
    assert "gpt-5.6-sol" in command
    assert review.patch_sha256 == candidate.patch_sha256
    assert review.check_evidence_sha256 == checks.digest


def test_approval_for_another_patch_cannot_be_persisted() -> None:
    with pytest.raises(ReviewIdentityMismatch):
        repository.record_review(candidate.id, other_patch_review)
```

Also prove no resume/thread reuse, no candidate worktree writes, no live web,
no MCP tools, no reviewer-authored fixes, reject-on-malformed/refusal/timeout,
and one reserved Sol turn is consumed after dispatch.

- [ ] **Step 2: Verify red**

```bash
uv run pytest -q tests/unit/test_promotion_review.py
```

Expected: review module is absent.

- [ ] **Step 3: Implement schema-constrained review**

```python
class PromotionReviewOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: Literal["approve", "reject"]
    findings: list[ReviewFinding] = Field(max_length=50)
    residual_risks: list[str] = Field(max_length=20)
```

The prompt includes the exact diff, policy decision, fixed command evidence,
and autonomous sandbox contract. It asks for security, correctness, test
quality, checker independence, holdout contamination, resource limits, and
scope review. The reviewer is not asked to edit. Approval is accepted only
when `findings` contains no Critical or Important item and every identity
matches persisted evidence.

- [ ] **Step 4: Run focused gates**

```bash
uv run pytest -q tests/unit/test_promotion_review.py
uv run ruff check src/mathloop/promotion/review.py tests/unit/test_promotion_review.py
uv run mypy src/mathloop/promotion/review.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/mathloop/promotion/review.py tests/unit/test_promotion_review.py
git commit -m "feat: independently review autonomous patches"
```

---

### Task 6: Equal-Budget Held-Out Canary

**Files:**
- Create: `src/mathloop/promotion/canary.py`
- Modify: `src/mathloop/evolution.py`
- Test: `tests/unit/test_promotion_canary.py`
- Test: `tests/integration/test_evolution_repository.py`

**Interfaces:**
- Produces: `PromotionCanary.evaluate(parent_sha, candidate_sha, suite)`.
- Reuses paired holdout persistence without mixing code promotion with method promotion.

- [ ] **Step 1: Write failing fairness and threshold tests**

```python
def test_canary_requires_identical_problem_seed_and_budget_pairs() -> None:
    decision = canary.evaluate(parent_sha, candidate_sha, heldout_suite)
    for pair in decision.pairs:
        assert pair.parent.problem_id == pair.candidate.problem_id
        assert pair.parent.seed == pair.candidate.seed
        assert pair.parent.work_limit == pair.candidate.work_limit
        assert pair.parent.turn_limit == pair.candidate.turn_limit


def test_candidate_requires_no_false_positive_and_material_value() -> None:
    assert decide(parent_verified=2, candidate_verified=2, candidate_cost_ratio=0.79).passed
    assert decide(parent_verified=2, candidate_verified=3, candidate_cost_ratio=1.0).passed
    assert not decide(parent_verified=2, candidate_verified=2, candidate_cost_ratio=1.0).passed
    assert not decide(
        parent_verified=2,
        candidate_verified=3,
        candidate_cost_ratio=0.5,
        candidate_false_positives=1,
    ).passed
```

Also require six pairs, two per portfolio category, separate immutable
parent/candidate runtime worktrees, no ordinary scheduling contamination,
independent verification, exact usage accounting, and deterministic replay.

- [ ] **Step 2: Verify red**

```bash
uv run pytest -q tests/unit/test_promotion_canary.py tests/integration/test_evolution_repository.py
```

Expected: promotion canary is absent.

- [ ] **Step 3: Implement thresholds**

A candidate passes only if:

- All six parent/candidate pairs complete under equal limits.
- Candidate has zero verifier rejection/false-positive outcomes.
- Candidate verified count is at least the parent count.
- Candidate either verifies at least one additional problem or uses at most
  80% of the parent's combined turn/token/time cost at equal verified count.
- No safety, cleanup, provenance, or reproduction check regresses.

Persist every pair and derived threshold input. The decision function receives
only persisted outcomes; no model score or self-reported metric enters it.

- [ ] **Step 4: Run focused gates**

```bash
uv run pytest -q tests/unit/test_promotion_canary.py tests/integration/test_evolution_repository.py
uv run ruff check src/mathloop/promotion/canary.py src/mathloop/evolution.py tests/unit/test_promotion_canary.py
uv run mypy src/mathloop/promotion/canary.py src/mathloop/evolution.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/mathloop/promotion/canary.py src/mathloop/evolution.py tests/unit/test_promotion_canary.py tests/integration/test_evolution_repository.py
git commit -m "feat: canary autonomous runtime patches"
```

---

### Task 7: Serialized Merge, Restart, Health Monitor, and Revert

**Files:**
- Create: `src/mathloop/promotion/controller.py`
- Modify: `src/mathloop/codex/supervisor.py`
- Modify: `src/mathloop/provenance.py`
- Test: `tests/integration/test_promotion_controller.py`

**Interfaces:**
- Produces: `PromotionController.run_once(worker_id) -> bool`.
- Produces: `monitor_runtime_epoch` and `revert_failed_epoch`.

- [ ] **Step 1: Write failing crash/race/rollback tests**

Scenarios:

- Runtime `main` moves after checks: candidate is returned for re-evaluation.
- Controller crashes before ref update: no merge projection exists.
- Ref advances but database commit fails: reconciliation records the exact
  merge only when commit trailers bind the candidate.
- Workers do not drain by deadline: merge does not begin.
- Merge succeeds: old workers stop, new workers report exact provenance, and
  only then promotion becomes `merged`.
- Health regression: one revert commit is created, workers restart at reverted
  bytes, and duplicate reconciliation is idempotent.

Example assertion:

```python
def test_health_regression_creates_revert_not_reset(controller: PromotionController) -> None:
    merged = controller.promote(ready_candidate)
    health.fail_epoch(merged.new_sha)
    reverted = controller.monitor_runtime_epoch(merged.new_sha)
    assert reverted.status is PromotionStatus.REVERTED
    assert runtime_repo.is_ancestor(merged.new_sha, reverted.revert_sha)
    assert runtime_repo.main_sha() == reverted.revert_sha
    assert git_commands.never_used_prefix(("git", "reset"))
```

- [ ] **Step 2: Verify red**

```bash
uv run pytest -q tests/integration/test_promotion_controller.py
```

Expected: controller is absent.

- [ ] **Step 3: Implement the stable controller**

The controller runs from the operator installation. It:

1. Claims one ready candidate under the database promotion lease.
2. Pauses new runtime dispatch.
3. Drains active runtime workers to an absolute deadline.
4. Confirms policy/check/review/canary identities.
5. Acquires the runtime repository lock.
6. Confirms compare-and-swap expected `main`.
7. Creates a merge commit with candidate/policy/check/review/canary trailers.
8. Records the merge commit before releasing the lock.
9. Starts runtime workers using the runtime clone and new SHA.
10. Requires exact executable provenance and health heartbeats.
11. Marks merged or executes
    `("git", "revert", "--no-edit", merge_sha)`.

Health checks cover worker startup, database compatibility, scheduler cycle,
artifact round-trip, exact verifier check, no budget/provenance migration
error, and bounded failure-rate comparison. The controller never imports or
executes candidate promotion/controller code.

- [ ] **Step 4: Run focused and existing recovery gates**

```bash
uv run pytest -q tests/integration/test_promotion_controller.py tests/integration/test_runtime_loop.py tests/integration/test_repository.py
uv run ruff check src/mathloop/promotion/controller.py src/mathloop/codex/supervisor.py src/mathloop/provenance.py tests/integration/test_promotion_controller.py
uv run mypy src/mathloop/promotion/controller.py src/mathloop/codex/supervisor.py src/mathloop/provenance.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/mathloop/promotion/controller.py src/mathloop/codex/supervisor.py src/mathloop/provenance.py tests/integration/test_promotion_controller.py
git commit -m "feat: merge and revert autonomous patches"
```

---

### Task 8: Promotion CLI, Reporting, and End-to-End Canary

**Files:**
- Modify: `src/mathloop/cli.py`
- Modify: `src/mathloop/reporting.py`
- Create: `tests/e2e/test_autonomous_promotion.py`
- Create: `docs/verification/codex-promotion-acceptance.md`

**Interfaces:**
- Adds `mathloop codex promotion init|status|run|pause|resume|revert`.
- Verifies one safe promotion and one protected-path gate.

- [ ] **Step 1: Write offline end-to-end promotion tests**

Test A:

1. Fake Codex produces a new autonomous method and new autonomous test.
2. Policy accepts it.
3. Fixed gates pass.
4. Fresh fake Sol review approves.
5. Six paired canary experiments show one additional verified result.
6. Controller merges into runtime `main`.
7. New workers report the new provenance epoch.
8. Operator checkout remains unchanged.

Test B:

1. Fake Codex also edits `verification.py`.
2. Entire patch becomes `human_gated`.
3. No checks/review/canary/merge runs automatically.

Test C:

1. A safe patch merges.
2. Health monitor receives a deterministic regression.
3. Controller creates a revert commit and restarts the reverted epoch.

- [ ] **Step 2: Add operator commands**

Commands:

```text
mathloop codex promotion init
mathloop codex promotion status
mathloop codex promotion run --max-promotions 1
mathloop codex promotion pause
mathloop codex promotion resume
```

`revert` takes one required `merge_sha: str` argument and is an explicit
operator action for a recorded promotion only. It validates that the
40-character SHA is the exact recorded promotion merge, creates a revert
commit, and never resets.
Reports include candidate/patch/source turn, policy, checks, reviewer turn,
canary pairs, merge/revert commits, runtime provenance, and reproduction
commands.

- [ ] **Step 3: Run full offline gates**

```bash
uv run pytest -q tests/e2e/test_autonomous_promotion.py
uv run pytest -q
uv run ruff check src tests
uv run mypy src
uv lock --check
git diff --check
```

Expected: all pass.

- [ ] **Step 4: Run one approved live safe-surface promotion canary**

Require immediate operator confirmation because this consumes Codex turns and
changes runtime-clone `main`:

```bash
uv run mathloop codex promotion run --max-promotions 1
uv run mathloop codex promotion status
```

Acceptance:

- No more than one promotion.
- Patch touches only auto-eligible paths.
- Fresh Sol review and six paired canaries are persisted.
- Fixed gates pass after rebasing onto current runtime `main`.
- Operator checkout is unchanged.
- Runtime workers restart at exact new provenance.
- A synthetic health failure test proves revert before enabling continuous
  promotion.

- [ ] **Step 5: Record evidence and commit**

```bash
git add src/mathloop/cli.py src/mathloop/reporting.py tests/e2e/test_autonomous_promotion.py docs/verification/codex-promotion-acceptance.md
git commit -m "feat: operate autonomous code promotion"
```

---

## Final Program Gate

```bash
uv run pytest -q
uv run ruff check src tests
uv run mypy src
uv lock --check
git diff --check
git status --short
```

Then run a whole-program security review over the exact clean commit. It must
explicitly attempt:

- Codex-auth and home-directory exfiltration.
- Shell-network and Docker-socket escape.
- MCP arbitrary-command/path injection.
- Forged turn receipts and replay after ambiguous dispatch.
- Web-content prompt injection into authority decisions.
- Checker/verifier self-authorization.
- Patch traversal, rename, binary, symlink, submodule, mixed-scope, test
  weakening, dependency, Docker, and promotion-policy bypass.
- Reviewer identity/patch substitution.
- Holdout contamination and unequal canary budgets.
- Runtime-main race, interrupted merge, false reconciliation, and rollback
  bypass.

Required outcome:

- No Critical or Important findings.
- Foundation, research, and promotion acceptance documents match fresh
  evidence.
- One approved live six-turn research canary and one approved safe-surface
  promotion canary have completed without API billing or publication.
- Continuous 100-turn/four-worker/five-promotion operation remains disabled
  until the operator explicitly enables it after reviewing those results.
