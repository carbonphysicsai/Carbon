# Carbon Eight Challenge Foundation Plan

> **First DEVELOPMENT round (2026-10-06).**
> [OWNER-PORTFOLIO-DEV-ROUND-01](../.agent/decisions/2026-10-06-OWNER-PORTFOLIO-DEV-ROUND-01.md)
> prospectively supplies owner-delegated customer-shaped requirements and
> finite reference-feasibility allowances for the five new briefs in the
> [round-one packets](../docs/development/challenge_pipeline/round1/README.md).
> This fills those first-round values, not reference adequacy by declaration,
> production qualification, protocol lock or launch. The original plan below
> remains the design basis and historical statement of what its adoption left open.

**Status.** Adopted 2026-10-04 by
[OWNER-LAUNCH-PORTFOLIO-02](../.agent/decisions/2026-10-04-OWNER-LAUNCH-PORTFOLIO-02.md):
the eight challenges in §4 are Carbon's launch portfolio, and §4's bounded
designs are their design basis. The text below is the owner-supplied plan as
written on 2026-10-03; the only change is that a link to a private strategy
page was removed. Values the plan leaves OPEN stay open. Adoption approves no
population, threshold, spend, protocol lock, qualification or launch.

Design draft dated 3 October 2026. Repository basis: `59d0fd589895557db607d228689010e65b6a33b5`. This document starts the foundation design for the eight selected use cases. It is not an approved population, execution ticket, spend grant, protocol lock, qualification or launch decision.

## 1 Outcome and boundaries

Build one reusable challenge-development backbone and eight bounded physics adapters. Each adapter must support a named engineering decision, independently reproducible references, useful public research tools, strong cheap baselines and protected evaluation. Do not create eight independent evaluation frameworks or one universal solver.

The commercial flagship is AI-accelerator cooling: cooling geometry and burst-power operation are two distinct challenges sharing one customer relationship and substantial infrastructure. The investor-facing frontier bet is manufacturing-tolerant photonic coupling. Battery and motor retain their useful existing work; the inexpensive symmetric photonic coupler remains supporting evidence and a regression asset, not the headline use case.

Portfolio selection retains a 25% Bittensor investor-alignment factor and 75% commercial and technical judgment. That factor does not enter a physics score, gate, deployment rubric or reward formula. This proposed eight-use-case portfolio does not silently replace the repository's approved three-factor family queue or its current four readiness records.

The synthetic foundation requires no customer solver access. Experimental credibility requires measurements later; an owned rig, independent lab or suitable rights-cleared public experiment may provide them. A customer is valuable for requirements and deployment context, not a prerequisite for every initial challenge.

## 2 Current state we can actually reuse

The repository already contains much of the architecture. Reuse it through its current boundaries rather than treating it as a fully generic production implementation.

| Existing area | Foundation use | Important limit |
| --- | --- | --- |
| `carbon/authoring/` | Physical system, candidate output, population, sampling and identity contracts | Typed objects do not establish scientific adequacy |
| `carbon/challenge_registry/` | Exact challenge and execution-profile discovery; refusal of unsupported selections | Battery is implemented in this registry; cold plate, motor and photonics remain reserved |
| `carbon/challenge_pipeline/` | Family queue, protocol state, construction ladder, proposals, lessons and generated reports | Protocol is DEFINING; only Phase 1 step 1 is done at this repository snapshot |
| `carbon/challenge_readiness/` | Per-axis readiness, typed pilot outcomes, cost provenance and admission bindings | Readiness is not scientific qualification or activation |
| `carbon/battery/` | Working battery reference, construction, research, practice and engineering-value studies | Frozen studies and their findings keep their original meaning |
| `carbon/cold_plate/`, `carbon/motor/`, `carbon/photonic/` | Reusable domain, population, numerical and exam work | These packages are not three completed miner-facing challenge environments |
| `carbon/challenge_kit/` | Public generator/reference provision standard and battery data generation | Battery generation runs on the miner's own machine; scoring generated cases in practice is not yet wired |
| Reconstruction, seeding, scoring and disclosure owners | Keep rebuild, protected evaluation and grade authority separated | Do not add a generic research/official mode or bypass the registered scoring authority |
| Reference and measurement runtimes | Patterns for pinned requests, artifacts and typed evidence | Concrete current runtime types include Burgers-specific contracts; eight adapters do not exist by renaming them |

