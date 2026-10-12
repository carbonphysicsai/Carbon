# VALUE-METRIC-AUDIT-01 — what the public battery value metric rewards

**DEVELOPMENT / exploratory research, 2026-10-12. No qualification or adoption.** The historical loss is dominated in magnitude by unsafe picks, but design regret still orders many otherwise tied members. The clearest counterexample is a no-op: always abstaining ranks **2nd of 100** on the historical EV5 verification common mask, delivers no new design and earns no gain. A constructed guarded default does **not** rank near the top on the fresh CPU replay. These are distinct findings.

Recommend evaluating **verified design benefit over a declared safe fallback, minus actual workflow cost**, with failures, unresolved references, coverage and reuse reported separately. Unsafe proposals rejected by verification spend budget; they are not deployed failures. Neither an economic coefficient nor good relative ranking can waive mandatory scientific admissibility.

All panel counts, objective quantities and arithmetic below are **MEASURED, low = base = high for these exact finite public panels**. They are not population estimates. Scenario coefficients are **ASSUMPTION / HUMAN_INPUT**; intervals are explicitly exploratory. Every table is derived from [results.json](../results.json); input identities and literature are in [SOURCES.md](../SOURCES.md). The [measurement protocol](../MEASUREMENT_PROTOCOL.md) records both initial choices and additions after inspecting the first replay. No analysis executable or raw input is committed.

## 1. Evidence scope and denominators

Pin main `1238dd3471f73d3fc0df375de1d63c4663e380b3`. Historical EV4 and EV5 each contain 99 eligible real members after excluding the recorded ineligible member. These original A40-era decisions are never replaced by rebuilt model results. The public CPU cohort contains 148 unique prediction bundles: 100 original-panel real rebuilds (80 recipe labels), 27 Graphite run-5 rebuilds, 11 additional public proof members and 10 adversarial rebuilds. There are 21 byte-identical folder copies, counted once. Every bundle supplies the allow-listed 420 D and 420 V cases. Standard references have 835 OK records and five failed records. CPU-rebuild membership is not a statement of current score/gate eligibility.

All 148 members have per-family outcomes in the derived JSON; primary associations/rank sensitivity use the 100 real CPU rebuilds, without attacks or constructed controls. Original records, fresh CPU records, post-hoc controls and refined-reference sensitivity remain distinct. A research manifest binds bundle digests to RES-06. The owner's public copy remains read-only and uncommitted.

Historical offered questions are 12 per split. Numeric denominators vary because reference-band uncertainty and failed references do not become zero loss. The table below shows each member's numeric minimum/maximum and the **common complete mask** used for the primary paired comparisons. These masks are an audit sensitivity, not a new registration of P, Q or w. The postmortem's supplied tau 0.953 is not reproduced by this different public cohort/estimand; it is not used as a measured input here.

## 2. Decompose the registered loss

The [historical contract](../../../../carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json) uses a fixed 35-action c1/c2 grid, time to a 4.19 V CV-onset proxy after the initial 120 s rest, reference plating/temperature/reach constraints and unchanged uncertainty bands. It does **not** measure charge to a target SOC, real-cell safety or lifetime. Define u = 120 s (registered historical opportunity unit):

`L = 10 × I(selected reference-INFEASIBLE) + I(selected FEASIBLE) × (t_selected − t_best-known-FEASIBLE)/u + I(missed opportunity)`.

Correct settled-NONE abstention contributes zero. Selected UNRESOLVED / unavailable, or unresolved abstention, has no numeric L. Best means best in the frozen finite action set, not a global optimum. The feasible term is **regret**, not direct benefit over the default. When that default is FEASIBLE, `regret = (t_default − t_best)/u − (t_default − t_selected)/u`. All applicable row identities and every component sum were checked exactly up to numerical roundoff. Negative benefit is retained.

| Panel | Common Q | Original numeric min/max | Mean L | Unsafe share of L | Regret share | Miss share | tau(L,unsafe) common | tau original denominators |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EV4 development | 6 | 7/11 | 1.116 | 93.52% | 6.18% | 0.30% | 0.725 | 0.914 |
| EV4 verification | 8 | 9/12 | 0.910 | 94.37% | 4.52% | 1.11% | 0.784 | 0.741 |
| EV5 development | 5 | 7/11 | 1.975 | 98.20% | 1.80% | 0.00% | 0.829 | 0.901 |
| EV5 verification | 8 | 9/11 | 2.027 | 96.57% | 3.12% | 0.31% | 0.791 | 0.858 |

