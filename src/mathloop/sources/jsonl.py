import hashlib
import json
import math
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import ValidationError

from mathloop.domain import ProblemCandidate
from mathloop.sources.base import ProblemSource
from mathloop.storage.repository import Repository


class JsonlProblemSource(ProblemSource):
    def __init__(self, path: Path) -> None:
        self.path = path

    def read(self) -> Iterator[ProblemCandidate]:
        with self.path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(
                        line,
                        parse_constant=_reject_non_finite,
                        parse_float=_parse_finite_float,
                    )
                except json.JSONDecodeError as error:
                    raise ValueError(
                        f"{self.path}:{line_number}: invalid JSON: {error.msg}"
                    ) from error
                except ValueError as error:
                    raise ValueError(
                        f"{self.path}:{line_number}: invalid JSON: {error}"
                    ) from error
                if not isinstance(record, dict):
                    raise ValueError(
                        f"{self.path}:{line_number}: invalid problem record: expected an object"
                    )
                canonical = json.dumps(
                    record, sort_keys=True, separators=(",", ":"), allow_nan=False
                )
                try:
                    yield ProblemCandidate(
                        **record,
                        source_hash=hashlib.sha256(canonical.encode()).hexdigest(),
                    )
                except ValidationError as error:
                    raise ValueError(
                        f"{self.path}:{line_number}: invalid problem record: {error}"
                    ) from error


def _reject_non_finite(value: str) -> NoReturn:
    raise ValueError(f"non-finite JSON number {value}")


def _parse_finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite JSON number {value}")
    return parsed


def ingest_source(source: ProblemSource, repository: Repository) -> list[UUID]:
    inserted: list[UUID] = []
    for candidate in source.read():
        cohort_byte = hashlib.sha256(candidate.source_id.encode()).digest()[0]
        inserted.append(
            repository.ingest_problem_snapshot(
                candidate,
                problem_id=uuid5(
                    NAMESPACE_URL, f"{candidate.source_id}:{candidate.source_hash}"
                ),
                cohort="holdout" if cohort_byte < 51 else "development",
                created_at=datetime.now(UTC),
            )
        )
    return inserted
