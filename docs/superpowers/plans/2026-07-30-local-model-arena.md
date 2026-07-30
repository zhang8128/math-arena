# Local-Model Arena and Mathloop Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a shared, hard-local-only LM Studio provider that powers bounded Qwen3.6 tool-using `.timeloop` turns and production `mathloop` proof leads without any paid inference fallback.

**Architecture:** A dedicated LM Studio lifecycle controller resolves and loads one already-installed model. One `LocalModelProvider` implements both strict structured generation and provider-neutral tool calling; `.timeloop` and production `mathloop` consume those interfaces while retaining host-owned tools, durable provenance, zero-dollar receipts, and independent verification.

**Tech Stack:** Python 3.13, Pydantic 2, OpenAI Python SDK 2.47 against a loopback LM Studio endpoint, PostgreSQL, Typer, pytest, Lean 4/mathlib, LM Studio `lms` CLI.

## Global Constraints

- Preserve the pre-existing user modification at `.timeloop/exam/results.jsonl`; never stage, revert, or rewrite it.
- Default runtime is LM Studio at `http://127.0.0.1:1234`.
- Logical model selector is `qwen3.6-35b-a3b`; startup must resolve exactly one already-installed compatible model.
- Context length is 32,768 tokens, generation concurrency is one, turn timeout is 1,800 seconds, and idle model TTL is 900 seconds.
- Per turn, allow at most 12 model actions, 4,096 output tokens per action, 12 tool invocations, 6 subprocesses, 120 seconds per subprocess, 16 MiB of artifacts, 6 research queries, two pre-side-effect transport retries, two structured-output repairs, and 2 MiB of assembled prompt/tool-result bytes.
- The implementation may call `lms server status`, `lms server start`, `lms ls`, `lms ps`, `lms load`, and resource estimation. It must not contain or construct `lms get` or any model-download request.
- External cognition mode is exactly one of `none`, `local`, `openai`, or `codex`.
- Local mode rejects non-loopback inference URLs, registers no paid provider, has no paid fallback, and scrubs paid-provider credentials from every child process.
- Local research tools use only public unauthenticated endpoints, direct approved URL retrieval, or a configured loopback search service.
- Model output is never verification, promotion, publication, or grading authority.
- Arena runs are bounded batches; continuous mode is out of scope.
- The real Qwen3.6 canary is a release gate. Code may be complete while the download is absent, but the feature is not release-ready until the canary passes.
- Ollama is a future explicit transport, not an automatic fallback; provider and arena contracts must contain no LM Studio wire or lifecycle types.
- Use TDD for every behavior change, run fresh relevant and full verification, and commit after each task.

---

## File Structure

New focused units:

- `src/mathloop/local/domain.py` — immutable local runtime and tool-call contracts.
- `src/mathloop/local/security.py` — loopback validation and child-environment scrubbing.
- `src/mathloop/local/lmstudio.py` — `lms` discovery, model resolution, startup, load, and health.
- `src/mathloop/providers/local.py` — structured and tool-calling local inference adapter.
- `src/mathloop/arena/domain.py` — strict arena action, turn, claim, and durable-event schemas.
- `src/mathloop/arena/storage.py` — immutable snapshots, append-only summaries, artifact hashes, and atomic materialization.
- `src/mathloop/arena/selection.py` — deterministic changing problem and method/frame selection.
- `src/mathloop/arena/tools.py` — typed host tool registry and bounded execution.
- `src/mathloop/arena/research.py` — unmetered curated research backends.
- `src/mathloop/arena/verification.py` — independent Lean/computation verification receipts.
- `src/mathloop/arena/runner.py` — bounded model/tool loop and turn orchestration.
- `.timeloop/methods.jsonl` — initial append-only method/frame population.
- `.timeloop/local/turns.jsonl` — tracked append-only turn-summary stream.

Existing units modified:

- `src/mathloop/config.py` — local settings and external cognition mode.
- `src/mathloop/providers/base.py` — provider-neutral tool-calling protocol.
- `src/mathloop/billing.py` — no structural change expected; local receipts use existing zero-capable fields.
- `src/mathloop/methods/proof_sketch.py` — configurable provider identity in proof-lead artifacts.
- `src/mathloop/provenance.py` — local proof method implementation identity.
- `src/mathloop/runtime.py` — mode-safe local method registration and worker propagation.
- `src/mathloop/cli.py` — `mathloop local` commands.
- `.gitignore` — ignore only local arena staging/lease scratch, not durable summaries.
- `pyproject.toml` / `uv.lock` — only if a direct dependency is required after implementation proves the pinned SDK insufficient.
- `.timeloop/README.md` / `.timeloop/ARENA.md` — operator and authority documentation.

---

### Task 1: External cognition mode and local-only security boundary

**Files:**
- Create: `src/mathloop/local/__init__.py`
- Create: `src/mathloop/local/security.py`
- Modify: `src/mathloop/config.py`
- Modify: `src/mathloop/runtime.py`
- Modify: `src/mathloop/cli.py`
- Test: `tests/unit/test_config.py`
- Test: `tests/unit/test_local_security.py`
- Test: `tests/unit/test_cli.py`
- Test: `tests/integration/test_runtime_loop.py`

**Interfaces:**
- Produces: `ExternalCognitionMode(StrEnum)`.
- Produces: `require_loopback_http_url(value: str) -> str`.
- Produces: `scrub_paid_credentials(environment: Mapping[str, str]) -> dict[str, str]`.
- Produces: `build_runtime(repository: Repository, artifacts: ArtifactStore, *, api_enabled: bool = False, codex_enabled: bool = False, external_mode: ExternalCognitionMode | None = None, settings: Settings | None = None, verifier_runner: JsonRunner | None = None) -> Runtime`.
- Preserves: current `api_enabled` and `codex_enabled` CLI behavior by translating them once at the composition boundary, then removes boolean combinations from internal registration logic.

- [ ] **Step 1: Write failing settings and security tests**

```python
def test_local_defaults_are_exact() -> None:
    settings = Settings(_env_file=None)
    assert settings.local_model_selector == "qwen3.6-35b-a3b"
    assert settings.local_api_base_url == "http://127.0.0.1:1234"
    assert settings.local_context_length == 32_768
    assert settings.local_model_concurrency == 1
    assert settings.local_turn_timeout_seconds == 1_800
    assert settings.local_model_ttl_seconds == 900
    assert settings.local_max_model_actions == 12
    assert settings.local_max_output_tokens_per_action == 4_096
    assert settings.local_max_tool_invocations == 12
    assert settings.local_max_subprocesses == 6
    assert settings.local_max_subprocess_seconds == 120
    assert settings.local_max_artifact_bytes == 16 * 1024 * 1024
    assert settings.local_max_research_queries == 6
    assert settings.local_max_pre_side_effect_retries == 2
    assert settings.local_max_repair_attempts == 2
    assert settings.local_max_context_bytes == 2 * 1024 * 1024


@pytest.mark.parametrize(
    "url",
    [
        "https://api.openai.com/v1",
        "http://192.168.1.4:1234",
        "http://example.test:1234",
        "file:///tmp/socket",
    ],
)
def test_local_endpoint_must_be_loopback(url: str) -> None:
    with pytest.raises(ValueError, match="loopback"):
        require_loopback_http_url(url)


def test_paid_credentials_are_removed_without_mutating_source() -> None:
    source = {
        "PATH": "/bin",
        "OPENAI_API_KEY": "paid",
        "CODEX_API_KEY": "paid",
        "ANTHROPIC_API_KEY": "paid",
    }
    assert scrub_paid_credentials(source) == {"PATH": "/bin"}
    assert source["OPENAI_API_KEY"] == "paid"
```

