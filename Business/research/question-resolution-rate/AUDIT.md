# Why questions do not resolve, and what recovery is worth

**QUESTION-RESOLUTION-RATE-01 — public DEVELOPMENT research; recommendation only.**

## The measured denominator and causes

Public EV4 and EV5 offer **24 questions each** to the same **99 eligible real members**. Their complete-common numeric decision-loss masks retain **14/24** and **13/24**, respectively: pooled **27/48 = 56.25%**. This reproduces #1055's historical sizing basis. **267 offered for 150 resolved is `ceil(150 / 0.5625)`, a planning projection**, rather than an observed 267-question sealed run in these inputs. The owner supplies approximately **0.73 CPU-h per offered question**; this audit never reads a sealed run or its timing. Counts and public point estimates are measured (low=base=high). [Output: `pooled_EV4_EV5`](results.json); [public custody and pins](SOURCES.md).

All **21 excluded questions** contain reference actions that remain within uncertainty bands. One also contains **five unavailable reference actions**. There are **zero missing member-question records**: all **4,752** expected records exist. Of these, **837** have nonnumeric loss: **769 SELECTED_UNRESOLVED** and **68 ABSTENTION_UNRESOLVED**. None is an exposed missing-prediction record or tie failure. Member-level numeric coverage is much higher than the all-member common mask: **3,915/4,752 = 82.39%**. A single unresolved member can exclude a whole question. [Output: `cause_summary`, `campaigns/*/questions`](results.json).

| Suspected cause | What public evidence shows | Consequence |
|---|---|---|
| NONE_FEASIBLE | Nine questions have all 35 actions reference-infeasible. All nine resolve for every real member, whether the model correctly abstains or wrongly selects an unsafe action. | Keep them: they test abstention and false feasibility. |
| No known feasible action, but ambiguity | Three questions have no known feasible action plus unresolved/unavailable references. | They do **not** prove NONE_FEASIBLE; abstention cannot be declared correct. |
| Reference uncertainty | All 21 excluded questions have unresolved reference actions; 38 distinct selected ambiguous actions block losses, across questions. There are 68 unresolved reference actions over the whole grid. | Reference quality and selection coverage, rather than a missing member manifest, dominate the current loss. |
| Infrastructure/reference failure | Five reference failures occur in one EV4 development question. | Keep typed reference failure separate from candidate failure; repeated solves are not automatically useful. |
| Objective ties | The pinned selector deterministically breaks ties by objective, c1 and c2; no TIE_UNRESOLVED outcome exists here. The number of objective ties is absent from aggregate inputs. | No measured unresolved loss can be assigned to ties. Tau tie correction remains necessary, but tie count cannot be invented. |
| Member coverage | Every real member has a record for every question. Numeric coverage ranges 70.8–91.7% in EV4 and 66.7–91.7% in EV5. | A record-completeness preflight is good future hygiene, but saves zero observed questions in this dataset. |

The reference-complete mask is stricter than the reported common-member mask: **23/48** questions resolve every action, while **27/48** give every real member a numeric decision loss. Four questions remain common-numeric despite unresolved actions nobody in this real panel selected. The current contract measures regret against the **best reference-feasible design in the tested, resolved set**; this is not proof of the full physical optimum. Keep both coverage measures visible. No historical outcome was rescored or reinterpreted.

Sparse blockers are a useful priority signal. For example, EV5 `V-T20-S0.38` is excluded by **one of 99 members**, selecting **one** unresolved action; EV4 `D-T34-S0.33` has **six** unresolved members selecting the same action. These observations justify testing a targeted reference-recovery policy, not dropping those members or calling their outcomes zero loss. [Per-question rows](results.json).

## The existing refinement policy: an honest before/after

REF-RESOLVE-01 v1 overlays **development references only**, with the **same uncertainty band**, preserving original records and versioned evidence. The published batch refined **27** blocked actions: **22** returned OK, **five failed again**. With the original bands, **six resolved**, **16 stayed unresolved**, and the five failures remained unavailable. Graphite Q1's common development mask increased **6/12 → 7/12**, rather than resolving all blocked questions. Verification references and historical EV4/EV5 results were not changed. [Policy and source records](SOURCES.md); [output: `reference_refinement`](results.json).

The recovered question is `D-T34-S0.33`. Two members' chosen action, `c1=2,c2=1`, changed **SELECTED_UNRESOLVED → SELECTED_INFEASIBLE**. This is useful evidence that makes the adverse finding clearer. Recovery does not mean the design became safe.

The published timing records sum to **1.83418 elapsed hours**, including **0.36309 hours** spent on the five failures; solver elapsed time sums to **1.83246 hours**. These are measured sums of record wall times, **not measurements of process CPU-time** or batch elapsed time under parallel execution. Any conversion below assumes **one busy CPU core** per solve. The actual thread count, process CPU and target-host transfer remain gaps.

Only **one already-refined action** is needed, in hindsight, to remove the actual two selected-action blockers for the recovered Graphite question. Its elapsed time is **0.061447 hours**. That is a lower-work counterfactual under the existing contract's outcome semantics, not a tested new policy or a proof that other unresolved actions can never affect a fuller optimality claim. The complete batch also refined actions that were not selected; an implementation cannot select the lucky successful case using future answers.

