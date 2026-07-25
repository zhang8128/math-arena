from collections.abc import Iterator

import pytest
from testcontainers.postgres import PostgresContainer
from typer.testing import CliRunner

from mathloop.storage.db import Database
from mathloop.storage.repository import Repository


@pytest.fixture(scope="session")
def database() -> Iterator[Database]:
    postgres = PostgresContainer("postgres:17-alpine")
    postgres.start()
    database_url = postgres.get_connection_url().replace("+psycopg2", "")
    db = Database(database_url)
    db.initialize()
    try:
        yield db
    finally:
        db.close()
        postgres.stop()


@pytest.fixture
def repository(database: Database) -> Iterator[Repository]:
    with database.transaction() as connection:
        connection.execute(
            "TRUNCATE events, problems, methods, experiments, artifacts, claims, evaluations, "
            "method_scores, completeness_progress, budget_reservations, problem_source_versions, "
            "codex_turn_events, codex_turns "
            "RESTART IDENTITY CASCADE"
        )
    yield Repository(database)


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()