- [ ] **Step 2: Run the focused tests and capture RED**

Run:

```bash
uv run pytest -q \
  tests/unit/test_config.py \
  tests/unit/test_local_security.py \
  tests/integration/test_runtime_loop.py -k 'local or cognition or credentials'
```

Expected: collection/import failures because the local security types do not exist.

- [ ] **Step 3: Implement the mode and security contracts**

Add to `src/mathloop/config.py`:

```python
from enum import StrEnum


class ExternalCognitionMode(StrEnum):
    NONE = "none"
    LOCAL = "local"
    OPENAI = "openai"
    CODEX = "codex"


class Settings(BaseSettings):
    external_cognition_mode: ExternalCognitionMode = ExternalCognitionMode.NONE
    local_lms_cli_path: Path = Path("lms")
    local_model_selector: str = "qwen3.6-35b-a3b"
    local_api_base_url: str = "http://127.0.0.1:1234"
    local_context_length: int = Field(default=32_768, ge=4_096, le=262_144)
    local_model_concurrency: int = Field(default=1, ge=1, le=1)
    local_turn_timeout_seconds: int = Field(default=1_800, ge=60, le=7_200)
    local_model_ttl_seconds: int = Field(default=900, ge=60, le=86_400)
    local_max_model_actions: int = Field(default=12, ge=1, le=64)
    local_max_output_tokens_per_action: int = Field(default=4_096, ge=128, le=32_768)
    local_max_tool_invocations: int = Field(default=12, ge=0, le=64)
    local_max_subprocesses: int = Field(default=6, ge=0, le=32)
    local_max_subprocess_seconds: int = Field(default=120, ge=1, le=600)
    local_max_artifact_bytes: int = Field(
        default=16 * 1024 * 1024,
        ge=1_024,
        le=256 * 1024 * 1024,
    )
    local_max_research_queries: int = Field(default=6, ge=0, le=32)
    local_max_pre_side_effect_retries: int = Field(default=2, ge=0, le=4)
    local_max_repair_attempts: int = Field(default=2, ge=0, le=4)
    local_max_context_bytes: int = Field(
        default=2 * 1024 * 1024,
        ge=65_536,
        le=16 * 1024 * 1024,
    )
```

Add to `src/mathloop/local/security.py`:

```python
from collections.abc import Mapping
from urllib.parse import urlsplit

PAID_CREDENTIAL_KEYS = frozenset({
    "OPENAI_API_KEY",
    "CODEX_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
})


def require_loopback_http_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "::1", "localhost"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("local inference endpoint must be an uncredentialed loopback HTTP URL")
    return value.rstrip("/")


def scrub_paid_credentials(environment: Mapping[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in environment.items()
        if key not in PAID_CREDENTIAL_KEYS
    }
```

Make `Runtime` carry one `external_mode`, and make registration reject any
paid/local method already present when another mode is requested. Keep CLI
compatibility by mapping `--api-enabled` to `OPENAI` and Codex commands to
`CODEX`; reject conflicting legacy flags before constructing a runtime.

- [ ] **Step 4: Add direct-construction and both-registration-order tests**

Test all pairs of non-`NONE` modes. Construct `Runtime` directly as well as
through `build_runtime`; both must reject mixed registration. Assert that local
mode does not inspect `OPENAI_API_KEY` and cannot register `proof_sketch` or
`codex_proof_strategy`.

- [ ] **Step 5: Run focused and compatibility suites**

Run:

```bash
uv run pytest -q \
  tests/unit/test_config.py \
  tests/unit/test_local_security.py \
  tests/unit/test_cli.py \
  tests/integration/test_runtime_loop.py
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add \
  src/mathloop/local/__init__.py \
  src/mathloop/local/security.py \
  src/mathloop/config.py \
  src/mathloop/runtime.py \
  src/mathloop/cli.py \
  tests/unit/test_config.py \
  tests/unit/test_local_security.py \
  tests/unit/test_cli.py \
  tests/integration/test_runtime_loop.py
git commit -m "feat: enforce local-only cognition mode"
```

---

### Task 2: LM Studio lifecycle and exact installed-model resolution

**Files:**
- Create: `src/mathloop/local/domain.py`
- Create: `src/mathloop/local/lmstudio.py`
- Test: `tests/unit/test_lmstudio_lifecycle.py`

**Interfaces:**
- Consumes: validated local settings and `scrub_paid_credentials`.
- Produces: `InstalledLocalModel`, `LocalRuntimeIdentity`, `LMStudioStatus`.
- Produces: `LMStudioLifecycle.status() -> LMStudioStatus`.
- Produces: `LMStudioLifecycle.ensure_ready() -> LocalRuntimeIdentity`.
- Produces: `CommandRunner.run(command: tuple[str, ...], *, timeout: float) -> CompletedProcess[str]`.

- [ ] **Step 1: Write model-resolution and forbidden-download tests**

```python
def test_resolve_model_requires_one_normalized_match() -> None:
    models = (
        InstalledLocalModel(
            model_key="qwen3.6-35b-a3b",
            path="lmstudio-community/Qwen3.6-35B-A3B-MLX-6bit",
            size_bytes=31_000_000_000,
            format="safetensors",
            quantization="6bit",
        ),
    )
    assert resolve_installed_model(models, "qwen3.6-35b-a3b") == models[0]


def test_lifecycle_never_constructs_download_command() -> None:
    runner = RecordingRunner(server_running=False, installed_models=())
    lifecycle = lifecycle_with(runner)
    with pytest.raises(LocalCapabilityUnavailableError, match="not installed"):
        lifecycle.ensure_ready()
    assert all("get" not in command for command in runner.commands)
```

Add cases for absent matches, ambiguous matches, malformed `lms` JSON, nonzero
CLI exits, status/start/load timeouts, and a model whose resolved identity
changes between listing and health verification. Include installed Qwen3.5
27B/35B/122B fixtures and prove none can satisfy the Qwen3.6 selector; the
lifecycle must never substitute a nearby family, parameter count, or
quantization.

- [ ] **Step 2: Run tests and capture RED**

Run:

```bash
uv run pytest -q tests/unit/test_lmstudio_lifecycle.py
```

Expected: import failure for `mathloop.local.lmstudio`.

- [ ] **Step 3: Implement immutable lifecycle domain records**

```python
@dataclass(frozen=True)
class InstalledLocalModel:
    model_key: str
    path: str
    size_bytes: int
    format: str
    quantization: str | None


@dataclass(frozen=True)
class LocalRuntimeIdentity:
    runtime: str
    endpoint: str
    model_key: str
    model_path: str
    model_format: str
    quantization: str | None
    context_length: int
    loaded_identifier: str
    identity_sha256: str
```

