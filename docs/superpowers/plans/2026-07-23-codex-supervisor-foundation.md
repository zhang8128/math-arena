# Codex Supervisor Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a durable, ChatGPT-authenticated Codex execution lane that can run full agents in disposable repository worktrees against the existing seeded problem corpus without using OpenAI API billing.

**Architecture:** The existing worker remains the outer authority and process supervisor. It reserves a Codex turn transactionally, commits the dispatch marker before releasing the child, streams bounded Codex JSONL events through the existing process pipe, and settles a reservation-bound non-dollar receipt. Each Codex run receives a disposable Git worktree, a generated structured-output schema, an allowlisted environment, explicit sandbox/model settings, and no shell network.

**Tech Stack:** Python 3.13, Codex CLI 0.145.0+, ChatGPT-managed Codex authentication, PostgreSQL 17, psycopg 3, Pydantic 2, Typer, Git worktrees, pytest, Ruff, mypy.

## Global Constraints

- Reuse saved ChatGPT Codex authentication; never set `OPENAI_API_KEY` or `CODEX_API_KEY`.
- Enforce 100 started turns/day, four concurrent turns, 30 minutes/turn, and model quotas of 40 Luna, 40 Terra, and 20 Sol.
- Keep at least ten Sol turns reserved for escalation/review.
- Record Codex accounting as turns and tokens; do not manufacture a dollar-equivalent receipt.
- A durable `turn.started` event consumes the turn; dispatched or ambiguous work is never retried automatically.
- Run Codex only in a disposable worktree with `--ephemeral`, `--json`, `--output-schema`, explicit model, `workspace-write`, ignored user config/rules, live web search disabled in this foundation phase, and shell network disabled.
- Preserve the fixed independent mathematical verification kernel and human publication gate.
- Preserve the existing OpenAI API provider unchanged and reject simultaneous API and Codex enablement.
- Every task follows red-green-refactor, runs focused tests, runs Ruff and mypy on touched code, and commits independently.

---

## File Structure

Create a focused `mathloop.codex` package:

- `src/mathloop/codex/domain.py` — immutable Codex policy, reservation, usage, and receipt types.
- `src/mathloop/codex/events.py` — bounded JSONL parsing and turn-state reduction.
- `src/mathloop/codex/launch.py` — command construction and environment allowlisting.
- `src/mathloop/codex/worktrees.py` — disposable Git worktree lifecycle and diff capture.
- `src/mathloop/codex/client.py` — supervised noninteractive Codex execution and schema parsing.
- `src/mathloop/methods/codex_agent.py` — Codex-backed proof-strategy method.
- `src/mathloop/codex/supervisor.py` — bounded cycle orchestration and status projection.

Modify existing boundaries rather than duplicating them:

- `src/mathloop/config.py` — Codex paths, quotas, deadlines, and model-role defaults.
- `src/mathloop/methods/base.py` — Codex receipt and event callback fields.
- `src/mathloop/worker.py` — Codex reservation/dispatch/event/settlement path.
- `src/mathloop/storage/schema.sql` — turn and event projections.
- `src/mathloop/storage/repository.py` — transactional Codex ledger methods.
- `src/mathloop/runtime.py` — exclusive Codex runtime composition and method registration.
- `src/mathloop/scheduling.py` — Codex proof-strategy experiment configuration.
- `src/mathloop/cli.py` — `mathloop codex` commands.
- `src/mathloop/provenance.py` — Codex CLI/policy/worktree runner provenance inputs.

Tests live in:

- `tests/unit/test_codex_domain.py`
- `tests/unit/test_codex_events.py`
- `tests/unit/test_codex_launch.py`
- `tests/unit/test_codex_worktrees.py`
- `tests/unit/test_codex_client.py`
- `tests/unit/test_codex_method.py`
- `tests/integration/test_codex_repository.py`
- `tests/integration/test_codex_worker.py`
- `tests/integration/test_codex_runtime.py`
- `tests/e2e/test_codex_canary.py`

---

### Task 1: Codex Policy and Immutable Accounting Types

**Files:**
- Create: `src/mathloop/codex/__init__.py`
- Create: `src/mathloop/codex/domain.py`
- Modify: `src/mathloop/config.py`
- Test: `tests/unit/test_codex_domain.py`
- Test: `tests/unit/test_config.py`

**Interfaces:**
- Consumes: `mathloop.domain.FrozenModel`.
- Produces: `CodexModelRole`, `CodexTurnStatus`, `CodexPolicy`, `CodexUsage`, `CodexTurnReservation`, and `CodexTurnReceipt`.

- [ ] **Step 1: Write failing immutable-policy and receipt tests**

