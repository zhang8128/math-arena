# .timeloop/tests/test_driver_runner.py
from __future__ import annotations

import json
import sys
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
