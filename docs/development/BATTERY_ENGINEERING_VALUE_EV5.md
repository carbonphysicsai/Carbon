# EV5: the battery Level 0 combined admission run — pre-registration DRAFT

**Status. DRAFT, not frozen. Nothing dispatches.** The owner approved option
A's USD 6 cap on 2026-10-03 (OWNER-EV5-CAP-01). The gate cutoff is set
(2.0 bands, OWNER-GATE-CUTOFF-01). The freeze now waits only on the
engineering work in §8.

**Authority.**
- OWNER-ADMISSION-COMBINED-01 (2026-10-02): construction, attack and value
  run as one test per rung, with three separate verdicts.
- The TRACK-B-STUCK-01 outcome (2026-10-03, `.agent/DECISIONS.md`): keep the
  deciding rule for ranking, add the near-limit optimism gate, report
  real-model divergence separately, and confirm once in EV5.
- Engineering choices below are the lead session's, under the owner's
  delegation, and are open to change until the freeze. Science values are
  marked HUMAN_INPUT.

**Scope.** Public synthetic DEVELOPMENT evidence:
- no chain action, reward or weight change;
- the testnet rule (`carbon.battery.exam.v1`) stays deciding;
- no level above 0 is opened;
- no qualification claim.

## 1. The questions

1. **Value: ranking.** On fresh conditions, does the SR-2 candidate
   (`sr2-a0-r0.3-g0.6-m0.1`, the best of SR-1..3 on EV4) rank real models by
   decision quality better than the deciding rule? EV4 said "not beyond
   noise" (τ 0.420 vs 0.403); EV5 is the one confirmation.
2. **Value: admissibility.** Does the near-limit optimism gate
   (`carbon/battery/value/admissibility.py`), at its 2.0-band cutoff, fail
   the boundary optimist? Do the real models it fails decide worse than those
   it passes?
3. **Attack.** Do the Track A families and the worker-boundary attacks find
   no breach at Level 0, against the frozen L0 study sheet
   (`docs/development/evidence/track-a-battery-l0-2026-10-02/study-sheet.json`)?
4. **Construction.** Does every panel and attack construction rebuild under
   the construction contract? Is every one it cannot rebuild refused, typed?

## 2. What carries over from EV4, unchanged

- **Decision contract and costs.** EV4's charge-protocol contract
  (`ev4-charge-protocol-selection.v1`), mistake costs, bands, baseline and
  35-candidate grid.
- **Reference and scoring.** The reference (PyBaMM 26.8.0.0, DFN,
  OKane2022) and the scoring set.
- **Panel.** The 100 panel recipes and seeds (`carbon/battery/value/panel.py`)
  and the 5 constructed controls.
- **Optimizer.** Mode D and Mode X with EV4's maxima.
- **Statistics.** The bootstrap (B = 10000) and the τ noise band.

## 3. What is new