```python
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from mathloop.codex.domain import (
    CodexModelRole,
    CodexPolicy,
    CodexTurnReceipt,
    CodexTurnReservation,
    CodexUsage,
)


def test_default_codex_policy_matches_approved_envelope() -> None:
    policy = CodexPolicy()
    assert policy.daily_turn_limit == 100
    assert policy.concurrent_turn_limit == 4
    assert policy.turn_timeout_seconds == 1800
    assert policy.model_turn_limits == {"luna": 40, "terra": 40, "sol": 20}
    assert policy.reserved_sol_turns == 10


def test_codex_receipt_is_bound_to_the_reservation() -> None:
    reservation = CodexTurnReservation(
        id=uuid4(),
        experiment_id=uuid4(),
        budget_day=date(2026, 7, 23),
        role=CodexModelRole.TERRA,
        model="gpt-5.6-terra",
        deadline_seconds=1800,
        created_at=datetime.now(UTC),
    )
    receipt = CodexTurnReceipt(
        reservation_id=reservation.id,
        experiment_id=reservation.experiment_id,
        thread_id="thread-1",
        model=reservation.model,
        cli_version="0.145.0",
        usage=CodexUsage(
            input_tokens=100,
            cached_input_tokens=20,
            output_tokens=30,
            reasoning_output_tokens=10,
        ),
        final_status="completed",
    )
    assert receipt.reservation_id == reservation.id
    with pytest.raises(ValidationError):
        CodexTurnReceipt.model_validate(
            {
                **receipt.model_dump(mode="python"),
                "final_status": "invented",
            }
        )
```

- [ ] **Step 2: Run tests and confirm missing module/types**

Run:

```bash
uv run pytest -q tests/unit/test_codex_domain.py
```

Expected: collection fails because `mathloop.codex.domain` does not exist.

- [ ] **Step 3: Implement the exact domain contract**

Create frozen enums/models with these signatures:

```python
class CodexModelRole(StrEnum):
    LUNA = "luna"
    TERRA = "terra"
    SOL = "sol"


class CodexTurnStatus(StrEnum):
    RESERVED = "reserved"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    AMBIGUOUS = "ambiguous"


class CodexPolicy(FrozenModel):
    daily_turn_limit: int = Field(default=100, ge=1)
    concurrent_turn_limit: int = Field(default=4, ge=1)
    turn_timeout_seconds: int = Field(default=1800, ge=60)
    model_turn_limits: dict[str, int] = Field(
        default_factory=lambda: {"luna": 40, "terra": 40, "sol": 20}
    )
    reserved_sol_turns: int = Field(default=10, ge=0)
    max_jsonl_bytes: int = Field(default=16 * 1024 * 1024, ge=1024)
    max_patch_bytes: int = Field(default=4 * 1024 * 1024, ge=1024)


class CodexUsage(FrozenModel):
    input_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    reasoning_output_tokens: int = Field(ge=0)


class CodexTurnReservation(FrozenModel):
    id: UUID
    experiment_id: UUID
    budget_day: date
    role: CodexModelRole
    model: str = Field(min_length=1)
    deadline_seconds: int = Field(ge=60)
    created_at: datetime


class CodexTurnReceipt(FrozenModel):
    reservation_id: UUID
    experiment_id: UUID
    thread_id: str = Field(min_length=1)
    model: str = Field(min_length=1)
    cli_version: str = Field(min_length=1)
    usage: CodexUsage
    final_status: Literal["completed"]
```

Add settings with exact defaults:

```python
codex_enabled: bool = False
codex_cli_path: Path = Path("codex")
codex_repo_root: Path = Path(".")
codex_worktree_root: Path = Path(".mathloop/codex-worktrees")
codex_daily_turn_limit: int = Field(default=100, ge=1)
codex_concurrent_turn_limit: int = Field(default=4, ge=1)
codex_turn_timeout_seconds: int = Field(default=1800, ge=60)
codex_luna_turn_limit: int = Field(default=40, ge=0)
codex_terra_turn_limit: int = Field(default=40, ge=0)
codex_sol_turn_limit: int = Field(default=20, ge=0)
codex_reserved_sol_turns: int = Field(default=10, ge=0)
codex_model_luna: str = "gpt-5.6-luna"
codex_model_terra: str = "gpt-5.6-terra"
codex_model_sol: str = "gpt-5.6-sol"
codex_min_cli_version: str = "0.145.0"
```

Validate that role limits sum to the daily limit and reserved Sol turns do not
exceed the Sol limit. Resolve repository/worktree paths like existing artifact
paths.

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest -q tests/unit/test_codex_domain.py tests/unit/test_config.py
uv run ruff check src/mathloop/codex/domain.py src/mathloop/config.py tests/unit/test_codex_domain.py
uv run mypy src/mathloop/codex/domain.py src/mathloop/config.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/mathloop/codex src/mathloop/config.py tests/unit/test_codex_domain.py tests/unit/test_config.py
git commit -m "feat: define Codex turn policy"
```

---

### Task 2: Bounded Codex JSONL State Machine

**Files:**
- Create: `src/mathloop/codex/events.py`
- Test: `tests/unit/test_codex_events.py`

**Interfaces:**
- Consumes: newline-delimited bytes from Codex CLI `--json`.
- Produces: `CodexEventParser.feed(line: bytes) -> CodexEvent` and `CodexEventState.finish() -> CodexTranscript`.

- [ ] **Step 1: Write failing parser tests**

```python
import json

