# SR-M1 — motor score-candidate study (registered before computing)

**Status:** REGISTERED. These definitions are committed and pushed before any candidate is computed on any panel.

**Authority:** the Test Lead's assignment of 2026-10-05, under TRACK-B-HARNESS-01 / OWNER-GRAPHITE-TEST-WAVE-01. DEVELOPMENT evidence only. Adopting any rule stays with the science owner. The frozen motor rule (`carbon/motor/exam.py`) is not edited. The study uses new modules only.

**Motivation:** the motor Q1 fixture panel (#601). The frozen rule's ranking had τ = ρ = 0 against decision quality. Its worst score went to a control that decides as well as KRR, and three unsafe deciders scored better.

## Notation (per scorable PRACTICE case)

- p, r: the predicted and reference 60-angle torque curves.
- m(x) = mean(x). The ripple is x − m(x). pp(x) = max(x) − min(x).
- rf(x) = pp(x) / m(x), the ripple fraction; it is infinite when m(x) ≤ 0, and the case is then capped as in `feasibility`.
- Scales, all population SD over OK TRAIN cases:
  - s_mean and s_ripple: the frozen rule's scales.
  - s_pp: the TRAIN pp(r).
- Feasibility limits L_rf = 0.30 and L_mt = 4.0 N·m: the motor study's synthetic §6 values, used only by M-C.
- The important region is J ≥ 10 A/mm² (exam `J_IMPORTANT`).
- Every score is a mean over scorable cases, with lower better. A combination is the mean of its listed per-case components, plus any aggregate-level term.

## Components

| Id | Per-case component | Definition |
| --- | --- | --- |
| mean | period-mean error | \|m(p) − m(r)\| / s_mean (the frozen rule's) |
| shape | ripple-shape error | RMS(ripple(p) − ripple(r)) / s_ripple (the frozen rule's) |
| amp | ripple-amplitude error (M-A1) | \|pp(p) − pp(r)\| / s_pp |
| shiftmin | phase-invariant shape error (M-A2) | the minimum over the 60 circular shifts k of RMS(roll(ripple(p), k) − ripple(r)), / s_ripple |
| dec | decision-aware error (M-C) | ( \|min(rf(p), 1) − min(rf(r), 1)\| / L_rf + \|m(p) − m(r)\| / L_mt ) / 2 |

**Aggregate-level term B (M-B).** max(0, b) / s_mean, where b is the important-region signed mean-torque bias: the mean of m(p) − m(r) over cases with J ≥ 10. It is exam D7's reported `important_mean_bias_nm`, now scored. Only optimism is charged: a positive bias promises torque the machine does not make.

## Candidates (registered)

| Id | Score |
| --- | --- |
| F0 | the frozen rule: mean(mean, shape) |
| A1 | mean(mean, amp) |
| A2 | mean(mean, shiftmin) |
| B | F0 + B |
| C | mean(dec) |
| A1B | A1 + B |
| A1C | mean(mean, amp, dec) |
| A1BC | A1C + B |
| A2B | A2 + B |

F0 is the baseline. No other candidate will be added after the computation without a new registration recorded as such.

## Panels (registered)

**Fixture panel (5):** `analytic-v1`, `learned-krr-v1`, `flat`, `phase-shifted` and `saturation-blind`, exactly as in #601.

**Widened development panel (16).** The fixture 5, plus 11 members built from public TRAIN only:
- ripple-amplitude scaling of the KRR curve, keeping its mean: α ∈ {0.5, 1.5, 2.0};
- mean-torque bias sweep: the KRR curve shifted by δ × its own mean, δ ∈ {−0.10, −0.05, +0.05, +0.10};
- KRR at registered-grid hyperparameters other than the selected (4.0, 1e-4): (length, ridge) ∈ {(2.0, 1e-4), (8.0, 1e-4), (4.0, 1e-2), (4.0, 1e-6)}.

**Decision value.** As in #601: Track B Q1 on the counted motor replay, fixed grid, 48 queries, ordered by `track_b.decision_value`, with TIE_DETERMINED safe selections ranking nothing.

## Statistics and claims (registered)

- **Per candidate and panel:** Kendall τ-b and Spearman ρ of −score against decision value; the SCORE_VALUE_DIVERGENCE count; top-1 and top-3 agreement.
- **Noise band.** The members are deterministic, so there is no seed band. The band comes from the score side instead: 2000 bootstrap resamples of the 30 PRACTICE cases (seed 0), recomputing every candidate's scores and τ. Decisions are fixed.
  - Report each candidate's τ 2.5–97.5% interval.
  - Report the paired interval of τ(candidate) − τ(F0).
- **Progress claim.** "Progress over F0" is said only when the paired 95% interval excludes 0. Even then it is descriptive: n ≤ 16, members are not independent, and the fixture controls were constructed by us.
- **Not promotable.** Nothing here is adopted. Confirmation requires Graphite's motor constructions and motor-graphite-confirmation-v1, under a frozen analysis.

## Scope

New modules only: `carbon/motor/score_candidates.py`, a script, tests and an evidence directory. No pinned file and no frozen rule is edited. No spend.
