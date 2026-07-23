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

CREATE UNIQUE INDEX IF NOT EXISTS events_event_id_unique ON events (event_id);

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

CREATE UNIQUE INDEX IF NOT EXISTS problems_source_id_version_unique
    ON problems (source_id, version);

CREATE TABLE IF NOT EXISTS problem_source_versions (
    source_id TEXT PRIMARY KEY,
    next_version INTEGER NOT NULL CHECK (next_version > 0)
);

INSERT INTO problem_source_versions (source_id, next_version)
SELECT source_id, MAX(version) + 1
FROM problems
GROUP BY source_id
ON CONFLICT (source_id) DO UPDATE
SET next_version = GREATEST(
    problem_source_versions.next_version, EXCLUDED.next_version
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
    failure_kind TEXT NULL,
    failure_message TEXT NULL,
    retryable BOOLEAN NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (problem_id, method_id, seed)
);

ALTER TABLE experiments
    ADD COLUMN IF NOT EXISTS failure_kind TEXT NULL,
    ADD COLUMN IF NOT EXISTS failure_message TEXT NULL,
    ADD COLUMN IF NOT EXISTS retryable BOOLEAN NULL;

CREATE INDEX IF NOT EXISTS experiments_claimable
    ON experiments (status, lease_expires_at, created_at);

DROP INDEX IF EXISTS experiments_completeness_interval_unique;
DROP INDEX IF EXISTS experiments_semantic_work_unique;

ALTER TABLE experiments
    ADD COLUMN IF NOT EXISTS semantic_unique_enforced BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE experiments
    ALTER COLUMN semantic_unique_enforced SET DEFAULT true;

WITH ranked_semantic_work AS (
    SELECT id,
           ROW_NUMBER() OVER (
               PARTITION BY problem_id, method_id, config
               ORDER BY created_at, id
           ) AS position
    FROM experiments
    WHERE lane <> 'verification'
)
UPDATE experiments AS experiment
SET semantic_unique_enforced = ranked.position = 1
FROM ranked_semantic_work AS ranked
WHERE experiment.id = ranked.id;

UPDATE experiments
SET semantic_unique_enforced = true
WHERE lane = 'verification';

CREATE UNIQUE INDEX experiments_semantic_work_unique
    ON experiments (problem_id, method_id, config)
    WHERE lane <> 'verification' AND semantic_unique_enforced;

CREATE TABLE IF NOT EXISTS artifacts (
    digest TEXT PRIMARY KEY,
    media_type TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    relative_path TEXT NOT NULL,
    experiment_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

DROP INDEX IF EXISTS artifacts_experiment_unique;

ALTER TABLE artifacts
    ADD COLUMN IF NOT EXISTS experiment_unique_enforced BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE artifacts
    ALTER COLUMN experiment_unique_enforced SET DEFAULT true;

WITH ranked_artifacts AS (
    SELECT digest,
           ROW_NUMBER() OVER (
               PARTITION BY experiment_id
               ORDER BY created_at, digest
           ) AS position
    FROM artifacts
)
UPDATE artifacts AS artifact
SET experiment_unique_enforced = ranked.position = 1
FROM ranked_artifacts AS ranked
WHERE artifact.digest = ranked.digest;

CREATE UNIQUE INDEX artifacts_experiment_unique
    ON artifacts (experiment_id)
    WHERE experiment_unique_enforced;

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

CREATE UNIQUE INDEX IF NOT EXISTS evaluations_verification_unique
    ON evaluations (claim_id, verifier, verifier_version);

CREATE TABLE IF NOT EXISTS method_scores (
    domain TEXT NOT NULL,
    method_id UUID NOT NULL,
    cohort TEXT NOT NULL CONSTRAINT method_scores_cohort_valid
        CHECK (cohort IN ('development', 'holdout')),
    trials BIGINT NOT NULL DEFAULT 0 CONSTRAINT method_scores_trials_nonnegative
        CHECK (trials >= 0),
    reward BIGINT NOT NULL DEFAULT 0 CONSTRAINT method_scores_reward_nonnegative
        CHECK (reward >= 0),
    false_positives BIGINT NOT NULL DEFAULT 0
        CONSTRAINT method_scores_false_positives_nonnegative
        CHECK (false_positives >= 0),
    cost_usd NUMERIC(14, 6) NOT NULL DEFAULT 0
        CONSTRAINT method_scores_cost_nonnegative
        CHECK (cost_usd >= 0),
    PRIMARY KEY (domain, method_id, cohort),
    CONSTRAINT method_scores_counts_valid CHECK (reward + false_positives <= trials)
);

ALTER TABLE method_scores
    ADD COLUMN IF NOT EXISTS false_positives BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS cost_usd NUMERIC(14, 6) NOT NULL DEFAULT 0;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM method_scores
        WHERE cohort IS NULL OR cohort NOT IN ('development', 'holdout')
           OR trials IS NULL OR trials < 0
           OR reward IS NULL OR reward::TEXT IN ('NaN', 'Infinity', '-Infinity')
           OR reward < 0 OR reward <> trunc(reward)
           OR reward > 9223372036854775807::NUMERIC
           OR false_positives IS NULL OR false_positives < 0
           OR cost_usd IS NULL OR cost_usd < 0
           OR reward + false_positives > trials
    ) THEN
        RAISE EXCEPTION 'invalid legacy method_scores data cannot be migrated'
            USING ERRCODE = '23514';
    END IF;
