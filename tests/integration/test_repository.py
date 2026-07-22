import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier
from typing import cast
from uuid import UUID, uuid4

import pytest

from mathloop.domain import (
    CandidateClaim,
    ClaimStatus,
    ClaimType,
    EvidenceLevel,
    Experiment,
    ExperimentStatus,
    MethodVersion,
    Problem,
    ProblemStatus,
    Verification,
)
from mathloop.sources.jsonl import JsonlProblemSource, ingest_source
from mathloop.storage.repository import (
    ClaimNotFoundError,
    ClaimSnapshotConflictError,
    ClaimStateConflictError,
    EventConflictError,
    InvalidIdentifierError,
    ProblemNotFoundError,
    ProjectionConflictError,
    Repository,
)
from mathloop.verification import IntegerWitnessVerifier, VerificationService
from mathloop.verifiers.calibration import build_verifier_registry


def _problem(*, version: int = 1, source_id: str = "calibration/euler-prime") -> Problem:
    return Problem(
        id=uuid4(),
        source_id=source_id,
        source_uri="local://calibration",
        source_hash=uuid4().hex * 2,
        statement="n^2+n+41 is always prime",
        normalized_statement="forall n>=0, prime(n^2+n+41)",
        domain="number_theory",
        features={"finite_witness": True},
        checker={"kind": "integer_predicate", "predicate_id": "euler_prime", "start": 0},
        status=ProblemStatus.ELIGIBLE,
        cohort="development",
        version=version,
        created_at=datetime.now(UTC),
    )


def _claim(problem_id: UUID, **updates: object) -> CandidateClaim:
    claim = CandidateClaim(
        id=uuid4(),
        problem_id=problem_id,
        experiment_id=uuid4(),
        claim_type=ClaimType.DISPROOF,
        statement="n=40 is a counterexample",
        witness={"n": 40, "value": 1681},
        status=ClaimStatus.CANDIDATE,
        evidence_level=EvidenceLevel.LEAD,
        created_at=datetime.now(UTC),
    )
    return claim.model_copy(update=updates)


def _verification(*, version: str = "canonical-1", accepted: bool = True) -> Verification:
    return Verification(
        verifier="integer-predicate",
        verifier_version=version,
        accepted=accepted,
        independent=True,
        details={"n": 40, "computed_value": 1681, "predicate_holds": False},
    )


def test_add_problem_is_idempotent(repository: Repository) -> None:
    problem = _problem()
    first = repository.add_problem(problem, idempotency_key="problem:a")
    second = repository.add_problem(problem, idempotency_key="problem:a")
    assert first == second
    assert repository.count_events("problem.discovered") == 1


def test_existing_problem_accepts_exact_projection_with_a_fresh_event_key(
    repository: Repository,
) -> None:
    problem = _problem()
    repository.add_problem(problem, idempotency_key="problem:first")

    assert repository.add_problem(problem, idempotency_key="problem:second") == problem.id
    assert repository.count_events("problem.discovered") == 2


def test_idempotency_key_rejects_mismatched_payload(repository: Repository) -> None:
    problem = _problem()
    repository.add_problem(problem, idempotency_key="problem:mismatch")

    with pytest.raises(EventConflictError, match="problem:mismatch"):
        repository.add_problem(
            problem.model_copy(update={"statement": "a contradictory statement"}),
            idempotency_key="problem:mismatch",
        )

    assert repository.count_events("problem.discovered") == 1


def test_idempotency_key_rejects_mismatched_envelope(repository: Repository) -> None:
    problem = _problem()
    repository.add_problem(problem, idempotency_key="shared-key")
    method = MethodVersion(
        id=uuid4(),
        family="baseline",
        version=1,
        spec={},
        status="active",
        created_at=datetime.now(UTC),
    )

    with pytest.raises(EventConflictError, match="shared-key"):
        repository.register_method(method, idempotency_key="shared-key")

    assert repository.count_events("method.registered") == 0


def test_problem_id_rejects_conflicting_immutable_projection(repository: Repository) -> None:
    problem = _problem()
    repository.add_problem(problem, idempotency_key="problem:first")

    with pytest.raises(ProjectionConflictError, match=str(problem.id)):
        repository.add_problem(
            problem.model_copy(update={"statement": "a contradictory statement"}),
            idempotency_key="problem:second",
        )

    assert repository.count_events("problem.discovered") == 1


