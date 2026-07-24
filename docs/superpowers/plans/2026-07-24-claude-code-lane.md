# Claude Code Execution Lane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a durable, subscription-authenticated Claude Code execution lane beside the Codex lane so both providers solve the same seeded problem corpus concurrently, roughly doubling daily agent-turn capacity without any API billing.

**Architecture:** The existing worker remains the outer authority for both lanes. Provider-neutral supervision machinery (disposable worktrees, bounded process supervision, deadline enforcement, receipt binding) is extracted from the Codex lane into a shared `mathloop.agents` package so it exists exactly once. The Claude lane adds its own domain types, a stream-JSON event parser, a fail-closed launch policy, and a separate turn ledger with its own accounting unit. The scheduler treats the two lanes as distinct method families over one problem population, and the promotion plan's fresh review becomes genuinely cross-provider when both lanes are enabled.

**Tech Stack:** Python 3.13, Claude Code CLI 2.1+ (pinned), subscription OAuth token from `claude setup-token`, PostgreSQL 17, psycopg 3, Pydantic 2, Typer, Git worktrees, pytest, Ruff, mypy.

## Global Constraints

- Complete `2026-07-23-codex-supervisor-foundation.md` first. The research and
  promotion plans do not block this plan, but promotion Task 5's
  cross-provider review tests require this plan's launch policy.
- Subscription authentication only: inject `CLAUDE_CODE_OAUTH_TOKEN` from
  trusted supervisor settings (generated once by the operator with
  `claude setup-token`); never set or forward `ANTHROPIC_API_KEY`.
- Record Claude accounting as turns and tokens with unit
  `claude_subscription_turn`; never a dollar-equivalent. Keep
  `experiments.cost_usd = 0` for Claude work. The `total_cost_usd` field on
  result events is preserved only as raw event evidence, never as billing.
- Never blend accounting units: Codex turns, Claude turns, and API dollars
  are reported side by side, never summed.
- Enforce 100 started Claude turns/day, four concurrent turns, 30
  minutes/turn, and model quotas of 40 Haiku, 40 Sonnet, and 20 Opus, with
  ten Opus turns reserved for cross-provider review/escalation.
- A durable `system.init` event consumes the turn; dispatched or ambiguous
  work is never retried automatically.
- Run Claude Code only in a disposable worktree with stream-JSON output,
  an explicit model, a pinned settings file, `WebFetch`/`WebSearch` denied,
  strict MCP config with no servers, and shell network disabled.
- The pinned settings file syntax is locked against the pinned CLI version
  during Task 4 and recorded in provenance. The behavioral integration tests
  — shell network denied, writes confined to the worktree — are the
  authority, not flag names.
- Live web discovery remains Codex-only in this phase; the Claude lane runs
  proof-strategy, solver, and read-only review roles.
- The OpenAI API provider remains mutually exclusive with every subscription
  lane. The Codex and Claude lanes may run together.
- Preserve the fixed independent mathematical verification kernel and the
  human publication gate unchanged.
- Every task follows red-green-refactor, runs focused tests, runs Ruff and
  mypy on touched code, and commits independently.

---

## File Structure

Create a shared provider-neutral core and a focused `mathloop.claude` package:

- `src/mathloop/agents/__init__.py` — shared agent-lane package.
- `src/mathloop/agents/domain.py` — `AgentProvider` enum shared by lanes.
- `src/mathloop/agents/supervision.py` — bounded process supervision extracted from the Codex client.
- `src/mathloop/agents/worktrees.py` — disposable worktree lifecycle moved from `mathloop.codex.worktrees`.
- `src/mathloop/claude/__init__.py` — Claude lane package.
- `src/mathloop/claude/domain.py` — immutable Claude policy, reservation, usage, and receipt types.
- `src/mathloop/claude/events.py` — bounded stream-JSON parsing and turn-state reduction.
- `src/mathloop/claude/launch.py` — command construction, pinned settings, environment allowlisting.
- `src/mathloop/claude/client.py` — supervised noninteractive Claude execution and schema parsing.
- `src/mathloop/methods/claude_agent.py` — Claude-backed proof-strategy method.
- `src/mathloop/claude/supervisor.py` — bounded cycle orchestration and status projection.

Modify existing boundaries rather than duplicating them:

- `src/mathloop/config.py` — Claude paths, auth, quotas, deadlines, model-role defaults.
- `src/mathloop/codex/client.py` and `worktrees.py` — delegate to the extracted shared core.
- `src/mathloop/methods/base.py` — Claude receipt field beside the Codex one.
- `src/mathloop/worker.py` — Claude arm of the frozen reservation tagged union.
- `src/mathloop/storage/schema.sql` — `claude_turns` and `claude_turn_events`.
- `src/mathloop/storage/repository.py` — shared reservation transaction helper plus Claude ledger methods.
- `src/mathloop/runtime.py` — co-run composition rules.
- `src/mathloop/scheduling.py` — Claude proof-strategy experiment configuration.
- `src/mathloop/cli.py` — `mathloop claude` commands and `mathloop agents status`.
- `src/mathloop/provenance.py` — Claude CLI/policy/settings provenance inputs.

Tests live in:

- `tests/unit/test_claude_domain.py`
- `tests/unit/test_claude_events.py`
- `tests/unit/test_claude_launch.py`
- `tests/unit/test_agents_supervision.py`
- `tests/unit/test_claude_client.py`
- `tests/unit/test_claude_method.py`
- `tests/integration/test_claude_repository.py`
- `tests/integration/test_claude_worker.py`
- `tests/integration/test_agents_runtime.py`
- `tests/e2e/test_claude_canary.py`

---

### Task 1: Claude Turn Policy and Immutable Accounting Types

**Files:**
- Create: `src/mathloop/claude/__init__.py`
- Create: `src/mathloop/claude/domain.py`
- Modify: `src/mathloop/config.py`
- Test: `tests/unit/test_claude_domain.py`
- Test: `tests/unit/test_config.py`

**Interfaces:**
- Consumes: `mathloop.domain.FrozenModel`.
- Produces: `ClaudeModelRole`, `ClaudeTurnStatus`, `ClaudePolicy`,
  `ClaudeUsage`, `ClaudeTurnReservation`, and `ClaudeTurnReceipt`.

