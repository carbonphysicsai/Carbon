# Four closest Challenges: Design fidelity DEVELOPMENT candidate v1

**Owner direction:** Ryan, 2026-10-18: Design must be graded; selecting the correct option alone must not earn full credit. Design this for the four closest Challenges. This document specifies a prospective experiment, not an adopted scientific rule, a production score, or four completed experiments.

**Scope:** existing exposed Motor 8-pole/24-slot study, existing Cooling periodic-cell study, frozen f02 cold eight-action pilot, and frozen f08 eight-geometry summary pilot. Battery-v3, Motor 10p/12s, revised Cooling and f02 menu-v2 are separate jobs; none is silently substituted here. No new solver producer, extra acquisition campaign, hidden access or spending grant is created.

## 1. Common rule

Keep the Challenge's native gates, reference acceptance, fixed query accounting and the separately declared Physics minimum. A mandatory failure cannot be compensated by either score half. An unaccepted reference is a reference problem, never a candidate failure.

For an eligible model on a resolved whole question:

```text
TOP = 0.50 * A + 0.50 * D
D = min(V, C)
V = 1 / (1 + r / s_value)
C = min(B_margin, B_response, B_gap, B_resonance)  # applicable components only
B_component = 1 / (1 + L_component)
L_component = max_over_registered_quantity_and_case_strata(effective_error / s_quantity)
```

`A` is the existing broad Physics measure, kept fixed in this comparison. `V` rewards achieved, independently verified buyer value. `C` rewards the correctness of the predictions that make the design decision trustworthy. Components are continuous, unit-matched and visible separately. No perfect incumbent's observed `D=1` is copied into a Design eligibility floor: the prospective `D.minimum` is `None`.

This minimum is a deliberately conservative DEVELOPMENT candidate: a lucky choice cannot compensate for wrong limit predictions, and excellent predictions cannot compensate for poor design value. The existing mean-error critical consumer is a comparison arm, not silently relabelled as this worst-stratum candidate. Record mean, worst and every raw error so we can see whether a single point dominates. Use reference-resolution allowances before testing a worst error.

### Value regret

For minimization, `r = max(0, reference_objective(selected) - reference_best_objective)`. Reverse the subtraction for maximization. `s_value` is the regret receiving half value credit; it is not a safety tolerance. A reference-best label means best in the declared finite action set, not a global engineering optimum.

Preserve each native tie rule. Accepted objective-equivalence intervals may establish zero distinguishable regret; never invent an equivalence width from the models' errors. Where reference intervals are supplied, report regret and score bounds as well as the point estimate. For a minimized objective with feasible-action intervals `[l_i,u_i]`, `[min_i l_i,min_i u_i]` encloses the best value; use conservative selected-minus-best bounds, retaining dependence limitations. Do not collapse an uncertain best action to a decimal winner. f02's analytic action energy is exact conditional on settled feasibility, but that does not settle feasibility itself.

### Critical prediction errors

- **Margin:** predict each signed distance to a hard limit in native units, not just a pass/fail label. Positive is feasible. Compare predicted and reference margins on frozen critical cases, including unselected actions.
- **Response:** compare the predicted change between two actual supported points with the reference change. These are finite differences in physical units, not gradients supplied by a model, and no monotonicity law is invented. Do not call a large step local or an unobserved point tested.
- **Gap:** where the objective is a learned physical output, compare the predicted objective difference for every pair of resolved reference-feasible actions. A correct action ID with an incorrect gap loses credit. Analytically known objectives receive no predictive-gap credit.
- **Resonance:** for f08's existing summary-output contract, compare predicted and reference tip-peak frequencies. No full FRF output is added as a prerequisite.

For a supplied accepted reference interval `[l,u]`, an individual level error is `max(l-prediction, 0, prediction-u)`. For a point reference without such an interval, use absolute point error and label the result POINT_ESTIMATE_DIAGNOSTIC. A model cannot enlarge the allowance by reporting its own uncertainty. For a response or gap, propagate source intervals to an enclosing difference interval before computing the error. Do not treat two correlated solver rungs as independent uncertainty samples.