Canonicalize identity as sorted compact JSON and SHA-256 it. Validate all
strings, sizes, URLs, and context lengths at construction.

- [ ] **Step 4: Implement lifecycle command flow**

`ensure_ready()` must issue only these exact command families:

```python
(lms, "server", "status", "--json", "--quiet")
(lms, "ls", "--json")
(lms, "server", "start")
(lms, "load", model_key, "--context-length", "32768",
 "--ttl", "900", "--identifier", "mathloop-qwen3.6-35b-a3b", "--yes")
```

Before loading, run the same `lms load` command with `--estimate-only` inserted
after the model key. After loading, check `GET /v1/models` through an injected
loopback HTTP probe and require the stable identifier. Record whether the
server was already running, but never stop it.

- [ ] **Step 5: Test idempotency and ownership boundaries**

Cover:

- already-running server plus already-loaded model performs no start/load;
- stopped server starts once;
- repeated `ensure_ready()` returns the same identity;
- a server started by another process between status and start converges;
- an already-running server is never stopped;
- all subprocess environments have paid credentials removed;
- `lms get` is absent from production source:

```bash
! rg -n 'lms.*get|\"get\".*model' src/mathloop/local
```

- [ ] **Step 6: Run tests and static checks**

```bash
uv run pytest -q tests/unit/test_lmstudio_lifecycle.py
uv run ruff check src/mathloop/local tests/unit/test_lmstudio_lifecycle.py
uv run mypy
```

- [ ] **Step 7: Commit**

```bash
git add \
  src/mathloop/local/domain.py \
  src/mathloop/local/lmstudio.py \
  tests/unit/test_lmstudio_lifecycle.py
git commit -m "feat: manage installed LM Studio models"
```

---

### Task 3: Shared structured and tool-calling local provider

**Files:**
- Modify: `src/mathloop/providers/base.py`
- Create: `src/mathloop/providers/local.py`
- Modify: `src/mathloop/providers/__init__.py`
- Test: `tests/unit/test_local_provider.py`
- Test: `tests/unit/test_billing.py`

**Interfaces:**
- Consumes: `LocalRuntimeIdentity`, existing `ModelRequest[T]`, and existing billing records.
- Produces: `LocalToolDefinition`, `LocalToolCall`, `LocalAgentRequest`, `LocalAgentResponse`.
- Produces: `ToolCallingModelProvider.next_action(request: LocalAgentRequest) -> LocalAgentResponse`.
- Produces: `LocalModelProvider.generate(request, schema) -> ModelResponse`.
- Produces: `LocalModelProvider.next_action(request) -> LocalAgentResponse`.

- [ ] **Step 1: Write zero-dollar structured-response tests**

```python
def test_local_provider_returns_strict_value_and_zero_dollar_receipt() -> None:
    provider = provider_with(
        parsed=ProofSketch(
            strategy="Reduce to residues.",
            lemmas=["Classify residue classes."],
            risks=["The modulus may be insufficient."],
        ),
        usage={"prompt_tokens": 120, "completion_tokens": 45},
    )
    request = model_request(
        cost_authorization=ModelCostAuthorization(Decimal("0.000000"))
    )
    response = provider.generate(request, ProofSketch)
    assert response.value.strategy == "Reduce to residues."
    assert request.cost_authorization.max_cost_usd == Decimal("0.000000")
    assert response.billing_authorization.provider == "local-lmstudio"
    assert response.billing_authorization.reserved_cost_usd == Decimal("0.000000")
    assert response.billing_receipt.actual_cost_usd == Decimal("0.000000")
    assert response.usage.input_tokens == 120
    assert response.usage.output_tokens == 45
```

Add rejection cases for missing usage, negative counts, wrong parsed schema,
refusal, incomplete output, output over cap, mismatched model, non-loopback
client, absent response ID, and elapsed deadline.

Add a compatibility test that `ModelCostAuthorization(Decimal("0.000000"))`
is valid provider-neutral input, while `OpenAIProvider.generate` rejects that
cap as insufficient before issuing a paid request.

- [ ] **Step 2: Write typed tool-call tests**

```python
def test_next_action_returns_only_declared_tool_calls() -> None:
    provider = provider_with_tool_calls([
        {"id": "call_1", "name": "run_python", "arguments": {"program": "print(2+2)"}}
    ])
    response = provider.next_action(agent_request(tools=(python_tool(),)))
    assert response.tool_calls == (
        LocalToolCall(
            id="call_1",
            name="run_python",
            arguments={"program": "print(2+2)"},
        ),
    )
    assert response.content is None
```

Reject duplicate call IDs, undeclared tool names, invalid JSON arguments,
content mixed with tool calls, excessive call counts, and response payloads
larger than the configured bound.

- [ ] **Step 3: Run focused tests and capture RED**

```bash
uv run pytest -q tests/unit/test_local_provider.py tests/unit/test_billing.py
```

Expected: missing tool-provider contracts and local provider.

- [ ] **Step 4: Add provider-neutral tool contracts**

Add frozen records to `providers/base.py`:

```python
@dataclass(frozen=True)
class LocalToolDefinition:
    name: str
    description: str
    input_schema: dict[str, object]


@dataclass(frozen=True)
class LocalToolCall:
    id: str
    name: str
    arguments: dict[str, object]


@dataclass(frozen=True)
class LocalAgentRequest:
    model: str
    messages: tuple[dict[str, object], ...]
    tools: tuple[LocalToolDefinition, ...]
    max_output_tokens: int
    timeout_seconds: float


@dataclass(frozen=True)
class LocalAgentResponse:
    response_id: str
    content: str | None
    tool_calls: tuple[LocalToolCall, ...]
    usage: ModelUsage
    billing_authorization: BillingAuthorization
    billing_receipt: BillingReceipt


class ToolCallingModelProvider(Protocol):
    def next_action(self, request: LocalAgentRequest) -> LocalAgentResponse:
        raise NotImplementedError
```

Validate nested messages and schemas as bounded JSON-compatible data. Do not
place LM Studio names in these records. Add an import-boundary test proving
`providers/base.py`, `arena/`, and production methods do not import
`LMStudioLifecycle` or LM Studio response classes; only the composition root
and `providers/local.py` may bind the generic contracts to that transport.

Change `ModelCostAuthorization.__post_init__` to call
`validate_database_usd(..., positive=False)`. Paid adapters retain their
provider-specific positive price/cap check; local callers must pass exactly
`Decimal("0.000000")`, and `LocalModelProvider` rejects any positive request
cap rather than presenting it as local accounting.

- [ ] **Step 5: Implement `LocalModelProvider`**

Use a separately injected compatible client. The real factory may use the
pinned OpenAI SDK with the validated loopback `base_url`, but the class must
not import `OPENAI_PRICING_CATALOG` or `OpenAIProvider`.

For structured generation:

```python
completion = client.chat.completions.parse(
    model=identity.loaded_identifier,
    messages=[
        {"role": "system", "content": request.system},
        {"role": "user", "content": request.prompt},
    ],
    response_format=schema,
    max_tokens=request.max_output_tokens,
    timeout=remaining,
    extra_body={"enable_thinking": request.effort != "none"},
)
```

Create authorization and receipt after validated usage is available:

