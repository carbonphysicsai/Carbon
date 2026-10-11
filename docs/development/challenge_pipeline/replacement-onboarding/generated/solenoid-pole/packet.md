# solenoid-pole — generated common packet draft

DEVELOPMENT / DRAFT_ONLY. SOURCE_EXTRACT means verified bytes, not approval.
Every unsourced field is HUMAN_INPUT. No runtime or qualification authority.

## 1. Engineering job

### buyer — HUMAN_INPUT

Proportional-actuator magnetics engineer (conditional internal mock customer)

Owner: science/product owner. Needed: Confirm applicability and authorize buyer.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### decision — HUMAN_INPUT

Choose a non-PM pole profile meeting every force-stroke condition with least stated-temperature copper loss

Owner: science/product owner. Needed: Confirm applicability and authorize decision.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### value — SOURCE_EXTRACT

An actuator magnetics engineer chooses a pole profile and air-gap geometry for a proportional solenoid that must satisfy the customer's force-stroke envelope while staying within packaging and electrical limits. Simulation supports this class of job in Magnet-Schultz's workflow; independent solenoid research examines force calculation. Neither source supplies Carbon's actual customer envelope.

Buyer role: **Actuator magnetics engineer**. Proposed decision: **Choose pole/air-gap geometry**. Independent role/workflow evidence: [SOL1: Magnet-Schultz](https://www.magnet-schultz.com/en/products); [SOL2: Vogel / Ulm and Heilbronn authors](https://www.comsol.com/paper/theory-of-proportional-solenoids-and-magnetic-force-calculation-using-comsol-multiphysics-11391); [SOL3: Magnet-Schultz](https://www.magnet-schultz.com/fileadmin/Daten/Vertrieb/PR1/TechnErl/GXX_e.pdf). Manufacturer and independent research origins are distinguished; neither is a confirmed Carbon customer. Buyer identity/authorised contact, actual current simulation tool, decision latency/cadence, allowed materials/data rights, acceptance criteria and value interview are **HUMAN_INPUT — business/customer owner; blocks G1/adoption**.

V2 proposed avoidable effort 3.00 / 8.00 / 20.00 hours/revision × 60.00 / 90.00 / 120.00 EUR/hour gives 180.00 / 720.00 / 2400.00 EUR/revision. V3 assumes 5.00 / 20.00 / 50.00 teams × 6.00 / 24.00 / 60.00 revisions/team/year = 30.00 / 480.00 / 3000.00 revisions/year. These are conditional cohort scenarios, not buyers/market size, actual savings or willingness to pay. Demonstrated commercial floor is zero.

Source: `docs/development/challenge_pipeline/discovery/dossiers/solenoid-pole.md` sha256 `8ab318c38c01bdc460afa213fdbf8f6b7b679deb946ae034bc92ffe40e524bc6`.
Owner: science/product owner. Needed: Confirm applicability and authorize value.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### wrong_decision — SOURCE_EXTRACT

An actuator magnetics engineer chooses a pole profile and air-gap geometry for a proportional solenoid that must satisfy the customer's force-stroke envelope while staying within packaging and electrical limits. Simulation supports this class of job in Magnet-Schultz's workflow; independent solenoid research examines force calculation. Neither source supplies Carbon's actual customer envelope.

Buyer role: **Actuator magnetics engineer**. Proposed decision: **Choose pole/air-gap geometry**. Independent role/workflow evidence: [SOL1: Magnet-Schultz](https://www.magnet-schultz.com/en/products); [SOL2: Vogel / Ulm and Heilbronn authors](https://www.comsol.com/paper/theory-of-proportional-solenoids-and-magnetic-force-calculation-using-comsol-multiphysics-11391); [SOL3: Magnet-Schultz](https://www.magnet-schultz.com/fileadmin/Daten/Vertrieb/PR1/TechnErl/GXX_e.pdf). Manufacturer and independent research origins are distinguished; neither is a confirmed Carbon customer. Buyer identity/authorised contact, actual current simulation tool, decision latency/cadence, allowed materials/data rights, acceptance criteria and value interview are **HUMAN_INPUT — business/customer owner; blocks G1/adoption**.

V2 proposed avoidable effort 3.00 / 8.00 / 20.00 hours/revision × 60.00 / 90.00 / 120.00 EUR/hour gives 180.00 / 720.00 / 2400.00 EUR/revision. V3 assumes 5.00 / 20.00 / 50.00 teams × 6.00 / 24.00 / 60.00 revisions/team/year = 30.00 / 480.00 / 3000.00 revisions/year. These are conditional cohort scenarios, not buyers/market size, actual savings or willingness to pay. Demonstrated commercial floor is zero.

Source: `docs/development/challenge_pipeline/discovery/dossiers/solenoid-pole.md` sha256 `8ab318c38c01bdc460afa213fdbf8f6b7b679deb946ae034bc92ffe40e524bc6`.
Owner: science/product owner. Needed: Confirm applicability and authorize wrong_decision.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### exclusions — HUMAN_INPUT

HUMAN_INPUT: no value supplied.

Owner: science/product owner. Needed: Confirm applicability and authorize exclusions.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 2. Physical system

### physics — HUMAN_INPUT

Axisymmetric nonlinear DC magnetostatics and winding resistance; no dynamic or thermal qualification

Owner: science/product owner. Needed: Confirm applicability and authorize physics.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### geometry — SOURCE_EXTRACT

Axisymmetric ferromagnetic pole/armature/yoke, prescribed winding and quasi-static DC excitation. Nonlinear B-H behaviour and fringing are relevant. Fix winding topology, material family and the allowed geometric parameterisation before collection. Magnetostatic force and stated-temperature resistive loss are the proposed screen; magnetic hysteresis, eddy currents, thermal transients and duty-cycle overheating remain outside the claimed model unless the buyer requires them, in which case this scope must be rejected or repriced.

Mandatory-stratum hypothesis (count [3,3,3]):

- customer-approved nominal operating state: numerical endpoints, joint conditions and source HUMAN_INPUT.
- customer-approved hot/material-variation operating state: numerical endpoints, joint conditions and source HUMAN_INPUT.
- customer-approved worst allowed assembly/gap state: numerical endpoints, joint conditions and source HUMAN_INPUT.

Scientific owner must confirm that these strata cover the unchanged customer job. Initial/boundary conditions, histories, idealisations, material applicability, neglected physics and manufacture/assembly tolerances are HUMAN_INPUT. A missing safety/material requirement stops the affected job; it is never relaxed to save compute. No physical population claim follows from deterministic execution.

Source: `docs/development/challenge_pipeline/discovery/dossiers/solenoid-pole.md` sha256 `8ab318c38c01bdc460afa213fdbf8f6b7b679deb946ae034bc92ffe40e524bc6`.
Owner: science/product owner. Needed: Confirm applicability and authorize geometry.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### materials — SOURCE_EXTRACT

Axisymmetric ferromagnetic pole/armature/yoke, prescribed winding and quasi-static DC excitation. Nonlinear B-H behaviour and fringing are relevant. Fix winding topology, material family and the allowed geometric parameterisation before collection. Magnetostatic force and stated-temperature resistive loss are the proposed screen; magnetic hysteresis, eddy currents, thermal transients and duty-cycle overheating remain outside the claimed model unless the buyer requires them, in which case this scope must be rejected or repriced.

Mandatory-stratum hypothesis (count [3,3,3]):

- customer-approved nominal operating state: numerical endpoints, joint conditions and source HUMAN_INPUT.
- customer-approved hot/material-variation operating state: numerical endpoints, joint conditions and source HUMAN_INPUT.
- customer-approved worst allowed assembly/gap state: numerical endpoints, joint conditions and source HUMAN_INPUT.

Scientific owner must confirm that these strata cover the unchanged customer job. Initial/boundary conditions, histories, idealisations, material applicability, neglected physics and manufacture/assembly tolerances are HUMAN_INPUT. A missing safety/material requirement stops the affected job; it is never relaxed to save compute. No physical population claim follows from deterministic execution.

Source: `docs/development/challenge_pipeline/discovery/dossiers/solenoid-pole.md` sha256 `8ab318c38c01bdc460afa213fdbf8f6b7b679deb946ae034bc92ffe40e524bc6`.
Owner: science/product owner. Needed: Confirm applicability and authorize materials.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### conditions — SOURCE_EXTRACT

Axisymmetric ferromagnetic pole/armature/yoke, prescribed winding and quasi-static DC excitation. Nonlinear B-H behaviour and fringing are relevant. Fix winding topology, material family and the allowed geometric parameterisation before collection. Magnetostatic force and stated-temperature resistive loss are the proposed screen; magnetic hysteresis, eddy currents, thermal transients and duty-cycle overheating remain outside the claimed model unless the buyer requires them, in which case this scope must be rejected or repriced.

Mandatory-stratum hypothesis (count [3,3,3]):

- customer-approved nominal operating state: numerical endpoints, joint conditions and source HUMAN_INPUT.
- customer-approved hot/material-variation operating state: numerical endpoints, joint conditions and source HUMAN_INPUT.
- customer-approved worst allowed assembly/gap state: numerical endpoints, joint conditions and source HUMAN_INPUT.

Scientific owner must confirm that these strata cover the unchanged customer job. Initial/boundary conditions, histories, idealisations, material applicability, neglected physics and manufacture/assembly tolerances are HUMAN_INPUT. A missing safety/material requirement stops the affected job; it is never relaxed to save compute. No physical population claim follows from deterministic execution.

Source: `docs/development/challenge_pipeline/discovery/dossiers/solenoid-pole.md` sha256 `8ab318c38c01bdc460afa213fdbf8f6b7b679deb946ae034bc92ffe40e524bc6`.
Owner: science/product owner. Needed: Confirm applicability and authorize conditions.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### omissions — HUMAN_INPUT

HUMAN_INPUT: no value supplied.

Owner: science/product owner. Needed: Confirm applicability and authorize omissions.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 3. Population P, Q and w

### P — SOURCE_EXTRACT

**P — customer request population.** Joint customer distribution over rated force-envelope jobs, packaging, winding/current permissions, material lots and operating temperatures. Actual job frequencies, covariance and eligibility are HUMAN_INPUT; neither uniform gap sampling nor manufacturer catalogue frequency is P.

**Q — diagnostic/acquisition proposal.** Enrich pole/air-gap designs near approved force and saturation boundaries, including the baseline's most confident disagreements. Q preserves the eligible geometric/material domain and records proposal densities or strata membership. Synthetic enrichment is not evidence of customer prevalence.

**w — evidence/score use.** Sampling/evidence weighting and any correction from Q to P are **HUMAN_INPUT — scientific owner**. Prospective per-stratum admissibility and reporting precede any ranking. Equal diagnostic counts are a collection convenience, not deployment weights. No soft objective can compensate for a mandatory failure.

Freeze a versioned population contract with joint variables, support, dependencies, strata/mixture probabilities, rights, exclusions, time validity and applicability. Keep request-job law distinct from the finite design menu conditional on that job. Request population and design-generation process are not interchangeable. No public draw is a hidden/protected exam draw; this researcher defines or accesses neither.

Source: `docs/development/challenge_pipeline/discovery/dossiers/solenoid-pole.md` sha256 `8ab318c38c01bdc460afa213fdbf8f6b7b679deb946ae034bc92ffe40e524bc6`.
Owner: science/product owner. Needed: Confirm applicability and authorize P.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### Q — SOURCE_EXTRACT

**P — customer request population.** Joint customer distribution over rated force-envelope jobs, packaging, winding/current permissions, material lots and operating temperatures. Actual job frequencies, covariance and eligibility are HUMAN_INPUT; neither uniform gap sampling nor manufacturer catalogue frequency is P.

**Q — diagnostic/acquisition proposal.** Enrich pole/air-gap designs near approved force and saturation boundaries, including the baseline's most confident disagreements. Q preserves the eligible geometric/material domain and records proposal densities or strata membership. Synthetic enrichment is not evidence of customer prevalence.

**w — evidence/score use.** Sampling/evidence weighting and any correction from Q to P are **HUMAN_INPUT — scientific owner**. Prospective per-stratum admissibility and reporting precede any ranking. Equal diagnostic counts are a collection convenience, not deployment weights. No soft objective can compensate for a mandatory failure.

Freeze a versioned population contract with joint variables, support, dependencies, strata/mixture probabilities, rights, exclusions, time validity and applicability. Keep request-job law distinct from the finite design menu conditional on that job. Request population and design-generation process are not interchangeable. No public draw is a hidden/protected exam draw; this researcher defines or accesses neither.

Source: `docs/development/challenge_pipeline/discovery/dossiers/solenoid-pole.md` sha256 `8ab318c38c01bdc460afa213fdbf8f6b7b679deb946ae034bc92ffe40e524bc6`.
Owner: science/product owner. Needed: Confirm applicability and authorize Q.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### w — SOURCE_EXTRACT

**P — customer request population.** Joint customer distribution over rated force-envelope jobs, packaging, winding/current permissions, material lots and operating temperatures. Actual job frequencies, covariance and eligibility are HUMAN_INPUT; neither uniform gap sampling nor manufacturer catalogue frequency is P.

**Q — diagnostic/acquisition proposal.** Enrich pole/air-gap designs near approved force and saturation boundaries, including the baseline's most confident disagreements. Q preserves the eligible geometric/material domain and records proposal densities or strata membership. Synthetic enrichment is not evidence of customer prevalence.

**w — evidence/score use.** Sampling/evidence weighting and any correction from Q to P are **HUMAN_INPUT — scientific owner**. Prospective per-stratum admissibility and reporting precede any ranking. Equal diagnostic counts are a collection convenience, not deployment weights. No soft objective can compensate for a mandatory failure.

Freeze a versioned population contract with joint variables, support, dependencies, strata/mixture probabilities, rights, exclusions, time validity and applicability. Keep request-job law distinct from the finite design menu conditional on that job. Request population and design-generation process are not interchangeable. No public draw is a hidden/protected exam draw; this researcher defines or accesses neither.

Source: `docs/development/challenge_pipeline/discovery/dossiers/solenoid-pole.md` sha256 `8ab318c38c01bdc460afa213fdbf8f6b7b679deb946ae034bc92ffe40e524bc6`.
Owner: science/product owner. Needed: Confirm applicability and authorize w.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### strata — SOURCE_EXTRACT

**P — customer request population.** Joint customer distribution over rated force-envelope jobs, packaging, winding/current permissions, material lots and operating temperatures. Actual job frequencies, covariance and eligibility are HUMAN_INPUT; neither uniform gap sampling nor manufacturer catalogue frequency is P.

**Q — diagnostic/acquisition proposal.** Enrich pole/air-gap designs near approved force and saturation boundaries, including the baseline's most confident disagreements. Q preserves the eligible geometric/material domain and records proposal densities or strata membership. Synthetic enrichment is not evidence of customer prevalence.

**w — evidence/score use.** Sampling/evidence weighting and any correction from Q to P are **HUMAN_INPUT — scientific owner**. Prospective per-stratum admissibility and reporting precede any ranking. Equal diagnostic counts are a collection convenience, not deployment weights. No soft objective can compensate for a mandatory failure.

Freeze a versioned population contract with joint variables, support, dependencies, strata/mixture probabilities, rights, exclusions, time validity and applicability. Keep request-job law distinct from the finite design menu conditional on that job. Request population and design-generation process are not interchangeable. No public draw is a hidden/protected exam draw; this researcher defines or accesses neither.

Source: `docs/development/challenge_pipeline/discovery/dossiers/solenoid-pole.md` sha256 `8ab318c38c01bdc460afa213fdbf8f6b7b679deb946ae034bc92ffe40e524bc6`.
Owner: science/product owner. Needed: Confirm applicability and authorize strata.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### independent_unit — HUMAN_INPUT

HUMAN_INPUT: no value supplied.

Owner: science/product owner. Needed: Confirm applicability and authorize independent_unit.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 4. Case contract

### case_identity — SOURCE_EXTRACT

Pole/yoke/armature dimensions and axisymmetric geometry checks; approved winding turns/resistance and copper reference temperature; owned B-H tables with temperature applicability; current/stroke schedule; packaging envelope; customer force lower/upper bounds; permitted power/current limits. All numerical values, units/version sources and uncertainty allowances are HUMAN_INPUT.

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

Source: `docs/development/challenge_pipeline/discovery/dossiers/solenoid-pole.md` sha256 `8ab318c38c01bdc460afa213fdbf8f6b7b679deb946ae034bc92ffe40e524bc6`.
Owner: science/product owner. Needed: Confirm applicability and authorize case_identity.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### validity — HUMAN_INPUT

HUMAN_INPUT: no value supplied.

Owner: science/product owner. Needed: Confirm applicability and authorize validity.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### disclosure — SOURCE_EXTRACT

Pole/yoke/armature dimensions and axisymmetric geometry checks; approved winding turns/resistance and copper reference temperature; owned B-H tables with temperature applicability; current/stroke schedule; packaging envelope; customer force lower/upper bounds; permitted power/current limits. All numerical values, units/version sources and uncertainty allowances are HUMAN_INPUT.

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

Source: `docs/development/challenge_pipeline/discovery/dossiers/solenoid-pole.md` sha256 `8ab318c38c01bdc460afa213fdbf8f6b7b679deb946ae034bc92ffe40e524bc6`.
Owner: science/product owner. Needed: Confirm applicability and authorize disclosure.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 5. Reference policy

### solver — SOURCE_EXTRACT

GetDP plus an approved nonlinear axisymmetric magnetic formulation. Validate Maxwell-stress/virtual-work consistency and mesh/refinement sensitivity against an independently owned buyer magnetic FE model. Saturation curve provenance, numerical tolerances, convergence policy, units and force extraction are HUMAN_INPUT. Zero-field/symmetry and energy checks are diagnostics, not a proof of physical adequacy.

Open route: [GETDP: GetDP authors](https://getdp.info/). Pin reviewed open licence/dependencies, source revision, container digest, compiler/math environment, meshing/solver/deck/material versions and extraction definition. None is supplied here as a fake immutable pin. Reproducibility within documented tolerances is necessary; physical adequacy is separate.

Credibility **earned: NOT_DEMONSTRATED**; target: framework Tier 2 via an applicable independent buyer tool. Tier 3 would require applicable physical experiments and their own rights/budget/acceptance; it is not priced or earned by this report. A successful balance or cross-tool check is evidence for an owner, not qualification itself.

Infrastructure failures preserve FAILED_INFRA/retry/non-scientific semantics. Nonconvergence, inappropriate constitutive law, extraction ambiguity or failed physical balance are reference inadequacy/UNRESOLVED and never candidate scientific failure. Stop grading until the affected reference is adequate. Tolerances, uncertainty bands, convergence thresholds and credibility acceptance are **HUMAN_INPUT — reference/science owners**.

Source: `docs/development/challenge_pipeline/discovery/dossiers/solenoid-pole.md` sha256 `8ab318c38c01bdc460afa213fdbf8f6b7b679deb946ae034bc92ffe40e524bc6`.
Owner: science/product owner. Needed: Confirm applicability and authorize solver.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### pins — SOURCE_EXTRACT

GetDP plus an approved nonlinear axisymmetric magnetic formulation. Validate Maxwell-stress/virtual-work consistency and mesh/refinement sensitivity against an independently owned buyer magnetic FE model. Saturation curve provenance, numerical tolerances, convergence policy, units and force extraction are HUMAN_INPUT. Zero-field/symmetry and energy checks are diagnostics, not a proof of physical adequacy.

Open route: [GETDP: GetDP authors](https://getdp.info/). Pin reviewed open licence/dependencies, source revision, container digest, compiler/math environment, meshing/solver/deck/material versions and extraction definition. None is supplied here as a fake immutable pin. Reproducibility within documented tolerances is necessary; physical adequacy is separate.

Credibility **earned: NOT_DEMONSTRATED**; target: framework Tier 2 via an applicable independent buyer tool. Tier 3 would require applicable physical experiments and their own rights/budget/acceptance; it is not priced or earned by this report. A successful balance or cross-tool check is evidence for an owner, not qualification itself.

Infrastructure failures preserve FAILED_INFRA/retry/non-scientific semantics. Nonconvergence, inappropriate constitutive law, extraction ambiguity or failed physical balance are reference inadequacy/UNRESOLVED and never candidate scientific failure. Stop grading until the affected reference is adequate. Tolerances, uncertainty bands, convergence thresholds and credibility acceptance are **HUMAN_INPUT — reference/science owners**.

Source: `docs/development/challenge_pipeline/discovery/dossiers/solenoid-pole.md` sha256 `8ab318c38c01bdc460afa213fdbf8f6b7b679deb946ae034bc92ffe40e524bc6`.
Owner: science/product owner. Needed: Confirm applicability and authorize pins.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### refinement — SOURCE_EXTRACT

GetDP plus an approved nonlinear axisymmetric magnetic formulation. Validate Maxwell-stress/virtual-work consistency and mesh/refinement sensitivity against an independently owned buyer magnetic FE model. Saturation curve provenance, numerical tolerances, convergence policy, units and force extraction are HUMAN_INPUT. Zero-field/symmetry and energy checks are diagnostics, not a proof of physical adequacy.

Open route: [GETDP: GetDP authors](https://getdp.info/). Pin reviewed open licence/dependencies, source revision, container digest, compiler/math environment, meshing/solver/deck/material versions and extraction definition. None is supplied here as a fake immutable pin. Reproducibility within documented tolerances is necessary; physical adequacy is separate.

Credibility **earned: NOT_DEMONSTRATED**; target: framework Tier 2 via an applicable independent buyer tool. Tier 3 would require applicable physical experiments and their own rights/budget/acceptance; it is not priced or earned by this report. A successful balance or cross-tool check is evidence for an owner, not qualification itself.

Infrastructure failures preserve FAILED_INFRA/retry/non-scientific semantics. Nonconvergence, inappropriate constitutive law, extraction ambiguity or failed physical balance are reference inadequacy/UNRESOLVED and never candidate scientific failure. Stop grading until the affected reference is adequate. Tolerances, uncertainty bands, convergence thresholds and credibility acceptance are **HUMAN_INPUT — reference/science owners**.

Source: `docs/development/challenge_pipeline/discovery/dossiers/solenoid-pole.md` sha256 `8ab318c38c01bdc460afa213fdbf8f6b7b679deb946ae034bc92ffe40e524bc6`.
Owner: science/product owner. Needed: Confirm applicability and authorize refinement.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### uncertainty — SOURCE_EXTRACT

GetDP plus an approved nonlinear axisymmetric magnetic formulation. Validate Maxwell-stress/virtual-work consistency and mesh/refinement sensitivity against an independently owned buyer magnetic FE model. Saturation curve provenance, numerical tolerances, convergence policy, units and force extraction are HUMAN_INPUT. Zero-field/symmetry and energy checks are diagnostics, not a proof of physical adequacy.

Open route: [GETDP: GetDP authors](https://getdp.info/). Pin reviewed open licence/dependencies, source revision, container digest, compiler/math environment, meshing/solver/deck/material versions and extraction definition. None is supplied here as a fake immutable pin. Reproducibility within documented tolerances is necessary; physical adequacy is separate.

Credibility **earned: NOT_DEMONSTRATED**; target: framework Tier 2 via an applicable independent buyer tool. Tier 3 would require applicable physical experiments and their own rights/budget/acceptance; it is not priced or earned by this report. A successful balance or cross-tool check is evidence for an owner, not qualification itself.

Infrastructure failures preserve FAILED_INFRA/retry/non-scientific semantics. Nonconvergence, inappropriate constitutive law, extraction ambiguity or failed physical balance are reference inadequacy/UNRESOLVED and never candidate scientific failure. Stop grading until the affected reference is adequate. Tolerances, uncertainty bands, convergence thresholds and credibility acceptance are **HUMAN_INPUT — reference/science owners**.

Source: `docs/development/challenge_pipeline/discovery/dossiers/solenoid-pole.md` sha256 `8ab318c38c01bdc460afa213fdbf8f6b7b679deb946ae034bc92ffe40e524bc6`.
Owner: science/product owner. Needed: Confirm applicability and authorize uncertainty.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### cost — SOURCE_EXTRACT

GetDP plus an approved nonlinear axisymmetric magnetic formulation. Validate Maxwell-stress/virtual-work consistency and mesh/refinement sensitivity against an independently owned buyer magnetic FE model. Saturation curve provenance, numerical tolerances, convergence policy, units and force extraction are HUMAN_INPUT. Zero-field/symmetry and energy checks are diagnostics, not a proof of physical adequacy.

Open route: [GETDP: GetDP authors](https://getdp.info/). Pin reviewed open licence/dependencies, source revision, container digest, compiler/math environment, meshing/solver/deck/material versions and extraction definition. None is supplied here as a fake immutable pin. Reproducibility within documented tolerances is necessary; physical adequacy is separate.

Credibility **earned: NOT_DEMONSTRATED**; target: framework Tier 2 via an applicable independent buyer tool. Tier 3 would require applicable physical experiments and their own rights/budget/acceptance; it is not priced or earned by this report. A successful balance or cross-tool check is evidence for an owner, not qualification itself.

Infrastructure failures preserve FAILED_INFRA/retry/non-scientific semantics. Nonconvergence, inappropriate constitutive law, extraction ambiguity or failed physical balance are reference inadequacy/UNRESOLVED and never candidate scientific failure. Stop grading until the affected reference is adequate. Tolerances, uncertainty bands, convergence thresholds and credibility acceptance are **HUMAN_INPUT — reference/science owners**.

Source: `docs/development/challenge_pipeline/discovery/dossiers/solenoid-pole.md` sha256 `8ab318c38c01bdc460afa213fdbf8f6b7b679deb946ae034bc92ffe40e524bc6`.
Owner: science/product owner. Needed: Confirm applicability and authorize cost.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 6. Output and measurement contract

### outputs — SOURCE_EXTRACT

Force at every registered stroke/current point, inductance/flux diagnostics and winding resistive power at the stated temperature. Each complete C1 unit is the #921 hypothesis of nine stroke positions by three currents ([9,9,9] and [3,3,3] illustrative fixed panel counts), not one field evaluation. Freeze these positions, all mandatory conditions and force/extraction conventions before admission.

Hard-limit family: Force-envelope compliance across all points; packaging; current/power at the stated condition; material/flux applicability. Limits must come from the customer and reference owner (SOL3 explains condition-dependent ratings). A temperature constraint cannot be silently satisfied by excluding heating; if required by the job, supply an adequate coupled model or reject.

Freeze each quantity's units, sample locations, aggregation, sign convention, mask, extrema treatment, applicability and reference uncertainty. Register output field/array shape and the decision projection prospectively. The same definitions and limits apply to reference, strongest cheap baseline and model. Measurement definition, qualification, applicability and score use are distinct approvals.

Admissibility must be established for **every required output in every mandatory stratum** before the customer's objective can rank actions. Near-infeasible means outside a prospectively approved uncertainty/refinement band for a specified hard limit while other mandatory conditions are respected; ambiguous reference signs remain UNRESOLVED. No new scalar score, scientific tolerance, safety factor or loss-based exemption is authorised. Customer objective: Customer preference among force-compliant geometries, such as material/size or envelope fit, is HUMAN_INPUT. No arbitrary force-weighted scalar is proposed.

Source: `docs/development/challenge_pipeline/discovery/dossiers/solenoid-pole.md` sha256 `8ab318c38c01bdc460afa213fdbf8f6b7b679deb946ae034bc92ffe40e524bc6`.
Owner: science/product owner. Needed: Confirm applicability and authorize outputs.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### hard_limits — SOURCE_EXTRACT

Force at every registered stroke/current point, inductance/flux diagnostics and winding resistive power at the stated temperature. Each complete C1 unit is the #921 hypothesis of nine stroke positions by three currents ([9,9,9] and [3,3,3] illustrative fixed panel counts), not one field evaluation. Freeze these positions, all mandatory conditions and force/extraction conventions before admission.

Hard-limit family: Force-envelope compliance across all points; packaging; current/power at the stated condition; material/flux applicability. Limits must come from the customer and reference owner (SOL3 explains condition-dependent ratings). A temperature constraint cannot be silently satisfied by excluding heating; if required by the job, supply an adequate coupled model or reject.

Freeze each quantity's units, sample locations, aggregation, sign convention, mask, extrema treatment, applicability and reference uncertainty. Register output field/array shape and the decision projection prospectively. The same definitions and limits apply to reference, strongest cheap baseline and model. Measurement definition, qualification, applicability and score use are distinct approvals.

Admissibility must be established for **every required output in every mandatory stratum** before the customer's objective can rank actions. Near-infeasible means outside a prospectively approved uncertainty/refinement band for a specified hard limit while other mandatory conditions are respected; ambiguous reference signs remain UNRESOLVED. No new scalar score, scientific tolerance, safety factor or loss-based exemption is authorised. Customer objective: Customer preference among force-compliant geometries, such as material/size or envelope fit, is HUMAN_INPUT. No arbitrary force-weighted scalar is proposed.

Source: `docs/development/challenge_pipeline/discovery/dossiers/solenoid-pole.md` sha256 `8ab318c38c01bdc460afa213fdbf8f6b7b679deb946ae034bc92ffe40e524bc6`.
Owner: science/product owner. Needed: Confirm applicability and authorize hard_limits.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### objective — SOURCE_EXTRACT

Force at every registered stroke/current point, inductance/flux diagnostics and winding resistive power at the stated temperature. Each complete C1 unit is the #921 hypothesis of nine stroke positions by three currents ([9,9,9] and [3,3,3] illustrative fixed panel counts), not one field evaluation. Freeze these positions, all mandatory conditions and force/extraction conventions before admission.

Hard-limit family: Force-envelope compliance across all points; packaging; current/power at the stated condition; material/flux applicability. Limits must come from the customer and reference owner (SOL3 explains condition-dependent ratings). A temperature constraint cannot be silently satisfied by excluding heating; if required by the job, supply an adequate coupled model or reject.

Freeze each quantity's units, sample locations, aggregation, sign convention, mask, extrema treatment, applicability and reference uncertainty. Register output field/array shape and the decision projection prospectively. The same definitions and limits apply to reference, strongest cheap baseline and model. Measurement definition, qualification, applicability and score use are distinct approvals.

Admissibility must be established for **every required output in every mandatory stratum** before the customer's objective can rank actions. Near-infeasible means outside a prospectively approved uncertainty/refinement band for a specified hard limit while other mandatory conditions are respected; ambiguous reference signs remain UNRESOLVED. No new scalar score, scientific tolerance, safety factor or loss-based exemption is authorised. Customer objective: Customer preference among force-compliant geometries, such as material/size or envelope fit, is HUMAN_INPUT. No arbitrary force-weighted scalar is proposed.

Source: `docs/development/challenge_pipeline/discovery/dossiers/solenoid-pole.md` sha256 `8ab318c38c01bdc460afa213fdbf8f6b7b679deb946ae034bc92ffe40e524bc6`.
Owner: science/product owner. Needed: Confirm applicability and authorize objective.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 7. Construction contract

### vocabulary — SOURCE_EXTRACT

Research a fast model predicting the frozen physical outputs/decision projection from allowed geometry, condition and material inputs. The current bounded Carbon search surface is neural-operator **TrainingStrategy**, subject to its current contracts. This draft does not widen it to arbitrary solver/code execution or a future ModelConstructionStrategy.

Parameterised geometry generation, meshing, reference runs and official grading remain owner-controlled. Learners can use only authorised public research examples/features under reviewed licences; exact permitted inputs, architecture/dependency/compute bounds, training split and geometry-to-fixed-output representation are **HUMAN_INPUT — construction/security owners**. No private samples, hidden seeds or reference authority are provided to participants. Any prototype stays developmental and structurally unable to emit LIVE ranking/frontier/treasury/product authority.

Strong baseline: **nonlinear reluctance circuit with fringing calibration, interpolation of an existing manufacturer force map, and a contact-free magnetic FE response surface**. Incremental-value hypothesis: nonlinear saturation and fringing can shift force margins between pole profiles. Show that this changes the same admissible choice; an adequate cached force map ends the proposal. Complete acquisition/build/fit/search/verification and retained high-fidelity calls must be counted for both alternatives. A good imitation of an inadequate reference is not a useful model.

Source: `docs/development/challenge_pipeline/discovery/dossiers/solenoid-pole.md` sha256 `8ab318c38c01bdc460afa213fdbf8f6b7b679deb946ae034bc92ffe40e524bc6`.
Owner: science/product owner. Needed: Confirm applicability and authorize vocabulary.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### training — HUMAN_INPUT

HUMAN_INPUT: no value supplied.

Owner: science/product owner. Needed: Confirm applicability and authorize training.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### permissions — SOURCE_EXTRACT

Research a fast model predicting the frozen physical outputs/decision projection from allowed geometry, condition and material inputs. The current bounded Carbon search surface is neural-operator **TrainingStrategy**, subject to its current contracts. This draft does not widen it to arbitrary solver/code execution or a future ModelConstructionStrategy.

Parameterised geometry generation, meshing, reference runs and official grading remain owner-controlled. Learners can use only authorised public research examples/features under reviewed licences; exact permitted inputs, architecture/dependency/compute bounds, training split and geometry-to-fixed-output representation are **HUMAN_INPUT — construction/security owners**. No private samples, hidden seeds or reference authority are provided to participants. Any prototype stays developmental and structurally unable to emit LIVE ranking/frontier/treasury/product authority.

Strong baseline: **nonlinear reluctance circuit with fringing calibration, interpolation of an existing manufacturer force map, and a contact-free magnetic FE response surface**. Incremental-value hypothesis: nonlinear saturation and fringing can shift force margins between pole profiles. Show that this changes the same admissible choice; an adequate cached force map ends the proposal. Complete acquisition/build/fit/search/verification and retained high-fidelity calls must be counted for both alternatives. A good imitation of an inadequate reference is not a useful model.

Source: `docs/development/challenge_pipeline/discovery/dossiers/solenoid-pole.md` sha256 `8ab318c38c01bdc460afa213fdbf8f6b7b679deb946ae034bc92ffe40e524bc6`.
Owner: construction/security owner. Needed: Confirm applicability and authorize permissions.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 8. Research kit

### public_kit — SOURCE_EXTRACT

Proposed public kit only: source-linked solver documentation, independently licensed geometry/material examples, canonical explanatory schema, output/measurement definitions, baseline specification, openly generated diagnostic cases and failure-report format. Release actual files only after owner rights/applicability review. It contains no official bank, private metadata, seeds, protected samples, reversible draw identities or AX42 material.

Training/support/domain claims require separate authorisation. Include both cheap-baseline and reference costs, convergence diagnostics and known limitations in public research reports where disclosure allows. A practice kit remains incomplete and cannot substitute for the independent exam. No kit is built or solver installed by this researcher.

Source: `docs/development/challenge_pipeline/discovery/dossiers/solenoid-pole.md` sha256 `8ab318c38c01bdc460afa213fdbf8f6b7b679deb946ae034bc92ffe40e524bc6`.
Owner: science/product owner. Needed: Confirm applicability and authorize public_kit.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### baseline — SOURCE_EXTRACT

Proposed public kit only: source-linked solver documentation, independently licensed geometry/material examples, canonical explanatory schema, output/measurement definitions, baseline specification, openly generated diagnostic cases and failure-report format. Release actual files only after owner rights/applicability review. It contains no official bank, private metadata, seeds, protected samples, reversible draw identities or AX42 material.

Training/support/domain claims require separate authorisation. Include both cheap-baseline and reference costs, convergence diagnostics and known limitations in public research reports where disclosure allows. A practice kit remains incomplete and cannot substitute for the independent exam. No kit is built or solver installed by this researcher.

Source: `docs/development/challenge_pipeline/discovery/dossiers/solenoid-pole.md` sha256 `8ab318c38c01bdc460afa213fdbf8f6b7b679deb946ae034bc92ffe40e524bc6`.
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

Full-bank hypothesis: designs [24,24,24], strata [3,3,3], primary cases [72,72,72], refined cases [24,24,24] at multiplier [2,2,2], charged failed attempts [15,15,15], independent witness pairs [8,8,8] with two tools each. Total equivalent complete cases U=[151,151,151]. This draft budget is not proof that the menu has the required feasible/near-infeasible counts.

C1 complete-case CPU-hours **0.01 / 0.04 / 0.12**, RAM GiB **0.50 / 2.00 / 6.00**; p50/p95 and elapsed/CPU ratio are NOT_MEASURED. Charged startup C2 **EUR 18.98 / 26.37 / 46.06**, under the [common formula](../methodology.md). All estimates are ASSUMPTION. Witness licence assumption is zero incremental charge only if the buyer has rights/access; otherwise reprice and reject if the cap fails. No spend is authorised.

V4 compares analytical/library, interpolation, calibrated response surface, reduced physics and actual buyer tool at matched admissibility, with complete overhead and retained verification over M=[1,10,100] served revisions (ASSUMPTION sensitivity). Acceptable false-feasible rate, regret/decision agreement and economic threshold are HUMAN_INPUT. An equal cheap decision, infeasible stratum or unqualified reference stops admission. The discovery estimate screen fits EUR100, but an actual bill above the cap stops the proposed bank.

Source: `docs/development/challenge_pipeline/discovery/dossiers/solenoid-pole.md` sha256 `8ab318c38c01bdc460afa213fdbf8f6b7b679deb946ae034bc92ffe40e524bc6`.
Owner: science/product owner. Needed: Confirm applicability and authorize panel.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### controls — SOURCE_EXTRACT

Before any new collection: get a real customer job with unchanged sourced limits and rights; confirm the open route exactly produces the needed outputs; check independent reference applicability and the buyer's actual current latency; and obtain the baseline's cheapest complete decisions. Source-first work may reject the candidate without a solve.

Then a separately authorised Data Collection task can run the panel below. It must demonstrate refined feasible witnesses and prospective contested counts per stratum before a full bank. Qualification owners choose tolerances, T3 power, alpha, effect severity, question law and reference acceptance. These are HUMAN_INPUT, not selected from cheap runtimes.

Full-bank hypothesis: designs [24,24,24], strata [3,3,3], primary cases [72,72,72], refined cases [24,24,24] at multiplier [2,2,2], charged failed attempts [15,15,15], independent witness pairs [8,8,8] with two tools each. Total equivalent complete cases U=[151,151,151]. This draft budget is not proof that the menu has the required feasible/near-infeasible counts.

C1 complete-case CPU-hours **0.01 / 0.04 / 0.12**, RAM GiB **0.50 / 2.00 / 6.00**; p50/p95 and elapsed/CPU ratio are NOT_MEASURED. Charged startup C2 **EUR 18.98 / 26.37 / 46.06**, under the [common formula](../methodology.md). All estimates are ASSUMPTION. Witness licence assumption is zero incremental charge only if the buyer has rights/access; otherwise reprice and reject if the cap fails. No spend is authorised.

V4 compares analytical/library, interpolation, calibrated response surface, reduced physics and actual buyer tool at matched admissibility, with complete overhead and retained verification over M=[1,10,100] served revisions (ASSUMPTION sensitivity). Acceptable false-feasible rate, regret/decision agreement and economic threshold are HUMAN_INPUT. An equal cheap decision, infeasible stratum or unqualified reference stops admission. The discovery estimate screen fits EUR100, but an actual bill above the cap stops the proposed bank.

Source: `docs/development/challenge_pipeline/discovery/dossiers/solenoid-pole.md` sha256 `8ab318c38c01bdc460afa213fdbf8f6b7b679deb946ae034bc92ffe40e524bc6`.
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

Source: `docs/development/challenge_pipeline/discovery/dossiers/solenoid-pole.md` sha256 `8ab318c38c01bdc460afa213fdbf8f6b7b679deb946ae034bc92ffe40e524bc6`.
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

Source: `docs/development/challenge_pipeline/discovery/dossiers/solenoid-pole.md` sha256 `8ab318c38c01bdc460afa213fdbf8f6b7b679deb946ae034bc92ffe40e524bc6`.
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

Source: `docs/development/challenge_pipeline/discovery/dossiers/solenoid-pole.md` sha256 `8ab318c38c01bdc460afa213fdbf8f6b7b679deb946ae034bc92ffe40e524bc6`.
Owner: science/product owner. Needed: Confirm applicability and authorize next_gate.
Held closed: No runtime registration, bank draw, execution, qualification or spend.