- [ ] **Step 1: Write failing immutable-policy and receipt tests**

```python
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from mathloop.claude.domain import (
    ClaudeModelRole,
    ClaudePolicy,
    ClaudeTurnReceipt,
    ClaudeTurnReservation,
    ClaudeUsage,
)


def test_default_claude_policy_matches_approved_envelope() -> None:
    policy = ClaudePolicy()
    assert policy.daily_turn_limit == 100
    assert policy.concurrent_turn_limit == 4
    assert policy.turn_timeout_seconds == 1800
    assert policy.model_turn_limits == {"haiku": 40, "sonnet": 40, "opus": 20}
    assert policy.reserved_opus_turns == 10


def test_claude_receipt_is_bound_to_the_reservation() -> None:
    reservation = ClaudeTurnReservation(
        id=uuid4(),
        experiment_id=uuid4(),
        budget_day=date(2026, 7, 24),
        role=ClaudeModelRole.SONNET,
        model="claude-sonnet-5",
        deadline_seconds=1800,
        created_at=datetime.now(UTC),
    )
    receipt = ClaudeTurnReceipt(
        reservation_id=reservation.id,
        experiment_id=reservation.experiment_id,
        session_id="session-1",
        model=reservation.model,
        cli_version="2.1.0",
        usage=ClaudeUsage(
            input_tokens=100,
            cached_input_tokens=20,
            cache_creation_tokens=5,
            output_tokens=30,
        ),
        final_status="completed",
    )
    assert receipt.reservation_id == reservation.id
    with pytest.raises(ValidationError):
        ClaudeTurnReceipt.model_validate(
            {
                **receipt.model_dump(mode="python"),
                "final_status": "invented",
            }
        )
```

- [ ] **Step 2: Run tests and confirm missing module/types**

Run:

```bash
uv run pytest -q tests/unit/test_claude_domain.py
```

Expected: collection fails because `mathloop.claude.domain` does not exist.

- [ ] **Step 3: Implement the exact domain contract**

Create frozen enums/models with these signatures:

```python
class ClaudeModelRole(StrEnum):
    HAIKU = "haiku"
    SONNET = "sonnet"
    OPUS = "opus"


class ClaudeTurnStatus(StrEnum):
    RESERVED = "reserved"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    AMBIGUOUS = "ambiguous"


class ClaudePolicy(FrozenModel):
    daily_turn_limit: int = Field(default=100, ge=1)
    concurrent_turn_limit: int = Field(default=4, ge=1)
    turn_timeout_seconds: int = Field(default=1800, ge=60)
    model_turn_limits: dict[str, int] = Field(
        default_factory=lambda: {"haiku": 40, "sonnet": 40, "opus": 20}
    )
    reserved_opus_turns: int = Field(default=10, ge=0)
    max_jsonl_bytes: int = Field(default=16 * 1024 * 1024, ge=1024)
    max_patch_bytes: int = Field(default=4 * 1024 * 1024, ge=1024)


class ClaudeUsage(FrozenModel):
    input_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(ge=0)
    cache_creation_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class ClaudeTurnReservation(FrozenModel):
    id: UUID
    experiment_id: UUID
    budget_day: date
    role: ClaudeModelRole
    model: str = Field(min_length=1)
    deadline_seconds: int = Field(ge=60)
    created_at: datetime


class ClaudeTurnReceipt(FrozenModel):
    reservation_id: UUID
    experiment_id: UUID
    session_id: str = Field(min_length=1)
    model: str = Field(min_length=1)
    cli_version: str = Field(min_length=1)
    usage: ClaudeUsage
    final_status: Literal["completed"]
```

Add settings with exact defaults:

```python
claude_enabled: bool = False
claude_cli_path: Path = Path("claude")
claude_home: Path = Path(".mathloop/claude-home")
claude_config_dir: Path = Path(".mathloop/claude-config")
claude_worktree_root: Path = Path(".mathloop/claude-worktrees")
claude_oauth_token: SecretStr | None = None
claude_daily_turn_limit: int = Field(default=100, ge=1)
claude_concurrent_turn_limit: int = Field(default=4, ge=1)
claude_turn_timeout_seconds: int = Field(default=1800, ge=60)
claude_haiku_turn_limit: int = Field(default=40, ge=0)
claude_sonnet_turn_limit: int = Field(default=40, ge=0)
claude_opus_turn_limit: int = Field(default=20, ge=0)
claude_reserved_opus_turns: int = Field(default=10, ge=0)
claude_model_haiku: str = "claude-haiku-4-5"
claude_model_sonnet: str = "claude-sonnet-5"
claude_model_opus: str = "claude-opus-4-8"
claude_min_cli_version: str = "2.1.0"
claude_max_agent_turns: int = Field(default=40, ge=1)
```

Validate that role limits sum to the daily limit and reserved Opus turns do
not exceed the Opus limit. Resolve home/config/worktree paths like existing
artifact paths. `claude_oauth_token` is a secret; it must never appear in
logs, artifacts, provenance payloads, or status output.

- [ ] **Step 4: Run focused tests**

```bash
uv run pytest -q tests/unit/test_claude_domain.py tests/unit/test_config.py
uv run ruff check src/mathloop/claude/domain.py src/mathloop/config.py tests/unit/test_claude_domain.py
uv run mypy src/mathloop/claude/domain.py src/mathloop/config.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/mathloop/claude src/mathloop/config.py tests/unit/test_claude_domain.py tests/unit/test_config.py
git commit -m "feat: define Claude turn policy"
```

---

### Task 2: Bounded Claude Stream-JSON State Machine

**Files:**
- Create: `src/mathloop/claude/events.py`
- Test: `tests/unit/test_claude_events.py`

**Interfaces:**
- Consumes: newline-delimited bytes from `claude --print --output-format stream-json --verbose`.
- Produces: `ClaudeEventParser.feed(line: bytes) -> ClaudeEvent` and
  `ClaudeEventParser.finish() -> ClaudeTranscript`.

- [ ] **Step 1: Write failing parser tests**