| | EV4 | EV5 (draft) |
|---|---|---|
| Conditions | 12 + 12 | **12 + 12, fresh**: no EV1, EV2 or EV4 condition repeats |
| Rules compared | deciding vs `dar-p0-r100-a0` | **deciding vs the SR-2 candidate**, both with and without the gate |
| Divergence criterion | all-pairs count | **across-family real-member count** (`real_divergence.py`); the all-pairs count and the other classes are reported alongside |
| Attack constructions in the panel | none | **Track A harness constructions** scored and value-tested like real ones |
| Confirmation set | none | **120 fresh private cases + 4 hidden duplicates** (the L0 sheet's population), sealed |
| Verdicts | value only | **three, never blended**: construction integrity, adversarial score, value |

**Proposed fresh conditions** (engineering choice). They lie inside the
published box (t_amb 5-40 °C, soc0 0.05-0.5) at temperatures that none of
EV2's or EV4's conditions use; a test checks them against EV1, EV2 and EV4 at
freeze:
- development: t_amb {6, 16, 26, 35} °C × soc0 {0.10, 0.30, 0.46};
- verification: t_amb {10, 20, 30, 39} °C × soc0 {0.07, 0.20, 0.38}.

## 4. Hypotheses (fixed at freeze)

- **H1 (ranking, paired).** Δτ = τ(SR-2 candidate) − τ(deciding) on the 12
  verification conditions, over eligible real members, with a 95 % paired
  bootstrap.
  - The candidate is promoted only if all three hold:
    - the interval's lower bound is above 0;
    - Δτ exceeds the τ noise band;
    - its across-family real-member divergence count is not higher than the
      deciding rule's.
  - Otherwise the deciding rule is confirmed for ranking.
  - EV4's prediction from `real_divergence.py` is that the last condition
    fails: 5 against 1.
- **H2 (gate).** At cutoff `THRESHOLD_BANDS = 2.0` (OWNER-GATE-CUTOFF-01),
  fixed before any EV5 solve:
  - the boundary optimist FAILs;
  - oracle, conservative and rank-preserving delay PASS;
  - the real members that FAIL have a higher mean verification decision loss
    than those that PASS, and the 95 % bootstrap interval of the difference
    excludes 0.
  - The number of real members failed is reported. A cutoff that fails more
    than half the real members is reported as such, not tuned after the fact.
- **H3 (known blind spot, reported).** The localized sign-error control's
  rank under each rule, and whether anything catches it. EV4 predicts
  none of the rules does.
  - **Proposed measurement** (OWNER-EXEC-APPROVALS-01, commissioned
    2026-10-03): near-limit false acceptance
    (`carbon/battery/value/false_acceptance.py`), the worst constraint's
    share of reference-resolved FAILs in the important region that a model
    calls PASS. On the scoring set it is 0.95 for the sign-error control,
    1.00 for the boundary optimist and 0 for the other controls
    (`docs/development/evidence/near-false-acceptance-2026-10-03/`).
  - It is reported for every member. Separation holds if the sign-error
    control's rate is above every eligible real member's.
  - No cutoff: it gates nothing in EV5. The SciML lead may amend or replace
    it before the freeze.
- **Adversarial score.** No Track A or Mode X construction with a
  reference-verified violation scores in the top half of eligible members,
  under the deciding rule plus the gate.
- **Construction integrity.** No breach, escape, canary read or
  forbidden access, in any family or in the worker-boundary scan. Every
  rebuild matches, or is refused typed.

A rung pass needs all three verdicts and the owner's signed lock
(OWNER-TRACK-A-L0-02). Any escape or answer-key exposure stops all runs
(the L0 sheet's stop rule).

## 5. Work

| Phase | Work | Basis for the estimate |
|---|---|---|
| References | 24 conditions × 35 candidates = 840 solves | EV4: 840 solves on 2 A40 pods, 81 and 79 min |
| Confirmation set | 124 solves | about 74 s per solve, 7 workers per pod |
| Panel | 100 reconstructions + harness attack constructions | EV4: 100 on one pod in 34 min; regen 27 min |
| Optimizer | Mode D ≤ 540 + Mode X ≤ 250 solves | EV4: 3 pods × 38.5 min |
| Analysis | gate, SR scores, divergence classes, bootstrap | local CPU, USD 0 |
| Attack harness | Track A families, worker-boundary scan | local and CI, USD 0 |

## 6. Panel additions

The Track A harness constructions are added as panel members of kind
`ATTACK_CONSTRUCTION`. They come from the declarative-recipe families only;
participant code is out of scope at Level 0. They are reconstructed, scored
and value-tested exactly like real ones. GRAPHITE Constructor and Attacker
constructions join only if their phases (GRAPHITE-01 phases 3 and 4) have
produced them under their own grants before the freeze. Their tokens are not
in this estimate.

## 7. Cost estimate (owner decision)

These figures are from EV4's measured pod times at the A40 rate of USD 0.49
per hour. EV4 itself cost USD 2.52 in total.

| Item | Pod time | Expected USD |
|---|---|---|
| References (840) | 2 pods × about 80 min | 1.31 |
| Confirmation set (124) | 1 pod × about 25 min | 0.21 |
| Panel (about 110 members) | 1 pod × about 40 min | 0.33 |
| Optimizer verification (≤ 790) | 3 pods × about 40 min | 0.98 |
| **Total, option A (no in-run agents)** | **about 6.2 pod-hours** | **about USD 2.8** |

- **Proposed cap for option A: USD 6.** Dispatch deadlines commit at most
  about USD 5. The rest is a resume reserve, and nothing is topped up.
- **Option B adds GRAPHITE agents in the run:** about USD 7-26 of tokens and
  about USD 7 of compute, from GRAPHITE plan phases 3 and 4. That is about
  USD 17-36 in all, and the upper end exceeds the L0 cap.
- **Both options count against OWNER-TRACK-A-L0-02's USD 25 L0 cap.** That
  cap covers agent tokens, pod time and the confirmation batch together.
  About USD 0.22 has been spent against it so far (ev4-regen).
- **Recommendation:** option A now; GRAPHITE joins under its own phase grants.
- Ledger figures follow POD-LEDGER-PRIVATE-01 once it merges: the repository
  ledger keeps only allow-listed fields.

## 8. Freeze blockers (HUMAN_INPUT)

1. **Gate cutoff: resolved.** `THRESHOLD_BANDS = 2.0` (OWNER-GATE-CUTOFF-01,
   2026-10-03): the SciML/technical lead deferred it to the lead session and
   the owner approved it. Evidence:
   `docs/development/evidence/admissibility-optimism-2026-10-03/`.
2. **Spend: resolved.** OWNER-EV5-CAP-01 (2026-10-03) approves option A: RunPod
   A40 at no more than USD 0.49 per hour, a hard cap of USD 6, counted inside
   the USD 25 L0 cap.
3. **Sign-error measurement: commissioned.** The owner commissioned one on
   2026-10-03 (OWNER-EXEC-APPROVALS-01). Near-limit false acceptance is
   built and proposed for H3 (§4). It is descriptive, with no cutoff, and the
   SciML lead may amend it before the freeze.

Engineering work before the freeze (the only remaining blocker):
- condition and panel builders, with tests for freshness and maxima;
- the `ATTACK_CONSTRUCTION` panel kind;
- plans and the campaign;
- the freeze manifest.

## 9. What it cannot show

- **No population claim.** Panels are development evidence, not population
  claims. "Best" means best in the tested set.
- **One confirmation per question.** A single fresh run confirms or fails
  once; it does not tune.
- **Level 0 only.** Nothing here speaks to participant code, hostile
  executables or higher ladder rungs.
