# Open material/input sets and equal-budget value screen

**OPEN-DATA-CHECK-01 / research only / DEVELOPMENT / SPECIFIED.**
Source cut-off: 2026-10-10. Repository authority and existing proposals were read at main `65ef88660fe02018c26f54d14655fe7b66354aa8`. The user instruction is the active research ticket; WAVE has no selected successor for it. [Business Canon](../../Business_Canon.md), the Constitution and invariants govern claims. Working scope: read public sources, inspect small published calibration files, recommend, and publish one PR to PR Head. No existing packet, optimizer, runtime, readiness, score or portfolio configuration is changed.

KEEP existing decision definitions and cost hypotheses as historical specifications; WRAP them with this source and rights audit. No solver, fitting, training, paid resource, hidden material or AX42 access. No customer approach. The Hub is retired and unchanged. [Owner direction](OWNER_DIRECTION.md) prospectively corrects #995's motor recommendation.

## What counts as a complete open set

An internal source set must connect geometry, material identity and processing, constitutive input, assembly/history, operating conditions and observations to the **same intended case**. A coherent family can contain its paper, supplements and repository; it need not be one file. Multiple families can be used only with an explicit applicability bridge, which this research cannot invent. Rights must permit the intended commercial-company research, modification and public miner-kit redistribution; a publicly readable PDF is not that grant.

Separate these conclusions:

- **RIGHTS_VERIFIED_INGREDIENT:** an explicit license was found for the identified asset. Obligations remain; this is a desk finding, not legal approval.
- **PUBLISHED_PARAMETER_MODEL:** a law/coefficient set is available, but its experimental provenance, completeness or admissible deformation/temperature range may be insufficient.
- **VERIFICATION_FIXTURE:** defined numerical inputs useful for implementation checks, with no implied material calibration.
- **COMPLETE_FOR_PROPOSED_JOB:** every mandatory condition/input and rights item is connected. None earned this disposition here.
- **HOLD_OPEN_SET_NOT_CONFIRMED:** search did not establish completeness. This does not assert universal nonexistence.

A rights-complete ingredient need not be scientifically adequate; a scientifically relevant paper need not release its data. Solver GPL does not automatically license independent material tables, vendor drawings or user-contributed decks. CC-BY attribution and modification notices must survive redistribution; NC/ND assets are not cleared for Carbon's intended use merely because a paper calls them open. See [license deeds and the exact source register](SOURCES.md). Owner/counsel retains rights acceptance.

**Number convention:** dates, DOI/version identifiers, hashes, coordinates naming files and section labels are identities. Source observations are fixed points with low=base=high at the stated record, not uncertainty bounds. All cost and rubric ranges below are explicitly ASSUMPTION. Missing physical ranges/limits, measurement uncertainty, actual costs and actual design gain are HUMAN_INPUT/null.

## Solenoid pole: useful open primitives, incomplete registered conditions