import pytest

from mathloop.codex.events import CodexEventError, CodexEventParser


def encoded(payload: dict[str, object]) -> bytes:
    return json.dumps(payload).encode() + b"\n"


def test_parser_reduces_completed_turn_and_usage() -> None:
    parser = CodexEventParser(max_bytes=4096)
    parser.feed(encoded({"type": "thread.started", "thread_id": "thread-1"}))
    parser.feed(encoded({"type": "turn.started"}))
    parser.feed(
        encoded(
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": '{"strategy":"induction"}'},
            }
        )
    )
    parser.feed(
        encoded(
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 10,
                    "cached_input_tokens": 2,
                    "output_tokens": 4,
                    "reasoning_output_tokens": 1,
                },
            }
        )
    )
    transcript = parser.finish()
    assert transcript.thread_id == "thread-1"
    assert transcript.dispatched is True
    assert transcript.final_message == '{"strategy":"induction"}'
    assert transcript.usage.output_tokens == 4


def test_parser_rejects_duplicate_start_completion_and_oversize() -> None:
    parser = CodexEventParser(max_bytes=80)
    parser.feed(encoded({"type": "turn.started"}))
    with pytest.raises(CodexEventError):
        parser.feed(encoded({"type": "turn.started"}))
    with pytest.raises(CodexEventError):
        parser.feed(b"x" * 81)
```

- [ ] **Step 2: Verify red**

Run:

```bash
uv run pytest -q tests/unit/test_codex_events.py
```

Expected: import failure for `mathloop.codex.events`.

- [ ] **Step 3: Implement strict event parsing**

Implement:

```python
@dataclass(frozen=True)
class CodexEvent:
    sequence: int
    event_type: str
    payload: dict[str, object]
    raw_sha256: str


@dataclass(frozen=True)
class CodexTranscript:
    thread_id: str
    dispatched: bool
    final_message: str
    usage: CodexUsage
    events: tuple[CodexEvent, ...]


class CodexEventParser:
    def __init__(self, *, max_bytes: int) -> None:
        if type(max_bytes) is not int or max_bytes < 1:
            raise ValueError("max_bytes must be a positive integer")
        self._max_bytes = max_bytes
        self._bytes_seen = 0
        self._events: list[CodexEvent] = []
        self._thread_id: str | None = None
        self._turn_started = False
        self._terminal_type: str | None = None
        self._final_message: str | None = None
        self._usage: CodexUsage | None = None
```

Add `feed(self, line: bytes) -> CodexEvent` and
`finish(self) -> CodexTranscript`. Their implementation must:

- Count raw bytes before decoding.
- Require one JSON object per line.
- Accept documented `thread.started`, `turn.started`, `turn.completed`,
  `turn.failed`, `error`, and `item.*` events.
- Preserve unknown events as evidence without treating them as lifecycle state.
- Require exactly one thread, one turn start, one terminal event, one final
  agent message, and non-negative integer usage fields.
- Reject agent messages after terminal completion.
- Never infer missing token counts or a successful terminal state.

- [ ] **Step 4: Run focused tests**

```bash
uv run pytest -q tests/unit/test_codex_events.py
uv run ruff check src/mathloop/codex/events.py tests/unit/test_codex_events.py
uv run mypy src/mathloop/codex/events.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/mathloop/codex/events.py tests/unit/test_codex_events.py
git commit -m "feat: parse Codex execution events"
```

---

### Task 3: Fail-Closed Launch Policy and Disposable Worktrees

**Files:**
- Create: `src/mathloop/codex/launch.py`
- Create: `src/mathloop/codex/worktrees.py`
- Test: `tests/unit/test_codex_launch.py`
- Test: `tests/unit/test_codex_worktrees.py`

**Interfaces:**
- Produces: `CodexLaunchPolicy.command(model: str, worktree: Path, schema: Path, prompt: str, web_search: Literal["disabled", "live"] = "disabled") -> tuple[str, ...]`.
- Produces: `CodexLaunchPolicy.environment(source: Mapping[str, str]) -> dict[str, str]`.
- Produces: `CodexWorktreeManager.create(turn_id, base_sha) -> CodexWorktree` and `remove(worktree)`.

- [ ] **Step 1: Write failing policy and real-Git worktree tests**

```python
def test_launch_is_ephemeral_structured_and_offline(tmp_path: Path) -> None:
    policy = CodexLaunchPolicy(
        codex_binary=Path("/opt/codex"),
        codex_home=Path("/safe/codex-home"),
    )
    command = policy.command(
        model="gpt-5.6-terra",
        worktree=tmp_path,
        schema=tmp_path / "schema.json",
        prompt="Solve the normalized problem.",
    )
    assert command[:2] == ("/opt/codex", "exec")
    assert "--ephemeral" in command
    assert "--json" in command
    assert "--output-schema" in command
    assert "--ignore-user-config" in command
    assert "--ignore-rules" in command
    assert "sandbox_workspace_write.network_access=false" in " ".join(command)