Thus unsafe loss contributes 93.52–98.20% of total loss magnitude. Cov(component, total)/Var(total) for unsafe loss is 0.960–0.975 across these panels; this accounting can include correlated components and is not a causal variance attribution. Correct abstention's scalar contribution is zero, but its count and distinction from missed opportunity matter.

Removing a component exposes its ranking effect, including newly created ties:

| Panel | Removed | tau with original L | Strict reversals / original strict pairs | Reversal fraction | Original orders becoming ties |
| --- | --- | --- | --- | --- | --- |
| EV4 development | failure | 0.434 | 1264/4532 | 27.89% | 48 |
| EV4 development | feasible_regret | 0.547 | 614/4532 | 13.55% | 1170 |
| EV4 verification | failure | 0.603 | 903/4630 | 19.50% | 49 |
| EV4 verification | feasible_regret | 0.765 | 84/4630 | 1.81% | 1593 |
| EV5 development | failure | 0.397 | 828/3940 | 21.02% | 913 |
| EV5 development | feasible_regret | 0.727 | 236/3940 | 5.99% | 989 |
| EV5 verification | failure | 0.327 | 1431/4463 | 32.06% | 170 |
| EV5 verification | feasible_regret | 0.710 | 301/4463 | 6.74% | 1118 |

Removing regret creates 989–1,593 ties in three panels and 1,170 in EV4 D. Its small magnitude does not mean it is irrelevant to ordering safe members. Removing unsafe loss reverses 19.50–32.06% of previously strict pairs. Neither a rescaling nor removing safety penalties is a registered score recommendation.

Realized benefit is a separate quantity. On common-mask rows where selection and registered default are both FEASIBLE, member-wise mean benefits have these min/median/max values in historical u units. Conditional member means use different numbers of qualifying rows, so these are descriptive benefits, **not another ranking target**:

| Panel | Min mean gain/u | Median | Max | Identity-checked feasible rows |
| --- | --- | --- | --- | --- |
| EV4 development | 2.981 | 7.160 | 7.214 | 293 |
| EV4 verification | 12.278 | 12.743 | 14.707 | 195 |
| EV5 development | 4.147 | 5.914 | 11.828 | 193 |
| EV5 verification | -0.675 | 5.704 | 11.408 | 149 |

The default c1 = 0.75, c2 = 0.6 is not globally safe: it is FEASIBLE on only 7/12 EV4 D, 5/12 EV4 V, 6/12 EV5 D and 5/12 EV5 V questions. Never call it a universal safe baseline or impute its benefit where it is infeasible.

## 3. A safe but unproductive control

Construct **always abstain**, not a prediction model: zero unsafe selections and zero new design benefit. Compute its registered loss only on each real cohort's common mask; every no-feasible question in these particular masks is settled NONE, not unresolved.

| Historical panel | No-op loss | Rank vs 99 real + control | New-design gain |
| --- | --- | --- | --- |
| EV4 development | 0.833 | 41/100 | 0 |
| EV4 verification | 0.625 | 44/100 | 0 |
| EV5 development | 0.600 | 23/100 | 0 |
| EV5 verification | 0.625 | 2/100 | 0 |

This proves that a no-benefit strategy can rank near the top of the historical EV5 V metric. It does not establish safe operation, score eligibility or useful coverage. It is an audit control, not a production miner.

Construct a more literal **safe but mediocre default**: choose the default only when ambient ≥ 14 C and SOC ≥ 0.33, otherwise abstain. Select these guards on EV4 D alone to maximize observed resolved-safe default coverage, with lower-threshold tie-breaking; then freeze and apply to V/edge and robust families. No V label chooses the rule. Observed zero unsafe picks means safe on this stored reference panel only.