```python
import json

import pytest

from mathloop.claude.events import ClaudeEventError, ClaudeEventParser


def encoded(payload: dict[str, object]) -> bytes:
    return json.dumps(payload).encode() + b"\n"


def test_parser_reduces_successful_result_and_usage() -> None:
    parser = ClaudeEventParser(max_bytes=8192)
    parser.feed(
        encoded({"type": "system", "subtype": "init", "session_id": "session-1"})
    )
    parser.feed(encoded({"type": "assistant", "message": {"content": "working"}}))
    parser.feed(
        encoded(
            {
                "type": "result",
                "subtype": "success",
                "session_id": "session-1",
                "num_turns": 3,
                "result": '{"strategy":"induction"}',
                "usage": {
                    "input_tokens": 10,
                    "cache_read_input_tokens": 2,
                    "cache_creation_input_tokens": 1,
                    "output_tokens": 4,
                },
                "total_cost_usd": 0.0123,
            }
        )
    )
    transcript = parser.finish()
    assert transcript.session_id == "session-1"
    assert transcript.dispatched is True
    assert transcript.terminal_subtype == "success"
    assert transcript.final_message == '{"strategy":"induction"}'
    assert transcript.usage.output_tokens == 4
    assert transcript.usage.cached_input_tokens == 2


def test_parser_represents_failed_result_without_final_message() -> None:
    parser = ClaudeEventParser(max_bytes=8192)
    parser.feed(
        encoded({"type": "system", "subtype": "init", "session_id": "session-2"})
    )
    parser.feed(
        encoded(
            {
                "type": "result",
                "subtype": "error_max_turns",
                "session_id": "session-2",
                "num_turns": 40,
            }
        )
    )
    transcript = parser.finish()
    assert transcript.dispatched is True
    assert transcript.terminal_subtype == "error_max_turns"
    assert transcript.final_message is None
    assert transcript.usage is None


def test_parser_rejects_duplicate_init_duplicate_result_and_oversize() -> None:
    parser = ClaudeEventParser(max_bytes=120)
    parser.feed(
        encoded({"type": "system", "subtype": "init", "session_id": "session-3"})
    )
    with pytest.raises(ClaudeEventError):
        parser.feed(
            encoded({"type": "system", "subtype": "init", "session_id": "session-3"})
        )
    with pytest.raises(ClaudeEventError):
        parser.feed(b"x" * 121)
```

- [ ] **Step 2: Verify red**

Run:

```bash
uv run pytest -q tests/unit/test_claude_events.py
```

Expected: import failure for `mathloop.claude.events`.

- [ ] **Step 3: Implement strict event parsing**

Implement:

```python
@dataclass(frozen=True)
class ClaudeEvent:
    sequence: int
    event_type: str
    payload: dict[str, object]
    raw_sha256: str


@dataclass(frozen=True)
class ClaudeTranscript:
    session_id: str
    dispatched: bool
    terminal_subtype: str
    final_message: str | None
    usage: ClaudeUsage | None
    events: tuple[ClaudeEvent, ...]


class ClaudeEventParser:
    def __init__(self, *, max_bytes: int) -> None:
        if type(max_bytes) is not int or max_bytes < 1:
            raise ValueError("max_bytes must be a positive integer")
        self._max_bytes = max_bytes
        self._bytes_seen = 0
        self._events: list[ClaudeEvent] = []
        self._session_id: str | None = None
        self._terminal_subtype: str | None = None
        self._final_message: str | None = None
        self._usage: ClaudeUsage | None = None
```

Add `feed(self, line: bytes) -> ClaudeEvent` and
`finish(self) -> ClaudeTranscript`. Their implementation must:

- Count raw bytes before decoding.
- Require one JSON object per line.
- Accept documented `system`, `assistant`, `user`, and `result` events.
- Preserve unknown events as evidence without treating them as lifecycle
  state.
- Treat exactly one `system`/`init` event as the dispatch marker and require
  exactly one `result` terminal event whose `session_id` matches the init
  event.
- Require a non-empty `result` string and non-negative integer usage fields
  when the terminal subtype is `success`. Map
  `cache_read_input_tokens -> cached_input_tokens` and
  `cache_creation_input_tokens -> cache_creation_tokens`.
- Yield `final_message=None` and `usage=None` for error terminal subtypes —
  a failed turn must still produce a transcript, because the ledger settles
  it as evidence.
- Preserve `total_cost_usd` only inside the raw event payload; never expose
  it on the transcript or receipt.
- Reject events after the terminal result.
- Never infer missing token counts or a successful terminal state.

- [ ] **Step 4: Run focused tests**

```bash
uv run pytest -q tests/unit/test_claude_events.py
uv run ruff check src/mathloop/claude/events.py tests/unit/test_claude_events.py
uv run mypy src/mathloop/claude/events.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/mathloop/claude/events.py tests/unit/test_claude_events.py
git commit -m "feat: parse Claude execution events"
```

---

### Task 3: Extract the Provider-Neutral Supervision Core

**Files:**
- Create: `src/mathloop/agents/__init__.py`
- Create: `src/mathloop/agents/domain.py`
- Create: `src/mathloop/agents/supervision.py`
- Create: `src/mathloop/agents/worktrees.py`
- Modify: `src/mathloop/codex/client.py`
- Modify: `src/mathloop/codex/worktrees.py`
- Test: `tests/unit/test_agents_supervision.py`
- Test: `tests/unit/test_codex_client.py` (must stay green unchanged)
- Test: `tests/unit/test_codex_worktrees.py` (must stay green unchanged)

**Interfaces:**
- Produces: `AgentProvider` with values `codex` and `claude`.
- Produces: `run_supervised_process(command: tuple[str, ...], *, cwd: Path, env: dict[str, str], deadline_seconds: float, on_line: Callable[[bytes], None], max_stderr_bytes: int) -> SupervisedProcessResult`.
- Produces: `AgentWorktreeManager.create(turn_id: UUID, base_sha: str) -> AgentWorktree` and `remove(worktree)` (moved, behavior identical).

- [ ] **Step 1: Write failing shared-supervision tests**

