# OPT-08-PUBLIC-SCORING — L1 decision Q1 on public EV4 only

- **Ticket and problem:** OPT-08 L1-DECISION-EXPERIMENT-01 requires public EV4 evidence only. The historical `Experiment.freeze`/`evaluate` default scoring set reads retained private-role references, so calling it unchanged would cross the ticket boundary.
- **Decision:** inject a scoring-set provider into the development experiment, leaving the existing default unchanged. OPT-08 supplies a digest-bound provider built solely from the committed public EV4 reference file. Its contract pins both panel source files and every member/level/seed/strategy identity.
- **Location:** `carbon/battery/value/experiment.py`, `contract.py`, `panel.py`; `scripts/dev/battery/l1_decision_q1.py`; prospective L1 contract.
- **Alternatives:** using the historical default was rejected for its private-role dependency; copying the value evaluator was rejected because it would fork decision semantics; assigning a synthetic score to actual members was rejected because it would invent evidence.
- **Interfaces and invariants:** the optional provider preserves existing callers. Public-only, no hidden leakage, no Level 0 report rewrite, per-level readiness routing, and no scientific or LIVE claim.
- **Reversibility:** remove the optional provider and prospective L1 registration without migrating historical EV4 records. No production schema changes.
- **Lead notification:** the PR and executor handoff identify the new contract, recipe, missing member bundles/scores, and cost uncertainty.
- **Human-reserved input:** Test Lead must decide resource use after measured Level 1 cost/memory. Graphite Test/Data Collection must supply public Level 1 prediction bundles and score records. The actual L1 Q1 result remains unmeasured until then.
