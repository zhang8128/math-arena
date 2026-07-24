"""Unit coverage for `CodexProofStrategyMethod` and its registration guard.

The client here is a small hand-rolled fake -- not the real `CodexClient` --
because these tests are about the method's own orchestration (config
validation, prompt framing, artifact shape, and the `on_dispatched` wiring),
not about supervising a real subprocess (that is `test_codex_client.py`'s
job). `base_sha` resolution is the one exception: it shells out to a real,
throwaway git repository, matching this codebase's convention of never
mocking a git subprocess call.
"""

import hashlib
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from mathloop.codex.client import CodexClientError, CodexRequest, CodexResponse
from mathloop.codex.domain import CodexModelRole, CodexTurnReceipt, CodexTurnReservation, CodexUsage
from mathloop.codex.events import CodexEvent
from mathloop.config import Settings
from mathloop.domain import Problem, ProblemStatus
from mathloop.methods.base import MethodContext, MethodRegistry, MethodResult
from mathloop.methods.codex_agent import CodexProofStrategyMethod, register_codex_proof_strategy
from mathloop.methods.proof_sketch import ProofSketch
from mathloop.provenance import codex_method_provenance, method_provenance

# ---------------------------------------------------------------------------
# Test scaffolding
# ---------------------------------------------------------------------------


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(repo: Path) -> str:
    repo.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", "-b", "main", cwd=repo)
    _git("config", "user.email", "codex-method-test@example.com", cwd=repo)
    _git("config", "user.name", "Codex Method Test", cwd=repo)
    (repo / "README.md").write_text("seed content\n")
    _git("add", "-A", cwd=repo)
    _git("commit", "-q", "-m", "seed", cwd=repo)
    return _git("rev-parse", "HEAD", cwd=repo).stdout.strip()


def _problem() -> Problem:
    return Problem(
        id=uuid4(),
        source_id=f"test/{uuid4()}",
        source_uri="local://codex-method-test",
        source_hash="a" * 64,
        statement="raw statement",
        normalized_statement="Every even integer greater than 2 is the sum of two primes.",
        domain="testing",
        features={},
        checker={"kind": "unsupported"},
        status=ProblemStatus.ELIGIBLE,
        cohort="development",
        version=1,
        created_at=datetime.now(UTC),
    )


def _reservation(
    *, role: CodexModelRole = CodexModelRole.TERRA, model: str = "gpt-5.6-terra"
) -> CodexTurnReservation:
    now = datetime.now(UTC)
    return CodexTurnReservation(
        id=uuid4(),
        experiment_id=uuid4(),
        budget_day=now.date(),
        role=role,
        model=model,
        deadline_seconds=1800,
        created_at=now,
    )


def _receipt(reservation: CodexTurnReservation) -> CodexTurnReceipt:
    return CodexTurnReceipt(
        reservation_id=reservation.id,
        experiment_id=reservation.experiment_id,
        thread_id="thread-fake",
        model=reservation.model,
        cli_version="0.145.0-test",
        usage=CodexUsage(
            input_tokens=100,
            cached_input_tokens=10,
            output_tokens=12,
            reasoning_output_tokens=5,
        ),
        final_status="completed",
    )


def _settings(repo_root: Path, *, codex_enabled: bool = False) -> Settings:
    return Settings(
        artifact_root=repo_root / "artifacts",
        incoming_root=repo_root / "incoming",
        codex_repo_root=repo_root,
        codex_enabled=codex_enabled,
    )


class _FakeCodexClient:
    """A duck-typed stand-in for `CodexClient.execute` -- either succeeds or raises."""

    def __init__(
        self,
        *,
        response: CodexResponse[ProofSketch] | None = None,
        error: BaseException | None = None,
    ) -> None:
        self._response = response
        self._error = error
        self.requests: list[CodexRequest[ProofSketch]] = []
        self.on_dispatched_calls: list[str] = []

    def execute(
        self,
        request: CodexRequest[ProofSketch],
        emit_event: Callable[[CodexEvent], None],
        *,
        on_dispatched: Callable[[], None] | None = None,
    ) -> CodexResponse[ProofSketch]:
        self.requests.append(request)
        if on_dispatched is not None:
            on_dispatched()
            self.on_dispatched_calls.append("dispatched")
        emit_event(
            CodexEvent(
                sequence=0,
                event_type="thread.started",
                payload={"type": "thread.started"},
                raw_sha256="a" * 64,
            )
        )
        if self._error is not None:
            raise self._error
        assert self._response is not None
        return self._response


class _StubMethod:
    def __init__(self, family: str) -> None:
        self.family = family

    def run(self, context: MethodContext) -> MethodResult:
        raise NotImplementedError


_USE_RESERVATION_ID = object()