```python
from mathloop.agents.domain import AgentProvider
from mathloop.agents.supervision import run_supervised_process


def test_provider_enum_is_closed() -> None:
    assert {provider.value for provider in AgentProvider} == {"codex", "claude"}


def test_supervised_process_streams_lines_enforces_deadline_and_kills_group(
    fake_slow_child: Path,
) -> None:
    lines: list[bytes] = []
    with pytest.raises(SupervisedProcessTimeout) as raised:
        run_supervised_process(
            (str(fake_slow_child), "hang"),
            cwd=tmp_path,
            env={"PATH": "/bin"},
            deadline_seconds=0.2,
            on_line=lines.append,
            max_stderr_bytes=4096,
        )
    assert descendant_is_running(raised.value.descendant_pid) is False
    assert lines == [b'{"type":"started"}\n']
```

Also prove: `stdin=DEVNULL`, `start_new_session=True`, no shell, stdout lines
are delivered to `on_line` synchronously in order, stderr is drained
concurrently and truncated at `max_stderr_bytes`, and a nonzero exit code is
reported with the bounded stderr tail.

- [ ] **Step 2: Verify red**

```bash
uv run pytest -q tests/unit/test_agents_supervision.py
```

Expected: `mathloop.agents` does not exist.

- [ ] **Step 3: Extract without changing behavior**

- Move the process-supervision internals of `CodexClient.execute` (Popen
  construction, bounded line reader, concurrent stderr drain, absolute
  deadline, process-group kill) into `run_supervised_process`. The Codex
  client keeps its ordering contract (worktree, schema file, dispatch
  marker, event acknowledgment, receipt, cleanup) and delegates only the
  process mechanics.
- Move `mathloop/codex/worktrees.py` to `mathloop/agents/worktrees.py`,
  renaming `CodexWorktreeManager` to `AgentWorktreeManager`. Keep
  `mathloop/codex/worktrees.py` as a one-line re-export so foundation
  imports keep working; the manager takes its root path as a constructor
  argument so each lane gets its own configured root.
- Add `AgentProvider(StrEnum)` with members `CODEX = "codex"` and
  `CLAUDE = "claude"`.

The proof of this task is that the existing Codex unit and integration
suites pass without edits.

- [ ] **Step 4: Run shared and untouched Codex gates**

```bash
uv run pytest -q tests/unit/test_agents_supervision.py tests/unit/test_codex_client.py tests/unit/test_codex_worktrees.py tests/integration/test_codex_worker.py
uv run ruff check src/mathloop/agents src/mathloop/codex/client.py src/mathloop/codex/worktrees.py tests/unit/test_agents_supervision.py
uv run mypy src/mathloop/agents src/mathloop/codex/client.py src/mathloop/codex/worktrees.py
```

Expected: all pass; Codex tests unmodified.

- [ ] **Step 5: Commit**

```bash
git add src/mathloop/agents src/mathloop/codex/client.py src/mathloop/codex/worktrees.py tests/unit/test_agents_supervision.py
git commit -m "refactor: extract shared agent supervision core"
```

---

### Task 4: Fail-Closed Claude Launch Policy and Pinned Sandbox Settings

**Files:**
- Create: `src/mathloop/claude/launch.py`
- Modify: `src/mathloop/provenance.py`
- Test: `tests/unit/test_claude_launch.py`
- Test: `tests/unit/test_provenance.py`

**Interfaces:**
- Produces: `ClaudeLaunchPolicy.command(model: str, prompt: str, mode: Literal["solver", "review"] = "solver") -> tuple[str, ...]`.
- Produces: `ClaudeLaunchPolicy.environment(source: Mapping[str, str]) -> dict[str, str]`.
- Produces: `ClaudeLaunchPolicy.write_pinned_settings() -> Path`.

- [ ] **Step 1: Write failing policy tests**

```python
def test_solver_launch_is_streamed_sandboxed_and_offline(tmp_path: Path) -> None:
    policy = ClaudeLaunchPolicy(
        claude_binary=Path("/opt/claude"),
        claude_home=tmp_path / "home",
        claude_config_dir=tmp_path / "config",
        settings_path=tmp_path / "settings.json",
        max_agent_turns=40,
    )
    command = policy.command(model="claude-sonnet-5", prompt="Solve the problem.")
    assert command[:2] == ("/opt/claude", "--print")
    assert ("--output-format", "stream-json") == adjacent_pair(command, "--output-format")
    assert "--verbose" in command
    assert ("--model", "claude-sonnet-5") == adjacent_pair(command, "--model")
    assert ("--max-turns", "40") == adjacent_pair(command, "--max-turns")
    assert ("--permission-mode", "acceptEdits") == adjacent_pair(command, "--permission-mode")
    assert "WebFetch" in flag_value(command, "--disallowedTools")
    assert "WebSearch" in flag_value(command, "--disallowedTools")
    assert "--strict-mcp-config" in command
    assert command[-1] == "Solve the problem."


def test_review_launch_is_read_only(tmp_path: Path) -> None:
    command = policy(tmp_path).command(
        model="claude-opus-4-8",
        prompt="Review the exact patch.",
        mode="review",
    )
    assert ("--permission-mode", "plan") == adjacent_pair(command, "--permission-mode")
    assert flag_value(command, "--allowedTools") == "Read Glob Grep"


def test_environment_is_allowlisted_and_never_carries_api_keys() -> None:
    env = policy(tmp_path).environment(
        {
            "PATH": "/bin",
            "HOME": "/Users/operator",
            "ANTHROPIC_API_KEY": "secret",
            "OPENAI_API_KEY": "secret",
            "DATABASE_URL": "secret",
            "CLAUDE_CODE_OAUTH_TOKEN": "stale-from-shell",
        },
        oauth_token="trusted-token",
    )
    assert env["HOME"] == str(tmp_path / "home")
    assert env["CLAUDE_CONFIG_DIR"] == str(tmp_path / "config")
    assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "trusted-token"
    assert "ANTHROPIC_API_KEY" not in env
    assert "OPENAI_API_KEY" not in env
    assert "DATABASE_URL" not in env
```

- [ ] **Step 2: Verify red**

```bash
uv run pytest -q tests/unit/test_claude_launch.py
```

Expected: module is missing.

- [ ] **Step 3: Implement exact command, settings, and environment**

`ClaudeLaunchPolicy.command` must emit this ordered shape (`mode="solver"`):

