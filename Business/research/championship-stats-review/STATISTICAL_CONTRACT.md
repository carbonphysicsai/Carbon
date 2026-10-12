# A coherent championship contract to give the Test Engineer

**PROPOSED_NOT_ADOPTED.** The daily schedule/N=3,000 is owner proposal context,
not a qualification or compute authorization. All production alpha, epsilon,
horizon, sample law, tolerances and admission limits remain HUMAN_INPUT.

## What counts as a hypothesis

Key a duel by incumbent artifact, contender artifact, measurement/rule version,
P/Q/w, strata, gate/reference identity and declared evidence horizon. Store the
immutable artifacts on both sides. A training-seed change, model update or new
incumbent creates a different hypothesis; previous evidence is not a duel against
the new incumbent. Exact duplicate hotkeys share that duel and its original
priority; many distinct artifacts still consume multiple-test allowance.

On a newly generated batch score both on the same inputs/references. For an
absolute loss floor test `X_i=L_inc,i-L_chal,i-epsilon_abs`. For a relative floor
test the linear contrast `X_i=(1-epsilon_rel)*L_inc,i-L_chal,i` directly, rather
than a ratio using an uncertain batch mean and an unadjusted SD. The null is
nonpositive mean under the registered population/weights and conditional model.
The SD summaries in paired.json divide by the average of pair means, whereas
relative takeover gain uses incumbent mean; align that normalization explicitly.

