## 2026-10-11 — SCORE-PROOF-PICKABLE-01: a score rule that places a known-bad control in the top half cannot be picked

**Authority.**
- **The direction.** The Test Lead, under OWNER-DEV-AUTONOMY-01, on research's #1082 (SCORE-CANDIDATE-ATTACKS-01). On public EV5, accuracy alone (`A`) ranks the boundary-optimist and localized sign-error controls above all 99 real members, despite their 8 and 4 unsafe picks.
- **When.** Registered before the sealed run's evaluation and before the owner's selection pick (SCORE-PROOF-01).

**Decision.**
- **The controls are proof members.** `control-boundary_optimist` and `control-localized_sign_error` are the registered known-bad members (`proof-members-v1.json`). The sealed evaluation builds them from the sealed references (`Experiment.evaluate`, controls on), so no change is needed before the evaluate step.
- **Every candidate's report names where each known-bad control ranks** (`known_bad_ranks`), at every level and pooled, in both phases.
- **Pickable.** At selection, a rule is pickable only if no screened pool (pooled, and each level with at least `minimum_level_members`) has a known-bad or adversarial member in its top half, and its legs are complete. Placement needs no precise tau, so it holds on the selection fold's few questions.
- **Enforced.** The confirmation phase refuses a `--rule` that its `--selection` report does not mark pickable (`rule_not_pickable`). The sealed confirmation's own FAIL-able screens are unchanged.

**#1082's other pre-registered checks.**

| Check | Status in this run | What is needed |
|---|---|---|
| Boundary errors | **Computed:** the known-bad ranks and pickability above | — |
| Worst stratum | Partly: the scenario-fold tau spread is reported | A registered stratum key (for example, the ambient band) for a per-stratum figure |
| Fixed-list invariance; shortlist padding and budget | **Not computable** | VERIFY-R's committed unique top-k lists and per-attempt cost fields (VERIFY-AWARE-SCORE-CODE-01) |
| Copying | **Not computable as a check** | Its disposition is HUMAN_INPUT (#1082). A pairwise prediction-identity diagnostic can be added from the tuning predictions |

**Maturity.** DEVELOPMENT only; no rule adopted.
