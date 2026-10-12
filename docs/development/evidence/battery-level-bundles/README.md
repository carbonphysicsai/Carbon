# OPT-09 — public Graphite level bundles

**Ticket-start state:** OPT-09 selected on 2026-10-12 from the local optimizer
queue, based on merged main `aa2f5391e6a9b3c8924ddfb51740ba20043e96bb`.
**Maturity ceiling:** registered and fixture-tested DEVELOPMENT rebuild path;
prediction bundles, decision values and Level 1–4 improvement claims remain
unmeasured. The Graphite Test executor rebuilds members after reviewing cost;
this change dispatches no pod, trains no model and runs no reference solver.

The prospective
[`ev4-dev-proof-bundled-v1.json`](../../../../carbon/battery/value/contracts/ev4-dev-proof-bundled-v1.json)
contract retains EV4's public cases and reference digest. Its panel contains
exactly ten `source.bundled: true` rows from the already registered
`proof-panel-levels-v1.json`: one L1, three L2, three L3 and three L4. It pins
the source bytes and each member's strategy, seed, level and arm. The bundle
path also checks the recorded development-variant and recipe digests before
reconstruction. This is a separate panel from OPT-08's 20-member L1 Q1 study.

The three Lane G members have `counts_for_level: false`: their plain strategies
did not exercise Level 4 graph freedom. They can be rebuilt and shown as
non-counting development observations; they cannot earn Level 4 improvement or
readiness credit. The registration changes no EV4 decision physics, score rule,
hidden evaluation or LIVE state.

## Executor plan, after a separate resource decision

```bash
python -m scripts.dev.exam_design.value_plans panel --study ev4-bundled --shards 1
```

The plan ships public TRAIN, calibration and EV4 references only. The
`value_panel` phase refuses a changed contract, member, variant or recipe
digest. It uses the Level 1–4 compiler path before every rebuild and never
falls back to the Level 0 base strategy for a level member. The executor must
measure or credibly bound CPU time and peak memory before dispatch; the total
for these ten level builds is **UNMEASURED**, not a budget authorization.

## Delivery and Hub impact

Working decision: reuse `panel.register_levels`, `member_bundle`, OPT-08's
public reference route and the existing pod plan, with a distinct bundled
panel so Lane G's non-counting status is visible. A wider proof panel would
confound the ledger with unrelated proposals. Dependencies: merged OPT-08 and
the source panel; #1202's host ledger consumes executor records separately.
Tests exercise digest drift, uncompiled-path refusal and each level using a
toy backend. Primary Development Hub `map_ref`: `SYSTEM/DEVELOPMENT-HUB`;
hub impact is none because this bounded public evidence registration changes
no hub purpose, placement, authority, maturity or primary routing link.