The current photonic reference is a local-supermode model, not a completed three-dimensional FDTD grating-coupler reference. The current cold plate is a bounded periodic-channel conjugate problem, not a manifold design. The current motor already outputs a 60-angle torque curve. The current battery already includes a 30-cycle ageing task; do not replace it with the roadmap's cheap single-charge example.

Current battery studies also retain known near-limit and localized-error findings. A new portfolio document neither resolves those findings nor changes EV5's frozen evidence. All new work must reconcile current owner records before execution.

## 3 The common foundation

### One design packet per challenge

Every packet must contain the same ten sections:

1. Engineering job: user, decision, objective, constraints, cost of a wrong decision and exclusions.
2. Physical system: geometry grammar, materials and provenance, causal inputs, initial and boundary conditions, units and time or frequency horizon.
3. Population: intended population P, support, sampling law Q, strata and evidence weighting. A box of ranges is not a deployment population.
4. Case contract: valid and invalid geometry rules, canonical identity, representation and public versus protected fields.
5. Reference policy: pinned solver/environment, numerical settings, controls, refinement, uncertainty, witnesses and failure handling.
6. Output and measurement contract: exact observable shapes, coordinates, transformations, normalizations, gates and decision measurements.
7. Construction contract: actual Level 0 vocabulary, permitted data/backends, reconstruction, resources and artifact identity.
8. Research kit: public documentation, vocabulary, training runtime, own-seed generation/reference, practice, compute, model and agent provisions.
9. Evidence plan: combined admission study, fresh confirmation, cost study, training-budget study, disclosure and change policy.
10. Readiness and claim record: what exists, what ran, what failed, what is unknown, responsible reviewers and next gate.

Proposed packet filenames and field lists are design aids, not new public protocols. Map them to existing authoring and readiness owners before adding schemas. Any value not supplied by evidence or the responsible owner stays explicitly OPEN; no invented safety limits or default scientific thresholds.

### Reference execution and data

Keep solver-specific launch, meshing and post-processing in adapters. Reuse shared job identity, resumability, cost accounting and evidence conventions only where their contracts match.

A reference job binds the challenge version, canonical case, geometry/material definition, solver build, mesh/time/frequency settings, output extraction, environment and relevant hardware. Cache identity includes every scientifically material pin. A coarse result, changed material law or prior solver image cannot satisfy a finer or different reference request.

Public research draws use the research population and the researcher's own seeds. Official draws, rotating exam batches and sealed confirmation stay in separate protected domains. Public generation need not imitate hidden exam composition. Generated research data is not automatically permitted construction data; the construction contract decides that prospectively.

Retain scheduled, attempted, successful, unresolved and failed jobs, including retries and cost. Never silently delete difficult geometries, replace failed cases until they look easy, or compare models on different resolved masks without a registered missing-evidence analysis.

Failure handling must distinguish:

- Invalid or out-of-contract inputs: refuse before solving; do not call them poor physics.
- Reference invalidity or nonconvergence: no candidate penalty; retain the cause and apply the registered common-case/censoring rule.
- Infrastructure failure: retry or defer under policy; never convert it into a scientific score.
- Candidate invalid output or mandatory scientific failure: use the owning challenge's declared outcome, without treating it as reference failure.
- Insufficient evidence: unresolved or inconclusive, not a fabricated pass.

These are semantic obligations, not authorization to create new shared enums or override existing owner taxonomies.

### Verification before volume

Use analytical or manufactured controls, mesh/time/frequency convergence, boundary-condition tests and representation checks before large datasets. Where justified, add an independently checked solver witness on selected difficult cases. Two solvers agreeing does not establish physical reality when they share assumptions.

The roadmap's initial Design panel is 30 stratified feasibility cases, plus controls and refinement cases. It is a feasibility instrument, not the final statistical sample size. Measure setup, mesh, solve, extraction, failed attempts, cold/warm runs and peak memory.

The approved CPU reference timing route is RunPod cpu5c, 16 vCPU, pinned image and recorded CPU model. This document authorizes no pod. GPU photonics requires a separately declared and approved timing profile; never compare its GPU seconds directly with CPU-family estimates.