def test_method_id_rejects_conflicting_immutable_projection(repository: Repository) -> None:
    method = MethodVersion(
        id=uuid4(),
        family="baseline",
        version=1,
        spec={"temperature": 0},
        status="active",
        created_at=datetime.now(UTC),
    )
    repository.register_method(method, idempotency_key="method:first")

    with pytest.raises(ProjectionConflictError, match=str(method.id)):
        repository.register_method(
            method.model_copy(update={"spec": {"temperature": 1}}),
            idempotency_key="method:second",
        )

    assert repository.count_events("method.registered") == 1


def test_experiment_id_rejects_conflicting_immutable_projection(repository: Repository) -> None:
    experiment = Experiment(
        id=uuid4(),
        problem_id=uuid4(),
        method_id=uuid4(),
        lane="completeness",
        config={"max_tokens": 100},
        seed=1,
        status=ExperimentStatus.QUEUED,
        created_at=datetime.now(UTC),
    )
    repository.enqueue(experiment, idempotency_key="experiment:first")

    with pytest.raises(ProjectionConflictError, match=str(experiment.id)):
        repository.enqueue(
            experiment.model_copy(update={"config": {"max_tokens": 200}}),
            idempotency_key="experiment:second",
        )

    assert repository.count_events("experiment.enqueued") == 1


def test_daily_budget_is_reserved_before_work(repository: Repository) -> None:
    assert repository.reserve_daily_budget(uuid4(), 0.8, daily_limit_usd=1.0) is True
    assert repository.reserve_daily_budget(uuid4(), 0.3, daily_limit_usd=1.0) is False


def test_existing_budget_reservation_rejects_mismatched_replay(
    repository: Repository,
) -> None:
    experiment_id = uuid4()
    assert repository.reserve_daily_budget(experiment_id, 0.5, daily_limit_usd=1.0)

    with pytest.raises(EventConflictError, match="budget:reserve"):
        repository.reserve_daily_budget(experiment_id, 0.4, daily_limit_usd=1.0)


def test_concurrent_daily_budget_reservations_do_not_exceed_limit(
    repository: Repository,
) -> None:
    barrier = Barrier(2)

    def reserve() -> bool:
        barrier.wait()
        return repository.reserve_daily_budget(uuid4(), 0.6, daily_limit_usd=1.0)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: reserve(), range(2)))

    assert sorted(results) == [False, True]


def test_budget_settlement_rejects_overrun_and_negative_amounts(
    repository: Repository,
) -> None:
    experiment_id = uuid4()
    assert repository.reserve_daily_budget(experiment_id, 0.8, daily_limit_usd=1.0)

    with pytest.raises(ValueError, match="reserved maximum"):
        repository.settle_budget(experiment_id, 0.81)
    with pytest.raises(ValueError, match="non-negative"):
        repository.settle_budget(experiment_id, -0.1)

    assert repository.count_events("budget.settled") == 0


def test_concurrent_source_versions_are_unique_and_persistable(
    repository: Repository,
) -> None:
    workers = 6
    barrier = Barrier(workers)

    def allocate_and_persist(_: int) -> int:
        barrier.wait()
        version = repository.next_problem_version("concurrent-source")
        problem = _problem(version=version, source_id="concurrent-source")
        repository.add_problem(problem, idempotency_key=f"problem:{problem.id}")
        return version

    with ThreadPoolExecutor(max_workers=workers) as executor:
        versions = list(executor.map(allocate_and_persist, range(workers)))

    assert sorted(versions) == list(range(1, workers + 1))


def test_source_reingestion_does_not_allocate_a_version_but_changes_do(
    repository: Repository, tmp_path: Path
) -> None:
    source = tmp_path / "problems.jsonl"
    source.write_text(
        '{"source_id":"demo/one","source_uri":"https://example.test/one",'
        '"statement":"All values are prime","normalized_statement":"forall n, P(n)",'
        '"domain":"number_theory","features":{"finite_witness":true},'
        '"checker":{"kind":"integer_predicate","predicate_id":"euler_prime"}}\n'
    )

    first = ingest_source(JsonlProblemSource(source), repository)
    identical = ingest_source(JsonlProblemSource(source), repository)
    source.write_text(
        '{"source_id":"demo/one","source_uri":"https://example.test/one",'
        '"statement":"All nonnegative values are prime",'
        '"normalized_statement":"forall n, P(n)","domain":"number_theory",'
        '"features":{"finite_witness":true},'
        '"checker":{"kind":"integer_predicate","predicate_id":"euler_prime"}}\n'
    )
    changed = ingest_source(JsonlProblemSource(source), repository)

    assert identical == first
    assert changed != first
    assert repository.count_events("problem.discovered") == 2
    assert repository.next_problem_version("demo/one") == 3


