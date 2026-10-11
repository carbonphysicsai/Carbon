# Proposed rule and public-data acceptance design

**PROPOSED_NOT_ADOPTED.** Numerical inputs below are HUMAN_INPUT, with
ASSUMPTION sensitivity where useful. No sealed panel, solver or payout action
was run. The purpose is a small, real improvement winning with defensible
evidence, rather than guaranteed displacement after a tenure timer.

## Recommended first rule

**Nomination.** Keep mandatory admissibility, current identities and typed
failures. Use the screen to allocate scarce final compute, not establish a
takeover. Separate its cutoff from the final's useful-gain threshold. Admit
plausible small gains and near-ties whose uncertainty could include useful
improvement; use a declared queue/budget to prevent an unlimited final for every
copy. A lightweight paired screen on shared current cases is preferable when
available. Do not infer an uncertainty bound from a single aggregate. Screening
recall for genuine close improvements must be measured, not assumed.

**Freeze and pairing.** Freeze challenger/incumbent artifact, recipe, state,
worker/device, measurement, population, weighting and rule identities before
assigning fresh final material. Test the retained artifacts on the same inputs,
reference results and any matched inference randomness. Cases seen during
screening or nominee selection do not become independent confirmation. Keep
current stale-incumbent withdrawal, missing-evidence and infrastructure rules.
Deterministic paired resampling may use a published analysis seed; that seed is
not the hidden input-generation seed and never authorizes disclosure of it.

**Final contrast.** Use `D_i = loss_inc,i - loss_chal,i`, positive meaning better,
with the registered P/Q/w and a value-proven measurement. Require a lower
confidence bound above `delta_useful` and all independent mandatory gates.
`delta_useful` is the smallest gain worth accepting, specified in decision/loss
units. Zero is an option for “any evidenced positive gain”; a positive floor
needs value or numerical-resolution evidence. Avoid an arbitrary large relative
anti-copy margin. If a required stratum must not worsen, establish a declared
noninferiority bound; an insignificant adverse estimate is not proof of no harm.
Challenge owners retain every tolerance.