def test_environment_drops_repository_and_provider_secrets() -> None:
    env = CodexLaunchPolicy(
        codex_binary=Path("/opt/codex"),
        codex_home=Path("/safe/codex-home"),
    ).environment(
        {
            "PATH": "/bin",
            "HOME": "/Users/test",
            "CODEX_HOME": "/Users/test/.codex",
            "OPENAI_API_KEY": "secret",
            "DATABASE_URL": "secret",
            "DOCKER_HOST": "secret",
        }
    )
    assert env["CODEX_HOME"] == "/safe/codex-home"
    assert "OPENAI_API_KEY" not in env
    assert "DATABASE_URL" not in env
    assert "DOCKER_HOST" not in env
```

The worktree test must initialize a temporary Git repository, commit one file,
create a detached worktree at that commit, edit it, assert the source checkout
is unchanged, capture the patch digest, remove the worktree, and run
`git worktree prune`.

- [ ] **Step 2: Verify red**

```bash
uv run pytest -q tests/unit/test_codex_launch.py tests/unit/test_codex_worktrees.py
```

Expected: both modules are missing.

- [ ] **Step 3: Implement exact command and worktree lifecycle**

`CodexLaunchPolicy.command` must emit this ordered shape:

```python
(
    str(self.codex_binary),
    "exec",
    "--ephemeral",
    "--json",
    "--output-schema",
    str(schema),
    "--sandbox",
    "workspace-write",
    "--ignore-user-config",
    "--ignore-rules",
    "--model",
    model,
    "--cd",
    str(worktree),
    "--config",
    "web_search=\"disabled\"",
    "--config",
    "sandbox_workspace_write.network_access=false",
    prompt,
)
```

Only allow `PATH`, `CODEX_HOME`, `TMPDIR`, `LANG`, `LC_ALL`,
`CODEX_CA_CERTIFICATE`, and `SSL_CERT_FILE`. Set `CODEX_HOME` from trusted
settings rather than the source environment.

Implement worktree commands as argument vectors with `shell=False`:

```python
add_argv = ("git", "worktree", "add", "--detach", str(path), base_sha)
diff_argv = (
    "git",
    "-C",
    str(path),
    "diff",
    "--binary",
    "--no-ext-diff",
    base_sha,
)
remove_argv = ("git", "worktree", "remove", str(path))
prune_argv = ("git", "worktree", "prune")
```

Validate UUID directory names, resolved containment under the configured root,
40-character lowercase base SHAs, clean initial worktrees, patch size, and
successful cleanup. Hash the patch bytes with SHA-256.

- [ ] **Step 4: Run focused tests**

```bash
uv run pytest -q tests/unit/test_codex_launch.py tests/unit/test_codex_worktrees.py
uv run ruff check src/mathloop/codex/launch.py src/mathloop/codex/worktrees.py tests/unit/test_codex_launch.py tests/unit/test_codex_worktrees.py
uv run mypy src/mathloop/codex/launch.py src/mathloop/codex/worktrees.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/mathloop/codex/launch.py src/mathloop/codex/worktrees.py tests/unit/test_codex_launch.py tests/unit/test_codex_worktrees.py
git commit -m "feat: isolate Codex agent worktrees"
```

---

### Task 4: Transactional Codex Turn Ledger

**Files:**
- Modify: `src/mathloop/storage/schema.sql`
- Modify: `src/mathloop/storage/repository.py`
- Test: `tests/integration/test_codex_repository.py`

**Interfaces:**
- Produces: `Repository.reserve_codex_turn(experiment_id: UUID, worker_id: str, role: CodexModelRole, model: str, policy: CodexPolicy, now: datetime) -> CodexTurnReservation | None`.
- Produces: `mark_codex_turn_dispatched`, `append_codex_turn_event`,
  `complete_codex_turn`, `fail_codex_turn`, `reconcile_codex_turns`, and
  `codex_usage_status`.

- [ ] **Step 1: Write failing transactional tests**

Cover these exact cases:

```python
def test_codex_turn_limit_and_concurrency_are_atomic(repository: Repository) -> None:
    policy = CodexPolicy(
        daily_turn_limit=2,
        concurrent_turn_limit=1,
        model_turn_limits={"luna": 0, "terra": 2, "sol": 0},
        reserved_sol_turns=0,
    )
    first = repository.reserve_codex_turn(
        experiment_id=experiment_id_1,
        role=CodexModelRole.TERRA,
        model="gpt-5.6-terra",
        policy=policy,
        now=fixed_now,
    )
    assert first is not None
    assert repository.reserve_codex_turn(
        experiment_id=experiment_id_2,
        role=CodexModelRole.TERRA,
        model="gpt-5.6-terra",
        policy=policy,
        now=fixed_now,
    ) is None