### Decision evidence and economics

Measure field or trajectory error where relevant, but test the engineering decision separately. Require fixed-choice decisions, boundary controls and model-guided design search where the job supports them. Commit a model's proposed design before independent reference checking.

Compare against the strongest applicable inexpensive alternatives: analytical relations, interpolation, cached/factorized direct solves, modal reduction, reduced-order models and hybrids. Use the same constraints, query allowance, optimizer and stopping rules. Include training data generation, fitting, calibration, compilation, inference, fallback and verification costs.

Report time and cost to a correct decision, unsafe/false-feasible outcomes, missed feasible choices, regret, tail/subgroup failures and uncertainty. Do not sell raw inference speedup as end-to-end advantage. A fast solver is not automatically disqualifying, but a cheap baseline that already solves the job removes the case for an expensive challenge.

Reuse the combined admission design: one sheet, one panel, one fresh confirmation set and one ledger, with separate construction-integrity, adversarial-score and engineering-value verdicts. None compensates for another. Final protected evidence must remain independent of Graphite's development work.

### Research and construction

Every offered contract needs all eight declared research provisions: research, hypothesize, train, generate, evaluate, compute, model and agent. A named gap is honest development state, not readiness to launch.

First close the practical battery precedent: own-generated cases can be validated and evaluated on the correct research path, with clear provenance and permitted-data rules. Shipping a solver binary alone is not a complete environment.

Start each new challenge at its actual Level 0. Draft challenge-specific capability proposals for Levels 0 through 5, then test expansions one level at a time with Carbon's reconstruction, ablations and combined-permission attacks. Unimplemented or untested levels remain NOT_RUN. Choose the best supported level, not automatically the highest, and open only its locked contract after the validators serve it.

Do not widen arbitrary-code execution, grant official access to sensor streams, or replace the existing reconstruction runtime as part of this design plan.

## 4 Eight bounded challenge designs

The labels below are planning labels, not registered challenge IDs. Numeric ranges, material choices, gates and sampling laws require the Design packet and owner acceptance.

### Challenge 1 AI accelerator cooling design

Family f04 with conduction support; retain the current cold plate as the starting asset.

Job: select a manufacturable cooling geometry and flow setting that reduces hydraulic power while meeting a declared hotspot-temperature requirement.

First scope: extend the verified periodic-channel problem through a bounded manifold topology, single-phase incompressible laminar flow and conjugate heat transfer. Flow-only development may come first, but it must not claim temperature-constrained cooling success until the coupled reference is verified. Exclude boiling, fouling and turbulence outside the registered regime.

Inputs: channel/manifold parameters, solid properties, coolant properties, inlet temperature, flow and declared heat-load map. Outputs: pressure loss, flow distribution, thermal/hotspot observables and hydraulic power in pinned units.

Reference: reuse pinned OpenFOAM cold-plate work, then qualify new manifold geometry and thermal coupling. Baselines: channel/network relations, existing closed-form approximation and reduced thermal-fluid models.

Decision test: identical geometry-search budget; independently verify hotspot constraints and pump burden, including boundary designs and perturbations. Controls must catch false cooling optimism and hidden flow imbalance.

Reality route: flow, differential pressure and temperature measurements on an instrumented plate. Synthetic success does not establish a datacenter system or field reliability.

### Challenge 2 Burst power thermal envelopes for AI chips

Family f02, separate from geometry optimization but sharing materials, geometry and thermal representations with Challenge 1.

Job: choose a burst-power schedule that delivers more useful operation without exceeding a declared thermal limit, and forecast recovery.

First scope: layered solid conduction under time-varying spatial power and prescribed convection/contact conditions. Exclude full coolant dynamics, phase change and thermal runaway.

Inputs: geometry/material stack, contact model, initial temperature, cooling boundary and complete permitted power waveform. Outputs: temperature trajectory at declared locations, peak, time to limit and recovery observables.

Reference proposal: pinned Elmer heat solver with analytical transient controls; select an independent DOLFINx or CalculiX witness only if it materially reduces uncertainty. Baselines: calibrated RC network and POD/reduced-order thermal dynamics.