def test_concurrent_duplicate_ingestion_is_one_transactional_snapshot(
    repository: Repository, tmp_path: Path
) -> None:
    workers = 6
    barrier = Barrier(workers)
    source = tmp_path / "problems.jsonl"
    source.write_text(
        '{"source_id":"demo/concurrent","source_uri":"https://example.test/concurrent",'
        '"statement":"All values are prime","normalized_statement":"forall n, P(n)",'
        '"domain":"number_theory","features":{"finite_witness":true},'
        '"checker":{"kind":"integer_predicate","predicate_id":"euler_prime"}}\n'
    )

    def ingest(_: int) -> UUID:
        barrier.wait()
        return ingest_source(JsonlProblemSource(source), repository)[0]

    with ThreadPoolExecutor(max_workers=workers) as executor:
        ids = list(executor.map(ingest, range(workers)))

    with repository.database.transaction() as connection:
        versions = connection.execute(
            "SELECT version FROM problems WHERE source_id = 'demo/concurrent'"
        ).fetchall()
        allocator = connection.execute(
            "SELECT next_version FROM problem_source_versions "
            "WHERE source_id = 'demo/concurrent'"
        ).fetchone()

    assert len(set(ids)) == 1
    assert versions == [(1,)]
    assert allocator == (2,)
    assert repository.count_events("problem.discovered") == 1


def test_concurrent_changed_snapshots_receive_contiguous_source_versions(
    repository: Repository, tmp_path: Path
) -> None:
    workers = 6
    barrier = Barrier(workers)
    sources: list[Path] = []
    for index in range(workers):
        source = tmp_path / f"problems-{index}.jsonl"
        source.write_text(
            json.dumps(
                {
                    "source_id": "demo/changing",
                    "source_uri": "https://example.test/changing",
                    "statement": f"Snapshot {index}",
                    "normalized_statement": f"snapshot({index})",
                    "domain": "number_theory",
                    "features": {"finite_witness": True},
                    "checker": {
                        "kind": "integer_predicate",
                        "predicate_id": "euler_prime",
                    },
                }
            )
            + "\n"
        )
        sources.append(source)

    def ingest(source: Path) -> UUID:
        barrier.wait()
        return ingest_source(JsonlProblemSource(source), repository)[0]

    with ThreadPoolExecutor(max_workers=workers) as executor:
        ids = list(executor.map(ingest, sources))

    with repository.database.transaction() as connection:
        versions = connection.execute(
            "SELECT version FROM problems WHERE source_id = 'demo/changing' ORDER BY version"
        ).fetchall()

    assert len(set(ids)) == workers
    assert [row[0] for row in versions] == list(range(1, workers + 1))
    assert repository.count_events("problem.discovered") == workers


def test_source_cohort_is_stable_across_changed_snapshots(
    repository: Repository, tmp_path: Path
) -> None:
    source_id = "demo/stable-cohort"
    source = tmp_path / "problems.jsonl"
    base = {
        "source_id": source_id,
        "source_uri": "https://example.test/stable-cohort",
        "statement": "Snapshot one",
        "normalized_statement": "snapshot(1)",
        "domain": "number_theory",
        "features": {"finite_witness": True},
        "checker": {"kind": "integer_predicate", "predicate_id": "euler_prime"},
    }
    source.write_text(json.dumps(base) + "\n")
    ingest_source(JsonlProblemSource(source), repository)
    source.write_text(json.dumps({**base, "statement": "Snapshot two"}) + "\n")
    ingest_source(JsonlProblemSource(source), repository)

    with repository.database.transaction() as connection:
        cohorts = connection.execute(
            "SELECT DISTINCT cohort FROM problems WHERE source_id = %(source_id)s",
            {"source_id": source_id},
        ).fetchall()

    expected = "holdout" if hashlib.sha256(source_id.encode()).digest()[0] < 51 else "development"
    assert cohorts == [(expected,)]