def test_dispatched_turn_cannot_be_reserved_or_replayed(repository: Repository) -> None:
    reservation = reserve_one(repository)
    repository.mark_codex_turn_dispatched(reservation.id, "worker-1")
    repository.fail_codex_turn(
        reservation.id,
        status=CodexTurnStatus.AMBIGUOUS,
        failure_kind="worker_lost",
        failure_message="dispatch outcome is ambiguous",
    )
    assert repository.reserve_codex_turn_for_existing_experiment(
        reservation.experiment_id
    ) is None
```

Also test 40/40/20 role limits, ten reserved Sol turns, concurrent callers under
PostgreSQL advisory locking, idempotent event replay, conflicting event replay,
lease expiry before dispatch, and conservative reconciliation after dispatch.

- [ ] **Step 2: Verify red**

```bash
uv run pytest -q tests/integration/test_codex_repository.py
```

Expected: schema tables and repository methods are absent.

- [ ] **Step 3: Add schema and repository transactions**

Add:

```sql
CREATE TABLE IF NOT EXISTS codex_turns (
    id UUID PRIMARY KEY,
    experiment_id UUID NOT NULL UNIQUE REFERENCES experiments(id),
    budget_day DATE NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('luna', 'terra', 'sol')),
    model TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN (
            'reserved', 'dispatched', 'running', 'completed',
            'failed', 'timed_out', 'ambiguous'
        )
    ),
    lease_owner TEXT NOT NULL,
    lease_expires_at TIMESTAMPTZ NOT NULL,
    thread_id TEXT NULL,
    cli_version TEXT NULL,
    input_tokens BIGINT NULL CHECK (input_tokens >= 0),
    cached_input_tokens BIGINT NULL CHECK (cached_input_tokens >= 0),
    output_tokens BIGINT NULL CHECK (output_tokens >= 0),
    reasoning_output_tokens BIGINT NULL CHECK (reasoning_output_tokens >= 0),
    failure_kind TEXT NULL,
    failure_message TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS codex_turn_events (
    turn_id UUID NOT NULL REFERENCES codex_turns(id),
    sequence INTEGER NOT NULL CHECK (sequence >= 0),
    event_type TEXT NOT NULL,
    raw_sha256 TEXT NOT NULL,
    payload JSONB NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (turn_id, sequence)
);
```

`reserve_codex_turn` must take one transaction-level advisory lock keyed by the
budget day, count all daily reservations, count active leases, enforce the
role quota and reserved-Sol floor, then insert the reservation and event. A
conflicting experiment reservation returns the exact existing reservation only
when every immutable field matches.

`append_codex_turn_event` compares the entire persisted event on replay.
`complete_codex_turn` requires prior dispatch, exact reservation/receipt
identity, exactly one persisted `turn.started`, and one matching
`turn.completed`. Terminal rows are immutable.

- [ ] **Step 4: Run repository integration tests**

```bash
uv run pytest -q tests/integration/test_codex_repository.py
uv run ruff check src/mathloop/storage/repository.py tests/integration/test_codex_repository.py
uv run mypy src/mathloop/storage/repository.py
```

Expected: all pass, including concurrency tests.

- [ ] **Step 5: Commit**

```bash
git add src/mathloop/storage/schema.sql src/mathloop/storage/repository.py tests/integration/test_codex_repository.py
git commit -m "feat: persist Codex turn accounting"
```

---

### Task 5: Supervised Codex Client and Event Streaming

**Files:**
- Create: `src/mathloop/codex/client.py`
- Modify: `src/mathloop/methods/base.py`
- Modify: `src/mathloop/worker.py`
- Test: `tests/unit/test_codex_client.py`
- Test: `tests/integration/test_codex_worker.py`

**Interfaces:**
- Produces: `CodexRequest[T]`, `CodexResponse[T]`, and
  `CodexClient.execute(request, schema, emit_event)`.
- Extends: `MethodContext.external_execution_id` and
  `MethodContext.emit_external_event`.
- Extends: `MethodResult.codex_turn_receipt`.

- [ ] **Step 1: Write fake-CLI red tests**

Create an executable fake Codex script fixture that emits valid JSONL, malformed
JSONL, a delayed terminal event, a child process, and nonzero exits based on an
argument. Tests must prove:

```python
def test_codex_client_returns_schema_value_usage_and_patch(fake_codex: Path) -> None:
    response = client(fake_codex).execute(
        request(response_schema=ProofSketch),
        events.append,
    )
    assert response.value.strategy == "induction"
    assert response.receipt.usage.output_tokens == 12
    assert response.patch_sha256 == hashlib.sha256(response.patch).hexdigest()
    assert any(event.event_type == "turn.started" for event in events)


