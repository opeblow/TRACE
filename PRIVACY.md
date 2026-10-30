# Privacy policy

This policy explains what data the TRACE web app and API handle, where it goes, how long it is kept, and how to delete it. It describes the code in this repository and the official deployment at [trace-7w2.pages.dev](https://trace-7w2.pages.dev/). If you run your own deployment, you are responsible for how it handles data.

## Summary

- TRACE has no user accounts and does not ask for your name, email or any personal details.
- TRACE never asks for a seed phrase or private key and cannot move funds.
- Wallet addresses and on-chain activity are public. TRACE reads public data; it does not make it private.
- Labels and feedback are saved only when you explicitly consent, and you can delete them.
- There are no advertising trackers and no analytics scripts.

## What TRACE handles

| Data | Where it comes from | Where it is kept | Why |
|---|---|---|---|
| Wallet address you analyse | You | Sent to the TRACE API and to Tatum. Saved in your workspace's investigation history. | To fetch and analyse the wallet's public activity |
| Public chain data (balance, transactions) | Sui Mainnet, through Tatum | Returned to your browser. A summary of each investigation (address, time, checkpoint, balance, baseline and findings) is saved in your workspace history. Full transaction history is not stored. | To show the analysis and your investigation history |
| Workspace key | Generated randomly in your browser | Your browser's local storage. The server receives it with each request but stores only a hash-derived namespace, never the key itself. | To keep your memory and history separate from everyone else's |
| Labels, alert feedback and summaries | You, with explicit consent | Encrypted and stored through Walrus Memory in your workspace's namespace. TRACE also records which workspace submitted each save. | To recall your context in later analyses |
| Last analysis result | The API | Your browser's local storage | To show the overview page without a new request |
| IP address | Your connection | Used for rate limiting: as a one-way hash in Redis, or in the API process's memory when no Redis is used, for at most one rate-limit window. It also appears in the server's standard access logs, and hosting providers may keep their own logs. | To prevent abuse and operate the service |
| Request logs | The API | Server logs with request IDs, paths, status codes and timings. Paths can include query parameters such as an address filter. Logs do not contain workspace keys, memory text or provider credentials. | To operate and debug the service |
| Metrics | The API | Counts and timings by route and outcome, kept in memory until the server restarts. No addresses or workspace keys. | To monitor reliability |

TRACE does not use cookies.

## Services that receive data

| Service | What it receives |
|---|---|
| [Tatum](https://tatum.io) | The wallet address you analyse, to return Sui Mainnet data |
| [Walrus Memory](https://docs.wal.app) | Your consented labels and feedback, encrypted, in your workspace's namespace |
| Database provider (PostgreSQL) | Your workspace's investigation history and memory job records, keyed by the hash-derived namespace |
| Hosting (Cloudflare Pages for the web app, Render for the API) | Standard request data such as IP address and user agent, under their own policies |
| Suiscan | Only if you click an evidence link, which opens their site |

Fonts are served from TRACE's own domain, so loading the app does not contact a font provider.

## Retention

- Investigation history is kept until you delete it.
- Memories are kept in Walrus Memory until you delete them from the index. Encrypted blobs already written to Walrus may remain on Walrus storage after deletion.
- Local storage stays in your browser until you clear it.
- Rate-limit records expire after one rate-limit window.

## Your choices and deletion

- **Do not save memory.** Analyses work without it. Nothing is saved to Walrus Memory unless you tick the consent box.
- **Delete memories.** Memory Centre, then Delete. This removes your memories from TRACE's Walrus Memory index and deletes TRACE's records of your memory jobs. Encrypted blobs already written to Walrus are not erased, and the app says so before you confirm.
- **Delete investigation history.** `DELETE /api/v1/investigations` with `{"confirm": "DELETE"}` and your workspace key permanently removes your history and its findings from TRACE's database.
- **Start fresh.** Clearing your browser's local storage removes your workspace key and last result from that browser. Without the key, TRACE cannot link you to your earlier workspace.

## Security

See [SECURITY.md](SECURITY.md) for how data is protected and how to report a vulnerability.

## Changes

Changes to this policy are made in this file, and its history is visible in the repository.