The existing policy's v2 proposal is already a negative result: a band based on twice the largest measured refinement shift would be wider than the original band and would recover no additional questions. Do not shrink bands or retry until a preferred label appears. The current development v1 policy is not permission to apply it to a sealed scoring/confirmation bank; any extension needs prospective scientific authority.

## Recommended changes that preserve the scientific task

**1. Register bounded targeted reference recovery first.** Freeze members, selections, reference version and the outcome law before recovery. Deduplicate ambiguous selected actions across all members, and prioritize by the number of blocked comparisons per estimated recovery cost, while keeping every member and every offered question in the ledger. A conservative implementation can target all reference ambiguities affecting a question's required claim, rather than only selected actions, where full best-in-set credibility is required. Predeclare the priority/tie rule, maximum attempts, cost ceiling, typed failure handling and which refinement tier may supply evidence. Never let a miner's identity or desired ranking determine which result is forced into a label. Record solve CPU-time and thread count, not wall time alone. Production recovery limits remain **HUMAN_INPUT**.

The optimistic public hindsight scenario is substantially cheaper than blanket refinement; the full measured batch illustrates that refinement can cost more than offering fresh questions. Freeze the proposal and test its recovery yield on new public planning questions before using it to reduce the confirmation budget. Preserve recovered unsafe findings explicitly.

