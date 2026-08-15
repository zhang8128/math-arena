# Continuous Ollama Researcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One command (`bin/research`) launches a continuous, locally-hosted recursive researcher that runs `.timeloop` room turns on Ollama `qwen3.8:27b-mlx` until stopped, with live probing from other sessions and no paid inference anywhere.

**Architecture:** An Ollama lifecycle controller resolves and preloads one already-installed model over the loopback native API. One `LocalModelProvider` implements strict structured generation and provider-neutral tool calling through the OpenAI-compatible `/v1` endpoint. A `ContinuousArenaRunner` wraps the bounded per-turn core with lease/heartbeat, signal handling, a circuit breaker, cumulative ceilings, rotation-capped diverse selection, and scheduled literature patrols. Host-owned tools, durable append-only records, zero-dollar receipts, and independent verification carry over unchanged in spirit from the superseded LM Studio plan.

**Tech Stack:** Python 3.13, Pydantic 2, OpenAI Python SDK 2.47 against loopback Ollama, stdlib `urllib` for native-API lifecycle probes, PostgreSQL (production path only), Typer, pytest, Lean 4/mathlib, Docker (SearXNG), bash + `caffeinate`.

**Spec:** `docs/superpowers/specs/2026-08-15-continuous-ollama-researcher-design.md` (supersedes `2026-07-30-local-model-arena-design.md`; read both — the older spec holds shared rationale).

## Global Constraints

- Never stage, revert, or rewrite pre-existing uncommitted changes. At plan time these include `.timeloop/exam/results.jsonl`, `.timeloop/ledger.md`, `.timeloop/pool.jsonl`, everything under `publication/`, `.DS_Store` files, and `.timeloop/notebook/frame-collision-lychrel.md` / `riemann-frames.md`. Commit only the files your task names.
- Default runtime is Ollama at `http://127.0.0.1:11434`. The logical model selector is `qwen3.8:27b-mlx`; startup must resolve exactly one already-installed model — nearby families, parameter counts, or quantizations never satisfy it.
- Context length is 65,536 tokens, generation concurrency is one, turn timeout is 1,800 seconds, model `keep_alive` is 900 seconds.
- Per turn: at most 12 model actions, 4,096 output tokens per action, 12 tool invocations, 6 subprocesses, 120 seconds per subprocess, 16 MiB of artifacts, 6 research queries, two pre-side-effect transport retries, two structured-output repairs, 2 MiB of assembled prompt/tool-result bytes.
- Continuous run: circuit breaker at 5 consecutive failed turns; rotation cap 3 consecutive turns per target; literature patrol every 25th turn; heartbeat every 60 s; a lease is stale after 600 s without heartbeat; cumulative artifact disk cap 2 GiB per run.
- The implementation may call `GET /api/version`, `GET /api/tags`, `GET /api/ps`, `POST /api/generate` (preload only), `GET /v1/models`, and may spawn `ollama serve`. It must not contain or construct `ollama pull`, `POST /api/pull`, or any other download request.
- External cognition mode is exactly one of `none`, `local`, `openai`, or `codex`. Local mode rejects non-loopback inference URLs, registers no paid provider, has no paid fallback, and scrubs paid-provider credentials from every child process.
- Research tools use only public unauthenticated endpoints (OEIS, arXiv, Crossref, Wikipedia) or a loopback SearXNG instance. Backends receive only explicit query strings or public identifiers.
- Model output is never verification, promotion, publication, or grading authority.
- The real `qwen3.8:27b-mlx` canary, a human-reviewed controlled batch, and a supervised 2-hour soak are release gates, in that order, before any unattended run.
- Use TDD for every behavior change; run `uv run pytest -q`, `uv run ruff check .`, and `uv run mypy` before each commit; commit after each task.
- No new Python dependencies without proof the pinned set is insufficient; lifecycle HTTP uses stdlib `urllib.request` against loopback only.

---

## File Structure

New units:

- `src/mathloop/local/__init__.py`, `src/mathloop/local/security.py` — loopback validation, credential scrubbing.
- `src/mathloop/local/domain.py` — immutable local runtime records.
- `src/mathloop/local/ollama.py` — Ollama server probe/spawn, installed-model resolution, preload, health.
- `src/mathloop/providers/local.py` — structured + tool-calling adapter over `/v1`.
- `src/mathloop/arena/{__init__,domain,storage,selection,tools,research,execution,verification,runner,continuous}.py` — arena core plus continuous supervisor.
- `src/mathloop/methods/local_proof.py` — production local method.
- `bin/research` — operator entry point (bash).
- `docker/searxng/settings.yml`, `compose.yaml` service — local web search.
- `.timeloop/methods.jsonl`, `.timeloop/local/turns.jsonl` — tracked durable populations/events.
- `tests/unit/…`, `tests/integration/…`, `tests/e2e/test_local_model_canary.py`, `tests/helpers/continuous_child.py`.

Modified: `src/mathloop/config.py`, `src/mathloop/runtime.py`, `src/mathloop/cli.py`, `src/mathloop/providers/base.py`, `src/mathloop/providers/__init__.py`, `src/mathloop/processes.py`, `src/mathloop/methods/proof_sketch.py`, `src/mathloop/provenance.py`, `compose.yaml`, `.gitignore`, `.timeloop/README.md`, `.timeloop/ARENA.md`.

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
- Produces: `ExternalCognitionMode(StrEnum)` with values `none|local|openai|codex`.
- Produces: `require_loopback_http_url(value: str) -> str`.
- Produces: `scrub_paid_credentials(environment: Mapping[str, str]) -> dict[str, str]`.
- Produces: `build_runtime(..., external_mode: ExternalCognitionMode | None = None, ...) -> Runtime` — translate legacy `api_enabled`/`codex_enabled` once at the composition boundary; internal registration logic uses only the mode.

- [ ] **Step 1: Write failing settings and security tests**

```python
def test_local_defaults_are_exact() -> None:
    settings = Settings(_env_file=None)
    assert settings.external_cognition_mode == ExternalCognitionMode.NONE
    assert settings.local_model_selector == "qwen3.8:27b-mlx"
    assert settings.local_api_base_url == "http://127.0.0.1:11434"
    assert settings.local_ollama_executable == Path("ollama")
    assert settings.local_context_length == 65_536
    assert settings.local_model_concurrency == 1
    assert settings.local_turn_timeout_seconds == 1_800
    assert settings.local_model_keep_alive_seconds == 900
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
    assert settings.local_breaker_consecutive_failures == 5
    assert settings.local_rotation_cap == 3
    assert settings.local_patrol_interval == 25
    assert settings.local_heartbeat_seconds == 60
    assert settings.local_stale_lease_seconds == 600
    assert settings.local_max_run_artifact_bytes == 2 * 1024 * 1024 * 1024
    assert settings.local_searxng_url == "http://127.0.0.1:8888"


@pytest.mark.parametrize(
    "url",
    [
        "https://api.openai.com/v1",
        "http://192.168.1.4:11434",
        "http://example.test:11434",
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

```bash
uv run pytest -q tests/unit/test_config.py tests/unit/test_local_security.py \
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
    local_ollama_executable: Path = Path("ollama")
    local_model_selector: str = "qwen3.8:27b-mlx"
    local_api_base_url: str = "http://127.0.0.1:11434"
    local_context_length: int = Field(default=65_536, ge=4_096, le=262_144)
    local_model_concurrency: int = Field(default=1, ge=1, le=1)
    local_turn_timeout_seconds: int = Field(default=1_800, ge=60, le=7_200)
    local_model_keep_alive_seconds: int = Field(default=900, ge=60, le=86_400)
    local_max_model_actions: int = Field(default=12, ge=1, le=64)
    local_max_output_tokens_per_action: int = Field(default=4_096, ge=128, le=32_768)
    local_max_tool_invocations: int = Field(default=12, ge=0, le=64)
    local_max_subprocesses: int = Field(default=6, ge=0, le=32)
    local_max_subprocess_seconds: int = Field(default=120, ge=1, le=600)
    local_max_artifact_bytes: int = Field(default=16 * 1024 * 1024, ge=1_024, le=256 * 1024 * 1024)
    local_max_research_queries: int = Field(default=6, ge=0, le=32)
    local_max_pre_side_effect_retries: int = Field(default=2, ge=0, le=4)
    local_max_repair_attempts: int = Field(default=2, ge=0, le=4)
    local_max_context_bytes: int = Field(default=2 * 1024 * 1024, ge=65_536, le=16 * 1024 * 1024)
    local_breaker_consecutive_failures: int = Field(default=5, ge=1, le=100)
    local_rotation_cap: int = Field(default=3, ge=1, le=20)
    local_patrol_interval: int = Field(default=25, ge=2, le=1_000)
    local_heartbeat_seconds: int = Field(default=60, ge=5, le=600)
    local_stale_lease_seconds: int = Field(default=600, ge=60, le=7_200)
    local_max_run_artifact_bytes: int = Field(
        default=2 * 1024 * 1024 * 1024, ge=16 * 1024 * 1024, le=64 * 1024 * 1024 * 1024
    )
    local_searxng_url: str = "http://127.0.0.1:8888"
