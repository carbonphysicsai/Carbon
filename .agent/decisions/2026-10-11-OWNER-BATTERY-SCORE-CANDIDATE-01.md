## 2026-10-11 — OWNER-BATTERY-SCORE-CANDIDATE-01: the active registered score candidate is registry v5's G-FEAS/A-Q>@0.05

**Authority.** The owner, 2026-10-11, directly in the Carbon Validator
session. Asked:

> Your security condition (1) requires each score candidate to have an owner
> decision record naming the candidate and its registry digest. Your existing
> record (OWNER-BATTERY-SCORE-RULE-01) names registry v4's `G-FEAS/A-Q`
> (sha 4479…). The validators will run registry v5's `G-FEAS/A-Q>@0.05`
> (sha 70f2943814db…), which is the same score and the same 0.05 gate; v5
> only fixes the gate's reading so that exactly 0.05 passes, as you confirmed
> for #972. Should I record v5's candidate as the active one?

the owner chose **"Record v5"**.

**Applies:**
- OWNER-BATTERY-SCORE-RULE-01, the adoption of A-Q with the G-FEAS@0.05
  gate;
- OWNER-BATTERY-V3-FINALS-01, how that score is used.

The owner approved #1101's security review with three conditions, given in
PR Head's session:
1. a score-candidate change is owner-only, each with a decision record
   naming the candidate and its digest;
2. the active candidate is recorded in each window's signed commitment;
3. a change applies prospectively, from the next window only.

**Decided.** The active registered score candidate for rule `v3-bank-sched`
is:
- **candidate:** `G-FEAS/A-Q>@0.05`;
- **registry:** `docs/development/evidence/battery-score-tuning/registry-v5.json`;
- **registry sha256:**
  `70f2943814db0531429613e6ca5e2bd1c0b656673c6ee74de08e98f540758277`.

A deployment's `score` term names this record as its `decision`.

**Enforced by VALIDATOR-26b:**
- the scorer refuses a term whose decision record is absent
  (`registered_score_decision_unrecorded`), or does not name both the
  candidate and the registry sha256 (`registered_score_decision_mismatch`);
- every window's signed commitment names the term;
- a validator refuses a window naming another term
  (`answer_key_score_mismatch`).

**A different candidate** needs a new owner record of this kind. It enters as
a new deployment state (the rule digest changes, and `store.bind` refuses a
changed rule), so it applies from that deployment's first window. Nothing
scored earlier is rescored.

**Not decided here:**
- any LIVE, reward, mainnet or qualification claim;
- the security acceptance itself, which the owner gave in PR Head's session.
