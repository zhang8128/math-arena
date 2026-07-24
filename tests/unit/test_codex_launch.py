from pathlib import Path

from mathloop.codex.launch import CodexLaunchPolicy


def test_launch_is_ephemeral_structured_and_offline(tmp_path: Path) -> None:
    policy = CodexLaunchPolicy(
        codex_binary=Path("/opt/codex"),
        codex_home=Path("/safe/codex-home"),
    )
    command = policy.command(
        model="gpt-5.6-terra",
        worktree=tmp_path,
        schema=tmp_path / "schema.json",
        prompt="Solve the normalized problem.",
    )
    assert command[:2] == ("/opt/codex", "exec")
    assert "--ephemeral" in command
    assert "--json" in command
    assert "--output-schema" in command
    assert "--ignore-user-config" in command
    assert "--ignore-rules" in command
    assert "sandbox_workspace_write.network_access=false" in " ".join(command)


def test_launch_supports_read_only_review_sandbox(tmp_path: Path) -> None:
    command = CodexLaunchPolicy(
        codex_binary=Path("/opt/codex"),
        codex_home=Path("/safe/codex-home"),
    ).command(
        model="gpt-5.6-sol",
        worktree=tmp_path,
        schema=tmp_path / "schema.json",
        prompt="Review the exact patch.",
        sandbox="read-only",
    )
    sandbox_index = command.index("--sandbox")
    assert command[sandbox_index + 1] == "read-only"
    assert "workspace-write" not in command


def test_command_matches_the_full_ordered_argv_shape(tmp_path: Path) -> None:
    schema = tmp_path / "schema.json"
    command = CodexLaunchPolicy(
        codex_binary=Path("/opt/codex"),
        codex_home=Path("/safe/codex-home"),
    ).command(
        model="gpt-5.6-terra",
        worktree=tmp_path,
        schema=schema,
        prompt="Solve the normalized problem.",
    )
    assert command == (
        "/opt/codex",
        "exec",
        "--ephemeral",
        "--json",
        "--output-schema",
        str(schema),
        "--sandbox",
        "workspace-write",
        "--ignore-user-config",
        "--ignore-rules",
        "--model",
        "gpt-5.6-terra",
        "--cd",
        str(tmp_path),
        "--config",
        'web_search="disabled"',
        "--config",
        "sandbox_workspace_write.network_access=false",
        "Solve the normalized problem.",
    )


def test_command_web_search_live_changes_only_the_web_search_config(tmp_path: Path) -> None:
    schema = tmp_path / "schema.json"
    command = CodexLaunchPolicy(
        codex_binary=Path("/opt/codex"),
        codex_home=Path("/safe/codex-home"),
    ).command(
        model="gpt-5.6-luna",
        worktree=tmp_path,
        schema=schema,
        prompt="Find candidate sources.",
        web_search="live",
    )
    assert 'web_search="live"' in command
    assert 'web_search="disabled"' not in command
    assert "sandbox_workspace_write.network_access=false" in command


def test_environment_drops_repository_and_provider_secrets() -> None:
    env = CodexLaunchPolicy(
        codex_binary=Path("/opt/codex"),
        codex_home=Path("/safe/codex-home"),
    ).environment(
        {
            "PATH": "/bin",
            "HOME": "/Users/test",
            "CODEX_HOME": "/Users/test/.codex",
            "OPENAI_API_KEY": "secret",
            "DATABASE_URL": "secret",
            "DOCKER_HOST": "secret",
        }
    )
    assert env["CODEX_HOME"] == "/safe/codex-home"
    assert "OPENAI_API_KEY" not in env
    assert "DATABASE_URL" not in env
    assert "DOCKER_HOST" not in env