| Fresh CPU family | Offered Q | Feasible default picks | Observed unsafe | Missed opportunities | Gain vs default when both F | Common-mask L | Rank vs 100 real + control |
| --- | --- | --- | --- | --- | --- | --- | --- |
| nominal | 12 | 6 | 0 | 3 | 0.000 | 3.940 | 101/101 |
| shifted | 12 | 3 | 0 | 6 | 0.000 | 1.847 | 91/101 |
| edge | 6 | 1 | 0 | 3 | 0.000 | 0.500 | 45/101 |

The guarded default has zero improvement over itself. It ranks 101st on D and 91st on V's common loss mask. An oracle-filtered default and slowest-feasible oracle also do not provide a general near-top result; full outcomes are in JSON. The guarded default abstains on all robust families. Robust-temperature has no feasible action, so many members correctly tie with abstention there; this is not evidence of design upside. Keeping the no-op counterexample is more honest than claiming the specific slow-default control succeeded.

## 4. Proposed buyer workflow and costs

For question q, require a buyer-approved **known safe fallback** b(q), an objective-to-benefit function and mandatory verifier. The economic proposal is:

`U(m,q;B) = benefit(best VERIFIED-feasible return or retained fallback) − expected deployed-failure cost − actual construction/search/inference/verification cost`, subject to unchanged admissibility and fixed complete-query wall/core budgets.

No buyer money or residual physical failure probability is measured here. The research linearization uses **ASSUMPTION** gain units `G = (t_fallback − t_return)/120`, with λ = failure cost / benefit of one such unit and κ = cost per verification token / benefit unit. Keeping the fallback gives G = 0. The fallback in the broad public replay is an **oracle diagnostic**: lowest c1, then c2 among known reference-FEASIBLE actions. It is not guaranteed available to a customer for free. A sensitivity restricts to questions with the historical default FEASIBLE.

Direct unverified picks have signed `U_direct = G − λ I(reference-INFEASIBLE pick) − κ I(attempt)`; abstention yields no gain. Settled NONE has no optimum or priced upside. Unresolved/unavailable truth is a measurement gap, never a zero-cost scientific failure. The direct-pick scenario prices a hypothetical deployment; Carbon's proposed screen-then-verify product should not deploy an unverified proposal.

The workflow orders predicted-feasible actions using predicted objective, c1 and c2 only. Verify the frozen prefix, all conditions of each action, under caps k = 1/3/5 **complete actions** (ASSUMPTION); return the best reference-FEASIBLE result, retain fallback if better, or make no new design. An unsafe, unavailable or band-unresolved attempt consumes its slot. No padding with duplicates, extra trials, reordered search, relaxed bands or free retries. Robust-SOC actions consume three case tokens; robust-temperature actions consume four. This analysis charges attempted panels completely, not optimistic early exits.

Relative to these stored reference labels, returned failures are zero **by construction**. Consequently **λ does not change verified-workflow ranks in this replay**. It must not be reinterpreted as zero residual physical risk. Measuring reference error and real deployment risk is required before λ can affect a credible customer-risk utility. Unsafe proposals are rejected and their cost enters κ. Mathematical admissibility is a separate gate, never a price for permission to fail.

Missed opportunity can be reported as `(t_fallback − t_best)/120 − credited G` on known-opportunity questions, rather than a uniform 1. That identity gives the no-op its entire missed gain and keeps its actual benefit at zero. Settled NONE is separately counted, not assigned fictitious physical regret. If no safe fallback is known, return/coverage evidence is available but absolute buyer benefit is **HUMAN_INPUT**.

## 5. Failure-to-upside sensitivity

ASSUMPTION λ grid: 0, 0.1, 0.3, 1, 3, 10, 30, 100; κ = 0 for this isolated direct-pick sensitivity. Use 6 D, 8 V and 4 edge common priced questions. These are counterfactual unverified utilities, **not verified-product scores**. Each table entry is measured from that declared scenario. Full member utilities and strict-pair reversals are in JSON.

