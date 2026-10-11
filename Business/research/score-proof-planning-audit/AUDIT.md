# Public battery planning audit and #1044 handoff

**SCORE-PROOF-PLANNING-AUDIT-01 — research measurements and conditional planning projections. DEVELOPMENT.**

The owner's choices are pooled tau half-width **0.15** and an interim look at **150 questions**. This audit runs only public historical battery statistics. It supplies a working **150 / 160 / 200 recipe** collection range at that question look; it cannot supply a qualified minimum for the in-force v3 rule or unobserved construction levels. The distinction matters: observed variance is measured; an extrapolated sample size still depends on the intended population, scoring-set treatment, seed policy and inference procedure.

## Working scope and authority

The direct owner request authorizes this bounded research ticket. No matching runtime ticket or qualification authority is assumed. Constitution, invariants, current WAVE, delivery/delegation protocols and Business Canon were checked before the audit; the existing #1045 design is the working statistical contract. The local checkout predates current main, so sources are read at the pinned main commit in [SOURCES.md](SOURCES.md), and the PR carries only this new research directory. The semantic seam is **NO_CONFLICT**: statistical planning recommendations remain outside scientific acceptance and live economics. No existing Challenge, Test Engineer code, packet, registry, reward or policy is edited. The Development Hub is retired; this research adds no hub event or regenerated map.

Every exact input/output count below is a **MEASURED public-source fact, low=base=high**. Mathematical constants are definitions. Statistical intervals have their own stated endpoints; scenario ranges are not confidence intervals. Confidence **0.95**, weak-screen power **0.80/0.90**, two-control alpha **0.025 each**, empirical exchangeability and future variance scaling are **ASSUMPTION planning choices**. Actual acceptance, multiplicity family, seed allocation, level weights and inferential stopping remain **HUMAN_INPUT**.

## What could actually be measured

