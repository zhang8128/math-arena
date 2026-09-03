# .timeloop/tests/test_driver_runner.py
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

TIMELOOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TIMELOOP))

from driver.config import DriverConfig  # noqa: E402
from driver.runner import build_command, parse_output, run_turn  # noqa: E402

FAKE = str(TIMELOOP / "tests" / "fixtures" / "fake_claude")


def cfg() -> DriverConfig:
    return DriverConfig(claude_executable=FAKE, model="m", effort="high")


def test_build_command_matches_spec(tmp_path: Path) -> None:
    cmd = build_command(cfg(), tmp_path)
    assert cmd[0] == FAKE and cmd[1] == "-p"
    assert "--bare" not in cmd
    for flag in (
        "--output-format", "--json-schema", "--permission-mode", "--allowedTools",
        "--no-session-persistence", "--append-system-prompt-file",
        "--strict-mcp-config", "--mcp-config", "--model", "--effort",
    ):
        assert flag in cmd
    assert cmd[cmd.index("--mcp-config") + 1] == '{"mcpServers": {}}'
    assert cmd[cmd.index("--permission-mode") + 1] == "bypassPermissions"
    assert cmd[cmd.index("--output-format") + 1] == "json"


def test_parse_output_variants() -> None:
    good = json.dumps(
        {"is_error": False, "structured_output": {"outcome": "nothing"}, "result": ""}
    )
    assert parse_output(good) == ({"outcome": "nothing"}, None)
    assert parse_output("not json") == (None, "stdout is not JSON")
    usage = json.dumps(
        {"is_error": True, "result": "Claude usage limit reached", "structured_output": None}
    )
    assert parse_output(usage) == (None, "usage_limit")
    auth = json.dumps(
        {"is_error": True, "result": "Not logged in · Please run /login", "structured_output": None}
    )
    assert parse_output(auth) == (None, "auth")
    noschema = json.dumps({"is_error": False, "result": "x", "structured_output": None})
    assert parse_output(noschema) == (None, "no structured_output")


@pytest.mark.parametrize(("mode", "reason", "error"), [
    ("ok", "completed", None),
    ("nonzero", "nonzero_exit", None),
    ("usage", "completed", "usage_limit"),
    ("noschema", "schema", "no structured_output"),
])
def test_run_turn_modes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, reason: str, error: str | None
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", mode)
    r = run_turn("brief", cfg(), tmp_path, timeout=20)
    assert r.exit_reason == reason and r.error == error
    if mode == "ok":
        assert r.structured == {
            "outcome": "nothing", "refinement": False, "ledger_line": None,
            "files_changed": [], "frames_filed": [], "next_action": None, "notes": "fake",
        }


def test_run_turn_timeout_kills_child(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "sleep")
    r = run_turn("brief", cfg(), tmp_path, timeout=2)
    assert r.exit_reason == "timeout" and r.seconds < 10


def test_run_turn_interrupt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "sleep")
    r = run_turn("brief", cfg(), tmp_path, timeout=20, interrupt=lambda: True)
    assert r.exit_reason == "interrupted" and r.seconds < 10


def test_run_turn_missing_executable_returns_result_not_traceback(tmp_path: Path) -> None:
    """I6 regression: a missing/renamed `claude` binary must come back as a
    RunResult the loop can halt on, not a FileNotFoundError escaping run_turn."""
    bad_cfg = DriverConfig(claude_executable=str(tmp_path / "no-such-claude-binary"))
    r = run_turn("brief", bad_cfg, tmp_path, timeout=5)
    assert r.exit_reason == "nonzero_exit"
    assert r.exit_code is None
    assert r.seconds == 0.0
    assert r.structured is None
    assert r.error == "missing_executable"


def test_run_turn_post_kill_communicate_is_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """I5 regression: after SIGTERM/SIGKILL to the process group, a Bash tool
    call inside the turn can have started a detached (setsid) grandchild that
    escapes the group and keeps the inherited stdout/stderr pipes open. The
    post-kill `proc.communicate()` then blocks forever with no timeout.

    A real fake-claude mode that forks a setsid grandchild holding the pipes
    open is awkward and platform-fragile to build reliably in the test
    fixture (fork() semantics, session detachment, pipe inheritance all need
    to line up exactly), so this instead monkeypatches `Popen.communicate` to
    hang -- by raising TimeoutExpired, same as a real blocked read would
    eventually surface once bounded -- specifically on the post-kill call,
    identified by the timeout=30 that only that call passes. It proves
    run_turn still returns quickly with the graceful "", "" fallback instead
    of hanging indefinitely.
    """
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "sleep")
    real_communicate = subprocess.Popen.communicate

    def flaky_communicate(
        self: subprocess.Popen[str], input: str | None = None, timeout: float | None = None
    ) -> tuple[str, str]:
        if timeout == 30:
            raise subprocess.TimeoutExpired(cmd="fake_claude", timeout=timeout)
        return real_communicate(self, input=input, timeout=timeout)  # type: ignore[return-value]

    monkeypatch.setattr(subprocess.Popen, "communicate", flaky_communicate)
    started = time.monotonic()
    r = run_turn("brief", cfg(), tmp_path, timeout=2)
    elapsed = time.monotonic() - started
    assert r.exit_reason == "timeout"
    assert r.stdout == "" and r.stderr == ""
    assert elapsed < 40  # bounded by the post-kill guard, not left hanging