def test_codex_client_timeout_kills_descendants_and_never_completes(
    fake_codex: Path,
) -> None:
    with pytest.raises(CodexTurnTimedOut) as raised:
        client(fake_codex, timeout=0.1).execute(
            request(mode="hang", response_schema=ProofSketch),
            sink,
        )
    assert raised.value.dispatched is True
    assert descendant_is_running(raised.value.descendant_pid) is False
```

Worker integration tests must prove the parent persists the dispatch marker
before the fake CLI starts, persists events as they arrive, blocks replay after
dispatch, settles pre-start failure without consuming a turn, and rejects a
receipt for another reservation.

- [ ] **Step 2: Verify red**

```bash
uv run pytest -q tests/unit/test_codex_client.py tests/integration/test_codex_worker.py
```

Expected: client, callbacks, and receipt path are absent.

- [ ] **Step 3: Implement the client**

Use these contracts:

```python
@dataclass(frozen=True)
class CodexRequest[T: BaseModel]:
    reservation: CodexTurnReservation
    prompt: str
    base_sha: str
    response_schema: type[T]


@dataclass(frozen=True)
class CodexResponse[T: BaseModel]:
    value: T
    receipt: CodexTurnReceipt
    patch: bytes
    patch_sha256: str


class CodexClient:
```

Implement
`CodexClient.execute(self, request: CodexRequest[T], emit_event: Callable[[CodexEvent], None]) -> CodexResponse[T]`
in this order:

1. Create the detached worktree.
2. Write `response_schema.model_json_schema()` to a mode-`0600` temporary file
   outside the candidate worktree.
3. Call `context.mark_external_execution_started()` immediately before
   `subprocess.Popen`.
4. Start Codex with `stdin=DEVNULL`, stdout/stderr pipes, `text=False`,
   `start_new_session=True`, the allowlisted environment, and no shell.
5. Read stdout line-by-line in a bounded reader, parse each event, and call
   `emit_event` synchronously before reading the next line.
6. Drain bounded stderr concurrently to prevent deadlock.
7. Enforce the one absolute deadline across start, reads, wait, parse, diff,
   and cleanup.
8. Parse the final agent message with `response_schema.model_validate_json`.
9. Capture and hash the worktree patch.
10. Construct a reservation-bound receipt.
11. Remove the worktree in `finally`; preserve a cleanup failure as terminal
    infrastructure evidence.

Extend the process pipe protocol with `external_event`. The child sends the
event, waits for `external_event_acknowledged`, and only then reads the next
Codex line. The parent persists the event before acknowledging it.

The worker must distinguish API-dollar and Codex-turn reservations with a
frozen tagged union. It continues writing `experiments.cost_usd = 0` for Codex
work while storing Codex usage only in `codex_turns`. The result artifact must
label the accounting unit `chatgpt_codex_turn`, never `usd`.

- [ ] **Step 4: Run focused process and worker tests**

```bash
uv run pytest -q tests/unit/test_codex_client.py tests/integration/test_codex_worker.py tests/unit/test_worker.py tests/integration/test_worker_billing.py
uv run ruff check src/mathloop/codex/client.py src/mathloop/methods/base.py src/mathloop/worker.py tests/unit/test_codex_client.py tests/integration/test_codex_worker.py
uv run mypy src/mathloop/codex/client.py src/mathloop/methods/base.py src/mathloop/worker.py
```

Expected: all pass; no orphan fake descendants remain.

- [ ] **Step 5: Commit**

```bash
git add src/mathloop/codex/client.py src/mathloop/methods/base.py src/mathloop/worker.py tests/unit/test_codex_client.py tests/integration/test_codex_worker.py
git commit -m "feat: supervise Codex agent turns"
```

---

### Task 6: Codex Proof-Strategy Method and Scheduling

**Files:**
- Create: `src/mathloop/methods/codex_agent.py`
- Modify: `src/mathloop/methods/__init__.py`
- Modify: `src/mathloop/scheduling.py`
- Modify: `src/mathloop/provenance.py`
- Test: `tests/unit/test_codex_method.py`
- Test: `tests/unit/test_scheduler.py`
- Test: `tests/unit/test_provenance.py`

**Interfaces:**
- Produces: `CodexProofStrategyMethod(settings, client, model, role)`.
- Uses: existing `ProofSketch` schema and returns a `MethodResult(status="lead")`.

- [ ] **Step 1: Write failing method and scheduler tests**

```python
def test_codex_method_returns_non_authoritative_lead_and_receipt() -> None:
    result = method.run(context)
    assert result.status == "lead"
    assert result.claim is None
    assert result.witness is None
    assert result.codex_turn_receipt == fake_response.receipt
    assert b'"accounting_unit":"chatgpt_codex_turn"' in result.artifact


