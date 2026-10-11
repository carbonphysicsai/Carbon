# Original 3D periodic metagrating: diffractive-optics design brief

**PROPOSED / NOT RUN.** For Packets; not a registered packet or question law. Applies [BENCHMARK-CONTAMINATION-POLICY-01](https://github.com/carbonphysicsai/Carbon/blob/35571897441bba349ed1b0d3b9a4ddf2856bc544/Business/research/benchmark-contamination-policy/POLICY.md). Preserve the 3D periodic electromagnetic job.

## Buyer and real workflow

Named role: **diffractive-optics R&D/design engineer** choosing a beam-deflecting silicon pattern and thickness under a stated efficiency and unwanted-order contract. The role is inferred from documented work, not an interviewed procurement role.

Corning/Harvard research describes library-based design, full-wave forward/adjoint shape optimization and manufactured metagrating comparison [P1]. Ansys independently documents diffraction-order simulation for grating design [P2]. These support a real simulation-based decision class; neither confirms demand for Carbon, exact annual decision volume, customer limits or willingness to pay. Those are HUMAN_INPUT.

Proposed question: supplied period/deflection brief and constraints, select a verified feasible pattern/thickness from a common menu or NONE_FEASIBLE. Packets owns k, masks/actions, aggregation, tie handling and uncertain/no-feasible rules. Reference uncertainty is not proof of infeasibility.

## Published anchor and open assets

The [NanoComp testbed](https://github.com/NanoComp/photonics-opt-testbed/blob/a06518872de6ec82bb4511190e544211539f55f1/Metagrating3D/README.md), masks and [Meep script](https://github.com/NanoComp/photonics-opt-testbed/blob/a06518872de6ec82bb4511190e544211539f55f1/Metagrating3D/metagrating_meep.py) are pinned at **a06518872de6ec82bb4511190e544211539f55f1**, with repository MIT license [P0]. They specify normally incident substrate-side light, TM polarization and desired transmitted **+1 diffraction order**, periodicity in x and y and a silicon pattern uniform through finite z thickness. Uniform thickness does not reduce Maxwell fields to a 2D solve.

| Source quantity | Source low/base/high | Interpretation |
|---|---|---|
| Vacuum wavelength | 1,050/1,050/1,050 nm | Fixed source point, not a dispersion interval |
| Deflection angle | 50/50/50 degrees | Output direction; **not** oblique incidence |
| Silicon / silica refractive index | 3.45/3.45/3.45 and 1.45/1.45/1.45 | Fixed nondispersive source model |
| Silicon thickness | 325/325/325 nm | Source geometry point |
| x period | 1050/sin(50 degrees) at all three points, nm | Source-defined relation; not an efficiency formula |
| y period | 525/525/525 nm | Source definition Py = 0.5 × wavelength |
| Original mask grid, devices 1–3 | 118 × 45 at all three points | Source design encoding; interpolated copies are not new devices |

These repeated points express absence of a reported range, not physical certainty. The testbed reports Meep and RETICOLO efficiencies for its published designs; it contains no fabrication measurements for these exact patterns. A source script printout is not a Carbon reproduction.

## Proposed family, novelty and limits

Use a periodic **binary silicon/air mask**, reflection symmetry in y as in the source, with finite silicon thickness and full x/y/z fields. Generate new masks independently in normalized cell coordinates; freeze binarization, contour/pixel interpretation and material-grid mapping. Interpolation can change the physical material model and must not silently create fractional-permittivity hardware claims.

Public development range proposals:

| Variable | Low/base/high | Status |
|---|---|---|
| Deflection angle | 40/50/60 degrees | ASSUMPTION; implied Px changes with the source relation |
| Thickness | 250/325/400 nm | ASSUMPTION; not a fabrication capability claim |
| Wavelength | 1050/1050/1050 nm | SOURCE fixed point; no new bandwidth/dispersion promise |
| Py/wavelength | 0.5/0.5/0.5 | SOURCE fixed ratio |
| Silicon / silica index | 3.45/3.45/3.45 and 1.45/1.45/1.45 | SOURCE idealized material model |
| Mask degrees of freedom / geometric construction parameters | HUMAN_INPUT | Must preserve a genuine two-direction periodic pattern family |

Normal incidence, source polarization convention and lossless source materials remain fixed. Do not substitute a 1D stripe family, effective-index 2D model or arbitrary dispersive fabrication stack. A smaller shape parameterization may reduce construction cost while retaining 3D fields, but loses freedom to discover unconstrained freeform masks; that tradeoff needs an explicit packet scope.

Compare each generated mask to **all** published testbed devices, interpolated encodings and other reconstructable catalogue designs. Use periodic occupancy difference after valid translations/coordinate symmetries, with separate distances in Px/wavelength, Py/wavelength, t/wavelength, material and excitation. Require mask novelty, not only altered thickness or angle. Resampling, mere translation and joint wavelength/geometry scaling in this nondispersive model do not establish novelty. Symmetries that exchange the desired order are not automatically equivalent.

The catalogue, extraction uncertainty, normalizers and “far enough” predicate are HUMAN_INPUT. These ranges are compatible with the proposed metric structure, but **cannot be called novelty-qualified** before public witness tests and scientific acceptance. Source-answer retrieval, mask-library interpolation and response maps must be tested on complete independent design panels. A novel mask with the same easy decision can still fail the value test.

Proposed outputs: normalized power in the specified transmitted order; reflected/transmitted power by propagating order; total R/T and energy-accounting residual; convergence/uncertainty evidence. Reference script currently extracts desired-order power with a separate normalization run; **complete reflection/order/energy reductions and generalized geometry interface are missing**.

Buyer minimum efficiency, unwanted-order/reflection caps, dimensional fabrication rules, etch bias/tolerances, accepted uncertainty and conservation/convergence tolerances are **HUMAN_INPUT**. Passivity bounds and sum-of-order energy accounting are physical consistency checks, not adopted numeric gate tolerances. Do not invent a fabrication minimum from the source's pixel size. Feasible/near-infeasible coverage and a contested design frontier remain unmeasured.

P is the future mask/brief population; Q is its prospective finite stratified sampling law; w is evidence/decision weighting. Each is HUMAN_INPUT. Uniform draws from a bitmap are not a scientifically accepted task population.

## Reference route and claim ceiling

Proposed reference: **Meep FDTD** source pin **b08d226ba311a04e59c984e97f3e88dd82bc56d1**, GPL-2.0-or-later [M1]. Preserve the source's substrate-side excitation, normalization, periodic boundaries, PML/domain and exact order convention. Future checks cover spatial/time resolution, decay/resonance completion, PML/domain sensitivity, material-grid interpretation and all propagating orders. Do not treat the tutorial's numerical controls as accepted qualification tolerances.

Open comparator/witness route: **S4 RCWA**, source pin **7fd00a231610bff51f5c7de5f723e3956eab7453**, GPL license text [R1]. Its documented layered-periodic fields and order-resolved flux support this family in principle. General mask materialization, harmonic convergence, output normalization and dependency/container pins remain unbuilt. Published RETICOLO results can be cited as numerical witnesses; redistributable RETICOLO executable rights are not established by the testbed's MIT license.

Agreement of independent numerical routes on source masks can support bounded code verification/comparison after Carbon runs it. It does not establish exact-pattern fabrication validity, dispersion validity, buyer-tool Tier 2 or customer hardware performance. Use [reference credibility](../../../docs/development/challenge_pipeline/round1/reference-credibility.md): formal Tier 2 requires matched task witnesses as well. Meep reproduction, S4 comparison and variant adequacy here are NOT_RUN.

## Strongest cheap baseline and equal-budget gain hypothesis

The analytic grating relation fixes angle/order kinematics; it does **not** predict efficiency. Admit source-mask lookup, tuned meta-atom/pattern libraries, cached order-efficiency response maps and converged open RCWA. Strong solver-alone competition includes direct RCWA gradient/shape search and Meep's adjoint optimization route where compatible. Give these methods the same action set, public kit, initialization opportunities and final reference verification.

Hypothesis: a fast model may screen novel patterns/thicknesses and direct full-fidelity verification toward high-efficiency feasible candidates under the same total budget. Coupling and resonance can make a crude library miss candidates; established RCWA or direct optimization may already solve the task cheaply. No positive gain, speedup, euros saved or customer value is measured.

Charge bank generation, construction/tuning, cheap screening, comparator calibration, failed runs, refinement and complete scenario verification. Hold fixed output conventions and all hard limits. Report reference-verified best feasible action, verdict disagreement and buyer-unit loss where defined; no known global optimum is inferred from the published high-efficiency designs. Full [#1014 equal-budget accounting](../equal-budget-realism/SPECIFICATION.md) applies. Cheap-baseline success is a legitimate negative result for Carbon's proposed incremental value.

## First public panel and compute estimate

Propose **32/64/128 complete independently generated design-condition cases**, ASSUMPTION low/base/high. This is a bank-size allowance, not registered question/action/scenario grouping. Packets must allocate complete design panels; scenario definitions and allocations remain HUMAN_INPUT and can change the estimate. They must fit the declared fixed-wavelength material model and avoid changing one hardware design's period inconsistently between scenarios. The first panel is public development evidence, not hidden EVAL/STRESS.

Start with non-scoring anchor reproduction on the full source-device set and independent RCWA/FDTD witnesses. Then check new-mask construction/equivalence, order accounting/convergence, reference failure/uncertainty, feasible-frontier existence and same-decision shortcuts. A finalist requires every mandatory scenario resolved. Do not lower full-3D fidelity or relax physical/fabrication limits to pass.

| Startup compute input | ASSUMPTION low/base/high |
|---|---|
| Host-hours per complete novel case, **including normalization/device runs, required refinements and output reductions** | 0.02/0.25/2.00 |
| Separate source-device/anchor convergence host-hours | 0.50/5/25 |
| RCWA/library comparator setup/calibration/check host-hours | 0.50/5/25 |
| Total host-hours | **1.64/26.00/306.00** |
| Compute euros at €1.37/host-hour | **€2.25/35.62/419.22** |

This deliberately broadens #1012's screening allowance for full-case normalization/refinement and comparator work; it is not new measured performance. CCX63 hourly price is the owner's **ASSUMPTION** planning basis. Serial compute elapsed hours follow the assumed single-host schedule; build, staffing, queue time, memory capacity and parallel efficiency are unknown. RAM/storage requirements: HUMAN_INPUT.

The base scenario fits the owner-stated **€500/500/500 cap**, and the high planning scenario also fits. Neither is a guarantee: the first timing/memory/adequacy receipts can invalidate the estimate. Labor, model construction and the later full equal-budget campaign remain unpriced and outside bank-startup cost. No spend is authorized here; future execution must stop/re-plan rather than silently narrow the job.

## Seven evidence-readiness answers

| Item | Answer now | Evidence / missing handoff |
|---|---|---|
| Registered panel | MISSING | Brief/ranges only; Packets must register constraints, scenarios, masks/actions, P/Q/w and novelty law |
| Pinned solver | PARTIAL | Meep/S4 source-license pins; actual builds, dependencies, digests and adapters absent |
| Reference adequacy | PARTIAL source evidence; Carbon NOT_RUN | Published RETICOLO/Meep comparison; Carbon reproduction, S4 witness and variant/order/convergence checks absent |
| Kit covering the panel | MISSING | Open masks/script identified; generalized generator, catalogue/distance extractor and all graded-output reductions missing |
| TRAIN set | MISSING | No generated bank; source masks are public anchors, not a qualified variant TRAIN bank; budget study required |
| Comparator | PARTIAL design | S4, libraries and direct search are credible routes; matched implementation, harmonic study and receipts absent |
| Equal-budget route | PARTIAL specification | #1014 supplies accounting; new Challenge adapter, preregistration and public execution evidence absent |

This preserves the original 3D optics proposal without claiming feasibility, launch readiness, hardware credibility or superiority. Packets owns the next design contracts; scientific acceptance and adoption remain human decisions.