| λ | tau(U,−L) D | tau V | tau edge | Guard rank D /101 | Guard V | Guard edge |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 0.905 | 0.614 | 0.463 | 101 | 101 | 94–101 |
| 0.1 | 0.915 | 0.842 | 0.985 | 101 | 101 | 94 |
| 0.3 | 0.920 | 0.850 | 0.985 | 101 | 101 | 94 |
| 1 | 0.929 | 0.977 | 0.985 | 101 | 101 | 94 |
| 3 | 0.908 | 0.983 | 0.986 | 101 | 101 | 94 |
| 10 | 0.909 | 0.986 | 0.988 | 98 | 96 | 45 |
| 30 | 0.908 | 0.988 | 0.988 | 47 | 90 | 45 |
| 100 | 0.908 | 0.988 | 0.988 | 43 | 43 | 45 |

The top real member is unchanged across λ on D and edge. V changes its top member between λ = 0 and positive λ, then keeps the same leader. On V, tau against negative historical loss rises from 0.614 at λ = 0 to 0.977 at λ = 1 and 0.986 at λ = 10; edge rises from 0.463 to 0.985 and 0.988. At λ = 0, unsafe picks on settled-NONE questions receive no hypothetical failure cost and create extra ties; at positive λ they are charged, even though no feasible upside exists. This comparison uses the same question denominator for every member. Positive λ therefore preserves much of historical ordering on these masks, while the verified-product objective is a distinct estimand. The safe default does not become a top-value control. All exact per-member ranks can be regenerated from the utility arrays; do not select λ to manufacture a preferred winner.

## 6. Budgeted verification and the cheap baseline

Primary budget is a **constant-cost token proxy**, not a measured CPU or wall cap. Gain/rank tables condition on 9 known-opportunity D questions, 9 V, 4 edge and 2 robust-SOC questions. All offered questions and empty/unresolved outcomes are preserved below and in JSON. Costs on the opportunity-free questions must also enter any actual customer workload. Conditioning here does not establish expected value over a registered P.

ASSUMPTION κ scenarios are 0 / 0.01 / 0.1 / 1 u per complete-action attempt. The last comparison column uses κ = 0.1. It counts strict net-utility wins, including different numbers of spent attempts under a shared cap. Means are in u units, **not money or target-SOC charging gain**.

| Family | Cap k | Real gain min | Real gain max | Fixed-order solver | Random-order median | D bilinear map gain | Real net wins vs map κ=.1 | Exact query-cache ceiling |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| nominal | 1 | 4.859 | 9.226 | 0.243 | 1.136 | 9.227 | 0/100 | 10.112 |
| nominal | 3 | 8.329 | 10.112 | 1.313 | 3.705 | 10.112 | 1/100 | 10.112 |
| nominal | 5 | 8.335 | 10.112 | 3.077 | 5.299 | 10.112 | 2/100 | 10.112 |
| shifted | 1 | 3.949 | 8.966 | 1.211 | 1.453 | 7.468 | 71/100 | 9.035 |
| shifted | 3 | 6.935 | 9.035 | 2.004 | 3.778 | 7.468 | 99/100 | 9.035 |
| shifted | 5 | 7.920 | 9.035 | 2.942 | 5.349 | 7.468 | 100/100 | 9.035 |
| edge | 1 | 2.596 | 8.263 | 1.868 | 1.269 | 4.911 | 95/100 | 8.263 |
| edge | 3 | 5.998 | 8.263 | 2.312 | 3.914 | 4.911 | 100/100 | 8.263 |
| edge | 5 | 7.243 | 8.263 | 2.443 | 5.244 | 4.911 | 100/100 | 8.263 |
| robust_soc | 1 | 0.000 | 6.435 | 0.000 | 0.000 | 6.435 | 0/100 | 6.435 |
| robust_soc | 3 | 0.000 | 6.435 | 0.000 | 0.000 | 6.435 | 18/100 | 6.435 |
| robust_soc | 5 | 4.013 | 6.435 | 0.000 | 0.000 | 6.435 | 19/100 | 6.435 |

The fixed and random solver-only arms are deliberately simple diagnostics. Their good model-comparison results are not evidence against industrial solver optimization. The stronger cheap check uses public D references only to predict V scalar decision quantities by nearest map or clamped bilinear interpolation; missing inputs/CV-onset remain unavailable. Cache construction uses 420 D records (415 OK), with a historical recorded wall-time sum of 7.744 hours. This is summed wall time including recorded failed cases, **not CPU-hours**, and is not a matched training/acquisition budget. Nominal cache tests reuse their source points. V answers never order the D maps.

