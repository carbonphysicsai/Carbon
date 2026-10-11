# Attack surface and preregistered checks

## Evidence boundary

This is an offline measurement of committed public synthetic EV4/EV5 outcomes,
not an official rescore. [Source manifest](SOURCES.md) pins inputs. A is
1/(1+E), which has the same ordering as historical CE=-E but different units.
VERIFY-R k=1 uses #1073's prospective bounded service regret: verified feasible
gap/u, capped at 1; no verified return gives 1. Settled NONE_FEASIBLE,
reference-band UNRESOLVED and missed opportunities remain separate labels.
Reference unavailability gives no numeric score. Best-in-finite-bank is not
a global optimum; oracle controls can be penalized when zero-band picks land
inside the registered unresolved reference band. Preserve that adverse result.

Every observed point/count is reproducible in [results.json](results.json).
Low/base/high u=60/120/240 s is ASSUMPTION sensitivity; base equals the
historical minimum-useful improvement, not a new buyer utility. Observed
rank ranges arise from ties. No confidence intervals or causal effect is
inferred from these attacks' observational placement.

## Candidate-specific exposure

| Candidate | Score-without-value mechanism | What the public evidence establishes | Proposed check / fix |
| --- | --- | --- | --- |
| A accuracy-alone | Improve abundant easy points, leave boundary decisions bad; optimistic local sign errors occupy little whole-field mass | Both boundary and sign-error controls rank above every real member in EV4 and EV5. EV5 sign control makes 4 unsafe single picks; E=0.007715 despite near-plating FA=70/74 | Keep accuracy descriptive or as an independently justified mandatory gate; grade verified service value separately. Never infer safety from E |
| A-Q+G-FEAS@0.05 | Hold q and the gate fixed while improving unrelated accuracy; concentrate allowed FA on high-utility boundary cases; fit the exposed gate | For a passing gate and fixed q, sqrt(a*q) strictly rises when E falls. Actual q and joint GF absent, so exact attack rank is unmeasured | Fixed-list A perturbation and high-value boundary controls; worst-stratum joint FA report; paired held-out decision value |
| G-PLATE/A-Q | Same blend attack; hide thermal violations or joint failures outside the plating denominator | Plating FA cannot establish thermal safety. Existing #1059 shows unsafe steps-b survives a zero-near-FA diagnostic; exact A-Q rank unavailable | Include all mandatory constraints, joint false-feasible, and worst-stratum/constraint diagnostics; do not relabel the plating gate as a full safety gate |
| Tighter G-FEAS/A-Q | Discrete gate cliff, conservative abstention near cutoff, errors just outside enriched zone, held-out failure despite zero observed FA | Tightening a finite sample cannot prove zero deployment risk. No prediction-margin curve can be rebuilt from these aggregates | Report count/denominator, uncertainty and abstention coverage; independent value panel; fit calibration on a separate fold, lock before confirmation |
| VERIFY-R | Memorize decision scenarios; exploit incomplete verifier; pad list if evaluator skips duplicates/failures for free; claim extra search budget; easy-question selective omission | Unsafe delivery becomes no-return under complete reference verification. Width-b has 4 observed inversions, steps-b 27; genuine k>1 orders and cost absent | Frozen unique top-k, fixed complete-panel attempt/core/wall budget, all offered questions retained, missing reference separated, no gratis retries; untouched decision variants |

For the joint GF owner rule, its denominator is reference-infeasible
**cases on the scoring set**, never decision scenarios or individual
constraint calls. Per-constraint 74 plating FAILs and 67 temperature FAILs
are different denominators; their intersections are not public. Do not sum
them to fabricate joint GF. Registered strict `>` and historical `>=` are
both tested prospectively, with the owner retaining comparison authority.

Integer gate sensitivity (mathematical derivation on sourced denominators):
at 74 FAILs, cutoffs low/base/high 0.005/0.02/0.05 allow 0/1/3 false accepts
under strict `>` rejection. At 67 FAILs they also allow 0/1/3. A rate of
0.05 on a hypothetical 100 failures passes with 5 errors for `>`, but only
4 for `>=` (ASSUMPTION denominator, structural test). No production cutoff
is recommended from these counts alone. Tighter cutoff's effectiveness and
false rejection require complete independent fields; #1059's recall curves
remain the authoritative public descriptive sweep, not a new adoption.

## Measurements and what they cannot prove

Full-panel tau with verification service value, at u=120 s:
EV4 A=0.23461, VERIFY-R=0.33120; EV5 A=0.47525, VERIFY-R=0.15103.
VERIFY-R is not demonstrated superior in rank agreement. #1073's crossed
recipe-by-condition sensitivity interval for EV5 spans -0.045 to 0.325.
Safety of the returned action under the reference contract differs from
population rank quality. Keep both, including this weak correlation.