def test_scheduler_uses_codex_only_when_enabled_and_never_on_holdout() -> None:
    methods = codex_methods(enabled=True)
    experiments = scheduler(methods).allocate(development_problem, limit=4, seed=7)
    assert any(item.config["external_provider"] == "codex" for item in experiments)
    assert all(item.problem_id != holdout_problem.id for item in experiments)
```

Also prove no Codex method registers when disabled, API and Codex cannot both
register, model/role are copied into immutable experiment config, and
provenance changes with CLI version, launch policy, model, or Codex source.

- [ ] **Step 2: Verify red**

```bash
uv run pytest -q tests/unit/test_codex_method.py tests/unit/test_scheduler.py tests/unit/test_provenance.py
```

Expected: Codex method and schedule path are absent.

- [ ] **Step 3: Implement the method**

Use the existing `ProofSketch` schema but a separate method family:

```python
class CodexProofStrategyMethod:
    family = "codex_proof_strategy"
```

Implement
`__init__(self, settings: Settings, client: CodexClient, model: str, role: CodexModelRole) -> None`
with strict type/nonempty checks and
`run(self, context: MethodContext) -> MethodResult` with the flow below.

The prompt must state that the normalized problem is untrusted mathematical
data, request explicit strategy/lemmas/risks, permit repository inspection and
local tests, forbid claims of proof, and require the schema. The method requires
`context.external_execution_id`, builds `CodexRequest`, and stores the
structured response, usage, source/base identity, and patch digest in its
artifact.

Scheduler configuration:

```python
{
    "external_provider": "codex",
    "codex_role": "terra",
    "codex_model": settings.codex_model_terra,
    "max_output_tokens": settings.max_model_output_tokens,
    "provenance": method_identity,
}
```

Do not allocate Codex work to ordinary holdout rows. Holdouts remain reachable
only through explicit evaluation lanes.

- [ ] **Step 4: Run focused tests**

```bash
uv run pytest -q tests/unit/test_codex_method.py tests/unit/test_scheduler.py tests/unit/test_provenance.py
uv run ruff check src/mathloop/methods/codex_agent.py src/mathloop/scheduling.py src/mathloop/provenance.py tests/unit/test_codex_method.py
uv run mypy src/mathloop/methods/codex_agent.py src/mathloop/scheduling.py src/mathloop/provenance.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/mathloop/methods src/mathloop/scheduling.py src/mathloop/provenance.py tests/unit/test_codex_method.py tests/unit/test_scheduler.py tests/unit/test_provenance.py
git commit -m "feat: schedule Codex proof strategies"
```

---

### Task 7: Runtime Composition and Operator Commands

**Files:**
- Create: `src/mathloop/codex/supervisor.py`
- Modify: `src/mathloop/runtime.py`
- Modify: `src/mathloop/cli.py`
- Test: `tests/unit/test_cli.py`
- Test: `tests/integration/test_codex_runtime.py`

**Interfaces:**
- Produces: `build_runtime(repository: Repository, artifacts: ArtifactStore, *, api_enabled: bool, codex_enabled: bool = False, verifier_runner: JsonRunner | None = None, settings: Settings) -> Runtime`.
- Produces: `CodexSupervisor.start(max_turns)`, `status`, `pause`, `resume`, and `drain`.
- Produces: Typer command group `mathloop codex`.

- [ ] **Step 1: Write failing runtime and CLI tests**

Test:

```python
def test_runtime_rejects_api_and_codex_together(repository: Repository) -> None:
    with pytest.raises(ValueError, match="mutually exclusive"):
        build_runtime(
            repository,
            artifacts,
            api_enabled=True,
            codex_enabled=True,
            settings=settings,
        )