**Full Design credit requires both verified value-equivalence and every applicable critical error within justified reference resolution, on a complete registered critical panel.** It does not require impossible precision beyond the reference. Keep two separate outputs: `point_estimate_D` for the available common diagnostic panel and `full_credit_eligible` for the panel's coverage/resolution status. If required limit-side/proximity or reference-resolution evidence is absent, set `full_credit_eligible=false`, `registered_D=null`, and retain the numerical `point_estimate_D` and diagnostic TOP. Even a numerical 1.0 on that incomplete panel must be labelled PARTIAL_DIAGNOSTIC, not 100% of a complete Design exam. This is a reference/bank limitation common to every model, never a model failure or an artificial candidate score penalty. Historical packs remain unchanged.

Full-panel coverage is a pre-model property. The prospective DEVELOPMENT coverage hypothesis is a resolved case on each accessible side of each registered condition/limit, with absolute reference margin no larger than the corresponding base critical margin scale in section7. Those numeric widths are explicitly provisional acquisition/coverage bands, not new physical limits; report sensitivity and actual distances. A physically inaccessible side may be structurally not applicable only under a source-owned applicability statement fixed before predictions, not because the current bank happens to omit it. Official/qualified coverage and reference-resolution acceptance remain under their existing scientific authority. Current point diagnostics can proceed immediately without pretending those receipts exist.

Missing required material produces an explicit incomplete/unresolved component, not a silently improved score. If no reference-feasible action exists, report NONE_FEASIBLE and its prediction outcome separately; this pilot's achieved-value item is not measured for that whole question for any model, rather than inventing a perfect optimization result.

## 2. Frozen cohort and anti-gaming policy

1. Commit the model state, complete prediction panel and selected action before reference reduction. Reuse saved full panels when available; do not request extra inference just to reconstruct existing predictions.
2. Derive the critical cohort using references only and the rule below, without inspecting model errors. Pin actual case IDs, native observer version, units, quantity scales and ties in the measurement identity. Existing exposed Motor/Cooling results are retrospective diagnostics; do not call their cohort preregistered independent evidence.
3. For each mandatory condition and physical limit, take the closest resolved nonnegative margin and the closest resolved negative margin; stable action-ID tie break. Deduplicate a repeated case within each quantity. The primary loss is the largest normalized effective error across these registered slots; also report mean and worst error per quantity, condition and sign.
4. Always report each selected reference distance and absent sign side. The nearest available point may be far from a limit. Missing one side is a coverage limitation common to all models, not evidence that the model handles it. Apply the separate full-credit eligibility rule above: the current Motor/Cooling panels are incomplete critical-coverage diagnostics, not complete boundary exams. Do not silently label a supported-subset numerical 1.0 as full exam credit.
5. Retain all action predictions and all errors, including unselected actions and known-bad controls. Near-limit slots are a stress cohort, not automatically a sample from buyer population P. Keep P, proposal Q and weights w separate. The current pilots are descriptive finite banks; they define no new P/Q law or population weights.
6. The fixed response and gap panels below are common across models. A model cannot choose which predicted-safe designs are audited. Zero or one settled feasible action makes a feasible-pair gap structurally not applicable; an unresolved potentially competitive action instead leaves the affected best-value/gap evidence unresolved. Record the distinction.
7. A candidate with nonfinite/missing required predictions is candidate-invalid. Missing references retain the same common mask and unresolved report across models. A still-unresolved selected action is unscored pending reference resolution, never recorded as a candidate's proven failure.
8. No new starts, solver rungs, mesh levels, damping values, pair comparisons or menu alternatives are counted as independent buyer questions. One selected design across all mandatory conditions is one question. All attempted queries and repeat calls retain their existing cost accounting; these new arithmetic reductions do not create free model retries.
9. In a later protected bank, disclose formulas, input/output contracts and aggregate feedback; keep actual protected cases, cohort membership, references and sampling material private under the existing allow-list. These exposed pilots are not hidden exams. Use off-path/off-lattice audit points only where the future bank actually supplies accepted independent references; do not claim that coverage now.

## 3. Motor: choose a low-ripple motor that still supplies required torque

