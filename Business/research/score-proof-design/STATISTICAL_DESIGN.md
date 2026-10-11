# Statistics design for proving score-to-decision alignment

**SCORE-PROOF-DESIGN-01. Research and specification only. DEVELOPMENT; NOT_RUN.**

The scientific owner decides acceptance and adopts any rule. This proposal supplies analysis choices for the Test Engineer's SCORE-PROOF-01; it does not edit that ticket, the rescorer, registry, validator or Challenge. No references, predictions, sealed tuning state, exam material or AX42 were accessed. Read-only source inspection and analytic sample-size arithmetic are the only computation performed.

## Evidence boundary and current implementation

Authority begins with [Business Canon](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/Business/Business_Canon.md), [Constitution](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/CONSTITUTION.md) and [invariants](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/.agent/INVARIANTS.md). Scientific admissibility precedes ranking; reference failure is separate; reconstruction seeds do not create independent recipes; a Challenge score does not acquire cross-Challenge comparability.

The source snapshot is main commit `fb47eb5725338a7733f6074650e58271c355006b`. The [source inventory](SOURCES.md) records blob identities. These are code/contract observations, not results of SCORE-PROOF-01:

| Source | What it currently establishes | Consequence for this design |
| --- | --- | --- |
| [tuning_rescore.py](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/scripts/dev/battery/tuning_rescore.py) | Actual REGISTRY points to registry-v4, despite a stale registry-v2 docstring. Values come from DEVELOPMENT decision results; optional q3_regret is supplied separately. The sealed work-directory route reads operator material. | Pin the actual route. This research never invokes it. The authorized Test Engineer must establish provenance and independence of its inputs. |
| [registry-v4](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/docs/development/evidence/battery-score-tuning/registry-v4.json) | 17 fixed rules plus 14 sweeps with 8 cutoffs each: 129 expanded configurations, 128 non-CE contrasts. | Count expanded configurations in the comparison family, not only registry rows. No cutoff is adopted here. |
| [score_tuning.py](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/carbon/battery/value/score_tuning.py) | Higher score is better; decision_values averages lower-is-better loss on a common resolved scenario mask. Gated failures receive a floor below passing scores. D and other q rules use Q3-derived regret; stable rules use recipe seed means. | Audit q outcome separation; disclose common-mask exclusions; preserve v4 gate semantics. A floor can make an all-failed panel appear ranked: require NONE_ELIGIBLE rather than deploy its arbitrary top member. |
| [score_candidates_b1.py](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/carbon/battery/value/score_candidates_b1.py) | tau_seed_band and paired delta bands are percentile ranges over one-seed-per-recipe panels. | Useful seed sensitivity. They are not bootstrap CIs over new recipes and new questions. Do not silently relabel them. |
| [score_value.py](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/carbon/design_search/score_value.py) | Tie-aware Kendall tau-b; null/None for undefined agreement. | Reuse its mathematical convention, with explicit missingness and tie counts. |
| [EV4 contract](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json) | DEVELOPMENT preferences, reference bands, independent development/verification intent and historical paired-bootstrap hypothesis. Time to CV onset is measured; SOC/current and v3 target-SOC job are unavailable. | Carry historical evidence under its original contract. A new score-proof protocol is prospective and cannot claim to validate the v3 job by renaming EV4. |

### Integration with the Test Engineer's open PR