EV5 boundary optimist: A rank 1, 95 real members have better V value without
higher A score; largest bounded-loss difference 0.40985. Sign-error: A rank
1, 89 such inversions, largest difference 0.32652. VERIFY-R demotes them
to 96–97 and 94–95, but leaves 1 and 3 inversions respectively. Width-b:
VERIFY-R 6–10, 4 inversions, maximum gap 0.08333. Steps-b: 44–54, 27
inversions, maximum gap 0.16667. EV4 full-D controls lack coverage; their
VERIFY-R ranks are withheld, not set to worst. EV4 A still ranks both unsafe
controls first (94 and 92 inversions). These are member point comparisons,
not seed-independent repetitions or evidence an attack caused improvement.

With all historical decisions frozen, retained-error low/base/high
0/0.5/1 (ASSUMPTION interventions), A gains for all real members at the first
two settings and none at the third. At 0.5, both panels' min/median/max gain
is 0.02359/0.03066/0.08682: EV4/EV5 share their scoring set. Pure VERIFY-R
gain is exactly zero. sqrt(a*q) gain is positive whenever q>0, gate passes,
and E decreases. Public aggregates cannot show that *easy-only* retraining
achieves this change; request per-case error contributions and frozen raw
lists on the selection fold. Never manufacture those fields here.

## Prospective adversarial protocol for #1044

1. Lock real members, seeds, D/selection/confirmation folds, action family,
   reference policy, list length k, attempt/core/wall budgets, u, all weights
   and gates before confirmation. k low/base/high 1/3/5 is ASSUMPTION
   sensitivity from #1073, not a production choice.
2. Create public development attack transforms only: optimism on signed
   thermal/plating margins; move just inside/outside gate enrichment;
   conservative abstention; preserve decision ranks while replacing easy
   region predictions; repeat actions, pad to k, insert unavailable/slow
   candidates; apply reference-band-aware oracle and always-abstain controls.
   Attacker owns permitted reconstruction; research runs none.
3. For each base/transform pair report score delta, independent verified
   regret delta, unsafe/no-return counts, coverage, attempts/core/wall,
   per-stratum denominators and worst-stratum behavior. Report unmeasurable
   fields and failed infrastructure separately. Use paired recipe/question
   bootstrap already designed in #1045/#1055. Multiplicity control and
   meaningful delta thresholds remain HUMAN_INPUT; all attempts stay in the
   log, including non-improving transforms.
4. Cheap detectors: fixed-list score invariance for a decision-only rule
   (exact algebraic expectation); list uniqueness/family membership and
   commitment identity; budget accounting on every attempted complete panel;
   unchanged ordered list under irrelevant field transforms; no missing-
   question denominator shrinkage; joint/constraint FA, abstention and margin
   histograms by registered stratum. Use already solved cases: O(member ×
   public cases) arithmetic, no new reference solves. Actual run time is
   UNMEASURED, not a fabricated CPU-hours claim.
5. Confirmation variant generation and thresholds are Test/owner authority.
   A large score delta with a statistically unresolved value delta is an
   alert, not proof that value is unchanged. Define an equivalence/no-gain
   region before inspecting confirmation; do not confuse p>alpha with no
   value gain. Whole-test unsafe recall never qualifies a physical model.

## Copying and literature

Copying an equally useful model does not by itself raise design score at
fixed decisions; it can multiply identities or bypass construction discovery.
Separate scientific merit from attribution, participation policy and IP.
Public prediction digests identify bytes, not authorship. No copying
prevalence is identifiable from public summaries; bundles stay host-only.
Compare permitted recipe/artifact digests first, then evaluator-held output
residual correlations on fresh allowed probe cases as an investigation.
Threshold, false-positive calibration on independent similar models, appeal
process and economic treatment are HUMAN_INPUT. Shared physics, training
data and architectures can create correlations; do not penalize similarity
as official scientific score (invariant 11).

[Hardt et al.](https://arxiv.org/abs/1506.06980) formalize strategic response
to a classifier; this motivates testing the gate miners observe, not assuming
its historical error stays fixed. [Gneiting and Raftery](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf)
prove propriety for probabilistic forecasts under specified scores. That
does not make deterministic A-Q blends, finite hard gates or winner contests
truthful, nor guarantee decision-optimal actions. [Guan et al.](https://papers.nips.cc/paper_files/paper/2022/hash/ed189de2611f200bd4c2ab30c576e99e-Abstract-Conference.html)
test sample-correlation fingerprints on neural classifiers; applying them
to physical regressors is a proposal requiring a calibrated null, not
established Carbon copy detection.