**Exact current job:** `motor-synthetic-decision-v2`, eight geometries, six commands, native 60-angle torque curve per point. Mandatory mean torque at least 4 N m and ripple fraction at most 0.30 at every command. Minimize the worst command's ripple fraction. Preserve native tie order (then higher worst mean torque, then frozen geometry order).

| Item | Measurement |
| --- | --- |
| V | Verified excess worst-command ripple fraction over the finite-bank best feasible geometry. |
| Critical levels | `m_torque = mean_torque_nm - 4`; `m_ripple = 0.30 - ripple_fraction`, using native curve observers. Test both sides where present across selected and unselected geometries. |
| Critical responses | Within each geometry: r01→r02, r02→r03, r03→b01 vary current density at zero current angle; r02→r04 varies current angle at density 10; r03→b02 varies angle at density 12. Compare mean-torque and ripple changes. The last angle step is 30 degrees, not a local derivative. |
| Critical gaps | Pairwise difference in worst-command ripple among all reference-feasible geometries. Existing resolved pair d04/d08 has a point gap about 0.00250369; do not demand an unsupported definitive near-tie ordering. |
| Existing A | Broad torque-waveform and declared cohort errors, unchanged for this experiment. |

**Available now:** all 48 reference curves and saved predictions for five actual KRR states. Existing critical diagnostic has 15 unique cells covering 18/24 possible slots; all six negative torque-margin sides are absent. No new solver or fit is required for the supported score calculation. Missing two-sided torque coverage remains explicitly untested.

## 4. Cooling: minimize pumping power while every operating condition stays safe

**Exact current job:** `ai-accelerator-cooling-synthetic-v1`, eight straight-channel/flow designs and six steady conditions. Derived die peak must be at most 100 C; hydraulic power at most 0.25 W at every condition. Minimize worst-condition hydraulic power. This is the old periodic-cell contract, not the revised TIM2/85 C job.

| Item | Measurement |
| --- | --- |
| V | Verified excess worst-condition hydraulic W over the finite-bank best feasible design. |
| Critical levels | `m_die = 100 - native_derived_die_peak_c`; `m_hydraulic = 0.25 - native_hydraulic_w`. Native die uses the 30-point profile, hotspot/TIM and peak excess; raw `peak_c` alone is wrong. |
| Critical responses | All cube-edge design pairs differing in exactly one of channel width, depth or flow setting, holding condition fixed (12 pairs × six conditions). Also rep-03→boundary-01 for inlet-temperature change only, and rep-04→boundary-01 for heat-load change only, within each geometry. Compare die-temperature and hydraulic-power changes. |
| Critical gaps | Pairwise difference in worst-condition hydraulic W for resolved feasible designs. Current d01 versus d03 gap is about 0.0911739 W. |
| Existing A | Broad peak/profile/pressure accuracy and existing cohorts, unchanged. No transient or independent OOD credit is invented. |

**Available now:** all 48 real CFD references, saved analytical/KRR/nearest-neighbour predictions, retained KRR state. Both analytical and KRR choose d03, yet critical die-margin errors differ; selecting d03 alone therefore cannot earn full Design. Existing cohort has 21/24 slots, with three missing sign sides and some far-from-limit points. No new CFD is needed for the supported diagnostic.

## 5. f02: accept the most useful burst without overheating

**Exact current job:** frozen eight-action cold pilot: coolant 30 C, h=2500 W/m2/K, initial 40 C, source split 0.5, rectangular bursts. Select the maximum analytic extra-energy schedule whose full 120-second top-die peak is at most 95 C. Preserve the frozen action order/ties and original B1–B7/B10 acceptance plus B8 same-side refinement rule.

| Item | Measurement |
| --- | --- |
| V | Best feasible added energy minus selected feasible added energy, in J. All eight declared actions are compared once references settle. |
| Critical levels | `m_thermal = 95 - peak_top_c` for every accepted action, including unselected schedules. The 84/85/86/87 W, 5 s proposals are a prospective critical block, not yet known near-limit truth. Report their actual resulting distances. |
| Critical responses | The three adjacent 84→85→86→87 W steps at 5 s, all other inputs fixed: predict the change in full-horizon peak temperature. These require no extra response-history model output. |
| Critical gaps | No learned-energy gap component: added joules are analytic inputs and receive no prediction credit. The thermal-response component supplies the discriminating prediction test. |
| Existing A | Broad peak prediction over the actual eight actions and frozen difficult block; no unpredicted time history is scored. |

