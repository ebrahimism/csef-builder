# T001 baseline

`manifest.json` records this checkout's source inventory, sizes and SHA-256
hashes. It deliberately excludes runtime state, caches, delivery packages,
progress reports and its own output directory. It is historical integrity
evidence, not a requirement that every later checkout stay identical.

From the project root:

```powershell
python tools/baseline_inventory.py --root . --output docs/evidence/baseline-vnext/manifest.json --verify
```

This explicitly compares the current tree without rewriting the manifest.
After later development, a mismatch is expected; use the baseline Git commit
to reproduce the original tree. Do not regenerate historical evidence merely
to make later source changes appear unchanged.
The repository's `.gitattributes` preserves exact bytes across checkouts,
including existing line endings, so Git normalization does not alter the hashes.

For this initial T001 implementation, the manifest was generated after review
repairs. Actual test commands, process status, counts and source digest are in
the controller receipt referenced by `docs/progress/T001-review.json` and
`docs/progress/T001-validation.json`. A JUnit file alone cannot prove process
exit status. The manifest does not invent execution metadata.

Existing Gate limitations remain: the Windows loopback boundary is unresolved,
measure-only stays REVIEW, and this inventory does not grant release authority.
