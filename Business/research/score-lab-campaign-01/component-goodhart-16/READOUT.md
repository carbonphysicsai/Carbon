# Component Goodhart tranche: actual mixed-source development evidence

**SYNTHETIC DEVELOPMENT; no rule selected or adopted.** All sixteen predeclared
settings (baseline plus every subset of four existing example components) ran
against all ten pinned proxies. The corrected matrix has **112 measured rows
and 48 unscored rows**. Three prototype paths are unscored in every setting;
their missing outcomes are not zero regret or evidence of a scientific failure.

## Completed execution, repair and reuse

1. The original canonical run at `9311c584adaddb061e688cc3e0777c59bc2ade7e`
   passed controls and completed all sixteen commands: **407.266 CPU-s /
   407.506 wall-s**. It produced 56 measured and 104 unscored rows.
2. All eight cheap-containing settings were unscored because the physics panel
   lacked `control-bilinear`. This was a missing comparison input, not a
   measurement of the cheap-relative term's scientific effect. Every original
   byte is preserved in [PRE_REPAIR/IDENTITY.json](PRE_REPAIR/IDENTITY.json).
3. Source `fe2f33ca30a71be3797e4ebf2e5e432eeb24757e` connects the existing legacy
   scalar control to scoring-only inputs and supplies its own neighbour metadata.
   Canonical **167 tests**, Black and Ruff passed. The discriminating control
   failed before repair and passed after it; prefix/CVaR scope, parameter
   independence, value-question rejection and nonlegacy refusal are covered.
4. Only the eight affected cheap settings reran canonically, under the same
   caps: **289.945 CPU-s / 290.080 wall-s**. Each has seven measured rows and
   three unscored rows. The eight valid non-cheap settings retain source-9311
   bytes and their original 56 measurements; they were not repeated.

Component-tranche CLI analysis totals **697.211 CPU-s / 697.586 wall-s**.
Together with error64's 266.571 CPU-s, this is **963.782 CPU-s (0.268 CPU-h)**,
below the predeclared one-hour envelope. Image/bootstrap/export and regression
test costs are excluded from these command sums; peak RSS was not measured.
No cap fired, no solver/model rebuild or provider/pod/spend occurred.

The complete order and unchanged settings are in [PROSPECTIVE.json](PROSPECTIVE.json).
[MATRIX_INDEX.json](MATRIX_INDEX.json) identifies each result's file/hash and
original or repaired source. [SUMMARY.csv](SUMMARY.csv) retains all 160 statuses,
losses, gaps and available query counts. Both run directories have their own
source/artifact identities, status, controls and execution receipts. Source
versions are deliberately not flattened into a single purported run.

## Findings on this one toy setup

The buyer loss is the existing neighbourhood-blend value on the fixed analytic
problem. The oracle is a separate random-plus-coordinate search over the same
bounded trait grammar, **not a proven global optimum**. Its measured loss is
0.051654151 across these scored rows. Lower buyer loss is better.

| Proxy | Score-selected loss without CRPS | Score-selected loss with CRPS | Signed sampled gap without CRPS |
|---|---:|---:|---:|
| N1 decision relevance | 0.125525409 | 0.125525409 | +0.073871258 |
| N2 regret on pick | 0.051654151 | 0.051654151 | 0 |
| N3 safe pick x gain | 0.051654151 | 0.051654151 | 0 |
| N4 top-region ranking | 0.062309026 | 0.062309026 | +0.010654875 |
| V2 rev2 k1 / cost 0.05 | 0.051654151 | 0.051654151 | 0 |
| V2 rev2 k3 / cost 0.10 | 0.043320818 | 0.051654151 | -0.008333333 |
| V2 rev2 k5 / cost 0.25 | 0.043320818 | 0.043320818 | -0.008333333 |

The same table values hold with or without the other three configured
components. These are exact observed toy equalities, not powered equivalence.

- **The positive N1 and N4 Goodhart gaps persist.** None of these fixed example
  component settings improves their selected buyer value on this profile/seed.
- **Adding CRPS worsens k3's selected buyer loss by 0.008333333.** Its signed
  gap becomes zero because its selected loss moves up to the approximate
  oracle, not because it achieves better value. A smaller absolute sampled
  gap is not necessarily an improvement when the oracle is imperfect.
- **Gradient-sign and score-CVaR settings do not change selected value here.**
  This limited observation is not evidence of general ineffectiveness.
- **Adding the repaired cheap term leaves selected value unchanged in all
  56 matched scored pairs.** This has a structural explanation: with a fixed
  comparator grade b and weight w=0.25, the implemented transformation is
  `(1-w)*a + w*max(0,a-b)`. Its slopes are 0.75 and 1, so it preserves the
  base score ordering and unchanged gate/tier. It cannot repair that ordering's
  value inversions merely by adding this relative term. No new rule is proposed.

## Comparator applicability and cost limits

The adapter reuses `synthetic._predict("control-bilinear", ...)`, whose analytic
map observes **x=0, 0.5 and 1 at each context**. These anchor observations and
acquisition are uncharged in this toy comparison; no strongest-industry or
matched-workflow-cost claim follows. It is not an injected value oracle.

Only the existing legacy scalar problem keys are supported. Dimension, changed
objective family, roughness, explicit optima count/location, changed constraint
count/offset/coupling and other extensions fail closed. The comparator's response
stays the **frozen nominal legacy response under neighbour transformations**;
it is not claimed accurate for transformed objective/constraint/operating/boundary
truth. Its physics measurements remain unavailable (None), not imputed as zero.

Comparator forecasts and neighbour metadata are independent of searched member
parameters and use only S-/N-S- tasks. Prefix and CVaR compositions retain the
same scoring subset. Gate/FLOOR and score formulas remain unchanged.

Search effort settings are shared, but actual work is not equalized: measured
searches use 52, 68 or 84 score assessments and 54 value assessments. These
counters are outer search assessments, not full comparator/internal-scoring
or acquisition costs. Original unscored rows did not capture counters and
remain explicitly unavailable; repaired unscored rows record attempts. Nothing
is filled with an inferred query count or zero buyer loss.

## What remains unmeasured

This is one fixed analytic task and one search seed, with no uncertainty band
on cross-setting Goodhart differences. The four numerical inputs are unchanged
example ASSUMPTION values, not owner-adopted coefficients. No EV4 fitting,
realism calibration, physical model, independent holdout, final confirmation,
value-bar pass or scoring-rule selection ran. Real value-tracking evidence
still needs applicable registered references and a common question mask.
The holdout remains unopened; no hidden/AX42 data, chain or LIVE path was used.