```python
authorization = BillingAuthorization(
    provider="local-lmstudio",
    model=identity.model_key,
    authorized_input_tokens=usage.input_tokens,
    max_output_tokens=request.max_output_tokens,
    reserved_cost_usd=Decimal("0.000000"),
    pricing_version="local-compute-v1",
    pricing_source="local://lmstudio/unmetered",
)
```

For tool actions, call `chat.completions.create` with only the typed tool
catalog. Normalize the compatible response into `LocalAgentResponse`.

- [ ] **Step 6: Prove paid-provider isolation**

Add a test that patches `openai.OpenAI` and asserts the only construction uses
the exact loopback base URL and a fixed non-secret local sentinel key. Patch
`OpenAIProvider` to raise if constructed during local tests. Search the local
provider for pricing imports and external URLs:

```bash
! rg -n 'OPENAI_PRICING|api\\.openai|developers\\.openai' \
  src/mathloop/providers/local.py
```

- [ ] **Step 7: Run provider and existing OpenAI suites**

```bash
uv run pytest -q \
  tests/unit/test_local_provider.py \
  tests/unit/test_openai_provider.py \
  tests/unit/test_billing.py \
  tests/unit/test_proof_sketch_method.py
uv run ruff check src/mathloop/providers tests/unit/test_local_provider.py
uv run mypy
```

- [ ] **Step 8: Commit**

```bash
git add \
  src/mathloop/providers/base.py \
  src/mathloop/providers/local.py \
  src/mathloop/providers/__init__.py \
  tests/unit/test_local_provider.py \
  tests/unit/test_billing.py
git commit -m "feat: add zero-cost local model provider"
```

---

### Task 4: Durable arena domain, method population, and deterministic selection

**Files:**
- Create: `src/mathloop/arena/__init__.py`
- Create: `src/mathloop/arena/domain.py`
- Create: `src/mathloop/arena/storage.py`
- Create: `src/mathloop/arena/selection.py`
- Create: `.timeloop/methods.jsonl`
- Create: `.timeloop/local/turns.jsonl`
- Modify: `.gitignore`
- Test: `tests/unit/test_arena_domain.py`
- Test: `tests/unit/test_arena_storage.py`
- Test: `tests/unit/test_arena_selection.py`

**Interfaces:**
- Produces: `ArenaProblem`, `ArenaMethod`, `ArenaFrame`, `ArenaSelection`, `ArenaTurnRecord`, `ArenaTurnStatus`, `ArenaSnapshot`, and `ArenaPartition`.
- Produces: `ArenaStateStore.snapshot() -> ArenaSnapshot`.
- Produces: `ArenaStateStore.append_turn(record: ArenaTurnRecord, expected_snapshot_digest: str) -> None`.
- Produces: `ArenaSelector.select(snapshot: ArenaSnapshot, seed: int, partition: ArenaPartition = ArenaPartition.LIVE) -> ArenaSelection`.

- [ ] **Step 1: Write strict domain tests**

Define the strict contracts before constructing fixtures:

```python
class ArenaPartition(StrEnum):
    LIVE = "live"
    HELD_OUT = "held_out"


class ArenaTurnStatus(StrEnum):
    NEGATIVE_RESULT = "negative_result"
    VERIFIED_LEAD = "verified_lead"
    INVALID_MODEL_OUTPUT = "invalid_model_output"
    TOOL_FAILURE = "tool_failure"
    VERIFIER_REJECTED = "verifier_rejected"
    TIMEOUT = "timeout"
    INTERRUPTED = "interrupted"


class ArenaProblem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str
    statement: str
    state: Literal["new", "active", "parked", "settled"]
    partition: ArenaPartition
    next_action: str | None
    content_sha256: str


class ArenaFrame(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str
    state: Literal["established", "trial", "retired"]
    description: str
    parent_ids: tuple[str, ...]
    content_sha256: str


class ArenaMethod(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str
    version: int
    state: Literal["established", "trial", "retired"]
    description: str
    sources: tuple[str, ...]
    parent_ids: tuple[str, ...]
    frame_ids: tuple[str, ...]
    composition: tuple[str, ...]
    content_sha256: str


class ArenaSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    digest: str
    problems: tuple[ArenaProblem, ...]
    methods: tuple[ArenaMethod, ...]
    frames: tuple[ArenaFrame, ...]
    prior_turns_sha256: str
    ledger_tail_sha256: str
    notebook_bundle_sha256: str


class ArenaSelection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    problem: ArenaProblem
    methods: tuple[ArenaMethod, ...]
    frames: tuple[ArenaFrame, ...]
    partition: ArenaPartition
    lane: Literal["resume", "explore_problem", "explore_frame", "exploit", "held_out"]
    snapshot_digest: str
```

Define tests showing that turn records require:

```python
record = ArenaTurnRecord(
    schema_version=1,
    event_version=1,
    batch_id=UUID("00000000-0000-0000-0000-000000000000"),
    turn_id=UUID("00000000-0000-0000-0000-000000000001"),
    turn_index=0,
    seed=7,
    problem_id="forge-digit-products",
    method_ids=("predict-confirm-prove",),
    frame_ids=("finite-state-dynamics", "base-change"),
    runtime_identity=runtime_identity_fixture,
    model_identity_sha256="a" * 64,
    generation_config_sha256="e" * 64,
    prompt_sha256="b" * 64,
    tool_catalog_sha256="c" * 64,
    model_response_ids=("response-1",),
    tool_receipt_ids=("tool-1",),
    searched=("bases 2 through 12",),
    hypotheses=("The orbit graph has a bounded attractor.",),
    ruled_out=("linear invariant",),
    structure=("digit products collapse under sorted multisets",),
    technique=("predict, confirm computationally, then formalize",),
    candidate_claims=(),
    caveats=("Finite search is not a universal proof.",),
    novelty_queries=("OEIS: digit product orbit base 10",),
    source_metadata_digests=("f" * 64,),
    next_action="Enumerate base 13 through 20.",
    status=ArenaTurnStatus.NEGATIVE_RESULT,
    verification_receipt_ids=(),
    artifact_digests=("d" * 64,),
    proposed_durable_changes=("append negative result to notebook",),
    input_tokens=300,
    output_tokens=90,
    wall_seconds=12.5,
    cost_usd=Decimal("0.000000"),
)
```

Reject blank durable fields, unknown status, unbounded collections, invalid
digests, nonzero local cost, non-finite time, and a positive status without an
independent verification receipt.

- [ ] **Step 2: Write append/replay/concurrency tests**

Cover exact replay, contradictory same-turn replay, two-process append,
truncated final line recovery, fsync-visible append, stale snapshot rejection,
artifact existence, and preservation of pre-existing notebook/ledger bytes
when validation fails.

- [ ] **Step 3: Write changing-population selection tests**

Use a fixture with four problems and four methods. Assert:

- same snapshot/seed yields the same selection;
- a concrete `next_action` receives the resume lane;
- verified unseen-problem outcomes affect exploitation;
- at least 15% of a deterministic 100-seed sample selects underused problems;
- at least 15% selects underused methods;
- at least 15% selects underused frame identities or frame compositions;
- retired methods are excluded;
- a trial method can be selected only by novelty/exploration;
- `ArenaPartition.HELD_OUT` selects only frozen held-out problems;
- held-out problems are never used for online method or frame promotion.

