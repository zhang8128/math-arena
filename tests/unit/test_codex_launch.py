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
