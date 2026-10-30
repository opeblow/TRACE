# TRACE Test Report

Date: 2026-10-30 · Tested against: *TRACE Product Requirements Document v1.0* (27 Oct 2026)

## Summary

| Area | Result |
|---|---|
| API tests (re-run 2026-10-30 with PostgreSQL 16) | **102 passed, 1 skipped** of 103 collected (`test_api.py` 58, `test_memory.py` 29, `test_persistence.py` 16). The skipped test is the opt-in live Tatum Mainnet test. |
| Live Tatum Sui Mainnet integration | **Passed** (opt-in test + 3 real wallets over HTTP, ~0.7 s each) |
| **Walrus Memory learning loop (live Mainnet)** | **Passed**: 12/12 writes completed, new-session recall changed 8 findings, other workspace recalled 0 ([evidence](evidence/LEARNING_LOOP.md)) |
| Browser end-to-end (Edge, desktop 1366px + mobile 375px) | **46 / 46 passed** against the live API |
| Browser memory loop (label → Walrus job → re-run → new session → delete) | **21 / 21 passed** against live Tatum + Walrus |
| Mobile audit (320 / 360 / 390 / 414 px, all pages) | No horizontal scroll or clipping; touch targets 44 px; 16 px inputs |
| Production configuration | Startup refuses missing or unsafe config (names only, no values); docs hidden; JSON logs; `/ready` returns 503 when Redis is down |
| TypeScript type-check / static build | Passed (Next.js 16.4.3) |
| Dependency audit | **0 known vulnerabilities** (npm audit, pip-audit) |
| Secret scan (web bundle, API source, server logs) | No secrets found |

## Critical issue found and fixed

**Wallet analysis did not work for any real wallet.** Tatum's Sui JSON-RPC route returns HTTP 404 for a valid key (a fake key gets 401, so the key is fine; the route is gone). Sui's public full node confirms: "JSON-RPC on public fullnodes has been deprecated. Please migrate to gRPC or GraphQL." Every real analysis returned "Wallet data provider is unavailable" (HTTP 502). The previous report had only verified this path with mocks.

Fix: the Tatum adapter (`apps/api/app/services/tatum.py`) now uses Tatum's Sui gRPC gateway (`sui.rpc.v2`):

- `LedgerService/GetServiceInfo`: confirms the provider is on **Mainnet** before data is used (PRD §10).
- `StateService/GetBalance`: native SUI balance.
- `LedgerService/ListTransactions`: one affected-address query (both directions), newest first, capped at 50, with an explicit "more history exists" signal.
- Bounded retries with exponential backoff and jitter for UNAVAILABLE / RESOURCE_EXHAUSTED / DEADLINE_EXCEEDED (3 attempts). Auth errors are not retried.
- 4 MB response cap and 12 s per-call timeout. Errors carry no credentials or upstream text.
- The schema is vendored in `sui_rpc_v2.binpb`. Refresh it with `scripts/refresh_sui_descriptors.py`.

## Other issues found and fixed

| Issue | PRD ref | Fix |
|---|---|---|
| Token amounts were floats (`amount_sui: 0.25`) | §10 "never use floating-point arithmetic for exact raw amounts" | Exact `Decimal` end to end; amounts are strings (`"-16516.159733664"`). The anomaly engine is also Decimal. |
| gRPC returns long-form coin type `0x000…02::sui::SUI`; code matched only `0x2::sui::SUI` | FR-04 | `canonical_coin_type()` normalizes both |
| No network shown or verified | §19 "clearly identifies Mainnet/Testnet" | API refuses non-Mainnet data; UI shows "Sui mainnet · checkpoint N · Source" |
| Next.js 14.2.0: 1 critical + 1 high advisory (RCE, SSRF, DoS, PostCSS) | §16 dependency gate | Upgraded to Next.js 16.4.3 (React 18 kept). npm audit is clean. |
| Pinned Python deps: 16 advisories (Starlette, python-dotenv) | §16 | Repinned to patched versions. pip-audit is clean. |
| `requirements-dev.txt` pins (pytest 8.2.0 + pytest-asyncio 0.23.0) crashed pytest, so CI could not run tests | §16 | Repinned; unused pytest-asyncio removed |
| Tests ran against unpinned global packages (FastAPI 0.141 vs pinned 0.111) | §17 "pin runtime" | Pins now match the tested versions |
| Unreachable `REDIS_URL` in local `.env.local` made every local analysis fail with 503 | DX | Development/demo falls back to the process-local limiter with a warning. Production still fails closed. `/health` reports the limiter actually in use. |
| `/api/v1/health` (PRD API contract) returned 404 | §13 | Added (alias of `/health`) |
| Unknown request fields accepted | §13 "reject unknown dangerous fields" | `extra="forbid"` → 422 |
| Address-error message not announced; `aria-describedby` pointed to a missing element | §18 WCAG 2.2 AA | Error has `role="alert"` and is linked via `aria-describedby`; button has `aria-busy` |
| `npm run lint` used `next lint`, which Next 16 removed | §16 | Lint runs `tsc --noEmit` |
| Docs described the JSON-RPC integration | FR-15 | README, API, architecture, and deployment docs updated |

## How to rerun

```bash
cd apps/api
pip install -r requirements-dev.txt
TRACE_ENV=development python -m pytest -q                      # 70 offline tests
TRACE_ENV=development TRACE_LIVE_TESTS=1 python -m pytest -q   # + live Mainnet test (uses TATUM_MAINNET_API_KEY)
cd ../web && npx tsc --noEmit -p tsconfig.json && cd ../.. && npm run build --workspace=apps/web && npm audit
```