```

Add `src/mathloop/local/security.py`:

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
    return {k: v for k, v in environment.items() if k not in PAID_CREDENTIAL_KEYS}
```

Make `Runtime` carry one `external_mode`; registration rejects any paid/local method already present when another mode is requested. Map `--api-enabled` to `OPENAI` and Codex commands to `CODEX`; reject conflicting legacy flags before constructing a runtime. Validate `local_api_base_url` and `local_searxng_url` with `require_loopback_http_url` in a Settings model validator when `external_cognition_mode == LOCAL`.

- [ ] **Step 4: Add direct-construction and both-registration-order tests**

Test all pairs of non-`NONE` modes; construct `Runtime` directly and via `build_runtime`; both must reject mixed registration. Assert local mode does not inspect `OPENAI_API_KEY` and cannot register `proof_sketch` or `codex_proof_strategy`.

- [ ] **Step 5: Run focused and compatibility suites**

```bash
uv run pytest -q tests/unit/test_config.py tests/unit/test_local_security.py \
  tests/unit/test_cli.py tests/integration/test_runtime_loop.py
uv run ruff check src/mathloop tests
uv run mypy
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/mathloop/local/__init__.py src/mathloop/local/security.py \
  src/mathloop/config.py src/mathloop/runtime.py src/mathloop/cli.py \
  tests/unit/test_config.py tests/unit/test_local_security.py \
  tests/unit/test_cli.py tests/integration/test_runtime_loop.py
git commit -m "feat: enforce local-only cognition mode"
```

---

### Task 2: Ollama lifecycle and exact installed-model resolution

**Files:**
- Create: `src/mathloop/local/domain.py`
- Create: `src/mathloop/local/ollama.py`
- Test: `tests/unit/test_ollama_lifecycle.py`

**Interfaces:**
- Consumes: validated local settings and `scrub_paid_credentials`.
- Produces: `InstalledLocalModel`, `LocalRuntimeIdentity`, `OllamaStatus`, `LocalCapabilityUnavailableError`.
- Produces: `OllamaLifecycle.status() -> OllamaStatus` (read-only), `OllamaLifecycle.ensure_ready() -> LocalRuntimeIdentity`.
- Produces: `HttpProbe` protocol — `get_json(path: str, *, timeout: float) -> object` and `post_json(path: str, body: dict[str, object], *, timeout: float) -> object` against the validated loopback base URL (real implementation on stdlib `urllib.request`).
- Produces: `ProcessSpawner` protocol — `spawn_detached(argv: tuple[str, ...], env: Mapping[str, str]) -> int` used only for `ollama serve`.

- [ ] **Step 1: Write model-resolution and forbidden-download tests**

```python
def test_resolve_model_requires_one_exact_match() -> None:
    models = (
        InstalledLocalModel(
            name="qwen3.8:27b-mlx",
            digest="5642e97495e1",
            size_bytes=18_000_000_000,
            family="qwen3_5",
            format="mlx",
            quantization="nvfp4",
        ),
    )
    assert resolve_installed_model(models, "qwen3.8:27b-mlx") == models[0]


@pytest.mark.parametrize(
    "name",
    ["qwen3.6:27b-mlx", "qwen3.8:27b", "qwen3.8-27b-heretic", "muse-glimmer:30b-mlx"],
)
def test_nearby_models_never_satisfy_the_selector(name: str) -> None:
    models = (installed_model_fixture(name=name),)
    with pytest.raises(LocalCapabilityUnavailableError, match="not installed"):
        resolve_installed_model(models, "qwen3.8:27b-mlx")


def test_lifecycle_never_constructs_download_request() -> None:
    probe = RecordingProbe(version_ok=True, tags=[])
    lifecycle = lifecycle_with(probe)
    with pytest.raises(LocalCapabilityUnavailableError, match="not installed"):
        lifecycle.ensure_ready()
    assert all("pull" not in path for path in probe.paths)
```

Add cases for: server unreachable then spawned once and converging; server unreachable and spawn failing (bounded error, no retry storm); malformed `/api/tags` JSON; duplicate-name listings (ambiguous → error); preload timeout; `/api/ps` missing the model after preload; identity changing between listing and health (error). Fixture `installed_model_fixture` builds an `InstalledLocalModel` with overridable fields.

- [ ] **Step 2: Run tests and capture RED**

```bash
uv run pytest -q tests/unit/test_ollama_lifecycle.py
```

Expected: import failure for `mathloop.local.ollama`.

- [ ] **Step 3: Implement immutable lifecycle domain records**

In `src/mathloop/local/domain.py`:

```python
@dataclass(frozen=True)
class InstalledLocalModel:
    name: str
    digest: str
    size_bytes: int
    family: str
    format: str
    quantization: str | None


@dataclass(frozen=True)
class LocalRuntimeIdentity:
    runtime: str            # "ollama"
    runtime_version: str    # from /api/version
    endpoint: str
    model_name: str
    model_digest: str
    model_format: str
    quantization: str | None
    context_length: int
    keep_alive_seconds: int
    identity_sha256: str


class LocalCapabilityUnavailableError(RuntimeError):
    pass
```

Canonicalize identity as sorted compact JSON and SHA-256 it. Validate strings, sizes, URLs, and context lengths at construction.

- [ ] **Step 4: Implement lifecycle flow**

`ensure_ready()` performs, in order:

1. `GET /api/version`; on connection failure, `spawn_detached((str(ollama_executable), "serve"), scrubbed_env)` once, then poll `GET /api/version` with a bounded deadline (30 s, 0.5 s interval);
2. `GET /api/tags`; parse `models[*].name`, `digest`, `size`, `details.family`, `details.format`, `details.quantization_level`; resolve the exact selector;
3. preload: `POST /api/generate` with body `{"model": "qwen3.8:27b-mlx", "prompt": "", "keep_alive": 900, "options": {"num_ctx": 65536}}`;
4. `GET /api/ps` must list the model; `GET /v1/models` must include it;
5. return the immutable identity. Repeated `ensure_ready()` returns an equal identity and re-issues no spawn.

