# TRACE API

FastAPI service for TRACE: Sui Mainnet wallet analysis through Tatum gRPC, anomaly detection, and the Walrus Memory learning loop.

## Run locally

```bash
cd apps/api
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                               # set TATUM_MAINNET_API_KEY (+ Walrus keys for memory)
TRACE_ENV=development uvicorn app.main:app --reload --port 8000
```

API docs are at `http://localhost:8000/docs` outside production.

## Layout

| Path | Purpose |
|---|---|
| `app/main.py` | App factory, middleware (rate limit, body cap, request IDs, security headers), health and readiness |
| `app/core/` | Settings with production validation; JSON logging |
| `app/routers/` | `wallets` (analysis), `memories` (Walrus Memory), `alerts` (feedback) |
| `app/services/tatum.py` | Tatum Sui gRPC adapter (schema in `sui_rpc_v2.binpb`) |
| `app/services/anomaly.py` | Median + MAD outlier rule with exact decimals |
| `app/services/memory.py` | Walrus Memory SDK integration, workspace namespaces, record validation |
| `app/services/learning.py` | Applies recalled memory to findings |
| `scripts/` | Schema refresh; live learning-loop evidence run |
| `tests/` | pytest suites (offline; live test with `TRACE_LIVE_TESTS=1`) |

## Test

```bash
TRACE_ENV=development python -m pytest -q
```

## Production

Set `TRACE_ENV=production`. Startup validates configuration and refuses to boot, naming the missing variables (never their values), if any required setting is absent or unsafe. See the root README's configuration table and [infra/deployment/README.md](../../infra/deployment/README.md).
