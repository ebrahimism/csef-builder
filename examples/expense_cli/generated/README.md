# Live Codex output

`expenses.py` was produced by the installed Codex agent, then independently executed
against the unchanged 14-case acceptance suite. All 14 behavioral cases passed.

The original defective fixture remains in `../project/expenses.py`. This copy is for
review and local use; it is not an accepted production artifact. Network isolation on
the host failed the loopback probe, so the gate returned REVIEW and refused a checkpoint.

Use an explicit UTF-8 runtime on Windows:

```powershell
python -X utf8 expenses.py --db local-expenses.db add 100000 hosting 2026-01-07
python -X utf8 expenses.py --db local-expenses.db report 2026-01
```

Reports and the real model usage receipt are in
`../../../docs/evidence/gate-pilot-2026-11-15/`.