@pytest.mark.parametrize(
    ("persisted_status", "accepted"),
    [
        (ClaimStatus.MACHINE_VERIFIED, False),
        (ClaimStatus.REJECTED, True),
    ],
)
def test_verification_cannot_overwrite_stale_non_candidate_projection(
    repository: Repository, persisted_status: ClaimStatus, accepted: bool
) -> None:
    claim = CandidateClaim(
        id=uuid4(),
        problem_id=uuid4(),
        experiment_id=uuid4(),
        claim_type=ClaimType.DISPROOF,
        statement="candidate snapshot",
        witness={"n": 40, "value": 1681},
        status=ClaimStatus.CANDIDATE,
        evidence_level=EvidenceLevel.LEAD,
        created_at=datetime.now(UTC),
    )
    repository.save_candidate(claim)
    with repository.database.transaction() as connection:
        connection.execute(
            "UPDATE claims SET status = %(status)s WHERE id = %(id)s",
            {"id": claim.id, "status": persisted_status.value},
        )
    verification = Verification(
        verifier="integer-predicate",
        verifier_version="stale-state-test",
        accepted=accepted,
        independent=True,
        details={"n": 40},
    )

    with pytest.raises(ClaimStateConflictError, match=str(claim.id)):
        repository.record_verification(claim, verification)

    with repository.database.transaction() as connection:
        stored_status = connection.execute(
            "SELECT status FROM claims WHERE id = %(id)s", {"id": claim.id}
        ).fetchone()
        evaluations = connection.execute(
            "SELECT count(*) FROM evaluations WHERE claim_id = %(id)s", {"id": claim.id}
        ).fetchone()
    assert stored_status == (persisted_status.value,)
    assert evaluations == (0,)
    assert repository.count_events("claim.verified") == 0


def test_repository_reads_canonical_problem_and_claim(repository: Repository) -> None:
    problem = _problem()
    claim = _claim(problem.id)
    repository.add_problem(problem, idempotency_key=f"problem:{problem.id}")
    repository.save_candidate(claim)

    assert repository.get_problem(problem.id) == problem
    assert repository.get_claim(claim.id) == claim


def test_missing_canonical_rows_raise_typed_errors(repository: Repository) -> None:
    missing_problem_id = uuid4()
    missing_claim_id = uuid4()

    with pytest.raises(ProblemNotFoundError, match=str(missing_problem_id)):
        repository.get_problem(missing_problem_id)
    with pytest.raises(ClaimNotFoundError, match=str(missing_claim_id)):
        repository.get_claim(missing_claim_id)
    with pytest.raises(ClaimNotFoundError, match=str(missing_claim_id)):
        VerificationService(
            repository, IntegerWitnessVerifier(build_verifier_registry())
        ).evaluate(missing_claim_id)

    assert repository.count_events("claim.verified") == 0


def test_service_rejects_problem_object_input_and_loads_canonical_problem(
    repository: Repository,
) -> None:
    problem = _problem()
    forged_problem = problem.model_copy(
        update={
            "checker": {
                "kind": "integer_predicate",
                "predicate_id": "sum_odds",
                "start": 0,
            }
        }
    )
    claim = _claim(problem.id)
    repository.add_problem(problem, idempotency_key=f"problem:{problem.id}")
    repository.save_candidate(claim)
    service = VerificationService(
        repository, IntegerWitnessVerifier(build_verifier_registry())
    )

    with pytest.raises(InvalidIdentifierError, match="claim_id"):
        service.evaluate(cast(UUID, forged_problem))

    assert repository.count_events("claim.verified") == 0
    promoted = service.evaluate(claim.id)
    assert promoted.status is ClaimStatus.MACHINE_VERIFIED
    assert promoted.problem_id == problem.id
    assert repository.count_events("claim.verified") == 1


def test_service_requires_canonical_problem_row(repository: Repository) -> None:
    claim = _claim(uuid4())
    repository.save_candidate(claim)

    with pytest.raises(ProblemNotFoundError, match=str(claim.problem_id)):
        VerificationService(
            repository, IntegerWitnessVerifier(build_verifier_registry())
        ).evaluate(claim.id)

    assert repository.get_claim(claim.id) == claim
    assert repository.count_events("claim.verified") == 0


