# Security policy

## Reporting a vulnerability

Please report security issues privately to the maintainers instead of opening a public issue. Include the affected component (API, web, deployment), reproduction steps, and the impact. You will get an acknowledgement, and fixes are coordinated before public disclosure.

## Scope and guarantees

TRACE is read-only. It never requests seed phrases or private keys and never signs or sends transactions.

TRACE claims the following:

- Provider credentials (Tatum API key, Walrus Memory delegate key) stay server-side and are not included in the web bundle.
- Public blockchain data remains public. TRACE does not make on-chain activity private.
- Labels and feedback are stored through the documented Walrus Memory flow. Each record is scoped to a per-browser workspace key, and the server stores only that key's hash.
- Deleting memory removes it from TRACE's Walrus Memory index. Encrypted blobs already written to Walrus, and all on-chain records, are not erased.

TRACE does **not** claim that any wallet is safe, that all malicious activity is detected, or that the product has been independently audited or certified.

## Operational guidance

- Keep all secrets in the hosting provider's secret store. Never commit `.env` files. Only `.env.example` placeholders are tracked.
- Rotate the Tatum key and the Walrus delegate key immediately if either may have been exposed. Then check logs and repository history.
- Production startup validates configuration and refuses unsafe settings: missing Redis, non-HTTPS or localhost CORS origins, wildcard hosts, half-configured memory, or the development namespace prefix.
