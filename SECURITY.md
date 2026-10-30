# Security policy

## Reporting a vulnerability

Please report security issues privately. Do not open a public issue, pull request or discussion for a vulnerability.

Use GitHub private vulnerability reporting: **[Report a vulnerability](https://github.com/opeblow/TRACE/security/advisories/new)**.

Include:

- The affected component (API, web app, memory, database, deployment)
- Steps to reproduce, and a proof of concept if you have one
- The impact you believe it has

What to expect:

- An acknowledgement of your report.
- An assessment, and a fix coordinated with you before any public disclosure.
- Credit in the release notes if you would like it.

Please test only against your own deployment or with your own data. Do not access other users' workspaces, run denial-of-service tests, or use social engineering.

## Supported versions

Security fixes are made on the `main` branch, which is what the live deployment runs.

## Scope and guarantees

TRACE is read-only. It never requests seed phrases or private keys and never signs or sends transactions.

TRACE claims the following:

- **Server-side credentials.** The Tatum API key, the Walrus Memory delegate key and the database URL stay on the server. They are never included in the web bundle, logs or error responses.
- **Workspace isolation.** There are no user accounts. Each browser holds a random 192-bit workspace key. The server stores only a hash-derived namespace, never the key. Memories, memory jobs and investigation history are all filtered by that namespace, and records from another workspace are reported as not found. TRACE records which workspace submitted each memory job, so ownership is checked even when the provider does not report it.
- **Untrusted recall.** Recalled memory text is re-validated against a strict schema. Records that fail, including ones claiming to be verified, are dropped.
- **Secret rejection.** Text that looks like a seed phrase, private key or password is rejected before it can be stored in memory.
- **Bounded input.** Request bodies are size-limited, addresses are validated before any provider call, and validation errors never echo the submitted value.
- **Rate limiting.** Routes that call paid providers share a rate limit, backed by Redis in multi-instance deployments. If Redis fails in production, those routes fail closed.
- **Headers.** `no-store`, `nosniff`, `X-Frame-Options: DENY`, a strict referrer policy and HSTS in production. The web app ships a strict Content Security Policy.
- **Metrics.** `/metrics` requires a bearer token and is hidden in production when no token is set. Metric labels never contain wallet addresses or workspace keys.
- **Deletion.** Deleting memory removes it from TRACE's Walrus Memory index. Encrypted blobs already written to Walrus, and all on-chain records, are not erased. Deleting investigation history permanently removes it from TRACE's database.

TRACE does **not** claim that any wallet is safe, that all malicious activity is detected, or that the product has been independently audited or certified. Public blockchain data remains public.

**Workspace key warning.** Anyone who holds a workspace key can read and change that workspace's memory and history. Treat it like a password.

## Operational guidance

- Keep all secrets in the hosting provider's secret store. Never commit `.env` files; only `.env.example` placeholders are tracked. CI runs a gitleaks secret scan on every push.
- Rotate the Tatum key, the Walrus delegate key or the database password immediately if any may have been exposed. Then review logs and repository history.
- Production startup validates configuration and refuses unsafe settings: a missing Tatum key, missing Redis (unless `RATE_LIMIT_STORE=memory`), non-HTTPS or localhost CORS origins, wildcard hosts, half-configured memory, a non-HTTPS Walrus relayer URL, an invalid database URL, an unreachable database, or the development namespace prefix.
- Dependencies are audited in CI with `pip-audit` and `npm audit`.

See also the [Privacy policy](PRIVACY.md).