- [ ] **Step 4: Run tests and capture RED**

```bash
uv run pytest -q \
  tests/unit/test_arena_domain.py \
  tests/unit/test_arena_storage.py \
  tests/unit/test_arena_selection.py
```

- [ ] **Step 5: Implement tracked durable files**

Seed `.timeloop/methods.jsonl` with immutable version-1 records for:

- invariant tabulation;
- decidable-family reduction;
- derived-invariant grouping;
- state-space collapse;
- known-value sanity check;
- boundary argmax check;
- map-image reduction;
- wall detection and parking;
- intersection reduction;
- predict-confirm-prove;
- mathlib specialized-case generalization.

Each line includes `id`, `version`, `state`, `description`, `sources`,
`parent_ids`, `frame_ids`, `composition`, and `content_sha256`. A frame is a
named transformation of representation or attention; a composition is an
ordered tuple of existing frame IDs, never model-written executable code.
Seed established frame IDs for algebraic, combinatorial, computational,
finite-state, invariant, extremal, probabilistic, geometric, base-change,
dual/complement, and specialized-case-generalization views. This is the
initial Prism-compatible vocabulary: if an external Prism adapter later
provides identities, import them through the same immutable schema rather than
giving Prism scheduling or verification authority. Seed
`.timeloop/local/turns.jsonl` with one schema event so the file is tracked.

Ignore only:

```gitignore
.timeloop/local/staging/
.timeloop/local/leases/
```

Do not ignore the turn summary or method population.

- [ ] **Step 6: Implement atomic storage and deterministic projection**

Use append-only JSONL with canonical sorted JSON, an exclusive lock file under
`.mathloop/local-arena/locks`, flush plus `fsync`, and content-addressed raw
artifacts under `.mathloop/local-arena/artifacts`. Compute one snapshot digest
over the exact pool, method, turn-summary, ledger-tail, and relevant notebook
bytes.

Selection uses seeded rank functions rather than global randomness. Project
outcomes from turn records; never let model-supplied scores enter the
projection. Reserve 10% of deterministic selections for
`ArenaPartition.HELD_OUT`, 15% for underused live problems, and 15% for
underused method/frame candidates; the remaining 60% may exploit resumable or
high-posterior live work. Held-out outcomes enter evaluation reports but never
online scores, promotion, retirement, or revival.

- [ ] **Step 7: Run tests and arena lint**

```bash
uv run pytest -q \
  tests/unit/test_arena_domain.py \
  tests/unit/test_arena_storage.py \
  tests/unit/test_arena_selection.py
.timeloop/bin/lint
git diff --check
```

- [ ] **Step 8: Commit without staging the user exam result**

```bash
git add \
  src/mathloop/arena/__init__.py \
  src/mathloop/arena/domain.py \
  src/mathloop/arena/storage.py \
  src/mathloop/arena/selection.py \
  .timeloop/methods.jsonl \
  .timeloop/local/turns.jsonl \
  .gitignore \
  tests/unit/test_arena_domain.py \
  tests/unit/test_arena_storage.py \
  tests/unit/test_arena_selection.py
git diff --cached --name-only | grep -v '^\\.timeloop/exam/results\\.jsonl$'
git commit -m "feat: add durable local arena state"
```

---

### Task 5: Bounded host tools and unmetered research

**Files:**
- Create: `src/mathloop/arena/tools.py`
- Create: `src/mathloop/arena/research.py`
- Create: `src/mathloop/arena/execution.py`
- Modify: `src/mathloop/processes.py`
- Test: `tests/unit/test_arena_tools.py`
- Test: `tests/unit/test_arena_research.py`
- Test: `tests/integration/test_arena_execution.py`

**Interfaces:**
- Consumes: provider-neutral `LocalToolDefinition` and `scrub_paid_credentials`.
- Produces: `ArenaToolRegistry.catalog() -> tuple[LocalToolDefinition, ...]`.
- Produces: `ArenaToolRegistry.execute(call: LocalToolCall, turn: TurnWorkspace) -> ToolReceipt`.
- Produces: `ResearchBackend.query(request: ResearchRequest) -> ResearchReceipt`.
- Produces: `BoundedProcessRunner.run(spec: ProcessSpec) -> ProcessReceipt`.
- Produces: frozen `TurnWorkspace`, `ToolReceipt`, `ResearchRequest`, `ResearchReceipt`, `ProcessSpec`, and `ProcessReceipt` records; each carries the owning turn/invocation identity and enforced byte/time limits.

- [ ] **Step 1: Write filesystem and subprocess escape tests**

Test rejection of:

- `..` traversal;
- absolute paths;
- symlinks escaping the repository;
- reads under `.env`, `.git`, `.codex`, `.engram`, and user-home credentials;
- canonical writes;
- shell strings instead of argument arrays;
- background descendants;
- output above the byte cap;
- elapsed timeout;
- paid credentials in child environment.

The positive fixture reads one notebook and runs:

```python
ProcessSpec(
    argv=(sys.executable, "-I", "-c", "print(sum(range(10)))"),
    cwd=workspace.scratch,
    timeout_seconds=5,
    max_output_bytes=4096,
)
```

- [ ] **Step 2: Write unmetered research tests**

```python
def test_paid_research_backend_is_rejected() -> None:
    with pytest.raises(ValueError, match="unmetered"):
        ResearchRegistry().register(
            name="paid-search",
            backend=FakeBackend(),
            metered=True,
        )


def test_remote_search_service_must_be_loopback() -> None:
    with pytest.raises(ValueError, match="loopback"):
        LocalSearchBackend("https://search.example.com")
```

Test OEIS and Crossref adapters with fake HTTP responses, request/result hashes,
rate limiting, bounded response size, explicit user agent, and no ambient
credentials. Test the arXiv adapter separately so an arXiv identifier, title,
authors, version date, and abstract digest survive normalization. Test
`search_web` with an injected loopback endpoint and prove it rejects remote,
credentialed, or metered search services.

- [ ] **Step 3: Run tests and capture RED**

```bash
uv run pytest -q \
  tests/unit/test_arena_tools.py \
  tests/unit/test_arena_research.py \
  tests/integration/test_arena_execution.py
```

- [ ] **Step 4: Implement typed tool registry**

Initial tool names and schemas are exact:

- `read_arena_file(path: str)`;
- `read_artifact(sha256: str)`;
- `run_python(program: str, timeout_seconds: int)`;
- `run_lean(file: str, declaration: str, replacement: str)`;
- `search_oeis(query: str)`;
- `search_crossref(query: str)`;
- `search_arxiv(query: str)`;
- `search_web(query: str)`;
- `fetch_approved_url(url: str)`;
- `stage_turn_record(record: object)`.

Each handler returns:

```python
@dataclass(frozen=True)
class ToolReceipt:
    invocation_id: str
    tool_name: str
    request_sha256: str
    output_sha256: str
    artifact_digest: str | None
    bounded_preview: str
    started_at: datetime
    completed_at: datetime
    status: str
```

The registry rejects unknown tools before dispatch and returns an existing
receipt for an exact invocation replay.

