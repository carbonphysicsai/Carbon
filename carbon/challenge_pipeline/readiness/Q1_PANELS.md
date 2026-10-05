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
- `score` = `members[m].cpu_practice_score` (primary rule), `value` =
  `members[m].development_decision_loss`, plus `eligible`, `recipe`, `kind`.
- `decision_outcome` = `{scenario: results.json decisions[m][scenario].outcome.selected}`,
  or `ABSTAIN` where `outcome.kind` is an abstention (`CORRECT_ABSTENTION`...).
  Only development-split scenarios on the common resolved mask (`q1-report` `mask`).
- `reference` = the EV4 / refined references the decisions were judged on; Data
  Collection names which kind applies.

Cooling's fixture smoke uses an analytical pseudo-reference and is refused by V1.
