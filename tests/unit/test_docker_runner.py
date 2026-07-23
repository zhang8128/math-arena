import importlib.util
import json
import secrets
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from mathloop.provenance import SAGE_IMAGE_DIGEST
from mathloop.tools.docker import DockerLimits, DockerRunner, SandboxFailure


def _runner() -> DockerRunner:
    return DockerRunner(
        image=SAGE_IMAGE_DIGEST,
        limits=DockerLimits(seconds=7, memory_mb=384, cpus=0.5),
    )


def _load_sage_runner(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    sage = ModuleType("sage")
    sage_all = ModuleType("sage.all")
    sage_all.QQ = object()
    sage_all.ZZ = int
    sage_all.PolynomialRing = object
    sage_all.factor = object
    sage.all = sage_all  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sage", sage)
    monkeypatch.setitem(sys.modules, "sage.all", sage_all)
    path = Path(__file__).parents[2] / "docker" / "sage" / "runner.py"
    spec = importlib.util.spec_from_file_location("tested_sage_runner", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("predicate_id", "n", "expected_value"),
    [
        ("sum_odds", 4, 16),
        ("sum_integers", 4, 10),
    ],
)
def test_sage_sum_predicates_compare_evaluated_sum_to_closed_form(
    predicate_id: str,
    n: int,
    expected_value: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_sage_runner(monkeypatch)
    evaluated = SimpleNamespace(calls=0)

    def deliberately_wrong_sum(values: object) -> int:
        list(values)  # type: ignore[arg-type]
        evaluated.calls += 1
        return -1

    monkeypatch.setattr(module, "sum", deliberately_wrong_sum, raising=False)

    assert module._predicate(predicate_id, n) == (False, expected_value)  # type: ignore[attr-defined]
    assert evaluated.calls == 1


def test_run_json_uses_exact_restricted_argv_and_canonical_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []
    monkeypatch.setattr(secrets, "token_hex", lambda size: "a" * (size * 2))

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(
            command, 0, stdout=b'{"ok": true, "value": 3}', stderr=b""
        )

    monkeypatch.setattr("mathloop.tools.docker.subprocess.run", fake_run)

    result = _runner().run_json({"z": 1, "a": 2})

    assert result == {"ok": True, "value": 3}
    assert calls == [
        (
            [
                "docker",
                "run",
                "--rm",
                "--name",
                "mathloop-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "-i",
                "--network",
                "none",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--memory",
                "384m",
                "--cpus",
                "0.5",
                "--pids-limit",
                "64",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=64m",
                SAGE_IMAGE_DIGEST,
            ],
            {
                "input": json.dumps({"z": 1, "a": 2}, sort_keys=True).encode(),
                "capture_output": True,
                "check": False,
                "timeout": 7,
            },
        )
    ]


def test_run_json_raises_typed_failure_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []
    monkeypatch.setattr(secrets, "token_hex", lambda size: "b" * (size * 2))

    def time_out_then_clean_up(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        calls.append((command, kwargs))
        if command[:2] == ["docker", "run"]:
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr("mathloop.tools.docker.subprocess.run", time_out_then_clean_up)

    with pytest.raises(SandboxFailure, match="timed out"):
        _runner().run_json({"operation": "factor", "value": 1681})

    assert calls[1] == (
        ["docker", "rm", "-f", "mathloop-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"],
        {
            "capture_output": True,
            "check": False,
            "shell": False,
            "timeout": 5,
        },
    )


@pytest.mark.parametrize(
    "cleanup_result",
    [
        subprocess.CompletedProcess([], 1, stdout=b"", stderr=b"already removed"),
        subprocess.TimeoutExpired(["docker", "rm"], 5),
        OSError("docker unavailable"),
    ],
)
def test_timeout_cleanup_failure_does_not_mask_sandbox_timeout(
    monkeypatch: pytest.MonkeyPatch,
    cleanup_result: subprocess.CompletedProcess[bytes] | BaseException,
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(secrets, "token_hex", lambda size: "c" * (size * 2))

    def time_out_then_fail_cleanup(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        calls.append(command)
        if command[:2] == ["docker", "run"]:
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        if isinstance(cleanup_result, BaseException):
            raise cleanup_result
        return cleanup_result

    monkeypatch.setattr("mathloop.tools.docker.subprocess.run", time_out_then_fail_cleanup)

    with pytest.raises(SandboxFailure, match="sandbox timed out after 7 seconds"):
        _runner().run_json({"operation": "factor", "value": 1681})

    assert calls[1] == [
        "docker",
        "rm",
        "-f",
        "mathloop-cccccccccccccccccccccccccccccccc",
    ]


@pytest.mark.parametrize(
    ("completed", "message"),
    [
        (subprocess.CompletedProcess([], 2, stdout=b"", stderr=b"denied"), "exit code 2"),
        (subprocess.CompletedProcess([], 0, stdout=b"not json", stderr=b""), "invalid JSON"),
        (
            subprocess.CompletedProcess(
                [], 0, stdout=b'{"ok": false, "error": "unsupported"}', stderr=b""
            ),
            "unsupported",
        ),
    ],
)
def test_run_json_raises_typed_failure_for_failed_sandbox_responses(
    monkeypatch: pytest.MonkeyPatch,
    completed: subprocess.CompletedProcess[bytes],
    message: str,
) -> None:
    monkeypatch.setattr("mathloop.tools.docker.subprocess.run", lambda *args, **kwargs: completed)

    with pytest.raises(SandboxFailure, match=message):
        _runner().run_json({"operation": "factor", "value": 1681})


def test_runner_rejects_images_outside_the_fixed_allowlist() -> None:
    with pytest.raises(ValueError, match="sandbox image is not allowlisted"):
        DockerRunner(
            image="sagemath/sagemath:latest",
            limits=DockerLimits(seconds=7, memory_mb=384, cpus=0.5),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("seconds", 0),
        ("seconds", -1),
        ("seconds", True),
        ("seconds", 1.5),
        ("memory_mb", 0),
        ("memory_mb", 127),
        ("memory_mb", True),
        ("memory_mb", 256.0),
        ("cpus", 0),
        ("cpus", -0.5),
        ("cpus", True),
        ("cpus", float("nan")),
        ("cpus", float("inf")),
        ("cpus", float("-inf")),
    ],
)
def test_docker_limits_reject_invalid_or_unsafe_values(field: str, value: object) -> None:
    values: dict[str, object] = {"seconds": 7, "memory_mb": 384, "cpus": 0.5}
    values[field] = value

    with pytest.raises(ValueError, match=field):
        DockerLimits(**values)  # type: ignore[arg-type]