The test identifies **reference-relative accuracy gain**, unless the owner
registers and validates a decision-value contrast. Current v3 uses A-Q at
nomination, accuracy plus gate at finals. Accuracy must not be described as
verified design gain merely because its interval is positive.
[Owner's finals contract](https://github.com/carbonphysicsai/Carbon/blob/2cfc2508e267e1b794d32fa617603bcc7e122397/.agent/decisions/2026-10-11-OWNER-BATTERY-V3-FINALS-01.md).

## Choose one of these controlled routes

**Route A: fixed round first.** Freeze the eligible cohort before drawing each
fresh batch. Obtain valid one-sided p-values for each paired contrast; apply
actual Holm step-down. Only a rejected eligible contender can win, under a
predeclared deterministic selection/tie rule. Report selection-adjusted evidence,
not an ordinary unadjusted interval for the selected maximum. The important
region/no-harm rule and gate uncertainty are separately registered; hard failure
cannot be compensated by average accuracy. Insufficient evidence is inconclusive.

Allocate round levels across a declared campaign, including immediate fast-lane
tests. A fixed finite horizon can spend `alpha_campaign/T` per round; adaptive
allocations are possible if chosen predictably with their total bounded by the
same budget. An indefinite illustrative spending rule is
`alpha_t=alpha_campaign*6/(pi^2*t^2)`. This is a mathematical option, not an
owner constant. It becomes conservative late; daily reset controls a different
claim. Do not quietly call a daily 5% allowance a lifetime 5% guarantee.

**Route B: fixed-cohort anytime Holm.** Keep the same incumbent and committed
cohort for an epoch. Each pair has a valid e-process and running anytime p-value
`p*_j(t)=min(1,1/sup_(s<=t) E_j(s))`, with a qualified dependence/variance model.
Apply Holm to these anytime p-values under one fixed epoch allowance. Optional
stopping and common case correlation are permitted: if any true null is first
rejected, one true anytime p-value has crossed alpha/m0; the union over the m0
true nulls bounds that event by alpha. This reasoning requires a fixed family
and uniformly valid individual processes; it does not justify changing k,
incumbent or population and refunding budget. Stopped comparison evidence is
not reused as a new independent test. [Anytime foundations](https://arxiv.org/abs/2009.03167),
[Holm](https://stat.ethz.ch/R-manual/R-devel/library/stats/html/p.adjust.html).

For dynamic entrants, a simpler alternative is irrevocable per-duel allocation:
before any final observation assign beta_j with sum beta_j <= alpha_campaign,
then test each valid anytime process at its own beta_j. New entrants, incumbent
resets and fast lanes consume that same ledger; a loss/withdrawal does not refund
its tested allowance. Entry before the cohort freeze versus the next round is
explicit, and queue limits are operational policy, not scientific merit. Retain
the ledger across restarts and exact duplicates. A new cohort/epoch needs an
explicitly charged budget; it cannot reset total risk by changing its name.

**Alpha-investing is an alternative target, not a synonym.** Classic investing
can earn budget after discoveries and controls mFDR under its conditional
assumptions. It does not supply strong FWER for all mixtures of true and false
nulls. If the owner chooses that target, name it, specify the full wealth update,
reward rule and dependency conditions, and simulate adversaries harvesting
legitimate wins before spending on null entrants. m04.py implements none of
this. A claim about probability of any false takeover should use a compatible
FWER contract instead. [Foster and Stine](https://deanfoster.net/research/edc.pdf).

Do not layer ordinary daily Holm and a carry boundary as independent full-alpha
ways to win. Either use one unified anytime route, or budget their union
explicitly. A fixed-sample fast lane is included in that same risk family.

## Conditional evidence and retirement

Variance adaptation is not “replace known SD with today's sample SD.” Select
a theorem whose bounds/conditional assumptions match the measurement. A
bounded-loss empirical-Bernstein process needs an approved bound and correct
resampling unit; clipping unbounded losses changes the estimand and cannot be
silently introduced. For stratified cases, fixed quotas, weights and reference
failure handling must preserve the declared conditional mean/variance relation.
Use whole fresh source blocks if source dependence is present; plan power using
effective information, not raw case count. [Confidence sequence theory](https://arxiv.org/abs/1810.08240).

Retire a batch after the shared round for all adaptively submitted future
artifacts. All precommitted contenders can share it without pretending their
outcomes are independent. Carry accumulates **new** case/block evidence for the
same frozen pair. Repeated inference is not new n. Lower-bound disclosure is
richer than a single bit; no numeric reuse tolerance is justified by the supplied
analysis. Custody/disclosure rules remain owner/Validator decisions.

An incumbent that fails a gate or has unavailable reference evidence needs an
explicit typed policy; it is not an automatic open throne. Candidate gate
failure blocks promotion; infra failure is not candidate inferiority. Important
stratum noninferiority needs an actual declared bound, not “no significant harm.”

## Minimum useful gain epsilon

Consistent with #1105, **recommend owner consideration of epsilon=0 for the
DEVELOPMENT accuracy contrast**, meaning any reliably positive accuracy gain
may win subject to mandatory gates and the shared error budget. This is a
proposal with HUMAN_INPUT adoption, not a production scientific value. Zero
does not eliminate uncertainty, finite power or a necessary numerical-resolution
check; tied/inconclusive cases stay with the incumbent.

A positive floor should be derived from either an approved meaningful
decision-value improvement after equal-budget verification costs, or evidenced
reference/measurement resolution. No buyer-value conversion or minimum numerical
resolution has been supplied for this accuracy leg, so inventing 1–3% as its
useful-gain floor would confuse power with value.

Sensitivity **ASSUMPTION relative epsilon low/base/high = 0/0.001/0.005**
(0/0.1/0.5%). At N=3,000, sigma=0.46, k=5 and the M04 known-normal first-step
formula, DERIVED 80%-detection true gains become approximately
**2.661/2.761/3.161%**. These do not establish the power of a corrected combined
procedure, nor the buyer value of each epsilon. To accept smaller gains sooner,
measure covariance/stratum information, improve the variance model and increase
fresh information or change the schedule; do not make the final's old point
margin an unacknowledged second floor.

## Minimum acceptance panel

Public-only complete-rule simulation must include correct nulls, small positive
and harmful alternatives, cross-contender dependence, source/round dependence,
heavy/skewed tails, underestimated variance, changing incumbent, open/close/reopen
duels, duplicate and many distinct near-copy hotkeys, alpha exhaustion, multiple
winning contenders, fast-lane union, all gates and failed references. Preserve
adverse outcomes. Report campaign/daily/duel errors separately, with Monte Carlo
intervals, and power by stratum. No hypothesis family may be selected after
seeing its favorable results. Readiness/qualification remain separate.