Define `TurnWorkspace` with `turn_id`, resolved repository root, resolved
scratch root, deadline, remaining subprocess/research/artifact budgets, and a
receipt store. Define `ProcessReceipt` and `ResearchReceipt` with request and
response digests, bounded preview, timestamps, status, and error
classification. No receipt stores a secret or unrestricted raw environment.

- [ ] **Step 5: Implement bounded process lifecycle**

Use `start_new_session=True`, explicit `cwd`, scrubbed `env`, stdin closed,
captured binary output, timeout, and the repository's existing process-tree
termination helper. Record descendant process groups before acknowledging tool
start. Kill the whole registered tree on timeout or parent failure.

- [ ] **Step 6: Implement curated research**

Allow only:

- OEIS JSON/API endpoints;
- Crossref REST endpoints;
- arXiv export API;
- direct HTTPS URLs whose hostname appears in an explicit configured allowlist;
- a configured loopback local search endpoint used only by `search_web`.

Reject any backend marked metered or requiring an API credential. Persist exact
query, URL, retrieval time, status, body digest, and bounded source metadata.
Pass research backends only the validated query or public identifier; add an
integration test that decoy notebook text, system prompts, proof drafts, and
environment values are absent from every captured outbound request.

- [ ] **Step 7: Run tests and containment probes**

```bash
uv run pytest -q \
  tests/unit/test_arena_tools.py \
  tests/unit/test_arena_research.py \
  tests/integration/test_arena_execution.py
uv run ruff check src/mathloop/arena tests/unit/test_arena_tools.py
uv run mypy
```

Run a decoy process outside the repository and prove arena cleanup leaves it
alive while terminating an arena descendant.

- [ ] **Step 8: Commit**

```bash
git add \
  src/mathloop/arena/tools.py \
  src/mathloop/arena/research.py \
  src/mathloop/arena/execution.py \
  src/mathloop/processes.py \
  tests/unit/test_arena_tools.py \
  tests/unit/test_arena_research.py \
  tests/integration/test_arena_execution.py
git commit -m "feat: add bounded local arena tools"
```

---

### Task 6: Independent arena verification

**Files:**
- Create: `src/mathloop/arena/verification.py`
- Test: `tests/unit/test_arena_verification.py`
- Test: `tests/integration/test_arena_lean.py`

**Interfaces:**
- Consumes: staged claims, tool receipts, and content-addressed artifacts.
- Produces: `VerificationRequest`, `VerificationReceipt`.
- Produces: `ArenaVerifier.verify(request: VerificationRequest) -> VerificationReceipt`.
- Guarantees: no positive turn classification without an accepted independent receipt.

- [ ] **Step 1: Write positive and negative control tests**

Positive Lean control:

```lean
import Mathlib
example : ∀ x : ZMod 6, x ^ 3 = x := by decide
```

Negative Lean control:

```lean
import Mathlib
example : ∀ x : ZMod 6, x ^ 2 = x := by decide
```

Assert the first receipt is accepted and the second is rejected with bounded
compiler evidence. Add tests showing that a model-authored `"verified": true`
field and a successful Python search without an explicit range cannot create
an accepted receipt.

- [ ] **Step 2: Run tests and capture RED**

```bash
uv run pytest -q \
  tests/unit/test_arena_verification.py \
  tests/integration/test_arena_lean.py
```

- [ ] **Step 3: Implement verifier contracts**

```python
@dataclass(frozen=True)
class VerificationReceipt:
    id: str
    verifier: str
    verifier_version: str
    request_sha256: str
    evidence_sha256: str
    accepted: bool
    independent: bool
    details: dict[str, object]
```

Support:

- Lean compilation in a temporary copy of `.timeloop/lean/arena`;
- exact recomputation of finite witnesses through a separately selected
  implementation;
- explicit bounded-search receipts that preserve the searched range but never
  claim universal truth.

Require verifier implementation provenance and hash every request/evidence
payload.

- [ ] **Step 4: Add same-implementation rejection tests**

If a generating tool and verifier name the same implementation identity, the
receipt must have `independent=False` and cannot support a positive
classification. Verify the arena record validator rejects it.

- [ ] **Step 5: Run tests**

```bash
uv run pytest -q \
  tests/unit/test_arena_verification.py \
  tests/integration/test_arena_lean.py \
  tests/unit/test_verification.py
```

- [ ] **Step 6: Commit**

```bash
git add \
  src/mathloop/arena/verification.py \
  tests/unit/test_arena_verification.py \
  tests/integration/test_arena_lean.py
git commit -m "feat: independently verify arena claims"
```

---

### Task 7: Bounded local arena runner and durable materialization

**Files:**
- Create: `src/mathloop/arena/runner.py`
- Test: `tests/unit/test_arena_runner.py`
- Test: `tests/integration/test_local_arena.py`

**Interfaces:**
- Consumes: `ToolCallingModelProvider`, `ArenaStateStore`, `ArenaSelector`, `ArenaToolRegistry`, and `ArenaVerifier`.
- Produces: `LocalArenaRunner.run_batch(turns: int, seed: int) -> ArenaBatchReport`.
- Produces: `LocalArenaRunner.run_turn(selection: ArenaSelection, seed: int) -> ArenaTurnRecord`.
- Produces: `ArenaBatchReport.metrics: ArenaEvaluationMetrics`, computed only from host records and verifier receipts.
- Produces: frozen Pydantic `ArenaBatchReport` with `batch_id`, `requested_turns`, `completed_turns`, `failed_turns`, `record_ids`, `metrics`, `started_at`, and `completed_at`.

- [ ] **Step 1: Write bounded tool-loop tests**

Use a scripted provider sequence:

1. request `read_arena_file`;
2. request `run_python`;
3. return a strict final turn record.

Assert ordered messages, stable invocation IDs, maximum step enforcement,
token accounting, one active provider call, and exact tool receipts.

Add cases for refusal, malformed call, undeclared tool, repeated call replay,
provider timeout before a tool, provider failure after a tool, turn timeout,
stale lease, invalid final record, and interrupted batch.

Assert every configured host limit independently: the thirteenth model action,
4,097th output token, thirteenth tool call, seventh subprocess, 121st
subprocess second, byte after 16 MiB of artifacts, seventh research query,
third pre-side-effect transport retry, third structured repair, and byte after
2 MiB of assembled context each ends the turn with its exact limit
classification and a durable failure event.

- [ ] **Step 2: Write canonical materialization tests**

```python
def test_invalid_turn_never_changes_canonical_arena_files(arena_fixture) -> None:
    before = arena_fixture.canonical_hashes()
    report = arena_fixture.runner(script="invalid-positive-without-receipt").run_batch(1, 4)
    assert report.invalid == 1
    assert arena_fixture.canonical_hashes() == before
    assert arena_fixture.raw_failure_event_exists()
```

Add a valid negative-result case that appends the turn summary and ledger
entry, and a verified positive case that updates the notebook only after the
receipt exists. Never delete prior notebook content.

- [ ] **Step 3: Run tests and capture RED**

```bash
uv run pytest -q \
  tests/unit/test_arena_runner.py \
  tests/integration/test_local_arena.py
```

- [ ] **Step 4: Implement one-action-at-a-time orchestration**

