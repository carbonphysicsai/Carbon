# Mapping a Data Collection panel to a readiness Q1 report

Verified by Data Collection (2026-10-05). `readiness.q1 build` takes a panel file:

```
{"reference": {"provenance": COUNTED_CAMPAIGN | EV4_REFERENCE | REFINED_REFERENCE_WAVE07, "ref": <committed path>},
 "decision_study": <ref>,
 "members": {name: {score, value, eligible, recipe, kind, decision_outcome}}}
```

`score` is higher-is-better; `value` is lower-is-better, `[class, number]` from
`track_b.decision_value` or a plain number (class 0). `decision_outcome` is a
design id or `ABSTAIN`, or for a challenge that decides per scenario a mapping
`{scenario: selected-or-ABSTAIN}`. V2 counts two members as distinct when their
whole outcome vectors differ (key order ignored; an empty vector is unrecorded).

## Motor: `docs/development/evidence/motor-q1-fixture-panel-v1/result.json`
(built by `carbon/motor/q1_panel.run`; decisions judged on the counted GetDP replay)
- `score` = `-members[n].practice_score` (the practice score is lower-is-better)
- `value` = `members[n].decision_value`
- `eligible` = `practice_eligible`; `recipe` = `n`; `kind` = `members[n].kind`
- `decision_outcome` = `members[n].selection` (a design id, e.g. `d01`). Check
  `decision.proposal_outcome` before mapping anything to `ABSTAIN`.
- `reference` = `COUNTED_CAMPAIGN`, ref = the counted-study evidence directory.

## Battery: `docs/development/evidence/graphite-run5-q1/q1-report.json` and `results.json`
(corrected by Data Collection; matches `scripts/dev/battery/graphite_run5_analysis.py`)
- `score` = `-members[m].cpu_practice_score` (NEGATED: the practice score is
  lower-is-better; unnegated, tau flips sign). `value` =
  `members[m].development_decision_loss` (plain number).
- `eligible` = `members[m].eligible` AND `cpu_practice_score is not None`
  (the results' exam eligibility, not `cpu_practice_eligible`).
- `recipe` = `members[m].recipe`; `kind` = `GRAPHITE_RECONSTRUCTED` (q1-report
  members carry no `kind`; the analysis used this constant).
- `decision_outcome` = `{scenario: ...}` over the development scenarios on the
  common resolved mask (`q1-report` `mask.common_resolved`, 6 scenarios;
  `mask.excluded` lists the rest), from `results.json`
  `decisions[m][scenario].outcome`:
  - `selected` when it is not None (this includes `SELECTED_UNRESOLVED`, which keeps its design);
  - `ABSTAIN` when `selected` is None and `kind` is `CORRECT_ABSTENTION`,
    `MISSED_OPPORTUNITY` or `ABSTENTION_UNRESOLVED`;
  - `MODEL_OUTPUT_MISSING` is NOT an abstention: record the token
    `MISSING_OUTPUT` for that scenario (5 cases in run 5). Do not turn every
    `selected is None` into `ABSTAIN`.
- `reference` = `{"provenance": "EV4_REFERENCE", "ref":
  "docs/development/evidence/ev4-2026-10-01/decision-references.jsonl.gz"}`,
  checked against `references.sha256` in that directory (run 5 made no new solves).
- `aliases` = the pairs in `graphite-run5-q1/aliasing.json` (`{alias, target}`;
  e.g. `p-fa70c075f903` aliases `p-69268f1b74ec`, identical predictions). V2 skips
  an alias, so identical outcome vectors are not counted as distinct evidence (the
  analysis uses n = 8 recipes). V1's alignment is recomputed over the members as
  given, so list the analysis's one-seed-per-recipe panel.

Cooling's fixture smoke uses an analytical pseudo-reference and is refused by V1.