Decision test: hold out whole waveform families and combinations, not random timesteps. Check forecasted limit crossings and safe burst selection under equal decision budgets.

Reality route: an owned instrumented heater/plate rig is the preferred first experiment. Freeze predictions before future observations; this demonstrates the observation contract without needing a chip customer.

### Challenge 3 Manufacturing tolerant fiber to chip grating couplers

Family f06 with f14 mode support. Replace the symmetric coupler as the headline; preserve its evidence and regression role.

Job: choose a bounded three-dimensional grating geometry with useful coupling over a wavelength band and declared fabrication/alignment perturbations.

First scope: fixed material stack, polarization, port/fiber definition and bounded parameterized geometry. Register perturbations explicitly. Synthetic robustness is not fabrication yield.

Inputs: grating dimensions, etch/material definition, wavelength, source/port and alignment offsets. Outputs: normalized coupled/reflected/radiated power and any registered complex amplitudes.

Reference proposal: Meep full-wave FDTD and mode/overlap extraction. Assess the existing fdtdx route for GPU feasibility rather than presuming it is qualified. Reuse current mode-analysis work only where applicable. Pin phase conventions, normalization, PML, resolution and simulation stopping.

Baselines: coupled-mode/semi-analytical models and interpolation of permitted reference data. Reject a scope where they already provide the required decision accuracy cheaply.

Decision test: commit geometries before independent tolerance-panel verification. Include asymmetric and low-coupling controls. Do not claim complete co-packaged optics performance.

Reality route: fabrication metrology and optical coupling measurements later, with an actual process distribution before any yield claim.

### Challenge 4 Cell specific fast charging with degradation constraints

Family f05. Preserve the existing ageing programme rather than restarting with a cheaper generic task.

Job: choose a charge protocol for a declared cell/parameterization that shortens charging while respecting voltage, thermal and registered degradation criteria.

First scope: current DFN electrothermal/ageing development contract. A broader schedule family or different cell is a prospective new version. Thirty simulated cycles do not establish lifetime or real-cell safety.

Inputs: accepted protocol parameters, initial SOC, ambient conditions and declared cell parameters. Outputs: existing voltage/temperature trajectories, capacity checkpoints and registered degradation/plating observables.

Reference: retain pinned PyBaMM and current truth environment; reconcile EV5, approved development gates and localized-error findings before changing anything. Baselines: CCCV rules, mechanistic reduced models and simple interpolation.

Decision test: reference-verified protocol selection with near-limit controls and explicit consequences of false feasibility. Do not promote a mean score that hides local sign errors.

Reality route: calibrated cycling/temperature/capacity measurements on identified cells, then whole-cell/batch/experiment holdouts. Simulator plating observables are not measured plating truth.

### Challenge 5 Low torque variation motors for precision robotics

Family f09. Retain full-curve motor work.

Job: choose bounded motor geometry/current parameters for smooth torque while meeting a mean-torque requirement.

First scope: existing two-dimensional eight-pole, 24-slot magnetic design and its complete 60-angle torque curve. Generic magnetic material laws remain explicitly generic; no full efficiency map, thermal rating or assembled robot-joint claim.

Inputs: declared geometry, current magnitude/angle and magnetic material definitions. Output: torque versus rotor angle with consistent orientation, period and units.

Reference: reuse GetDP/Gmsh, meshing and verification rungs; check saturation, air-gap refinement and force/energy agreement. Baselines: analytical harmonics, curve interpolation and fitted reduced magnetic models.

Decision test: design selection and full-curve verification near mean/ripple constraints. A good mean cannot compensate for a wrong torque ripple waveform.

Reality route: torque-angle/current measurements with independently characterized material and assembly tolerances. New material laws or 3D end effects require new scope and evidence.

### Challenge 6 Resonance resistant precision automation structures

Family f08 with f01 stress/stiffness and f12 modal support.

Job: choose a lightweight robot link or motion-stage support that limits response in a declared excitation band while meeting mass and stiffness constraints.

First scope: one bounded geometry family, linear elasticity, explicit supports, damping and harmonic excitation. Geometry varies; do not sell a cheap fixed-geometry frequency sweep as the entire challenge.

