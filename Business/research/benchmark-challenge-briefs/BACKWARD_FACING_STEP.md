# Backward-facing step: internal-flow design brief

**PROPOSED / NOT RUN.** For Packets; not a common packet, registered question law or panel specification. Applies [BENCHMARK-CONTAMINATION-POLICY-01](https://github.com/carbonphysicsai/Carbon/blob/35571897441bba349ed1b0d3b9a4ddf2856bc544/Business/research/benchmark-contamination-policy/POLICY.md). Source IDs and rights are in [SOURCES.md](SOURCES.md); planning arithmetic is in [briefs.json](briefs.json).

## Buyer and real workflow

Named role: **internal-flow design/CAE engineer** at a duct, valve or flow-channel supplier; role label is an inference from published work, not an interviewed buyer.

The decision is to choose an expansion/recovery contour for lower total-pressure loss while meeting a separation/recovery requirement over specified operating scenarios. Rheinmetall Automotive's published engineering case uses parametric flow-channel design, CFD, DoE, metamodel optimization and robustness checks [B1]. SU2 independently documents adjoint pressure-drop optimization of an internal-flow component [B2]. These support the workflow class, not an exact customer request for a backward-facing step. Actual buyer limits, annual volume, current latency, willingness to pay and economic value remain HUMAN_INPUT.

A proposed question supplies a flow brief and a common menu of contours; the action is a verified feasible contour or NONE_FEASIBLE. Action count k, objective aggregation, ties, uncertainty and fallback rules are HUMAN_INPUT for Packets. An unresolved reference cannot establish NONE_FEASIBLE.

## Source anchor and physical scope

Use the [NASA/TMBWG case](https://github.com/tmbwg/turbmodels/blob/20a39f549dbff988a6accc421ac84dafc4487695/backstep_val.html) and [grids](https://github.com/tmbwg/turbmodels/blob/20a39f549dbff988a6accc421ac84dafc4487695/backstep_grids.html) at source commit **20a39f549dbff988a6accc421ac84dafc4487695**. Geometry, BC description, wall pressure/skin friction and velocity/turbulence profiles are public. The repository declares CC0-1.0 [N0]; preserve file-level provenance and notices when packaging.

Sourced anchor points, written as **source low/base/high**, repeat a point where no uncertainty interval is supplied; that is not a confidence band:

| Anchor quantity | Low/base/high | Meaning |
|---|---|---|
| Reynolds number based on H | approximately 36,000/36,000/36,000 | NASA corrected an older convention/value; freeze reference velocity and definition |
| Momentum-thickness Reynolds number before step | 5,000/5,000/5,000 | Separate Reynolds convention; do not equate it to Re_H |
| Boundary-layer thickness/H | approximately 1.5/1.5/1.5 | Approximate source condition, not a calibrated interval |
| Upstream Mach | 0.128/0.128/0.128 | Source operating point |
| Opposite-wall angle | 0/0/0 degrees | This NASA case uses a straight top wall |
| Measured reattachment x/H | **6.16/6.26/6.36** | Source reports 6.26 ± 0.10; interval type/confidence is not inferred |

The air/gas property deck, inlet development/profile mapping, back-pressure setting and exact turbulence-model variant must be transcribed and reviewed before construction; **complete Carbon solver deck: MISSING**. Nested grids are source assets, not accepted production resolution.

Keep a **2D turbulent separated-flow** job. No heat transfer, combustion, roughness, compressible high-speed extension or arbitrary 3D duct validity is claimed. This is broader than the published contour but narrower than an industrial EGR assembly.

## Proposed parametrized family and novelty

The following **ASSUMPTION low/base/high** ranges are public development proposals, not supported operating-envelope claims or adopted limits:

| Variable | Low/base/high | Proposed use |
|---|---|---|
| Recovery/ramp length divided by H | 0.5/2/4 | Replace the abrupt lower-wall recovery with a parametrized contour |
| Edge radius divided by H | 0/0.10/0.25 | Optional rounding; zero radius alone cannot establish novelty |
| Expansion-ratio multiplier relative to the source geometry | 0.95/1/1.05 | Perturb the normalized channel geometry; source ratio comes from the grid |
| Re_H multiplier relative to the corrected anchor definition | 0.8/1/1.2 | Operating variation; physical adequacy away from the source is unearned |
| Inlet boundary-layer thickness multiplier | 0.9/1/1.1 | Requires a consistent developed/profile BC, not independent inconsistent turbulence inputs |

Generator representation: normalized upper/lower wall contours, with a monotone recovery/ramp and deterministic radius/contour construction. Parameter combinations must preserve a connected positive-height channel and consistent BCs. Shape parameter count and exact construction law are HUMAN_INPUT. Do not use all extreme combinations until the reference route is adequate there.

Novelty distance: normalized wall-profile integral plus separately retained dimensionless operating/profile distances under #1022. Compare with every reconstructable published case in the versioned catalogue, including tutorials and derivative decks. Require **geometry novelty**, not only altered Reynolds number. Dimensional scaling at fixed similarity parameters and re-meshing are excluded equivalents. Coordinate window, normalizers, tolerances and exclusion predicate are HUMAN_INPUT.

These ranges cannot guarantee novelty before the metric is accepted and evaluated. Cases failing that check remain outside scored use. Public development witnesses must show anchor-answer retrieval/interpolation does not reliably reproduce the design decision while a properly specified reference can resolve it. Record the exclusion's effects on P support and Q rejection rates.

P is the future intended design/operating population; Q is the prospective stratified finite panel sampling law; w is the separately accepted decision/evidence weighting. All three remain HUMAN_INPUT. Proposed range endpoints do not define any of them.

## Limits, outputs and reference claim

Proposed outputs: mass-flow-weighted total-pressure loss between frozen planes, bottom-wall Cf and reattachment crossings, wall Cp, and selected velocity/turbulence profiles. Coordinate/unit conventions, compressible total-pressure definition, averaging, crossing extraction and uncertainty remain for the measurement contract. NASA's shifted Cp must not be mistaken for absolute total-pressure loss.

Buyer limits on loss, maximum separation/recovery length and geometric manufacturing/envelope constraints are **HUMAN_INPUT**. The published reattachment interval is an anchor-validation target, not a customer design limit. Mandatory conservation/convergence acceptance limits are also HUMAN_INPUT. No feasible design or contested frontier has been demonstrated; keep the original discovery requirement for feasible and near-infeasible coverage open.

Open reference route: proposed **SU2 RANS**, source pin **bc15466602a687d6fb796d5df7a12ce3fde0949a**, LGPL-2.1 license file [C1]. Container, dependency lock, closure/options mapping, meshes and output adapter remain unbuilt. Default SST is not automatically the NASA SSTm convention. An open code pin establishes a route, not a tested reference.

The measured anchor can support bounded experimental agreement after Carbon reproduces it with uncertainty. Self-convergence and reference-relative variant checks are different evidence. It does not establish loss validation for new contours, buyer-tool Tier 2, physical customer validity or launch readiness; the formal [credibility tiers](../../../docs/development/challenge_pipeline/round1/reference-credibility.md) require separate matched witnesses. Carbon reproduction and every claimed adequacy test here are NOT_RUN.

## Strongest competitors and equal-budget hypothesis

Use the strongest admissible combination: published expansion/loss correlations where applicable [B3], source-answer retrieval, a cached RANS response map with interpolation/error controls, coarse-to-fine RANS and direct adjoint or DoE/metamodel search [B1–B2]. Pipe-fitting correlations are not assumed valid for this planar boundary-layer geometry; disclose that mismatch and allow calibrated corrections. Constant source x/H is only a diagnostic shortcut.

Hypothesis: a learned decision model may screen many novel contours and focus verified solves near feasibility boundaries, yielding a better **reference-verified feasible** pressure-loss design at equal total resources. Actual gain and buyer monetary value are unknown and can be negative. Fast 2D RANS/adjoints or a compact map may already make the same decisions.

Charge Carbon's new bank, construction/tuning, inference, retries and final complete-panel verification; give solver-alone a realistic design initialization, adjoint/DoE search and cache. Use identical legal actions, scenario completion, hard limits and tie rules. Report feasibility disagreement and opportunity loss in the declared buyer units where defined. Best-so-far is not global optimum/regret without a complete finite truth bank. Apply [#1014's accounting](../equal-budget-realism/SPECIFICATION.md); no comparator run is claimed.

## First public feasibility/novelty/value panel and cost

Planning proposal: **32/64/128 complete design-condition cases**, ASSUMPTION low/base/high. These are complete physical evaluations, not a claim that question/action/scenario grouping is registered. Packets must allocate the bank into complete design panels; strata, action counts, scenario counts and statistical sufficiency remain HUMAN_INPUT and can change the estimate. A candidate can be picked only after every required scenario has resolved. Separate non-scoring anchor refinements from novel-design cases.

First measure the anchor route, conservation, convergence, BC sensitivity and observable normalization; then test contour construction, distance/equivalence, reference failure rate, attainable feasibility and cheap-decision agreement on independent public designs. Preserve failures and unresolved cases. Approved limits and adequate boundary coverage must precede a value verdict.

| Startup compute input | ASSUMPTION low/base/high |
|---|---|
| Host-hours per complete novel case, **including all required refinement solves and reductions** | 0.05/0.30/1.00 |
| Separate anchor reproduction/refinement host-hours | 0.25/2/10 |
| Cheap-comparator setup/calibration/check host-hours | 0.50/3/15 |
| Total host-hours | **2.35/24.20/153.00** |
| Compute euros at €1.37/host-hour | **€3.22/33.15/209.61** |

This replaces #1012's rough screening estimate with a broader complete-case planning allowance, not a measured cost revision. The rate is the owner's **ASSUMPTION** CCX63 planning basis, not a verified current vendor quote. Serial elapsed compute hours equal these totals only under the assumed uninterrupted single-host plan; staffing, queue/build time and parallel efficiency are unknown. RAM/storage needs: HUMAN_INPUT.

The base estimate fits the **owner-stated €500 cap** (source low/base/high €500/500/500). High is a planning scenario, not a bound. Labor, model training and the full equal-budget campaign are unpriced and outside this startup-bank estimate. Do not spend under this research authorization. Future authorized execution must stop/re-plan if runtime, memory, adequacy or cap fails; do not lower fidelity or relax limits to fit.

## Seven evidence-readiness answers

| Item | Answer now | Evidence / missing handoff |
|---|---|---|
| Registered panel | MISSING | Proposed family and cost counts only; Packets must register limits, actions, strata, P/Q/w and novelty law |
| Pinned solver | PARTIAL | Public SU2 source/license pin; executable container, dependencies, settings and hashes missing |
| Reference adequacy | PARTIAL source evidence; Carbon NOT_RUN | NASA measured anchor/grids; closure mapping, Carbon reproduction, variant convergence and loss applicability missing |
| Kit covering the panel | MISSING | Public inputs identified; need public generator, reference/reduction adapter, source catalogue and permitted data under miner-owned seeds |
| TRAIN set | MISSING | No generated bank; training-budget study must set size and construction budget; semantic split required |
| Comparator | PARTIAL design | Credible correlation/cache/RANS/adjoint routes identified; matched-admissibility implementation and receipts missing |
| Equal-budget route | PARTIAL specification | #1014 supplies the accounting; Challenge adapter, preregistration and public execution evidence missing |

Packets owns the next packet/question-law/panel-spec work. Data Collection may measure only after separate authorization. This brief adopts no physical tolerance, spends nothing and does not read hidden EVAL/STRESS material.