The [EV4](https://github.com/carbonphysicsai/Carbon/blob/d426cf8b3f86a20c27e4dd82593b5935d99ada1f/docs/development/evidence/ev4-2026-10-01/results.json) and [EV5](https://github.com/carbonphysicsai/Carbon/blob/d426cf8b3f86a20c27e4dd82593b5935d99ada1f/docs/development/evidence/ev5-2026-10-03/results.json) records have the same **99 eligible RECONSTRUCTED members**. Removing only terminal reconstruction-seed suffixes gives **79 recipes**: **60** with one seed, **18** with two, **1** with three. Controls and adversarial constructions are purposive probes and excluded from primary tau. The historical CE published numeric score vector is identical across the shared members; it is held fixed. The historical DAR comparator is `dar-p0-r100-a0`. The third sensitivity candidate is the published EV5 candidate score with FAIL under its **historical near-optimism gate** placed below every passing score. It is not registry-v5's G-FEAS/A-Q rule. [Output: `inventory`, `provenance`; implementation: `run`, `tau` in audit.py](results.json).

| Campaign | Published complete question slates | Common-resolved across eligible members | Development / verification retained |
| --- | ---: | ---: | ---: |
| EV4 | 24 | 14 | 6 / 8 |
| EV5 | 24 | 13 | 5 / 8 |
| Union | 48 | 27 | 11 / 16 |

The union has no repeated public temperature/SOC question identity. Each question retains its complete published action decision; protocol alternatives and trajectory points are not counted as questions. The 27-question numeric mask is frozen before resampling, contains only numeric decision loss for every eligible member, and spans **14 campaign/split/temperature blocks**. The excluded questions contain unresolved candidate/reference outcomes; they are not given zero loss or turned into candidate failures. This model-dependent common mask narrows the estimand and is not a prospective population definition. [Output: `inventory/campaign_questions`; pinned inputs: `decisions`, `references`](results.json).

“Pooled” here means the shared Level-0 recipe set across these two public campaigns and both published splits. It does not mean all construction levels. The old development/verification labels are retained for sensitivity; their union is retrospective planning data and cannot become a new untouched confirmation set. Numeric tau on this new common mask differs from the old per-member summary tau, which averages each member's available outcomes. Neither historical record is silently rescored.

Keep population P, proposal Q and evidence weights w separate: prospective P and level weights remain HUMAN_INPUT; this audit's Q is empirical resampling of the explicitly listed public support, and numeric value uses equal question weights on the frozen mask. Point tau ranks members, retaining the recorded seed multiplicities, while uncertainty clusters those seeds by recipe. It is not an equal-recipe point-tau statistic. Distinct recipe strings are not evidence of independent construction lineages; the family/lineage boundary must be registered for the future proof.

## Measured variance and dependence

Each bootstrap resamples recipes with all their recorded seeds and separately resamples whole questions, using the same draws for the candidate rules. Gate outcomes/scoring cases are fixed, because per-scoring-case legs and predictions are not public inputs. A failed-score floor uses tie-aware comparisons, including ties among failed members. Undefined tau stays undefined. A second analysis resamples temperature blocks together. Each mode has **4,000** public research replicates (ASSUMPTION numerical resolution; low=base=high); five separate shorter runs measure Monte Carlo variation, not new physics evidence. [Method: audit.py `bootstrap`; output: `bootstrap_*`](results.json). The crossed design follows [Owen](https://arxiv.org/abs/0712.1111) and [Owen–Eckles](https://arxiv.org/abs/1106.2125); their guarantees for means do not certify gated tau-b coverage.

| Frozen historical rule | Pooled tau | Recipe-only variance | Question-only variance | Crossed variance | Crossed percentile interval / half-width |
| --- | ---: | ---: | ---: | ---: | --- |
| CE | 0.358 | 0.003877 | 0.014419 | 0.018125 | −0.001 to 0.522 / **0.262** |
| DAR | 0.187 | 0.006625 | 0.003068 | 0.009610 | −0.028 to 0.359 / **0.193** |
| EV5 candidate + historical near gate | 0.369 | 0.003350 | 0.019281 | 0.022687 | −0.041 to 0.537 / **0.289** |

Source: [results.json `point_tau` and `bootstrap_iid_questions/modes`](results.json). CE's recipe-only half-width is **0.121**. Question uncertainty dominates CE and the historical gated candidate; a member-only CI cannot meet this owner's joint precision claim. Joint percentile intervals remain descriptive research uncertainty because coverage is uncalibrated and the recipe grid is purposive.

Recorded seed losses have correlation min/median/max **0.280 / 0.624 / 1.000** over **21** within-recipe seed pairs. Question-loss correlation across members is **−0.274 / 0.191 / 0.631** within a temperature block (**13** nonconstant pairs) and **−0.462 / 0.092 / 1.000** across different temperature blocks (**287** pairs). These are measured similarities on this panel, not estimates of independent future miner supply. Architecture sensitivity is separately given for dropping MLP, DeepONet or kNN; only three broad families exist, so between-family population variance remains unidentified. [Output: `dependence_diagnostics`, `family_sensitivity`](results.json).

The paired DAR−CE resampling correlation is measured in `dependence_diagnostics/paired_CE_DAR_tau_resample_correlations`; the earlier assumed rule correlation is no longer a valid substitute. Split-specific point tau varies substantially, e.g. CE **0.049** on EV5 common-mask development versus **0.416** on verification. Bootstrap bias and nonlinear ranking sensitivity are visible in the stored replicate means. [Output: `split_points`, `bootstrap_iid_questions`](results.json).

## Counts for the 150-question look

First fit the planning approximation

```text
Var(tau | fixed scoring cases) ~= a/M + b/C + c/(M*C)
a = observed recipes * recipe-only variance
b = observed question units * question-only variance
c = observed recipes * observed question units * max(0, joint - row - column variance)
M_required(C) = ceil((a + c/C) / ((0.15/z)^2 - b/C))
```

This is an **ASSUMPTION extrapolation using MEASURED coefficients**, not an exact random-effects decomposition for nonlinear tau. Negative residuals are recorded and the projection uses a zero floor; that is a planning convention, not evidence that interactions vanish. A nonpositive remaining variance allowance returns **no finite recipe count**. [Output: `planning`; definitions: audit.py `coefficients`, `required_recipes`](results.json).

| Historical sensitivity rule | First-order recipes at C=150: low / pooled base / high | Source of low/high | Questions at existing M=79 | Questions at M=150 |
| --- | ---: | --- | ---: | ---: |
| CE | **59 / 94 / 107** | Separate EV4, EV5, pooled and temperature-block fits | 197 | 103 |
| DAR | **88 / 99 / 108** | Same sensitivity family | No finite C in this model | 35 |
| EV5 candidate + historical near gate | **49 / 112 / 155** | Same sensitivity family | 209 | 128 |

Source: [results.json `planning/*/low_base_high_recipes_at_150`, `sensitivity_recipes_at_150`, `questions_at_*`](results.json). Low/high are measured-panel **sensitivity** endpoints, not percentile confidence bounds for future sample size. Temperature-block conversion preserves the observed average block size; it does not assume each future question is independent. DAR has a recipe-variance floor at the current 79 recipes, so adding questions alone is insufficient under this fit.

The approximation understates finite-support percentile widths for some rules. Therefore the audit also resamples **150 draws from the observed 27-question support**, with varying recipe-cluster draw counts, and recomputes the actual tau interval. That measures an empirical-support planning experiment; duplicated draws do not become 150 distinct references or 160 newly built recipes.

| Recipe-cluster draws, C=150 | CE half-width | DAR half-width | Historical gated candidate half-width |
| ---: | ---: | ---: | ---: |
| 79 | 0.167 | 0.165 | 0.174 |
| 94 | 0.159 | 0.155 | 0.170 |
| 112 | 0.146 | 0.141 | 0.153 |
| 125 | 0.144 | 0.137 | 0.155 |
| 150 | 0.140 | 0.127 | 0.150 (unrounded 0.1499) |
| 160 | 0.137 | 0.122 | 0.146 |
| 175 | 0.134 | 0.117 | 0.146 |
| 200 | 0.131 | 0.113 | 0.145 |

Source: [results.json `empirical_support_projection_at_150_questions`](results.json). Nonmonotonic differences, such as 112 versus 125, are finite Monte Carlo variability and nonlinear ranks; do not claim an exact minimum from this grid. This is why the working **low/base/high collection recommendation is 150 / 160 / 200 real recipes and 150 distinct common-resolved questions**, labelled ASSUMPTION operational choices informed by these projections. The 150-recipe cell is marginal; 160 adds observed numerical margin; 200 supplies an explicit higher-count scenario, not insurance against an unobserved distribution shift. Seed multiplicities and family composition must remain comparable or the public planning audit must be repeated. No member count is substituted for the recipe count.

If the owner means **150 offered questions**, rather than 150 resolved value questions, the observed resolution rate is **13/24 to 14/24**, pooled **27/48**. Applying those rates projects **258 / 267 / 277 offered questions** to obtain 150 common-resolved questions (low/base/high; ASSUMPTION extrapolation). Conversely, 150 offered questions project only about **81 / 84 / 88** usable questions. Do not silently turn unresolved outcomes into good outcomes to hit the count. A prospective panel should seek adequate references for the intended family, rather than accept this historic coverage as the launch standard. [Input/output counts: `inventory/campaign_questions`](results.json).

### Interim interpretation

The recommended interim is an **inventory/precision/failure-reporting look** at 150 resolved questions. A discovered unsafe selection or known-bad placement is retained immediately. The public audit selects a fixed future protocol before prospective confirmation; it does not authorize accepting a rule when an ordinary CI happens to get narrow enough. If both interim and final looks can make inferential acceptance decisions, a conservative two-look Bonferroni planning example uses **97.5%** intervals at each look. The first-order M at C=150 then becomes **163 CE / 134 DAR / 264 historical gated candidate** (ASSUMPTION multiplicity choice with measured coefficients), before any rule or level comparison family. This calculation still lacks coverage validation. [Output: `planning/*/two_inferential_looks_at_150`](results.json).

Any alternative stopping/alpha-spending rule remains **HUMAN_INPUT**. [Howard et al.](https://arxiv.org/abs/1810.08240) explains the distinction between fixed-time CIs and time-uniform confidence sequences; this audit supplies no confidence sequence for crossed, gated tau. Pooled precision on these three historical rules does not simultaneously certify the entire registry or detect a delta-tau of 0.05.

## Per-level known-bad and gate screens

#1044 requires no registered known-bad member in the member top half and catches every registered unsafe member. These are finite-panel checks, not population recall certifications. The audit supplies the same member-top-half endpoint on this historical real-plus-control panel and a labelled weaker recipe-median power calculation, so the latter cannot be substituted for the former. Its historical panel is smaller than #1044's expanded pool and does not reproduce that pool's full ranking or registered unsafe-member list.

The member-rank projection resamples real recipe clusters with their seed multiplicity and holds the **five public controls** fixed. It reports both guaranteed and possible top-half placement when scores tie. At **25 real recipe draws**, CE places both bad controls in the top half with measured conditional probability **1.000**; DAR places neither there (**0.000**); the historical gated candidate places localized sign error there (**1.000**). A grid covers 6–150 recipes. These are **5,000** empirical resamples per grid cell (ASSUMPTION numerical resolution); proportions 0 or 1 are not universal guarantees for new families. Neither questions nor unsafe labels enter these fixed-score placement calculations. [Output: `screens/member_top_half_cluster_projection`](results.json).

For a planning power curve, test the weak null that a real recipe's **mean recorded seed score** exceeds the bad control with probability at most one half. Ties are conservatively non-successes. Exact binomial rejection/power calculations use the observed probability and its equal-tail exact interval. This assumes independent comparable recipes; it is weaker than #1044's member top-half screen and much weaker than “below every real member.” [Method: audit.py `known_bad_power`; binomial interval method: NIST source in SOURCES.md](SOURCES.md).

| Control / historical rule | Recipes strictly above control | 80%-power weak-screen recipes, low/base/high | Base at 90% power |
| --- | ---: | ---: | ---: |
| Boundary optimist / CE | 0/79 | No finite correct-direction plan | No finite plan |
| Boundary optimist / DAR | 79/79 | **6 / 6 / 9** | 6 |
| Boundary optimist / historical gated candidate | 62/79, 17 floor ties | **12 / 25 / 63** | 30 |
| Localized sign error / CE | 0/79 | No finite correct-direction plan | No finite plan |
| Localized sign error / DAR | 69/79 | **9 / 12 / 25** | 17 |
| Localized sign error / historical gated candidate | 0/79 | No finite correct-direction plan | No finite plan |

Source: [results.json `screens/control_placement`](results.json). Low/high invert the observed probability interval into counts; these are conditional planning ranges, not CI coverage for sample size. The alpha 0.025 allocation covers only these two control tests at one level. An additional exact column in JSON uses alpha **0.005** each for the ten control/level comparisons across the manifest's five levels, under a labelled 0.05 familywise planning assumption. It does not assert that the Level-0 success probability holds at other levels. Choosing the confirmatory rule adds its own selection issue; no multiple-rule adoption test is run here.

For gate recall, unsafe means at least one **SELECTED_INFEASIBLE** decision in the published split. A recipe is missed if any of its unsafe seeds passes the historical gate; seeds are not counted as independent unsafe recipes. All published split questions are inspected for this safety screen, including questions excluded from the numeric tau mask; unresolved decisions are never asserted unsafe or safe.

| EV5 public split | Unsafe recipes | Caught / missed | Historical gate recall, exact interval | Unsafe recipes for 80% chance of exposing a miss, low/base/high |
| --- | ---: | ---: | --- | ---: |
| Development | 66/79 | 15 / 51 | 0.227, 0.133–0.347 | **1 / 2 / 2** |
| Verification | 78/79 | 16 / 62 | 0.205, 0.122–0.312 | **1 / 2 / 2** |

Source: [results.json `screens/gate_recall`](results.json). Failure-detection power is `1 - recall^n` for independently drawn unsafe recipes; base 90%-power count is also **2** in these splits. This is a cheap **falsification** screen at a very poor observed recall, not a small sample that proves a good gate. No finite sample establishes universal recall=1. Bounds rely on binomial exchangeability and are conditional on public question support. Detecting failures is already achieved in the full observed census; no future collection is needed to establish that these historical gates miss members of this panel.

For the question side, **98 of 99** eligible real members have an infeasible selection somewhere in EV5's **24** questions. Their observed unsafe-question rates project **4 / 19 / 38 question draws** for an 80% chance of exposing each particular unsafe member (min/median/max across those fixed members, ASSUMPTION IID empirical question draws). This is not simultaneous 80% detection of all members and not 38 newly observed questions. Temperature dependence, new-member alternatives and unresolved coverage can change it. Keep the gate-recall screen's unsafe denominator separate from this question-detection calculation. [Output: `screens/question_screen`](results.json).

| Construction level | What this audit can hand over |
| --- | --- |
| L0 | Observed 79-recipe, 99-member census; measured historical tau variance/dependence; screen probabilities and conditional counts above. |
| L1 | NOT_IDENTIFIABLE: no matched public real-recipe score/question panel. |
| L2 | Same explicit gap; do not divide pooled counts by levels. |
| L3 | Same explicit gap. |
| L4 | Same explicit gap; this research cannot authorize its security-dependent construction route. |

Level mapping is sourced to [#1044's public member manifest](https://github.com/carbonphysicsai/Carbon/blob/fd3308af4041c32b8609cfccc5f5d5987b4a4a0f/docs/development/evidence/battery-score-tuning/proof-members-v1.json). Controls may be shared across levels; their repetitions do not add independent real recipes or new unsafe examples. Questions can be shared for paired comparisons, but a pooled precision count is not automatically a per-level precision count.

## Technical handoff to the Test Engineer, #1044

1. Use this audit as **public Level-0 planning evidence**, keyed by the pinned inputs and declared mask. Start the owner discussion from 160 distinct comparable real recipes and 150 resolved complete decision questions; show 150/200 recipe sensitivities. Keep the 150-question interim non-accepting unless a sequential protocol is registered.
2. Keep crossed recipe/question resampling, matched rule draws and fixed-score conditioning. Add a temperature-block sensitivity. Never count seeds, actions, trajectory samples or duplicate bootstrap draws as newly acquired recipes/questions.
3. State which question count the run means: offered, reference-resolved or common resolved. Measure the resolution rate, excluded question strata, seed allocation, ties and reference failures in the new run; do not inherit the historical missingness or architecture mix silently.
4. Retain #1044's known-bad member top-half endpoint. The weak binomial median counts are supplementary planning only. A failed historical known-bad or gate screen remains a failure, even with a narrow tau CI.
5. Obtain matched **public/stand-in** score legs and per-question decisions for the actual rule and every level to be claimed. Register unsafe examples independently of the scoring cases. This researcher has neither inspected nor requested sealed inputs; owner-only material stays owner-only.
6. Re-estimate the actual-rule and per-level variance, measured unsafe prevalence and screen power after those panels exist. Freeze recipe/lineage grouping and level weights before testing. Empty levels and missing Q3/G-FEAS legs stay **INCOMPLETE/NOT_IDENTIFIABLE**.
7. Before using these intervals as proof, validate coverage under the declared score/gate/tie and dependence regime; specify selection/confirmation, inferential look handling, multiple-rule/level family and uncertainty thresholds. These are unresolved **HUMAN_INPUT** or Test Engineer statistical work, not acceptance earned by this audit.

## Validation and maturity

Only allow-listed, digest-matched public blobs are inputs. The analyzer imports NumPy and the standard library, never Carbon, and cannot launch a solver or discover a hidden directory. Its numerical self-checks and deterministic aggregate reproduction are recorded with the runtime in [results.json](results.json). Local Docker was unavailable; native outputs remain research diagnostics and do not claim canonical runtime acceptance. PR CI acceptance is separate. [Reproduction commands and primary references](SOURCES.md).

Maturity earned: **research specification and measured public statistical evidence**. Not earned: new physics evidence, scoring-case variance, v3 rule proof, per-level power outside L0, prospective interval coverage, scientific qualification, launch readiness or economics. No solver/training/reconstruction run, no spend, no sealed material, no AX42; the owner decides the scientific protocol and PR Head handles delivery.