## Live evidence (Mainnet, 2026-10-30)

| Wallet | Balance | Txs | Baseline | Findings |
|---|---|---|---|---|
| `0x545b…e817` | 377.75958541 SUI | 50 (more exist) | established (n=50) | 0 |
| `0x7d3f…cf72` | 0.000101651 SUI | 50 (more exist) | established (n=48) | 10 (e.g. 16,516.16 SUI outflow, high) |
| `0xabab…abab` | 0.00012 SUI | 1 | thin history | not assessed |

## Walrus Memory (added 2026-10-30)

Built on the official `memwal` 0.2.2 Python SDK against the Mainnet relayer (`relayer.memory.walrus.xyz`). Before building, a live proof checked:

- relayer health: `ok`, production, write-ready;
- delegate key matches the account;
- write completed in about 22 s, recall in about 2 s;
- another namespace saw nothing;
- forget worked.

| PRD requirement | Status | Proof |
|---|---|---|
| FR-08 write via SDK, await job before reporting success | Done | UI shows "Accepted as job… not saved until this completes", then the blob ID; browser test |
| FR-09 recall relevant memories in the correct namespace; attach IDs to the result | Done | `memory.memories[].memory_id`, `finding.memory_context[]` |
| FR-10 feedback with timestamp and provenance; assertion ≠ verified | Done | `alert_feedback` memories, `verified: false` enforced on read |
| FR-11 inspect and manage memory | Done | Memory Centre: list with provenance, workspace transfer, confirmed delete with caveats |
| §9 learning-loop acceptance (label → new session → changed priority + stateless comparison) | Done | `test_learning_loop_label_changes_result_in_a_new_session` + live [evidence](evidence/LEARNING_LOOP.md) |
| ≥10 completed Mainnet memories, failed jobs not counted | Done | 12/12 completed, blob IDs in `docs/evidence/walrus-memory-evidence.json` |
| Journey D: memory outage → disclosed stateless analysis | Done | `test_memory_outage_falls_back_to_disclosed_stateless_analysis` |
| Isolation negative tests | Done | Workspace B cannot list, recall, read jobs of, or delete workspace A's memory (unit + live + browser) |
| Never store secrets; treat recalled text as untrusted | Done | Seed-phrase, private-key, and PEM patterns rejected; tampered or injected records dropped (tests) |
| Audit events without raw text or keys | Done | `memory_audit` JSON log lines; test asserts no text, workspace key, or address |

Isolation is a deliberate **demo-mode boundary**, as the PRD allows (§4 "authentication or a deliberate demo-mode boundary"): a random per-browser workspace key, stored only as a hash in the namespace. It is not user authentication.

## Not implemented yet

1. **User accounts and authentication** (§11). Memory isolation uses workspace keys (above).
2. **Durable storage** (PostgreSQL entities in §13) and **pagination** (`/wallets/{id}/activity` returns 501).
3. **LLM explanation layer** with structured output (§14). Explanations are deterministic templates with evidence.
4. **Structured metrics and the PRD error envelope** `{code, message, request_id, retryable}` (§13, §15). Errors use `{detail}` with a request ID.
5. **Design system items**: Framer Motion, Radix primitives, settings and status pages, stale-data state (§6, §7).

## Analysis-quality note

**Fixed in `amount-outlier-v2`.** Gas-only transactions are now identified from Tatum's reported gas fee and excluded, and incoming and outgoing transfers have separate baselines. Regression tests: `test_gas_only_transactions_do_not_distort_the_baseline`, `test_incoming_and_outgoing_have_separate_baselines`.

Original observation:

On wallet `0x7d3f…cf72`, all 10 findings are "high". Most of its transactions are gas-only movements (~0.0018 SUI), so the median/MAD baseline is near zero and every real transfer exceeds it. Recommended next rule version: exclude gas-only transactions (or the sender's gas cost) from the baseline, and baseline inflows and outflows separately.

## Housekeeping

- Two test memories from aborted browser runs remain in an unreachable workspace (its key was not kept); it is never recalled by anyone.
- **Production startup (fixed 2026-10-30).** The code no longer refuses production. The remaining failure was `ALLOWED_HOSTS=trace-api.onrender.com` in `render.yaml`, while the service runs at `trace-ym2m.onrender.com`, so every request got "Invalid host header". The API now trusts Render's `RENDER_EXTERNAL_HOSTNAME` automatically. Verified locally: production boots, `/ready` returns 200 on the Render host, and other hosts are still rejected.
- **Test count (re-run 2026-10-30):** 86 passed, 1 skipped (live Tatum test, opt-in). Earlier figures of 74 and 77 were from older states of the suite. The browser counts above came from runs outside this repository; no browser suite is committed.
- The root `.env.local` holds Tatum keys and the Walrus private key. It is git-ignored and not read by the web build, but keep secrets only in `apps/api/.env`.
- `apps/api/pyproject.toml` lists dependencies the app doesn't use (jose, passlib, sqlalchemy…) that disagree with `requirements.txt`.
- `atlas.db` at the repo root is an empty SQLite file with unrelated tables (`deadlines`, `mcp_tool_calls`…). It looks like a leftover.
- The workspace is not a git repository, so the PRD's "public repository" and git-history secret checks could not be run.
- The vendored gRPC schema must be refreshed if Tatum upgrades its Sui node in a way that changes `sui.rpc.v2`.

This report is not an independent security assessment or production certification.
