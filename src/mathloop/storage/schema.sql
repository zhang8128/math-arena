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
