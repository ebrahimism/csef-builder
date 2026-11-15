# Offline expense tool: project brief

Build a small, maintainable tool for one small-business owner on a local Windows computer. Support recording expenses offline, reporting by month, safely retrying imports, and exporting data. Preserve the owner's goal and architecture across six engineering handoffs.

## Priority requirements

- **REQ-001 — Data preservation:** Keep a local SQLite database. Preserve every preexisting row and ID through every upgrade. Never drop or recreate a populated table.
- **ADR-002 — Legacy compatibility:** Support `expenses(id INTEGER PRIMARY KEY, amount INTEGER NOT NULL, category TEXT NOT NULL, day TEXT NOT NULL)`. Add fields safely. Preserve legacy row `id=7, amount=500, category=legacy, day=2025-12-01`.
- **REQ-002 — Validation:** Accept positive integer amounts, canonical `YYYY-MM-DD` dates, and `YYYY-MM` months only. Reject invalid input with exit 2 and JSON `{"error":"invalid_input"}`. Preserve Unicode categories exactly.
- **REQ-004 — Add and retry:** `add AMOUNT CATEGORY DATE [--key KEY]` returns `{"id":integer}`. Once retry support is implemented, identical key and payload return the original ID without another row; a reused key with different payload returns exit 2 and `{"error":"conflict"}`.
- **REQ-003 — Report:** `report YYYY-MM` returns JSON category totals for that month, or `{}`, excluding other months.
- **REQ-005 — Export:** `export YYYY-MM` returns `{"records":[{"id":…, "amount":…, "category":…, "date":…}]}` for that month, ordered by ID, without mutation.
- **CON-001 — Offline constraints:** Python standard library only; no HTTP, telemetry, cloud login, network calls, subprocesses, package installation, online services, new accounts, or paid dependencies.
- **ADR-001 — Architecture:** `app.py` owns CLI/JSON and argparse; `domain.py` owns pure business validation; `storage.py` owns SQLite/SQL and sqlite3. Use real imports between modules.

Success requires intact existing data and passing all CLI observations and module rules. No owner questions remain.
