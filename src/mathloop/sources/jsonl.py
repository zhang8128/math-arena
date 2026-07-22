import hashlib
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from mathloop.domain import Problem, ProblemCandidate, ProblemStatus
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
                    record = json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(f"invalid JSON on line {line_number}") from error
                if not isinstance(record, dict):
                    raise ValueError(f"JSONL record on line {line_number} must be an object")
                canonical = json.dumps(record, sort_keys=True, separators=(",", ":"))
                yield ProblemCandidate(
                    **record,
                    source_hash=hashlib.sha256(canonical.encode()).hexdigest(),
                )


def ingest_source(source: ProblemSource, repository: Repository) -> list[UUID]:
    inserted: list[UUID] = []
    for candidate in source.read():
        existing = repository.find_problem_by_source_hash(candidate.source_hash)
        if existing is not None:
            inserted.append(existing)
            continue
        cohort_byte = hashlib.sha256(candidate.source_id.encode()).digest()[0]
        problem = Problem(
            id=uuid5(NAMESPACE_URL, f"{candidate.source_id}:{candidate.source_hash}"),
            **candidate.model_dump(exclude={"expected"}),
            status=ProblemStatus.ELIGIBLE,
            cohort="holdout" if cohort_byte < 51 else "development",
            version=repository.next_problem_version(candidate.source_id),
            created_at=datetime.now(UTC),
        )
        inserted.append(
            repository.add_problem(problem, idempotency_key=f"problem:{candidate.source_hash}")
        )
    return inserted
