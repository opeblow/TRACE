# Database

TRACE uses PostgreSQL 16 for data that must outlive a request: who owns what, past investigations, their findings, and memory job ownership. Blockchain data is not copied; Tatum remains the source for chain facts.

Code: [`apps/api/app/db/store.py`](../apps/api/app/db/store.py). Migrations: [`apps/api/app/db/migrations`](../apps/api/app/db/migrations).

## Ownership

There are no user accounts. The owner of every row is the workspace's Walrus namespace, `<prefix>-ws-<sha256(workspace key)[:32]>`. The workspace key itself is never stored. Every query filters by namespace, and a row owned by another namespace is reported as not found.

## Tables

| Table | Purpose | Key constraints and indexes |
|---|---|---|
| `workspaces` | One row per namespace, with `created_at` and `last_seen_at` | Namespace format check |
| `investigations` | One row per saved analysis: address, network, checkpoint, balance, activity count, status, partial reasons, rule versions, memory status, finding count, baseline (JSONB) | Address format check, status check; indexes on `(namespace, created_at DESC)` and `(namespace, address, created_at DESC)`; deleted with its workspace |
| `findings` | One row per finding: digest, direction, amount, threshold, robust z, severity before and after memory, state, confidence, counterparty, rule version, memory blob IDs | `NUMERIC(38,9)` amounts (exact), severity and confidence checks, unique `(investigation_id, transaction_digest)`; deleted with its investigation |
| `memory_jobs` | Which namespace submitted each Walrus Memory job, its status and blob ID | Job ID format check; index on `(namespace, created_at DESC)` |
| `schema_migrations` | Applied migration versions | Primary key on version |

## Migrations

Migrations are numbered SQL files (`0001_initial.sql`, ...). At startup the API takes a PostgreSQL advisory lock, applies any file not yet recorded in `schema_migrations`, and records it, all in one transaction. Several instances can start at once safely, and a failed migration leaves the schema unchanged.

To change the schema, add the next numbered file. Never edit an applied migration.

## Writes and failures

- Saving an investigation and its findings is one transaction.
- Database errors surface as `StoreUnavailable` with the driver error type only. Connection strings and SQL are never logged or returned.
- If saving fails, the analysis still returns, with `history.saved: false`.
- In production, if `DATABASE_URL` is set but unreachable at startup, the API refuses to start.
- Without `DATABASE_URL`, a bounded in-process store is used (50 investigations per workspace, 10,000 jobs) and responses report `durable: false`.

## Deletion

- `DELETE /api/v1/investigations` permanently deletes the workspace's investigations and findings.
- `DELETE /api/v1/memories` removes the workspace's Walrus Memory index entries and its `memory_jobs` rows. Walrus blobs already written are not erased.