The lifecycle never stops the server (whether or not it started it), and no code path constructs `pull`. `status()` performs steps 1–2 read-only (no spawn, no preload) and reports server reachability, resolved model or absence, and `/api/ps` contents.

- [ ] **Step 5: Test idempotency and ownership boundaries**

Cover: already-running server performs no spawn; repeated `ensure_ready()` idempotent; a server appearing between probe and spawn converges (spawn failure tolerated if version probe then succeeds); spawn environment has paid credentials removed; static probe of production source:

```bash
! rg -n '"/api/pull"|ollama.*pull|pull.*model' src/mathloop/local
```

- [ ] **Step 6: Run tests and static checks**

```bash
uv run pytest -q tests/unit/test_ollama_lifecycle.py
uv run ruff check src/mathloop/local tests/unit/test_ollama_lifecycle.py
uv run mypy
```

- [ ] **Step 7: Commit**

```bash
git add src/mathloop/local/domain.py src/mathloop/local/ollama.py \
  tests/unit/test_ollama_lifecycle.py
git commit -m "feat: manage installed Ollama models"
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
- Consumes: `LocalRuntimeIdentity`, existing `ModelRequest[T]`, existing billing records.
- Produces: `LocalToolDefinition`, `LocalToolCall`, `LocalAgentRequest`, `LocalAgentResponse`, `ToolCallingModelProvider` protocol.
- Produces: `LocalModelProvider.generate(request, schema) -> ModelResponse` and `LocalModelProvider.next_action(request: LocalAgentRequest) -> LocalAgentResponse`.
- Provider identity strings: provider `"local-ollama"`, pricing version `"local-compute-v1"`, pricing source `"local://ollama/unmetered"`.

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
    request = model_request(cost_authorization=ModelCostAuthorization(Decimal("0.000000")))
    response = provider.generate(request, ProofSketch)
    assert response.value.strategy == "Reduce to residues."
    assert response.billing_authorization.provider == "local-ollama"
    assert response.billing_authorization.reserved_cost_usd == Decimal("0.000000")
    assert response.billing_receipt.actual_cost_usd == Decimal("0.000000")
    assert response.usage.input_tokens == 120
    assert response.usage.output_tokens == 45
```

Add rejection cases for missing usage, negative counts, wrong parsed schema, refusal, incomplete output, output over cap, mismatched model, non-loopback client, absent response ID, and elapsed deadline. Add a compatibility test that `ModelCostAuthorization(Decimal("0.000000"))` is valid provider-neutral input while `OpenAIProvider.generate` rejects that cap as insufficient before issuing a paid request.

- [ ] **Step 2: Write typed tool-call and think-flag tests**

```python
def test_next_action_returns_only_declared_tool_calls() -> None:
    provider = provider_with_tool_calls([
        {"id": "call_1", "name": "run_python", "arguments": {"program": "print(2+2)"}}
    ])
    response = provider.next_action(agent_request(tools=(python_tool(),)))
    assert response.tool_calls == (
        LocalToolCall(id="call_1", name="run_python", arguments={"program": "print(2+2)"}),
    )
    assert response.content is None


def test_think_flag_is_transmitted_and_observed_reasoning_is_recorded() -> None:
    client = RecordingCompatClient(reasoning_content="chain")
    provider = provider_with_client(client, think=True)
    response = provider.next_action(agent_request(tools=()))
    assert client.last_extra_body == {"think": True}
    assert response.thinking_requested is True
    assert response.reasoning_observed is True
```

Reject duplicate call IDs, undeclared tool names, invalid JSON arguments, content mixed with tool calls, excessive call counts, and payloads above the configured bound.

- [ ] **Step 3: Run focused tests and capture RED**

```bash
uv run pytest -q tests/unit/test_local_provider.py tests/unit/test_billing.py
```

- [ ] **Step 4: Add provider-neutral tool contracts**

Add frozen records to `providers/base.py` (no Ollama names in these types):

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
    think: bool = True


@dataclass(frozen=True)
class LocalAgentResponse:
    response_id: str
    content: str | None
    tool_calls: tuple[LocalToolCall, ...]
    usage: ModelUsage
    billing_authorization: BillingAuthorization
    billing_receipt: BillingReceipt
    thinking_requested: bool
    reasoning_observed: bool


class ToolCallingModelProvider(Protocol):
    def next_action(self, request: LocalAgentRequest) -> LocalAgentResponse:
        raise NotImplementedError
```

Add an import-boundary test proving `providers/base.py`, `arena/`, and production methods do not import `OllamaLifecycle` or Ollama wire types; only the composition root and `providers/local.py` bind the contracts to the transport. Change `ModelCostAuthorization.__post_init__` to `validate_database_usd(..., positive=False)`; paid adapters keep their positive-cap check; `LocalModelProvider` rejects any positive request cap.

- [ ] **Step 5: Implement `LocalModelProvider`**

Inject a compatible client; the real factory uses the pinned OpenAI SDK with the validated loopback `base_url` (`http://127.0.0.1:11434/v1`) and the fixed non-secret sentinel key `"local-unmetered"`. The class must not import `OPENAI_PRICING_CATALOG` or `OpenAIProvider`.

Structured generation:

```python
completion = client.chat.completions.parse(
    model=identity.model_name,
    messages=[
        {"role": "system", "content": request.system},
        {"role": "user", "content": request.prompt},
    ],
    response_format=schema,
    max_tokens=request.max_output_tokens,
    timeout=remaining,
    extra_body={"think": think},
)
```

Tool actions use `chat.completions.create` with only the typed tool catalog and the same `extra_body`. Record `thinking_requested` from the request and `reasoning_observed` from any `reasoning`/`reasoning_content` field on the response message (absent → `False`). If the live canary (Task 9) later shows the compatibility endpoint ignores `think`, the documented contingency is one native `/api/chat` code path inside this provider only — do not build it now.

Billing after validated usage:

```python
authorization = BillingAuthorization(
    provider="local-ollama",
    model=identity.model_name,
    authorized_input_tokens=usage.input_tokens,
    max_output_tokens=request.max_output_tokens,
    reserved_cost_usd=Decimal("0.000000"),
    pricing_version="local-compute-v1",
    pricing_source="local://ollama/unmetered",
)
```

- [ ] **Step 6: Prove paid-provider isolation**

Patch `openai.OpenAI` and assert the only construction uses the exact loopback base URL and the sentinel key. Patch `OpenAIProvider` to raise if constructed during local tests. Static probe:

```bash
! rg -n 'OPENAI_PRICING|api\.openai|developers\.openai' src/mathloop/providers/local.py
```

- [ ] **Step 7: Run provider and existing suites**

```bash
uv run pytest -q tests/unit/test_local_provider.py tests/unit/test_openai_provider.py \
  tests/unit/test_billing.py tests/unit/test_proof_sketch_method.py
uv run ruff check src/mathloop/providers tests/unit/test_local_provider.py
uv run mypy
```

- [ ] **Step 8: Commit**

```bash
git add src/mathloop/providers/base.py src/mathloop/providers/local.py \
  src/mathloop/providers/__init__.py tests/unit/test_local_provider.py \
  tests/unit/test_billing.py
git commit -m "feat: add zero-cost local model provider"
```

---