```python
(
    str(self.claude_binary),
    "--print",
    "--output-format",
    "stream-json",
    "--verbose",
    "--model",
    model,
    "--max-turns",
    str(self.max_agent_turns),
    "--settings",
    str(self.settings_path),
    "--permission-mode",
    "acceptEdits",
    "--allowedTools",
    "Read Glob Grep Edit Write Bash",
    "--disallowedTools",
    "WebFetch WebSearch",
    "--strict-mcp-config",
    prompt,
)
```

`mode="review"` differs only in `--permission-mode plan` and
`--allowedTools "Read Glob Grep"`. The working directory is not a flag: the
client runs the process with `cwd=<worktree>` through the shared supervision
core.

`write_pinned_settings` writes this content with mode `0600`:

```json
{
  "sandbox": {"enabled": true, "network": {"allow": []}},
  "permissions": {"deny": ["WebFetch", "WebSearch"]}
}
```

The exact settings-key syntax is verified once against the pinned CLI
version during this task (Claude Code's sandbox/settings schema is the one
part of this contract owned by the vendor). If the pinned version spells
these keys differently, update the constant here, record the final bytes'
SHA-256 in provenance, and keep the behavioral tests as the authority.

`environment` allows only `PATH`, `TMPDIR`, `LANG`, `LC_ALL`, and
`SSL_CERT_FILE` from the source. It sets `HOME`, `CLAUDE_CONFIG_DIR`, and
`CLAUDE_CODE_OAUTH_TOKEN` from trusted settings only — a token present in
the source environment is dropped, never forwarded. Provenance gains the
CLI version, command shape, settings digest, and environment allowlist.

- [ ] **Step 4: Run focused tests**

```bash
uv run pytest -q tests/unit/test_claude_launch.py tests/unit/test_provenance.py
uv run ruff check src/mathloop/claude/launch.py src/mathloop/provenance.py tests/unit/test_claude_launch.py
uv run mypy src/mathloop/claude/launch.py src/mathloop/provenance.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/mathloop/claude/launch.py src/mathloop/provenance.py tests/unit/test_claude_launch.py tests/unit/test_provenance.py
git commit -m "feat: pin Claude launch and sandbox policy"
```

---

### Task 5: Transactional Claude Turn Ledger

**Files:**
- Modify: `src/mathloop/storage/schema.sql`
- Modify: `src/mathloop/storage/repository.py`
- Test: `tests/integration/test_claude_repository.py`
- Test: `tests/integration/test_codex_repository.py` (must stay green unchanged)

**Interfaces:**
- Produces: `Repository.reserve_claude_turn(experiment_id: UUID, worker_id: str, role: ClaudeModelRole, model: str, policy: ClaudePolicy, now: datetime) -> ClaudeTurnReservation | None`.
- Produces: `mark_claude_turn_dispatched`, `append_claude_turn_event`,
  `complete_claude_turn`, `fail_claude_turn`, `reconcile_claude_turns`, and
  `claude_usage_status`.

- [ ] **Step 1: Write failing transactional tests**

Cover these exact cases:

```python
def test_claude_turn_limit_and_concurrency_are_atomic(repository: Repository) -> None:
    policy = ClaudePolicy(
        daily_turn_limit=2,
        concurrent_turn_limit=1,
        model_turn_limits={"haiku": 0, "sonnet": 2, "opus": 0},
        reserved_opus_turns=0,
    )
    first = repository.reserve_claude_turn(
        experiment_id=experiment_id_1,
        worker_id="worker-1",
        role=ClaudeModelRole.SONNET,
        model="claude-sonnet-5",
        policy=policy,
        now=fixed_now,
    )
    assert first is not None
    assert repository.reserve_claude_turn(
        experiment_id=experiment_id_2,
        worker_id="worker-2",
        role=ClaudeModelRole.SONNET,
        model="claude-sonnet-5",
        policy=policy,
        now=fixed_now,
    ) is None


def test_claude_and_codex_budgets_are_independent(repository: Repository) -> None:
    exhaust_codex_daily_budget(repository)
    reservation = repository.reserve_claude_turn(
        experiment_id=experiment_id_3,
        worker_id="worker-1",
        role=ClaudeModelRole.HAIKU,
        model="claude-haiku-4-5",
        policy=ClaudePolicy(),
        now=fixed_now,
    )
    assert reservation is not None
```

Also test 40/40/20 role limits, ten reserved Opus turns, concurrent callers
under PostgreSQL advisory locking (a different advisory-lock key space from
the Codex lane so the lanes never serialize each other), idempotent event
replay, conflicting event replay, lease expiry before dispatch, ambiguous
dispatch never re-reserved, and conservative reconciliation after dispatch.

- [ ] **Step 2: Verify red**

```bash
uv run pytest -q tests/integration/test_claude_repository.py
```

Expected: schema tables and repository methods are absent.

- [ ] **Step 3: Add schema and share the reservation transaction shape**

Add:

```sql
CREATE TABLE IF NOT EXISTS claude_turns (
    id UUID PRIMARY KEY,
    experiment_id UUID NOT NULL UNIQUE REFERENCES experiments(id),
    budget_day DATE NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('haiku', 'sonnet', 'opus')),
    model TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN (
            'reserved', 'dispatched', 'running', 'completed',
            'failed', 'timed_out', 'ambiguous'
        )
    ),
    lease_owner TEXT NOT NULL,
    lease_expires_at TIMESTAMPTZ NOT NULL,
    session_id TEXT NULL,
    cli_version TEXT NULL,
    input_tokens BIGINT NULL CHECK (input_tokens >= 0),
    cached_input_tokens BIGINT NULL CHECK (cached_input_tokens >= 0),
    cache_creation_tokens BIGINT NULL CHECK (cache_creation_tokens >= 0),
    output_tokens BIGINT NULL CHECK (output_tokens >= 0),
    failure_kind TEXT NULL,
    failure_message TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS claude_turn_events (
    turn_id UUID NOT NULL REFERENCES claude_turns(id),
    sequence INTEGER NOT NULL CHECK (sequence >= 0),
    event_type TEXT NOT NULL,
    raw_sha256 TEXT NOT NULL,
    payload JSONB NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (turn_id, sequence)
);
```

