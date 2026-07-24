"""Fail-closed launch policy for the Codex CLI.

`CodexLaunchPolicy` is the single place that decides how `codex exec` is
invoked: the exact, ordered argument vector and the allowlisted child
environment. Nothing here reads a subprocess or touches the filesystem --
it only builds values for a caller (the future `CodexClient`) to execute.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

# The only environment variables ever forwarded to the Codex child process.
# CODEX_HOME is listed here for documentation purposes only -- its value is
# always taken from `CodexLaunchPolicy.codex_home`, never from `source`.
_ALLOWED_ENVIRONMENT_KEYS = frozenset(
    {
        "PATH",
        "CODEX_HOME",
        "TMPDIR",
        "LANG",
        "LC_ALL",
        "CODEX_CA_CERTIFICATE",
        "SSL_CERT_FILE",
    }
)


@dataclass(frozen=True)
class CodexLaunchPolicy:
    """Builds the exact `codex exec` command and its allowlisted environment."""

    codex_binary: Path
    codex_home: Path

    def command(
        self,
        model: str,
        worktree: Path,
        schema: Path,
        prompt: str,
        web_search: Literal["disabled", "live"] = "disabled",
        sandbox: Literal["workspace-write", "read-only"] = "workspace-write",
    ) -> tuple[str, ...]:
        return (
            str(self.codex_binary),
            "exec",
            "--ephemeral",
            "--json",
            "--output-schema",
            str(schema),
            "--sandbox",
            sandbox,
            "--ignore-user-config",
            "--ignore-rules",
            "--model",
            model,
            "--cd",
            str(worktree),
            "--config",
            f'web_search="{web_search}"',
            "--config",
            "sandbox_workspace_write.network_access=false",
            prompt,
        )

    def environment(self, source: Mapping[str, str]) -> dict[str, str]:
        # CODEX_HOME is deliberately excluded from the comprehension below
        # even though it is allowlisted: it must come from trusted settings,
        # never from whatever the source environment happens to contain.
        environment = {
            key: value
            for key, value in source.items()
            if key in _ALLOWED_ENVIRONMENT_KEYS and key != "CODEX_HOME"
        }
        environment["CODEX_HOME"] = str(self.codex_home)
        return environment