def _context(
    *,
    reservation: CodexTurnReservation,
    external_execution_id: object = _USE_RESERVATION_ID,
    external_execution_callback: Callable[[], None] | None = None,
    emit_external_event: Callable[[CodexEvent], None] | None = None,
) -> MethodContext:
    resolved_id = (
        reservation.id
        if external_execution_id is _USE_RESERVATION_ID
        else external_execution_id
    )
    resolved_emit = emit_external_event if emit_external_event is not None else _ignore_event
    return MethodContext(
        problem=_problem(),
        seed=1,
        config={"codex_reservation": reservation},
        external_execution_id=resolved_id,  # type: ignore[arg-type]
        external_execution_callback=external_execution_callback,
        emit_external_event=resolved_emit,
    )


def _ignore_event(event: CodexEvent) -> None:
    del event


# ---------------------------------------------------------------------------
# Brief-verbatim case
# ---------------------------------------------------------------------------


def test_codex_method_returns_non_authoritative_lead_and_receipt(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _init_repo(repo_root)
    reservation = _reservation()
    fake_response = CodexResponse(
        value=ProofSketch(
            strategy="induction",
            lemmas=["base case holds"],
            risks=["induction step may hide an off-by-one"],
        ),
        receipt=_receipt(reservation),
        patch=b"diff --git a/x b/x\n",
        patch_sha256=hashlib.sha256(b"diff --git a/x b/x\n").hexdigest(),
    )
    client = _FakeCodexClient(response=fake_response)
    method = CodexProofStrategyMethod(
        _settings(repo_root, codex_enabled=True), client, reservation.model, reservation.role  # type: ignore[arg-type]
    )
    context = _context(reservation=reservation)

    result = method.run(context)

    assert result.status == "lead"
    assert result.claim is None
    assert result.witness is None
    assert result.codex_turn_receipt == fake_response.receipt
    assert result.artifact is not None
    assert b'"accounting_unit":"chatgpt_codex_turn"' in result.artifact
    assert b'"usd"' not in result.artifact


def test_prompt_frames_the_problem_as_untrusted_data_and_covers_every_required_point(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    _init_repo(repo_root)
    reservation = _reservation()
    fake_response = CodexResponse(
        value=ProofSketch(strategy="s", lemmas=["l"], risks=["r"]),
        receipt=_receipt(reservation),
        patch=b"",
        patch_sha256=hashlib.sha256(b"").hexdigest(),
    )
    client = _FakeCodexClient(response=fake_response)
    method = CodexProofStrategyMethod(
        _settings(repo_root, codex_enabled=True), client, reservation.model, reservation.role  # type: ignore[arg-type]
    )
    context = _context(reservation=reservation)

    method.run(context)

    assert len(client.requests) == 1
    prompt = client.requests[0].prompt
    assert "untrusted mathematical data" in prompt
    assert "strategy" in prompt and "lemmas" in prompt and "risks" in prompt
    assert "inspect this repository" in prompt or "local tests" in prompt
    assert "never claim" in prompt or "not a verified result" in prompt
    assert context.problem.normalized_statement in prompt


# ---------------------------------------------------------------------------
# The one pointer that matters most: on_dispatched must be wired even when
# the turn fails after dispatch, not just on the success path.
# ---------------------------------------------------------------------------


def test_on_dispatched_is_wired_even_when_the_turn_fails_after_dispatch(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _init_repo(repo_root)
    reservation = _reservation()
    client = _FakeCodexClient(error=CodexClientError("codex exited with code 1"))
    method = CodexProofStrategyMethod(
        _settings(repo_root, codex_enabled=True), client, reservation.model, reservation.role  # type: ignore[arg-type]
    )
    started: list[str] = []
    context = _context(
        reservation=reservation,
        external_execution_callback=lambda: started.append("dispatched"),
    )

    with pytest.raises(CodexClientError):
        method.run(context)

    # Load-bearing: if the method's `run()` ever dropped
    # `on_dispatched=context.mark_external_execution_started` from its call
    # into `self.client.execute(...)`, `started` would stay empty here even
    # though the fake client genuinely dispatched before raising -- exactly
    # the silent, unsafe-direction bug the worker depends on this wiring to
    # prevent (a dispatched-then-failed turn would be recorded as a clean
    # FAILED instead of AMBIGUOUS/TIMED_OUT, understating real Codex spend).
    assert started == ["dispatched"]
    assert client.on_dispatched_calls == ["dispatched"]


# ---------------------------------------------------------------------------
# Invalid-configuration guards
# ---------------------------------------------------------------------------


def test_missing_external_execution_id_is_rejected(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _init_repo(repo_root)
    reservation = _reservation()
    client = _FakeCodexClient()
    method = CodexProofStrategyMethod(
        _settings(repo_root, codex_enabled=True), client, reservation.model, reservation.role  # type: ignore[arg-type]
    )
    context = _context(reservation=reservation, external_execution_id=None)

    result = method.run(context)

    assert result.status == "invalid_config"
    assert client.requests == []


def test_missing_emit_external_event_is_rejected(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _init_repo(repo_root)
    reservation = _reservation()
    client = _FakeCodexClient()
    method = CodexProofStrategyMethod(
        _settings(repo_root, codex_enabled=True), client, reservation.model, reservation.role  # type: ignore[arg-type]
    )
    context = MethodContext(
        problem=_problem(),
        seed=1,
        config={"codex_reservation": reservation},
        external_execution_id=reservation.id,
        emit_external_event=None,
    )

    result = method.run(context)

    assert result.status == "invalid_config"
    assert client.requests == []


def test_missing_reservation_in_config_is_rejected(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _init_repo(repo_root)
    reservation = _reservation()
    client = _FakeCodexClient()
    method = CodexProofStrategyMethod(
        _settings(repo_root, codex_enabled=True), client, reservation.model, reservation.role  # type: ignore[arg-type]
    )
    context = MethodContext(
        problem=_problem(),
        seed=1,
        config={},
        external_execution_id=reservation.id,
        emit_external_event=lambda e: None,
    )

    result = method.run(context)

    assert result.status == "invalid_config"
    assert client.requests == []


def test_external_execution_id_must_match_the_reservation_id(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _init_repo(repo_root)
    reservation = _reservation()
    client = _FakeCodexClient()
    method = CodexProofStrategyMethod(
        _settings(repo_root, codex_enabled=True), client, reservation.model, reservation.role  # type: ignore[arg-type]
    )
    context = _context(reservation=reservation, external_execution_id=uuid4())

    result = method.run(context)

    assert result.status == "invalid_config"
    assert client.requests == []


@pytest.mark.parametrize(
    ("configured_model", "configured_role"),
    [("gpt-5.6-terra", CodexModelRole.SOL), ("gpt-5.6-sol", CodexModelRole.TERRA)],
)
def test_reservation_role_and_model_must_match_the_configured_method(
    tmp_path: Path, configured_model: str, configured_role: CodexModelRole
) -> None:
    repo_root = tmp_path / "repo"
    _init_repo(repo_root)
    reservation = _reservation(role=CodexModelRole.TERRA, model="gpt-5.6-terra")
    client = _FakeCodexClient()
    method = CodexProofStrategyMethod(
        _settings(repo_root, codex_enabled=True), client, configured_model, configured_role  # type: ignore[arg-type]
    )
    context = _context(reservation=reservation)

    result = method.run(context)

    assert result.status == "invalid_config"
    assert client.requests == []


@pytest.mark.parametrize(
    ("model", "role"),
    [("", CodexModelRole.TERRA), ("   ", CodexModelRole.TERRA)],
)
def test_constructor_rejects_empty_model(model: str, role: CodexModelRole) -> None:
    with pytest.raises(ValueError, match="model"):
        CodexProofStrategyMethod(Settings(), object(), model, role)  # type: ignore[arg-type]


def test_constructor_rejects_non_string_model() -> None:
    with pytest.raises(TypeError, match="model"):
        CodexProofStrategyMethod(Settings(), object(), 5, CodexModelRole.TERRA)  # type: ignore[arg-type]


def test_constructor_rejects_non_role() -> None:
    with pytest.raises(TypeError, match="role"):
        CodexProofStrategyMethod(Settings(), object(), "gpt-5.6-terra", "terra")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# register_codex_proof_strategy: enable-flag gating and provider exclusivity
# ---------------------------------------------------------------------------


def test_register_codex_proof_strategy_is_a_noop_when_disabled(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _init_repo(repo_root)
    registry = MethodRegistry()
    settings = _settings(repo_root, codex_enabled=False)
    client = _FakeCodexClient()

    registered = register_codex_proof_strategy(
        registry, settings, client, model="gpt-5.6-terra", role=CodexModelRole.TERRA  # type: ignore[arg-type]
    )

    assert registered is False
    assert registry.contains(CodexProofStrategyMethod.family) is False


def test_register_codex_proof_strategy_registers_when_enabled(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _init_repo(repo_root)
    registry = MethodRegistry()
    settings = _settings(repo_root, codex_enabled=True)
    client = _FakeCodexClient()

    registered = register_codex_proof_strategy(
        registry, settings, client, model="gpt-5.6-terra", role=CodexModelRole.TERRA  # type: ignore[arg-type]
    )

    assert registered is True
    assert registry.contains(CodexProofStrategyMethod.family) is True
    expected = codex_method_provenance(
        model="gpt-5.6-terra",
        role=CodexModelRole.TERRA,
        min_cli_version=settings.codex_min_cli_version,
    )
    assert registry.provenance(CodexProofStrategyMethod.family) == expected


def test_codex_and_api_methods_cannot_both_register(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _init_repo(repo_root)
    registry = MethodRegistry()
    registry.register(_StubMethod("proof_sketch"), provenance=method_provenance("proof_sketch"))
    settings = _settings(repo_root, codex_enabled=True)
    client = _FakeCodexClient()

    with pytest.raises(ValueError, match="cannot both be registered"):
        register_codex_proof_strategy(
            registry, settings, client, model="gpt-5.6-terra", role=CodexModelRole.TERRA  # type: ignore[arg-type]
        )

    assert registry.contains(CodexProofStrategyMethod.family) is False