### Task 4: Durable arena domain, storage, and diversity-aware selection

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
- Produces: `ArenaProblem`, `ArenaMethod`, `ArenaFrame`, `ArenaSelection`, `ArenaTurnRecord`, `ArenaTurnStatus`, `ArenaTurnKind`, `ArenaRunEvent`, `ArenaSnapshot`, `ArenaPartition`.
- Produces: `ArenaStateStore.snapshot() -> ArenaSnapshot`.
- Produces: `ArenaStateStore.append_turn(record: ArenaTurnRecord, expected_snapshot_digest: str) -> None`.
- Produces: `ArenaStateStore.append_run_event(event: ArenaRunEvent) -> None`.
- Produces: `ArenaSelector.select(snapshot: ArenaSnapshot, seed: int, turn_index: int, recent_problem_ids: tuple[str, ...], partition: ArenaPartition = ArenaPartition.LIVE) -> ArenaSelection`.

- [ ] **Step 1: Write strict domain tests**

```python
class ArenaPartition(StrEnum):
    LIVE = "live"
    HELD_OUT = "held_out"


class ArenaTurnKind(StrEnum):
    ATTACK = "attack"
    PATROL = "patrol"


class ArenaTurnStatus(StrEnum):
    NEGATIVE_RESULT = "negative_result"
    VERIFIED_LEAD = "verified_lead"
    PATROL_COMPLETED = "patrol_completed"
    INVALID_MODEL_OUTPUT = "invalid_model_output"
    TOOL_FAILURE = "tool_failure"
    TRANSPORT_FAILURE = "transport_failure"
    VERIFIER_REJECTED = "verifier_rejected"
    TIMEOUT = "timeout"
    INTERRUPTED = "interrupted"


BREAKER_FAILURE_STATUSES = frozenset({
    ArenaTurnStatus.INVALID_MODEL_OUTPUT,
    ArenaTurnStatus.TOOL_FAILURE,
    ArenaTurnStatus.TRANSPORT_FAILURE,
    ArenaTurnStatus.TIMEOUT,
})


class ArenaProblem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str
    statement: str
    state: Literal["new", "active", "parked", "settled", "superseded"]
    partition: ArenaPartition
    next_action: str | None
    novelty_checked_at: datetime | None
    content_sha256: str


class ArenaSelection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    problem: ArenaProblem
    methods: tuple[ArenaMethod, ...]
    frames: tuple[ArenaFrame, ...]
    partition: ArenaPartition
    lane: Literal["resume", "explore_problem", "explore_frame", "exploit", "held_out", "patrol"]
    kind: ArenaTurnKind
    patrol_target_ids: tuple[str, ...]
    snapshot_digest: str


class ArenaRunEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: int
    kind: Literal["schema", "run_started", "run_halted", "lease_expired"]
    run_id: UUID
    pid: int
    seed: int
    reason: str
    occurred_at: datetime
```

`ArenaMethod`, `ArenaFrame`, `ArenaSnapshot` keep the shapes from the superseded plan: methods carry `id`, `version`, `state (established|trial|retired)`, `description`, `sources`, `parent_ids`, `frame_ids`, `composition`, `content_sha256`; frames carry `id`, `state`, `description`, `parent_ids`, `content_sha256`; snapshots carry `digest`, `problems`, `methods`, `frames`, `prior_turns_sha256`, `ledger_tail_sha256`, `notebook_bundle_sha256`.

`ArenaTurnRecord` carries every field from the superseded plan's fixture (schema/event versions, batch/turn UUIDs, `turn_index`, seed, problem/method/frame ids, runtime identity, model/config/prompt/tool-catalog digests, response and receipt ids, `searched`, `hypotheses`, `ruled_out`, `structure`, `technique`, `candidate_claims`, `caveats`, `novelty_queries`, `source_metadata_digests`, `next_action`, `status`, `verification_receipt_ids`, `artifact_digests`, `proposed_durable_changes`, token/wall/cost fields) **plus**:

```python
    kind: ArenaTurnKind
    research_backends_available: tuple[str, ...]
```

Reject: blank durable fields, unknown status, unbounded collections, invalid digests, nonzero local cost, non-finite time, a positive status (`VERIFIED_LEAD`) without an independent verification receipt, `kind=PATROL` with status `VERIFIED_LEAD` or `NEGATIVE_RESULT` (patrol turns conclude `PATROL_COMPLETED` or a failure status), and `kind=ATTACK` with status `PATROL_COMPLETED`.

- [ ] **Step 2: Write append/replay/concurrency and projection tests**

Cover: exact replay; contradictory same-turn replay; two-process append; truncated final line recovery; fsync-visible append; stale snapshot rejection; artifact existence; preservation of pre-existing notebook/ledger bytes when validation fails; `append_run_event` ordering; and the projection functions later tasks rely on —

```python
def test_projection_yields_recent_problems_and_novelty_ages(tmp_store) -> None:
    ids = tmp_store.recent_problem_ids(limit=3)
    assert ids == ("lychrel-bases", "lychrel-bases", "giuga")
    stalest = tmp_store.stalest_novelty_problem_ids(limit=3)
    assert stalest[0] == "kaprekar-maps"   # oldest novelty_checked_at first
```

`novelty_checked_at` per problem is projected as the timestamp of the last turn record naming it with nonempty `novelty_queries` (attack) or `kind=PATROL`; problems never touched project `None` and sort stalest-first.

- [ ] **Step 3: Write diversity and patrol selection tests**

Fixture: six problems, four methods. Assert:

- same snapshot/seed/turn_index yields the same selection;
- a concrete `next_action` receives the resume lane;
- **rotation cap:** with `recent_problem_ids == ("p1", "p1", "p1")`, the selector never returns `p1`, even when `p1` has the only resumable `next_action`;
- **patrol scheduling:** `turn_index` values where `(turn_index + 1) % 25 == 0` return `kind=PATROL`, `lane="patrol"`, `patrol_target_ids` = up to 3 stalest-novelty ids (deterministic), and `problem` = the stalest; all other indices return `kind=ATTACK` with empty `patrol_target_ids`;
- over a deterministic 100-seed sample at fixed `turn_index=0`: ≥20% select underused problems, ≥15% underused methods, ≥15% underused frames;
- retired methods are excluded; trial methods appear only via exploration;
- `ArenaPartition.HELD_OUT` selects only frozen held-out problems, never used for online promotion.

- [ ] **Step 4: Run tests and capture RED**

```bash
uv run pytest -q tests/unit/test_arena_domain.py tests/unit/test_arena_storage.py \
  tests/unit/test_arena_selection.py
```

- [ ] **Step 5: Implement tracked durable files and storage**

Seed `.timeloop/methods.jsonl` with immutable version-1 records for the eleven forged techniques (invariant tabulation; decidable-family reduction; derived-invariant grouping; state-space collapse; known-value sanity check; boundary argmax check; map-image reduction; wall detection and parking; intersection reduction; predict-confirm-prove; mathlib specialized-case generalization), each line carrying `id`, `version`, `state`, `description`, `sources`, `parent_ids`, `frame_ids`, `composition`, `content_sha256`. Seed established frame ids for algebraic, combinatorial, computational, finite-state, invariant, extremal, probabilistic, geometric, base-change, dual/complement, and specialized-case-generalization views. Seed `.timeloop/local/turns.jsonl` with one `{"kind": "schema", ...}` run event so the file is tracked.

Storage: append-only JSONL with canonical sorted JSON, an exclusive lock file under `.mathloop/local-arena/locks`, flush + `fsync`, content-addressed artifacts under `.mathloop/local-arena/artifacts`. One snapshot digest over pool, methods, turn events, ledger tail, and relevant notebook bytes.

Ignore only runtime scratch:

```gitignore
.timeloop/local/staging/
.timeloop/local/lease.json
```

- [ ] **Step 6: Implement deterministic diverse selection**