At one verification the bilinear map beats 29/100 real members' net utility on V (71 are strictly better); at three it beats one (99 better), and at five all 100 real members are better. That limited shifted evidence is useful, but not a value-bar pass. On robust-SOC the same map reaches the finite-grid ceiling with one action; **no real member strictly beats it, and 91 tie** at κ = 0.1. More budget cannot create gain above the known finite-grid optimum. On nominal questions the map reaches that optimum with three actions. An exact cached lookup on an already-solved query can obtain the best known action without new solves, with acquisition cost charged separately; it remains a serious cheap-baseline risk.

Historical per-member mean verification wall sums for k = 3 show the timing proxy's range:

| Family | Low observed mean seconds | Median | High |
| --- | --- | --- | --- |
| nominal | 138.1 | 193.2 | 196.5 |
| shifted | 151.5 | 182.3 | 191.4 |
| edge | 148.2 | 182.7 | 203.1 |
| robust_soc | 292.0 | 582.0 | 582.0 |

These are stored reference wall-time sums, exclude inference, search, startup and amortized construction, and are not prospective CCX63 costs. Whole-query inference/core-time and a registered wall-budget replay remain missing. Equal caps do not prove equal spent compute. [VALUE-BAR-V1](../../../../docs/development/challenge_pipeline/value-bar-v1.json) requires a preselected strongest cheap and solver-alone policy, matched admissibility, registered independent held-out folds and measured complete-query cost. This audit supplies hypotheses/controls, not a pass.

Restricting the comparison to questions where the **registered default** is FEASIBLE gives 7 D and 5 V questions. At k = 3, κ = 0.1, tau between those net-utility rankings and broad oracle-fallback rankings is 0.923 on D and 0.866 on V. Thus fallback choice also affects value. The guarded default's new benefit relative to the registered default is zero; its positive gain relative to a slower diagnostic fallback is **not** a new model improvement over the customer's own default.

## 7. Public shifted and reuse questions

V uses interleaved public temperatures/SOCs within the old envelope; it is neither beyond-envelope nor an untouched new test. Edge is the predeclared ASSUMPTION distance ≤ 0.1 to a registered ambient/SOC boundary, normalized by the envelope widths (35 C, 0.45 SOC). It contains six offered V questions. Robust-SOC composes one protocol across three V SOC conditions at each ambient; robust-temperature composes one across four V temperatures at each SOC. Objective is worst-condition time and every condition must satisfy every constraint. These are new research **task compositions of the same case outputs**, not independent observations, current v3 question laws, or a proposed P change.

| Family | Offered | Common numeric mask | Known feasible opportunity | Settled NONE | No F but unresolved/unavailable |
| --- | --- | --- | --- | --- | --- |
| nominal | 12 | 6 | 9 | 1 | 2 |
| shifted | 12 | 8 | 9 | 3 | 0 |
| edge | 6 | 4 | 4 | 2 | 0 |
| robust_soc | 4 | 3 | 2 | 2 | 0 |
| robust_temperature | 3 | 3 | 0 | 3 | 0 |

All robust-temperature actions fail at least one required condition in the supplied references; no design benefit can be demonstrated on that family. Retain it as a failed feasibility/reuse hypothesis. Robust-SOC has opportunities at 19 C and 29 C, and settled NONE at 9 C and 38 C. Its two opportunity questions are too few to claim transferable economic value. Both robust families cost more conditions per attempted action.

**B1–B10 and stretch: GAP.** The owner confirms no public B-probe copy and no beyond-envelope reference set. Neither was accessed or fabricated. A future owner-authorized public stretch set can test them; this ticket runs no solver and dispatches no data collection.

## 8. Does physics consistency predict reuse value?

Match RES-06's D residuals to these exact CPU bundle digests; compare them with shifted registered loss and verified gain. Larger residual versus larger loss would be the expected direction if compliance helps economically. Primary cohort is 100 real members/80 recipe labels. Exploration uses 2,000 crossed recipe/temperature-block resamples and 95% percentile intervals (**ASSUMPTION exchangeability and numerical resolution**), preserving reconstruction seeds inside recipe clusters. There are only three temperature blocks on each common mask. Undefined correlations are dropped and their counts reported; no nominal coverage guarantee, confirmatory p-value or best-gate selection is claimed.