The [current first-panel proposal](https://github.com/carbonphysicsai/Carbon/blob/65ef88660fe02018c26f54d14655fe7b66354aa8/docs/development/challenge_pipeline/magnetics-first-panels/solenoid-pole.md) fixes an axisymmetric **non-PM** pot yoke, translating armature and annular winding. It requires nominal, hot-material/winding and permitted axial-gap conditions. It grades a complete force-stroke/current envelope and stated-temperature resistive loss. Thus a permanent-magnet demagnetization/recoil law is **not applicable to this architecture**; adding magnets would create a different job. Steel B–H(T), winding and loss inputs are required.

[S01 GetDP](SOURCES.md) was pinned at `259f4c38ce89c3ad4775aecf515840bd3331b0aa`. Its GPL-2.0-or-later source supplies an electromagnet geometry/formulation and generic steel tables. These are reproducible open numerical ingredients. The tutorial is planar, and its material example is not a measured pot-yoke steel family over temperature. It does not supply the complete graded force/loss contract. An axisymmetric option elsewhere in the solver is a route to implement, not evidence of that implementation.

[S02 TEAM 20](SOURCES.md) supplies steel B–H, DC excitation, geometry and force/field comparison quantities in a coherent benchmark family. It is a three-dimensional static-force benchmark, not the prescribed axisymmetric profile family. No explicit reusable data license was located in the inspected specification. It also does not establish the proposed hot/winding-loss set. Do not turn its ampere-turn excitation into a unique winding resistance.

[S03 FEMM](SOURCES.md) supplies an air-core coil tutorial with winding information, but no nonlinear pole/armature. [S04 DT4C study](SOURCES.md) reports temperature/frequency magnetic characterization; it is not a confirmed rights-cleared, complete DC pot-solenoid dataset. Neither closes the missing bridge to S01/S02.

| Required input | Confirmed ingredient | Full-proposal disposition |
| --- | --- | --- |
| Pot-yoke/armature drawing, tolerances, fillets, allowed pole actions | GetDP tutorial; TEAM geometry is a different case | HUMAN_INPUT: matched geometry and public reuse provenance |
| Steel grade/process and monotone B–H over every mandatory temperature | Generic table; TEAM benchmark law; separate temperature study | HUMAN_INPUT: same-grade, same-process B–H(T), interpolation/extrapolation domain |
| Winding turns, conductor dimensions, fill, mean turn length, leads, resistance versus temperature | Tutorial coil inputs or benchmark ampere-turns | HUMAN_INPUT: coherent actual winding/loss model and units |
| Stroke/current/force envelope, package and electrical limits | Existing proposal identifies fields, not sourced limits | HUMAN_INPUT: limit/source/authority per condition |
| Axisymmetric force, flux, coenergy and I²R extraction | Open reference route, no executed adapter/witness | NOT_DEMONSTRATED |
| Permanent-magnet curves | Original job explicitly non-PM | Excluded by architecture; required if a future PM job is proposed |

**Recommendation:** HOLD the full internal proposal. Best route to a reduced numerical rehearsal is an explicitly specified open-law electromagnet at a supported fixed material condition; a source-confirmed pot geometry and force implementation would still need work. Such a new job gives up the hot-material/winding constraint and the full least-loss actuator decision. It is not a passed version of the existing job. If the owner requires the original job and missing open inputs remain unavailable, retain it for later rights-permitted customer data.

## Bolted joint: reusable benchmark drawings do not determine bracket friction

The [existing job](https://github.com/carbonphysicsai/Carbon/blob/65ef88660fe02018c26f54d14655fe7b66354aa8/docs/development/challenge_pipeline/value-cost/replacements/bolted-joint.md) is a finite local bracket with preload/geometry decisions and assembly then eccentric service loading. Opening, slip and bolt/parent loading matter. Thread/under-head tightening friction, torque-to-preload conversion and **faying-interface service friction** are distinct inputs.

[S05 TRC design family](SOURCES.md), DOI `10.18419/DARUS-3147`, version 1.0, has CC-BY-4.0 CAD/drawings and revision-D assembly documentation. The downloaded PDF's MD5 matched the repository metadata. It gives material identities and tightening sequence/torque for a clamped nonlinear-vibration benchmark. This is a useful coherent geometry/assembly family; it is not the proposed bracket. Torque instructions and steel names do not alone give its force preload distribution, faying law or strength curves.

[S06 KIT tightening data](SOURCES.md) covers measured preload and thread/head friction, but the dataset license is **CC-BY-NC-ND-4.0**, unlike a broadly reusable open-data expectation. [S07 UNESP BERT](SOURCES.md) is also NC and concerns vibration with controlled tightening torque. Neither is cleared for the intended kit; neither substitutes its tightening information for a matched bracket's faying friction.

[S08 CalculiX example collection](SOURCES.md) contains a bolt-through-plates contact input. The inspected `bolt.inp` has an elastic law and thermal initial conditions, but no `*FRICTION` keyword or calibrated plastic/strength law. The collection mixes official and contributed examples; no root license declaration was found in the inspected tree. Its generic `materials/Rubber.inp` is elastic, not hyperelastic calibration. Do not inherit the solver license for every contributed asset.

| Required input | Confirmed ingredient | Full-proposal disposition |
| --- | --- | --- |
| Bracket/bolt geometry, interfaces, tolerances and action grammar | Rights-clear TRC CAD for a different assembly | HUMAN_INPUT: matched bracket family or expressly new internal case |
| Bolt/member constitutive curves, strength domain and process identity | TRC grade identities; example elasticity | HUMAN_INPUT: same-family curves/limits or documented elastic-only applicability |
| Faying friction versus surface/pressure/condition; uncertainty | Different tightening or vibration datasets | HUMAN_INPUT: applicable service-interface law, not generic steel-on-steel default |
| Force preload, locking/assembly order and scatter | TRC torque sequence; KIT measured force in another rig | HUMAN_INPUT: matched preload/assembly/scatter |
| Service load history, opening/slip/strength acceptances | Proposed buyer fields | HUMAN_INPUT: sourced limits and load boundary conditions |
| CalculiX contact/pretension/history observers and convergence | Open solver route | NOT_DEMONSTRATED |

**Recommendation:** HOLD the full proposal. Among the two contact candidates, prioritize **bolt** for additional source-completeness work: its geometry/contact opening can give the quote model useful structural coverage, and a constitutive model need not introduce seal chemistry or leakage claims. This is a priority hypothesis, not a finding of higher measured value. A separately scoped TRC assembly/preload numerical rehearsal could reuse licensed geometry, but would teach a different decision and need explicit friction/preload/constitutive provenance. Do not silently replace an eccentric bracket with a vibration benchmark. Later customer data is a design route, not an outreach job.

## Seal gland: calibration data exist; a complete supported gland set was not found

The [existing job](https://github.com/carbonphysicsai/Carbon/blob/65ef88660fe02018c26f54d14655fe7b66354aa8/docs/development/challenge_pipeline/value-cost/replacements/seal-gland.md) selects gland/back-up support geometry using assembly force and registered contact/deformation margins through squeeze and pressure loading. Its temperature/material conditions need an applicable hyperelastic law; incompressibility is a constitutive choice requiring support. Contact pressure alone cannot certify leakage or lifetime.

[S09 Roels/Costa Cornellà/Brancart](SOURCES.md), Zenodo `14983287`, explicitly licenses its elastomer datasets **CC-BY-4.0**. Tension and compression ZIPs were downloaded read-only, MD5-matched, and inspected for material CSV entries and strain/stress headers. This is actual accessible calibration data, not a hardness-to-law guess. The associated paper is a separate asset; its repository copy carries CC-BY-NC. The family concerns soft-robotics elastomers and does not provide the proposed gland's same-compound friction, pressure/temperature service law or acceptance limits.

[S10 Moreno-Mateos family](SOURCES.md), Zenodo `15187640`, also declares CC-BY-4.0 and supplies equibiaxial force/displacement and field data with test context. It is a different material/preparation family, including pre-cut fracture specimens. Do not splice those curves into S09 as a matched multiaxial calibration.

[S11 Jing et al.](SOURCES.md) is closely aligned to axisymmetric O-ring/support contact. Its paper is CC-BY-4.0, but its data statement explicitly withholds raw experiments because of third-party material confidentiality. Its coefficient prose also repeats a parameter symbol; a deck must reconcile the published table, units, compressibility and stability rather than silently repair it. This research adopts none of its coefficients or aerospace safety recommendations.

[S12 Yenigun et al.](SOURCES.md) publishes O-ring tests and fitted/predicted parameters under CC-BY-4.0. Friction is inferred rather than independently measured; its availability statement supplies no raw-data archive. Those facts support a bounded parameter-model rehearsal, not a complete gland/extrusion/temperature calibration.

| Required input | Confirmed ingredient | Full-proposal disposition |
| --- | --- | --- |
| Exact compound, cure/conditioning, raw test modes and published law | S09 raw tension/compression; S10 separate biaxial family; S12 parameters | Ingredient rights verified; selected supported material/strain domain HUMAN_INPUT |
| Compressibility/volumetric response and law stability over graded modes | No accepted, matched gland calibration established | HUMAN_INPUT; do not invent a Poisson ratio or bulk modulus |
| Same-compound metal/lubricant friction and condition range | S11 relevant experiment withheld; S12 inferred friction | HUMAN_INPUT |
| Gland/back-up geometry, gap, finish and assembly sequence | S11 relevant published case; different S12 component test | HUMAN_INPUT: complete, unambiguous selected case and rights |
| Pressure/temperature history, strain/contact/extrusion limits | No accepted full source set | HUMAN_INPUT; thermal degradation tests are not temperature-dependent hyperelastic curves |
| CalculiX nearly incompressible/contact mapping, force/extrusion observer | Solver route only | NOT_DEMONSTRATED |

**Recommendation:** HOLD full seal-gland launch scope; keep as a later customer-data design. A material-calibration or component-compression rehearsal based on a single licensed family is plausible, but gives up pressured gland/back-up design, thermal service, leakage and qualification claims. Material testing, calibration and physical seal validation are different evidence. An open material ingredient is a useful result even though it does not clear the design.

## Scores under the owner's value framing

These are **research-priority rubrics**, not official scoring or adopted economic policy. Intervals are scenario judgments, not confidence intervals. An upper score cannot claim an experiment that was not run.

| Axis | Ordinal rubric (ASSUMPTION definition) |
| --- | --- |
| Shortcut difficulty, 0–4 | 0: exact permitted lookup settles the decision; 1: charts/circuit/compliance plausibly suffice; 2: calibrated ordinary response surface is a strong likely comparator; 3: contact/frontier or saturation effects plausibly leave residual decision errors on whole-design holdouts; 4: matched evidence demonstrates those strongest shortcuts fail |
| Equal-budget gain potential, 0–4 | 0: no gain or worse is plausible; 1: a narrow gain hypothesis, with amortization risk; 2: a specific feasible-frontier search mechanism could improve the independently confirmed design at equal total budget; 3: closely matched published equal-total-budget evidence supports the mechanism; 4: Carbon demonstrates it in the registered comparison |
| Gain evidence, 0–4 | 0: no equal-budget comparison; 1: incomplete/unequal-budget comparison; 2: complete matched comparison for one declared setting; 3: replicated across the declared strata; 4: prospectively replicated in changed supported briefs with full cost accounting |

| Candidate | Difficulty low/base/high | Gain potential low/base/high | Gain evidence low/base/high | Why the base is a hypothesis |
| --- | --- | --- | --- | --- |
| Bolted joint | 2 / 3 / 3 | 0 / 2 / 2 | 0 / 0 / 0 | Moving opening/slip fronts could alter the lightest admissible bracket or preload choice; an ordinary contact-aware surrogate might already capture them |
| Solenoid pole | 1 / 2 / 3 | 0 / 1 / 2 | 0 / 0 / 0 | Pole saturation/fringing might change the least-loss envelope choice; nonlinear circuits and established metamodel workflows make residual gain uncertain |
| Seal gland | 1 / 2 / 3 | 0 / 1 / 2 | 0 / 0 / 0 | Custom support/gap contact could change assembly-force choices; catalogue charts and ordinary axisymmetric surfaces may already settle them |

All three have actual gain low/base/high **null/null/null**, actual value per euro **null**, and full open-data readiness **HOLD**. A zero evidence score means no measurement, not measured zero performance. Difficulty never overrides rights, adequacy, feasibility or budget. The conditional research priority is bolt, then solenoid, then seal; it is not a launch ranking. Existing assumed annual value-to-cost indices are not evidence of equal-budget gain and are not relabelled here.

### Strongest comparator, not solver brute force

Use the incumbent comparator in the [cheap-baseline contract](https://github.com/carbonphysicsai/Carbon/blob/65ef88660fe02018c26f54d14655fe7b66354aa8/docs/development/challenge_pipeline/cheap-baselines/README.md) and proposed replacement cards. For solenoid: nonlinear reluctance/fringing circuit, complete force-map interpolation, FE-calibrated RBF/Kriging and an established metamodel optimization workflow ([S13 Bosch/Ansys case](SOURCES.md)). That case reports replacing solver calls with a metamodel during optimization and robustness analysis. Merely proposing a surrogate is therefore not a differentiated value claim. For bolt: VDI/compliance calculation, contact-aware FE response surface and direct optimization. For seal: supplier gland/fill/extrusion guidance, calibrated contact surface and direct optimization.

If every permitted action's outputs are already available, exact **CLOSED_BANK** lookup is the comparator and can remove the surrogate's value. Test **NEW_SUPPORTED** whole geometries/briefs only when the registered grammar permits them; do not create private or out-of-domain freedom to beat the cache. A model-assisted optimizer's value cannot be claimed as a network advantage without a further matched network-versus-centralized comparison.

### First equal-budget design-gain experiment for Data Collection to specify

**No dispatch authorized; all missing inputs above must close first.** This protocol recommendation is separate from a feasibility/admissibility panel and does not edit the packet.

1. Freeze intended decision, P, strata, geometric actions, mandatory limits, units, observer/reference tier and graded whole-curve history. Define Q and w separately. Pre-register starting information, training/fit permissions, whole-design holdouts, stopped/failed solve handling and independent confirmation. Preserve the existing feasibility and near-frontier rules; numeric acceptance remains the Test Lead/owner's.
2. Give **solver-alone** a competent direct constrained search with warm starts, continuation, caching and its ordinary optimizer. Give the **cheap method** its best pre-registered calibrated circuit/compliance/chart/response-surface search. Give **Carbon** its construction/fit plus model-assisted search. Same supported actions, objective, hard limits, initial data access and stopping budget; no weaker safety or higher failure allowance in one arm.
3. Charge all new source/mesh generation, bank/reference solves, training/fitting, hyperparameter search, failed attempts, inference, optimization, refinement and fallback to the arm that uses them. Shared initial evidence and final confirmation are identical common allocations; count their bill in both absolute totals, not twice in a joint cash total. No free prebuilt bank for Carbon. No free commercial baseline license. Record allocated node-hours, elapsed time and human time separately; a CPU-hour estimate does not imply parallel speedup.
4. Report one-off total budget and, separately, repeated-brief amortization with a declared reuse policy. Reuse frequency and real annual buyer volume are HUMAN_INPUT. A training-heavy method can lose the one-off test and win only after repeated use; state that dependence.
5. Independently confirm each arm's final proposal with the same adequate reference/refinement/observers across every mandatory condition. An unresolved/reference/infra failure gives no admissible gain; retain adverse results and typed failures. Record best verified feasible objective versus consumed budget, false-feasible choices, NONE_FEASIBLE outcomes, fallback count and decision stability. Keep regret/uncertainty bands in buyer units.
6. Repeat the registered search comparisons and uncertainty analysis as specified by the test owner; repetition count, confidence rule, seeds under public research only, objective scale and acceptance margin are HUMAN_INPUT. This research fixes none of them.

For a minimizing objective, define **raw gain = J(best verified solver-alone design) − J(best verified Carbon design)** at the same complete budget. Compare Carbon with the strongest cheap arm as well. Report objective units, uncertainty and all hard gates before interpreting the sign. Positive measured gain still needs the pre-registered materiality criterion. If an arm has no verified feasible output, report that outcome separately; do not substitute a finite penalty and call it objective improvement. Do not divide by a zero baseline objective or monetize an unsourced unit.

Historical bank-startup estimates from [R04](https://github.com/carbonphysicsai/Carbon/blob/65ef88660fe02018c26f54d14655fe7b66354aa8/docs/development/challenge_pipeline/value-cost/replacements/scenarios.json) are ASSUMPTION EUR low/base/high: solenoid **18.98/26.37/46.06**; bolt **26.11/42.08/93.21**; seal **20.21/28.83/53.45**. They use unmeasured complete-case CPU costs, serial/tax/overhead assumptions and pending witness arrangements. They exclude the unresolved public-case integration and this full matched optimization campaign. New all-in equal-budget test cost, time and gain are **HUMAN_INPUT** until the complete route and trial ledger exist. No budget ceiling is silently changed.

## Portfolio implications and handoff

Carry the owner-reported motor observation and keep/reserve direction exactly as recorded. Motor, solenoid and transformer have distinct engineering questions but overlap electromagnetic coverage. Bolt and seal overlap contact structures. Prefer one of the latter for learning breadth only after it passes data, feasibility, strongest-baseline and equal-budget value tests. Keep f13 in contention subject to energy accounting and value; keep f06 HOLD until measured complete cost. This report neither fills gaps with unrelated benchmarks nor adopts a final eight.

Each incomplete original job remains a **customer-data design candidate**, not a launch-ready or customer-ready executable package. If a future customer supplies missing data, rights and applicable evidence must be reviewed then; no pilot or partnership is requested now.

Closeout predicate: the new research files cite all factual findings, retain source/rights/version distinctions, contain no invented limits or measured gains, pass document/JSON checks and applicable CI, and are handed to PR Head. The maturity earned is a researched specification only. Solver/container reproducibility, adequate references, physical validation, real buyer value, security, launch, legal and commercial qualification remain unearned.