Seeded rank functions, no global randomness. Lane budget over deterministic selections: 10% held-out, 20% underused live problems, 15% underused method/frame candidates, remainder exploit/resume. Apply the rotation cap **before** lane logic: drop any problem equal to the last `local_rotation_cap` consecutive `recent_problem_ids`. Patrol short-circuits lanes entirely at scheduled indices. Held-out outcomes enter evaluation reports but never online scores, promotion, retirement, or revival.

- [ ] **Step 7: Run tests and lint**

```bash
uv run pytest -q tests/unit/test_arena_domain.py tests/unit/test_arena_storage.py \
  tests/unit/test_arena_selection.py
.timeloop/bin/lint
git diff --check
```

- [ ] **Step 8: Commit without staging user-owned dirty files**

```bash
git add src/mathloop/arena/__init__.py src/mathloop/arena/domain.py \
  src/mathloop/arena/storage.py src/mathloop/arena/selection.py \
  .timeloop/methods.jsonl .timeloop/local/turns.jsonl .gitignore \
  tests/unit/test_arena_domain.py tests/unit/test_arena_storage.py \
  tests/unit/test_arena_selection.py
git diff --cached --name-only | grep -v -E '^\.timeloop/(exam/results\.jsonl|ledger\.md|pool\.jsonl)$'
git commit -m "feat: add durable diverse arena state"
```

---

### Task 5: Bounded host tools and unmetered research

**Files:**
- Create: `src/mathloop/arena/tools.py`
- Create: `src/mathloop/arena/research.py`
- Create: `src/mathloop/arena/execution.py`
- Modify: `src/mathloop/processes.py`
- Create: `docker/searxng/settings.yml`
- Modify: `compose.yaml`
- Test: `tests/unit/test_arena_tools.py`
- Test: `tests/unit/test_arena_research.py`
- Test: `tests/integration/test_arena_execution.py`

**Interfaces:**
- Consumes: `LocalToolDefinition`, `scrub_paid_credentials`.
- Produces: `ArenaToolRegistry.catalog() -> tuple[LocalToolDefinition, ...]`, `ArenaToolRegistry.execute(call: LocalToolCall, turn: TurnWorkspace) -> ToolReceipt`.
- Produces: `ResearchRegistry.available_backends() -> tuple[str, ...]` (probed at turn start; feeds `research_backends_available`).
- Produces: `ResearchBackend.query(request: ResearchRequest) -> ResearchReceipt`, `BoundedProcessRunner.run(spec: ProcessSpec) -> ProcessReceipt`.
- Produces frozen `TurnWorkspace`, `ToolReceipt`, `ResearchRequest`, `ResearchReceipt`, `ProcessSpec`, `ProcessReceipt` records carrying owning turn/invocation identity and enforced byte/time limits.

- [ ] **Step 1: Write filesystem and subprocess escape tests**

Test rejection of: `..` traversal; absolute paths; symlinks escaping the repository; reads under `.env`, `.git`, `.codex`, `.engram`, and user-home credentials; canonical writes; shell strings instead of argument arrays; background descendants; output above the byte cap; elapsed timeout; paid credentials in child environment. Positive fixture reads one notebook and runs:

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
        ResearchRegistry().register(name="paid-search", backend=FakeBackend(), metered=True)


def test_search_web_requires_loopback_searxng() -> None:
    with pytest.raises(ValueError, match="loopback"):
        SearxngBackend("https://search.example.com")


def test_available_backends_reports_degraded_web() -> None:
    registry = registry_with(searxng=UnreachableBackend())
    assert "search_web" not in registry.available_backends()
    assert {"search_oeis", "search_arxiv", "search_crossref", "search_wikipedia"} <= set(
        registry.available_backends()
    )
```

Test OEIS, Crossref, and Wikipedia adapters with fake HTTP responses, request/result hashes, rate limiting, bounded response size, explicit user agent, no ambient credentials. Test the arXiv adapter separately so identifier, title, authors, version date, and abstract digest survive normalization. Test `search_web` against an injected loopback SearXNG (`GET /search?q=...&format=json`) and prove it rejects remote, credentialed, or metered services. Integration-test that decoy notebook text, system prompts, proof drafts, and environment values never appear in any captured outbound request.

- [ ] **Step 3: Run tests and capture RED**

```bash
uv run pytest -q tests/unit/test_arena_tools.py tests/unit/test_arena_research.py \
  tests/integration/test_arena_execution.py
```

- [ ] **Step 4: Implement typed tool registry**

Exact tool names and schemas:

- `read_arena_file(path: str)`
- `read_artifact(sha256: str)`
- `run_python(program: str, timeout_seconds: int)`
- `run_lean(file: str, declaration: str, replacement: str)`
- `search_oeis(query: str)`
- `search_crossref(query: str)`
- `search_arxiv(query: str)`
- `search_wikipedia(query: str)`
- `search_web(query: str)`
- `fetch_approved_url(url: str)`
- `stage_turn_record(record: object)`

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

The registry rejects unknown tools before dispatch and returns the existing receipt for an exact invocation replay. `TurnWorkspace` carries `turn_id`, resolved repository root, resolved scratch root, deadline, remaining subprocess/research/artifact budgets, and a receipt store.

- [ ] **Step 5: Implement bounded processes and curated research**

Processes: `start_new_session=True`, explicit `cwd`, scrubbed env, stdin closed, captured binary output, timeout, the repository's existing process-tree termination helper; register descendant process groups before acknowledging tool start; kill the whole tree on timeout or parent failure.

Research allowlist: OEIS JSON endpoints; Crossref REST; arXiv export API; Wikipedia REST API; explicit configured HTTPS hostname allowlist for `fetch_approved_url`; the loopback SearXNG endpoint for `search_web` only. Reject any metered or credentialed backend. Persist exact query, URL, retrieval time, status, body digest, and bounded source metadata per query. `available_backends()` probes each backend cheaply (SearXNG: `GET /healthz`, fall back to `GET /search?q=ping&format=json` with a 2 s timeout) at turn start.

- [ ] **Step 6: Add the SearXNG service**

Append to `compose.yaml`:

```yaml
  searxng:
    image: searxng/searxng:latest
    ports:
      - "127.0.0.1:8888:8080"
    volumes:
      - ./docker/searxng:/etc/searxng:ro
    environment:
      SEARXNG_BASE_URL: "http://127.0.0.1:8888/"
```

Create `docker/searxng/settings.yml`:

```yaml
use_default_settings: true
server:
  secret_key: "mathloop-local-searxng-not-a-secret"
  limiter: false
search:
  formats:
    - html
    - json
```

(The secret key is a local non-credential constant; SearXNG requires one to boot. JSON format must be enabled or `format=json` queries return 403.)

- [ ] **Step 7: Run tests and containment probes**

```bash
uv run pytest -q tests/unit/test_arena_tools.py tests/unit/test_arena_research.py \
  tests/integration/test_arena_execution.py
uv run ruff check src/mathloop/arena tests
uv run mypy
```

Run a decoy process outside the repository and prove arena cleanup leaves it alive while terminating an arena descendant.

- [ ] **Step 8: Commit**

```bash
git add src/mathloop/arena/tools.py src/mathloop/arena/research.py \
  src/mathloop/arena/execution.py src/mathloop/processes.py \
  docker/searxng/settings.yml compose.yaml \
  tests/unit/test_arena_tools.py tests/unit/test_arena_research.py \
  tests/integration/test_arena_execution.py