**First implementation should be fixed-horizon.** Predeclare one fresh final
panel per attempt, its dependency blocks and minimum resolution; use paired
cluster resampling for correlated case families. Insufficient power returns
INCONCLUSIVE and keeps the incumbent. A continuation is permitted only under a
predeclared fixed total horizon / alpha-spending plan with no tuning on interim
results. Ordinary percentile intervals inspected repeatedly do not provide
anytime error control. A later bounded-loss confidence sequence can accumulate
fresh blocks until its lower bound clears the useful gain or budget expires,
after public-data calibration of its assumptions.
[Time-uniform inference](https://arxiv.org/abs/1810.08240),
[finite-bank sampling without replacement](https://proceedings.neurips.cc/paper/2020/hash/e96c7de8f6390b1e6c71556e4e0a4959-Abstract.html).

**Multiple attempts.** Freeze a contender cohort before the fresh final; use a
predeclared familywise correction (Bonferroni is a conservative simple option;
shared-resample max-T needs validated exchangeability/dependence assumptions).
The hypothesis family includes repeated artifact digests, hotkeys and interim
looks, not only the winning hotkey. A per-window error allowance reset forever
does not bound lifetime false takeovers. Declare the scope of the error budget.
An auditable summable allocation is `alpha_j = alpha_total*6/(pi^2*j^2)` for
ordered attempts j; this is a **mathematical option**, not an adopted Carbon
parameter. It becomes conservative late in a long contest, so disclose that
power/entry trade-off. Dedup identical artifacts before consuming attempts;
grouping unrelated identities is a separate owner/security decision, not an
assumed Sybil solution. [Cohort correction analogue](https://github.com/TensorLink-AI/cascade/blob/0fba3c0dcfd38aa6f9901ba4a9ec3f4ec20d843e/cascade/eval/koth.py).

**Copying.** Canonical recipe/state identity catches exact copies including
equivalent serialization; retain earliest committed priority. Functional
similarity flags can prompt investigation but do not prove copying, theft or
failure of decision value. A distinct lawful construction that makes a small
real improvement should remain eligible. Require null, re-sharded and
near-copy controls to stay below the statistical takeover rule. Payout-clock
resets and rights enforcement remain separate policy. No extra incumbent
protection percentage is justified solely by a similarity flag.

**Disclosure and consensus.** Validators replay identical signed identities,
rules and analysis, with allowlisted aggregate verdicts. Keep all hidden seeds,
case IDs, references and reconstruction-sensitive state private. Roll out any
rule prospectively at an explicit version/activation boundary; no silent
historical rescore. A promotion does not itself establish payout or production
qualification. Carbon's existing [parity check](https://github.com/carbonphysicsai/Carbon/blob/43f664319e1c2f977908186d7a017f2eb0771251/carbon/challenge_validator/acceptance.py)
is the integration surface.

## Why this rule, rather than the alternatives

| Option | Close-gain entry | Statistical and operational cost | Recommendation |
|---|---|---|---|
| Keep the current percentage at both stages | Gains below the margin cannot win in the ideal limit | Cheap and stable; deterministic exclusion | Does not meet the owner's stated goal |
| Looser screen only, stored final | More final nominees; small gains still fail current final | Tests relevant artifacts but leaves point-margin barrier | Necessary design discussion, insufficient alone |
| Lower/zero margin, uncorrected repeated duels | Small gains can pass | Null copies get repeated lottery tickets | Reject as a rule set |
| Paired fixed-horizon with small useful-gain floor and attempt correction | Small gain can win if resolved | Needs enough independent blocks and final budget | Recommended first candidate |
| Calibrated accumulating confidence sequence | Small gain can accumulate evidence without repeated-peek inflation | More engineering; needs valid bounded-loss/dependence model; may run out of budget | Strong follow-on option |
| Tenure-decaying practical floor | Entrenched incumbent becomes easier to beat | Does not solve selection error; floor still excludes smaller gains | Optional economic/value policy, not necessary statistical protection |
| Two consecutive wins | Can protect against an isolated lucky result | Can unnecessarily lose power and adds latency; not automatic familywise control | Do not require by default; prefer one properly controlled final |

## How much evidence a close gain could need

No measured independent case/rebuild variance is supplied by this literature
survey. Illustrative **ASSUMPTION**, not an official sizing:

- Normalize incumbent loss to fixed low/base/high 1/1/1.
- Target useful true gain is fixed 0.01/0.01/0.01, with tested gain sensitivity
  low/base/high 0.005/0.01/0.02.
- Independent paired-difference SD low/base/high 0.03/0.05/0.10.
- One-sided alpha is fixed 0.025/0.025/0.025 and power fixed 0.80/0.80/0.80
  **HUMAN_INPUT scenarios**, not recommended production thresholds.

For an approximate independent normal mean test with `delta_useful=0`,
`n = ceil((1.959964 + 0.841621)^2 * sigma_D^2 / gain^2)`.
At the fixed 1% gain this is **71 / 197 / 785 independent units** for the SD
range. At base SD, gains 0.5% / 1% / 2% need **785 / 197 / 50 units**.
These calculations exclude multiplicity, clustering, weighting, heavy tails,
abstention, reference failure and regional gates; bootstrap validity must be
checked. If the target gain approaches a positive useful-gain floor, replace
gain with `gain-delta_useful`; budget diverges as that gap shrinks.

Pairing reduces variance only through covariance:
`Var(D)=Var(L_inc)+Var(L_chal)-2*Cov(L_inc,L_chal)`.
For equal marginal variances and correlation **ASSUMPTION** low/base/high
0/0.5/0.9, paired-to-unpaired variance is **1/0.5/0.1**. This is not a forecast
of compute savings: both models still infer, dependent bank cases reduce ESS,
and stored artifacts remove rebuild variability from the estimand rather than
measuring it. Fixed literature sample counts cannot determine Carbon's power.

## Acceptance panel to hand to Validator / Test Engineer

Use only committed public or explicitly synthetic stand-ins; final cases and
confirmation remain outside this research lane. Pre-register the variants and
report uncertainty on acceptance/rejection frequencies, not just mean rank.

| Public panel family | Compare | Required result / failure being tested |
|---|---|---|
| Exact/null and equivalent-serialization copies | Same predictions and state, re-sharded representations | Canonical dedup; no lucky takeover; a missing incumbent record never becomes an open crown |
| Small positive controls | Gain sensitivity 0.005/0.01/0.02, ASSUMPTION | Screen recall, final power and delay separately; show current rule's deterministic barrier |
| Recipe seed spread | Actual retained artifacts vs matched fresh rebuilds | Separate deployed-model merit from method repeatability; quantify any decision flip, do not select lucky rebuilds |
| Mandatory/important stratum regressions | Better aggregate, adverse local performance | Hard failure cannot be compensated; insufficient regional evidence remains unresolved |
| Correlated bank/source cases | Same distinct-case count, different source dependence | Compare case-IID vs cluster uncertainty; repeated exposure is not fresh n |
| Multiple challengers and hotkeys | Fixed unique artifact cohort plus duplicate attempts | Hold error allowance across the declared attempt family; compare selection-adjusted and unadjusted finals |
| Early looks / budget exhaustion | Fixed final vs predeclared continuation | No repeated-peek claim from ordinary bootstrap; exhausted close duel stays inconclusive |
| Validator parity / missing reference | Same signed evidence with altered/missing pins | Identical verdicts or typed refusal; infra/reference failure is not candidate inferiority |

Candidate values for screen admission, useful gain, alpha scope, dependency
blocks, n_max, repeatability requirement and no-harm bound remain **HUMAN_INPUT**.
Recommend selecting them on these public diagnostic curves, then freezing before
an independently authorized protected campaign. Research does not adopt them.