**Acquisition already frozen:** 80 launches (36 convergence transients, 40 disjoint registered cold-context TRAIN, four missing step responses), reuse 12 matching old baselines. Retain fields required for B5; do not waive missing fields or alter limits. This design does not add launches. Current references/TRAIN do not yet support an actual accepted model score. One context with eight actions is one question, not eight independent jobs.

## 6. f08: choose a stiff, vibration-safe structure under the mass limit

**Exact current job:** eight prospective geometries, all three damping ratios 0.005/0.01/0.02 and 80–600 Hz band mandatory. Native limits: mass at most 0.45 kg, static tip compliance at most 0.03 mm/N and dynamic tip compliance at most 0.15 mm/N at each damping. Minimize worst tip compliance across the frequency band and all dampings. Tip-only observer; probe is not silently substituted.

| Item | Measurement |
| --- | --- |
| V | Selected feasible geometry's verified worst tip compliance minus finite-bank best, in mm/N. |
| Critical levels | Static margin `0.03 - static_tip_mm_per_n`; three dynamic margins `0.15 - peak_tip_z*_mm_per_n`. Check selected and unselected geometries. |
| Critical responses | Within each geometry, compare actual adjacent damping changes .005→.01 and .01→.02 in peak compliance and peak frequency. Do not impose a fabricated monotonic resonance-frequency law or treat damping settings as separate decisions. |
| Critical gaps | Pairwise difference in worst tip compliance among resolved feasible geometries. |
| Critical resonance | Peak-frequency error at each damping for every geometry, within the existing seven learned summary outputs. A right amplitude at the wrong frequency loses credit. Full complex FRF is a later contract, not a new blocker. |
| Existing A | Seven learned static/dynamic/frequency summaries across whole geometries. Exact geometry-derived mass is a hard feasibility input with no learned-prediction credit in A or C. |

**Acquisition already frozen:** reuse 255 complete public TRAIN rows, exclude all 256 TRAIN geometries including failed train-0016, acquire eight new geometries at three mesh rungs (24 launches). Native mode/mesh/frequency acceptance stays unchanged. Only eight primaries are model evaluation points; sixteen witnesses are reference work. TRAIN mode-ladder PASS alone does not certify a new EVAL optimum. No added solve or full-FRF output is required by this design.

## 7. Explicit DEVELOPMENT scale candidates

These are half-credit normalization scales for a comparative experiment, **not physical acceptance thresholds, solver tolerances, adopted buyer benefits or production values**. Existing V scales are retained for comparability. New critical scales below are transparent ASSUMPTION working choices; compare 0.5×, 1× and 2× without selecting a winner after seeing which model benefits. Freeze the f02/f08 measurement bytes before reading new EVAL outcomes. Motor/Cooling are already exposed, so sensitivity there is retrospective.

| Challenge | s_value | Critical base scales, used in their own units |
| --- | --- | --- |
| Motor | 0.01 ripple fraction (existing experiment) | Torque margin/response: 0.10 N m; ripple margin/response and objective gap: 0.01 fraction. Torque scale is 2.5% of the declared 4 N m floor; ripple scale is one percentage point. These are DEVELOPMENT normalization assumptions. |
| Cooling | 0.025 W (existing experiment) | Die margin/response: 1 C; hydraulic margin/response and objective gap: 0.025 W. These are DEVELOPMENT normalization assumptions. |
| f02 | 100 J (existing experiment) | Peak-temperature margin and adjacent-step response: 1 C. Joules have no critical-prediction scale. This is a DEVELOPMENT normalization assumption. |
| f08 | 0.01 mm/N (existing experiment) | Static margin: 0.003 mm/N; each dynamic margin/response: 0.015 mm/N; objective gap: 0.01 mm/N; resonance frequency/response: 10 Hz. Static/dynamic scales are one tenth of the declared limits; all are DEVELOPMENT normalization assumptions. |