A later read-only check found [SCORE-PROOF-01 #1044](https://github.com/carbonphysicsai/Carbon/pull/1044), at head `83b03b7c8f883ee73403ee33f2fbf04f9bc84e93`, still open at inspection. Its public [registry-v5](https://github.com/carbonphysicsai/Carbon/blob/83b03b7c8f883ee73403ee33f2fbf04f9bc84e93/docs/development/evidence/battery-score-tuning/registry-v5.json) adds one fixed rule to v4: **130 expanded rules, 129 contrasts** if all are compared to its in-force baseline. Its implementation names `G-FEAS/A-Q>@0.05` as the rule in force. This is a source observation, not this researcher adopting a cutoff. The v4/CE calculations below answer the requested pinned design; an executor using v5 must pin it, name that actual baseline, and recompute its comparison family. Historical v4 comparison conventions cannot be silently rewritten.

The [public member manifest](https://github.com/carbonphysicsai/Carbon/blob/83b03b7c8f883ee73403ee33f2fbf04f9bc84e93/docs/development/evidence/battery-score-tuning/proof-members-v1.json) defines **construction Levels 0–4**, distinct from the illustrative quality bands below. Controls join every level as anchors. They must not count as independent real recipes for power or the primary bootstrap; their placement remains a separate required endpoint. The PR description reports public stand-in plumbing with all members at Level 0 and no members yet for Levels 1–4; this research did not rerun or validate that report.

For a claim with the requested precision **at each construction level**, apply the full sample calculation separately to each level. Under the base joint assumptions below, that is **1,117 independent recipes at each tested level**, evaluated on **628 independent questions**. The same questions may be shared across levels for paired comparison, so do not automatically multiply question/reference cost by the number of levels. A pooled result may be dominated by Level 0 and cannot fill empty higher-level cells. Level-family and rule-family multiplicity must both be declared if all levels are confirmatory; base counts below are for one contrast at one level, before that adjustment. Aggregating across levels requires preregistered level weights; extrapolation to missing levels stays a gap.

The [proposed score_proof source](https://github.com/carbonphysicsai/Carbon/blob/83b03b7c8f883ee73403ee33f2fbf04f9bc84e93/carbon/battery/value/score_proof.py) supplies a recipe bootstrap, development scenario-fold diagnostics and adversarial divergence. This design asks for additional question/scoring-case uncertainty, control separation, outcome-independent q evidence, confirmatory holdout and multiplicity. Existing fold sensitivity or an observed divergent attacker is useful DEVELOPMENT evidence; neither substitutes for those confirmations. No owner-run sheet, sealed run or execution state was read.

All sourced fixed counts/identities in this proposal have low=base=high; this signifies a source fact, not absence of scientific uncertainty. Planning ranges below are labelled ASSUMPTION. Mathematical constants are definitions. Owner-requested precision/effect targets are planning targets, not pass thresholds.

## What the experiment is estimating

Freeze the intended use: a rule selects a model to select designs for a declared battery decision family. Keep population P, sampling/proposal Q and value/evidence weights w separate. If the recipe panel is deliberately curated, the primary estimand is **alignment on this declared finite panel and declared decision distribution**. Bootstrapping cannot convert that panel into a random sample of every future miner model.

A member is one reconstruction of a recipe. A recipe is a model-construction family, including close architecture/hyperparameter relatives in a predeclared grouping. A complete decision question is one operating condition/brief, its whole candidate action set, reference feasibility calls, and fallback. Protocol alternatives, time points and multiple outputs within that question are not independent questions. Strata are the packet's registered groups; proposed new quality bands are only sampling/diagnostic labels.

For member m and question j, store the model-chosen action a_mj, reference-verified outcome class, resolved loss L_mj, fallback used, selected-action false-feasibility and reference availability. Define V_m = -sum_j(w_j L_mj)/sum_j w_j on the declared resolved mask for numeric alignment: higher V and score S are both better. Reference uncertainty remains UNRESOLVED; missing reference is REFERENCE_UNAVAILABLE. NONE_FEASIBLE and NONE_ELIGIBLE are distinct and must retain their contract's fallback semantics.

Safety is a separate outcome class and mandatory reporting dimension. Keep the historical EV4 numeric mistake costs only when reporting EV4; they are provisional preferences, not customer valuation or universal safety tradeoffs. If a new packet uses lexicographic outcome classes, use its class ordering and within-class value without inventing a dollar or finite failure penalty. Report feasible-only numeric regret separately from infeasible selections and fallback mistakes.

Primary recipe-level reporting uses a predeclared seed aggregation matching intended deployment (for example expected reconstruction performance, not the most favorable seed). Also report individual-member and one-seed-per-recipe sensitivity. Average seed performance must not hide a seed's hard failure: publish worst-seed safety outcomes. Group close relatives in uncertainty/folds; if only purposive families are available, state the inference is conditional on them.

## Required endpoints

| Endpoint | Definition and reporting | What it cannot prove |
| --- | --- | --- |
| Rank agreement | tau-b(S,V) on the fixed common assessable pool; concordant/discordant pairs, score ties, value ties, double ties and usable recipe count. Report all-outcome class ordering and feasible-only sensitivity where applicable. Spearman rho is secondary. | Association alone does not establish that the winner is safe or useful. A large set of poor models can make tau look strong while ordering at the frontier is wrong. |
| Paired rule comparison | Delta = tau-b(S_A,V) - tau-b(S_B,V), using identical recipes, cases, weights and resampling indices. CI for Delta itself, never subtraction of independent CI endpoints. | Failure to reject zero is UNRESOLVED; it does not establish equivalence. An interval excluding zero does not establish a practically sufficient gain. |
| Known-bad controls | Predeclare each failure mechanism and expected placement relative to admissible real recipes; report rank, gate verdict, tied ranks, top-k inclusion, and whether it outranks a good decider. Analyze controls separately from the primary random-recipe pool. | Purposive controls are falsification probes, not independent random observations that boost power. One correctly placed bad control is not universal defense. |
| Top-k regret | For the frozen score slate A_k, deployment loss minus the lowest loss available among admissible models in the same finite panel. Primary top-1 deployment regret; optionally slate-best regret min_(m in A_k)L_m - min_(m in panel)L_m, explicitly requiring reference checks of k models. | Slate-best regret is an optimistic acquisition metric, not what an unchecked random slate member will deliver. The panel's best is not the best possible model. |
| Gate recall | Two separate quantities: question-level unsafe selections detected/unsafe selections reference verified; and model-level unsafe members rejected/unsafe members labelled by the independent safety panel. Report false rejects, reference exclusions and each stratum's counts. | An undefined denominator is NOT_IDENTIFIABLE, never perfect recall. Pooling many failures from one model does not make many independent safety trials. |
| Frontier performance | Tau, top-1 regret, feasible decision gain versus the same cheap/solver-alone comparator, fallback rate and false-feasible rate within declared competitive/frontier groups. | Overall tau must not replace decision-level gain or the equal-budget value test. Comparator/search budgets must be matched and independently specified. |

Deployment k, useful regret reduction, acceptable tau, gate recall and permitted failure rates are **HUMAN_INPUT**. Illustrative k planning is low/base/high **1/3/5 (ASSUMPTION)**, with top-1 always reported; this does not change a question's action count.

Use a common assessment mask fixed by reference availability and a predeclared missing-prediction rule. Missing model predictions cannot be dropped to improve alignment. If the current all-member resolved mask shrinks when a bad member is added, show that shrinkage and repeat on a fixed reference-resolved universe under the existing missing-output treatment; do not silently change the historical measure. Publish losses/exclusions by rule and stratum so apparent improvement through removal is visible.

## Paired crossed resampling, with honest limitations

Use a recipe-by-question array, retaining seeds nested within recipe and all actions/outputs within question. At each replicate:

1. Sample recipe clusters with replacement; sample question clusters with replacement within registered strata, independently of the recipe draw. Carry all members/seed records of each selected recipe. Represent repeated recipe draws as distinct sampling units so dictionary keys do not erase multiplicity.
2. Apply the same draws to every rule, comparator and outcome. If scoring cases are random for the target estimand, resample their clusters as a **separate, disjoint** scoring set and recompute score legs/gates. Pair those scoring draws across rules; never merge them with decision-outcome cases. If scoring cases are fixed, state that the interval conditions on that scoring set.
3. Recompute question-weighted values, declared seed aggregation, gates, eligibility, ranks, deployment choices, tau and regret. A question always retains its entire action slate and reference status. Keep controls fixed as a separate panel, rather than resampling them as purported recipe discoveries.
4. Record tau_A, tau_B, their paired Delta, regrets and safety endpoints. Never substitute zero when tau is undefined; report undefined replicate fraction and reason.
5. Report a joint recipe/question interval and conditional recipe-only and question-only sensitivity intervals. Keep the existing seed band as another distinct display. Monte Carlo interval stability is checked by a second resampling seed/increased replicate count, without acquiring new physics evidence.

This adapts crossed-row/column resampling from [Owen](https://arxiv.org/abs/0712.1111) and [Owen–Eckles](https://arxiv.org/abs/1106.2125); their guarantees for mean statistics do **not** automatically prove coverage for gated tau-b, argmin decisions or a purposive panel. [Efron–Tibshirani](https://doi.org/10.1214/ss/1177013815) motivates bootstrap uncertainty generally. Require a statistical coverage check using public/synthetic statistical arrays and tie/gate scenarios before relying on this interval. The check does not need a physics solver.

A percentile interval is the continuity option for the existing EV4 contract, not a universal coverage guarantee. A studentized/jackknife interval is a sensitivity option after checking influence stability; naive row-wise BCa does not repair crossed dependence. At heavy ties, all-gated pools, near-constant scores, threshold jumps or very few recipe families, report descriptive bounds/sensitivity and **INFERENCE_UNRESOLVED** rather than force a CI. The gate numerical comparison remains registry-v4's pinned comparison, including its boundary convention.

Proposed bootstrap replicate count low/base/high **5,000/10,000/20,000 (ASSUMPTION)**; the historical EV4 hypothesis specified 10,000. Replicate count improves numerical precision of the interval; it does not replace independent recipes/questions. New replay seeds belong in a public statistical manifest, never official hidden seed provenance.

A p-value for tau=0 from an independence permutation is not a test of equal alignment for two dependent rules. An A/B label swap requires a justified exchangeability null and cannot be assumed for deterministic score formulas. For paired Delta tests use a validated centered/studentized paired-cluster bootstrap null or an appropriate influence-function asymptotic test, with the coverage check above.

## Power and sample planning

**There is no single defensible number of members and cases from half-width and delta alone.** True association, ties, recipe dependence, rule covariance, case effects and the target distribution are missing inputs. The following analytic sensitivity calculations answer the owner's requested targets without inventing those inputs. No rescore, Monte Carlo power experiment or solver was run.

For these tables only: confidence **95%**, two-sided alpha **0.05**, power **80%**, normal quantiles z=1.959964 and z_power=0.841621 are **ASSUMPTION, low=base=high**. Requested half-width h=0.1 and detectable Delta=0.05 come from the owner, low=base=high. Actual scientific acceptance, confidence and power requirements remain **HUMAN_INPUT**.

For independent, untied observations **under independence**, the [SciPy null formula](https://docs.scipy.org/doc/scipy/tutorial/stats/hypothesis_kendalltau.html) is

    Var(tau) = 2(2M+5)/(9 M(M-1)).

The smallest M satisfying z*sqrt(Var)<=0.1 is **175 (CALCULATED; low=base=high under this null)**. Counting M(M-1)/2 pair comparisons as independent would drastically understate uncertainty. The null formula is not a sufficient-sample guarantee when tau is positive, scores tied or cases sampled.

For general first-order planning, estimate Var(tau) approximately v/M from a public pilot's recipe-cluster influence/jackknife variance. Illustrative v low/base/high **0.2 / 4/9 / 1 (ASSUMPTION)** yields:

| Fixed decision cases; one tau | Low | Base | High |
| --- | ---: | ---: | ---: |
| Independent recipes ceil(z² v/h²) | 77 | 171 | 385 |

The high v is a sensitivity assumption, not an upper bound for tau-b near a vanishing denominator.

For paired rules, v_Delta = v_A+v_B-2 cov_A,B. With v_A=v_B=4/9 and correlation of **recipe influence contributions**, not raw scores, low-cost/base/high-cost rho **0.95/0.80/0.50 (ASSUMPTION)**, v_Delta is 0.044444/0.177778/0.444444. Normal local-alternative planning for rejecting Delta=0 when its true value is 0.05 gives M=ceil((z+z_power)² v_Delta/0.05²):

| Fixed decision cases; paired rule comparison | Low | Base | High |
| --- | ---: | ---: | ---: |
| Independent recipes; one frozen contrast | 140 | 559 | 1,396 |
| Independent recipes; conservative 128-contrast Bonferroni planning | 343 | 1,370 | 3,423 |

The second row uses z_(1-alpha/(2*128))=3.546338, a **calculated** planning value. Holm can be less conservative in realized tests; assume no such discount before observing data. Power to prove Delta exceeds 0.05 requires specifying a true Delta **above** 0.05 and substituting its excess over that null in the denominator. Detecting a true difference of 0.05 from zero is not proof it exceeds 0.05.

To include cases, use a **working variance model (ASSUMPTION)**:

    Var(statistic) ≈ v_recipe/M + v_question/C + v_interaction/(M*C)
                    + reconstruction contribution.

Estimate components and dependence from a public statistical planning audit; they are not identified by the current seed band. C counts complete independent questions. Allocate half the variance allowance to recipes and half to questions in these illustrations; interaction/reconstruction contributions are set to zero **for arithmetic only**. A positive contribution increases the required counts or reallocates the budget.

| Joint planning target | Low | Base | High |
| --- | --- | --- | --- |
| Tau CI half-width 0.1; v_recipe=4/9, v_question=0.01/0.1/1 | M>=342; C>=8 | M>=342; C>=77 | M>=342; C>=769 |
| Paired Delta=0.05; v_recipe=0.044444/0.177778/0.444444, v_question=0.01/0.1/0.5 | M>=280; C>=63 | M>=1,117; C>=628 | M>=2,791; C>=3,140 |
| Same Delta target, rounded recipes per quality level if **5** balanced bands | 56 | 224 | 559 |
| Same Delta target, rounded questions per stratum if **3** balanced strata | 21 | 210 | 1,047 |
| Tau CI target, rounded recipes per **5** quality bands | 69 | 69 | 69 |
| Tau CI target, rounded questions per **3** strata | 3 | 26 | 257 |

All variance ranges and balanced band/stratum allocations are **ASSUMPTION**. Five diagnostic quality levels (bad, weak, middle, competitive, frontier) and three case strata are illustrative accounting, not a new battery population. Counts are totals across levels; balanced rounding can exceed a total minimum. Required real strata, weights and boundaries remain the registered packet's or **HUMAN_INPUT**. These counts concern overall tau; a separate interval of the requested precision **inside each level** requires applying the full M/C calculation within each, not dividing the total. Member reconstructions equal M times declared seeds per recipe; repeated seeds do not raise independent M.

The base joint comparison needs **1,117 independent recipes and 628 questions** under its assumptions. That is much larger than a demonstration panel; it may be impractical. A smaller finite-panel falsification is still useful, but must report its attained interval and detectable effect rather than claim the requested precision. There is no authority here to fund or acquire that sample.

For reference-cost accounting, a new question with k action alternatives requires up to k reference cases plus declared refinements; prediction evaluations scale with member reconstructions times action cases. Reusing verified public references changes marginal cost, not effective question count. C_score for the independent scoring panel must be planned separately from C_value; this table does not determine it. No spend estimate is asserted without the Test Engineer's measured route and costs.

Safety planning has a different denominator. With **zero missed unsafe events**, IID Bernoulli trials and one-sided confidence 95% (ASSUMPTION), the exact upper miss-probability limit solves (1-p)^n=0.05, hence p_upper=1-0.05^(1/n), an inversion of the [NIST exact-binomial construction](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm). Illustrative upper miss targets 10% / 5% / 1% (ASSUMPTION, not adopted gates) require **29 / 59 / 299 independent unsafe events**. Dependence across a model's cases invalidates treating them as IID; model-level safety uses independent unsafe recipes, question-level safety uses independently sampled deployment units or an explicitly validated cluster method. A few bad controls cannot establish rare-failure recall.

### Planning audit before any confirmation

The Test Engineer should first report publicly safe aggregate facts: unique recipe-family count, reconstructed seeds, resolved question count per stratum, effective weights, missingness, tie rates, gate crossing frequency, recipe/question variance components and influence covariance across rules. No hidden identifiers or seeds enter that report. Use that audit to replace the illustrative v and rho ranges, validate interval coverage, and state attainable precision/power at the available panel size. The planning audit is **NOT_RUN** in this PR.

## Folds, selection and multiple comparisons

Keep construction training/practice, score calculation, development rule selection and independent decision confirmation separate. Score measurement and value measurement cannot use the same question outcomes for the q leg. Related recipes and all their seeds stay in one group; all action alternatives and outputs of one question stay in one question group. Versions/digests are fixed before inspecting confirmation outcomes.

Use grouped inner development folds to assess selection stability, then freeze the proposed rule and baseline for an untouched confirmation rectangle of **new recipe groups × new decision questions**, with its own separate scoring questions if that is the target estimand. Also report known-recipe/new-question and new-recipe/known-question transfer as secondary diagnostics. Inner fold count low/base/high **3/5/10 (ASSUMPTION)**, conditional on enough groups per fold. Folds are correlated evaluations, not five independent experiments. If available data cannot form these blocks, report which transfer claim remains untested. Previously inspected verification cases are development data for a new selection.

[Cawley–Talbot](https://www.jmlr.org/papers/v11/cawley10a.html) documents selection bias from optimizing a noisy evaluation criterion. Nested splitting addresses the selection step; it does not manufacture external validity for a curated model population.

Two confirmatory routes are options for the owner/Test Engineer:

- **One frozen primary comparison:** choose on development only; compare once with CE on genuinely untouched confirmation. Predeclare primary tau contrast and safety/value conditions. Other rule results remain exploratory unless separately controlled.
- **All registered comparisons:** 128 contrasts versus CE in one family, plus any added confirmatory endpoints/stratum claims in a predeclared family or gatekeeping plan. Use valid paired-cluster null tests with [Holm's step-down FWER procedure](https://www.ime.usp.br/~abe/lista/pdf4R8xPVzCnX.pdf); ordered p_(i) is compared with alpha/(J-i+1). Provide simultaneous Bonferroni intervals or a validated joint max-statistic method, with assumptions stated. Ordinary 95% per-rule CIs are not simultaneous. A max-statistic/bootstrap method must pass joint coverage checks, including ties, before replacing the conservative option.

Do not use exploratory false-discovery control to waive safety failures. Alpha, family membership, practical superiority and safety/value acceptance criteria remain **HUMAN_INPUT**. Failed confirmation stays failed/unresolved; revising the rule consumes that data as development and needs a new independent confirmation, not repeated testing until success.

## Adversarial “score up without value up” test

Predeclare permitted attack families and a budget **HUMAN_INPUT**. On public practice/development only, let an attack choose among frozen-output transformations or declared model variants to maximize score: feasibility optimism just across a boundary, better average error away from the decisions, near-case overfitting, gate-cutoff surfing, abstention/missingness abuse, seed selection, and imitation of the fixed conservative answer. Include a null transformation whose score/value should be identical.

Freeze the attack before independent operator confirmation. The authorized Test Engineer, not this researcher, runs evaluation on the new decision set; no hidden data is given to the attacker. Measure paired score change, reference-verified value change, false-feasible/fallback outcomes and the resulting rank/slate movement. Pair base and attack by recipe and question, and keep unsuccessful attacks in the report.

A successful falsification is a score increase accompanied by reference-relative value degradation, a hard unsafe decision, or a reliably negligible value increase under a **predeclared meaningful-value margin HUMAN_INPUT**. Merely failing to reject a positive value change does not prove “value did not rise”; use a one-sided upper bound or a predeclared equivalence interval. Absolute meaningful-value units must be the decision contract's, never inferred from score units.

Separate attack search from confirmation; count all attack families/attempts in multiplicity or report them as exploratory falsifications without a population success-rate claim. Independent confirmation is necessary for an adaptively optimized attack too. Q3 answers used to create q scores cannot also certify those same attacks' value. No label “cheating” follows from this diagnostic alone.

## Proper scoring and decision theory: what applies

[Strictly proper scoring rules](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf) incentivize honest **probability distributions** in expectation under their assumptions. Brier/log scores could test probabilistic feasibility forecasts if the interface supplies them and reference labels are meaningful. Squared-error point forecasts target a conditional mean. None of these results guarantees that Carbon's current geometric mixture of error/gate legs ranks models by a particular constrained design decision. A deterministic output is not a predictive distribution, and unsafe outcomes cannot be compensated by probabilistic score.

A decision rule minimizes expected loss for a declared utility, action set and state distribution. Reference-relative design loss is therefore the right outcome to test; a generally accurate model may be worse near a hard constraint. [Donti–Amos–Kolter](https://proceedings.neurips.cc/paper/2017/file/3fc2c60b5782f641f76bcefc39fb2392-Paper.pdf) provides task-based-learning examples supporting this distinction, not a theorem about Carbon's score. Utility/loss, solver-alone budgets and safety constraints remain independently fixed.

[Blackwell's comparison of experiments](https://doi.org/10.1214/aoms/1177729032) orders information by attainable risk across decision problems when decision policies can use that information optimally. It does not imply that one empirically higher scalar score dominates for every buyer, utility or safety limit. Carbon should claim bounded alignment for a particular P, question law, reference route and decision contract; physical/customer value needs its own evidence.

## Test Engineer handoff and owner decisions

Implementation should add a prospective statistical report alongside existing outputs, preserving historical fields. Required records are input/registry/source digests; split provenance without hidden identifiers; family/question counts; outcome exclusions; per-rule metrics; paired/simultaneous intervals with method; seed sensitivity; control placements; attack successes and failures; achieved precision; and the explicit **DEVELOPMENT, reference-relative** claim.

Before claiming a pass, the owner must set the decision-value definition and useful gain; score/value split and population claim; confirmatory comparison family; confidence/power; minimum acceptable alignment; top-k/deployment budget; safety/recall limits; adversarial/equivalence margins; and action for unresolved evidence. They are **HUMAN_INPUT**, not defaults inherited from illustrative arithmetic.

Primary Hub impact: NONE — research-only, no implementation or maturity change; the repository's retired Hub is not regenerated. The result is **SPECIFIED research design**, not TESTED score alignment, scientific qualification or an adopted rule.
