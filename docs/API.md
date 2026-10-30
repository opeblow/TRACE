# TRACE API contract (demo)

Base prefix: `/api/v1`. OpenAPI: `GET /docs`. Every response carries `X-Request-ID`, `Cache-Control: no-store`, and security headers. Errors have one shape: `{ "detail": "<safe message>", "error": { "code", "message", "request_id", "retryable" } }`. Validation errors (422) add `error.fields[]` with field names and messages only; submitted values are never echoed. Provider failures include `Reference: <request id>` and never include credentials or upstream bodies.

## Memory workspace header

There are no user accounts in this release. Memory is scoped by a per-browser workspace key, sent as:

```
X-Trace-Workspace: <22–64 chars of A–Z a–z 0–9 _ ->
```

The web app generates it randomly (192 bits) and keeps it in local storage. The API stores only `sha256(key)` inside the Walrus namespace name, so keys cannot be recovered from namespaces. Anyone holding the key can read and change that workspace's memory, so treat it like a password. Mutating memory routes accept an optional `Idempotency-Key` header.

## Wallet analysis

`POST /wallets/analyze` with `{ "address": "0x…64 hex…" }` (unknown fields → 422). The optional `X-Trace-Workspace` header enables memory recall.

The response contains:

- `snapshot`: native SUI balance (exact decimal string), `network` (always `mainnet`; anything else is refused with 502), `checkpoint_height`, `fetched_at`, `sources: ["tatum_sui_grpc"]`.
- `activity.items[]`: up to 150 of the most recent transactions touching the address, newest first, fetched in cursor pages of 50 with no duplicates. Each has `digest`, `timestamp_ms`, `checkpoint`, `status`, `direction`, `amount_sui` (exact signed decimal string, net change including gas), `transfer_amount_sui` (gas removed), `gas_fee_sui`, `activity_kind` (`transfer`, `gas_only`, `failed`, `no_sui_change`), `counterparty`, and `counterparty_label` (from memory). `activity.has_more` reports more history.
- `analysis`: baseline (`thin_history` below 10 samples), `anomalies[]` (memory-adjusted, highest priority first), `partial_reasons`, `rule_version`.
- `memory`:
  - `status`: one of `used | recalled | none | unavailable | not_configured | no_workspace`.
  - `message`: the human-readable disclosure.
  - `recalled_count`, `changed_result`, `effects[]`, and `rule_version`.
  - `memories[]`: each with `memory_id` (Walrus blob ID), `used`, and `verified: false`.
  - `stateless.anomalies[]`: the same findings computed **without** memory, for comparison.

Each finding includes `severity`, `severity_without_memory`, `state` (`open | marked_expected | marked_incorrect | needs_review`), `memory_context[]` (summary, date, and blob ID for each memory that affected it), evidence links, threshold, and uncertainty.

If Walrus Memory fails, analysis still succeeds statelessly and says so (`memory.status = unavailable`).

Status codes: 400 invalid address, 422 invalid body, 413 body too large, 429 rate limited, 502 provider failure or non-Mainnet provider, 503 not configured or rate store down.

## Memory (Walrus Memory, Mainnet relayer)

| Route | Purpose |
|---|---|
| `POST /memories` → 202 | `{memory_type, wallet, subject, value, reason?, consent: true}`. Types: `counterparty_label` (subject = counterparty address, value = label ≤60 chars; empty value removes the label), `investigation_summary` (value ≤280 chars). Returns `{job_id, status: "pending"}`. **Accepted is not stored.** |
| `GET /memories/jobs/{job_id}` | `pending \| succeeded \| failed`, with `blob_id` once succeeded. Jobs from other workspaces return 404. |
| `GET /memories?wallet=` | Recalled, schema-validated records with provenance (`created_at`, `source_type`, `user_confirmed`, `verified: false`, `memory_id`). |
| `DELETE /memories` | Body `{"confirm": "DELETE"}`. Removes the workspace's records from the Walrus Memory index. Encrypted blobs already on Walrus are not erased, and chain data is unaffected. |
| `POST /alerts/{digest}/feedback` → 202 | `{wallet, label: expected\|needs_review\|incorrect, reason?, consent: true}`. Stored as an `alert_feedback` memory. |

Writes require `consent: true`. Text that looks like a secret is rejected with 422: seed phrases or 12–24-word mnemonics, `suiprivkey…`, bare 64-hex keys, PEM blocks, and "password"/"private key". Memory writes and deletes share the analysis rate limit.

`DELETE /memories` responds with `index_removed: true`, `blobs_erased: false` and `chain_records_affected: false` so clients can show exactly what deletion did. Memory jobs are bound to the workspace that created them: TRACE records the owner of every job and returns 404 to any other workspace, including when the provider does not report a namespace.

## Investigation history (PostgreSQL)

Every analysis sent with `X-Trace-Workspace` is saved, and the response includes `history: {saved, investigation_id, durable}`. A storage failure never fails the analysis; it returns `saved: false, reason: "storage_unavailable"`.

| Route | Purpose |
|---|---|
| `GET /investigations?address=&limit=` | This workspace's investigations, newest first (`limit` 1-100, default 20). Each has `investigation_id`, `address`, `created_at`, `checkpoint_height`, `balance_sui`, `activity_count`, `status`, `partial_reasons`, `rule_version`, `memory_status`, `anomaly_count`, `highest_severity`. |
| `GET /investigations/{id}` | One investigation with its `baseline` and `findings[]`. 404 if it belongs to another workspace. |
| `DELETE /investigations` | Body `{"confirm": "DELETE"}`. Permanently deletes this workspace's history and findings. Rate limited. |
| `GET /alerts?limit=` | This workspace's finding history across investigations. Without a workspace header: `available: false`. |

`durable` is `true` with PostgreSQL and `false` with the process-local fallback used when `DATABASE_URL` is not set.

## Other routes

- `GET /wallets/{id}/activity`: 501. The analysis itself returns up to 150 recent transactions.
- `GET /metrics`: Prometheus text. Send `Authorization: Bearer <METRICS_TOKEN>`. Hidden (404) in production when no token is configured.
- `GET /me`: 501. Access is scoped by workspace key.

`GET /health` (also `/api/v1/health`) reports capabilities. `GET /ready` returns 200 only when configuration, the rate-limit store and (when `DATABASE_URL` is set) PostgreSQL are healthy, otherwise 503. `GET /health` reports `persistence: postgresql | process_memory`. Development falls back to a process-local rate cap; production requires Redis (or `RATE_LIMIT_STORE=memory` for a single instance) and fails closed.