| Target | D residual | tau with loss | Exploratory 95% interval | Defined /2,000 | Partial rank corr controlling D loss + architecture |
| --- | --- | --- | --- | --- | --- |
| shifted | rest_voltage_span_v | 0.029 | [-0.111, 0.199] | 2000 | 0.110 |
| shifted | rest_temperature_span_c | 0.077 | [-0.074, 0.325] | 2000 | 0.127 |
| shifted | below_ambient_max_c | 0.038 | [-0.298, 0.257] | 2000 | 0.228 |
| shifted | historical_gate_case_violations | -0.013 | [-0.212, 0.079] | 1245 | 0.026 |
| edge | rest_voltage_span_v | 0.008 | [-0.229, 0.203] | 2000 | 0.083 |
| edge | rest_temperature_span_c | 0.020 | [-0.137, 0.212] | 2000 | 0.033 |
| edge | below_ambient_max_c | 0.043 | [-0.389, 0.301] | 2000 | 0.243 |
| edge | historical_gate_case_violations | 0.068 | [-0.054, 0.159] | 1254 | 0.110 |
| robust_soc | rest_voltage_span_v | -0.104 | [-0.298, 0.106] | 1432 | 0.068 |
| robust_soc | rest_temperature_span_c | 0.058 | [-0.155, 0.248] | 1385 | 0.107 |
| robust_soc | below_ambient_max_c | -0.306 | [-0.460, -0.099] | 1402 | 0.030 |
| robust_soc | historical_gate_case_violations | -0.029 | [-0.061, -0.020] | 934 | 0.006 |

Rest-voltage variation fails RES-06's diagnostic allowance for all 100 real rebuilds, so no passing cohort exists to establish a gate's discrimination. On V its tau is 0.029 with a wide interval crossing zero; with negative verified gain it is −0.076, interval [−0.254, 0.116]. Rest-temperature residuals are only 0.000001–0.000006 C and all real members pass the RES-06 allowance; ranking tiny rounding differences is not evidence of physical noncompliance. Below-ambient excursions depend on the conditional zero-entropic reference setup, not a universal thermodynamic floor.

The robust-SOC below-ambient association points in the opposite direction (tau −0.306); conditioning on nominal performance and architecture moves the partial rank association to 0.030. That is evidence of fragility/confounding, not a reason to reward a violation. Historical gate flags occur in **only one of 100** rebuilt real members (`mlp_raw-s0`, 241 voltage-ceiling flags). The mostly tied gate statistic is not a usable economic gate predictor; resamples without that member make tau undefined. JSON also reports unsafe-per-offered and verified-return associations as secondary descriptors. Unknown references are retained, not counted as safe labels.

No reliable positive economic reuse association is established for these measured residuals. A physics invariant can still be mandatory for scientific reasons under its registered applicability; this audit does not relax it. B-probes, intermediate model queries, conservation outputs, uncertainty calibration and beyond-envelope transfer remain unmeasured. A retrospective correlation on reused cases cannot justify a HARD gate or claim causal commercial value.