**2. Keep P fixed; make any Q change prospective and weighted.** Frontier-targeted Q can make safety questions more informative, but it is not an evidenced yield improvement here: the public subset with both a known feasible and an infeasible action resolves only **18/36 = 50%**. A frontier can also be intrinsically close to uncertainty bands. Use a mixture `Q = epsilon*P + (1−epsilon)*Q_target` with positive support and computable draw probabilities; epsilon and target law are **HUMAN_INPUT**. Record the registered P/Q/evidence weighting and appropriate weighted question-block uncertainty. A larger raw resolved fraction does not imply a larger effective sample. [Owen, importance sampling, §§9.1, 9.3 and 9.11](https://artowen.su.domains/mc/Ch-var-is.pdf).

Design Q_target from public/independent engineering features and a frozen low-cost screening rule, not from knowing which future confirmation answers resolve. Keep abstention, unsafe-boundary and difficult strata represented. Collect proposal and rejection counts, density/weight diagnostics, unresolved rate and recovery cost by stratum. The yield and weighted-tau power of such a future generator are **NOT_IDENTIFIABLE** in this aggregate audit.

Importantly, **P/Q weighting cannot manufacture missing outcome values**. Dropping unresolved cases and renormalising weights still conditions on resolvability, which depends on the reference and the members. The current common-resolved tau is a conditional historical estimand. A claim about all of P requires reference recovery, an approved interval/partial-identification treatment, or an explicitly narrower owner-approved population. Do not silently declare rejection-sampling to be the original P. A prospective interval loss/rank analysis could retain uncertainty instead of forcing a scalar; its acceptance rule is a separate scientific decision.

**3. Preflight complete coverage, and preassign cohorts only for diagnostics.** Require every expected member/question/action output before ranking, with typed missingness and retries confined to the infrastructure policy. The current panel has no missing record to repair, so there is **no measured saving** from this rule. Hash-preassigned recipe cohorts in the public audit sometimes retain more numeric questions, because fewer models select an ambiguous action. That does not resolve the omitted model's decision or establish a comparable pooled tau. Do not select cohorts from observed safety or results. A balanced incomplete-block design would need a preregistered comparison graph, inclusion probabilities, value estimand and new power analysis; the #1055 150-question sizing cannot simply be carried over.

Relaxing coverage to 95% would retain **28/48** questions, but one still has an unmeasured member loss. It would superficially reduce sizing from **267 to 258** offered questions, a base gross **6.57 CPU-h** reduction. That is **not an admissible pooled-proof saving** under the complete-common law. In particular, the excluded member might be unsafe; replacing missing loss with a pass or zero would invalidate the feasibility proof. The proposed preflight/cohort rules preserve that distinction.

**4. Keep resolved NONE_FEASIBLE and the existing deterministic tie rule.** Removing the nine all-infeasible questions would lower yield to **18/39 = 46.15%**, and erase informative unsafe/abstention observations. The notional budget would rise to **325 offered questions**, base **237.25 CPU-h**, rather than 267 / 194.91. Keeping them avoids that **42.34 CPU-h** base increase relative to an invalid filter, not a new saving against the current task. Tie handling causes no measured resolution loss and therefore no measured recoverable CPU cost.

**5. Do not densify the design grid to fix reference resolution.** The public grid diagnostic increased actions **35 → 117**, changed selections **43/234 = 18.38%**, and changed **2/52** reference-judged feasibility labels, both FEASIBLE ↔ UNRESOLVED. It established no common-question resolution gain and did not move the run-5 picks. At the same per-action cost and yield (**ASSUMPTION**), its bank cost multiplies by **117/35 = 3.343**, giving base **651.56 CPU-h** instead of 194.91. Geometry/action coverage and uncertainty-band resolution are different questions. [Published grid report](SOURCES.md).

## CPU-hour sensitivity, including the cost of recovery

Use `N=ceil(150/r)` and `CPU=N*(c+d)`, where r is complete-common resolution rate, c is CPU-h per offered question, and d is additional recovery CPU-h per offer. The owner's c base is **0.73**; **0.66 / 0.73 / 0.80** is an explicitly **ASSUMPTION** low/base/high sensitivity range, not measured host variability or a confidence interval. Target **150** is the owner's interim choice. These figures cover the question/reference-bank component; scoring, member construction, calibration and administration are not included.

| Future resolution rate (ASSUMPTION) | Offers for 150 | CPU-h low / base / high, before recovery | Gross saving low / base / high against current sizing |
|---|---:|---|---|
| Public historical 56.25% | 267 | 176.22 / 194.91 / 213.60 | 0 / 0 / 0 |
| 60% | 250 | 165.00 / 182.50 / 200.00 | 11.22 / 12.41 / 13.60 |
| 65% | 231 | 152.46 / 168.63 / 184.80 | 23.76 / 26.28 / 28.80 |
| 70% | 215 | 141.90 / 156.95 / 172.00 | 34.32 / 37.96 / 41.60 |
| 80% | 188 | 124.08 / 137.24 / 150.40 | 52.14 / 57.67 / 63.20 |
| 100% | 150 | 99.00 / 109.50 / 120.00 | 77.22 / 85.41 / 93.60 |

All offers are conditional arithmetic (low=base=high given r); the future rates are scenario choices, not predictions. The **85.41 CPU-h base** perfect-resolution saving is a gross upper bound before recovery overhead, not a promise. The output includes 75% and 90% scenarios and exact break-even overheads. At 70%, additional recovery must average less than **0.17656 CPU-h per offered question** at the base cost to save CPU at this sizing. This is a financial/compute break-even, not a scientific tolerance.

For the **measured Graphite development before/after**, the historical mix repeating is an ASSUMPTION: 6/12 → 7/12 would reduce 300 → 258 offers. Blanket refinement repeating its 27-case cost per 12 offers changes base **219.00 → 227.77 CPU-h**, costing **8.77 more**. The hindsight one-case pattern changes 219.00 → **189.66 CPU-h**, saving **29.34**. Neither is a measured sealed outcome; the first is a warning that gross recovered-question counts alone are inadequate.

To put that mechanism on the owner's **current 267-question sizing**, one additional recovered question per 12 offers would hypothetically raise yield to **64.583%** and need **233** offers. If the one-case hindsight work repeated, total CPU would be **154.97 / 171.28 / 187.59**, saving **21.25 / 23.63 / 26.01 CPU-h**. If the full 27-case work repeated, it would instead be **189.39 / 205.70 / 222.01**, costing **13.17 / 10.79 / 8.41 more** than baseline. These are **ASSUMPTION transport scenarios**, conditional on the same recovery rate and one busy core. Their low/high values vary c only; they do not bound uncertain recovery yield. If recovery yields no additional questions, its cost is a loss. There is no defensible forecast of net sealed savings yet.

For frontier Q, the public known-contested proxy provides a negative check: even a positive-support mixture with the original P has raw support yield below 56.25% at the tested epsilon scenarios. The report includes that diagnostic rather than assigning a positive saving to it. It is not a deployable prescreen, and weighted effective sample size/power remains unmeasured.

## Concrete handoff and evidence needed next

Recommend a **public, prospective recovery-policy test**, with the same questions, members, P/Q and bands, before shrinking #1044's bank. Compare standard, fixed-tier blanket and predeclared targeted recovery on the same offered questions; report typed failures, unsafe labels revealed, masks before/after, per-stratum yield, CPU-time/core/thread records, and added cost per net question recovered. Keep the 150 interim conditional until its current-rule/gate and dependence assumptions are checked. Any Q change needs its own frozen weighting and power design. No solver run is authorised or conducted by this research PR.

The near-term benefit is better reference evidence for feasibility, not just a lower invoice. The recovery policy must keep adverse resolutions in the dossier and must not make an unsafe member disappear from a common-mask analysis.

## Reproduction and maturity

Run `python Business/research/question-resolution-rate/analyze.py --inputs Business/research/question-resolution-rate/inputs --out Business/research/question-resolution-rate/results.json` with the seven exact public blobs in [SOURCES.md](SOURCES.md), then `python Business/research/question-resolution-rate/test_analyze.py`. Every input Git identity is checked; extras in the ignored cache are never read. The analyzer has no Carbon runtime imports, solver, reconstruction or network capability and emits LF-only deterministic JSON.

Five native diagnostic tests passed: proven NONE_FEASIBLE versus uncertain abstention, absent-record fail-closed, planning rounding/CPU units, digest-bound masks and adverse refinement, and LF export. Native Windows execution is public research evidence, not canonical repository acceptance. Local Docker daemon is unavailable; PR CI supplies scope checks. Maturity is research design and measured public diagnostics only. No prospective generator, recovery policy, weighted proof, launch claim or scientific threshold is adopted.