git commit -m "feat: add bounded tools and unmetered research"
```

---

### Task 6: Independent arena verification

**Files:**
- Create: `src/mathloop/arena/verification.py`
- Test: `tests/unit/test_arena_verification.py`
- Test: `tests/integration/test_arena_lean.py`

**Interfaces:**
- Consumes: staged claims, tool receipts, content-addressed artifacts.
- Produces: `VerificationRequest`, `VerificationReceipt`, `ArenaVerifier.verify(request: VerificationRequest) -> VerificationReceipt`.
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

Assert the first receipt is accepted and the second rejected with bounded compiler evidence. Add tests showing a model-authored `"verified": true` field and a successful Python search without an explicit range cannot create an accepted receipt.

- [ ] **Step 2: Run tests and capture RED**

```bash
uv run pytest -q tests/unit/test_arena_verification.py tests/integration/test_arena_lean.py
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

Support: Lean compilation in a temporary copy of `.timeloop/lean/arena`; exact recomputation of finite witnesses through a separately selected implementation; explicit bounded-search receipts that preserve the searched range but never claim universal truth. Require verifier implementation provenance; hash every request/evidence payload.

- [ ] **Step 4: Add same-implementation rejection tests**

If a generating tool and verifier name the same implementation identity, the receipt must have `independent=False` and cannot support a positive classification; the record validator rejects it.

- [ ] **Step 5: Run tests**

```bash
uv run pytest -q tests/unit/test_arena_verification.py \
  tests/integration/test_arena_lean.py tests/unit/test_verification.py
```

- [ ] **Step 6: Commit**

```bash
git add src/mathloop/arena/verification.py tests/unit/test_arena_verification.py \
  tests/integration/test_arena_lean.py
git commit -m "feat: independently verify arena claims"
```

---

### Task 7: Bounded turn core and continuous supervisor

**Files:**
- Create: `src/mathloop/arena/runner.py`
- Create: `src/mathloop/arena/continuous.py`
- Test: `tests/unit/test_arena_runner.py`
- Test: `tests/unit/test_continuous_supervisor.py`
- Test: `tests/integration/test_local_arena.py`
- Test: `tests/integration/test_continuous_runner.py`
- Create: `tests/helpers/continuous_child.py`

**Interfaces:**
- Consumes: `ToolCallingModelProvider`, `ArenaStateStore`, `ArenaSelector`, `ArenaToolRegistry`, `ResearchRegistry`, `ArenaVerifier`.
- Produces: `LocalArenaRunner.run_turn(selection: ArenaSelection, seed: int, turn_index: int) -> ArenaTurnRecord`.
- Produces: `LocalArenaRunner.run_batch(turns: int, seed: int) -> ArenaBatchReport` (frozen Pydantic: `batch_id`, `requested_turns`, `completed_turns`, `failed_turns`, `record_ids`, `metrics: ArenaEvaluationMetrics`, `started_at`, `completed_at`).
- Produces: `ContinuousSupervisor.run(seed: int, max_hours: float | None, require_web: bool) -> ContinuousRunReport` (frozen Pydantic: `run_id`, `turns_completed`, `halt_reason: Literal["signal","breaker","max_hours","disk_ceiling"]`, `started_at`, `halted_at`, `metrics`).
- Produces: `Lease` helpers in `continuous.py` — `acquire_lease(path: Path, *, pid: int, run_id: UUID, seed: int) -> Lease`, `Lease.heartbeat() -> None`, `Lease.release() -> None`, `expire_stale_lease(path: Path, stale_after_seconds: int) -> ArenaRunEvent | None`.

- [ ] **Step 1: Write bounded tool-loop tests (turn core)**

Scripted provider sequence: request `read_arena_file` → request `run_python` → return a strict final record. Assert ordered messages, stable invocation IDs, maximum step enforcement, token accounting, one active provider call, exact tool receipts. Add cases for refusal, malformed call, undeclared tool, repeated call replay, provider timeout before a tool, provider failure after a tool (→ `TRANSPORT_FAILURE`, no blind retry), turn timeout, invalid final record, interrupted turn. Assert every configured limit independently: the 13th model action, 4,097th output token, 13th tool call, 7th subprocess, 121st subprocess second, byte after 16 MiB artifacts, 7th research query, 3rd pre-side-effect retry, 3rd repair, byte after 2 MiB context — each ends the turn with its exact classification and a durable failure event.

Patrol-turn test: a `kind=PATROL` selection routes a patrol prompt (stored NOVELTY entries for `patrol_target_ids`), permits only research/read tools, requires `PATROL_COMPLETED`, and materializes correction appends only when research receipts justify them.

- [ ] **Step 2: Write canonical materialization tests**

```python
def test_invalid_turn_never_changes_canonical_arena_files(arena_fixture) -> None:
    before = arena_fixture.canonical_hashes()
    report = arena_fixture.runner(script="invalid-positive-without-receipt").run_batch(1, 4)
    assert report.failed_turns == 1
    assert arena_fixture.canonical_hashes() == before
    assert arena_fixture.raw_failure_event_exists()
```

Valid negative result appends turn summary + ledger entry; verified positive updates the notebook only after the receipt exists; nothing ever deletes prior notebook content; every record carries `research_backends_available` from the registry probe.

- [ ] **Step 3: Write continuous-supervisor tests**

Unit (`test_continuous_supervisor.py`, scripted runner injected):

- lease contention: second `acquire_lease` on a fresh lease raises; `expire_stale_lease` on a heartbeat older than 600 s returns one `lease_expired` event and allows acquisition;
- breaker: 5 consecutive breaker-class failures halt with `halt_reason="breaker"` and a `run_halted` event; a `NEGATIVE_RESULT`, `VERIFIER_REJECTED`, or `PATROL_COMPLETED` resets the count;
- ceilings: cumulative artifact bytes past `local_max_run_artifact_bytes` → `halt_reason="disk_ceiling"`; `max_hours` elapsed → `halt_reason="max_hours"`;
- rotation feed: supervisor passes the last `local_rotation_cap` completed problem ids into `ArenaSelector.select`;
- patrol feed: `turn_index` increments monotonically across the run so patrols land every 25th turn;
- heartbeat: a fake clock shows `Lease.heartbeat()` called at every turn boundary and by the in-turn ticker at the configured interval.

Integration (`test_continuous_runner.py`): spawn `tests/helpers/continuous_child.py` as a subprocess (it wires a scripted slow provider into `ContinuousSupervisor.run` against a tmp arena fixture), send SIGTERM mid-turn, assert exit 0, an `INTERRUPTED` turn record, a released lease, and a `run_halted` event with `halt_reason="signal"`; send SIGTERM twice quickly and assert immediate exit with the lease left stale, then a fresh start records exactly one `lease_expired`.

- [ ] **Step 4: Run tests and capture RED**

```bash
uv run pytest -q tests/unit/test_arena_runner.py tests/unit/test_continuous_supervisor.py \
  tests/integration/test_local_arena.py tests/integration/test_continuous_runner.py
```

- [ ] **Step 5: Implement the turn core**

Fixed state machine:

```text
ORIENTED -> MODEL_PENDING -> TOOL_PENDING -> MODEL_PENDING
ORIENTED/MODEL_PENDING -> FINAL_PENDING -> VERIFYING -> MATERIALIZING -> COMPLETE
any non-terminal state -> FAILED
```

Persist every model/tool event before advancing. Serialize model generation with a process-safe concurrency gate of one. Retry a transport failure at most twice and only while no tool side effect has a receipt; afterwards record and end. Partial output is never parsed as final. The model returns a `ProposedArenaTurn`; the host derives identity, digests, receipts, token/time/cost, final status, and allowed canonical updates — the model cannot supply or override them. Positive statuses require accepted independent receipts. Materialization uses the selection's snapshot digest and fails on concurrent canonical changes. Contradictions append corrections with superseded record IDs; nothing is overwritten.

