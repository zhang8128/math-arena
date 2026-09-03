# .timeloop/driver/runner.py
"""Run one brief through `claude -p` under a hard timeout."""

from __future__ import annotations

import dataclasses
import json
import os
import signal
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from driver.brief import RESULT_SCHEMA
from driver.config import DriverConfig

USAGE_MARKERS = ("usage limit", "rate limit", "out of extra usage", "limit reached")
AUTH_MARKERS = ("not logged in", "please run /login", "authentication", "invalid api key")


@dataclasses.dataclass(frozen=True)
class RunResult:
    exit_reason: str
    exit_code: int | None
    seconds: float
    stdout: str
    stderr: str
    structured: dict[str, object] | None
    error: str | None


def build_command(config: DriverConfig, repo_root: Path) -> list[str]:
    system_prompt = repo_root / ".timeloop" / "driver" / "templates" / "system.md"
    cmd = [
        config.claude_executable, "-p",
        "--output-format", "json",
        "--json-schema", json.dumps(RESULT_SCHEMA),
        "--permission-mode", "bypassPermissions",
        "--allowedTools", *config.allowed_tools,
        "--no-session-persistence",
        "--append-system-prompt-file", str(system_prompt),
        "--strict-mcp-config", "--mcp-config", '{"mcpServers": {}}',
    ]
    if config.model:
        cmd += ["--model", config.model]
    if config.effort:
        cmd += ["--effort", config.effort]
    return cmd


def parse_output(stdout: str) -> tuple[dict[str, object] | None, str | None]:
    try:
        env = json.loads(stdout.strip().splitlines()[-1] if stdout.strip() else "")
    except (json.JSONDecodeError, IndexError):
        return (None, "stdout is not JSON")
    if not isinstance(env, dict):
        return (None, "stdout is not a JSON object")
    text = str(env.get("result", "")).lower()
    if env.get("is_error"):
        if any(m in text for m in USAGE_MARKERS):
            return (None, "usage_limit")
        if any(m in text for m in AUTH_MARKERS):
            return (None, "auth")
        return (None, f"claude error: {text[:200]}")
    structured = env.get("structured_output")
    if not isinstance(structured, dict):
        return (None, "no structured_output")
    return (structured, None)


def _kill_group(proc: subprocess.Popen[str]) -> None:
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=10)
            return
        except subprocess.TimeoutExpired:
            continue


def run_turn(
    brief_text: str,
    config: DriverConfig,
    repo_root: Path,
    timeout: int,
    interrupt: Callable[[], bool] | None = None,
) -> RunResult:
    started = time.monotonic()
    try:
        proc = subprocess.Popen(
            build_command(config, repo_root),
            cwd=repo_root,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
    except (FileNotFoundError, PermissionError) as e:
        return RunResult("nonzero_exit", None, 0.0, "", str(e), None, "missing_executable")
    reason = "completed"
    pending_input: str | None = brief_text
    while True:
        try:
            out, err = proc.communicate(input=pending_input, timeout=1)
            break
        except subprocess.TimeoutExpired:
            pending_input = None
            if interrupt is not None and interrupt():
                reason = "interrupted"
            elif time.monotonic() - started > timeout:
                reason = "timeout"
            else:
                continue
            _kill_group(proc)
            # A Bash tool call inside the turn can start a detached (setsid)
            # grandchild that escapes the killed process group and holds the
            # inherited stdout/stderr pipes open. Without a timeout here this
            # drain can block forever, silently stopping an unattended run.
            try:
                out, err = proc.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                out, err = "", ""
            break
    seconds = round(time.monotonic() - started, 3)
    if reason != "completed":
        return RunResult(reason, proc.returncode, seconds, out, err, None, None)
    if proc.returncode != 0:
        return RunResult("nonzero_exit", proc.returncode, seconds, out, err, None, None)
    structured, error = parse_output(out)
    if structured is None:
        exit_reason = "completed" if error in ("usage_limit", "auth") else "schema"
        return RunResult(exit_reason, proc.returncode, seconds, out, err, None, error)
    return RunResult("completed", proc.returncode, seconds, out, err, structured, None)