Crossed resampling follows the dependence motivation of [Owen and Eckles](https://arxiv.org/abs/1106.2125v3), whose mean-variance results do not guarantee our tau intervals. [Domain generalization research](https://arxiv.org/abs/2007.01434) supports keeping shifted tests and their model-selection history explicit.

## 9. A reuse term that cannot hide gaps

Proposed diagnostic: `U_total = (1 − ρ) × mean(U_nominal) + ρ × mean(U_shifted)`, with a separate source/coverage/unknown register for every family and predeclared within-family weights. These weights are business/measurement decisions, never inferred from seeds. P, Q and w remain separate. A robust family with no feasible action does not become free improvement; an unavailable family stays unmeasured, not zero utility. This replay mixes the nine D and nine V known-opportunity means only, k = 3, κ = 0.1 (**ASSUMPTION**). The reuse term is therefore within-family ambient/SOC reuse, not cross-physics transfer or current v3 coverage.

| ρ ASSUMPTION | tau vs nominal only | Nominal top-ten retained | Top real member (public label) |
| --- | --- | --- | --- |
| 0 | 1.000 | 10/10 | deeponet_t3000_w256_d2-s1 |
| 0.1 | 0.879 | 5/10 | deeponet-s0 |
| 0.25 | 0.808 | 2/10 | deeponet-s0 |
| 0.5 | 0.684 | 2/10 | deeponet_t1500_w256_d3-s1 |
| 1 | 0.188 | 2/10 | deeponet_t1500_w256_d3-s1 |

At ρ = 0.25, only two nominal top-ten members remain; tau is 0.808. At ρ = 1, tau is 0.188. These are descriptive rank sensitivities, not confidence that any named recipe will win a future exam. Repeated public tuning and shared case outputs prevent confirmatory selection. [Decision-focused learning](https://ojs.aaai.org/index.php/AAAI/article/view/3982) motivates assessing downstream usefulness; [ranking-feasible-solutions research](https://proceedings.mlr.press/v162/mandi22a.html) motivates verifying the ranked shortlist. Neither supplies Carbon's commercial weights.

## 10. One owner decision, with limits

**HUMAN_INPUT: choose one joint prospective audit profile (λ, ρ), not a production score or customer price.** Recommended exploratory low/base/high is **λ = 1 / 10 / 30** and **ρ = 0 / 0.1 / 0.25** (ASSUMPTION). Pair these for sensitivity as (1, 0), (10, 0.1), (30, 0.25), and keep the full independent grid to reveal interactions. Stress ρ = 0.5/1 separately. λ = 10 is an audit anchor from the historical false-acceptance coefficient, not an empirically estimated buyer ratio; λ = 1/30 brackets equal-unit to failure-dominant scenarios without selecting a winner. The conservative reuse band reflects evidence on only one public within-P shift and substantial rank movement even at small weights. No buyer demand or transfer probability was measured.

For the verified product, keep λ explicitly **unmeasured** until residual reference/deployment risk is estimable: in this replay it cancels from ranking. Keep safety gates independent. The base research report can use ρ = 0.1 while reporting nominal and V value separately; adoption/thresholds/budgets remain the owner's. Do not use these assumptions to quote money, claim launch value, qualify models or weaken safety. Required buyer receipt: value of a verified improvement in the actual objective, consequence/cost of deployed failure, safe fallback, reuse distribution and full compute/service costs. Without it, a commercial ratio is HUMAN_INPUT.

## 11. Handoff and verification

The Test Engineer can use these **research controls and hypotheses**: always abstain; D-only guarded default; known-query exact cache; D-only nearest/bilinear maps; direct-pick failure-grid sensitivity; fixed-budget verified gain minus spent cost; and separately registered nominal/shifted strata. Freeze selector, fallback, whole-query budget, costs, family weighting and reference bands before a new selection fold. Require positive matched-admissibility gain over the strongest cheap and fair solver-alone arm, not merely rank agreement with a failure-dominated loss. Retain adverse controls, unresolved/reference failures and structural NONE counts.

The 22 OK refined D records change 13 fresh real outcome rows and expand the common D mask from six to seven. On the **paired six-question original/refined mask**, ranking tau is 1.000; V has no changed rows and tau 1.000. This secondary reference-policy sensitivity never rewrites historical scores or treats the five failed records as infeasible.

Verification: digest/shape/allow-list checks; exact historical component sums and original summaries; baseline-gain identity; frozen order/unique attempts/cap checks; every returned design reference-FEASIBLE; matched RES-06 digests; paired refined masks; finite JSON; aggregate reproduction; document/link/manifest hygiene. Native offline calculations are research diagnostics, not canonical runtime acceptance; exact-head canonical CI is the delivery gate. Inputs and local analysis code are not in the PR.

Maturity: **specified exploratory utility proposal and measured public-panel analysis**. Not independently validated customer value, causal physics-gate evidence, current v3 score proof, physical qualification or a VALUE-BAR-V1 pass. No runtime changes. KEEP registered contracts and evidence; no Hub event/regeneration because the Hub is frozen and this report changes no runtime placement, dependencies or maturity. No solver/property-engine/model run, spend, hidden/sealed material, AX42, key/chain access, merge or other-lane edits.
