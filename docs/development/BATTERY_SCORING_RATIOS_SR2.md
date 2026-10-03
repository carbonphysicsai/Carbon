# SR-2: a margin-aware scoring component, pre-registration

**Status.** PRE-REGISTERED on 2026-10-02. This document is committed before
the component is computed for any member. The commit order is the record.

**Authority.** The owner, 2026-10-02: "Build SR-2 with the margin-aware
component". It runs under OWNER-ADMISSION-COMBINED-01, as score tuning
inside the combined admission test.

**Class.** Public synthetic DEVELOPMENT evidence. It is offline, with no
spend, and changes no testnet rule. A selected profile is a proposal until
fresh confirmation and its own approval.

## 1. Why

SR-1 (`docs/development/BATTERY_SCORING_RATIOS_SR1.md`) showed two things:
- re-weighting accuracy, important-region error and decision agreement
  catches the boundary-optimist control;
- no ratio of those legs reduces score-value divergence among real models.

The decision-agreement leg `g` is thresholded. A call is right or wrong, and
a model that overstates a safety margin by 6 bands costs the same as one
that misses by a hair. SR-2 adds the continuous version.

## 2. The new leg: `m`, cost-weighted margin error

For each scoring-set case, and for each of the two decision constraints with
a continuous margin, both margins are taken in the contract's own band
units:
- **`no_plating_onset`:** margin = plating overpotential minus the threshold
  of 0 V, over a band of 1.97 mV;
- **`peak_temperature`:** margin = the 45 °C limit minus the peak, over a
  band of 0.157 °C.

`s_model` and `s_ref` are those margins from the model's outputs and from the
reference (`decision.measure`).

**Cost per case and constraint:**

    cost = false_acceptance × max(0, s_model − s_ref)        (optimism)
         + missed_opportunity × max(0, s_ref − s_model)      (pessimism)

**The leg:** `m = 1 / (1 + mean cost)`, over every case and both
constraints, in (0, 1].

**Nothing new is chosen.**
- The constraints, limits, bands and the asymmetric costs (10 for an unsafe
  acceptance, 1 for a missed opportunity) are the decision contract's own
  values.
- Measuring the margin error in band units and weighting it by those costs
  is the experimental factor.
- `reach_cv_in_window` is left to `g`. Its margin is undefined when the
  window is not reached, and no value is invented for that case.

**Gates** stay mandatory: an ineligible member scores 0.

## 3. Profiles

**Combination:** Carbon's weighted geometric mean (as in SR-1), over four
legs: `a` (accuracy), `r` (important-region robustness), `g` (decision
agreement) and `m`.

**Grid:** weights in steps of 0.1 on the simplex, which gives **286
profiles** (`sr2-a…-r…-g…-m…`). The 66 with `w_m = 0` are exactly SR-1's
profiles.

## 4. Data

- **Primary: EV2**
  (`docs/development/evidence/ev2-2026-10-01/results.json`). Its 15 member
  prediction files are retained and verified against
  `docs/development/evidence/ev2-2026-10-01/predictions.sha256`. The run
  refuses any file that does not match. The controls come from the
  references, as in EV2.
- **Replication: EV4,** only once its 100 prediction files are available and
  verified against `docs/development/evidence/ev4-2026-10-01/predictions.sha256`.
  They are not retained in the repository. Regenerating them is a separate
  run reported before it spends anything. Until then the EV4 replication is
  `NOT_RUN`, never passed.

## 5. Selection, fixed now (as in SR-1, on the primary data)

1. **Admissible.** The profile scores the boundary-optimist control below
   every eligible real member. This is mandatory.
2. **Chosen.** Among admissible profiles, the highest Kendall τ-b between
   score and negative decision loss over eligible reconstructed members, on
   EV2's **development** conditions.
   - First tie-break: fewer development divergence conditions.
   - Second tie-break: higher `w_a`.

Verification conditions are never used to choose.

## 6. Outcome, fixed now

**PROMOTE_TO_CONFIRMATION** only if all four hold on EV2:
1. it catches the boundary optimist;
2. it fires fewer `SCORE_VALUE_DIVERGENCE` conditions on verification than
   the deciding rule;
3. its verification Δτ point estimate (against the deciding rule) is at
   least 0;
4. the lower end of its Δτ interval is above minus the τ noise band.

The interval is the paired bootstrap with EV2's contract settings, B = 10000
and seed 20261003.

Otherwise the outcome is **NO_PROMOTION**, and the study counts toward
`STUCK`.

**Reported for the leg itself,** `m` against `g`:
- the paired difference of the `sr2-a0-r0-g0-m1` and `sr2-a0-r0-g1-m0`
  profiles;
- how each member's `m` moves the boundary optimist.

## 7. What it cannot show

- **A small panel.** EV2 has 14 eligible real members, and its τ noise band
  is wide. A promotion is weak evidence by construction.
- **Not confirmation.** EV2's verification conditions are published, and 286
  profiles are tried. This is development evidence. A promoted profile goes
  to a fresh confirmation, EV5, the first combined admission run.
- **Synthetic control.** The boundary optimist is a constructed control.

## 8. Disclosed before running

- SR-1's results for the 66 `w_m = 0` profiles on EV2 are known.
- No value of `m` has been computed for any member.
