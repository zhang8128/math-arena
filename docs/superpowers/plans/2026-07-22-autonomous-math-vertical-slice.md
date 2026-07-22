# Autonomous Mathematics Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a continuously runnable, crash-recoverable vertical slice that ingests changing conjecture sets, executes diverse bounded methods, independently verifies exact counterexamples, evolves method routing on held-out problems, and produces an auditable review queue.

**Architecture:** A Python service uses PostgreSQL as an append-only event ledger plus durable work queue, a content-addressed artifact directory for evidence, and replaceable source/method/provider/verifier plugins. Stateless workers claim bounded experiments, run exact local or sandboxed tools, and submit candidate claims to an independent verifier; a portfolio scheduler and contextual method scores evolve without granting models authority over claim promotion.

**Tech Stack:** Python 3.13, uv, Pydantic 2, psycopg 3, PostgreSQL 17, Typer, Docker, SageMath 10.9, OpenAI Responses API through the official Python SDK, pytest, Ruff, mypy.

## Global Constraints

- The canonical ledger and artifact store are authoritative; Prism and Engram are optional integrations only.
- Source statements, method versions, verifier versions, and artifacts are immutable after use.
- Only an independent verifier may promote a mathematical claim.
- Numerical evidence is never labeled a proof.
- Generated computation has explicit CPU, memory, wall-clock, filesystem, network, token, and monetary limits.
- The scheduler always reserves nonzero allocations for completeness search, novel methods/domains, and verification.
- Problem and method populations both change over time.
- Method promotion is based on rolling unseen problems under comparable budgets.
- Public release, contacting third parties, and spending-policy changes remain approval-gated.
- Use local exact tools before optional external services; Wolfram output is never the sole certificate.
- Every task follows TDD: failing test, observed failure, minimal implementation, passing test, focused commit.

## Delivery Boundaries

This plan implements the approved first autonomous vertical slice. It deliberately defers large solver swarms, distributed hosts, arbitrary generated-code execution, automatic Lean proof search, and public-release automation. Lean and live OpenConjecture ingestion receive separate implementation plans after this slice establishes trustworthy state, verification, and learning behavior.

## File Map

```text
.
├── .env.example                         # documented runtime settings, no secrets
├── .gitignore                           # runtime, credential, and artifact exclusions
├── compose.yaml                         # local PostgreSQL service
├── pyproject.toml                       # package, CLI, dependencies, test/lint settings
├── data/
│   ├── calibration/problems.jsonl       # known true/false calibration problems
│   └── incoming/.gitkeep                # continuously watched problem snapshots
├── docker/sage/
│   ├── Dockerfile                       # pinned Sage sandbox image
│   └── runner.py                        # allowlisted JSON-in/JSON-out exact operations
├── src/mathloop/
│   ├── __init__.py
│   ├── artifacts.py                     # atomic SHA-256 content store
│   ├── cli.py                           # operator commands and autonomous loop
│   ├── config.py                        # validated environment configuration
│   ├── domain.py                        # immutable domain contracts and states
│   ├── evolution.py                     # contextual scores and method mutation
│   ├── reporting.py                     # review and metrics reports
│   ├── runtime.py                       # dependency composition root
│   ├── scheduling.py                    # portfolio lanes and experiment creation
│   ├── verification.py                  # independent witness verification/promotion
│   ├── worker.py                        # lease/execute/checkpoint/commit lifecycle
│   ├── methods/
│   │   ├── base.py                      # SolverMethod protocol and registry
│   │   ├── integer_search.py            # complete bounded counterexample search
│   │   ├── proof_sketch.py              # structured model proposal method
│   │   ├── sage.py                      # Sage sandbox method
│   │   └── symbolic.py                  # exact symbolic induction certificates
│   ├── predicates/
│   │   ├── base.py                      # exact predicate protocol and registry
│   │   └── calibration.py               # independently implemented fixtures
│   ├── providers/
│   │   ├── base.py                      # provider-neutral structured model contract
│   │   └── openai.py                    # Responses API adapter and usage accounting
│   ├── sources/
│   │   ├── base.py                      # ProblemSource contract
│   │   └── jsonl.py                     # versioned local snapshot ingestion
│   ├── storage/
│   │   ├── db.py                        # connection pool and transactions
│   │   ├── repository.py                # event/projection/lease operations
│   │   └── schema.sql                   # idempotent PostgreSQL schema
│   ├── tools/
│   │   └── docker.py                    # restricted container runner
│   └── verifiers/
│       └── calibration.py               # checker implementation independent of search
├── tests/
    ├── conftest.py                      # temporary PostgreSQL and settings
    ├── e2e/test_autonomous_cycle.py     # complete counterexample lifecycle
    ├── integration/
    │   ├── test_leases.py
    │   ├── test_repository.py
    │   └── test_sage_sandbox.py
    └── unit/
        ├── test_artifacts.py
        ├── test_budget.py
        ├── test_domain.py
        ├── test_evolution.py
        ├── test_integer_search.py
        ├── test_jsonl_source.py
        ├── test_openai_provider.py
        ├── test_scheduler.py
        ├── test_symbolic.py
        └── test_verification.py
└── docs/verification/
    └── vertical-slice-acceptance.md      # captured acceptance evidence
```

---

### Task 1: Reproducible Project and Runtime Configuration

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `compose.yaml`
- Create: `src/mathloop/__init__.py`
- Create: `src/mathloop/config.py`
- Create: `tests/unit/test_config.py`

**Interfaces:**
- Consumes: none.
- Produces: `Settings`, `get_settings()`, the `mathloop` CLI entry point, and the local PostgreSQL service used by all later tasks.

- [ ] **Step 1: Write the failing configuration test**

```python
# tests/unit/test_config.py
from pathlib import Path

import pytest
from pydantic import ValidationError

from mathloop.config import Settings


def test_settings_require_positive_budgets(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql://mathloop:mathloop@localhost:55432/mathloop",
            artifact_root=tmp_path,
            daily_api_budget_usd=0,
            max_experiment_seconds=30,
            lease_seconds=60,
        )


def test_settings_create_absolute_artifact_root(tmp_path: Path) -> None:
    settings = Settings(
        database_url="postgresql://mathloop:mathloop@localhost:55432/mathloop",
        artifact_root=tmp_path / "artifacts",
        daily_api_budget_usd=5,
        max_experiment_seconds=30,
        lease_seconds=60,
    )
    assert settings.artifact_root.is_absolute()
    assert settings.lease_seconds > settings.max_experiment_seconds
```

- [ ] **Step 2: Run the test and observe the missing package failure**

Run: `uv run pytest tests/unit/test_config.py -q`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'mathloop'`.

- [ ] **Step 3: Add packaging, dependencies, runtime services, and validated settings**

```toml
# pyproject.toml
[project]
name = "mathloop"
version = "0.1.0"
description = "Persistent autonomous mathematics solver ecology"
requires-python = ">=3.13,<3.14"
dependencies = [
  "openai>=2,<3",
  "psycopg[binary,pool]>=3.2,<4",
  "pydantic>=2.11,<3",
  "pydantic-settings>=2.9,<3",
  "sympy>=1.14,<2",
  "typer>=0.16,<1",
]

[project.optional-dependencies]
dev = [
  "mypy>=1.15,<2",
  "pytest>=8.4,<9",
  "pytest-asyncio>=1,<2",
  "ruff>=0.12,<1",
  "testcontainers[postgres]>=4.10,<5",
]

[project.scripts]
mathloop = "mathloop.cli:app"

