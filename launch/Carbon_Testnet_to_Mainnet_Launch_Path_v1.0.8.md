# Carbon launch path — v1.0.8 training budget study amendment

**Decision:** `OWNER-TRAINING-BUDGET-STUDY-01`, 2026-09-29 owner adoption.
**Predecessor:** `Carbon_Testnet_to_Mainnet_Launch_Path_v1.0.7.md`.
**Scope:** adds one standing launch requirement. Nothing else in v1.0.7 or
earlier changes.

**The requirement.** Every Challenge completes the Challenge training budget
study (`docs/development/CHALLENGE_TRAINING_BUDGET_STUDY.md`), with its own
sheet, before two things:
- **its training limit is set** (step caps, raised caps or a compute-cost
  limit);
- **it pays rewards,** on any network.

**How it is enforced.** Each Challenge readiness record carries a required
`training_budget_study` block, schema `carbon.challenge-readiness.v2`.
- The validator refuses a launch approval unless the study is `COMPLETE`,
  with a result report and an owner decision.
- A study that stopped without choosing a limit (for example, because R1,
  the determinism gate, failed) does not satisfy launch.

**The frozen rules.** The decision rules R1-R8 are frozen in
`docs/development/training_budget_study/DECISION_RULES.md`. Their digest is
recorded in `.agent/DECISIONS.md`.

**Order.** Battery runs the study first, on testnet. Its sheet's values are
applied only once the sheet is in the repository.

**What this does not do.**
- The study is off-chain development evidence for one Challenge on one GPU
  type.
- It grants no scientific, security or production qualification.
- It sets no production value by itself, and changes no live exam, reward or
  miner score.
- It authorizes no pod spend beyond the Challenge sheet's approved ceiling.
