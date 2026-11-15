# DEC-003 — staged context, continuous checks, targeted model review

Status: adopted for the next local prototype, 2026-11-15. Release isolation remains open.

The owner prioritizes lower cost, availability, simple chat interaction, preserving goals
and architecture, and easier delivery of advanced projects. These goals are recorded in
`docs/PROJECT-GOALS.json`; they are not claims that the prototype already meets them.

## Observed screening results

Three shared engineering-document stages preceded three implementation milestones per
arm. Every arm passed 25/25 behavioral observations and the explicit import-boundary
checks, without coding retries in the valid run. Shared design cost is allocated equally.

| Arm | Logical calls including shared design | Input tokens | Uncached input | Output tokens |
| --- | ---: | ---: | ---: | ---: |
| Raw history | 6 | 116450 | 98018 | 7043 |
| Compact dossier | 6 | 106341 | 93925 | 6531 |
| Dossier + reviewer every coding stage | 9 | 162543 | 150127 | 6642 |

The dossier used 8.68% less total input and 4.18% less uncached input in this run.
Always reviewing used 52.85% more total input than the dossier. This is token usage,
not measured monetary savings; cache, output rates, subscription terms and model choice
affect actual cost. Shared design ran once and was reused, not billed once per arm.

No improvement in these behavioral tests was observed from model review. A separate
obvious goal-drift proposal was caught; a legitimate feature proposal was returned for
contract clarification. Two canaries do not establish general reviewer precision.

The first layout had an infrastructure failure. Its code error scores were excluded;
reused artifacts and extra completed model receipts are disclosed in the evidence. This
development overhead is not counted as savings or hidden in the quality comparison.

## Decision and implementation

- Persist owner facts, versioned decisions, stage handoffs and observed evidence.
- Use compact current context with links to older evidence. Never silently truncate goals.
- Keep revision/hash/scope/architecture/behavior checks in every applicable handoff.
- Request a second model at architecture/contract decisions and explicit risks: changed
  goals, migration, security boundaries and repeated failures. Keep always-review available.
- Ask only questions that affect outcomes; reasoned engineering proposals handle routine
  choices. Stop on material unresolved contradictions instead of silently rewriting goals.
- Instantiate roles when their input is ready; do not require six idle model processes.

Implemented in `project.py`, `assistant.py`, `review.py`, `model_session.py` and the
`project` CLI. This reuses Codex rather than building another coding engine.

Selective review is a cost-conscious engineering choice, not an empirically established
quality win. Its quality must be tested on harder/more varied projects before strong claims.
Availability across providers, real user effort and advanced application success remain
unmeasured. The next scope is the guided conversation/context path and risk-based review,
not a dashboard, model swarm or generic deployment platform.

Evidence: `docs/evidence/handoff-screening-2026-11-15/summary.json` and `results.json`.
