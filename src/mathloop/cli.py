"""Command-line interface for Mathloop."""

import typer

app = typer.Typer(help="Mathloop autonomous mathematics solver ecology.")


@app.callback()
def main() -> None:
    """Run Mathloop commands."""