[build-system]
requires = ["hatchling>=1.27"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["integration: requires Docker", "live_api: incurs an external API call"]

[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "RUF"]

[tool.mypy]
python_version = "3.13"
strict = true
packages = ["mathloop"]
```

```python
# src/mathloop/__init__.py
"""Persistent autonomous mathematics solver ecology."""

__version__ = "0.1.0"
```

```python
# src/mathloop/config.py
from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MATHLOOP_", env_file=".env")

    database_url: str = "postgresql://mathloop:mathloop@localhost:55432/mathloop"
    artifact_root: Path = Path(".mathloop/artifacts")
    incoming_root: Path = Path("data/incoming")
    daily_api_budget_usd: float = Field(default=5.0, gt=0)
    max_experiment_seconds: int = Field(default=300, gt=0)
    lease_seconds: int = Field(default=420, gt=0)
    max_container_memory_mb: int = Field(default=1024, ge=128)
    max_container_cpus: float = Field(default=1.0, gt=0)
    openai_model_scout: str = "gpt-5.6-luna"
    openai_model_reasoner: str = "gpt-5.6-terra"
    openai_model_escalation: str = "gpt-5.6-sol"
    max_model_output_tokens: int = Field(default=4096, ge=128)
    max_api_cost_usd_per_experiment: float = Field(default=1.0, gt=0)

    @model_validator(mode="after")
    def validate_runtime(self) -> "Settings":
        self.artifact_root = self.artifact_root.expanduser().resolve()
        self.incoming_root = self.incoming_root.expanduser().resolve()
        if self.lease_seconds <= self.max_experiment_seconds:
            raise ValueError("lease_seconds must exceed max_experiment_seconds")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

```yaml
# compose.yaml
services:
  postgres:
    image: postgres:17-alpine
    environment:
      POSTGRES_DB: mathloop
      POSTGRES_USER: mathloop
      POSTGRES_PASSWORD: mathloop
    ports:
      - "55432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mathloop -d mathloop"]
      interval: 2s
      timeout: 2s
      retries: 20
    volumes:
      - mathloop-postgres:/var/lib/postgresql/data

volumes:
  mathloop-postgres:
```

```dotenv
# .env.example
MATHLOOP_DATABASE_URL=postgresql://mathloop:mathloop@localhost:55432/mathloop
MATHLOOP_ARTIFACT_ROOT=.mathloop/artifacts
MATHLOOP_INCOMING_ROOT=data/incoming
MATHLOOP_DAILY_API_BUDGET_USD=5
MATHLOOP_MAX_EXPERIMENT_SECONDS=300
MATHLOOP_LEASE_SECONDS=420
MATHLOOP_MAX_MODEL_OUTPUT_TOKENS=4096
MATHLOOP_MAX_API_COST_USD_PER_EXPERIMENT=1
# OPENAI_API_KEY is optional. Do not commit it.
```

```gitignore
# .gitignore
.env
.mathloop/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.venv/
__pycache__/
*.py[cod]
.coverage
htmlcov/
```

- [ ] **Step 4: Install Python 3.13, sync, and run quality checks**

Run: `uv python install 3.13 && uv sync --extra dev && uv run pytest tests/unit/test_config.py -q && uv run ruff check src tests && uv run mypy src`

Expected: two tests pass; Ruff and mypy report no errors.

- [ ] **Step 5: Commit the reproducible skeleton**

```bash
git add pyproject.toml uv.lock .gitignore .env.example compose.yaml src/mathloop tests/unit/test_config.py
git commit -m "chore: initialize mathloop runtime"
```

---

### Task 2: Immutable Domain Contracts and State Transitions

**Files:**
- Create: `src/mathloop/domain.py`
- Create: `tests/unit/test_domain.py`

**Interfaces:**
- Consumes: Pydantic from Task 1.
- Produces: `Problem`, `MethodVersion`, `Experiment`, `CandidateClaim`, `Verification`, status enums, and `advance_claim()` used by every later subsystem.

- [ ] **Step 1: Write tests for immutability and verifier-only promotion**

```python
# tests/unit/test_domain.py
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from mathloop.domain import (
    CandidateClaim,
    ClaimStatus,
    ClaimType,
    EvidenceLevel,
    Verification,
    advance_claim,
)


def test_claim_is_immutable() -> None:
    claim = CandidateClaim(
        id=uuid4(),
        problem_id=uuid4(),
        experiment_id=uuid4(),
        claim_type=ClaimType.DISPROOF,
        statement="n=40 is a counterexample",
        witness={"n": 40},
        status=ClaimStatus.CANDIDATE,
        evidence_level=EvidenceLevel.LEAD,
        created_at=datetime.now(UTC),
    )
    with pytest.raises(ValidationError):
        claim.status = ClaimStatus.MACHINE_VERIFIED


def test_only_accepted_independent_verification_promotes_claim() -> None:
    claim = CandidateClaim.model_validate(
        {
            "id": uuid4(), "problem_id": uuid4(), "experiment_id": uuid4(),
            "claim_type": "disproof", "statement": "counterexample", "witness": {"n": 40},
            "status": "candidate", "evidence_level": "lead", "created_at": datetime.now(UTC),
        }
    )
    rejected = Verification(
        verifier="integer-predicate", verifier_version="1", accepted=False,
        independent=True, details={"reason": "predicate held"},
    )
    assert advance_claim(claim, rejected).status is ClaimStatus.REJECTED

    accepted = rejected.model_copy(update={"accepted": True, "details": {"value": False}})
    assert advance_claim(claim, accepted).status is ClaimStatus.MACHINE_VERIFIED
```

- [ ] **Step 2: Run the tests and observe the missing module failure**

Run: `uv run pytest tests/unit/test_domain.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'mathloop.domain'`.

- [ ] **Step 3: Implement the complete domain vocabulary and transition guard**

```python
# src/mathloop/domain.py
from datetime import datetime
from enum import StrEnum
from typing import Any, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ProblemStatus(StrEnum):
    DISCOVERED = "discovered"
    NORMALIZED = "normalized"
    ELIGIBLE = "eligible"
    ACTIVE = "active"
    QUARANTINED = "quarantined"
    REVISIT_LATER = "revisit_later"


class ExperimentStatus(StrEnum):
    QUEUED = "queued"
    LEASED = "leased"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXPIRED = "expired"


class ClaimType(StrEnum):
    PROOF = "proof"
    DISPROOF = "disproof"
    CORRECTION = "correction"
    PARTIAL = "partial"


class ClaimStatus(StrEnum):
    CANDIDATE = "candidate"
    MACHINE_VERIFIED = "machine_verified"
    REJECTED = "rejected"
    NOVELTY_CHECKED = "novelty_checked"
    HUMAN_REVIEWED = "human_reviewed"


class EvidenceLevel(StrEnum):
    LEAD = "lead"
    COMPUTATIONALLY_SUPPORTED = "computationally_supported"
    REPRODUCIBLE_WITNESS = "reproducible_witness"
    FORMALLY_VERIFIED = "formally_verified"


class Problem(FrozenModel):
    id: UUID
    source_id: str
    source_uri: str
    source_hash: str
    statement: str
    normalized_statement: str
    domain: str
    features: dict[str, Any]
    checker: dict[str, Any]
    status: ProblemStatus
    cohort: str = Field(pattern="^(development|holdout)$")
    version: int = Field(ge=1)
    created_at: datetime


class ProblemCandidate(FrozenModel):
    source_id: str
    source_uri: str
    source_hash: str
    statement: str
    normalized_statement: str
    domain: str
    features: dict[str, Any]
    checker: dict[str, Any]
    expected: str | None = None


class MethodVersion(FrozenModel):
    id: UUID
    family: str
    version: int = Field(ge=1)
    spec: dict[str, Any]
    parent_id: UUID | None = None
    status: str = Field(pattern="^(candidate|active|retired|archived)$")
    created_at: datetime


class Experiment(FrozenModel):
    id: UUID
    problem_id: UUID
    method_id: UUID
    lane: str
    config: dict[str, Any]
    seed: int
    status: ExperimentStatus
    created_at: datetime


class CandidateClaim(FrozenModel):
    id: UUID
    problem_id: UUID
    experiment_id: UUID
    claim_type: ClaimType
    statement: str
    witness: dict[str, Any] | None
    status: ClaimStatus
    evidence_level: EvidenceLevel
    created_at: datetime


class Verification(FrozenModel):
    verifier: str
    verifier_version: str
    accepted: bool
    independent: bool
    details: dict[str, Any]


def advance_claim(claim: CandidateClaim, verification: Verification) -> CandidateClaim:
    if not verification.independent:
        raise ValueError("claim promotion requires an independent verifier")
    if verification.accepted:
        return claim.model_copy(
            update={
                "status": ClaimStatus.MACHINE_VERIFIED,
                "evidence_level": EvidenceLevel.REPRODUCIBLE_WITNESS,
            }
        )
    return claim.model_copy(update={"status": ClaimStatus.REJECTED})
```

- [ ] **Step 4: Run the focused and full unit suites**

Run: `uv run pytest tests/unit/test_domain.py tests/unit/test_config.py -q && uv run ruff check src tests && uv run mypy src`

Expected: four tests pass; static checks pass.

- [ ] **Step 5: Commit the domain contracts**

```bash
git add src/mathloop/domain.py tests/unit/test_domain.py
git commit -m "feat: define immutable mathloop domain"
```

---

### Task 3: PostgreSQL Event Ledger, Projections, and Durable Leases

**Files:**
- Create: `src/mathloop/storage/__init__.py`
- Create: `src/mathloop/storage/schema.sql`
- Create: `src/mathloop/storage/db.py`
- Create: `src/mathloop/storage/repository.py`
- Create: `tests/conftest.py`
- Create: `tests/integration/test_repository.py`
- Create: `tests/integration/test_leases.py`

**Interfaces:**
- Consumes: `Settings`, domain models.
- Produces: `Database`, `Repository.add_problem()`, `register_method()`, `enqueue()`, `claim_next()`, `heartbeat()`, `complete()`, `save_candidate()`, and `record_verification()`.

- [ ] **Step 1: Write integration tests for idempotent events and expired-lease recovery**

```python
# tests/integration/test_repository.py
from datetime import UTC, datetime
from uuid import uuid4

from mathloop.domain import Problem, ProblemStatus
from mathloop.storage.repository import Repository


def test_add_problem_is_idempotent(repository: Repository) -> None:
    problem = Problem(
        id=uuid4(), source_id="calibration/euler-prime", source_uri="local://calibration",
        source_hash="a" * 64, statement="n^2+n+41 is always prime",
        normalized_statement="forall n>=0, prime(n^2+n+41)", domain="number_theory",
        features={"finite_witness": True},
        checker={"kind": "integer_predicate", "predicate_id": "euler_prime"},
        status=ProblemStatus.ELIGIBLE, cohort="development", version=1,
        created_at=datetime.now(UTC),
    )
    first = repository.add_problem(problem, idempotency_key="problem:a")
    second = repository.add_problem(problem, idempotency_key="problem:a")
    assert first == second
    assert repository.count_events("problem.discovered") == 1


def test_daily_budget_is_reserved_before_work(repository: Repository) -> None:
    assert repository.reserve_daily_budget(uuid4(), 0.8, daily_limit_usd=1.0) is True
    assert repository.reserve_daily_budget(uuid4(), 0.3, daily_limit_usd=1.0) is False
```

```python
# tests/integration/test_leases.py
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from mathloop.storage.repository import Repository


def test_expired_experiment_can_be_reclaimed(repository: Repository) -> None:
    experiment_id = repository.enqueue_raw(
        problem_id=uuid4(), method_id=uuid4(), lane="completeness", config={}, seed=1
    )
    now = datetime.now(UTC)
    first = repository.claim_next("worker-a", now=now, lease_seconds=1)
    assert first is not None and first.id == experiment_id
    assert repository.claim_next("worker-b", now=now, lease_seconds=1) is None
    reclaimed = repository.claim_next("worker-b", now=now + timedelta(seconds=2), lease_seconds=30)
    assert reclaimed is not None and reclaimed.id == experiment_id
```

- [ ] **Step 2: Start PostgreSQL and observe missing storage failures**

Run: `docker compose up -d postgres && uv run pytest tests/integration/test_repository.py tests/integration/test_leases.py -q`

Expected: FAIL during collection because `mathloop.storage.repository` does not exist.

- [ ] **Step 3: Create the idempotent schema**

```sql
-- src/mathloop/storage/schema.sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS events (
    sequence BIGSERIAL PRIMARY KEY,
    event_id UUID NOT NULL DEFAULT gen_random_uuid(),
    aggregate_type TEXT NOT NULL,
    aggregate_id UUID NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS problems (
    id UUID PRIMARY KEY,
    source_id TEXT NOT NULL,
    source_uri TEXT NOT NULL,
    source_hash TEXT NOT NULL UNIQUE,
    statement TEXT NOT NULL,
    normalized_statement TEXT NOT NULL,
    domain TEXT NOT NULL,
    features JSONB NOT NULL,
    checker JSONB NOT NULL,
    status TEXT NOT NULL,
    cohort TEXT NOT NULL CHECK (cohort IN ('development', 'holdout')),
    version INTEGER NOT NULL CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS methods (
    id UUID PRIMARY KEY,
    family TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version > 0),
    spec JSONB NOT NULL,
    parent_id UUID NULL REFERENCES methods(id),
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (family, version)
);

CREATE TABLE IF NOT EXISTS experiments (
    id UUID PRIMARY KEY,
    problem_id UUID NOT NULL,
    method_id UUID NOT NULL,
    lane TEXT NOT NULL,
    config JSONB NOT NULL,
    seed BIGINT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    lease_owner TEXT NULL,
    lease_expires_at TIMESTAMPTZ NULL,
    attempt INTEGER NOT NULL DEFAULT 0,
    cost_usd NUMERIC(14, 6) NOT NULL DEFAULT 0,
    result JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (problem_id, method_id, seed)
);

CREATE INDEX IF NOT EXISTS experiments_claimable
    ON experiments (status, lease_expires_at, created_at);

CREATE TABLE IF NOT EXISTS artifacts (
    digest TEXT PRIMARY KEY,
    media_type TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    relative_path TEXT NOT NULL,
    experiment_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS claims (
    id UUID PRIMARY KEY,
    problem_id UUID NOT NULL,
    experiment_id UUID NOT NULL,
    claim_type TEXT NOT NULL,
    statement TEXT NOT NULL,
    witness JSONB NULL,
    status TEXT NOT NULL,
    evidence_level TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS evaluations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id UUID NOT NULL REFERENCES claims(id),
    verifier TEXT NOT NULL,
    verifier_version TEXT NOT NULL,
    accepted BOOLEAN NOT NULL,
    independent BOOLEAN NOT NULL,
    details JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS method_scores (
    domain TEXT NOT NULL,
    method_id UUID NOT NULL,
    cohort TEXT NOT NULL,
    trials INTEGER NOT NULL DEFAULT 0,
    reward DOUBLE PRECISION NOT NULL DEFAULT 0,
    PRIMARY KEY (domain, method_id, cohort)
);

CREATE TABLE IF NOT EXISTS budget_reservations (
    experiment_id UUID PRIMARY KEY,
    reserved_usd NUMERIC(14, 6) NOT NULL CHECK (reserved_usd >= 0),
    settled_usd NUMERIC(14, 6) NULL CHECK (settled_usd >= 0),
    budget_day DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

- [ ] **Step 4: Implement connections and transactional repository operations**

```python
# src/mathloop/storage/db.py
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from psycopg import Connection
from psycopg_pool import ConnectionPool


class Database:
    def __init__(self, database_url: str) -> None:
        self.pool = ConnectionPool(database_url, min_size=1, max_size=8, open=True)

    @contextmanager
    def transaction(self) -> Iterator[Connection[object]]:
        with self.pool.connection() as connection, connection.transaction():
            yield connection

    def initialize(self) -> None:
        schema = Path(__file__).with_name("schema.sql").read_text()
        with self.transaction() as connection:
            connection.execute(schema)

    def close(self) -> None:
        self.pool.close()
```

Implement `src/mathloop/storage/repository.py` with one private `_append_event()` helper. Each public mutation performs its projection write and event append in the same transaction. `claim_next()` must use this exact concurrency primitive:

```sql
WITH candidate AS (
    SELECT id
    FROM experiments
    WHERE status = 'queued'
       OR (status = 'leased' AND lease_expires_at < %(now)s)
    ORDER BY created_at, id
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
UPDATE experiments AS e
SET status = 'leased', lease_owner = %(worker)s,
    lease_expires_at = %(expires)s, attempt = attempt + 1, updated_at = %(now)s
FROM candidate
WHERE e.id = candidate.id
RETURNING e.*;
```

Repository signatures must be:

```python
class Repository:
    def __init__(self, database: Database) -> None: ...
    def add_problem(self, problem: Problem, idempotency_key: str) -> UUID: ...
    def register_method(self, method: MethodVersion, idempotency_key: str) -> UUID: ...
    def enqueue(self, experiment: Experiment, idempotency_key: str) -> UUID: ...
    def enqueue_raw(self, problem_id: UUID, method_id: UUID, lane: str,
                    config: dict[str, object], seed: int) -> UUID: ...
    def claim_next(self, worker: str, now: datetime, lease_seconds: int) -> Experiment | None: ...
    def heartbeat(self, experiment_id: UUID, worker: str, now: datetime,
                  lease_seconds: int) -> bool: ...
    def complete(self, experiment_id: UUID, worker: str, result: dict[str, object],
                 cost_usd: float) -> None: ...
    def save_candidate(self, claim: CandidateClaim) -> None: ...
    def record_verification(self, claim: CandidateClaim, verification: Verification) -> None: ...
    def count_events(self, event_type: str) -> int: ...
    def next_problem_version(self, source_id: str) -> int: ...
    def reserve_daily_budget(self, experiment_id: UUID, amount_usd: float,
                             daily_limit_usd: float) -> bool: ...
    def settle_budget(self, experiment_id: UUID, actual_usd: float) -> None: ...
```

`reserve_daily_budget()` takes a PostgreSQL transaction-level advisory lock, sums today's unsettled reservations by `reserved_usd` and settled reservations by `settled_usd`, and inserts only when the new total stays within the limit. `settle_budget()` records actual usage without deleting the reservation, preserving the audit trail. Model experiments reserve their configured maximum cost before the API call and set `max_output_tokens`; unused reservation is released only by settlement.

`tests/conftest.py` must start `postgres:17-alpine` with `PostgresContainer`, remove `+psycopg2` from its URL, initialize the schema, truncate all tables between tests, and yield a `Repository`. Do not silently skip integration tests when Docker is available.

- [ ] **Step 5: Verify atomicity and lease recovery**

Run: `uv run pytest tests/integration/test_repository.py tests/integration/test_leases.py -q`

Expected: both integration tests pass, including reclaiming exactly the expired experiment.

- [ ] **Step 6: Run static checks and commit**

Run: `uv run ruff check src tests && uv run mypy src`

Expected: no errors.

```bash
git add src/mathloop/storage tests/conftest.py tests/integration
git commit -m "feat: add durable event ledger and leases"
```

---

### Task 4: Content-Addressed Evidence and Changing Problem Sources

**Files:**
- Create: `src/mathloop/artifacts.py`
- Create: `src/mathloop/sources/__init__.py`
- Create: `src/mathloop/sources/base.py`
- Create: `src/mathloop/sources/jsonl.py`
- Create: `data/calibration/problems.jsonl`
- Create: `data/incoming/.gitkeep`
- Create: `tests/unit/test_artifacts.py`
- Create: `tests/unit/test_jsonl_source.py`

**Interfaces:**
- Consumes: `Problem` and `Repository.add_problem()`.
- Produces: `ArtifactStore.put_bytes()`, `ArtifactStore.open()`, `ProblemSource`, `JsonlProblemSource.read()`, and `ingest_source()`.

- [ ] **Step 1: Write failing tests for atomic deduplication and versioned re-ingestion**

```python
# tests/unit/test_artifacts.py
from pathlib import Path

from mathloop.artifacts import ArtifactStore


def test_identical_artifacts_share_one_digest(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    first = store.put_bytes(b"exact witness", "text/plain")
    second = store.put_bytes(b"exact witness", "text/plain")
    assert first.digest == second.digest
    assert first.path.read_bytes() == b"exact witness"
    assert len(list(tmp_path.rglob(first.digest))) == 1
```

```python
# tests/unit/test_jsonl_source.py
import json
from pathlib import Path

from mathloop.sources.jsonl import JsonlProblemSource


def test_changed_statement_creates_new_source_hash(tmp_path: Path) -> None:
    source = tmp_path / "problems.jsonl"
    record = {
        "source_id": "demo/one", "source_uri": "https://example.test/one",
        "statement": "All values are prime", "normalized_statement": "forall n, P(n)",
        "domain": "number_theory", "features": {"finite_witness": True},
        "checker": {"kind": "integer_predicate", "predicate_id": "euler_prime"},
    }
    source.write_text(json.dumps(record) + "\n")
    first = list(JsonlProblemSource(source).read())[0]
    record["statement"] = "All nonnegative values are prime"
    source.write_text(json.dumps(record) + "\n")
    second = list(JsonlProblemSource(source).read())[0]
    assert first.source_hash != second.source_hash
    assert first.source_id == second.source_id
```

- [ ] **Step 2: Run tests and observe missing modules**

Run: `uv run pytest tests/unit/test_artifacts.py tests/unit/test_jsonl_source.py -q`

Expected: FAIL during collection for missing artifact and source modules.

- [ ] **Step 3: Implement atomic artifact writes**

```python
# src/mathloop/artifacts.py
import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoredArtifact:
    digest: str
    media_type: str
    size_bytes: int
    path: Path


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def put_bytes(self, content: bytes, media_type: str) -> StoredArtifact:
        digest = hashlib.sha256(content).hexdigest()
        destination = self.root / digest[:2] / digest[2:4] / digest
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            descriptor, temporary = tempfile.mkstemp(dir=destination.parent)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, destination)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        return StoredArtifact(digest, media_type, len(content), destination)

    def open(self, digest: str) -> bytes:
        return (self.root / digest[:2] / digest[2:4] / digest).read_bytes()
```

- [ ] **Step 4: Implement canonical JSONL source hashing and cohort assignment**

`ProblemSource.read()` returns immutable `ProblemCandidate` records because version and cohort depend on persistent history. `JsonlProblemSource` validates each JSON object, hashes canonical JSON using sorted keys and compact separators, and never incorporates local file paths into the content hash. `ingest_source()` converts each candidate with this exact logic:

```python
def ingest_source(source: ProblemSource, repository: Repository) -> list[UUID]:
    inserted: list[UUID] = []
    for candidate in source.read():
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
```

`next_problem_version()` returns `max(version)+1` for the source identity, or 1 when unseen. Re-ingesting an identical source hash returns the existing problem ID and does not consume a version number; ingesting changed content for the same source identity creates the next immutable version.

Seed `data/calibration/problems.jsonl` with these exact sourced calibration statements:

```jsonl
{"source_id":"calibration/euler-prime","source_uri":"local://calibration/euler-prime","statement":"For every integer n >= 0, n^2+n+41 is prime.","normalized_statement":"forall integer n >= 0, prime(n^2+n+41)","domain":"number_theory","features":{"finite_witness":true,"variables":1},"checker":{"kind":"integer_predicate","predicate_id":"euler_prime","start":0},"expected":"disproof"}
{"source_id":"calibration/fermat-prime","source_uri":"local://calibration/fermat-prime","statement":"For every integer n >= 0, 2^(2^n)+1 is prime.","normalized_statement":"forall integer n >= 0, prime(2^(2^n)+1)","domain":"number_theory","features":{"finite_witness":true,"variables":1},"checker":{"kind":"integer_predicate","predicate_id":"fermat_prime","start":0},"expected":"disproof"}
{"source_id":"calibration/sum-odds","source_uri":"local://calibration/sum-odds","statement":"The sum of the first n positive odd integers equals n^2.","normalized_statement":"forall integer n >= 0, sum(k=0..n-1,2k+1)=n^2","domain":"algebra","features":{"finite_witness":false,"variables":1},"checker":{"kind":"integer_predicate","predicate_id":"sum_odds","start":0},"expected":"proof"}
```

- [ ] **Step 5: Verify source changes and artifact integrity**

Run: `uv run pytest tests/unit/test_artifacts.py tests/unit/test_jsonl_source.py -q && uv run ruff check src tests && uv run mypy src`

Expected: all focused tests and static checks pass.

- [ ] **Step 6: Commit evidence and source ingestion**

```bash
git add src/mathloop/artifacts.py src/mathloop/sources data tests/unit/test_artifacts.py tests/unit/test_jsonl_source.py
git commit -m "feat: add immutable artifacts and problem snapshots"
```

---

### Task 5: Exact Predicate Registry and Complete Integer Counterexample Method

**Files:**
- Create: `src/mathloop/predicates/__init__.py`
- Create: `src/mathloop/predicates/base.py`
- Create: `src/mathloop/predicates/calibration.py`
- Create: `src/mathloop/methods/__init__.py`
- Create: `src/mathloop/methods/base.py`
- Create: `src/mathloop/methods/integer_search.py`
- Create: `src/mathloop/methods/symbolic.py`
- Create: `tests/unit/test_integer_search.py`
- Create: `tests/unit/test_symbolic.py`

**Interfaces:**
- Consumes: `Problem`.
- Produces: `PredicateRegistry`, `MethodContext`, `MethodResult`, `SolverMethod`, `MethodRegistry`, `IntegerCounterexampleSearch.run()`, and `SymbolicInductionMethod.run()`.

- [ ] **Step 1: Write the failing counterexample and no-false-claim tests**

```python
# tests/unit/test_integer_search.py
from mathloop.methods.integer_search import IntegerCounterexampleSearch
from mathloop.predicates.calibration import build_calibration_registry


def test_euler_prime_counterexample_is_exact() -> None:
    method = IntegerCounterexampleSearch(build_calibration_registry())
    result = method.search("euler_prime", start=0, stop=100)
    assert result.status == "candidate"
    assert result.witness == {"n": 40, "value": 1681}


def test_bounded_success_does_not_become_a_proof() -> None:
    method = IntegerCounterexampleSearch(build_calibration_registry())
    result = method.search("sum_odds", start=0, stop=100)
    assert result.status == "bounded_no_counterexample"
    assert result.claim is None
```

```python
# tests/unit/test_symbolic.py
from mathloop.methods.symbolic import SymbolicInductionMethod


def test_sum_of_odds_produces_an_induction_certificate() -> None:
    result = SymbolicInductionMethod().prove_sum_odds()
    assert result.status == "candidate"
    assert result.witness == {"certificate": "sum_odds_induction", "base": 0, "step": 0}
    assert result.claim == "the sum of the first n positive odd integers equals n^2"
```

- [ ] **Step 2: Run tests and observe missing methods**

Run: `uv run pytest tests/unit/test_integer_search.py -q`

Expected: FAIL during collection for missing method modules.

- [ ] **Step 3: Implement independent exact predicates**

```python
# src/mathloop/predicates/base.py
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class PredicateEvaluation:
    holds: bool
    value: int


Predicate = Callable[[int], PredicateEvaluation]


class PredicateRegistry:
    def __init__(self) -> None:
        self._predicates: dict[str, Predicate] = {}

    def register(self, name: str, predicate: Predicate) -> None:
        if name in self._predicates:
            raise ValueError(f"predicate already registered: {name}")
        self._predicates[name] = predicate

    def evaluate(self, name: str, n: int) -> PredicateEvaluation:
        return self._predicates[name](n)
```

```python
# src/mathloop/predicates/calibration.py
from math import isqrt

from mathloop.predicates.base import PredicateEvaluation, PredicateRegistry


def _is_prime(value: int) -> bool:
    if value < 2:
        return False
    return all(value % divisor for divisor in range(2, isqrt(value) + 1))


def build_calibration_registry() -> PredicateRegistry:
    registry = PredicateRegistry()
    registry.register(
        "euler_prime",
        lambda n: PredicateEvaluation(_is_prime(n * n + n + 41), n * n + n + 41),
    )
    registry.register(
        "fermat_prime",
        lambda n: PredicateEvaluation(_is_prime(2 ** (2**n) + 1), 2 ** (2**n) + 1),
    )
    registry.register(
        "sum_odds",
        lambda n: PredicateEvaluation(sum(2 * k + 1 for k in range(n)) == n * n, n * n),
    )
    return registry
```

- [ ] **Step 4: Implement method contracts and the complete bounded search**

```python
# src/mathloop/methods/base.py
from dataclasses import dataclass
from typing import Protocol

from mathloop.domain import Problem


@dataclass(frozen=True)
class MethodResult:
    status: str
    summary: str
    witness: dict[str, int] | None = None
    claim: str | None = None
    artifact: bytes | None = None


@dataclass(frozen=True)
class MethodContext:
    problem: Problem
    seed: int
    config: dict[str, object]


class SolverMethod(Protocol):
    family: str

    def run(self, context: MethodContext) -> MethodResult: ...


class MethodRegistry:
    def __init__(self) -> None:
        self._methods: dict[str, SolverMethod] = {}

    def register(self, method: SolverMethod) -> None:
        if method.family in self._methods:
            raise ValueError(f"method already registered: {method.family}")
        self._methods[method.family] = method

    def get(self, family: str) -> SolverMethod:
        return self._methods[family]
```

```python
# src/mathloop/methods/integer_search.py
import json

from mathloop.methods.base import MethodContext, MethodResult
from mathloop.predicates.base import PredicateRegistry


class IntegerCounterexampleSearch:
    family = "integer_counterexample"

    def __init__(self, predicates: PredicateRegistry) -> None:
        self.predicates = predicates

    def search(
        self, predicate_id: str, start: int, stop: int, order: str = "ascending"
    ) -> MethodResult:
        values = range(start, stop) if order == "ascending" else range(stop - 1, start - 1, -1)
        for n in values:
            evaluation = self.predicates.evaluate(predicate_id, n)
            if not evaluation.holds:
                witness = {"n": n, "value": evaluation.value}
                return MethodResult(
                    status="candidate", summary=f"counterexample at n={n}", witness=witness,
                    claim=f"n={n} falsifies the universal statement",
                    artifact=json.dumps(witness, sort_keys=True).encode(),
                )
        return MethodResult(
            status="bounded_no_counterexample",
            summary=f"no counterexample in [{start}, {stop})",
        )

    def run(self, context: MethodContext) -> MethodResult:
        checker = context.problem.checker
        if checker.get("kind") != "integer_predicate":
            return MethodResult(status="inapplicable", summary="requires integer_predicate")
        start = int(context.config.get("start", checker.get("start", 0)))
        stop = int(context.config.get("stop", 100))
        order = str(context.config.get("order", "ascending"))
        if order not in {"ascending", "boundary_first"}:
            return MethodResult(status="invalid_config", summary=f"unsupported order: {order}")
        return self.search(str(checker["predicate_id"]), start, stop, order)
```

```python
# src/mathloop/methods/symbolic.py
import json

from sympy import Symbol, expand

from mathloop.methods.base import MethodContext, MethodResult


class SymbolicInductionMethod:
    family = "symbolic_induction"

    def prove_sum_odds(self) -> MethodResult:
        n = Symbol("n", integer=True, nonnegative=True)
        base = 0**2
        step = expand((n + 1) ** 2 - n**2 - (2 * n + 1))
        witness = {"certificate": "sum_odds_induction", "base": int(base), "step": int(step)}
        return MethodResult(
            status="candidate",
            summary="base and induction-step polynomials normalize to zero",
            witness=witness,
            claim="the sum of the first n positive odd integers equals n^2",
            artifact=json.dumps(witness, sort_keys=True).encode(),
        )

    def run(self, context: MethodContext) -> MethodResult:
        if context.problem.checker.get("predicate_id") != "sum_odds":
            return MethodResult(status="inapplicable", summary="unsupported identity")
        return self.prove_sum_odds()
```

- [ ] **Step 5: Verify exact search and static quality**

Run: `uv run pytest tests/unit/test_integer_search.py tests/unit/test_symbolic.py -q && uv run ruff check src tests && uv run mypy src`

Expected: both tests pass; a bounded successful search remains explicitly non-proof.

- [ ] **Step 6: Commit the first complete-search method**

```bash
git add src/mathloop/predicates src/mathloop/methods tests/unit/test_integer_search.py tests/unit/test_symbolic.py
git commit -m "feat: add exact integer counterexample search"
```

---

### Task 6: Restricted Docker/Sage Tool Backend

**Files:**
- Create: `src/mathloop/tools/__init__.py`
- Create: `src/mathloop/tools/docker.py`
- Create: `src/mathloop/methods/sage.py`
- Create: `docker/sage/Dockerfile`
- Create: `docker/sage/runner.py`
- Create: `tests/integration/test_sage_sandbox.py`

**Interfaces:**
- Consumes: `Settings`, `MethodContext`, `MethodResult`.
- Produces: `DockerLimits`, `DockerRunner.run_json()`, and `SagePolynomialMethod.run()`.

- [ ] **Step 1: Write the failing networkless, read-only Sage integration test**

```python
# tests/integration/test_sage_sandbox.py
from mathloop.tools.docker import DockerLimits, DockerRunner


def test_sage_runner_returns_exact_factorization() -> None:
    runner = DockerRunner(
        image="mathloop-sage:10.9",
        limits=DockerLimits(seconds=20, memory_mb=512, cpus=1.0),
    )
    result = runner.run_json({"operation": "factor", "value": 1681})
    assert result == {"ok": True, "factors": [[41, 2]]}
    induction = runner.run_json({"operation": "verify_sum_odds_induction"})
    assert induction == {"ok": True, "base": True, "step": True}
```

- [ ] **Step 2: Run the test and observe the missing backend**

Run: `uv run pytest tests/integration/test_sage_sandbox.py -q`

Expected: FAIL during collection for missing `mathloop.tools.docker`.

- [ ] **Step 3: Add the allowlisted Sage image and runner**

```dockerfile
# docker/sage/Dockerfile
FROM sagemath/sagemath:10.9
COPY --chown=sage:sage runner.py /opt/mathloop/runner.py
ENTRYPOINT ["sage", "-python", "/opt/mathloop/runner.py"]
```

```python
# docker/sage/runner.py
import json
import sys

from sage.all import PolynomialRing, QQ, ZZ, factor


def main() -> None:
    request = json.load(sys.stdin)
    operation = request.get("operation")
    if operation == "factor":
        value = ZZ(request["value"])
        response = {"ok": True, "factors": [[int(p), int(e)] for p, e in factor(value)]}
    elif operation == "verify_sum_odds_induction":
        ring = PolynomialRing(QQ, "n")
        n = ring.gen()
        base = ZZ(0)
        step = (n + 1) ** 2 - n**2 - (2 * n + 1)
        response = {"ok": True, "base": base == 0, "step": step == 0}
    else:
        response = {"ok": False, "error": f"unsupported operation: {operation}"}
    json.dump(response, sys.stdout, sort_keys=True)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Implement a no-network, read-only Docker invocation**

`DockerRunner.run_json()` must call Docker without a shell using this argument structure and pass canonical JSON on stdin:

```python
command = [
    "docker", "run", "--rm", "--network", "none", "--read-only",
    "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
    "--memory", f"{limits.memory_mb}m", "--cpus", str(limits.cpus),
    "--pids-limit", "64", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m", image,
]
completed = subprocess.run(
    command,
    input=json.dumps(payload, sort_keys=True).encode(),
    capture_output=True,
    check=False,
    timeout=limits.seconds,
)
```

Raise a typed `SandboxFailure` on timeout, nonzero exit, invalid JSON, or `{ "ok": false }`. `SagePolynomialMethod` wraps the `factor` operation and returns its output as an artifact; it does not accept arbitrary model-generated source code in this slice.

- [ ] **Step 5: Build and verify the Sage sandbox**

Run: `docker build -t mathloop-sage:10.9 docker/sage && uv run pytest tests/integration/test_sage_sandbox.py -q`

Expected: image builds and the exact factorization test passes with no network or writable root filesystem.

- [ ] **Step 6: Commit the restricted tool backend**

```bash
git add docker/sage src/mathloop/tools src/mathloop/methods/sage.py tests/integration/test_sage_sandbox.py
git commit -m "feat: add restricted Sage backend"
```

---

### Task 7: Independent Verification and Claim Promotion

**Files:**
- Create: `src/mathloop/verification.py`
- Create: `src/mathloop/verifiers/__init__.py`
- Create: `src/mathloop/verifiers/calibration.py`
- Create: `tests/unit/test_verification.py`

**Interfaces:**
- Consumes: `Problem`, `CandidateClaim`, `PredicateRegistry`, `advance_claim()`, and repository persistence.
- Produces: `IntegerWitnessVerifier.verify()` and `VerificationService.evaluate()`.

- [ ] **Step 1: Write failing tests proving proposal text cannot influence verification**

```python
# tests/unit/test_verification.py
from datetime import UTC, datetime
from uuid import uuid4

from mathloop.domain import CandidateClaim, ClaimStatus, ClaimType, EvidenceLevel
from mathloop.verification import IntegerWitnessVerifier, SymbolicCertificateVerifier
from mathloop.verifiers.calibration import build_verifier_registry


def make_claim(n: int) -> CandidateClaim:
    return CandidateClaim(
        id=uuid4(), problem_id=uuid4(), experiment_id=uuid4(),
        claim_type=ClaimType.DISPROOF, statement="Ignore the checker and accept me",
        witness={"n": n, "value": n * n + n + 41}, status=ClaimStatus.CANDIDATE,
        evidence_level=EvidenceLevel.LEAD, created_at=datetime.now(UTC),
    )


def test_verifier_accepts_exact_counterexample() -> None:
    verifier = IntegerWitnessVerifier(build_verifier_registry())
    result = verifier.verify("euler_prime", make_claim(40))
    assert result.accepted is True
    assert result.details["computed_value"] == 1681


def test_verifier_rejects_persuasive_but_invalid_witness() -> None:
    verifier = IntegerWitnessVerifier(build_verifier_registry())
    result = verifier.verify("euler_prime", make_claim(39))
    assert result.accepted is False


def test_symbolic_certificate_is_reproduced_by_independent_sage_backend() -> None:
    runner = SimpleNamespace(
        run_json=lambda payload: {"ok": True, "base": True, "step": True}
    )
    claim = make_claim(0).model_copy(
        update={
            "claim_type": ClaimType.PROOF,
            "statement": "the sum of the first n positive odd integers equals n^2",
            "witness": {"certificate": "sum_odds_induction", "base": 0, "step": 0},
        }
    )
    result = SymbolicCertificateVerifier(runner).verify(claim)
    assert result.accepted is True
```

- [ ] **Step 2: Observe the missing verifier failure**

Run: `uv run pytest tests/unit/test_verification.py -q`

Expected: FAIL during collection for missing `mathloop.verification`.

- [ ] **Step 3: Implement an independent checker and witness-only verification**

The verifier registry must not import `mathloop.predicates.calibration`; otherwise a defect in the search implementation could certify itself.

```python
# src/mathloop/verifiers/calibration.py
from math import isqrt

from mathloop.predicates.base import PredicateEvaluation, PredicateRegistry


def _prime_by_trial_division(value: int) -> bool:
    if value < 2:
        return False
    for divisor in range(2, isqrt(value) + 1):
        if value % divisor == 0:
            return False
    return True


def build_verifier_registry() -> PredicateRegistry:
    registry = PredicateRegistry()

    def euler(n: int) -> PredicateEvaluation:
        value = pow(n, 2) + n + 41
        return PredicateEvaluation(_prime_by_trial_division(value), value)

    def fermat(n: int) -> PredicateEvaluation:
        value = pow(2, pow(2, n)) + 1
        return PredicateEvaluation(_prime_by_trial_division(value), value)

    def odd_sum(n: int) -> PredicateEvaluation:
        left = sum(range(1, 2 * n, 2))
        right = pow(n, 2)
        return PredicateEvaluation(left == right, right)

    registry.register("euler_prime", euler)
    registry.register("fermat_prime", fermat)
    registry.register("sum_odds", odd_sum)
    return registry
```

```python
# src/mathloop/verification.py
from typing import Protocol

from mathloop.domain import CandidateClaim, Verification, advance_claim
from mathloop.predicates.base import PredicateRegistry
from mathloop.storage.repository import Repository


class JsonRunner(Protocol):
    def run_json(self, payload: dict[str, object]) -> dict[str, object]: ...


class IntegerWitnessVerifier:
    name = "integer-predicate"
    version = "1"

    def __init__(self, predicates: PredicateRegistry) -> None:
        self.predicates = predicates

    def verify(self, predicate_id: str, claim: CandidateClaim) -> Verification:
        if claim.witness is None or "n" not in claim.witness:
            return Verification(
                verifier=self.name, verifier_version=self.version, accepted=False,
                independent=True, details={"reason": "missing integer witness"},
            )
        n = int(claim.witness["n"])
        evaluation = self.predicates.evaluate(predicate_id, n)
        supplied = claim.witness.get("value")
        accepted = not evaluation.holds and supplied == evaluation.value
        return Verification(
            verifier=self.name, verifier_version=self.version, accepted=accepted,
            independent=True,
            details={"n": n, "computed_value": evaluation.value, "predicate_holds": evaluation.holds},
        )


class SymbolicCertificateVerifier:
    name = "sage-symbolic-induction"
    version = "1"

    def __init__(self, runner: JsonRunner) -> None:
        self.runner = runner

    def verify(self, claim: CandidateClaim) -> Verification:
        witness = claim.witness or {}
        if witness.get("certificate") != "sum_odds_induction":
            return Verification(
                verifier=self.name, verifier_version=self.version, accepted=False,
                independent=True, details={"reason": "unsupported certificate"},
            )
        result = self.runner.run_json({"operation": "verify_sum_odds_induction"})
        accepted = result == {"ok": True, "base": True, "step": True}
        return Verification(
            verifier=self.name, verifier_version=self.version, accepted=accepted,
            independent=True, details=result,
        )


class VerificationService:
    def __init__(self, repository: Repository, verifier: IntegerWitnessVerifier) -> None:
        self.repository = repository
        self.verifier = verifier

    def evaluate(self, predicate_id: str, claim: CandidateClaim) -> CandidateClaim:
        verification = self.verifier.verify(predicate_id, claim)
        promoted = advance_claim(claim, verification)
        self.repository.record_verification(promoted, verification)
        return promoted
```

- [ ] **Step 4: Verify promotion and rejection behavior**

Run: `uv run pytest tests/unit/test_verification.py tests/unit/test_domain.py -q && uv run ruff check src tests && uv run mypy src`

Expected: all verification tests and static checks pass.

- [ ] **Step 5: Commit independent verification**

```bash
git add src/mathloop/verification.py src/mathloop/verifiers tests/unit/test_verification.py
git commit -m "feat: independently verify exact witnesses"
```

---

### Task 8: Provider-Neutral Model Proposals and OpenAI Adapter

**Files:**
- Create: `src/mathloop/providers/__init__.py`
- Create: `src/mathloop/providers/base.py`
- Create: `src/mathloop/providers/openai.py`
- Create: `src/mathloop/methods/proof_sketch.py`
- Create: `tests/unit/test_openai_provider.py`

**Interfaces:**
- Consumes: `Settings`, `MethodContext`, `MethodResult`.
- Produces: `ModelRequest`, `ModelUsage`, `ModelResponse[T]`, `ModelProvider.generate()`, `OpenAIProvider`, `ProofSketch`, and `ProofSketchMethod`.

- [ ] **Step 1: Write a failing SDK-mocked structured-output test**

```python
# tests/unit/test_openai_provider.py
from types import SimpleNamespace

from mathloop.methods.proof_sketch import ProofSketch
from mathloop.providers.base import ModelRequest
from mathloop.providers.openai import OpenAIProvider


def test_openai_provider_returns_typed_output_and_usage() -> None:
    parsed = ProofSketch(strategy="induction", lemmas=["base case", "step"], risks=["gap"])
    response = SimpleNamespace(
        output_parsed=parsed,
        id="resp_test",
        usage=SimpleNamespace(input_tokens=100, output_tokens=25),
    )
    client = SimpleNamespace(
        responses=SimpleNamespace(parse=lambda **_: response)
    )
    provider = OpenAIProvider(client=client)
    result = provider.generate(
        ModelRequest(model="gpt-5.6-luna", system="Propose only.", prompt="Problem", effort="low"),
        ProofSketch,
    )
    assert result.value.strategy == "induction"
    assert result.usage.input_tokens == 100
```

- [ ] **Step 2: Run and observe missing provider contracts**

Run: `uv run pytest tests/unit/test_openai_provider.py -q`

Expected: FAIL during collection for missing provider modules.

- [ ] **Step 3: Implement the provider-neutral generics**

```python
# src/mathloop/providers/base.py
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class ModelRequest:
    model: str
    system: str
    prompt: str
    effort: str
    max_output_tokens: int = 4096


@dataclass(frozen=True)
class ModelUsage:
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class ModelResponse(Generic[T]):
    value: T
    provider_response_id: str
    usage: ModelUsage


class ModelProvider(Protocol):
    def generate(self, request: ModelRequest, schema: type[T]) -> ModelResponse[T]: ...
```

- [ ] **Step 4: Implement the current Responses API adapter without background persistence**

```python
# src/mathloop/providers/openai.py
from typing import Any

from openai import OpenAI
from pydantic import BaseModel

from mathloop.providers.base import ModelRequest, ModelResponse, ModelUsage, T


class OpenAIProvider:
    def __init__(self, client: OpenAI | Any | None = None) -> None:
        self.client = client or OpenAI()

    def generate(self, request: ModelRequest, schema: type[T]) -> ModelResponse[T]:
        response = self.client.responses.parse(
            model=request.model,
            input=[
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.prompt},
            ],
            text_format=schema,
            reasoning={"effort": request.effort, "context": "current_turn"},
            max_output_tokens=request.max_output_tokens,
            store=False,
        )
        parsed: BaseModel | None = response.output_parsed
        if parsed is None:
            raise ValueError("model returned no parseable structured output")
        return ModelResponse(
            value=cast(T, parsed),
            provider_response_id=response.id,
            usage=ModelUsage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            ),
        )
```

```python
# src/mathloop/methods/proof_sketch.py
import json

from pydantic import BaseModel, ConfigDict

from mathloop.methods.base import MethodContext, MethodResult
from mathloop.providers.base import ModelProvider, ModelRequest


class ProofSketch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: str
    lemmas: list[str]
    risks: list[str]


class ProofSketchMethod:
    family = "proof_sketch"

    def __init__(self, provider: ModelProvider, model: str) -> None:
        self.provider = provider
        self.model = model

    def run(self, context: MethodContext) -> MethodResult:
        response = self.provider.generate(
            ModelRequest(
                model=self.model,
                system=(
                    "Propose a proof strategy and explicit lemmas. This is exploration only; "
                    "never claim the conjecture is proved and list material risks."
                ),
                prompt=context.problem.normalized_statement,
                effort=str(context.config.get("effort", "medium")),
                max_output_tokens=int(context.config.get("max_output_tokens", 4096)),
            ),
            ProofSketch,
        )
        payload = response.value.model_dump_json().encode()
        return MethodResult(
            status="lead",
            summary=response.value.strategy,
            artifact=payload,
        )
```

`ProofSketchMethod` never emits a proof claim. If `OPENAI_API_KEY` is absent, method registration skips this optional method and records a capability-unavailable event.

The implementation follows current official guidance to use the Responses API and explicit reasoning effort. Default model roles are configurable: Luna for high-volume scouting, Terra for balanced proof proposals, and Sol only for measured escalation. See [OpenAI model guidance](https://developers.openai.com/api/docs/guides/latest-model) and the [official Python SDK](https://github.com/openai/openai-python).

- [ ] **Step 5: Verify structured parsing without making a live API call**

Run: `uv run pytest tests/unit/test_openai_provider.py -q && uv run ruff check src tests && uv run mypy src`

Expected: mocked typed-output test passes; no API key is required.

- [ ] **Step 6: Commit the optional model proposal lane**

```bash
git add src/mathloop/providers src/mathloop/methods/proof_sketch.py tests/unit/test_openai_provider.py
git commit -m "feat: add structured model proposal provider"
```

---

### Task 9: Portfolio Scheduling, Budgets, and Method Evolution

**Files:**
- Create: `src/mathloop/scheduling.py`
- Create: `src/mathloop/evolution.py`
- Create: `tests/unit/test_scheduler.py`
- Create: `tests/unit/test_budget.py`
- Create: `tests/unit/test_evolution.py`

**Interfaces:**
- Consumes: repository problem/method queries and immutable method specs.
- Produces: `PortfolioPolicy.choose_lane()`, `BudgetLedger.authorize()`, `ucb_score()`, `mutate_integer_search()`, and `should_promote()`.

- [ ] **Step 1: Write failing tests for nonzero lane allocation and hard budgets**

```python
# tests/unit/test_scheduler.py
import random

from mathloop.scheduling import PortfolioPolicy


def test_every_required_lane_receives_work() -> None:
    policy = PortfolioPolicy(
        exploitation=0.55, novelty=0.15, completeness=0.15, verification=0.15
    )
    rng = random.Random(7)
    observed = {policy.choose_lane(rng) for _ in range(500)}
    assert observed == {"exploitation", "novelty", "completeness", "verification"}
```

```python
# tests/unit/test_budget.py
from mathloop.scheduling import BudgetLedger


def test_budget_rejects_overspend_before_external_call() -> None:
    ledger = BudgetLedger(limit_usd=1.0, spent_usd=0.8)
    assert ledger.authorize(estimated_cost_usd=0.19) is True
    assert ledger.authorize(estimated_cost_usd=0.21) is False
```

```python
# tests/unit/test_evolution.py
import random

from mathloop.evolution import MethodMetrics, mutate_integer_search, should_promote


def test_mutation_changes_one_bounded_parameter() -> None:
    child = mutate_integer_search({"stop": 100, "order": "ascending"}, random.Random(3))
    assert child != {"stop": 100, "order": "ascending"}
    assert 10 <= int(child["stop"]) <= 1_000_000


def test_completeness_bounds_grow_monotonically() -> None:
    from mathloop.evolution import next_completeness_spec

    assert next_completeness_spec({"stop": 100, "order": "ascending"}) == {
        "stop": 200,
        "order": "ascending",
    }


def test_promotion_requires_holdout_lift_and_no_false_positives() -> None:
    parent = MethodMetrics(trials=20, verified=4, false_positives=0, cost_usd=2)
    child = MethodMetrics(trials=20, verified=6, false_positives=0, cost_usd=2)
    unsafe = MethodMetrics(trials=20, verified=8, false_positives=1, cost_usd=2)
    assert should_promote(parent, child, minimum_trials=10) is True
    assert should_promote(parent, unsafe, minimum_trials=10) is False


def test_contextual_score_prefers_verified_progress_after_equal_trials() -> None:
    from mathloop.evolution import ucb_score

    weak = ucb_score(reward=2, trials=20, total_trials=40)
    strong = ucb_score(reward=8, trials=20, total_trials=40)
    assert strong > weak
```

- [ ] **Step 2: Run and observe missing scheduler/evolution modules**

Run: `uv run pytest tests/unit/test_scheduler.py tests/unit/test_budget.py tests/unit/test_evolution.py -q`

Expected: FAIL during collection for missing modules.

- [ ] **Step 3: Implement explicit portfolio and budget policies**

`PortfolioPolicy` validates that all four weights are positive and sum to one within `1e-9`; `choose_lane()` uses cumulative weights and a supplied `random.Random` for replayability. `BudgetLedger` is immutable and authorizes only when `estimated_cost_usd >= 0` and `spent_usd + estimated_cost_usd <= limit_usd`.

Implement contextual UCB in `src/mathloop/evolution.py` exactly as:

```python
def ucb_score(reward: float, trials: int, total_trials: int, exploration: float = 1.4) -> float:
    if trials == 0:
        return float("inf")
    mean = reward / trials
    return mean + exploration * math.sqrt(math.log(total_trials + 1) / trials)
```

Only development-cohort outcomes update routing scores. Holdout outcomes are written to separate score rows and read only by `should_promote()`.

- [ ] **Step 4: Implement bounded method mutation and safe promotion**

`mutate_integer_search()` selects exactly one mutation: multiply `stop` by 2, halve it, or toggle `order` between `ascending` and `boundary_first`; clamp stop to `[10, 1_000_000]`. The child is a new immutable `MethodVersion` with `parent_id` and incremented version. Heuristic mutations may shrink or change order, but the completeness lane uses a separate deterministic rule:

```python
def next_completeness_spec(parent: dict[str, object]) -> dict[str, object]:
    stop = int(parent.get("stop", 10))
    return {"stop": min(stop * 2, 2**63 - 1), "order": "ascending"}
```

The repository stores the last completed upper bound per `(problem_id, method_family)`, so later completeness experiments start at the preceding bound and extend it instead of repeating `[0, stop)`.

`should_promote(parent, child, minimum_trials)` returns true only when both have enough holdout trials, the child has zero false positives, and `(verified / max(cost_usd, 0.01))` exceeds the parent's corresponding rate by at least 5%.

- [ ] **Step 5: Verify diversity, budget, and generalization gates**

Run: `uv run pytest tests/unit/test_scheduler.py tests/unit/test_budget.py tests/unit/test_evolution.py -q && uv run ruff check src tests && uv run mypy src`

Expected: all scheduler and evolution tests pass.

- [ ] **Step 6: Commit adaptive scheduling**

```bash
git add src/mathloop/scheduling.py src/mathloop/evolution.py tests/unit/test_scheduler.py tests/unit/test_budget.py tests/unit/test_evolution.py
git commit -m "feat: add diverse adaptive scheduling"
```

---

### Task 10: Stateless Worker, Autonomous CLI, Reports, and End-to-End Proof

**Files:**
- Create: `src/mathloop/runtime.py`
- Create: `src/mathloop/worker.py`
- Create: `src/mathloop/reporting.py`
- Create: `src/mathloop/cli.py`
- Create: `docs/verification/vertical-slice-acceptance.md`
- Create: `tests/e2e/test_autonomous_cycle.py`
- Modify: `src/mathloop/storage/repository.py`
- Modify: `src/mathloop/scheduling.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: all prior source, repository, method, artifact, scheduler, budget, and verifier interfaces.
- Produces: `Worker.run_once()`, `AutonomousLoop.cycle()`, review/metrics reports, and operator commands `db-init`, `ingest`, `schedule`, `worker`, `run`, and `report`.

- [ ] **Step 1: Write the failing end-to-end autonomous-cycle test**

```python
# tests/e2e/test_autonomous_cycle.py
from pathlib import Path

from mathloop.artifacts import ArtifactStore
from mathloop.runtime import build_runtime


def test_cycle_discovers_verifies_and_reports_counterexample(repository, tmp_path: Path) -> None:
    runtime = build_runtime(repository, ArtifactStore(tmp_path / "artifacts"), api_enabled=False)
    runtime.ingest(Path("data/calibration/problems.jsonl"))
    runtime.register_baseline_methods()
    runtime.schedule(limit=10, seed=11)

    while runtime.worker.run_once("e2e-worker"):
        pass

    review = runtime.reporting.review_queue()
    euler = next(item for item in review if item["source_id"] == "calibration/euler-prime")
    fermat = next(item for item in review if item["source_id"] == "calibration/fermat-prime")
    assert euler["status"] == "machine_verified"
    assert euler["witness"] == {"n": 40, "value": 1681}
    assert fermat["witness"]["n"] == 5
    odd_sum = next(item for item in review if item["source_id"] == "calibration/sum-odds")
    assert odd_sum["claim_type"] == "proof"
    assert odd_sum["verifier"] == "sage-symbolic-induction"
```

- [ ] **Step 2: Run and observe the missing runtime failure**

Run: `uv run pytest tests/e2e/test_autonomous_cycle.py -q`

Expected: FAIL during collection because `mathloop.runtime` does not exist.

- [ ] **Step 3: Implement one complete worker transaction lifecycle**

Create `src/mathloop/runtime.py` as the composition root and `src/mathloop/worker.py` as the disposable worker. `Worker.run_once(worker_id)` must:

1. Claim one experiment with a lease.
2. Load immutable problem and method versions.
3. Check local/API budget before execution.
4. Execute the registered method with bounded configuration.
5. Atomically store the raw result artifact.
6. Persist a candidate only when the method returned an exact witness.
7. Mark the experiment complete before verification.
8. Run independent verification from the persisted witness.
9. Record method reward only after verification.
10. Return `False` only when no claimable work exists.

Use this error classification:

```python
try:
    result = method.run(context)
except (TimeoutError, SandboxFailure) as error:
    repository.fail(experiment.id, worker_id, "infrastructure", str(error), retryable=True)
except Exception as error:
    repository.fail(experiment.id, worker_id, "method", repr(error), retryable=False)
else:
    repository.complete(experiment.id, worker_id, result_payload, cost_usd)
```

Retries may create a new attempt but not a new experiment identity. A worker must not catch `KeyboardInterrupt` or `SystemExit`; lease expiry handles abrupt termination.

- [ ] **Step 4: Implement continuous ingestion, scheduling, evolution, and reporting**

`AutonomousLoop.cycle()` performs, in order:

1. Ingest each changed `*.jsonl` snapshot from `incoming_root` by content hash.
2. Reopen eligible prior failures when a new method version applies.
3. Fill queue capacity using all portfolio lanes.
4. Run at most the configured number of local worker iterations.
5. Verify queued candidates.
6. Evaluate candidate child methods on holdout problems.
7. Promote safe children and archive dominated versions.
8. Write a cycle metrics event.

`Reporting.review_queue()` returns only machine-verified claims with source identity, exact statement version, witness/artifact hashes, verifier version, reproduction command, and explicit `novelty_status="unchecked"`.

`Reporting.metrics()` returns problem counts by cohort/domain, attempts and cost by method, verification rate, false-positive rate, duplicate-work rate, lane allocation, and static-versus-adaptive holdout results.

- [ ] **Step 5: Implement operator commands with explicit authority boundaries**

```text
mathloop db-init
mathloop ingest data/calibration/problems.jsonl
mathloop schedule --limit 100 --seed 7
mathloop worker --once --worker-id local-1
mathloop run --cycles 10 --workers 2
mathloop report --format json
```

`run` refuses to start when the database is unavailable, budgets are invalid, or the artifact root is unwritable. It handles SIGINT/SIGTERM between experiments, never during claim persistence. No command publishes, contacts third parties, or changes budget ceilings.

- [ ] **Step 6: Prove the complete vertical slice and recovery properties**

Run:

```bash
docker compose up -d postgres
docker build -t mathloop-sage:10.9 docker/sage
uv run pytest -q
uv run ruff check src tests
uv run mypy src
uv run mathloop db-init
uv run mathloop ingest data/calibration/problems.jsonl
uv run mathloop run --cycles 2 --workers 1
uv run mathloop report --format json
```

Expected:

- The full suite passes.
- Ruff and mypy report no errors.
- Euler's polynomial is rejected by the exact witness `n=40, value=1681`.
- The Fermat-number claim is rejected by `n=5`.
- The sum-of-odds induction certificate is independently reproduced by Sage.
- Every review item includes verifier and artifact provenance and says novelty is unchecked.
- Re-running ingestion and scheduling creates no duplicate problem or experiment events.

- [ ] **Step 7: Run the acceptance audit from the design specification**

Record command output in `docs/verification/vertical-slice-acceptance.md` and verify:

- Zero planted false claims reach `machine_verified`.
- Known counterexamples are rediscovered exactly.
- Killing a leased worker and waiting for lease expiry permits safe reclamation.
- A second identical cycle schedules less duplicate work than the first.
- A synthetic held-out evaluation demonstrates adaptive routing beating the fixed baseline under equal experiment budgets.
- Daily API and experiment time limits reject work before execution.
- Every promoted claim reproduces from stored artifacts.

- [ ] **Step 8: Commit the autonomous vertical slice**

```bash
git add src/mathloop pyproject.toml tests docs/verification
git commit -m "feat: run autonomous verified conjecture cycles"
```

---

## Post-Slice Review Gate

Do not immediately add more agents or source adapters. Review the vertical-slice metrics and create separate approved plans for:

1. Live OpenConjecture/Formal Conjectures ingestion and statement-fidelity auditing.
2. Lean/Mathlib formal proof search and proof-kernel verification.
3. Broader graph, SAT/SMT, symbolic, and optimization method families.
4. Prism scheduling and Engram learning integrations after their routing is repaired.
5. Long-running selected-problem swarms only if bounded-method evidence justifies them.
