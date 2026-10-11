# bolted-joint — generated common packet draft

DEVELOPMENT / DRAFT_ONLY. SOURCE_EXTRACT means verified bytes, not approval.
Every unsourced field is HUMAN_INPUT. No runtime or qualification authority.

## 1. Engineering job

### buyer — HUMAN_INPUT

Mechanical joint design engineer (conditional internal mock customer)

Owner: science/product owner. Needed: Confirm applicability and authorize buyer.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### decision — HUMAN_INPUT

Choose preload and bracket/support geometry under unchanged eccentric service loads and opening, slip and strength limits

Owner: science/product owner. Needed: Confirm applicability and authorize decision.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### value — SOURCE_EXTRACT

A mechanical joint-design engineer selects bolt pattern/size, preload and local support geometry for a known load envelope. BOLT1 documents simulation-informed sizing/preload; BOLT2 is an independent fastener-design manual. BOLT3 offers independent FE research at abstract level, so the exact current simulation decision/customer source must still be confirmed.

Buyer role: **Joint-design engineer**. Proposed decision: **Choose preload/bolt pattern/support geometry**. Independent role/workflow evidence: [BOLT1: Ansys](https://learninghub.ansys.com/learn/course/external/view/elearning/36/ansys-mechanical-bolt-pretension); [BOLT2: Richard T. Barrett / NASA](https://ntrs.nasa.gov/api/citations/19900009424/downloads/19900009424.pdf); [BOLT3: Independent bolted-connection researchers](https://www.sciencedirect.com/science/article/pii/S1350630719304686). Manufacturer and independent research origins are distinguished; neither is a confirmed Carbon customer. Buyer identity/authorised contact, actual current simulation tool, decision latency/cadence, allowed materials/data rights, acceptance criteria and value interview are **HUMAN_INPUT — business/customer owner; blocks G1/adoption**.

V2 proposed avoidable effort 3.00 / 8.00 / 20.00 hours/revision × 60.00 / 90.00 / 120.00 EUR/hour gives 180.00 / 720.00 / 2400.00 EUR/revision. V3 assumes 5.00 / 20.00 / 50.00 teams × 6.00 / 24.00 / 60.00 revisions/team/year = 30.00 / 480.00 / 3000.00 revisions/year. These are conditional cohort scenarios, not buyers/market size, actual savings or willingness to pay. Demonstrated commercial floor is zero.

Source: `docs/development/challenge_pipeline/discovery/dossiers/bolted-joint.md` sha256 `bebad0c570089a193c816d74d1bd6e40a62cb180fee119d35f4ae36e45335793`.
Owner: science/product owner. Needed: Confirm applicability and authorize value.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### wrong_decision — SOURCE_EXTRACT

A mechanical joint-design engineer selects bolt pattern/size, preload and local support geometry for a known load envelope. BOLT1 documents simulation-informed sizing/preload; BOLT2 is an independent fastener-design manual. BOLT3 offers independent FE research at abstract level, so the exact current simulation decision/customer source must still be confirmed.

Buyer role: **Joint-design engineer**. Proposed decision: **Choose preload/bolt pattern/support geometry**. Independent role/workflow evidence: [BOLT1: Ansys](https://learninghub.ansys.com/learn/course/external/view/elearning/36/ansys-mechanical-bolt-pretension); [BOLT2: Richard T. Barrett / NASA](https://ntrs.nasa.gov/api/citations/19900009424/downloads/19900009424.pdf); [BOLT3: Independent bolted-connection researchers](https://www.sciencedirect.com/science/article/pii/S1350630719304686). Manufacturer and independent research origins are distinguished; neither is a confirmed Carbon customer. Buyer identity/authorised contact, actual current simulation tool, decision latency/cadence, allowed materials/data rights, acceptance criteria and value interview are **HUMAN_INPUT — business/customer owner; blocks G1/adoption**.

V2 proposed avoidable effort 3.00 / 8.00 / 20.00 hours/revision × 60.00 / 90.00 / 120.00 EUR/hour gives 180.00 / 720.00 / 2400.00 EUR/revision. V3 assumes 5.00 / 20.00 / 50.00 teams × 6.00 / 24.00 / 60.00 revisions/team/year = 30.00 / 480.00 / 3000.00 revisions/year. These are conditional cohort scenarios, not buyers/market size, actual savings or willingness to pay. Demonstrated commercial floor is zero.

Source: `docs/development/challenge_pipeline/discovery/dossiers/bolted-joint.md` sha256 `bebad0c570089a193c816d74d1bd6e40a62cb180fee119d35f4ae36e45335793`.
Owner: science/product owner. Needed: Confirm applicability and authorize wrong_decision.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### exclusions — HUMAN_INPUT

HUMAN_INPUT: no value supplied.

Owner: science/product owner. Needed: Confirm applicability and authorize exclusions.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 2. Physical system

### physics — HUMAN_INPUT

Nonlinear contact through assembly/preload and service history; tightening and faying friction are distinct

Owner: science/product owner. Needed: Confirm applicability and authorize physics.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### geometry — SOURCE_EXTRACT

An approved joint family with bolts, clamped members, frictional contact and assembly preload followed by the customer's service loads. Begin with a bounded single-joint assembly; do not extrapolate to flight, fatigue life or fracture certification. Approved material/plasticity and friction models must match the loads. A linear modal surrogate does not itself resolve separation or slip.

Mandatory-stratum hypothesis (count [4,4,4]):

- approved nominal clamp/service loading: numerical endpoints, joint conditions and source HUMAN_INPUT.
- approved minimum clamp/friction loading: numerical endpoints, joint conditions and source HUMAN_INPUT.
- approved maximum preload/service combination: numerical endpoints, joint conditions and source HUMAN_INPUT.
- approved worst allowed member/bolt tolerance state: numerical endpoints, joint conditions and source HUMAN_INPUT.

Scientific owner must confirm that these strata cover the unchanged customer job. Initial/boundary conditions, histories, idealisations, material applicability, neglected physics and manufacture/assembly tolerances are HUMAN_INPUT. A missing safety/material requirement stops the affected job; it is never relaxed to save compute. No physical population claim follows from deterministic execution.

Source: `docs/development/challenge_pipeline/discovery/dossiers/bolted-joint.md` sha256 `bebad0c570089a193c816d74d1bd6e40a62cb180fee119d35f4ae36e45335793`.
Owner: science/product owner. Needed: Confirm applicability and authorize geometry.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### materials — SOURCE_EXTRACT

An approved joint family with bolts, clamped members, frictional contact and assembly preload followed by the customer's service loads. Begin with a bounded single-joint assembly; do not extrapolate to flight, fatigue life or fracture certification. Approved material/plasticity and friction models must match the loads. A linear modal surrogate does not itself resolve separation or slip.

Mandatory-stratum hypothesis (count [4,4,4]):

- approved nominal clamp/service loading: numerical endpoints, joint conditions and source HUMAN_INPUT.
- approved minimum clamp/friction loading: numerical endpoints, joint conditions and source HUMAN_INPUT.
- approved maximum preload/service combination: numerical endpoints, joint conditions and source HUMAN_INPUT.
- approved worst allowed member/bolt tolerance state: numerical endpoints, joint conditions and source HUMAN_INPUT.

Scientific owner must confirm that these strata cover the unchanged customer job. Initial/boundary conditions, histories, idealisations, material applicability, neglected physics and manufacture/assembly tolerances are HUMAN_INPUT. A missing safety/material requirement stops the affected job; it is never relaxed to save compute. No physical population claim follows from deterministic execution.

Source: `docs/development/challenge_pipeline/discovery/dossiers/bolted-joint.md` sha256 `bebad0c570089a193c816d74d1bd6e40a62cb180fee119d35f4ae36e45335793`.
Owner: science/product owner. Needed: Confirm applicability and authorize materials.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### conditions — SOURCE_EXTRACT

An approved joint family with bolts, clamped members, frictional contact and assembly preload followed by the customer's service loads. Begin with a bounded single-joint assembly; do not extrapolate to flight, fatigue life or fracture certification. Approved material/plasticity and friction models must match the loads. A linear modal surrogate does not itself resolve separation or slip.

Mandatory-stratum hypothesis (count [4,4,4]):

- approved nominal clamp/service loading: numerical endpoints, joint conditions and source HUMAN_INPUT.
- approved minimum clamp/friction loading: numerical endpoints, joint conditions and source HUMAN_INPUT.
- approved maximum preload/service combination: numerical endpoints, joint conditions and source HUMAN_INPUT.
- approved worst allowed member/bolt tolerance state: numerical endpoints, joint conditions and source HUMAN_INPUT.

Scientific owner must confirm that these strata cover the unchanged customer job. Initial/boundary conditions, histories, idealisations, material applicability, neglected physics and manufacture/assembly tolerances are HUMAN_INPUT. A missing safety/material requirement stops the affected job; it is never relaxed to save compute. No physical population claim follows from deterministic execution.

Source: `docs/development/challenge_pipeline/discovery/dossiers/bolted-joint.md` sha256 `bebad0c570089a193c816d74d1bd6e40a62cb180fee119d35f4ae36e45335793`.
Owner: science/product owner. Needed: Confirm applicability and authorize conditions.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### omissions — HUMAN_INPUT

HUMAN_INPUT: no value supplied.

Owner: science/product owner. Needed: Confirm applicability and authorize omissions.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 3. Population P, Q and w

### P — SOURCE_EXTRACT

**P — customer request population.** Customer joint-revision jobs: load envelope, bolt/material family, member stiffness, preload uncertainty and contact/friction variation. Define joint correlations and load-case prevalence from the buyer; a geometry box or invented independent uniform friction distribution is insufficient.

**Q — diagnostic/acquisition proposal.** Enrich incipient separation, slip and applicable stress limits using the same approved friction/preload domain. Include the baseline's most confident failures and near-ties. Diagnostic points cannot be weighted as customer request frequency.

**w — evidence/score use.** Sampling/evidence weighting and any correction from Q to P are **HUMAN_INPUT — scientific owner**. Prospective per-stratum admissibility and reporting precede any ranking. Equal diagnostic counts are a collection convenience, not deployment weights. No soft objective can compensate for a mandatory failure.

Freeze a versioned population contract with joint variables, support, dependencies, strata/mixture probabilities, rights, exclusions, time validity and applicability. Keep request-job law distinct from the finite design menu conditional on that job. Request population and design-generation process are not interchangeable. No public draw is a hidden/protected exam draw; this researcher defines or accesses neither.

Source: `docs/development/challenge_pipeline/discovery/dossiers/bolted-joint.md` sha256 `bebad0c570089a193c816d74d1bd6e40a62cb180fee119d35f4ae36e45335793`.
Owner: science/product owner. Needed: Confirm applicability and authorize P.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### Q — SOURCE_EXTRACT

**P — customer request population.** Customer joint-revision jobs: load envelope, bolt/material family, member stiffness, preload uncertainty and contact/friction variation. Define joint correlations and load-case prevalence from the buyer; a geometry box or invented independent uniform friction distribution is insufficient.

**Q — diagnostic/acquisition proposal.** Enrich incipient separation, slip and applicable stress limits using the same approved friction/preload domain. Include the baseline's most confident failures and near-ties. Diagnostic points cannot be weighted as customer request frequency.

**w — evidence/score use.** Sampling/evidence weighting and any correction from Q to P are **HUMAN_INPUT — scientific owner**. Prospective per-stratum admissibility and reporting precede any ranking. Equal diagnostic counts are a collection convenience, not deployment weights. No soft objective can compensate for a mandatory failure.

Freeze a versioned population contract with joint variables, support, dependencies, strata/mixture probabilities, rights, exclusions, time validity and applicability. Keep request-job law distinct from the finite design menu conditional on that job. Request population and design-generation process are not interchangeable. No public draw is a hidden/protected exam draw; this researcher defines or accesses neither.

Source: `docs/development/challenge_pipeline/discovery/dossiers/bolted-joint.md` sha256 `bebad0c570089a193c816d74d1bd6e40a62cb180fee119d35f4ae36e45335793`.
Owner: science/product owner. Needed: Confirm applicability and authorize Q.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### w — SOURCE_EXTRACT

**P — customer request population.** Customer joint-revision jobs: load envelope, bolt/material family, member stiffness, preload uncertainty and contact/friction variation. Define joint correlations and load-case prevalence from the buyer; a geometry box or invented independent uniform friction distribution is insufficient.

**Q — diagnostic/acquisition proposal.** Enrich incipient separation, slip and applicable stress limits using the same approved friction/preload domain. Include the baseline's most confident failures and near-ties. Diagnostic points cannot be weighted as customer request frequency.

**w — evidence/score use.** Sampling/evidence weighting and any correction from Q to P are **HUMAN_INPUT — scientific owner**. Prospective per-stratum admissibility and reporting precede any ranking. Equal diagnostic counts are a collection convenience, not deployment weights. No soft objective can compensate for a mandatory failure.

Freeze a versioned population contract with joint variables, support, dependencies, strata/mixture probabilities, rights, exclusions, time validity and applicability. Keep request-job law distinct from the finite design menu conditional on that job. Request population and design-generation process are not interchangeable. No public draw is a hidden/protected exam draw; this researcher defines or accesses neither.

Source: `docs/development/challenge_pipeline/discovery/dossiers/bolted-joint.md` sha256 `bebad0c570089a193c816d74d1bd6e40a62cb180fee119d35f4ae36e45335793`.
Owner: science/product owner. Needed: Confirm applicability and authorize w.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### strata — SOURCE_EXTRACT

**P — customer request population.** Customer joint-revision jobs: load envelope, bolt/material family, member stiffness, preload uncertainty and contact/friction variation. Define joint correlations and load-case prevalence from the buyer; a geometry box or invented independent uniform friction distribution is insufficient.

**Q — diagnostic/acquisition proposal.** Enrich incipient separation, slip and applicable stress limits using the same approved friction/preload domain. Include the baseline's most confident failures and near-ties. Diagnostic points cannot be weighted as customer request frequency.

**w — evidence/score use.** Sampling/evidence weighting and any correction from Q to P are **HUMAN_INPUT — scientific owner**. Prospective per-stratum admissibility and reporting precede any ranking. Equal diagnostic counts are a collection convenience, not deployment weights. No soft objective can compensate for a mandatory failure.

Freeze a versioned population contract with joint variables, support, dependencies, strata/mixture probabilities, rights, exclusions, time validity and applicability. Keep request-job law distinct from the finite design menu conditional on that job. Request population and design-generation process are not interchangeable. No public draw is a hidden/protected exam draw; this researcher defines or accesses neither.

Source: `docs/development/challenge_pipeline/discovery/dossiers/bolted-joint.md` sha256 `bebad0c570089a193c816d74d1bd6e40a62cb180fee119d35f4ae36e45335793`.
Owner: science/product owner. Needed: Confirm applicability and authorize strata.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### independent_unit — HUMAN_INPUT

HUMAN_INPUT: no value supplied.

Owner: science/product owner. Needed: Confirm applicability and authorize independent_unit.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 4. Case contract

### case_identity — SOURCE_EXTRACT

CAD/parameterisation; bolt/thread modelling convention; owned material data; preload method; friction/contact definitions; full assembly/service sequence; geometry/load/tolerance envelope; allowable stress/slip/separation rules. All numeric loads, factors and thresholds are HUMAN_INPUT.

A proposed case contains a customer-job version, action geometry, stratum/condition, material version, initial/boundary/history version and exact requested outputs. Freeze canonical units/order, numerical representation, valid-geometry checks, action eligibility, case/material/extractor identities and failure semantics before collecting evidence. A draft schema outline, all registration fields unresolved:

```json
{
  "customer_job_version": "HUMAN_INPUT",
  "action_geometry_version": "HUMAN_INPUT",
  "stratum_and_condition_contract": "HUMAN_INPUT",
  "material_and_rights_version": "HUMAN_INPUT",
  "initial_boundary_history_version": "HUMAN_INPUT",
  "reference_image_deck_mesh_extractor_pins": "HUMAN_INPUT",
  "measurement_and_limit_contract": "HUMAN_INPUT",
  "request_population_P_version": "HUMAN_INPUT",
  "proposal_Q_and_evidence_w_versions": "HUMAN_INPUT"
}
```

This is an explanatory outline, not a public runtime schema migration. Supply only an allow-listed public research case. Internal reference diagnostics, protected identities/metadata and future evaluation/reconstruction-sensitive state cannot enter miner/public outputs. Mock/practice cases must remain structurally separated from official evaluation. No existing Challenge identifier or file is changed.

Source: `docs/development/challenge_pipeline/discovery/dossiers/bolted-joint.md` sha256 `bebad0c570089a193c816d74d1bd6e40a62cb180fee119d35f4ae36e45335793`.
Owner: science/product owner. Needed: Confirm applicability and authorize case_identity.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### validity — HUMAN_INPUT

HUMAN_INPUT: no value supplied.

Owner: science/product owner. Needed: Confirm applicability and authorize validity.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### disclosure — SOURCE_EXTRACT

CAD/parameterisation; bolt/thread modelling convention; owned material data; preload method; friction/contact definitions; full assembly/service sequence; geometry/load/tolerance envelope; allowable stress/slip/separation rules. All numeric loads, factors and thresholds are HUMAN_INPUT.

A proposed case contains a customer-job version, action geometry, stratum/condition, material version, initial/boundary/history version and exact requested outputs. Freeze canonical units/order, numerical representation, valid-geometry checks, action eligibility, case/material/extractor identities and failure semantics before collecting evidence. A draft schema outline, all registration fields unresolved:

```json
{
  "customer_job_version": "HUMAN_INPUT",
  "action_geometry_version": "HUMAN_INPUT",
  "stratum_and_condition_contract": "HUMAN_INPUT",
  "material_and_rights_version": "HUMAN_INPUT",
  "initial_boundary_history_version": "HUMAN_INPUT",
  "reference_image_deck_mesh_extractor_pins": "HUMAN_INPUT",
  "measurement_and_limit_contract": "HUMAN_INPUT",
  "request_population_P_version": "HUMAN_INPUT",
  "proposal_Q_and_evidence_w_versions": "HUMAN_INPUT"
}
```

This is an explanatory outline, not a public runtime schema migration. Supply only an allow-listed public research case. Internal reference diagnostics, protected identities/metadata and future evaluation/reconstruction-sensitive state cannot enter miner/public outputs. Mock/practice cases must remain structurally separated from official evaluation. No existing Challenge identifier or file is changed.

Source: `docs/development/challenge_pipeline/discovery/dossiers/bolted-joint.md` sha256 `bebad0c570089a193c816d74d1bd6e40a62cb180fee119d35f4ae36e45335793`.
Owner: science/product owner. Needed: Confirm applicability and authorize disclosure.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 5. Reference policy

### solver — SOURCE_EXTRACT

CalculiX nonlinear structural/contact route with approved preload and service sequencing. Validate balances, pretension force, mesh/contact/load-step sensitivity and independent buyer structural FE results. VDI-style compliance is a baseline and limiting-case check, not a disqualified competitor. Applicable criteria/uncertainty and pins are HUMAN_INPUT.

Open route: [CALC: CalculiX authors](https://www.dhondt.de/). Pin reviewed open licence/dependencies, source revision, container digest, compiler/math environment, meshing/solver/deck/material versions and extraction definition. None is supplied here as a fake immutable pin. Reproducibility within documented tolerances is necessary; physical adequacy is separate.

Credibility **earned: NOT_DEMONSTRATED**; target: framework Tier 2 via an applicable independent buyer tool. Tier 3 would require applicable physical experiments and their own rights/budget/acceptance; it is not priced or earned by this report. A successful balance or cross-tool check is evidence for an owner, not qualification itself.

Infrastructure failures preserve FAILED_INFRA/retry/non-scientific semantics. Nonconvergence, inappropriate constitutive law, extraction ambiguity or failed physical balance are reference inadequacy/UNRESOLVED and never candidate scientific failure. Stop grading until the affected reference is adequate. Tolerances, uncertainty bands, convergence thresholds and credibility acceptance are **HUMAN_INPUT — reference/science owners**.

Source: `docs/development/challenge_pipeline/discovery/dossiers/bolted-joint.md` sha256 `bebad0c570089a193c816d74d1bd6e40a62cb180fee119d35f4ae36e45335793`.
Owner: science/product owner. Needed: Confirm applicability and authorize solver.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### pins — SOURCE_EXTRACT

CalculiX nonlinear structural/contact route with approved preload and service sequencing. Validate balances, pretension force, mesh/contact/load-step sensitivity and independent buyer structural FE results. VDI-style compliance is a baseline and limiting-case check, not a disqualified competitor. Applicable criteria/uncertainty and pins are HUMAN_INPUT.

Open route: [CALC: CalculiX authors](https://www.dhondt.de/). Pin reviewed open licence/dependencies, source revision, container digest, compiler/math environment, meshing/solver/deck/material versions and extraction definition. None is supplied here as a fake immutable pin. Reproducibility within documented tolerances is necessary; physical adequacy is separate.

Credibility **earned: NOT_DEMONSTRATED**; target: framework Tier 2 via an applicable independent buyer tool. Tier 3 would require applicable physical experiments and their own rights/budget/acceptance; it is not priced or earned by this report. A successful balance or cross-tool check is evidence for an owner, not qualification itself.

Infrastructure failures preserve FAILED_INFRA/retry/non-scientific semantics. Nonconvergence, inappropriate constitutive law, extraction ambiguity or failed physical balance are reference inadequacy/UNRESOLVED and never candidate scientific failure. Stop grading until the affected reference is adequate. Tolerances, uncertainty bands, convergence thresholds and credibility acceptance are **HUMAN_INPUT — reference/science owners**.

Source: `docs/development/challenge_pipeline/discovery/dossiers/bolted-joint.md` sha256 `bebad0c570089a193c816d74d1bd6e40a62cb180fee119d35f4ae36e45335793`.
Owner: science/product owner. Needed: Confirm applicability and authorize pins.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### refinement — SOURCE_EXTRACT

CalculiX nonlinear structural/contact route with approved preload and service sequencing. Validate balances, pretension force, mesh/contact/load-step sensitivity and independent buyer structural FE results. VDI-style compliance is a baseline and limiting-case check, not a disqualified competitor. Applicable criteria/uncertainty and pins are HUMAN_INPUT.

Open route: [CALC: CalculiX authors](https://www.dhondt.de/). Pin reviewed open licence/dependencies, source revision, container digest, compiler/math environment, meshing/solver/deck/material versions and extraction definition. None is supplied here as a fake immutable pin. Reproducibility within documented tolerances is necessary; physical adequacy is separate.

Credibility **earned: NOT_DEMONSTRATED**; target: framework Tier 2 via an applicable independent buyer tool. Tier 3 would require applicable physical experiments and their own rights/budget/acceptance; it is not priced or earned by this report. A successful balance or cross-tool check is evidence for an owner, not qualification itself.

Infrastructure failures preserve FAILED_INFRA/retry/non-scientific semantics. Nonconvergence, inappropriate constitutive law, extraction ambiguity or failed physical balance are reference inadequacy/UNRESOLVED and never candidate scientific failure. Stop grading until the affected reference is adequate. Tolerances, uncertainty bands, convergence thresholds and credibility acceptance are **HUMAN_INPUT — reference/science owners**.

Source: `docs/development/challenge_pipeline/discovery/dossiers/bolted-joint.md` sha256 `bebad0c570089a193c816d74d1bd6e40a62cb180fee119d35f4ae36e45335793`.
Owner: science/product owner. Needed: Confirm applicability and authorize refinement.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### uncertainty — SOURCE_EXTRACT

CalculiX nonlinear structural/contact route with approved preload and service sequencing. Validate balances, pretension force, mesh/contact/load-step sensitivity and independent buyer structural FE results. VDI-style compliance is a baseline and limiting-case check, not a disqualified competitor. Applicable criteria/uncertainty and pins are HUMAN_INPUT.

Open route: [CALC: CalculiX authors](https://www.dhondt.de/). Pin reviewed open licence/dependencies, source revision, container digest, compiler/math environment, meshing/solver/deck/material versions and extraction definition. None is supplied here as a fake immutable pin. Reproducibility within documented tolerances is necessary; physical adequacy is separate.

Credibility **earned: NOT_DEMONSTRATED**; target: framework Tier 2 via an applicable independent buyer tool. Tier 3 would require applicable physical experiments and their own rights/budget/acceptance; it is not priced or earned by this report. A successful balance or cross-tool check is evidence for an owner, not qualification itself.

Infrastructure failures preserve FAILED_INFRA/retry/non-scientific semantics. Nonconvergence, inappropriate constitutive law, extraction ambiguity or failed physical balance are reference inadequacy/UNRESOLVED and never candidate scientific failure. Stop grading until the affected reference is adequate. Tolerances, uncertainty bands, convergence thresholds and credibility acceptance are **HUMAN_INPUT — reference/science owners**.

Source: `docs/development/challenge_pipeline/discovery/dossiers/bolted-joint.md` sha256 `bebad0c570089a193c816d74d1bd6e40a62cb180fee119d35f4ae36e45335793`.
Owner: science/product owner. Needed: Confirm applicability and authorize uncertainty.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### cost — SOURCE_EXTRACT

CalculiX nonlinear structural/contact route with approved preload and service sequencing. Validate balances, pretension force, mesh/contact/load-step sensitivity and independent buyer structural FE results. VDI-style compliance is a baseline and limiting-case check, not a disqualified competitor. Applicable criteria/uncertainty and pins are HUMAN_INPUT.

Open route: [CALC: CalculiX authors](https://www.dhondt.de/). Pin reviewed open licence/dependencies, source revision, container digest, compiler/math environment, meshing/solver/deck/material versions and extraction definition. None is supplied here as a fake immutable pin. Reproducibility within documented tolerances is necessary; physical adequacy is separate.

Credibility **earned: NOT_DEMONSTRATED**; target: framework Tier 2 via an applicable independent buyer tool. Tier 3 would require applicable physical experiments and their own rights/budget/acceptance; it is not priced or earned by this report. A successful balance or cross-tool check is evidence for an owner, not qualification itself.

Infrastructure failures preserve FAILED_INFRA/retry/non-scientific semantics. Nonconvergence, inappropriate constitutive law, extraction ambiguity or failed physical balance are reference inadequacy/UNRESOLVED and never candidate scientific failure. Stop grading until the affected reference is adequate. Tolerances, uncertainty bands, convergence thresholds and credibility acceptance are **HUMAN_INPUT — reference/science owners**.

Source: `docs/development/challenge_pipeline/discovery/dossiers/bolted-joint.md` sha256 `bebad0c570089a193c816d74d1bd6e40a62cb180fee119d35f4ae36e45335793`.
Owner: science/product owner. Needed: Confirm applicability and authorize cost.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 6. Output and measurement contract

### outputs — SOURCE_EXTRACT

Joint opening/separation, slip, clamp load transfer, applicable bolt/member stress and displacement over every registered assembly/service step. Grade explicitly defined regularised stresses or resultants; stress singularities, absent thread detail and solver contact residuals need prospective handling.

Hard-limit family: Customer separation/slip permissions, material stress/strain allowables, required load cases, bolt/preload and package/manufacturing limits. NASA examples are not authority for a new industrial or aerospace limit. Friction uncertainty cannot be narrowed to make the menu feasible.

Freeze each quantity's units, sample locations, aggregation, sign convention, mask, extrema treatment, applicability and reference uncertainty. Register output field/array shape and the decision projection prospectively. The same definitions and limits apply to reference, strongest cheap baseline and model. Measurement definition, qualification, applicability and score use are distinct approvals.

Admissibility must be established for **every required output in every mandatory stratum** before the customer's objective can rank actions. Near-infeasible means outside a prospectively approved uncertainty/refinement band for a specified hard limit while other mandatory conditions are respected; ambiguous reference signs remain UNRESOLVED. No new scalar score, scientific tolerance, safety factor or loss-based exemption is authorised. Customer objective: Customer's preference among fully admissible joint configurations, such as manufacturing/assembly effort or material use, is HUMAN_INPUT.

Source: `docs/development/challenge_pipeline/discovery/dossiers/bolted-joint.md` sha256 `bebad0c570089a193c816d74d1bd6e40a62cb180fee119d35f4ae36e45335793`.
Owner: science/product owner. Needed: Confirm applicability and authorize outputs.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### hard_limits — SOURCE_EXTRACT

Joint opening/separation, slip, clamp load transfer, applicable bolt/member stress and displacement over every registered assembly/service step. Grade explicitly defined regularised stresses or resultants; stress singularities, absent thread detail and solver contact residuals need prospective handling.

Hard-limit family: Customer separation/slip permissions, material stress/strain allowables, required load cases, bolt/preload and package/manufacturing limits. NASA examples are not authority for a new industrial or aerospace limit. Friction uncertainty cannot be narrowed to make the menu feasible.

Freeze each quantity's units, sample locations, aggregation, sign convention, mask, extrema treatment, applicability and reference uncertainty. Register output field/array shape and the decision projection prospectively. The same definitions and limits apply to reference, strongest cheap baseline and model. Measurement definition, qualification, applicability and score use are distinct approvals.

Admissibility must be established for **every required output in every mandatory stratum** before the customer's objective can rank actions. Near-infeasible means outside a prospectively approved uncertainty/refinement band for a specified hard limit while other mandatory conditions are respected; ambiguous reference signs remain UNRESOLVED. No new scalar score, scientific tolerance, safety factor or loss-based exemption is authorised. Customer objective: Customer's preference among fully admissible joint configurations, such as manufacturing/assembly effort or material use, is HUMAN_INPUT.

Source: `docs/development/challenge_pipeline/discovery/dossiers/bolted-joint.md` sha256 `bebad0c570089a193c816d74d1bd6e40a62cb180fee119d35f4ae36e45335793`.
Owner: science/product owner. Needed: Confirm applicability and authorize hard_limits.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### objective — SOURCE_EXTRACT

Joint opening/separation, slip, clamp load transfer, applicable bolt/member stress and displacement over every registered assembly/service step. Grade explicitly defined regularised stresses or resultants; stress singularities, absent thread detail and solver contact residuals need prospective handling.

Hard-limit family: Customer separation/slip permissions, material stress/strain allowables, required load cases, bolt/preload and package/manufacturing limits. NASA examples are not authority for a new industrial or aerospace limit. Friction uncertainty cannot be narrowed to make the menu feasible.

Freeze each quantity's units, sample locations, aggregation, sign convention, mask, extrema treatment, applicability and reference uncertainty. Register output field/array shape and the decision projection prospectively. The same definitions and limits apply to reference, strongest cheap baseline and model. Measurement definition, qualification, applicability and score use are distinct approvals.

Admissibility must be established for **every required output in every mandatory stratum** before the customer's objective can rank actions. Near-infeasible means outside a prospectively approved uncertainty/refinement band for a specified hard limit while other mandatory conditions are respected; ambiguous reference signs remain UNRESOLVED. No new scalar score, scientific tolerance, safety factor or loss-based exemption is authorised. Customer objective: Customer's preference among fully admissible joint configurations, such as manufacturing/assembly effort or material use, is HUMAN_INPUT.

Source: `docs/development/challenge_pipeline/discovery/dossiers/bolted-joint.md` sha256 `bebad0c570089a193c816d74d1bd6e40a62cb180fee119d35f4ae36e45335793`.
Owner: science/product owner. Needed: Confirm applicability and authorize objective.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 7. Construction contract

### vocabulary — SOURCE_EXTRACT

Research a fast model predicting the frozen physical outputs/decision projection from allowed geometry, condition and material inputs. The current bounded Carbon search surface is neural-operator **TrainingStrategy**, subject to its current contracts. This draft does not widen it to arbitrary solver/code execution or a future ModelConstructionStrategy.

Parameterised geometry generation, meshing, reference runs and official grading remain owner-controlled. Learners can use only authorised public research examples/features under reviewed licences; exact permitted inputs, architecture/dependency/compute bounds, training split and geometry-to-fixed-output representation are **HUMAN_INPUT — construction/security owners**. No private samples, hidden seeds or reference authority are provided to participants. Any prototype stays developmental and structurally unable to emit LIVE ranking/frontier/treasury/product authority.

Strong baseline: **VDI-style joint compliance calculation plus contact-aware cached structural FE response surface and buyer's existing sizing worksheet**. Incremental-value hypothesis: separation/slip topology changes can alter joint admissibility. Demonstrate a decision residual beyond cached contact-aware FE; pure elastic stiffness may reduce to current f08's cheap response-map failure. Complete acquisition/build/fit/search/verification and retained high-fidelity calls must be counted for both alternatives. A good imitation of an inadequate reference is not a useful model.

Source: `docs/development/challenge_pipeline/discovery/dossiers/bolted-joint.md` sha256 `bebad0c570089a193c816d74d1bd6e40a62cb180fee119d35f4ae36e45335793`.
Owner: science/product owner. Needed: Confirm applicability and authorize vocabulary.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### training — HUMAN_INPUT

HUMAN_INPUT: no value supplied.

Owner: science/product owner. Needed: Confirm applicability and authorize training.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### permissions — SOURCE_EXTRACT

Research a fast model predicting the frozen physical outputs/decision projection from allowed geometry, condition and material inputs. The current bounded Carbon search surface is neural-operator **TrainingStrategy**, subject to its current contracts. This draft does not widen it to arbitrary solver/code execution or a future ModelConstructionStrategy.

Parameterised geometry generation, meshing, reference runs and official grading remain owner-controlled. Learners can use only authorised public research examples/features under reviewed licences; exact permitted inputs, architecture/dependency/compute bounds, training split and geometry-to-fixed-output representation are **HUMAN_INPUT — construction/security owners**. No private samples, hidden seeds or reference authority are provided to participants. Any prototype stays developmental and structurally unable to emit LIVE ranking/frontier/treasury/product authority.

Strong baseline: **VDI-style joint compliance calculation plus contact-aware cached structural FE response surface and buyer's existing sizing worksheet**. Incremental-value hypothesis: separation/slip topology changes can alter joint admissibility. Demonstrate a decision residual beyond cached contact-aware FE; pure elastic stiffness may reduce to current f08's cheap response-map failure. Complete acquisition/build/fit/search/verification and retained high-fidelity calls must be counted for both alternatives. A good imitation of an inadequate reference is not a useful model.

Source: `docs/development/challenge_pipeline/discovery/dossiers/bolted-joint.md` sha256 `bebad0c570089a193c816d74d1bd6e40a62cb180fee119d35f4ae36e45335793`.
Owner: construction/security owner. Needed: Confirm applicability and authorize permissions.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 8. Research kit

### public_kit — SOURCE_EXTRACT

Proposed public kit only: source-linked solver documentation, independently licensed geometry/material examples, canonical explanatory schema, output/measurement definitions, baseline specification, openly generated diagnostic cases and failure-report format. Release actual files only after owner rights/applicability review. It contains no official bank, private metadata, seeds, protected samples, reversible draw identities or AX42 material.

Training/support/domain claims require separate authorisation. Include both cheap-baseline and reference costs, convergence diagnostics and known limitations in public research reports where disclosure allows. A practice kit remains incomplete and cannot substitute for the independent exam. No kit is built or solver installed by this researcher.

Source: `docs/development/challenge_pipeline/discovery/dossiers/bolted-joint.md` sha256 `bebad0c570089a193c816d74d1bd6e40a62cb180fee119d35f4ae36e45335793`.
Owner: science/product owner. Needed: Confirm applicability and authorize public_kit.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### baseline — SOURCE_EXTRACT

Proposed public kit only: source-linked solver documentation, independently licensed geometry/material examples, canonical explanatory schema, output/measurement definitions, baseline specification, openly generated diagnostic cases and failure-report format. Release actual files only after owner rights/applicability review. It contains no official bank, private metadata, seeds, protected samples, reversible draw identities or AX42 material.

Training/support/domain claims require separate authorisation. Include both cheap-baseline and reference costs, convergence diagnostics and known limitations in public research reports where disclosure allows. A practice kit remains incomplete and cannot substitute for the independent exam. No kit is built or solver installed by this researcher.

Source: `docs/development/challenge_pipeline/discovery/dossiers/bolted-joint.md` sha256 `bebad0c570089a193c816d74d1bd6e40a62cb180fee119d35f4ae36e45335793`.
Owner: science/product owner. Needed: Confirm applicability and authorize baseline.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### rights — HUMAN_INPUT

HUMAN_INPUT: no value supplied.

Owner: science/product owner. Needed: Confirm applicability and authorize rights.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 9. Evidence plan

### panel — SOURCE_EXTRACT

Before any new collection: get a real customer job with unchanged sourced limits and rights; confirm the open route exactly produces the needed outputs; check independent reference applicability and the buyer's actual current latency; and obtain the baseline's cheapest complete decisions. Source-first work may reject the candidate without a solve.

Then a separately authorised Data Collection task can run the panel below. It must demonstrate refined feasible witnesses and prospective contested counts per stratum before a full bank. Qualification owners choose tolerances, T3 power, alpha, effect severity, question law and reference acceptance. These are HUMAN_INPUT, not selected from cheap runtimes.

Full-bank hypothesis: designs [24,24,24], strata [4,4,4], primary cases [96,96,96], refined cases [32,32,32] at multiplier [2,2,2], charged failed attempts [20,20,20], independent witness pairs [8,8,8] with two tools each. Total equivalent complete cases U=[196,196,196]. This draft budget is not proof that the menu has the required feasible/near-infeasible counts.

C1 complete-case CPU-hours **0.03 / 0.08 / 0.24**, RAM GiB **1.00 / 4.00 / 12.00**; p50/p95 and elapsed/CPU ratio are NOT_MEASURED. Charged startup C2 **EUR 26.11 / 42.08 / 93.21**, under the [common formula](../methodology.md). All estimates are ASSUMPTION. Witness licence assumption is zero incremental charge only if the buyer has rights/access; otherwise reprice and reject if the cap fails. No spend is authorised.

V4 compares analytical/library, interpolation, calibrated response surface, reduced physics and actual buyer tool at matched admissibility, with complete overhead and retained verification over M=[1,10,100] served revisions (ASSUMPTION sensitivity). Acceptable false-feasible rate, regret/decision agreement and economic threshold are HUMAN_INPUT. An equal cheap decision, infeasible stratum or unqualified reference stops admission. The discovery estimate screen fits EUR100, but an actual bill above the cap stops the proposed bank.

Source: `docs/development/challenge_pipeline/discovery/dossiers/bolted-joint.md` sha256 `bebad0c570089a193c816d74d1bd6e40a62cb180fee119d35f4ae36e45335793`.
Owner: science/product owner. Needed: Confirm applicability and authorize panel.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### controls — SOURCE_EXTRACT

Before any new collection: get a real customer job with unchanged sourced limits and rights; confirm the open route exactly produces the needed outputs; check independent reference applicability and the buyer's actual current latency; and obtain the baseline's cheapest complete decisions. Source-first work may reject the candidate without a solve.

Then a separately authorised Data Collection task can run the panel below. It must demonstrate refined feasible witnesses and prospective contested counts per stratum before a full bank. Qualification owners choose tolerances, T3 power, alpha, effect severity, question law and reference acceptance. These are HUMAN_INPUT, not selected from cheap runtimes.

Full-bank hypothesis: designs [24,24,24], strata [4,4,4], primary cases [96,96,96], refined cases [32,32,32] at multiplier [2,2,2], charged failed attempts [20,20,20], independent witness pairs [8,8,8] with two tools each. Total equivalent complete cases U=[196,196,196]. This draft budget is not proof that the menu has the required feasible/near-infeasible counts.

C1 complete-case CPU-hours **0.03 / 0.08 / 0.24**, RAM GiB **1.00 / 4.00 / 12.00**; p50/p95 and elapsed/CPU ratio are NOT_MEASURED. Charged startup C2 **EUR 26.11 / 42.08 / 93.21**, under the [common formula](../methodology.md). All estimates are ASSUMPTION. Witness licence assumption is zero incremental charge only if the buyer has rights/access; otherwise reprice and reject if the cap fails. No spend is authorised.

V4 compares analytical/library, interpolation, calibrated response surface, reduced physics and actual buyer tool at matched admissibility, with complete overhead and retained verification over M=[1,10,100] served revisions (ASSUMPTION sensitivity). Acceptable false-feasible rate, regret/decision agreement and economic threshold are HUMAN_INPUT. An equal cheap decision, infeasible stratum or unqualified reference stops admission. The discovery estimate screen fits EUR100, but an actual bill above the cap stops the proposed bank.

Source: `docs/development/challenge_pipeline/discovery/dossiers/bolted-joint.md` sha256 `bebad0c570089a193c816d74d1bd6e40a62cb180fee119d35f4ae36e45335793`.
Owner: science/product owner. Needed: Confirm applicability and authorize controls.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### confirmation — HUMAN_INPUT

HUMAN_INPUT: no value supplied.

Owner: science/product owner. Needed: Confirm applicability and authorize confirmation.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 10. Readiness and claim record

### readiness — SOURCE_EXTRACT

| Field | Present record / owner / blocked behaviour |
| --- | --- |
| Customer packet/acceptance | HUMAN_INPUT — customer/business owner; G1 and adoption blocked |
| Scientific limits, P/Q/w and coverage | HUMAN_INPUT — science/customer owner; official draws and grading blocked |
| Exact image/deck/material/measurement pins | HUMAN_INPUT — reference owner; reference execution/grading blocked |
| G3 feasible witnesses / G4 counts | NOT_DEMONSTRATED — Data Collection evidence required; no finalist |
| G5 baseline advantage | NOT_DEMONSTRATED — matched V4 panel required |
| C1/C2/C3/C4 | ASSUMPTION or NOT_MEASURED; no approved bank affordability/benefit |
| Credibility / qualification | NOT_DEMONSTRATED; target Tier 2 is a plan, not earned |
| Question/power/security contracts | HUMAN_INPUT — relevant owners; no new execution authority |
| Adoption / replacement / dispatch | HUMAN_INPUT; false dispatch readiness; no grant or runtime ID |

Earned maturity is a sourced conditional research specification. Scientific, security, network, commercial and production qualification are not earned. Final scientific/adoption decisions belong to owners. Nothing here qualifies the exam or candidates, relaxes a limit, activates LIVE, creates a frontier/settlement obligation, or changes historical evidence.

Source: `docs/development/challenge_pipeline/discovery/dossiers/bolted-joint.md` sha256 `bebad0c570089a193c816d74d1bd6e40a62cb180fee119d35f4ae36e45335793`.
Owner: science/product owner. Needed: Confirm applicability and authorize readiness.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### owners — SOURCE_EXTRACT

| Field | Present record / owner / blocked behaviour |
| --- | --- |
| Customer packet/acceptance | HUMAN_INPUT — customer/business owner; G1 and adoption blocked |
| Scientific limits, P/Q/w and coverage | HUMAN_INPUT — science/customer owner; official draws and grading blocked |
| Exact image/deck/material/measurement pins | HUMAN_INPUT — reference owner; reference execution/grading blocked |
| G3 feasible witnesses / G4 counts | NOT_DEMONSTRATED — Data Collection evidence required; no finalist |
| G5 baseline advantage | NOT_DEMONSTRATED — matched V4 panel required |
| C1/C2/C3/C4 | ASSUMPTION or NOT_MEASURED; no approved bank affordability/benefit |
| Credibility / qualification | NOT_DEMONSTRATED; target Tier 2 is a plan, not earned |
| Question/power/security contracts | HUMAN_INPUT — relevant owners; no new execution authority |
| Adoption / replacement / dispatch | HUMAN_INPUT; false dispatch readiness; no grant or runtime ID |

Earned maturity is a sourced conditional research specification. Scientific, security, network, commercial and production qualification are not earned. Final scientific/adoption decisions belong to owners. Nothing here qualifies the exam or candidates, relaxes a limit, activates LIVE, creates a frontier/settlement obligation, or changes historical evidence.

Source: `docs/development/challenge_pipeline/discovery/dossiers/bolted-joint.md` sha256 `bebad0c570089a193c816d74d1bd6e40a62cb180fee119d35f4ae36e45335793`.
Owner: science/product owner. Needed: Confirm applicability and authorize owners.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### next_gate — SOURCE_EXTRACT

| Field | Present record / owner / blocked behaviour |
| --- | --- |
| Customer packet/acceptance | HUMAN_INPUT — customer/business owner; G1 and adoption blocked |
| Scientific limits, P/Q/w and coverage | HUMAN_INPUT — science/customer owner; official draws and grading blocked |
| Exact image/deck/material/measurement pins | HUMAN_INPUT — reference owner; reference execution/grading blocked |
| G3 feasible witnesses / G4 counts | NOT_DEMONSTRATED — Data Collection evidence required; no finalist |
| G5 baseline advantage | NOT_DEMONSTRATED — matched V4 panel required |
| C1/C2/C3/C4 | ASSUMPTION or NOT_MEASURED; no approved bank affordability/benefit |
| Credibility / qualification | NOT_DEMONSTRATED; target Tier 2 is a plan, not earned |
| Question/power/security contracts | HUMAN_INPUT — relevant owners; no new execution authority |
| Adoption / replacement / dispatch | HUMAN_INPUT; false dispatch readiness; no grant or runtime ID |

Earned maturity is a sourced conditional research specification. Scientific, security, network, commercial and production qualification are not earned. Final scientific/adoption decisions belong to owners. Nothing here qualifies the exam or candidates, relaxes a limit, activates LIVE, creates a frontier/settlement obligation, or changes historical evidence.

Source: `docs/development/challenge_pipeline/discovery/dossiers/bolted-joint.md` sha256 `bebad0c570089a193c816d74d1bd6e40a62cb180fee119d35f4ae36e45335793`.
Owner: science/product owner. Needed: Confirm applicability and authorize next_gate.
Held closed: No runtime registration, bank draw, execution, qualification or spend.