END $$;

ALTER TABLE method_scores
    ALTER COLUMN trials TYPE BIGINT USING trials::BIGINT,
    ALTER COLUMN reward TYPE BIGINT USING reward::BIGINT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'method_scores'::regclass
          AND conname = 'method_scores_cohort_valid'
    ) THEN
        ALTER TABLE method_scores ADD CONSTRAINT method_scores_cohort_valid
            CHECK (cohort IN ('development', 'holdout'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'method_scores'::regclass
          AND conname = 'method_scores_trials_nonnegative'
    ) THEN
        ALTER TABLE method_scores ADD CONSTRAINT method_scores_trials_nonnegative
            CHECK (trials >= 0);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'method_scores'::regclass
          AND conname = 'method_scores_reward_nonnegative'
    ) THEN
        ALTER TABLE method_scores ADD CONSTRAINT method_scores_reward_nonnegative
            CHECK (reward >= 0);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'method_scores'::regclass
          AND conname = 'method_scores_false_positives_nonnegative'
    ) THEN
        ALTER TABLE method_scores
            ADD CONSTRAINT method_scores_false_positives_nonnegative
            CHECK (false_positives >= 0);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'method_scores'::regclass
          AND conname = 'method_scores_cost_nonnegative'
    ) THEN
        ALTER TABLE method_scores ADD CONSTRAINT method_scores_cost_nonnegative
            CHECK (cost_usd >= 0);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'method_scores'::regclass
          AND conname = 'method_scores_counts_valid'
    ) THEN
        ALTER TABLE method_scores ADD CONSTRAINT method_scores_counts_valid
            CHECK (reward + false_positives <= trials);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS completeness_progress (
    problem_id UUID NOT NULL,
    method_family TEXT NOT NULL,
    completed_upper_bound BIGINT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (problem_id, method_family)
);

CREATE TABLE IF NOT EXISTS budget_reservations (
    experiment_id UUID PRIMARY KEY,
    reserved_usd NUMERIC(14, 6) NOT NULL CHECK (reserved_usd >= 0),
    settled_usd NUMERIC(14, 6) NULL CHECK (settled_usd >= 0),
    execution_dispatched BOOLEAN NOT NULL DEFAULT false,
    budget_day DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE budget_reservations
    ADD COLUMN IF NOT EXISTS execution_dispatched BOOLEAN NOT NULL DEFAULT false;
