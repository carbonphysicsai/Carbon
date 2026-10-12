# Registry-v9 score-candidate attacks and Test Engineer protocol

**RES-02 / SCORE-CANDIDATE-ATTACKS-01. DEVELOPMENT public-data analysis.**
Historical EV4/EV5 outcomes are unchanged. Every result is traceable through
[results.json](results.json) and its immutable [source ledger](SOURCES.md).
The owner's description of failed sealed confirmation motivates this work;
this job neither accesses nor independently measures that confirmation.

## Evidence and estimands

The pinned registry has A, R, P, ARP, V3, ARP-V3, ENV/ARP, ENV/ARP-V3,
A-Q and the strict G-FEAS/A-Q>@0.05 sweep. Weights are **geometric**, not
arithmetic: [score_tuning.score_member](https://github.com/carbonphysicsai/Carbon/blob/fcab655b30f42d4e3a42786f22af8aa2b08402e2/carbon/battery/value/score_tuning.py)
calls the registered log/geometric combiner. ARP's weights are thirds;
ARP-V3's are quarters. The PR body's described value-first/near-tiebreak
superset is absent from the pinned registry bytes: DOCUMENTATION_LAG. No
unstored rule or threshold is invented. A later actual registry revision
requires a prospective version of the audit.

A=1/(1+E), R=1/(1+E_important) are reconstructed from public component
aggregates. Exact P needs per-case signed margins/proximity weights. ENV
needs the restricted scoring-case mask and margins; joint G-FEAS needs the
case-wise reference-any-FAIL/model-all-PASS mask. Per-constraint counts do
not reconstruct that intersection. Q3 q and the actual model's ordered
top-three Q3 choices are also absent. Scores requiring these fields remain
**NOT_MEASURABLE**, never a fabricated zero, one or substituted proxy.

For observations we report the historical available verification loss and
the previous #1073 diagnostic: a feasible pick's gap to the best certified
member of the finite action bank, divided by u and capped at one; no verified
return gives one. Reference unavailability/missing model output withholds
measurement. Registered-band UNRESOLVED, missed opportunity and settled
NONE_FEASIBLE remain different labels even when their diagnostic service
loss is one. This is a **single-pick service diagnostic, not registry V3**.

u=60/120/240 seconds is ASSUMPTION low/base/high sensitivity from the prior
audit; u=1200 seconds is a separate transfer sensitivity matching the new
Q3 source unit, not proof of equivalence of banks. Fixed finite counts and
point ranks have low=base=high as measurements; tied rank intervals show
the possible positions, not confidence. Scenario bands and toy parameter
ranges are not inferential CIs. No policy is selected by these reused data.

EV4 and EV5 each contain 99 eligible RECONSTRUCTED members and 12 offered
verification questions. Eligible totals with controls/attacks are 104 and
113. They share their scoring set and published A/R components for the real members: these are
not independent replications. EV4 has three settled NONE_FEASIBLE questions;
EV5 has three plus one UNRESOLVED family without a certified feasible action.
These affect no-return values and are reported explicitly.

## Candidate-specific exposure

| Candidate | Mechanism that needs testing | Public measurement / gap | Cheap check or prospective option |
| --- | --- | --- | --- |
| A | Reduce abundant/irrelevant output errors while keeping wrong boundary choices | Both boundary and sign-error controls outrank every real member; observed value inversions | Fixed ordered-list/reference-result intervention; report signed failures and independent decision value |
| R | Improve most important-region cases while hiding sparse, decision-critical sign failures | Boundary rank becomes 74; localized sign control remains above every real member | Worst-stratum and tail/sign diagnostics; keep localized known-bad controls, not only mean important-region accuracy |
| P | Pessimism has no optimism penalty; weakly penalized sparse optimism | Exact public p absent; one-sided formula gives p=1 for uniformly pessimistic toy margins | Always-cautious/missed-opportunity control plus paired feasible-return coverage; do not call P a proper/truthful score |
| ARP | A/R gains compensate poor decisions; P can reward caution | Actual p absent; geometric compensation shown by toy | Pre-register irrelevant-field/fixed-list invariance and localized optimism transforms; non-compensable scientific gates stay separate |
| V3 | Public-family memorization, missing-question omission or budget/commitment loopholes | Real k3 orders/LEG results absent | Frozen unique top-k, complete attempt accounting, all-offered denominator, registered LEG/VALUE separation; new variants for untouched confirmation |
| ARP-V3 | A/R/P credit raises blend without improving the verified list | Actual composite absent; fixed-list toy raises it while pure V3 is unchanged | Report score delta beside paired verified-value delta, not tau alone; consider decision-primary or bounded tie credit only if owner registers it |
| ENV/ARP | Mean optimism dilution, pessimism blindness and support restricted to envelope | ENV and p absent; public outer conditions and toy mean dilution expose coverage risk | All target strata/constraints and tail diagnostics; retain P/Q/w and limits rather than discard difficult strata |
| ENV/ARP-V3 | Same gate risks plus compensating field credit | Actual score absent; toy retains field-credit increase with V3 fixed | Both gate coverage and fixed-list checks; verify independently rather than infer safety from mean optimism |
| A-Q | q unchanged while A improves; question-family memorization | Exact Q3 q absent; positive geometric-credit derivative | Fixed-list/fixed-q counterfactual; independent VALUE questions, full coverage and regret |
| G-FEAS/A-Q>@0.05 | Spend finite allowed false accepts on the most valuable actions; game the strict boundary | Actual scoring joint FA absent; count allowance is exact; gate still passes at 0.05 | Count/denominator and per-stratum distributions; adversarial controls at/around registered comparison, no threshold adoption here |

The [P formula](https://github.com/carbonphysicsai/Carbon/blob/fcab655b30f42d4e3a42786f22af8aa2b08402e2/carbon/battery/value/score_candidates_b1.py)
charges max(0, predicted margin − reference margin), weighted by
1/(1+abs(reference margin)). The [ENV measure](https://github.com/carbonphysicsai/Carbon/blob/fcab655b30f42d4e3a42786f22af8aa2b08402e2/carbon/battery/value/admissibility.py)
is a mean optimism, not a maximum or a physical feasibility certificate.
Its one-sided nature makes conservative errors invisible. Admissibility of
a corresponding physical trajectory is untested by the abstract examples.

## Measured public adversarial placement

All ranks below use 99 real members **plus the individual listed control**;
they are not the all-control leaderboard, nor sealed-confirmation ranks.
Base diagnostic u=120 seconds; [raw outputs](results.json).

| Panel/member | A rank | R rank | Unsafe / offered V picks | Better-value real members with no higher R |
| --- | --- | --- | --- | --- |
| EV4 boundary optimist | 1 | 74 | 8 / 12 | 21 |
| EV5 boundary optimist | 1 | 74 | 8 / 12 | 22 |
| EV4 localized sign error | 1 | 1 | 4 / 12 | 92 |
| EV5 localized sign error | 1 | 1 | 4 / 12 | 89 |
| EV5 steps-b | see results | 5–6 | 1 / 12 | 43 |
| EV5 width-b | see results | 11–12 | 1 / 12 | 4 |

The sign-error control has E=0.0077153183 and E_important=0.0393952585,
yet four unsafe choices. Its source near-plating count is 70/74 in the
prior public classification record; the joint scoring-set FA is still
unmeasured. Important-region accuracy is useful but not sufficient.

Against full diagnostic service value on the real members, tau is:

| Panel/rule | u=60 (low unit) | u=120 (base unit) | u=240 (high unit) |
| --- | --- | --- | --- |
| EV4 A | 0.259074 | 0.234607 | 0.175904 |
| EV4 R | 0.262869 | 0.235440 | 0.179234 |
| EV5 A | 0.478629 | 0.475247 | 0.471798 |
| EV5 R | 0.483337 | 0.479930 | 0.478578 |

These are deterministic descriptive point estimates under the sensitivity
units, not independent significance tests or fresh proof that R is superior.
Historical-loss tau is also retained; it has a different denominator and
failure treatment. Near ties in transformed floating-point scores are ties
in this audit; no lexicographic recipe advantage is introduced.

Six of twelve public V conditions lie outside ENV's temperature/SOC range
(5–34 degrees C; SOC 0.12–0.48, source-defined). They account for 65/81 EV4
and 145/183 EV5 unsafe picks across **all eligible** members. This diagnostic
uses public condition identifiers only, ignores c1/c2, and is **not an ENV
gate verdict** or a counterfactual safety-recall estimate. It shows why the
gate's support must be checked against the entire claimed decision family.

## Quantified structural stress tests

All examples here are **ASSUMPTION, synthetic, non-production**. They are
neither trained attacks nor reconstructed battery trajectories. The toy
leg assignments isolate the registered algebra; physical eligibility and
the realizability of a raw prediction transform must be tested separately.

1. **Over-caution:** toy margin bias low/base/high 2/4/8 bands produces
   p=1, ENV optimism=0 and zero predicted-feasible choices. Verified-service
   loss is one versus zero for truthful choices. Thus neither quantity
   distinguishes useful return from an unnecessarily empty list by itself.
2. **Concentrated boundary optimism:** 100 failed toy scoring cases plus a
   safe fallback; five failures are flipped. Epsilon low/base/high
   0.01/0.05/0.1 toy bands. Removing an assumed harmless extra-field error
   (0.1) while making those flips raises A/R and ARP/ENV-ARP, despite a
   top-three list with no verified feasible return. At base epsilon, ARP
   rises 0.938436→0.995074 while service loss rises 0→1. ENV mean is only
   0.004950 bands, and strict G-FEAS allows 5/100. This toy **does not**
   defeat V3 or A-Q: V3 falls 1→0.5 and their blends fall in this example.
   A passing gate is not enough; retain that negative attack result.
3. **Fixed-list field credit:** retained toy E low/base/high 0/0.5/1,
   with ordered actions, all verifier outcomes, r/p/q and gates fixed.
   At the half-error point, A increases 0.119048, ARP 0.040618,
   ARP-V3 0.028434, A-Q 0.052453; V3/R/P increase zero. The real-member
   scalar-E counterfactual increases A for all 99 members, with gain
   min/median/max 0.023593/0.030656/0.086821, decisions frozen. The latter
   is aggregate algebra, **not proof of achievable easy-only retraining**.
4. **Shortlist padding:** with k=3 and three failed first actions, fixed
   replay returns full regret. A deliberately broken failure-skipping
   evaluator can reach a fourth safe action and return zero regret after
   four attempts. The correct toy refuses overlength/duplicates. This is
   a harness mutation control, **not a discovered current verifier bug**.
5. **Copy/clone pool distortion:** assumed additional identical boundary-
   control rows low/base/high 0/10/100. EV5 R tau changes
   0.481328/0.492701/0.526279 while every unique artifact's score and value
   are unchanged. A tau changes 0.446308/0.211158/−0.481905. This stresses
   the score-proof statistic, not an individual model score or an observed
   copy/Sybil rate. Seed replicas already have dependence; artifact/recipe
   views and a frozen pool are necessary, not a similarity-score penalty.

Finite gate arithmetic on **sourced per-constraint** denominators 67 and
74: strict rejection above cutoffs low/base/high 0.005/0.02/0.05 permits
0/1/3 false accepts. These are not the joint G-FEAS denominator. For the
**assumed** denominator 100, exactly 0.05 permits five under `>` but four
under `>=`. Existing comparator authority is preserved; cutoffs are not
selected from this stress test.

## Pre-register three cheap detector bundles

**D1 — paired decision invariance and signed failure controls.** Freeze the
base artifact, allowed prediction transform, ordered actions, question
cohort and independent references. Test localized optimism, conservative
abstention and irrelevant-field improvement. Record score delta, return
loss/gap delta, unsafe/UNRESOLVED/missed-opportunity counts, offer/return
coverage and margins by each registered stratum. Pure V3 must be identical
if its exact ordered lists and all independent outcomes are identical.
Blends' positive accuracy credit is an expected mechanism to evaluate,
not automatically scientific fraud. A non-significant value difference
is not equivalence; freeze a no-useful-gain/equivalence region and alpha
before testing (HUMAN_INPUT), with paired recipe/question resampling and
the score-proof multiplicity plan.

**D2 — immutable list and budget mutations.** Reuse the existing
[verifier](https://github.com/carbonphysicsai/Carbon/blob/fcab655b30f42d4e3a42786f22af8aa2b08402e2/carbon/design_search/verify_aware.py):
it already checks duplicate/out-of-family actions, length≤k, bound digests,
independent receipts and charges each attempted complete panel. Pre-register
mutations that disable each guard; require tests to detect them. The
[Q3 wrapper](https://github.com/carbonphysicsai/Carbon/blob/fcab655b30f42d4e3a42786f22af8aa2b08402e2/carbon/battery/value/verify_quiz.py)
uses k=1/3/5, 120 s per complete panel and 1200 s regret unit (source
points), and explicitly reports uncharged inference overhead. Log actual
startup/inference/search time and out-of-allotment references separately;
any policy change is the owner's, not a retroactive rescore. Missing
reference is infrastructure/evidence failure, never fabricated candidate
loss. Retain all offered questions and full denominators.

**D3 — fold/support and pool integrity.** Enforce the registered public
[LEG/VALUE split](https://github.com/carbonphysicsai/Carbon/blob/e99881523712d2a8969a003a7ffcdd99641f1d01/docs/development/evidence/battery-score-tuning/public-dev-split-v1.json)
before any new draw and disallow overlap. Hash splitting by scenario does
not ensure semantic independence of near-identical conditions or erase
previous adaptive data reuse. Audit source-family/condition overlap and
the target P versus proposal Q and weights w. Report ENV support per
stratum; do not narrow P or relax limits to rescue a candidate. Freeze the
distinct model/recipe/seed pool, show the canonical per-artifact view plus
seed sensitivity, and run row-cloning as a diagnostic. Exact digest reuse
and residual correlations may trigger attribution investigation; similarity
never becomes an invented scientific score, and copying/IP dispositions
and false-positive thresholds remain HUMAN_INPUT.

These checks replay already-retained public/selection outputs and need no
additional reference solves. Work is linear in prediction/list records
plus the chosen resampling. Operational CPU-hours are UNMEASURED; no
fabricated price claim. The handoff specifies the missing public fields.

## Literature and interpretation

[Hardt et al., Strategic Classification](https://arxiv.org/abs/1506.06980)
formalize strategic responses to a known decision rule. Applying that idea
to Carbon means testing the announced gate and reward, rather than assuming
its old error distribution persists. This is an analogy, not their theorem
proving these battery attacks.

[Dwork et al., adaptive analysis and holdout reuse](https://arxiv.org/abs/1506.02629)
show why repeated feedback can overfit held-out data. LEG/VALUE separation
addresses direct reuse within one measurement; it is not their reusable-
holdout algorithm and supplies no unlimited-adaptivity guarantee.

[Tramèr et al., model extraction](https://www.usenix.org/conference/usenixsecurity16/technical-sessions/presentation/tramer)
demonstrate extraction through prediction APIs for several model classes.
They do not give a Carbon neural-operator copy success rate or prove
attribution from matching outputs. No live service is queried here.

## Maturity and validation

Public aggregate measurements and abstract counterexamples are implemented
and diagnostically tested; the new research-only CPU collector exercises
the controls in canonical CI. They do not earn scientific qualification,
calibration, production attack resistance, a selected score or economic
authority. P/ENV/Q3/V3 joint measurements and a prospective public attack
reconstruction remain missing. Test Engineer owns the actual proof; owner
owns thresholds and adoption. Research hands off and stops after RES-02.