Use **separate** 0.5×/1×/2× V-scale and C-scale sweeps (nine paired variants), preserving raw errors and the unchanged outer 50/50 ratio. Also reproduce the previous Motor normalization (.553677806526828 N m and .0415258354895121 ripple fraction) as a labelled historical-scale diagnostic; do not mix it with the tighter candidate above. A difference error uses the response/gap scale once; interval propagation handles reference uncertainty and is not a hidden double scale.

If accepted reference uncertainty is comparable to or larger than a proposed scale, report the resulting indeterminate resolution instead of certifying a distinction. No new reference-resolution floor is invented. The Physics minimum is whatever the separately pinned pack says; this document neither raises nor lowers it.

## 8. Acceptance experiment and outputs

### Actual supported-component readout, completed during this design

Product executed the existing saved-data cohort-MAE consumer (not the new worst/response/resonance specification). Summary `/home/miner/.carbon/product-scorelab-decision-critical-20261018/summary.json`, independently byte-hash checked by Optimizer: `066f66b558bc6d1560e54020813b8f1d38cfbec8d01095d9a2b35e4284078e84`. Cleanup receipt `codex-queue/reports/PRODUCT_SCORELAB_DECISION_CRITICAL_CLEANUP_20261018.json`. No new fits, inference or reference solves; no score adoption.

- Cooling analytical and KRR both retain zero finite-menu regret, but Design becomes respectively **0.4782043916** and **0.2936431617**, rather than both 1. Their prospective TOPs are **0.6613126170** and **0.5606129940**. Unsafe nearest-neighbour remains gate-failed.
- Motor baseline remains value-limited at D **0.3419193229**, TOP **0.3115014704**; length2/ridge1e-4 becomes critical-limited at D **0.1716579081**, TOP **0.2343902976**. Three other states still fail the unchanged A minimum. This reverses the eligible states' old order and demonstrates content sensitivity, not proof of improved buyer-value alignment.

These are actual executions of the **mean-cohort comparison variant using historical Motor scales**, not measurements of the tighter Motor scales, worst-stratum/response additions, nine-variant sweep or full four-Challenge rule. The point references still have no accepted uncertainty intervals and the boundary coverage limitations above remain.

Reuse the normal ScoreEngine and Challenge-native observers. Register a new measurement identity for each prospective rule; leave historical packs/results byte-identical. Keep model states, predictions, reference mask, selected actions and resource ledger fixed across value-only, existing cohort-MAE and proposed worst-stratum critical variants.

Required result fields per model and whole question:

- Native gate status and exact adverse outcome (unsafe selection, abstention, missed opportunity, reference unresolved); existing public enum compatibility plus bound raw cause where needed.
- A; reference selected objective; finite-bank best and reference scope; raw regret/units/interval; V; every C component; limiting component; D; eligible TOP or explicit null reason.
- All critical slot IDs owner-side, reference distances, missing sides, signed errors, worst/mean errors, response and gap errors; full-panel raw errors remain retained.
- Prediction/state/pack/source/reference/measurement digests; identical paired model set across candidate rules; all query attempts and repeat costs.
- Actual number of whole questions, independent bank/model-family clusters, P/Q/w scope and full-vs-partial boundary coverage; separate `point_estimate_D`, `full_credit_eligible`, `registered_D` and the diagnostic TOP label. One question per current pilot does not establish a generalization confidence interval.

Before any adoption, exercise the saved known-bad controls plus synthetic perturbations: correct pick but wrong margins; constant offset preserving rank; wrong contender gap; over-caution; optimism just outside a limit; missing/NaN prediction; failing repeat; incorrect resonance; analytic energy/mass copied perfectly; unresolved reference. A correct-pick/wrong-margin model must have C<1 and D<1. A selected proven unsafe design remains ineligible regardless of A or D. A candidate failing reference coverage must not be called scientifically failed. Passing analytic quantities must not increase C. Source/fixture tests are not evidence that a real model improves buyer value.

**Immediate execution:** Motor/Cooling supported diagnostics use saved data with no new inference/fit/solve. f02/f08 consumers receive the same new measurement reduction once the existing source-owned acquisition has accepted outputs. Product alone runs applications/provider jobs; Optimizer owns the score specification/consumer and Research independently audits interpretation. Lead publishes integrated source. Remaining gaps are actual reference coverage/acceptance, not a demand for an additional buyer approval or a new research campaign.