Use this fixed state machine:

```text
ORIENTED -> MODEL_PENDING -> TOOL_PENDING -> MODEL_PENDING
ORIENTED/MODEL_PENDING -> FINAL_PENDING -> VERIFYING -> MATERIALIZING -> COMPLETE
any non-terminal state -> FAILED
```

Persist a lease before the first provider call. Persist every model/tool event
before advancing. Limit steps, tokens, tool calls, artifact bytes, and time.
Serialize model generation with a process-safe concurrency gate of one.
Retry a transport failure at most twice and only while no tool side effect has
a receipt. After the first side effect, do not replay the provider request:
record the failure and end or resume from durable state. Treat partial output
as non-final, expire each stale lease exactly once on startup, and record that
transition without inventing model or verifier evidence.

- [ ] **Step 5: Implement host-owned finalization**

The model returns a Pydantic `ProposedArenaTurn`; the host derives:

- model/runtime identity;
- prompt/tool digests;
- receipts;
- token/time/cost fields;
- final status;
- allowed canonical updates.

The model cannot supply or override those fields. Positive statuses require
accepted independent receipts. Materialization uses the snapshot digest from
selection and fails on concurrent canonical changes.
Contradictory validated evidence appends a correction with the superseded
record IDs and verifier provenance; it never overwrites or deletes an earlier
claim.

- [ ] **Step 6: Prove both populations change without collapsing**

Run 100 scripted turns with mixed outcomes. Assert:

- new problems can enter from `pool.jsonl`;
- a unique proposed method becomes `trial`;
- verified outcomes affect later exploitation;
- invalid/redundant outcomes reduce selection;
- retired methods disappear from exploitation;
- the exploration count for both populations remains at least 15;
- held-out outcomes never affect online scores.

Compute `ArenaEvaluationMetrics` from immutable turn records with these exact
fields:

```python
@dataclass(frozen=True)
class ArenaEvaluationMetrics:
    attempted_turns: int
    valid_turns: int
    repaired_model_actions: int
    total_model_actions: int
    verified_leads: int
    rejected_positive_claims: int
    distinct_problem_ids: frozenset[str]
    distinct_frame_ids: frozenset[str]
    resumed_turns: int
    cold_start_turns: int
    reused_negative_results: int
    wall_seconds: float
    input_tokens: int
    output_tokens: int
    held_out_attempts: int
    held_out_verified_leads: int
```

Expose derived rates with zero-denominator behavior defined as `Decimal("0")`.
Test valid structured-turn rate, repair rate, verified-lead rate,
false-positive rate, negative-result reuse, tokens/wall-time per verified
outcome, distinct problem/frame coverage, resume rate, and held-out performance.
The held-out aggregation may read verifier outcomes but must not write selector
scores.

- [ ] **Step 7: Run focused and arena verification**

```bash
uv run pytest -q \
  tests/unit/test_arena_runner.py \
  tests/integration/test_local_arena.py \
  tests/unit/test_arena_selection.py \
  tests/integration/test_arena_lean.py
.timeloop/bin/lint
```

- [ ] **Step 8: Commit**

```bash
git add \
  src/mathloop/arena/runner.py \
  tests/unit/test_arena_runner.py \
  tests/integration/test_local_arena.py
git commit -m "feat: run bounded local arena turns"
```

---

### Task 8: Local CLI and production mathloop method

**Files:**
- Modify: `src/mathloop/methods/proof_sketch.py`
- Create: `src/mathloop/methods/local_proof.py`
- Modify: `src/mathloop/provenance.py`
- Modify: `src/mathloop/runtime.py`
- Modify: `src/mathloop/cli.py`
- Test: `tests/unit/test_local_proof_method.py`
- Test: `tests/unit/test_cli.py`
- Test: `tests/integration/test_local_runtime.py`
- Test: `tests/integration/test_worker_billing.py`

**Interfaces:**
- Consumes: `LMStudioLifecycle`, `LocalModelProvider`, and `LocalArenaRunner`.
- Produces: `LocalProofStrategy.family == "local_proof_sketch"`.
- Produces CLI: `local init`, `local status`, `local arena`, `local run`.
- Produces CLI helpers: `_local_init(settings: Settings) -> LocalInitReport`, `_local_status(settings: Settings) -> LocalStatusReport`, `_local_arena(settings: Settings, turns: int, seed: int) -> ArenaBatchReport`, and `_local_run(settings: Settings, cycles: int, workers: int) -> LocalRunReport`.
- Produces frozen Pydantic `LocalInitReport`, `LocalStatusReport`, and `LocalRunReport` models; consumes the frozen Pydantic `ArenaBatchReport` from Task 7 so every command emits stable JSON with `.model_dump_json()`.

- [ ] **Step 1: Write local proof-method tests**

Assert the method:

- sends only the normalized problem statement;
- treats problem text as untrusted;
- constructs `ModelCostAuthorization(Decimal("0.000000"))`;
- returns `status="lead"` with no claim or witness;
- includes local runtime identity and zero-dollar receipts;
- marks external execution before the provider call;
- rejects a non-local receipt;
- uses family `local_proof_sketch`.

- [ ] **Step 2: Write runtime mutual-exclusion and accounting tests**

Construct runtimes for all four modes. Assert only local mode registers
`local_proof_sketch`; no mode registers two external families. Schedule and
execute one local proof lead, then assert:

```python
assert experiment.cost_usd == Decimal("0.000000")
assert artifact["billing_receipt"]["provider"] == "local-lmstudio"
assert artifact["billing_receipt"]["actual_cost_usd"] == "0.000000"
assert repository.daily_spend(day) == Decimal("0.000000")
```

Patch OpenAI and Codex construction to raise if touched.

- [ ] **Step 3: Write CLI tests**

`mathloop local --help` must list:

```text
init
status
arena
run
```

Test:

- `local init` invokes lifecycle readiness and a no-write structured/tool
  canary;
- `local status` is read-only;
- bare `local arena` uses `turns=20` and `seed=1`;
- `local arena --turns 0` is rejected;
- `local arena --turns 2 --seed 7` reports two durable results;
- bare `local run` uses `cycles=5` and `workers=1`;
- `local run --cycles 2 --workers 1` builds only local mode;
- no local command accepts `--continuous`, `--api-enabled`, or paid fallback.

- [ ] **Step 4: Run tests and capture RED**

```bash
uv run pytest -q \
  tests/unit/test_local_proof_method.py \
  tests/unit/test_cli.py \
  tests/integration/test_local_runtime.py \
  tests/integration/test_worker_billing.py
```

- [ ] **Step 5: Implement local proof provenance**

Add local files to `_METHOD_FILES` or a parameterized provenance function that
incorporates:

- local runtime identity digest;
- model key and path;
- quantization;
- context length;
- provider and method implementation hashes;
- lockfile identity.

`require_current_method_provenance` must reject scheduled work from a prior
model/runtime identity.

- [ ] **Step 6: Register deferred local execution**

Mirror the safe deferred-client pattern:

```python
@dataclass
class DeferredLocalProofMethod:
    settings: Settings
    identity: LocalRuntimeIdentity
    family: str = "local_proof_sketch"

    def run(self, context: MethodContext) -> MethodResult:
        provider = build_local_provider(self.settings, self.identity)
        return LocalProofStrategy(self.settings, provider, self.identity).run(context)
```