- [ ] **Step 6: Implement the continuous supervisor**

```python
class ContinuousSupervisor:
    def run(self, seed: int, max_hours: float | None, require_web: bool) -> ContinuousRunReport:
        event = expire_stale_lease(self.lease_path, self.settings.local_stale_lease_seconds)
        if event is not None:
            self.store.append_run_event(event)
        lease = acquire_lease(self.lease_path, pid=os.getpid(), run_id=self.run_id, seed=seed)
        self.store.append_run_event(self._run_started())
        stop = _SignalFlag.install()          # first signal: request stop; second: raise SystemExit
        ticker = _HeartbeatTicker(lease, self.settings.local_heartbeat_seconds)
        turn_index, consecutive_failures = self._resume_counters()
        try:
            while True:
                if stop.requested:
                    return self._halt("signal", turn_index)
                if consecutive_failures >= self.settings.local_breaker_consecutive_failures:
                    return self._halt("breaker", turn_index)
                if self._deadline_passed(max_hours):
                    return self._halt("max_hours", turn_index)
                if self._artifact_bytes_used() >= self.settings.local_max_run_artifact_bytes:
                    return self._halt("disk_ceiling", turn_index)
                selection = self.selector.select(
                    self.store.snapshot(), seed, turn_index,
                    self.store.recent_problem_ids(limit=self.settings.local_rotation_cap),
                )
                with ticker.during_turn():
                    record = self.runner.run_turn(selection, seed, turn_index)
                lease.heartbeat()
                consecutive_failures = (
                    consecutive_failures + 1 if record.status in BREAKER_FAILURE_STATUSES else 0
                )
                turn_index += 1
        finally:
            ticker.stop()
            lease.release()
```

Lease writes are atomic (temp file + `os.replace`). The signal handler converts an in-flight turn into an `INTERRUPTED` record via the runner's cancellation hook rather than killing mid-write. `_resume_counters()` projects `turn_index` from prior records so patrol cadence survives restarts. `require_web=True` makes an unavailable `search_web` backend a preflight `LocalCapabilityUnavailableError`.

- [ ] **Step 7: Prove populations and metrics behave over a long scripted run**

Run 100 scripted turns with mixed outcomes. Assert: new problems enter from `pool.jsonl`; a unique proposed method becomes `trial`; verified outcomes affect exploitation; retired methods disappear; exploration counts stay nonzero for both populations; no problem exceeds 3 consecutive turns anywhere in the sequence; patrols occur exactly at indices 24, 49, 74, 99; held-out outcomes never affect online scores. Compute `ArenaEvaluationMetrics` exactly as in the superseded plan (attempted/valid turns, repaired/total model actions, verified leads, rejected positives, distinct problem/frame ids, resumed/cold turns, reused negatives, wall seconds, tokens, held-out attempts/leads) plus `patrol_turns: int` and `patrol_corrections: int`; derived rates define zero-denominator as `Decimal("0")`.

- [ ] **Step 8: Run focused suites and lint**

```bash
uv run pytest -q tests/unit/test_arena_runner.py tests/unit/test_continuous_supervisor.py \
  tests/integration/test_local_arena.py tests/integration/test_continuous_runner.py \
  tests/unit/test_arena_selection.py tests/integration/test_arena_lean.py
.timeloop/bin/lint
```

- [ ] **Step 9: Commit**

```bash
git add src/mathloop/arena/runner.py src/mathloop/arena/continuous.py \
  tests/unit/test_arena_runner.py tests/unit/test_continuous_supervisor.py \
  tests/integration/test_local_arena.py tests/integration/test_continuous_runner.py \
  tests/helpers/continuous_child.py
git commit -m "feat: run continuous local arena turns"
```

---

### Task 8: CLI, `bin/research`, and production local method

**Files:**
- Modify: `src/mathloop/methods/proof_sketch.py`
- Create: `src/mathloop/methods/local_proof.py`
- Modify: `src/mathloop/provenance.py`
- Modify: `src/mathloop/runtime.py`
- Modify: `src/mathloop/cli.py`
- Create: `bin/research`
- Test: `tests/unit/test_local_proof_method.py`
- Test: `tests/unit/test_cli.py`
- Test: `tests/integration/test_local_runtime.py`
- Test: `tests/integration/test_worker_billing.py`

**Interfaces:**
- Consumes: `OllamaLifecycle`, `LocalModelProvider`, `LocalArenaRunner`, `ContinuousSupervisor`.
- Produces: `LocalProofStrategy.family == "local_proof_sketch"`.
- Produces CLI: `local init`, `local status`, `local research`, `local arena`, `local run`, `local stop`.
- Produces helpers returning frozen Pydantic reports emitted via `.model_dump_json()`: `_local_init(settings) -> LocalInitReport`, `_local_status(settings) -> LocalStatusReport`, `_local_research(settings, seed, max_hours, require_web) -> ContinuousRunReport`, `_local_arena(settings, turns, seed) -> ArenaBatchReport`, `_local_run(settings, cycles, workers) -> LocalRunReport`, `_local_stop(settings) -> LocalStopReport`.

- [ ] **Step 1: Write local proof-method tests**

Assert the method: sends only the normalized problem statement; treats problem text as untrusted; constructs `ModelCostAuthorization(Decimal("0.000000"))`; returns `status="lead"` with no claim or witness; includes local runtime identity and zero-dollar receipts; marks external execution before the provider call; rejects a non-local receipt; uses family `local_proof_sketch`.

- [ ] **Step 2: Write runtime mutual-exclusion and accounting tests**

Construct runtimes for all four modes; only local mode registers `local_proof_sketch`; no mode registers two external families. Execute one local proof lead, then:

```python
assert experiment.cost_usd == Decimal("0.000000")
assert artifact["billing_receipt"]["provider"] == "local-ollama"
assert artifact["billing_receipt"]["actual_cost_usd"] == "0.000000"
assert repository.daily_spend(day) == Decimal("0.000000")
```

Patch OpenAI and Codex construction to raise if touched.

- [ ] **Step 3: Write CLI tests**

`mathloop local --help` lists `init status research arena run stop`. Test:

- `local init` invokes lifecycle readiness plus a no-write structured/tool canary;
- `local status` is read-only (never spawns, loads, or writes) and reports lease state, current/last turn, counts from `.timeloop/local/turns.jsonl`, and backend availability;
- `local research` defaults `seed=1`, `max_hours=None`, `require_web=False`; `--max-hours 0` rejected;
- bare `local arena` uses `turns=20 seed=1`; `--turns 0` rejected;
- `local run` defaults `cycles=5 workers=1` and builds only local mode;
- `local stop` reads the lease, sends SIGTERM to its pid, and reports `stopped=True/False`; with no lease it reports `running=False` without error;
- no local command accepts `--api-enabled` or any paid-fallback flag.

- [ ] **Step 4: Run tests and capture RED**

```bash
uv run pytest -q tests/unit/test_local_proof_method.py tests/unit/test_cli.py \
  tests/integration/test_local_runtime.py tests/integration/test_worker_billing.py
```

- [ ] **Step 5: Implement provenance, deferred registration, CLI**

Provenance incorporates local runtime identity digest, model name/digest, quantization, context length, provider and method implementation hashes, and lockfile identity; `require_current_method_provenance` rejects scheduled work from a prior identity. Mirror the deferred-client pattern:

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

No live HTTP client across fork boundaries; one interprocess gate serializes local generation. CLI:

