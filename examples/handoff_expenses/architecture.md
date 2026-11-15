# Architecture decision record

Status: Approved owner decisions retained (ADR-001, ADR-002).

## Decision and rationale

Use a local Python CLI and SQLite for one small-business owner on Windows. This supports offline recording, monthly reporting, safe import retries, and export with minimal operational burden. Use only the Python standard library; introduce no web server, microservices, cloud services, accounts, paid dependencies, HTTP, telemetry, network calls, subprocesses, or package installation (CON-001).

## Ownership

- `app.py` owns argparse, command dispatch, JSON output, and exit codes. It imports and calls domain and storage functions.
- `domain.py` owns pure validation: positive integer amounts, canonical valid `YYYY-MM-DD` dates and `YYYY-MM` months. Preserve Unicode categories exactly (REQ-002).
- `storage.py` exclusively owns sqlite3, SQL, connections, transactions, and schema migration. Modules contain real implementations and imports (ADR-001).

Invalid input returns exit 2 and `{"error":"invalid_input"}` (REQ-002). Add returns `{"id":integer}`. Store retry keys in a separate table referencing expense IDs; transactionally bind key and insertion. Identical key/payload returns the original ID; differing payload returns exit 2 and `{"error":"conflict"}` (REQ-004).

## Preservation and queries

Retain `expenses(id INTEGER PRIMARY KEY, amount INTEGER NOT NULL, category TEXT NOT NULL, day TEXT NOT NULL)`. Map stored `day` to exported `date` (ADR-002). Inspect schema before transactional, additive migrations. Never drop or recreate a populated table; preserve every existing row and ID, including `(7,500,'legacy','2025-12-01')` (REQ-001, ADR-002).

Report sums categories only within the validated month, returning `{}` when empty (REQ-003). Export uses read-only queries, filters the same month, orders by ID, and returns `{"records":[{"id":…,"amount":…,"category":…,"date":…}]}` without mutation (REQ-005). Keep migration separate from export.