Do not retain a live HTTP client across fork boundaries. Pass external mode
through `_worker_process_main`, and serialize local model access across worker
processes with one interprocess gate.

- [ ] **Step 7: Implement CLI commands**

Create a `local_app = typer.Typer(...)` and register it under `local`.

Use these exact command signatures:

```python
@local_app.command("init")
def local_init() -> None:
    typer.echo(_local_init(Settings()).model_dump_json())


@local_app.command("status")
def local_status() -> None:
    typer.echo(_local_status(Settings()).model_dump_json())


@local_app.command("arena")
def local_arena(
    turns: Annotated[int, typer.Option(min=1)] = 20,
    seed: int = 1,
) -> None:
    typer.echo(_local_arena(Settings(), turns, seed).model_dump_json())


@local_app.command("run")
def local_run(
    cycles: Annotated[int, typer.Option(min=1)] = 5,
    workers: Annotated[int, typer.Option(min=1)] = 1,
) -> None:
    typer.echo(_local_run(Settings(), cycles, workers).model_dump_json())
```

- `init`: lifecycle readiness, strict structured canary, one declared no-op
  tool call, exact zero receipt, no arena write.
- `status`: lifecycle status plus counts from `.timeloop/local/turns.jsonl`;
  never starts or loads.
- `arena`: readiness, then bounded `LocalArenaRunner.run_batch`.
- `run`: readiness, then production cycles under `ExternalCognitionMode.LOCAL`.

- [ ] **Step 8: Run local, compatibility, and full offline tests**

```bash
uv run pytest -q \
  tests/unit/test_local_proof_method.py \
  tests/unit/test_cli.py \
  tests/integration/test_local_runtime.py \
  tests/integration/test_worker_billing.py \
  tests/integration/test_runtime_loop.py \
  tests/integration/test_codex_runtime.py \
  tests/unit/test_openai_provider.py
uv run pytest -q
uv run ruff check .
uv run mypy
```

- [ ] **Step 9: Commit**

```bash
git add \
  src/mathloop/methods/proof_sketch.py \
  src/mathloop/methods/local_proof.py \
  src/mathloop/provenance.py \
  src/mathloop/runtime.py \
  src/mathloop/cli.py \
  tests/unit/test_local_proof_method.py \
  tests/unit/test_cli.py \
  tests/integration/test_local_runtime.py \
  tests/integration/test_worker_billing.py
git commit -m "feat: expose local arena and runtime commands"
```

---

### Task 9: Documentation, live Qwen3.6 release canary, and controlled batch

**Files:**
- Modify: `.timeloop/README.md`
- Modify: `.timeloop/ARENA.md`
- Modify: `pyproject.toml`
- Create: `docs/verification/local-model-acceptance.md`
- Create: `tests/e2e/test_local_model_canary.py`

**Interfaces:**
- Consumes: completed local CLI and installed Qwen3.6 35B A3B.
- Produces: exact acceptance evidence and first controlled batch report.

- [ ] **Step 1: Add an explicitly marked live-local canary**

Register a `live_local_model` pytest marker. The test must skip with an exact
reason when `lms ls --json` has no unique Qwen3.6 match. When available it:

1. fingerprints `.timeloop` canonical files and the real production database;
2. runs lifecycle readiness;
3. asserts the exact resolved model identity;
4. checks strict structured output;
5. executes one read-only tool call in an isolated arena fixture;
6. rejects `∀ x : ZMod 6, x^2 = x`;
7. accepts `∀ x : ZMod 6, x^3 = x`;
8. asserts all receipts cost zero;
9. asserts no paid-provider event or credential exposure;
10. asserts only the isolated fixture changed.

- [ ] **Step 2: Write operator documentation**

Document:

```bash
uv run mathloop local init
uv run mathloop local status
uv run mathloop local arena --turns 5 --seed 1
uv run mathloop local run --cycles 2 --workers 1
```

Include startup behavior, model TTL, no-download rule, local-only guarantee,
tracked versus ignored arena files, how to inspect receipts, how to resume,
how to interrupt safely, and how to diagnose absent/ambiguous models.

- [ ] **Step 3: Run the complete offline release matrix**

```bash
uv run pytest -q
uv run ruff check .
uv run mypy
.timeloop/bin/lint
.timeloop/bin/exam
git diff --check
```

Record literal counts and commands in
`docs/verification/local-model-acceptance.md`.

- [ ] **Step 4: Wait for installed-model visibility without downloading**

Run:

```bash
lms ls --json
```

If no unique Qwen3.6 35B A3B match exists, stop with code-complete but
release-blocked status. Do not run `lms get`, change the model selector, or
substitute Qwen3.5.

- [ ] **Step 5: Run the live release canary**

```bash
uv run pytest -q -m live_local_model tests/e2e/test_local_model_canary.py -vv
```

Expected: one passing live canary, exact model identity recorded, no canonical
arena or real database mutation.

- [ ] **Step 6: Run one controlled canonical arena batch**

Before the batch, require a clean worktree except the preserved
`.timeloop/exam/results.jsonl` modification. Run:

```bash
uv run mathloop local arena --turns 3 --seed 1
```

Review all three raw receipts, tool calls, verification outcomes, and proposed
canonical updates. Run `.timeloop/bin/lint`. Do not claim mathematical novelty
or publish anything. Commit only validated durable summaries and method
population changes; leave raw artifacts under ignored `.mathloop/`.

- [ ] **Step 7: Run post-batch verification**

```bash
uv run pytest -q
uv run ruff check .
uv run mypy
.timeloop/bin/lint
git diff --check
git status --short
```

Confirm the pre-existing exam result is preserved byte-for-byte except for
changes already present before implementation.

- [ ] **Step 8: Commit documentation and canary**

```bash
git add \
  .timeloop/README.md \
  .timeloop/ARENA.md \
  docs/verification/local-model-acceptance.md \
  tests/e2e/test_local_model_canary.py \
  pyproject.toml
git commit -m "docs: verify local Qwen arena"
```

Stage controlled-batch durable arena changes in a separate commit after human
review:

```bash
git add .timeloop/local/turns.jsonl .timeloop/methods.jsonl .timeloop/ledger.md
git add .timeloop/notebook
git commit -m "experiment: record initial local arena batch"
```

Do not stage `.timeloop/exam/results.jsonl`.

---

## Final release verification

After all tasks and commits:

```bash
uv run pytest -q
uv run ruff check .
uv run mypy
.timeloop/bin/lint
.timeloop/bin/exam
uv run pytest -q -m live_local_model tests/e2e/test_local_model_canary.py -vv
git diff --check
git status --short
```

Release authorization requires:

- zero offline failures;
- one passing real Qwen3.6 canary;
- no paid provider construction or receipt in local mode;
- exact zero-dollar local settlements;
- exact installed model provenance;
- no download path;
- no non-loopback inference path;
- no canonical mutation from invalid or rejected turns;
- nonzero problem and method/frame exploration;
- independent positive verification;
- a clean worktree except the preserved user-owned exam result if it remains
  intentionally uncommitted.