## 9. Design the evidence for the intelligence product as well as the exam

**Additional owner direction, same wave:** evaluation coverage must generate enough evidence to help customers use the product intelligently. Reuse the product/intelligence design already in the repository. This section changes evidence planning and retention; it does not implement that product or add an intelligence/novelty/demand reward term.

### Existing design located and read

Exact inspected source revision: `cf7950867e151faf3bc3327e21ecd3f54049bf62`. The root checkout is older; these paths were read from Git objects where absent on disk.

- `Design_Specs/Evidence_Intelligence_and_Agent_Research.md` §§3–7,9,14: durable evidence memory, approved Knowledge Layer, EvidenceBriefs, grounded Research Concierge, corrections and prospective value. This is owner-approved implementation design, not proof of a deployed intelligence product.
- `Business/research/customer-deliverable/PRODUCT_SPEC_V2.md` CMP-03/04/05/08/09: region-level model evidence; Trust Map; decision evidence; Envelope Guard; budgeted Decision Assistant. Guard TRUST/VERIFY/REFUSE is a separately governed product policy, not an exam-score output.
- `Design_Specs/Physics_Intelligence_System.md` §§4,5,9,10: keep informative failures, preserve epistemic status, context-of-use/escalation and intervention/outcome lineage.
- `Design_Specs/Landscape_Agent.md` D1/D4/D5/D7/D11 and four ports: evidence store, failure atlas, coverage/frontier/transfer maps, product-attempt outcomes and controlled release.
- `Design_Specs/Customer_Bounds_Specialist.md`, `Design_Specs/Product_Qualification_Evidence.md` and `Design_Specs/Specialist_Bank.md`: bounds-based use, exact artifact, fresh job-shaped product evidence and written escalation edges. Competition rank nominates; it does not qualify the product.
- Existing `carbon/trust_map/core.py::build_maps` and `docs/development/TRUST_MAP.md`: Challenge-neutral PUBLIC/RELEASED aggregate error/disagreement maps, two axes plus a band and explicit marginalized inputs. Error/disagreement support exists; it is not calibrated uncertainty or a query-level safety guarantee. Use this component rather than author a second map system. Product Guard source exists in a bounded DEVELOPMENT profile; that does not establish real-model TRUST acceptance.

### What a customer should eventually be able to ask

1. For this exact model and operating context, what reference-relative error has actually been observed, particularly near my limits?
2. Is this query inside tested support, merely inside the input box, or outside applicable physical/reference support?
3. Which output or constraint is unreliable here, and how often did the model recommend an unsafe or needlessly cautious choice in matching evidence?
4. Which design alternatives did the model confuse, by how much, and what was the realized verified regret?
5. Does the local response follow the reference when load, operating condition or design changes?
6. When should I request a solver or human check, and what does that full workflow cost in time and compute?
7. What evidence supports the answer, what contradicts it, and what remains unknown?

The evidence must support these answers with stated limitations. A global score, a pooled heatmap or model agreement alone cannot answer them.

### Coverage axes to preserve for the four pilots

| Challenge | Decision-relevant coordinates and facets | Customer-use questions the data should support | Current support and explicit gap |
| --- | --- | --- | --- |
| Motor | Current density × current angle, faceted by exact geometry; retain all six geometry variables, torque waveform observer and command groups. Later geometry generalization uses actual disjoint geometries, not more angles on a trained geometry. | Torque/ripple trade-off; which command is limiting; whether a design change or increased current makes a recommendation unreliable. | Eight geometries × six commands, with all saved predictions. Six absent negative torque sides and sparse angle/current combinations; no continuous 6-D geometry trust envelope is established. |
| Cooling | Heat load × inlet temperature; facet by channel geometry, flow policy and hotspot ratio/location/width. Never pool materially different hotspot conditions into an unexplained safe-looking cell. | Thermal versus pumping trade-off; temperature/load/flow sensitivity; when local die heating or a geometry/flow choice needs verification. | Eight designs × six exact contexts. The grid is sparse and some near-limit sides are absent. No transient controller, arbitrary hotspot or revised-TIM applicability is inferred. |
| f02 | Peak burst power × on-time, with coolant/h/initial-temperature/source-split/waveform as explicit context. Preserve full-horizon peak definition and the reference's retained transient/field evidence. | How much extra energy is feasible; how quickly the thermal limit is approached; whether a proposed burst change is supported or needs a solver. | Eight evaluation schedules at one fixed cold context, plus disjoint public TRAIN. This can describe a cold-context slice, not a coolant/h/initial-state trust volume. |
| f08 | Actual geometry coordinates, with thickness/rib geometry/relief as decision-relevant facets; retain all six inputs and damping-specific peak amplitude/frequency and the evaluated frequency band. A two-axis view must identify every held-fixed or marginalized variable. | Static/dynamic/mass trade-off; resonance-location error; damping sensitivity; which geometry/damping is weak and should be checked. | Eight new EVAL geometries with accepted mesh/mode/frequency witnesses when acquired; 255 TRAIN rows remain TRAIN. No full FRF prediction fidelity or continuous six-dimensional qualification is inferred. |

