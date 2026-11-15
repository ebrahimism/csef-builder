# Command, error, and data contract

For one small-business owner on Windows, provide an offline Python standard-library CLI for recording, monthly reporting, safe import retries, and export. No HTTP, telemetry, cloud login, network calls, subprocesses, package installation, online services, new accounts, or paid dependencies (CON-001).

- `add AMOUNT CATEGORY DATE [--key KEY]` returns `{"id":integer}`. With retry support, identical key/payload returns the original ID without insertion; different payload with that key returns exit 2 and `{"error":"conflict"}` (REQ-004).
- Accept positive integer amounts, canonical valid `YYYY-MM-DD` dates and `YYYY-MM` months. Invalid input returns exit 2 and `{"error":"invalid_input"}`. Preserve Unicode categories exactly (REQ-002).
- `report YYYY-MM` returns JSON category totals for that month only, or `{}` (REQ-003).
- `export YYYY-MM` returns `{"records":[{"id":integer,"amount":integer,"category":string,"date":string}]}`, filtered by month, ordered by ID, without mutation. Map stored `day` to `date`; keep migrations separate (REQ-005, ADR-002).

Preserve every existing row and ID. Retain `expenses(id INTEGER PRIMARY KEY, amount INTEGER NOT NULL, category TEXT NOT NULL, day TEXT NOT NULL)`, including `(7,500,'legacy','2025-12-01')`. Inspect schema; migrate transactionally and additively; never drop or recreate populated tables (REQ-001, ADR-002).

## Six-stage build/test plan

1. Check documents against all fact IDs; record contracts and ownership. Document checks establish consistency only.
2. Implement real module imports: `app.py` owns CLI/JSON/argparse; `domain.py` pure validation; `storage.py` exclusively SQLite/SQL/sqlite3. Inspect ownership (ADR-001).
3. Implement storage/migrations; execution-test upgrades for complete row/ID preservation (REQ-001, ADR-002).
4. Implement validation/add/retry; execution-test invalid inputs, Unicode, atomic key binding, identical retries, and conflicts (REQ-002, REQ-004).
5. Implement report/export; execution-test month isolation, empty results, totals, ordering, and export nonmutation (REQ-003, REQ-005).
6. Assess release readiness using recorded CLI observations, module checks, preservation evidence, and offline constraint checks. Readiness requires passing evidence; this document reports no execution or release success.
