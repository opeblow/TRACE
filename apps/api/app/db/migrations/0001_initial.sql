-- TRACE schema v1: workspace ownership, investigation history, findings, memory job ownership.
-- Chain data is not copied here beyond what an investigation record needs; Tatum stays the source of truth.

CREATE TABLE workspaces (
    namespace     TEXT PRIMARY KEY CHECK (namespace ~ '^[a-z0-9][a-z0-9-]{1,120}$'),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE investigations (
    id                   UUID PRIMARY KEY,
    namespace            TEXT NOT NULL REFERENCES workspaces (namespace) ON DELETE CASCADE,
    address              TEXT NOT NULL CHECK (address ~ '^0x[0-9a-f]{64}$'),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    network              TEXT NOT NULL,
    checkpoint_height    BIGINT CHECK (checkpoint_height IS NULL OR checkpoint_height >= 0),
    balance_sui          NUMERIC(38, 9),
    activity_count       INTEGER NOT NULL CHECK (activity_count >= 0),
    history_truncated    BOOLEAN NOT NULL,
    status               TEXT NOT NULL CHECK (status IN ('complete', 'partial')),
    partial_reasons      TEXT[] NOT NULL DEFAULT '{}',
    rule_version         TEXT NOT NULL,
    memory_rule_version  TEXT,
    memory_status        TEXT NOT NULL,
    anomaly_count        INTEGER NOT NULL CHECK (anomaly_count >= 0),
    baseline             JSONB NOT NULL
);
CREATE INDEX investigations_namespace_created ON investigations (namespace, created_at DESC);
CREATE INDEX investigations_namespace_address ON investigations (namespace, address, created_at DESC);

CREATE TABLE findings (
    id                       BIGSERIAL PRIMARY KEY,
    investigation_id         UUID NOT NULL REFERENCES investigations (id) ON DELETE CASCADE,
    transaction_digest       TEXT NOT NULL,
    direction                TEXT CHECK (direction IS NULL OR direction IN ('in', 'out')),
    amount_sui               NUMERIC(38, 9) NOT NULL,
    threshold_sui            NUMERIC(38, 9),
    robust_z                 DOUBLE PRECISION,
    severity                 TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high')),
    severity_without_memory  TEXT CHECK (severity_without_memory IS NULL OR severity_without_memory IN ('low', 'medium', 'high')),
    state                    TEXT NOT NULL,
    confidence               DOUBLE PRECISION CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    counterparty             TEXT,
    rule_version             TEXT NOT NULL,
    memory_ids               TEXT[] NOT NULL DEFAULT '{}',
    UNIQUE (investigation_id, transaction_digest)
);
CREATE INDEX findings_digest ON findings (transaction_digest);

CREATE TABLE memory_jobs (
    job_id       TEXT PRIMARY KEY CHECK (job_id ~ '^[A-Za-z0-9_-]{1,128}$'),
    namespace    TEXT NOT NULL REFERENCES workspaces (namespace) ON DELETE CASCADE,
    memory_type  TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'succeeded', 'failed')),
    blob_id      TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX memory_jobs_namespace_created ON memory_jobs (namespace, created_at DESC);
