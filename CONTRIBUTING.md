# Contributing to TRACE

Thank you for helping improve TRACE. This guide covers how to set up the project, what we expect from a change, and how to submit it.

By taking part you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md). Please report security problems privately as described in [SECURITY.md](SECURITY.md), never in a public issue.

## Table of contents

1. [Ways to contribute](#ways-to-contribute)
2. [Project principles](#project-principles)
3. [Development setup](#development-setup)
4. [Making a change](#making-a-change)
5. [Tests and checks](#tests-and-checks)
6. [Code style](#code-style)
7. [Commit messages](#commit-messages)
8. [Pull requests](#pull-requests)
9. [Changing the detection or memory rules](#changing-the-detection-or-memory-rules)
10. [Database changes](#database-changes)

## Ways to contribute

- Report a bug with steps to reproduce, what you expected, and what happened.
- Suggest an improvement by opening an issue that describes the problem before the solution.
- Improve documentation where it is unclear or out of date.
- Fix an open issue. Comment on it first so work is not duplicated.

## Project principles

Every change should keep these true:

- **Read-only.** TRACE never asks for seed phrases or private keys and never signs or sends transactions.
- **Evidence before confidence.** Findings must link to chain evidence and explain the rule, threshold and uncertainty behind them.
- **No accusations.** Findings describe activity as unusual relative to a wallet's history. A large amount alone is never called malicious.
- **Memory is an assertion.** User labels and feedback are context, never presented as verified fact.
- **Honest failure.** If Tatum or Walrus Memory is unavailable, TRACE says so instead of guessing or reporting a save that did not happen.
- **No fabricated data.** No mock data, invented metrics or placeholder results in the product.
- **Secrets stay server-side.** Nothing secret goes into the web bundle, logs, error messages or memory.

## Development setup

Requirements: Python 3.11+, Node.js 20.9+, and a Tatum API key. A Walrus Memory account and a PostgreSQL database are optional for most work.

```bash
git clone https://github.com/opeblow/TRACE.git
cd TRACE

# API
cd apps/api
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                               # fill in your own keys; never commit .env
TRACE_ENV=development uvicorn app.main:app --reload --port 8000

# Web (new terminal, repository root)
npm ci
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > apps/web/.env.local
npm run dev                                        # http://localhost:3000
```

Without `DATABASE_URL` the API keeps history in process memory. Without Walrus Memory credentials, analyses run statelessly and say so.

## Making a change

1. Fork the repository and create a branch from `main` with a short descriptive name, for example `fix-thin-history-copy`.
2. Keep the change focused. Separate refactors from behaviour changes.
3. Add or update tests for any behaviour you change.
4. Update the documentation in the same pull request when behaviour, configuration or the API changes.

## Tests and checks

All of these must pass before a pull request is merged. CI runs them on every push.

```bash
# API (from apps/api)
TRACE_ENV=development python -m pytest -q
TRACE_TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/trace_test TRACE_ENV=development python -m pytest -q   # with a disposable database
pip-audit -r requirements.txt

# Web (from the repository root)
npm run lint
npm run build
NEXT_PUBLIC_API_URL=http://api.test npm run build && npm run test:e2e -w apps/web
npm audit --omit=dev --audit-level=high
```

Never mark a test as passing that did not run, and never weaken a test to make a change pass. If a test is wrong, explain why in the pull request.

## Code style

- **Python:** typed, small functions, `Decimal` for every on-chain amount, no bare `except`. Provider and database errors must not leak credentials, connection strings or upstream response bodies.
- **TypeScript:** strict mode, no `any` unless unavoidable and explained. Every API call has loading, empty and error states.
- **UI:** keep the existing visual identity, keyboard access, visible focus, and layouts that work at 320 px without horizontal scrolling.
- **Comments:** explain why, not what.
- **Dependencies:** add one only when it clearly earns its place, and say why in the pull request.

## Commit messages

- Use the imperative mood and describe the change: `Exclude gas-only transactions from the baseline`.
- Keep the subject under about 72 characters. Add a body when the reason is not obvious.
- One logical change per commit.

## Pull requests

A good pull request includes:

- What changed and why, with a link to the issue.
- How you tested it, including any manual checks against the live providers.
- Screenshots or a short recording for UI changes, at desktop and mobile widths.
- Any documentation you updated.

A maintainer will review it. Please respond to review comments, and keep the discussion respectful and focused on the change.

## Changing the detection or memory rules

The anomaly rule (`apps/api/app/services/anomaly.py`) and the memory rule (`apps/api/app/services/learning.py`) are versioned, so past results stay interpretable.

- Any change to how findings or severities are produced needs a new rule version, for example `amount-outlier-v3`.
- Explain the statistical reasoning in the module docstring and the pull request.
- Add regression tests that show the old problem and the new behaviour.
- Update the README sections "Anomaly detection" or "The learning loop".

## Database changes

- Add a new numbered SQL file in `apps/api/app/db/migrations`, for example `0002_add_column.sql`. Never edit a migration that has already been applied.
- Keep changes backward compatible where possible, and update [docs/DATABASE.md](docs/DATABASE.md).
- Do not store blockchain data that can be fetched reliably from Tatum.

## License

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).
