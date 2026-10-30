# Deployment

TRACE deploys as two independent parts: a FastAPI service with a Redis-compatible store (Render Blueprint or any container host), and a static web app (Vercel, Cloudflare Pages, or Netlify).

## 1. API on Render

1. In Render, create a **Blueprint** from this repository. It reads [`render.yaml`](../../render.yaml) and creates:
   - `trace-api`: a Python web service rooted at `apps/api`, with health check `/health`.
   - `trace-rate-limits`: a private Key Value instance wired to `REDIS_URL`.
2. Set the secrets marked `sync: false`:
   - `TATUM_MAINNET_API_KEY`
   - `WALRUS_MEMORY_PRIVATE_KEY` and `MEMWAL_ACCOUNT_ID` (leave both empty to run without memory)
   - `BACKEND_CORS_ORIGINS`: your exact web origin(s), for example `https://trace.vercel.app`
3. If you use a custom API domain, add it to `ALLOWED_HOSTS`.
4. Deploy. On startup, the API refuses to boot and lists the variable names (never their values) if any of these are true:
   - the Tatum key or Redis is missing;
   - a CORS origin is not a public `https://` origin;
   - `ALLOWED_HOSTS` contains `*`;
   - memory is half-configured;
   - the namespace prefix is still `trace-dev`.
5. Verify:
   - `GET https://<api-host>/health` returns 200 and the capability summary.
   - `GET https://<api-host>/ready` returns 200 with `"ready": true` (503 if Redis or configuration is not healthy).

**Other container hosts:** build [`apps/api/Dockerfile`](../../apps/api/Dockerfile) (non-root, with a built-in health check), provide the same environment variables and a Redis URL, and expose `$PORT`.

## 2. Web app

Build settings, the same on every host:

| Setting | Value |
|---|---|
| Root directory | repository root |
| Install | `npm ci` |
| Build | `npm run build --workspace=apps/web` |
| Output | `apps/web/out` |
| Environment | `NEXT_PUBLIC_API_URL=https://<api-host>` |

- **Vercel:** [`vercel.json`](../../vercel.json) already sets these, plus security headers.
- **Cloudflare Pages:** set the values above. [`apps/web/public/_headers`](../../apps/web/public/_headers) applies the security headers and long-lived caching for hashed assets.
- **Netlify:** [`apps/web/netlify.toml`](../../apps/web/netlify.toml).

The Content Security Policy allows API calls to `https://*.onrender.com`. If your API is hosted elsewhere, add its origin to `connect-src` in both `vercel.json` and `_headers`.

## 3. After deploying

- Add the final web origin to the API's `BACKEND_CORS_ORIGINS` and redeploy the API.
- Open the web app, analyze a wallet, and confirm the overview shows "Sui mainnet" and a checkpoint.
- Save a label and confirm "Stored in Walrus Memory" appears with a blob ID. Then delete it from the Memory Centre.
- Logs are structured JSON. Watch for `memory_audit` events and `provider failure` warnings.

## Operations

| Situation | Action |
|---|---|
| Tatum key invalid or expired | Rotate it in the dashboard, update `TATUM_MAINNET_API_KEY`, and redeploy. Analyses return 502 with a reference until fixed. |
| Walrus Memory unavailable | Analyses continue statelessly and say so; writes return 503 with "Nothing was saved". Check relayer health and the delegate key. |
| Redis unavailable | Rate-limited routes return 503 (fail closed) and `/ready` returns 503. Restore Key Value. |
| Cost or abuse spike | Lower `ANALYSIS_RATE_LIMIT`. History depth is capped at 50 transactions per analysis. |
| Possible credential leak | Rotate the credential first, then inspect logs and history. |
| Tatum upgrades its Sui node | Run `python apps/api/scripts/refresh_sui_descriptors.py`, run the tests, and commit the updated schema. |