Display exact sampled support first. Empty cells are NO_DATA, not zero error. Neighboring cells do not automatically justify interpolation; the same numeric input bounds do not establish joint coverage. A broad surface plot is inappropriate where only a few coupled contexts exist. Distinguish marginal summaries from evidence at the customer's exact joint context.

### One underlying evidence record, several bounded uses

Retain the following in the existing source-owned per-case/pair/raw result stores; index the same immutable facts rather than create a duplicate intelligence fact store:

- Exact artifact/build/runtime, input and output contracts, Challenge/job/law, observer and reference/solver identities; case context, units, applicable physical/reference envelope and training-support role.
- Full committed predictions and resolved reference quantities in native units; signed residuals and margins, per-output errors, actual reference intervals where available, missing outputs and failure reasons. Keep the complete action panel and unselected alternatives, not only winners or averages.
- Cohort/proposal membership, P/Q/w/evidence role, sampling/draw policy, repeat/mesh/shared-bank/model-family dependence, exposure/publication state and actual denominator. These records support uncertainty estimates without pretending repeated conditions or sibling fits are independent.
- Local response-pair endpoints, which inputs differ, observed finite differences, contender comparisons, provisional ranks, selected action, verified feasibility/value, abstention, missed opportunity and unresolved outcomes. Derived metrics reference the same underlying predictions.
- Broad A and all Design subcomponents, native gates, law diagnostics if actually applicable/measured, repeatability/export observations if run, and adverse findings for weak as well as strong models. FAILED_INFRA/FAILED_REFERENCE are not negative model-physics labels.
- Measured build, inference, search/probe, verification/refinement/fallback and I/O/startup costs; hardware/resource context and uncertainty. Allocated vCPUs are not measured CPU time; current Cooling multithread timing caveat stays attached.
- Retained reference artifacts necessary for replay and adequacy under the existing retention plan; digest, custody/access, source corrections and claim dependencies. No promise to retain every optional large field or collect private customer telemetry is made.

These facts feed distinct reductions: (a) the fixed exam score; (b) internal regional error/failure/coverage and next-data diagnostics; (c) an independently authorized PUBLIC/RELEASED or customer evidence projection; (d) later approved EvidenceBrief/Concierge guidance. The score is not an extra fee for interesting data, and these reductions confer different authority.

### Choose test locations prospectively, with a finite next-data loop

