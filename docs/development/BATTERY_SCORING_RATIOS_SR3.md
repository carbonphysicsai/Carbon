# SR-3: margin error near the decision boundary, pre-registration

**Status.** PRE-REGISTERED on 2026-10-02. This document is committed before
the new leg is computed for any member.

**Authority.** OWNER-SR3-NEAR-01: "near" is the published important region.
Score tuning inside the combined admission test (OWNER-ADMISSION-COMBINED-01).

**Class.** Public synthetic DEVELOPMENT evidence. It is offline, with no
spend, and changes no testnet rule.

## 1. Why

SR-2's leg `m` measured what it was built to measure: the boundary optimist
overstates safety margins by 1.6 bands, the real MLPs by 0.5-0.7. But
averaged over all 1,588 scoring cases, it did not track decision quality.
Decisions turn on cases near the limits, and the mean diluted them.

## 2. The new leg: `n`

`n` is SR-2's cost-weighted margin error, restricted to the near cases.
- **Same definition** as `m` (`docs/development/BATTERY_SCORING_RATIOS_SR2.md`
  §2): plating and peak-temperature margins in the decision contract's band
  units, optimism costing `false_acceptance` (10) per band, pessimism costing
  `missed_opportunity` (1) per band, `n = 1 / (1 + mean cost)`.
- **Averaged only over near cases:** those whose reference is in the
  published important region (`domain.is_important`). That means a plating
  margin within 5 mV of zero, or a peak temperature at or above 55 °C:
  311 of 1,588 cases.

Nothing new is chosen. The region, bands and costs are existing published
values.

## 3. Profiles

Carbon's weighted geometric mean over `a` (accuracy), `r` (important-region
robustness), `g` (decision agreement) and `n`. Weights in steps of 0.1 give
**286 profiles** (`sr3-a…-r…-g…-n…`). The 66 with `w_n = 0` are exactly
SR-1's.

## 4. Data, selection and outcome, as in SR-2

- **Data.** EV2 is primary. Its 15 prediction files are verified against
  their committed digests. The EV4 replication is `NOT_RUN` until its
  predictions are regenerated and verified.
- **Admissible.** The profile scores the boundary optimist below every
  eligible real member.
- **Chosen.** The highest τ-b on EV2 **development** conditions.
  Tie-breaks: fewer development divergence conditions, then higher `w_a`.
- **PROMOTE_TO_CONFIRMATION** only if all four hold on EV2:
  1. it catches the optimist;
  2. it fires fewer verification divergence conditions than the deciding
     rule;
  3. its verification Δτ point estimate is at least 0;
  4. its Δτ interval's lower end is above minus the τ noise band.

  The bootstrap uses B = 10000, seed 20261004. Otherwise the outcome is
  NO_PROMOTION.

**Also reported:**
- `n` against `g`;
- `n` against SR-2's `m`;
- the τ of the near-only and all-case versions.

## 5. What it cannot show

- **A small panel.** EV2 has 14 eligible members, and its τ noise band is
  about 0.26.
- **Not confirmation.** EV2's verification conditions are published, and 286
  profiles are tried.

## 6. Disclosed before running

- SR-1's and SR-2's EV2 results are known: every `w_n = 0` profile, and
  `m` for every member.
- No value of `n` has been computed for any member.
- Disclosure, not a rule: I expect `n` to separate the boundary optimist
  more sharply than `m`. The optimist is built to be wrong exactly in this
  region.
- A hard stop. If SR-3 also ends NO_PROMOTION, it is the third consecutive
  non-progressing study, and the `STUCK` trigger (§4.2) fires a full Track B
  review.
