from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from psycopg import Connection
from psycopg_pool import ConnectionPool


class Database:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.pool = ConnectionPool(database_url, min_size=1, max_size=8, open=True)

    @contextmanager
    def transaction(self) -> Iterator[Connection[tuple[Any, ...]]]:
        with self.pool.connection() as connection, connection.transaction():
            yield connection

    def initialize(self) -> None:
        schema = Path(__file__).with_name("schema.sql").read_text()
        with self.transaction() as connection:
            connection.execute(schema)

    def close(self) -> None:
        self.pool.close()