def test_codex_start_runs_bounded_turns_and_reports_usage(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, ["codex", "start", "--turns", "6", "--workers", "4"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["requested_turns"] == 6
    assert payload["usage"]["daily_limit"] == 100
```

Also cover `init`, `status`, `pause`, `resume`, `drain`, absent login, old CLI
version, unavailable Git, dirty main checkout, missing Sage image, and graceful
SIGINT/SIGTERM drain.

- [ ] **Step 2: Verify red**

```bash
uv run pytest -q tests/unit/test_cli.py tests/integration/test_codex_runtime.py
```

Expected: Codex command group and runtime mode are absent.

- [ ] **Step 3: Implement bounded supervisor and CLI**

`CodexSupervisor.start(max_turns, workers)` repeatedly invokes the existing
autonomous cycle with `codex_enabled=True`, stops when the requested number of
new Codex reservations has been reached, and never exceeds the durable daily
or concurrency policy. Pause state is persisted as an event/projection so a
restart cannot resume dispatch accidentally. Drain prevents new claims and
waits for active leases until the configured grace deadline.

Commands:

```text
mathloop codex init
mathloop codex start --turns 6 --workers 4
mathloop codex status
mathloop codex pause
mathloop codex resume
mathloop codex drain
mathloop codex report
```

`init` checks:

- `codex --version` is at least `0.145.0`.
- `codex login status` reports ChatGPT authentication.
- `OPENAI_API_KEY` and `CODEX_API_KEY` are absent from the launch environment.
- repository root is Git, `main` is clean except documented ignored/untracked
  operator paths, worktree root is writable, PostgreSQL is available, and the
  exact Sage image exists.

Status is read-only JSON and includes daily/role reservations, token totals,
active leases, worktree IDs, pause/drain state, last failure, and CLI version.

- [ ] **Step 4: Run runtime and CLI tests**

```bash
uv run pytest -q tests/unit/test_cli.py tests/integration/test_codex_runtime.py tests/integration/test_runtime_loop.py
uv run ruff check src/mathloop/codex/supervisor.py src/mathloop/runtime.py src/mathloop/cli.py tests/integration/test_codex_runtime.py
uv run mypy src/mathloop/codex/supervisor.py src/mathloop/runtime.py src/mathloop/cli.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/mathloop/codex/supervisor.py src/mathloop/runtime.py src/mathloop/cli.py tests/unit/test_cli.py tests/integration/test_codex_runtime.py
git commit -m "feat: operate bounded Codex cycles"
```

---

### Task 8: Foundation End-to-End and Credit-Consuming Canary Gate

**Files:**
- Create: `tests/e2e/test_codex_canary.py`
- Modify: `docs/verification/vertical-slice-acceptance.md`
- Create: `docs/verification/codex-foundation-acceptance.md`
- Modify: `.env.example`

**Interfaces:**
- Verifies the complete foundation path.
- Defines the only live test marker: `@pytest.mark.live_codex`.

- [ ] **Step 1: Add offline fake-CLI end-to-end coverage**

The test must:

1. Initialize real PostgreSQL.
2. Ingest the calibration corpus.
3. Register Codex methods.
4. Schedule one development proof-strategy experiment.
5. Run a fake Codex executable that edits its disposable worktree and emits a
   schema-valid proof strategy.
6. Persist every event and a bound usage receipt.
7. Store the patch as non-authoritative artifact evidence.
8. Report one consumed Codex turn and zero API dollars.
9. Prove no claim was machine-verified from the proof sketch.
10. Prove the source `main` checkout is unchanged and worktree cleanup completed.

- [ ] **Step 2: Run the offline end-to-end test**

```bash
uv run pytest -q tests/e2e/test_codex_canary.py -m "not live_codex"
```

Expected: pass without contacting Codex or OpenAI.

- [ ] **Step 3: Add the explicit live compatibility test**

The live test skips unless `MATHLOOP_RUN_LIVE_CODEX=1`. It invokes one Luna
turn with:

- A tiny deterministic structured response.
- `--ephemeral`.
- Shell network disabled.
- No OpenAI/Codex API key variables.
- A 120-second test timeout.
- No repository modification.

It asserts ChatGPT login, CLI version, `thread.started`, `turn.started`,
`turn.completed`, schema validity, non-negative usage, and no API billing row.

- [ ] **Step 4: Run all offline gates**

```bash
uv run pytest -q
uv run ruff check src tests
uv run mypy src
uv lock --check
git diff --check
```

Expected: all pass. Do not run the live test without an explicit operator
decision immediately before execution.

- [ ] **Step 5: Run one approved live smoke test and record evidence**

After the operator confirms one credit-consuming turn:

```bash
MATHLOOP_RUN_LIVE_CODEX=1 uv run pytest -q tests/e2e/test_codex_canary.py -m live_codex
```

Expected: one pass, exactly one started Codex turn, no API key, no API-dollar
reservation, and no publication action.

- [ ] **Step 6: Commit**

```bash
git add tests/e2e/test_codex_canary.py docs/verification .env.example
git commit -m "test: verify Codex supervisor foundation"
```

---

## Foundation Completion Gate

Before starting the research-intake plan:

```bash
uv run pytest -q
uv run ruff check src tests
uv run mypy src
uv lock --check
git diff --check
git status --short
```

Required outcome:

- Offline suite and static gates pass.
- One separately approved live Codex smoke test passes.
- The worktree is clean.
- A whole-branch reviewer reports no Critical or Important findings in dispatch,
  accounting, auth isolation, process cleanup, worktree containment,
  provenance, or mathematical verification.
