# Six-stage local expense example

The brief, architecture and contracts were generated in separate stage calls. The
three Python modules came from the compact-dossier arm of the live comparison.
The code passed all staged observations (4 + 8 + 13), including legacy-data retention,
idempotent retries, conflicting-key rejection, Unicode and export.

From this directory:

```powershell
python -X utf8 src/app.py --db expenses.db add 2500 hosting 2026-01-03 --key receipt-1
python -X utf8 src/app.py --db expenses.db report 2026-01
python -X utf8 src/app.py --db expenses.db export 2026-01
```

This is a reviewed local sample, not an accepted release. Native loopback isolation
remains incomplete. No advanced-project or architecture-quality guarantee follows from
the small comparison. See `docs/evidence/handoff-screening-2026-11-15/` in the repository.