Inputs: geometry/material/support/damping parameters and excitation definition. Outputs: complex displacement/response functions, band peaks, mass and declared static/stiffness observables.

Reference proposal: CalculiX with mesh/modal convergence and harmonic-response controls. Baselines: retained-mode reduction, analytical beam models and reusable factorizations.

Decision test: reference-check selected designs and difficult resonant peaks under identical search budgets. Test peak location, phase and amplitude; coarse frequency grids must not miss narrow peaks.

Reality route: accelerometers, force measurement and modal tests. Full-machine settling time, throughput and nonlinear joint behavior are excluded until separately supported.

### Challenge 7 Compact industrial compressor silencers

Family f13.

Job: choose a compact duct/chamber silencer that attenuates a declared acoustic band within packaging constraints.

First scope: linear passive acoustics, bounded multi-chamber geometry, declared source and termination impedances. This predicts transmission, not compressor noise generation.

Inputs: geometry, medium properties, frequency band and impedance/source conditions. Outputs: complex transfer quantities and transmission loss on a qualified frequency grid.

Reference proposal: Elmer Helmholtz finite elements with straight-duct and transfer-matrix controls, mesh/frequency refinement and energy/passivity checks. GetDP is a possible witness, not an automatic second production backend.

Baselines: acoustic transfer matrices and reduced modal models. Park a topology that these solve adequately without a valuable learned advantage.

Decision test: verified band attenuation/packaging choices, including resonant narrow failures. Operating-flow pressure loss and flow-modified acoustics require separate coupled evidence before claiming compressor operating economics.

Reality route: calibrated transfer measurements on a duct rig, then operating-flow testing under a new contract where needed.

### Challenge 8 Passive micromixer cartridges for lab automation

Family f17 with f04 flow and f24 diffusion support.

Job: select bounded passive channel/groove geometry and flow settings for outlet uniformity at an acceptable length or residence time.

First scope: prescribed or independently qualified laminar velocity and passive scalar transport. No chemistry, reaction yield, cell viability or clinical claim.

Inputs: geometry, velocity/flow, diffusivity, inlet concentration and declared outlet/sampling definition. Outputs: concentration field/fluxes, outlet uniformity and arrival/residence observables.

Reference proposal: OpenFOAM flow plus passive scalar transport, with the velocity source explicitly identified and its work charged. Check Péclet regime, mesh/time refinement, positivity, conservation and artificial diffusion.

Baselines: diffusion scaling, simple channel/network models and transport ROMs.

Decision test: verify geometry choices using common outlet sampling and budgets. Include controls that appear mixed only because of numerical smoothing. Do not hide the flow solve outside the cost comparison.

Reality route: dye or fluorescence measurements with a calibrated observation model and held-out whole cartridges/flow conditions.

## 5 Implementation sequence and proposed work packages

All eight design briefs begin now. Implementation uses the existing battery-led protocol, not a second deployment queue.

| Package | Deliverable | Dependency and exit |
| --- | --- | --- |
| F0 State and reuse reconciliation | Eight-use-case mapping, code/data inventory, explicit gaps, proposed IDs and version decisions | No reserved challenge silently becomes implemented; old evidence preserved |
| F1 Common design packet | Templates mapped to existing authoring/readiness owners; battery worked example | Physical scope, data roles, pins, failures and OPEN fields are explicit |
| F2 Protocol and evidence suite | Stage permissions, combined-study instruments, controls, lessons and revision procedure | Existing Phase 1 steps 2 and 3 completed through their own authorized tickets |
| F3 Battery research vertical | Public generation-to-evaluation path, rebuild conformance and retained findings | Correct research provenance; no official assets; existing studies unchanged |
| F4 Battery protocol completion | Internal Level 0 testing/first climb, chosen-level freeze, final evidence, rubric and cost baseline | Existing Phase 1 steps 4 through 8 and process-owner lock; no qualification inferred |
| F5 Cooling adapter and thermal bridge | f04 next-family Design, manifold feasibility, separate f02 transient contract | Qualified component interfaces; CPU timings; cheap-baseline decision; new scopes reviewed |
| F6 Full-wave photonic design | 3D pilot plan, mode/port conventions, memory/cost feasibility and research-kit inventory | GPU profile/spend accepted before execution; no substitution of current supermode results |
| F7 Remaining domain packets and adapters | Motor reuse; vibration, acoustics and mixer adapter work with embedded prerequisites | Enter in authorized queue order after protocol lock; prerequisites can be built inside packets |
| F8 Experimental interface and first pilot plan | Observation/provenance specification and frozen heater/plate study design | Design only until rig, rights, budget and experimental contract are accepted |