```python
@local_app.command("research")
def local_research(
    seed: int = 1,
    max_hours: Annotated[float | None, typer.Option(min=0.1)] = None,
    require_web: bool = False,
) -> None:
    typer.echo(_local_research(Settings(), seed, max_hours, require_web).model_dump_json())
```

plus `init`, `status`, `arena(turns: min=1 = 20, seed=1)`, `run(cycles: min=1 = 5, workers: min=1 = 1)`, `stop` with the same echo pattern.

- [ ] **Step 6: Implement `bin/research`**

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

case "${1:-run}" in
  status) exec uv run mathloop local status ;;
  stop)   exec uv run mathloop local stop ;;
  run|*)
    [ "${1:-run}" = "run" ] && shift || true
    uv run mathloop local init
    if command -v docker >/dev/null 2>&1; then
      docker compose up -d searxng || echo "warn: searxng unavailable; web search degraded" >&2
    else
      echo "warn: docker absent; web search degraded" >&2
    fi
    exec caffeinate -i uv run mathloop local research "$@"
    ;;
esac
```

`chmod +x bin/research`. Add a CLI test invoking `bin/research status` via subprocess to prove the wrapper resolves the repo root from any cwd.

- [ ] **Step 7: Run local, compatibility, and full offline tests**

```bash
uv run pytest -q tests/unit/test_local_proof_method.py tests/unit/test_cli.py \
  tests/integration/test_local_runtime.py tests/integration/test_worker_billing.py \
  tests/integration/test_runtime_loop.py tests/integration/test_codex_runtime.py \
  tests/unit/test_openai_provider.py
uv run pytest -q
uv run ruff check .
uv run mypy
```

- [ ] **Step 8: Commit**

```bash
git add src/mathloop/methods/proof_sketch.py src/mathloop/methods/local_proof.py \
  src/mathloop/provenance.py src/mathloop/runtime.py src/mathloop/cli.py bin/research \
  tests/unit/test_local_proof_method.py tests/unit/test_cli.py \
  tests/integration/test_local_runtime.py tests/integration/test_worker_billing.py
git commit -m "feat: expose continuous local research commands"
```

---

### Task 9: Documentation, live canary, controlled batch, supervised soak

**Files:**
- Modify: `.timeloop/README.md`
- Modify: `.timeloop/ARENA.md`
- Create: `docs/verification/continuous-ollama-acceptance.md`
- Create: `tests/e2e/test_local_model_canary.py`
- Modify: `pyproject.toml` (only the `live_local_model` marker registration)

**Interfaces:**
- Consumes: completed local CLI and installed `qwen3.8:27b-mlx`.
- Produces: exact acceptance evidence, first controlled batch report, soak report.

- [ ] **Step 1: Add an explicitly marked live-local canary**

Register a `live_local_model` pytest marker. The test skips with an exact reason when `GET /api/tags` has no unique `qwen3.8:27b-mlx`. When available it:

1. fingerprints `.timeloop` canonical files and the real production database;
2. runs lifecycle readiness and asserts the exact resolved model identity (name + digest);
3. checks strict structured output;
4. records whether `extra_body={"think": ...}` measurably toggles reasoning content, and files the observation in the acceptance doc (contingency: native `/api/chat` path, not built now);
5. executes one read-only tool call in an isolated arena fixture;
6. rejects `∀ x : ZMod 6, x^2 = x`;
7. accepts `∀ x : ZMod 6, x^3 = x`;
8. asserts all receipts cost zero, no paid-provider event or credential exposure;
9. asserts only the isolated fixture changed.

- [ ] **Step 2: Write operator documentation**

Document in `.timeloop/README.md` and `.timeloop/ARENA.md`:

```bash
bin/research                # continuous; Ctrl-C or bin/research stop to end
bin/research --max-hours 8
bin/research status
bin/research stop
uv run mathloop local arena --turns 5 --seed 1   # bounded smoke
```

Cover: startup behavior, keep_alive, the no-download rule, the local-only guarantee, lease/heartbeat and stale recovery, circuit breaker and ceilings, rotation cap and patrol cadence, degraded-web semantics and `--require-web`, tracked vs ignored files, inspecting receipts, resuming, interrupting safely, diagnosing absent/ambiguous models, and the live-probe surface (`status` + `tail -f .timeloop/local/turns.jsonl`).

- [ ] **Step 3: Run the complete offline release matrix**

```bash
uv run pytest -q
uv run ruff check .
uv run mypy
.timeloop/bin/lint
.timeloop/bin/exam
git diff --check
```

Record literal counts and commands in `docs/verification/continuous-ollama-acceptance.md`.

- [ ] **Step 4: Verify installed-model visibility without downloading**

```bash
curl -s http://127.0.0.1:11434/api/tags | uv run python -c \
  "import json,sys; names=[m['name'] for m in json.load(sys.stdin)['models']]; print(names)"
```

If no unique `qwen3.8:27b-mlx` exists, stop with code-complete but release-blocked status. Do not run `ollama pull`, change the selector, or substitute another model.

- [ ] **Step 5: Run the live release canary**

```bash
uv run pytest -q -m live_local_model tests/e2e/test_local_model_canary.py -vv
```

Expected: one passing canary, exact identity recorded, no canonical mutation.

- [ ] **Step 6: Run one controlled bounded batch and review it**

Require a clean worktree except the pre-existing user-owned changes named in Global Constraints. Run:

```bash
uv run mathloop local arena --turns 3 --seed 1
```

Human-review all three raw receipts, tool calls, verification outcomes, and proposed updates. Run `.timeloop/bin/lint`. No novelty claims, no publication. Commit validated durable summaries separately (see Step 9).

- [ ] **Step 7: Run the supervised soak**

With the operator present:

```bash
bin/research --max-hours 2
```

While it runs, from a second terminal: `bin/research status` and `tail -f .timeloop/local/turns.jsonl` must both work; end with `bin/research stop` if it has not halted. Afterward verify: turns rotated targets (no >3 consecutive), at least one patrol fired if ≥25 turns completed (otherwise note turn count), zero paid-provider events, all receipts zero-dollar, breaker/ceiling counters consistent, and the halt event matches how the run ended. Record findings in the acceptance doc. **The first unattended overnight run is authorized only after this review.**

- [ ] **Step 8: Run post-soak verification**

```bash
uv run pytest -q
uv run ruff check .
uv run mypy
.timeloop/bin/lint
git diff --check
git status --short
```

Confirm pre-existing user-owned files are preserved byte-for-byte.

- [ ] **Step 9: Commit documentation, canary, and reviewed durable state**

```bash
git add .timeloop/README.md .timeloop/ARENA.md \
  docs/verification/continuous-ollama-acceptance.md \
  tests/e2e/test_local_model_canary.py pyproject.toml
git commit -m "docs: verify continuous Ollama researcher"
```

Then, after human review of batch/soak durable output only:

```bash
git add .timeloop/local/turns.jsonl .timeloop/methods.jsonl
git commit -m "experiment: record first continuous local runs"
```

Do not stage `.timeloop/exam/results.jsonl`, `.timeloop/ledger.md`, or `.timeloop/pool.jsonl` unless the batch itself appended to them and the diff has been human-reviewed hunk-by-hunk (`git add -p`).

---

## Final release verification

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

Release authorization requires: zero offline failures; one passing real `qwen3.8:27b-mlx` canary; a human-reviewed controlled batch; a reviewed 2-hour supervised soak; no paid provider construction or receipt in local mode; exact zero-dollar settlements; exact installed-model provenance; no download path; no non-loopback inference path; no canonical mutation from invalid or rejected turns; nonzero problem and method/frame exploration; rotation and patrol visible in records; independent positive verification; a clean worktree except the preserved user-owned changes.
