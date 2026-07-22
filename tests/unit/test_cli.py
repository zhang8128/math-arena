from typer.testing import CliRunner

from mathloop.cli import app


def test_cli_help_is_available() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "mathloop" in result.output.lower()
