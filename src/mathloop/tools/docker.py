"""Constrained JSON-over-stdin Docker execution."""

import json
import subprocess
from dataclasses import dataclass

ALLOWED_SANDBOX_IMAGES = frozenset({"mathloop-sage:10.9"})


class SandboxFailure(RuntimeError):
    """A sandbox process failed to return a successful JSON response."""


@dataclass(frozen=True)
class DockerLimits:
    seconds: int
    memory_mb: int
    cpus: float


@dataclass(frozen=True)
class DockerRunner:
    image: str
    limits: DockerLimits

    def __post_init__(self) -> None:
        if self.image not in ALLOWED_SANDBOX_IMAGES:
            raise ValueError(f"sandbox image is not allowlisted: {self.image}")

    def run_json(self, payload: dict[str, object]) -> dict[str, object]:
        command = [
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
            f"{self.limits.memory_mb}m",
            "--cpus",
            str(self.limits.cpus),
            "--pids-limit",
            "64",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
            self.image,
        ]
        try:
            completed = subprocess.run(
                command,
                input=json.dumps(payload, sort_keys=True).encode(),
                capture_output=True,
                check=False,
                timeout=self.limits.seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise SandboxFailure(
                f"sandbox timed out after {self.limits.seconds} seconds"
            ) from exc

        if completed.returncode != 0:
            stderr = completed.stderr.decode(errors="replace").strip()
            detail = f": {stderr}" if stderr else ""
            raise SandboxFailure(f"sandbox exited with exit code {completed.returncode}{detail}")

        try:
            decoded: object = json.loads(completed.stdout)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise SandboxFailure("sandbox returned invalid JSON") from exc
        if not isinstance(decoded, dict) or not all(isinstance(key, str) for key in decoded):
            raise SandboxFailure("sandbox returned invalid JSON object")

        response: dict[str, object] = dict(decoded)
        if response.get("ok") is False:
            raise SandboxFailure(str(response.get("error", "sandbox reported failure")))
        return response
