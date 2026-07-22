import json
import subprocess

import pytest

from mathloop.tools.docker import DockerLimits, DockerRunner, SandboxFailure


def _runner() -> DockerRunner:
    return DockerRunner(
        image="mathloop-sage:10.9",
        limits=DockerLimits(seconds=7, memory_mb=384, cpus=0.5),
    )


def test_run_json_uses_exact_restricted_argv_and_canonical_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

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
                "mathloop-sage:10.9",
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
    def time_out(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr("mathloop.tools.docker.subprocess.run", time_out)

    with pytest.raises(SandboxFailure, match="timed out"):
        _runner().run_json({"operation": "factor", "value": 1681})


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