Extract the Codex reservation transaction body into a private
`_reserve_agent_turn` helper parameterized by table name, advisory-lock key
space, role-limit map, and reserved-deep-tier floor, then implement both
`reserve_codex_turn` and `reserve_claude_turn` as thin typed wrappers. The
advisory-lock logic, daily counting, concurrency counting, quota
enforcement, and exact-replay comparison must exist once. The proof is that
the existing Codex repository integration suite passes unmodified.

`append_claude_turn_event` compares the entire persisted event on replay.
`complete_claude_turn` requires prior dispatch, exact reservation/receipt
identity, exactly one persisted `system` init event, and one matching
`result` success event. Terminal rows are immutable.

- [ ] **Step 4: Run both lanes' repository gates**

```bash
uv run pytest -q tests/integration/test_claude_repository.py tests/integration/test_codex_repository.py
uv run ruff check src/mathloop/storage/repository.py tests/integration/test_claude_repository.py
uv run mypy src/mathloop/storage/repository.py
```

Expected: all pass, including concurrency tests, with Codex tests unchanged.

- [ ] **Step 5: Commit**

```bash
git add src/mathloop/storage/schema.sql src/mathloop/storage/repository.py tests/integration/test_claude_repository.py
git commit -m "feat: persist Claude turn accounting"
```

---

### Task 6: Supervised Claude Client and Worker Lane

**Files:**
- Create: `src/mathloop/claude/client.py`
- Modify: `src/mathloop/methods/base.py`
- Modify: `src/mathloop/worker.py`
- Test: `tests/unit/test_claude_client.py`
- Test: `tests/integration/test_claude_worker.py`

**Interfaces:**
- Produces: `ClaudeRequest[T]`, `ClaudeResponse[T]`, and
  `ClaudeClient.execute(request, emit_event)`.
- Extends: `MethodResult.claude_turn_receipt` beside
  `MethodResult.codex_turn_receipt`.
- Extends: the worker's frozen reservation tagged union with a Claude arm.

- [ ] **Step 1: Write fake-CLI red tests**

Create an executable fake Claude script fixture that emits valid
stream-JSON, malformed JSON, a delayed result event, a child process, and
nonzero exits based on an argument. Tests must prove:

```python
def test_claude_client_returns_schema_value_usage_and_patch(fake_claude: Path) -> None:
    response = client(fake_claude).execute(
        request(response_schema=ProofSketch),
        events.append,
    )
    assert response.value.strategy == "induction"
    assert response.receipt.usage.output_tokens == 12
    assert response.patch_sha256 == hashlib.sha256(response.patch).hexdigest()
    assert any(event.event_type == "system" for event in events)


def test_schema_invalid_final_message_fails_the_turn_without_retry(
    fake_claude: Path,
) -> None:
    with pytest.raises(ClaudeTurnFailed) as raised:
        client(fake_claude).execute(
            request(mode="invalid_json", response_schema=ProofSketch),
            sink,
        )
    assert raised.value.dispatched is True
    assert raised.value.failure_kind == "schema_validation"


def test_claude_client_timeout_kills_descendants_and_never_completes(
    fake_claude: Path,
) -> None:
    with pytest.raises(ClaudeTurnTimedOut) as raised:
        client(fake_claude, timeout=0.1).execute(
            request(mode="hang", response_schema=ProofSketch),
            sink,
        )
    assert raised.value.dispatched is True
    assert descendant_is_running(raised.value.descendant_pid) is False
```

Worker integration tests must prove the parent persists the dispatch marker
before the fake CLI starts, persists events as they arrive through the
existing `external_event`/`external_event_acknowledged` pipe protocol,
blocks replay after dispatch, settles pre-start failure without consuming a
turn, rejects a receipt for another reservation, and never mixes a Claude
receipt into a Codex reservation or vice versa.

- [ ] **Step 2: Verify red**

```bash
uv run pytest -q tests/unit/test_claude_client.py tests/integration/test_claude_worker.py
```

Expected: client, receipt field, and worker arm are absent.

- [ ] **Step 3: Implement the client**

Use these contracts:

```python
@dataclass(frozen=True)
class ClaudeRequest[T: BaseModel]:
    reservation: ClaudeTurnReservation
    prompt: str
    base_sha: str
    response_schema: type[T]


@dataclass(frozen=True)
class ClaudeResponse[T: BaseModel]:
    value: T
    receipt: ClaudeTurnReceipt
    patch: bytes
    patch_sha256: str


class ClaudeClient:
```

Implement
`ClaudeClient.execute(self, request: ClaudeRequest[T], emit_event: Callable[[ClaudeEvent], None]) -> ClaudeResponse[T]`
in this order:

1. Create the detached worktree via the shared `AgentWorktreeManager` rooted
   at `claude_worktree_root`.
2. Render `request.response_schema.model_json_schema()` into the prompt's
   final section: Claude Code has no `--output-schema` flag, so the prompt
   requires the last message to be exactly one JSON object matching the
   schema, and the client validates locally.
3. Call `context.mark_external_execution_started()` immediately before
   process start.
4. Start Claude through `run_supervised_process` with the launch-policy
   command, allowlisted environment, `cwd=<worktree>`, and one absolute
   deadline across start, reads, wait, parse, diff, and cleanup.
5. Feed each stdout line to `ClaudeEventParser` and call `emit_event`
   synchronously before reading the next line.
6. Parse the final message with `response_schema.model_validate_json`. A
   schema-invalid final message is a failed turn (`schema_validation`); the
   turn is consumed and never retried automatically.
7. Capture and hash the worktree patch.
8. Construct a reservation-bound receipt from the success transcript.
9. Remove the worktree in `finally`; preserve a cleanup failure as terminal
   infrastructure evidence.

The worker's frozen tagged union gains a Claude arm beside the API-dollar
and Codex-turn arms. It continues writing `experiments.cost_usd = 0` for
Claude work while storing Claude usage only in `claude_turns`. The result
artifact must label the accounting unit `claude_subscription_turn`, never
`usd` and never `chatgpt_codex_turn`.

- [ ] **Step 4: Run focused process and worker tests**