@pytest.mark.parametrize(
    "updates",
    [
        {"witness": {"n": 40, "value": 1}},
        {"statement": "forged statement"},
        {"problem_id": uuid4()},
    ],
)
def test_record_verification_rejects_forged_same_id_claim_snapshot(
    repository: Repository, updates: dict[str, object]
) -> None:
    claim = _claim(uuid4())
    repository.save_candidate(claim)
    forged = claim.model_copy(update=updates)

    with pytest.raises(ClaimSnapshotConflictError, match=str(claim.id)):
        repository.record_verification(forged, _verification())

    assert repository.get_claim(claim.id) == claim
    assert repository.count_events("claim.verified") == 0
    with repository.database.transaction() as connection:
        evaluations = connection.execute(
            "SELECT count(*) FROM evaluations WHERE claim_id = %(id)s", {"id": claim.id}
        ).fetchone()
    assert evaluations == (0,)


def test_exact_replay_rejects_altered_caller_snapshot_before_event_lookup(
    repository: Repository,
) -> None:
    claim = _claim(uuid4())
    verification = _verification()
    repository.save_candidate(claim)
    canonical_result = repository.record_verification(claim, verification)
    forged = claim.model_copy(update={"statement": "altered replay"})

    with pytest.raises(ClaimSnapshotConflictError, match=str(claim.id)):
        repository.record_verification(forged, verification)

    assert repository.get_claim(claim.id) == canonical_result
    assert repository.count_events("claim.verified") == 1
    with repository.database.transaction() as connection:
        evaluations = connection.execute(
            "SELECT count(*) FROM evaluations WHERE claim_id = %(id)s", {"id": claim.id}
        ).fetchone()
    assert evaluations == (1,)


def test_exact_verification_replay_returns_canonical_persisted_projection(
    repository: Repository,
) -> None:
    claim = _claim(uuid4())
    verification = _verification()
    repository.save_candidate(claim)

    first = repository.record_verification(claim, verification)
    replay = repository.record_verification(claim, verification)
    canonical = repository.get_claim(claim.id)

    assert first == canonical
    assert replay == canonical
    assert replay is not claim
    assert canonical.status is ClaimStatus.MACHINE_VERIFIED
    assert repository.count_events("claim.verified") == 1
    with repository.database.transaction() as connection:
        evaluations = connection.execute(
            "SELECT count(*) FROM evaluations WHERE claim_id = %(id)s", {"id": claim.id}
        ).fetchone()
    assert evaluations == (1,)


def test_exact_accepted_replay_preserves_later_canonical_claim_state(
    repository: Repository,
) -> None:
    claim = _claim(uuid4())
    verification = _verification()
    repository.save_candidate(claim)
    repository.record_verification(claim, verification)
    with repository.database.transaction() as connection:
        connection.execute(
            "UPDATE claims SET status = 'novelty_checked' WHERE id = %(id)s",
            {"id": claim.id},
        )

    replay = repository.record_verification(claim, verification)

    assert replay == repository.get_claim(claim.id)
    assert replay.status is ClaimStatus.NOVELTY_CHECKED
    assert repository.count_events("claim.verified") == 1
    with repository.database.transaction() as connection:
        evaluations = connection.execute(
            "SELECT count(*) FROM evaluations WHERE claim_id = %(id)s", {"id": claim.id}
        ).fetchone()
    assert evaluations == (1,)


def test_new_verifier_version_against_non_candidate_rolls_back(
    repository: Repository,
) -> None:
    claim = _claim(uuid4())
    repository.save_candidate(claim)
    canonical_result = repository.record_verification(claim, _verification(version="v1"))

    with pytest.raises(ClaimStateConflictError, match=str(claim.id)):
        repository.record_verification(claim, _verification(version="v2", accepted=False))

    assert repository.get_claim(claim.id) == canonical_result
    assert repository.count_events("claim.verified") == 1
    with repository.database.transaction() as connection:
        evaluations = connection.execute(
            "SELECT count(*) FROM evaluations WHERE claim_id = %(id)s", {"id": claim.id}
        ).fetchone()
    assert evaluations == (1,)


def test_record_verification_requires_canonical_claim_row(repository: Repository) -> None:
    claim = _claim(uuid4())

    with pytest.raises(ClaimNotFoundError, match=str(claim.id)):
        repository.record_verification(claim, _verification())

    assert repository.count_events("claim.verified") == 0
