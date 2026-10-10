# A realistic solver-alone and industry-workflow comparison

Ticket EQUAL-BUDGET-REALISM-01. RESEARCH / SPECIFIED / NOT_RUN. Scope: optimizer parameters and evidence/economics recommendations only. Authority snapshot 567dae6491a187253d463390225e019835de33f7; no reference tolerance, objective, admissibility gate or action grammar is changed.

## Source-confirmed incumbent methods

| Job | Primary evidence | What transfers | What does not |
|---|---|---|---|
| Battery | [Attia et al., Nature 2020](https://www.nature.com/articles/s41586-020-1994-5), closed-loop charging optimization; [Romeo Power engineering account](https://www.mathworks.com/company/technical-articles/modeling-and-simulating-battery-performance-for-design-optimization.html); [PyBOP paper](https://joss.theoj.org/papers/10.21105/joss.07874.pdf) | Sequential Bayesian experimentation, temperature/SOC/age lookup workflow, direct deterministic/stochastic battery-model optimizers | LFP experimental lifetime result is not v3 DFN/OKane plating/thermal evidence; parameter inference is not necessarily protocol design |
| Motor | [Motor-CAD/optiSLang workflow](https://www.ansys.com/training-center/course-catalog/electronics/ansys-motor-cad-and-optislang-optimizing-e-machine-designs); [official requirements/objectives interface](https://ansyshelp.ansys.com/public/Views/Secured/MotorCAD/v252/en/Motor-CAD_UG/MotorCAD/topics/ansys_opitslang.html); [Liu et al., COMPUMAG 2019](https://www.compumag.org/Proceedings/2019_Paris/files/papers/PB-A2-5.pdf) | DOE, ordinary metamodel optimization, multiobjective requirements, FE-informed global search and analytical/coarse-model reuse | An IPM/linear motor or TEAM 25 result is not a robot-joint torque/ripple witness or a CCX63 runtime |
| f02 | [COMSOL thermal optimal-control example](https://doc.comsol.com/6.4/doc/com.comsol.help.models.opt.optimal_heating_control/optimal_heating_control.html); [time-dependent sensitivity theory](https://doc.comsol.com/6.4/doc/com.comsol.help.opt/opt_ug_theory.5.10.html); [optimization method catalog](https://www.comsol.com/optimization-module) | Temperature-constrained control, derivative-free methods and adjoint gradients are existing tool capabilities | Rod heating is not accelerator burst scheduling; stationary heat-sink optimization does not establish f02 runtime or fidelity |

Vendor documentation demonstrates product capability, not the fraction of buyers using it. The Romeo account is a historical company-authored workflow, not a claim about the company's current commercial status. No “typical industry number” is fabricated.

Published quantitative context, all **source point low=base=high** rather than uncertainty bands:

| Source/task | Evaluation-count context | Reported duration context | Applicability boundary |
|---|---|---|---|
| Attia charging study | 224/224/224 candidate-protocol space | 16/16/16 days to identify promising protocols; exhaustive comparison described as over 500 days, a lower bound, not a fabricated finite high | Physical cycling with early prediction and Bayesian selection; candidate-space size is not total actual evaluation count |
| Liu TEAM 25 illustration | 100/100/100 Kriging sample points in introductory example | Approximately 50/50/50 seconds per 2D condition in that example | Not Carbon's complete motor panel; paper's illustrative savings ratio and full comparison describe different settings, so do not transplant either |
| Carbon battery cost context | Whole 30-cycle evaluation, not session or timestep | Owner-reported historical 91/91/91 CPU-seconds [battery comparator](../../../docs/development/challenge_pipeline/cheap-baselines/battery.md) | Current v3 whole-map quantiles and observer costs unmeasured |
| Carbon f02 cost context | Whole waveform evaluation | Owner-reported 2–3 CPU-minutes; low/high 2/3, midpoint 2.5 ASSUMPTION [f02 comparator](../../../docs/development/challenge_pipeline/cheap-baselines/f02.md) | Not complete-bank quantiles or ROM latency |
| Carbon revised motor | Geometry's complete command/angle/skew panel | HUMAN_INPUT | Legacy cost and owner peak-torque point do not price S3 |

## Arm definitions and fair information

Retain the owner-approved three arms:

1. **Direct solver search:** adaptive direct objective/constraint evaluations with a serious constrained local method and a separately registered global/multistart challenger where useful. Physical adjoints or analytic sensitivities are allowed only when the selected reference supplies valid derivatives; charge them.
2. **Carbon model screen then reference verify:** one permitted reconstruction, fixed model/policy, proposals from permitted inputs, independent full-condition reference confirmation.
3. **Ordinary industry surrogate/shortcut then reference verify:** exact cache if applicable, a calibrated ordinary ROM/response surface, and adaptive improvement under the same data budget.

Industry already employs metamodels. Beating direct FE alone while losing to the ordinary third arm does not establish V4 or a commercial advantage. Select the incumbent policy/portfolio on separate development/calibration jobs, freeze it before evaluation, and report both direct and ordinary-method results. Do not select a different winning competitor after observing each exam question. Allocate any competitor tuning/portfolio costs within the same accounting convention.

All arms receive the same permissible geometry/action bounds, previously published feasible designs, material/input laws, objective and hard limits. Data rights, acquisition costs, scope and disclosure must match. Never expose hidden reference labels or protected case identities. Use separately authorized public development panels; no exam feedback feed is created by this research.

## Challenge-specific recipes

### Battery v3

Use the registered five-band map; discrete cooling and switch branches remain distinct. A direct constrained branch optimizer can use COBYLA/pattern methods for nonsmooth event-limited outputs, with a differential-evolution/CMA-ES challenger where budgets permit. PyBOP establishes available open battery optimization methods, not a plug-in implementation of v3's multi-cycle safety contract.

Warm-start each branch from the same permitted known feasible protocols. Reuse symbolic/discretization structures only when supported. The electrochemical aged state is protocol-dependent: continuing a previous protocol's aged solution changes the question. Sharing a compiled model is different from sharing an initial physical state.

Exact cached observables settle covered banks cheaply. For new supported designs, use conservative local interpolation or constrained GP/EGO with an acquisition charge; every proposed optimum receives the full reference programme. Count all five band results, all charging-phase extrema, session crossings and capacity ratio. Never multiply finite per-band menu sizes into a brute-force map space when independent positive-weight band choices suffice.

### Motor

Fix the registered pole/slot/winding/skew topology. Use constrained pattern/COBYLA-type geometry search, multiple feasible starts and a global evolutionary challenger. Gradients require consistent meshing and differentiable/validated extrema; cogging and between-angle ripple can defeat a naive smooth proxy.

Warm starts can reuse a previous angular solution or nearby-geometry initialization only if the independent reference still converges to its registered result. Record exactly what was reused and its cost. Parameterize ordinary Kriging/RBF surfaces on full signed curves or supported Fourier observables; do not smooth away cogging or grade mean torque alone. The historical all-infeasible space is not the new S3 space. The owner's new 12.81 N·m point is owner-reported, source-point low=base=high with uncertainty/full receipt missing; it supports retention for study, not complete admissibility or measured design gain.

### f02

For the finite nine-action contract, direct enumeration and exact cache are legitimate strong incumbents. Do not hide this by giving solver-alone a poor randomized order. A continuous action grammar is prospective owner/packet authority, not adopted by this research.

For an authorized continuous version, exploit the fixed linear conduction stack: multi-input impulse/state-space representations with separate patches, initial-state response and cooling-regime-specific operators are strong candidates. Direct low-dimensional constrained search and transient adjoint control are challengers. The Elmer adapter may not yet supply gradients; lack of that adapter cannot be disguised as industry lacking adjoints. Keep event-aligned spatial peaks, crossing and recovery observations. A one-node RC average alone is a weak comparison.

## Pre-registered budget scenarios and stopping

The following numerical optimizer settings are **ASSUMPTION low/base/high**, offered to optimizer for development tuning, not production policy:

| Knob | Low/base/high | Meaning |
|---|---|---|
| Equal wall budget | 0.5/2/8 allocated-host hours | Sensitivity tiers, not typical industry project duration |
| Local restarts | 2/4/8 | Only if each fits the complete budget; warm starts common to arms |
| Space-filling DOE | 2/4/8 points per continuous dimension | Initial design, constrained by acquisition cap; dimensions from registered grammar |
| Global population multiplier | 5/10/15 times continuous dimension | Independent challenger; insufficient budget to complete a meaningful population is explicitly reported |
| Hourly planning rate | €1.37/1.37/1.37 | Owner planning assumption; no current-vendor quote |

Estimated whole-host charge for the wall tiers is **ASSUMPTION €0.685/2.74/10.96**. Allocated cores, cold p50/p95 costs, complete evaluation counts and reference numerical tolerances are HUMAN_INPUT. Do not extrapolate cheap 2D per-angle cost into a complete motor bank.

A resource cap stops the arm; it never lowers a physical requirement or accepted reference error. Infeasible proposals are expected and recorded. Typed reference/infrastructure failures, required refinements, optimizer/fitting time, startup and unsuccessful attempts are charged under the frozen policy. For incomplete full panels, no favorable design is reported.

Report cold one-job economics and reuse scenarios separately. Reuse-volume low/base/high is HUMAN_INPUT until a buyer receipt exists; a sensitivity-only hypothetical reuse count must remain ASSUMPTION. Do not amortize over fleet charging sessions when the unit is protocol-development decisions. A cache shared across arms is a common starting asset; a privately acquired bank is paid by its arm. Bank construction for earlier unrelated scopes is not free reuse.

## #998 handoff seam: replay versus adaptive experiment

The current [equal-budget contract](../../../docs/development/challenge_pipeline/equal-budget-design.md) has a preregistered complete solver_order and screen ranks before reference access. It validly replays fixed ordering against settled references. It cannot faithfully represent a policy that chooses the next point using earlier settled results.

For a true adaptive experiment, recommend a **prospective** policy/trace record: policy/configuration digest and independently timestamped pre-experiment registration; each proposal's timestamp, candidate digest and hash of the permitted observed prefix; full condition-panel identity; typed settled verdict; wall/core costs; warm-start/cache provenance; failure/refinement costs; stopping reason. Register the *policy* before the run, not its unknown future list of proposals. This requires separate optimizer-owned implementation and review. Never retrofit an adaptive trace into a fixed-order replay and call it preregistered.

Budget comparisons should use independently settled final reference values. In a finite settled bank, oracle best and regret are known; in continuous search the global best is generally unknown. Report best verified value and an explicitly bounded best-known comparator, with no invented global regret. UNRESOLVED reference candidates retain their failure semantics.

[The value bar](../../../docs/development/challenge_pipeline/value-bar-evaluator.md) requires measured costs and a paired uncertainty analysis. One shared bank is one cluster; times/angles/ambient bands are not independent jobs. At least two independent clusters are a tooling minimum for a bootstrap, not a promise of adequate statistical power. Sample size, accepted gain, value equivalence and scientific confidence policy remain with the registered owners.

## Evidence to request and decision rule

Data Collection/optimizer should return exact input/action/reference/observer/policy identities; legal common priors; full traces; per-candidate wall/core/RAM; cold/reused acquisition/fit/inference/optimizer costs; settled complete condition results; admissible best/equivalent designs; and independent whole-bank clusters. Test Lead owns whether those records pass the registered bar.

Actual battery-v3/motor-S3/f02 equal-budget gain, runtime quantiles, industry prevalence and buyer annual value remain **null/HUMAN_INPUT**. KEEP existing contracts; no runtime migration, policy selection or scientific result is earned. Validation of this PR is structural JSON, range arithmetic, citation/claim review and whitespace only. Hub purpose/dependencies/maturity remain unchanged.
