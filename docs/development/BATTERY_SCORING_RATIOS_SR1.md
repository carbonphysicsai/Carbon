# SR-1: battery scoring ratios, pre-registration

**Status.** PRE-REGISTERED on 2026-10-02. This document and the code that
runs it are committed before any ratio below is computed. The commit order
is the record (`Challenge_Admission.md` §2).

**Authority.** OWNER-TRACK-A-L0-02 item 7: "We need to be proposing and
testing new scoring ratios when we're having this problem."

**Class.** Public synthetic DEVELOPMENT evidence.
- Offline, on retained results only: no reference solve, no fit and no
  spend.
- It changes no testnet rule. A selected ratio is a proposal, like
  `dar-p0-r100-a0`, until a fresh confirmation and its own approval.

## 1. The problem

On EV2 and EV4 the deciding rule (`control-exam-v1`: gates, then the lowest
mean normalized case error) scores the boundary-optimist control at or above
every eligible real model. That control is accurate almost everywhere and
optimistic exactly near the plating and temperature limits. On EV4 the
divergence detector fires 41 `SCORE_VALUE_DIVERGENCE` conditions under the
deciding rule. Track A at Level 0 cannot lock while this stands
(OWNER-TRACK-A-L0-02 item 6).

## 2. What is tested

Linear ratios over the three components already measured for every EV2 and
EV4 member. No new metric is introduced:

| Leg | Definition (unchanged, `carbon/battery/value/scoring.py`) |
|---|---|
| `a`, accuracy | `1/(1+E)`, where `E` is the mean normalized case error (the exam's score) |
| `r`, important-region robustness | `1/(1+E_important)` over the published important region |
| `g`, decision agreement | `1/(1 + mean mistake cost per resolved constraint call)`, from the decision contract's own costs and bands |

**Score definition.** `score = w_a·a + w_r·r + w_g·g`, with weights on the
simplex in steps of 0.1. That gives **66 profiles**, `sr-a{w_a}-r{w_r}-g{w_g}`.

**Fixed rules for every profile:**
- Gates are mandatory: an ineligible member scores 0 under every profile.
- Physics stays NOT_MEASURABLE and has weight 0.
- The deciding rule, `control-exam-v1`, is the comparator.

## 3. Data

- **Primary: EV4** (`docs/development/evidence/ev4-2026-10-01/results.json`).
  - 99 eligible reconstructed members;
  - decision losses on the development and verification conditions;
  - the boundary-optimist control and the other constructed controls.
- **Replication: EV2** (`docs/development/evidence/ev2-2026-10-01/results.json`).
  It has a different, smaller panel and its own conditions.

Both results are hashed into the SR-1 output.

## 4. Selection, fixed now

1. **Admissible.** The profile scores the boundary-optimist control below
   every eligible real member on EV4. This is mandatory, and profiles that
   fail it are rejected.
2. **Chosen.** Among admissible profiles, the one with the highest Kendall
   τ-b between score and negative decision loss, over eligible reconstructed
   members, on EV4's **development** conditions.
   - First tie-break: fewer divergence conditions on EV4 development.
   - Second tie-break: higher `w_a`, meaning closer to the current rule.

Verification conditions are never used to choose.

## 5. Reported for the chosen profile, and for every profile in a table

- **EV4 verification.**
  - τ-b against the deciding rule's;
  - the paired bootstrap Δτ with its 95% interval, using EV4's own settings
    (`hypotheses.paired_bootstrap`: members and conditions resampled
    jointly, B = 10000) but **seed 20261002**;
  - the divergence noise band.
- **Divergence conditions** (`divergence.conditions(results, rule=…)`) on
  EV4 and on EV2, by split, against the deciding rule's counts.
- **EV2 replication.**
  - Does the profile also catch the boundary optimist on EV2?
  - Its τ-b on EV2 verification.
- **Every other constructed control's position.**

## 6. Outcome, fixed now

**PROMOTE_TO_CONFIRMATION** only if all four hold:
1. the chosen profile catches the boundary optimist on EV4 **and** on EV2;
2. it fires fewer `SCORE_VALUE_DIVERGENCE` conditions than the deciding rule
   on EV4 verification;
3. its EV4 verification Δτ point estimate is at least 0 (it ranks real
   models no worse);
4. its Δτ interval's lower end is above minus the divergence τ noise band
   (`divergence.tau_noise_band`) on EV4 verification.

Otherwise the outcome is **NO_PROMOTION**. The best profile is reported, and
the study counts toward the `STUCK` trigger (§4.2: three consecutive studies
with no progress).

## 7. What it cannot show

- **Not confirmation.** EV2's and EV4's verification conditions are
  published, and 66 profiles are tried. This is selection on development
  conditions with descriptive verification, not confirmation. A promoted
  profile still needs a fresh confirmation set, EV5, under its own
  pre-registration and budget.
- **Bounded comparisons.** Linear ratios over three fixed legs are one
  family. Other forms, such as lexicographic safety-first ordering, are a
  separate study.
- **Synthetic controls.** The boundary optimist is a constructed control, not
  evidence about how real models generalize.

## 8. Disclosed before running

- **Already-published EV4 figures.** The pre-registered EV4 profiles that
  overlap this grid, and their published figures:

  | Profile | Grid name | Optimist check |
  |---|---|---|
  | `p0-r20-a80` | `sr-a0.8-r0.2-g0` | 94 of 99 members at or below it |
  | `p0-r30-a70` | `sr-a0.7-r0.3-g0` | published in the EV4 report |
  | `p0-r40-a60` | `sr-a0.6-r0.4-g0` | published in the EV4 report |
  | `dar-p0-r100-a0` | `sr-a0-r0-g1` | catches it |
  | `dar-p0-r50-a50` | `sr-a0.5-r0-g0.5` | catches it |
  | `dar-p0-r30-a70` | `sr-a0.7-r0-g0.3` | 3 of 99 at or below it |

  These were seen in the EV4 report before this pre-registration. No other
  profile in the grid has been computed.
- **Ratios mixing all three legs** have not been evaluated before.

## 9. How it runs

```text
python -m carbon.battery.value.ratios --out docs/development/evidence/sr1-2026-10-02
```