1. Execute the already frozen Motor/Cooling reductions and f02/f08 acquisitions. Do not duplicate their TRAIN/references or add a full grid merely to fill a picture. Extra structured reductions over retained predictions require no new solver labels.
2. Build an internal coverage matrix from those actual outputs: representative operating support; limit sides/proximity; local changes; close alternatives; whole-design generalization; valid-domain edges; unsafe/cautious outcomes; reference failure and cost. Tag every cell EVIDENCED/PARTIAL/GAP, preserving failures as evidenced outcomes.
3. For later data, freeze the declared buyer-law representative sample separately from deliberate critical/edge/perturbation probes. Preserve P/Q/w; do not replace representative evidence with only near-limit points. Do not choose official scored points adaptively from a particular model's error map.
4. Prioritize additional **public development/product** references where they close a named customer-use gap or disambiguate a recommendation: a missing accessible limit side, a coupled-context hole, a close design comparison or a reference-limited margin. State input tuple, reusable existing data, required observable/accuracy, proposed role, solver cost and the specific claim it could support. Freeze a finite scope/cap with Product before execution. A map hole alone is not a mandate for every possible combination.
5. Set target uncertainty/decision resolution for each intended regional statement before choosing its sample count. Report independent questions and model families, not raw rows alone. The current one-question pilots can demonstrate arithmetic and measured failures; they cannot estimate reliable regional failure probabilities or validate general customer guidance.
6. Keep TRAIN, rule/scale calibration, and independent guidance/product evaluation roles separate. Evaluate a frozen map/Guard/Assistant on independent matching evidence and actual optimizer-selected candidates before claiming that its advice reduces mistakes or verification cost. Reusing the score-tuning cases cannot validate the resulting guidance. Full product qualification remains separate and should not be made a prerequisite for the present development ScoreLab experiment.

### Protected exam and customer-knowledge boundary

An intelligence service must never query the protected exam vault to answer a customer/miner question. Internal records remain custody-bound. Release only approved, versioned and rights-eligible aggregates/briefs through the existing disclosure process; customer status does not unlock cases, IDs, unreleased reference labels or reconstructive metadata. Public/released development panels may support the first descriptive views without waiting for retirement of a hidden bank. Customer-host product verification is a separate authorized evidence route.

The immediate deliverable from these pilots is a **reference-relative use/limits evidence table** per exact model, with visible gaps and solver-escalation candidates. It is not automatically a TRUST/VERIFY/REFUSE policy, a calibrated risk probability, physical validation, qualification or prospective proof that the intelligence improves a customer's decisions. Keep corrections and withdrawn claims linked to every dependent map/brief/report.

## 10. Owner lock: main evaluation focus and continuing data cycle

Ryan directly approved this as Carbon's main evaluation focus on 2026-10-18 and directed that accumulated evidence inform future batch data, with retirement into the public training pool. The durable owner record is `.agent/decisions/2026-10-18-OWNER-EVALUATION-FOCUS-AND-DATA-CYCLE-01.md` (source staged in Optimizer's author worktree for Lead integration).

This locks the direction: gates, broad Physics and graded verified-value/critical-fidelity Design, plus retained evidence supporting customer use. It does not adopt every experimental normalization or deploy the candidate score. Aggregate historical evidence may guide a separately frozen future acquisition/SamplingPlan; no per-miner, in-flight or post-outcome exam changes. Representative P, stress Q and evidence weights remain distinct, with material changes prospectively versioned.

Retire/expose through the existing bank machinery, then publish eligible retired cases through the existing signed public training pool only after all dependent active uses and required reveal/journal steps close. Published or answer-inferable material never returns to hidden scoring. Shared-bank dependencies, source failures, holdout custody, equal release and immutable TRAIN manifests remain explicit. The resulting public pool grows across a Challenge's life while each construction/evaluation job stays pinned to its own version.

## Existing evidence and reuse

- `FOUR_CHALLENGE_EVALUATION_CONTRACT_20261018.json`: sole current data/source index and existing packet identities.
- `RESEARCH_SCORELAB_PUBLIC_CRITICAL_MARGIN_DIAGNOSTIC_20261018.md`: actual saved Motor/Cooling errors, coverage and historical-scale sensitivity.
- `RESEARCH_SCORELAB_GRADED_DESIGN_RESOLUTION_RECOMMENDATION_20261018.md`: supported quantities, reference semantics, continuous value and critical-fidelity recommendation.
- `OPTIMIZER_DECISION_CRITICAL_READOUT_20261018.py`: existing saved-data cohort-MAE comparison consumer; not a worst-stratum implementation.
- `OPTIMIZER_F02_COLD_DUAL_PACKET_20261018.py` and `OPTIMIZER_F08_SUMMARY_DUAL_PACKET_20261018.py`: existing value-only first-pilot consumers; not yet implementations of all components specified here.

**Maturity:** specified prospective DEVELOPMENT experiment. Motor/Cooling supporting errors are measured; the full four-Challenge score design is not implemented, runtime-tested, adopted or qualified by writing this document.