```bash
uv run pytest -q tests/unit/test_claude_client.py tests/integration/test_claude_worker.py tests/unit/test_worker.py tests/integration/test_worker_billing.py
uv run ruff check src/mathloop/claude/client.py src/mathloop/methods/base.py src/mathloop/worker.py tests/unit/test_claude_client.py tests/integration/test_claude_worker.py
uv run mypy src/mathloop/claude/client.py src/mathloop/methods/base.py src/mathloop/worker.py
```

Expected: all pass; no orphan fake descendants remain.

- [ ] **Step 5: Commit**

```bash
git add src/mathloop/claude/client.py src/mathloop/methods/base.py src/mathloop/worker.py tests/unit/test_claude_client.py tests/integration/test_claude_worker.py
git commit -m "feat: supervise Claude agent turns"
```

---

### Task 7: Claude Proof-Strategy Method and Scheduling

**Files:**
- Create: `src/mathloop/methods/claude_agent.py`
- Modify: `src/mathloop/methods/__init__.py`
- Modify: `src/mathloop/scheduling.py`
- Test: `tests/unit/test_claude_method.py`
- Test: `tests/unit/test_scheduler.py`

**Interfaces:**
- Produces: `ClaudeProofStrategyMethod(settings, client, model, role)` with
  `family = "claude_proof_strategy"`.
- Uses: existing `ProofSketch` schema and returns a `MethodResult(status="lead")`.

- [ ] **Step 1: Write failing method and scheduler tests**

```python
def test_claude_method_returns_non_authoritative_lead_and_receipt() -> None:
    result = method.run(context)
    assert result.status == "lead"
    assert result.claim is None
    assert result.witness is None
    assert result.claude_turn_receipt == fake_response.receipt
    assert b'"accounting_unit":"claude_subscription_turn"' in result.artifact


def test_scheduler_mixes_both_lanes_and_never_uses_holdouts() -> None:
    methods = agent_methods(codex_enabled=True, claude_enabled=True)
    experiments = scheduler(methods).allocate(development_problem, limit=8, seed=7)
    providers = {item.config["external_provider"] for item in experiments}
    assert providers == {"codex", "claude"}
    assert all(item.problem_id != holdout_problem.id for item in experiments)
```

Also prove no Claude method registers when disabled, the Claude lane
registers independently of the Codex lane, model/role are copied into
immutable experiment config, provider assignment is deterministic under a
fixed seed, and provenance changes with CLI version, launch policy, model,
or settings digest.

- [ ] **Step 2: Verify red**

```bash
uv run pytest -q tests/unit/test_claude_method.py tests/unit/test_scheduler.py
```

Expected: Claude method and schedule path are absent.

- [ ] **Step 3: Implement the method**

Use the existing `ProofSketch` schema but a separate method family:

```python
class ClaudeProofStrategyMethod:
    family = "claude_proof_strategy"
```

Implement
`__init__(self, settings: Settings, client: ClaudeClient, model: str, role: ClaudeModelRole) -> None`
with strict type/nonempty checks and
`run(self, context: MethodContext) -> MethodResult`.

The prompt must state that the normalized problem is untrusted mathematical
data, request explicit strategy/lemmas/risks, permit repository inspection
and local tests, forbid claims of proof, forbid web access, and require the
final message to be exactly one JSON object matching the embedded schema.
The method requires `context.external_execution_id`, builds `ClaudeRequest`,
and stores the structured response, usage, source/base identity, and patch
digest in its artifact.

Scheduler configuration:

```python
{
    "external_provider": "claude",
    "claude_role": "sonnet",
    "claude_model": settings.claude_model_sonnet,
    "max_output_tokens": settings.max_model_output_tokens,
    "provenance": method_identity,
}
```

Do not allocate Claude work to ordinary holdout rows. Holdouts remain
reachable only through explicit evaluation lanes.

- [ ] **Step 4: Run focused tests**

```bash
uv run pytest -q tests/unit/test_claude_method.py tests/unit/test_scheduler.py
uv run ruff check src/mathloop/methods/claude_agent.py src/mathloop/scheduling.py tests/unit/test_claude_method.py
uv run mypy src/mathloop/methods/claude_agent.py src/mathloop/scheduling.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/mathloop/methods src/mathloop/scheduling.py tests/unit/test_claude_method.py tests/unit/test_scheduler.py
git commit -m "feat: schedule Claude proof strategies"
```

---

### Task 8: Co-Run Composition and Operator Commands

**Files:**
- Create: `src/mathloop/claude/supervisor.py`
- Modify: `src/mathloop/runtime.py`
- Modify: `src/mathloop/cli.py`
- Modify: `src/mathloop/reporting.py`
- Test: `tests/unit/test_cli.py`
- Test: `tests/integration/test_agents_runtime.py`

**Interfaces:**
- Extends: `build_runtime(repository, artifacts, *, api_enabled: bool, codex_enabled: bool = False, claude_enabled: bool = False, verifier_runner: JsonRunner | None = None, settings: Settings) -> Runtime`.
- Produces: `ClaudeSupervisor.start(max_turns, workers)`, `status`, `pause`,
  `resume`, and `drain`.
- Produces: Typer command groups `mathloop claude` and `mathloop agents`.

- [ ] **Step 1: Write failing runtime and CLI tests**

```python
def test_runtime_rejects_api_with_any_subscription_lane(repository: Repository) -> None:
    with pytest.raises(ValueError, match="mutually exclusive"):
        build_runtime(
            repository,
            artifacts,
            api_enabled=True,
            claude_enabled=True,
            settings=settings,
        )


def test_runtime_composes_codex_and_claude_together(repository: Repository) -> None:
    runtime = build_runtime(
        repository,
        artifacts,
        api_enabled=False,
        codex_enabled=True,
        claude_enabled=True,
        settings=settings,
    )
    families = {method.family for method in runtime.methods}
    assert "codex_proof_strategy" in families
    assert "claude_proof_strategy" in families


def test_agents_status_reports_lanes_side_by_side(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, ["agents", "status"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["codex"]["accounting_unit"] == "chatgpt_codex_turn"
    assert payload["claude"]["accounting_unit"] == "claude_subscription_turn"
    assert "total" not in payload
```

