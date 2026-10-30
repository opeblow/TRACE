# TRACE Architecture

Modular monolith: a Next.js static web app plus a FastAPI service. External systems are Tatum (Sui Mainnet gRPC) and Walrus Memory (official `memwal` Python SDK → Mainnet relayer).

```
Browser (Next.js static export)
  │  X-Trace-Workspace (random per-browser key)
  ▼
FastAPI  ── rate limit / body cap / request IDs / security headers
  ├─ wallets router ── tatum.py ──gRPC──▶ Tatum sui.rpc.v2 (Mainnet)
  │        │            anomaly.py (median + MAD, Decimal)
  │        └──────────▶ learning.py (memory-context-v1)
  ├─ memories / alerts routers
  └─ memory.py ── memwal SDK ──HTTPS (signed)──▶ Walrus Memory relayer
                                  (embeds, Seal-encrypts, uploads to Walrus, indexes)
```

## Analysis flow

1. Validate the address (32-byte hex) before any provider call.
2. In parallel:
   - Tatum gRPC calls (`sui-mainnet-grpc.gateway.tatum.io:443`, `x-api-key` metadata):
     - `LedgerService/GetServiceInfo`: refuse anything that isn't `mainnet`.
     - `StateService/GetBalance`: native SUI balance.
     - `LedgerService/ListTransactions`: affected-address filter, newest first, max 50.

     These calls retry transient errors up to 3 times with backoff and jitter, and cap responses at 4 MB with a 12 s timeout.
   - Walrus Memory recall for this workspace (8 s budget; failure → disclosed stateless analysis).
3. Normalize with exact `Decimal` arithmetic: net SUI change per transaction, direction, and primary counterparty from balance changes.
4. Baseline and outlier rule `amount-outlier-v2` (separate in/out baselines, gas-only excluded, robust z-score severity) produce evidence-linked findings. This is the **stateless** result.
5. `learning.py` applies recalled memory and returns both results:
   - A counterparty label lowers priority one step.
   - Alert feedback sets the review state.
   - The newest record per subject wins, and an empty label removes an earlier one.
   - Findings are never hidden and chain facts are never changed.

The schema is vendored in `apps/api/app/services/sui_rpc_v2.binpb`. Refresh it with `scripts/refresh_sui_descriptors.py`.

## Memory design (PRD §9)

**Namespace strategy.** One Walrus Memory namespace per workspace and environment:
`{MEMWAL_NAMESPACE_PREFIX}-ws-{sha256(workspace_key)[:32]}`. The prefix is `trace-dev` locally and `trace-prod` on Render. All memory operations, job-status reads, and deletes run against the caller's namespace. Jobs whose namespace differs are reported as not found. The app holds one Walrus delegate key (server-side only), so isolation between workspaces is enforced by the API and by unguessable keys, not by separate Walrus accounts.

**Record format.** Each memory is a readable sentence (for semantic search) plus a JSON envelope: `memory_type, wallet, subject, value, reason, created_at, source_type="user_confirmed", user_confirmed=true, verified=false, schema_version=1`. On recall, every record is re-validated against the schema. Anything that fails is dropped (prompt-injection and tampering defence), and a record claiming `verified=true` is rejected.

**Write semantics.**
- Writes happen only after explicit consent.
- `remember` returns a job. The UI and API report success only when Walrus reports the job `done`, and show the blob ID.
- Audit log events (`memory_audit`) record type, job ID, status, time, and a short namespace reference. They never record memory text or the workspace key.

**Correction and deletion.**
- A later record supersedes an earlier one.
- `forget` removes the workspace's index rows. Walrus blobs persist (encrypted) and public chain data is untouched. The UI says so before deletion.

**Evidence.** `scripts/memory_demo.py` runs the PRD learning-loop test live and writes `docs/evidence/`.

## What is persisted where

| Data | Where |
|---|---|
| Analysis result | Browser local storage only |
| Workspace key | Browser local storage; server sees it per request and stores only its hash in namespace names |
| Labels, alert feedback, investigation notes | Walrus Memory (encrypted by the relayer) |
| Tatum key, Walrus delegate key | Server environment only (never in the web bundle; verified by secret scan) |

## Not implemented

User accounts and authentication, history beyond the 150 most recent transactions, and LLM explanations. Production rate limiting requires Redis and fails closed.

## Persistence

PostgreSQL stores workspace ownership, investigations, findings and memory job ownership. See [DATABASE.md](DATABASE.md). Chain data stays in Tatum; TRACE keeps only what an investigation record needs.