F5 through F7 are dependency-aware planning packages, not authorization to advance several families at once. Motor can receive an early reuse assessment without silently jumping the queue. Supporting families are infrastructure dependencies, not extra commercial launch slots.

The first implementation ticket to propose is F1: common packet and battery worked example, coordinated with the existing Phase 1 step 2. Its scope is documentation, contract mapping and static conformance checks. It must not launch Graphite, alter EV5, change the scorer, provision paid compute or edit the active queue.

The next practical integration ticket is F3, narrowly wiring own-generated battery data into research evaluation under an accepted data contract. Do not grant new submission training-data permissions implicitly.

No calendar or total budget is asserted yet. Price each pilot after scope and a measured feasibility panel. Use the protocol's stage-cost baseline to estimate throughput; do not extrapolate eight scopes from a single solver timing.

## 6 The path from solver learning to reality learning

The potential end state is an envelope-specific physical model system: known physics provides structure; measurements identify parameters and permitted corrections; independent future experiments determine whether the combined model is useful.

Build the interfaces for that path now, but do not turn a simulation challenge into an experimental challenge by adding a source flag.

An experimental contract must bind specimen/assembly identity, input actuation, sensor placement and units, calibration, timestamp alignment, observation mapping, raw-data provenance, missing/saturated readings, uncertainty, data rights and model-update rules. Inputs needed to identify the physical response must be observed or explicitly treated as uncertainty.

Maintain two different registered tasks:

1. Frozen prediction: calibrate only on allowed past data, commit forecasts before an unseen experiment or future segment, then evaluate against its measurements.
2. Online adaptation: permit only the declared causal update rule and past sensor observations, then evaluate future responses under new excitation and held-out specimens where claimed.

A sensor trace can be predicted well without identifying the internal physical state or constitutive law. Claim only tested observables/decisions unless extra identifiability evidence supports internal quantities.

Use a tiered evidence budget rather than four complete evaluations of every candidate: cheap research screens; selected numerical refinement/witness cases; independent experimental confirmation of finalists. Screens nominate only and cannot replace the required complete reconstruction or qualified official decision evidence. Solvers remain useful controls and extrapolation tools; their agreement is no longer the sole target once an experimental truth policy is accepted.

Guard against gaming with protected whole experiments, causal prediction cutoffs, independent data custody, calibrated sensors, retained failed runs, anti-contamination checks and independent rebuilding. Hashes alone do not prove sensor truth, preregistration chronology or security. No finite suite proves the system ungameable.

First pilot proposal: Challenge 2 on an instrumented heater/plate. Compare RC/reduced-order, existing mechanistic and learned/hybrid models on new power schedules. Freeze the model and decision rule before the unseen run. Assess temperature/limit forecasts, useful burst decisions, uncertainty and total cost. No automatic hardware control is in scope.

Long-term capability target: fast design and operating decisions inside a stated envelope, cheaper than the best solver-based workflow at equal decision quality, with abstention/fallback outside demonstrated competence. That is a strong, testable way to beat solvers; universal solver replacement is not.

## 7 Acceptance and owner decisions

Foundation design is ready for implementation when all eight briefs and the common packet exist, reuse versus new work is explicit, every open scientific/security/economic value has an owner, and the first bounded implementation package fits the active protocol.

A challenge's implemented foundation is complete only when it also has:

- A pinned runnable reference and generator with controls, refinement and typed failure records.
- Measured full-task p50/p95 costs, including setup and failed attempts.
- Exact output/measurement and Level 0 reconstruction contracts.
- A public research kit tested on a clean researcher environment, including own-seed generation and permitted practice.
- Strong baseline results and registered engineering-value tests.
- Combined admission evidence at the chosen supported level and independent fresh confirmation.
- Its own completed training-budget study before training limits or rewards are set.
- Separate numerical, scientific, security and launch decisions; no inferred qualification from a green test.