Also cover `claude init`, `start --turns 6 --workers 4`, `status`, `pause`,
`resume`, `drain`, absent auth, old CLI version, unavailable Git, dirty main
checkout, per-lane pause independence (pausing Claude does not pause Codex),
and graceful SIGINT/SIGTERM drain.

- [ ] **Step 2: Verify red**

```bash
uv run pytest -q tests/unit/test_cli.py tests/integration/test_agents_runtime.py
```

Expected: Claude command group and co-run mode are absent.

- [ ] **Step 3: Implement bounded supervisor and CLI**

`ClaudeSupervisor.start(max_turns, workers)` mirrors the Codex supervisor:
it repeatedly invokes the existing autonomous cycle with
`claude_enabled=True`, stops when the requested number of new Claude
reservations has been reached, and never exceeds the durable daily or
concurrency policy. Pause state is persisted per lane so a restart cannot
resume dispatch accidentally and lanes pause independently.

Commands:

```text
mathloop claude init
mathloop claude start --turns 6 --workers 4
mathloop claude status
mathloop claude pause
mathloop claude resume
mathloop claude drain
mathloop claude report
mathloop agents status
```

`claude init` checks:

- `claude --version` is at least `claude_min_cli_version`.
- Subscription authentication works: `claude_oauth_token` is configured (or
  the isolated `claude_config_dir` holds subscription credentials), and
  `ANTHROPIC_API_KEY` is absent from the launch environment.
- The pinned settings file exists with the recorded digest, the repository
  root is Git, `main` is clean except documented ignored/untracked operator
  paths, the Claude worktree root is writable, and PostgreSQL is available.

`mathloop agents status` is read-only JSON with one top-level key per
enabled lane (`codex`, `claude`), each carrying daily/role reservations,
token totals, active leases, worktree IDs, pause/drain state, last failure,
CLI version, and its accounting unit. There is no combined total: the units
are not commensurable, and reporting must never imply they are.

- [ ] **Step 4: Run runtime and CLI tests**

```bash
uv run pytest -q tests/unit/test_cli.py tests/integration/test_agents_runtime.py tests/integration/test_codex_runtime.py tests/integration/test_runtime_loop.py
uv run ruff check src/mathloop/claude/supervisor.py src/mathloop/runtime.py src/mathloop/cli.py src/mathloop/reporting.py tests/integration/test_agents_runtime.py
uv run mypy src/mathloop/claude/supervisor.py src/mathloop/runtime.py src/mathloop/cli.py src/mathloop/reporting.py
```

Expected: all pass, including the untouched Codex runtime suite.

- [ ] **Step 5: Commit**

```bash
git add src/mathloop/claude/supervisor.py src/mathloop/runtime.py src/mathloop/cli.py src/mathloop/reporting.py tests/unit/test_cli.py tests/integration/test_agents_runtime.py
git commit -m "feat: operate Codex and Claude lanes together"
```

---

### Task 9: Lane End-to-End and Credit-Consuming Canary Gate

**Files:**
- Create: `tests/e2e/test_claude_canary.py`
- Create: `docs/verification/claude-lane-acceptance.md`
- Modify: `.env.example`

**Interfaces:**
- Verifies the complete Claude lane path and the two-lane co-run.
- Defines the only live test marker for this lane: `@pytest.mark.live_claude`.

- [ ] **Step 1: Add offline fake-CLI end-to-end coverage**

The test must:

1. Initialize real PostgreSQL.
2. Ingest the calibration corpus.
3. Register both Codex and Claude methods with fake CLIs.
4. Schedule development experiments until both lanes have run at least one
   proof-strategy turn on the same problem population.
5. Persist every event and a bound usage receipt per lane in that lane's
   tables only.
6. Store each patch as non-authoritative artifact evidence.
7. Report Codex turns and Claude turns side by side and zero API dollars.
8. Prove no claim was machine-verified from either proof sketch.
9. Prove the source `main` checkout is unchanged and both worktree roots are
   clean.
10. Prove pausing one lane leaves the other lane dispatching.

- [ ] **Step 2: Run the offline end-to-end test**

```bash
uv run pytest -q tests/e2e/test_claude_canary.py -m "not live_claude"
```

Expected: pass without contacting Claude, Codex, OpenAI, or Anthropic.

- [ ] **Step 3: Add the explicit live compatibility test**

The live test skips unless `MATHLOOP_RUN_LIVE_CLAUDE=1`. It invokes one
Haiku turn with:

- A tiny deterministic structured response.
- The pinned settings file and stream-JSON output.
- Shell network disabled; `WebFetch`/`WebSearch` denied.
- No `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` variables.
- A 120-second test timeout.
- No repository modification.

It asserts subscription auth, CLI version, one `system` init event, one
`result` success event, schema validity, non-negative usage, and no API
billing row. It must also prove the sandbox behaviorally: a model-issued
`curl https://example.org` command fails inside the turn.

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

After the operator confirms one subscription-consuming turn:

```bash
MATHLOOP_RUN_LIVE_CLAUDE=1 uv run pytest -q tests/e2e/test_claude_canary.py -m live_claude
```

Expected: one pass, exactly one started Claude turn, no API key, no
API-dollar reservation, and no publication action.

- [ ] **Step 6: Commit**

```bash
git add tests/e2e/test_claude_canary.py docs/verification/claude-lane-acceptance.md .env.example
git commit -m "test: verify Claude execution lane"
```

---

## Claude Lane Completion Gate

Before enabling continuous two-lane operation:

```bash
uv run pytest -q
uv run ruff check src tests
uv run mypy src
uv lock --check
git diff --check
git status --short
```

Required outcome:

- Offline suite and static gates pass, including the untouched Codex suites
  after the shared-core extraction.
- One separately approved live Claude smoke test passes with behavioral
  proof of network denial.
- The worktree is clean.
- A whole-branch reviewer reports no Critical or Important findings in
  dispatch, per-lane accounting separation, auth isolation (no
  `ANTHROPIC_API_KEY`, token never logged), process cleanup, worktree
  containment, provenance, or mathematical verification.
- Promotion Task 5's cross-provider review tests pass once the promotion
  plan is implemented: a Codex-authored patch is reviewed by a Claude
  read-only turn and vice versa.