The training-budget study's supplied challenge sheet, resource limits and spend approval are prerequisites. Do not invent values or reuse battery's limit for other challenges. Operational watchdogs and deterministic recipe budgets remain distinct.

Owner roles remain the roadmap's: Harshdeep owns physical/reference/data/measurement and value decisions; Ryan owns construction and technical/attack boundaries; Fitz owns protocol/rubric lock and deployment selection. Rights and output licensing require the responsible owner/legal decision.

Open decisions to record before implementation or execution:

- Adopt the eight-use-case commercial shortlist without silently changing the authorized family queue.
- Accept bounded first scopes, geometry/material choices and new-version mappings, especially manifold cooling, transient thermal and full-wave grating coupling.
- Set task-specific populations, output grids, mandatory gates and decision resolution.
- Accept solver packaging/licensing and separately approve CPU/GPU execution profiles and spend.
- Supply per-challenge budget-study sheets and construction-data permissions.
- Approve experimental data/rig scope before measurements, online adaptation or any hardware interaction.

## 8 Source basis and non claims

Repository sources below are pinned to the inspected snapshot so the plan does not imply a live deployment audit:

- [Challenge Roadmap](https://github.com/carbonphysicsai/Carbon/blob/59d0fd589895557db607d228689010e65b6a33b5/Design_Specs/Challenge_Roadmap.md): pipeline, owners, verification panel, timing and stage gates.
- [Challenge Admission](https://github.com/carbonphysicsai/Carbon/blob/59d0fd589895557db607d228689010e65b6a33b5/Design_Specs/Challenge_Admission.md): combined tests, independent evidence, failures and construction ladder.
- [Research environment standard](https://github.com/carbonphysicsai/Carbon/blob/59d0fd589895557db607d228689010e65b6a33b5/carbon/challenge_kit/standard.py): actual provision inventory and battery integration limits.
- [Challenge readiness](https://github.com/carbonphysicsai/Carbon/blob/59d0fd589895557db607d228689010e65b6a33b5/docs/development/CHALLENGE_READINESS.md) and [training-budget study](https://github.com/carbonphysicsai/Carbon/blob/59d0fd589895557db607d228689010e65b6a33b5/docs/development/CHALLENGE_TRAINING_BUDGET_STUDY.md): distinct maturity axes and standing study requirement.
- [Scientific Canon](https://github.com/carbonphysicsai/Carbon/blob/59d0fd589895557db607d228689010e65b6a33b5/docs/context/SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md): scoped truth, prospective contracts, independent reconstruction and claim control. Its v4.1 additions remain ratification proposals, not silently adopted law.
- [Business Canon](https://github.com/carbonphysicsai/Carbon/blob/59d0fd589895557db607d228689010e65b6a33b5/Business/Business_Canon.md): evidence-led customer entry and empirically earned network advantage.
- [Licence decision](https://github.com/carbonphysicsai/Carbon/blob/59d0fd589895557db607d228689010e65b6a33b5/.agent/decisions/2026-10-03-OWNER-LICENSE-01.md): MIT subnet code, third-party terms preserved, outputs separately licensed. Open-source solver access is not automatic rights to redistribute every artifact or reuse customer data.

Primary solver documentation supports candidate capability, not Carbon qualification: [OpenFOAM standard solvers](https://www.openfoam.com/documentation/user-guide/a-reference/a.1-standard-solvers) and [passive scalar transport](https://doc.openfoam.com/2212/tools/processing/solvers/rtm/basic/scalarTransportFoam/); [CalculiX structural and thermal capabilities](https://www.calculix.de/); [Meep mode decomposition and normalization](https://meep.readthedocs.io/en/latest/Mode_Decomposition/); [Elmer official source and model documentation](https://github.com/ElmerCSC/elmerfem). Exact new builds are chosen and pinned during Design.

No solver was installed, no campaign or live Graphite session was launched, no paid compute was provisioned, and no repository code, policy, frozen evidence, qualification, network weights or rewards were changed for this plan. Dry runs, smoke tests, code tests and design documents are not scientific, security or production qualification.
