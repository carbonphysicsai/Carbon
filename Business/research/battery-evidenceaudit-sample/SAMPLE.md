# Battery EvidenceAudit — DEVELOPMENT SAMPLE

**No qualification claim. Eligible tier: UNESTABLISHED.** Filled using #956's frozen template; evidence cut-off is the committed baseline below. Numeric measurements are **SOURCED**: a reported point uses low = base = high = that recorded value, not a confidence range. Reported intervals retain their source method and confidence level separately. The [quantity ledger](evidence.json) makes that convention explicit. Version, date, section and source identifiers are metadata. There are no new scientific or price estimates.

| Header | Filled value |
| --- | --- |
| Deliverable ID / version | BATTERY-EVIDENCEAUDIT-SAMPLE-01 / development draft |
| Challenge / contracts | `battery-fastcharge-ageing-development-v1`; EV4 decision contract v1; historical `control-exam-v1`, run-5 v2 and prospective v3 kept distinct |
| Intended / eligible tier | EvidenceAudit / **UNESTABLISHED** |
| Buyer role / intended decision | Battery-management and cell engineers selecting a charge protocol; a buyer hypothesis in R1, not an identified customer |
| Exact deployable artifact / runtime | **HUMAN_INPUT**; this document reviews public panels, not one product candidate |
| Public source snapshot | `915225242146be67e6de098d4a08324cc63dc684` |
| Audience / rights | Public development evidence only; customer reuse rights/authority HUMAN_INPUT |
| Standard profile | NASA-STD-7009B, March 2024; tailoring and acceptance authority HUMAN_INPUT |
| Qualification record | None reviewed; **HUMAN_INPUT** |
| Adverse review | FINDINGS_RETAINED; EV4/EV5/Q1 public findings included; protected evidence uninspected |

Source IDs R1–R7 below resolve to exact files, revisions, blob identities and locators in [evidence.json](evidence.json).

## D01 Intended use and decision

Coverage: **PARTIAL**. Automation: manual.

The proposed job is to choose a two-stage constant-current protocol using predicted time to CV onset, temperature and plating margin. Its intended use is prediction of a specified PyBaMM DFN/OKane2022 reference, rather than real-cell qualification. ABSTAIN is a valid decision when no predicted-feasible design exists. EV4 Problem C demonstrated this workflow with model and reference disagreement explicitly reported. [R1 readiness](https://github.com/carbonphysicsai/Carbon/blob/915225242146be67e6de098d4a08324cc63dc684/carbon/challenge_readiness/records/battery-fastcharge-ageing-development-v1.v3.json), [R2 EV4 §§6,12](https://github.com/carbonphysicsai/Carbon/blob/915225242146be67e6de098d4a08324cc63dc684/docs/development/BATTERY_ENGINEERING_VALUE_EV4.md).

Gaps: named customer, actual product workflow/decision authority, consequences and costs of error, cooling-map decision evidence, appropriate-use acceptance. No demand, annual volume or willingness-to-pay is demonstrated by these records.

## D02 Requirements

Coverage: **PARTIAL**. Automation: manual.

| Requirement | Measurement / criterion in development | Evidence and outcome | Missing authority |
| --- | --- | --- | --- |
| Reach CV in window | Time to first terminal-voltage crossing above 4.19 V within 3600 s; interpolation on the recorded grid | Defined in R3; unreachable objectives remain undefined | Customer-approved target and measurement |
| No plating onset | Cycle-one minimum plating margin ≥ 0 V | R3; false-feasible selections recorded by R2/R4 | Real-cell applicability and approved margin |
| Temperature | Peak volume-averaged temperature ≤ 45 °C over the first hour | R3; finite development constraint, not an automotive safety limit | Physical uncertainty and buyer-specific limit |
| Mandatory admission | Gate failure must rank last and cannot be compensated | R6 gate specification; historical experiments are not proof of customer admission | Qualified exam and exact product gate evidence |

The EV4 contract explicitly calls its preferences **provisional DEVELOPMENT**, not customer declared or commercially qualified. The earlier readiness record's proposed important-region temperature is a different quantity; it must not replace EV4's decision limit. R6 describes the adopted v3 false-feasible cutoff 0.05, but matched measurements for the Q1 members are missing. [R3 contract](https://github.com/carbonphysicsai/Carbon/blob/915225242146be67e6de098d4a08324cc63dc684/carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json), [R6 gate plan](https://github.com/carbonphysicsai/Carbon/blob/915225242146be67e6de098d4a08324cc63dc684/.agent/tickets/VALIDATOR-26_battery_rule_v3.md), [R5 Q1 audit](https://github.com/carbonphysicsai/Carbon/blob/915225242146be67e6de098d4a08324cc63dc684/docs/development/evidence/score-value-alignment-01/README.md).

Gaps: all customer acceptance, standard tailoring and physical-limit approvals are HUMAN_INPUT. The plan's status is not independently treated as implementation or qualification evidence.

## D03 Applicability domain

Coverage: **PARTIAL**. Automation: manual.

**P:** a scientifically approved customer population is absent. R1 records an unapproved development input box; R3 defines a finite decision contract. **Q:** EV4 uses fixed development/verification conditions and a finite protocol grid; Problem C's primary in-band study spans 15–35 °C and initial SOC 0.05–0.50. **w:** EV4 decision loss uses provisional mistake costs and aggregation, not customer-derived preferences. These are separate objects, not interchangeable declarations of representativeness. [R1], [R2 §§2,4–7], [R3].

R3 covers thirty simulated cycles, while the decision measurements are first-hour and cycle-one quantities. It does not measure charging time to target SOC. The Q1 common mask resolves six of twelve development scenarios; excluded or missing outcomes do not become successful abstentions. [R7 Q1 panel mapping](https://github.com/carbonphysicsai/Carbon/blob/915225242146be67e6de098d4a08324cc63dc684/carbon/challenge_pipeline/readiness/Q1_PANELS.md).

Gaps: approved P and strata; sampled-domain adequacy; continuous or real-cell coverage; matched v3 scoring/evidence population. The in-band restriction is a disclosed historical development choice, not permission to narrow a customer's mandatory envelope.

## D04 Reference route and credibility tier

Coverage: **PARTIAL**. Automation: manual.

Reference: pinned PyBaMM 26.8.0.0, DFN with OKane2022 parameters, SEI/partially reversible plating and lumped thermal treatment. R1 describes model-relative use and reference execution. R2 reports five reference solver failures, kept separate from candidate failures. R3 makes near-threshold reference outcomes UNRESOLVED and missing/failed references REFERENCE_UNAVAILABLE. [R1–R3].

**Earned credibility:** public development reference execution and bounded numerical comparisons are reported. **Physical-validation tier and qualified-exam status: HUMAN_INPUT / unestablished.** This sample contains no reviewed cell-test referents or physical uncertainty. Shared reference-model errors would remain invisible to surrogate agreement. Solver/model pinning does not independently establish scientific adequacy.

Gaps: numerical-reference/scientific reviews not approved in R1; customer-relevant experimental validation, reference error budget and rights; exact current qualification evidence. Later EV records do not silently fill those catalogue approvals.

## D05 Requirement-by-requirement validation evidence

Coverage: **PARTIAL** overall; the stated development failures are **EVIDENCED**. Automation: automatable later.

| Requirement / scoped public study | Recorded outcome | Decision implication / unresolved evidence |
| --- | --- | --- |
| Feasible protocol / EV4 Problem C | First selected protocol: 46 feasible, zero infeasible, four unresolved in fifty in-band verification points | Not feasible at every point; no physical safety claim. Baseline fails reach at fifteen of fifty points, so its time-speedup comparison is undefined. R2 §12 |
| False-feasible behavior / EV4 real-model panel | 56 of 99 eligible members make a reference-verified false acceptance | Good aggregate error/rank does not establish a reliable feasible decision. R2 §12 H3 |
| Score/decision alignment / EV4 historical rule | H1 UNRESOLVED; paired Δτ −0.142, reported 95% interval [−0.275,+0.121] | Neither superiority nor equivalence established. R2 §12 H1 |
| Score/decision alignment / EV5 historical rule | Δτ −0.029, reported 95% interval [−0.132,+0.074]; no promotion condition holds | Do not promote an improvement from an interval spanning both signs. R4 |
| Reconstructed score exploitation / EV5 | Adversarial-score verdict FAIL; eight of ten selected members expose upper-half reference-infeasible decisions | A reliable reconstruction does not establish a scientifically adequate score. R4 |
| Alignment / run-5 Q1 v2 public PRACTICE | Eight-member τ −0.473 and ρ −0.539; six historical divergences | Negative point alignment on this panel, with wide descriptive bands; not a v3 result. R5 |
| Same members / prospective v3 | Accuracy leg, Q3 regret leg and false-feasible gate measurement uncomputable from these committed records | Gap, not zero, pass, or candidate failure. R5/R6 |

[R4 EV5 public summary](https://github.com/carbonphysicsai/Carbon/blob/915225242146be67e6de098d4a08324cc63dc684/docs/development/evidence/ev5-2026-10-03/README.md). The later Q1 audit uses a different denominator and analysis from the primary EV experiments; this sample retains each original outcome and does not re-score or combine panels. Independent comparison is to the recorded reference, not to physical truth.

Gaps: approved requirement-by-stratum evidence for one deployable artifact; held-out matched v3 evidence; physical validation; buyer's strongest matched-admissibility baseline and value acceptance.

## D06 Uncertainty

Coverage: **PARTIAL**. Automation: manual.

R3's development near-threshold bands are 3.15 s, 0.00197 V and 0.157 °C, derived from observed standard/refined reference shifts. They do not cover cell variability, parameter error, lumped-model discrepancy or real ageing uncertainty. EV4 notes dependence among members sharing recipes and seeds; its bootstrap exchangeability is approximate. R5's cluster bands are descriptive and share scenarios and adaptive PRACTICE exposure. None is a qualification interval. [R2 §7], [R3 reference.uncertainty], [R5].

Gaps: calibrated customer-use uncertainty, reference/referent/input/model/decision propagation, independence assessment, physical sensitivity and justified extrapolation. No quantitative physical uncertainty estimate is available in the inspected evidence.

## D07 Adversarial and robustness evidence

Coverage: **EVIDENCED for the reported adverse findings; PARTIAL for robustness coverage**. Automation: automatable later.

EV4 reports twenty-nine in-band and seventeen out-of-band reference-verified adversarial violations. Its top deciding member also has in-band violations. EV5 reports twenty-five in-band and twenty-one out-of-band findings; adversarial-score adequacy FAIL is distinct from construction-integrity PASS. EV5's sign-error control achieves a near false-acceptance value of 0.946 while passing the historical rule's gates; a descriptive measure identifies the failure. [R2 §12], [R4].

EV5 reconstruction matches for all 110 reported members do not repair that scientific defect. Its attack families remain IN_PROGRESS; absence of a construction finding is not full robustness coverage. The sample retains these failures even though later rules aim to address them.

Gaps: complete attack-family coverage; current-rule/product retesting; physical stress tests; independent verification of any remediation. No zero-findings safety bound.

## D08 Reproducibility and provenance

Coverage: **PARTIAL**. Automation: automatable now.

The ledger binds this sample to public Git paths, the exact snapshot and blob IDs. EV4 documents frozen plans/manifests, hashed outputs and typed reference failures. EV5 reports a frozen code identity and 110/110 reconstruction matches; local CI-service coverage is explicitly limited. R1 pins the reference overlay/model. [R1], [R2 §§10–12], [R4], [evidence.json](evidence.json).

Gaps: no exact deployable product artifact or independently reviewed deployment parity; incomplete full lineage/reproducibility review. Private confirmation and uncommitted prediction bundles are **uninspected**, not corroboration. This document copies no protected seed, case, label, operator account or private ledger.

## D09 Fallback rules

Coverage: **PARTIAL**. Automation: manual.

EV4 includes valid ABSTAIN and reports unresolved reference margins explicitly. R3 separates missing reference from candidate failure. The v3 gate plan separates missing quiz/reference/infrastructure from invalid candidate predictions and prevents soft compensation of a gate failure. These are recorded development semantics, not tested customer deployment controls. [R2 §§6–7,12], [R3], [R6].

Gaps: customer abstention thresholds, domain detection, uncertainty escalation, reference availability, integration, operator responsibility and accepted fallback tests. No deployment recommendation is inferred.

## D10 Known limits and gaps

Coverage: **EVIDENCED for disclosed development limitations; PARTIAL for a customer assessment**. Automation: automatable later.

The job is model-relative, finite-grid and first-hour/cycle-one for decision measurements. It cannot establish a global optimum, lifetime, warranty, charge-to-SOC, physical cell safety or performance outside the studied domain. Reference-common-mode errors, unresolved margins and false-feasible decisions remain. EV5's adversarial-score FAIL and Q1's missing matched v3 legs are material dossier warnings. [R2 §7,12], [R3], [R4], [R5].

R1 is a versioned historical readiness catalogue with unapproved scientific/numerical/customer reviews. Some listed future experiments have later development evidence, but this sample does not alter review states or treat a narrative PROCEED recommendation as qualification. A successful construction test cannot compensate for scientific failure.

Gaps and authority: customer/model/exam qualification, physical limits and referents, current-rule confirmation, rights, baseline/value proof and NASA tailoring all HUMAN_INPUT.

## D11 Audit trail

Coverage: **PARTIAL**. Automation: automatable now.

The public ledger indexes each source at the immutable baseline. EV4 retains pre-freeze disclosures and later accounting-projection changes; EV5 retains frozen-study and failure outcomes. R5 records precisely what cannot be inferred from the committed panels. Template source: #956 exact head `b0244360dbe49d534b0346779e1cebe5b21de085`. [evidence.json](evidence.json), [R2], [R4], [R5].

Gaps: buyer review, professional qualifications, conflict/independence assessment, disclosure rights, scoped product qualification record, full Appendix A applicability decision and lifecycle authority. No signature or digest is treated as physical credibility.

## Standard rendering annex — NASA-STD-7009B

This is a factor-by-factor evidence index from [NASA-STD-7009B §§4.2.1.8,4.3.6.1 and reporting §§4.3.8.4–5](https://standards.nasa.gov/sites/default/files/standards/NASA/B/1/NASA-STD-7009B-Final-3-5-2024.pdf). Coverage labels are this sample's judgments about the inspected records, not formal NASA levels. Thresholds, applicability and risk acceptance remain HUMAN_INPUT.

| Factor / group | Coverage | Common sections / sources | Evidence and gap |
| --- | --- | --- | --- |
| Data pedigree / capability | PARTIAL | D03,D04,D08 / R1,R3 | Model/parameter identity recorded; real-system referent pedigree absent |
| Verification / capability | PARTIAL | D04,D08 / R2,R4 | Pinned execution, refinements and reconstruction checks; qualified numerical review missing |
| Validation / capability | GAP for physical claim | D04,D05 / R1,R3 | Surrogate/reference comparisons exist; no reviewed real-cell comparator |
| Development technical review / capability | GAP | D10,D11 / R1 | Scientific/numerical approvals not recorded; later studies do not supply them |
| Development process/product management / capability | PARTIAL | D08,D11 / R2,R4 | Freeze/provenance records; no reviewed product configuration/qualification chain |
| Use assessment / results | PARTIAL | D01,D03,D09 / R1–R3 | Bounded model-relative use described; customer appropriate-use acceptance absent |
| Input pedigree / results | PARTIAL | D03,D08 / R2,R3 | Declared development inputs; customer input acquisition/rights/uncertainty missing |
| Uncertainty characterization / results | PARTIAL | D06 / R2–R5 | Numerical bands and study intervals; physical/use UQ missing |
| Results robustness / results | PARTIAL, adverse outcome retained | D05,D07 / R2,R4,R5 | Documented failures and thin alignment; full/current-rule robustness not demonstrated |
| Use/analysis technical review / results | GAP | D10,D11 / R1,R5 | Public analysis available; designated customer review/risk decision absent |
| Use process/product management / results | PARTIAL | D08,D11 / R2,R4,R5 | Versioned study trail; customer operation/change-control evidence missing |

Record-location subset for Appendix A: M&S 40/22–23 → D01; 43 → D02; 13–14/16/18/26 → D03; 15/17 → D04–D05; 19/21/28–30/33–34 → D06; 51/32 → D07,D10; 45–46/24–25 → D08; 49/39 → D09,D11; 48/50/31/35 → this annex; 36–38 → D11. All applicability, assessment-level sufficiency and risk acceptance decisions are HUMAN_INPUT. This **subset is not a complete compliance matrix**; remaining requirements need review under the framework crosswalk.

## Tier eligibility record

| EvidenceAudit prerequisite | Coverage | Missing / adverse evidence | Authority |
| --- | --- | --- | --- |
| Agreed buyer use and rights | GAP | No customer or approved engagement | HUMAN_INPUT |
| Exact audited artifact | GAP | Multiple historical panels, no product candidate | HUMAN_INPUT |
| Qualified exam and credible scoped reference | PARTIAL | Execution evidence; scientific reviews and physical claim prerequisites missing; adverse scoring results retained | HUMAN_INPUT |
| Declared domain, measurements and independence | PARTIAL | Development contracts; approved P, representative coverage and independent customer evidence missing | HUMAN_INPUT |
| Adequate records and approved disclosure | PARTIAL | Public-source audit exists; completeness and buyer reuse need approval | HUMAN_INPUT |
| Accepted audit scope | GAP | No designated acceptance authority | HUMAN_INPUT |

Result: **UNESTABLISHED**. Decision-tool and lifecycle tiers require further evidence and acceptance. A customer EvidenceAudit may validly conclude that a subject model fails; this development sample has not established the audit prerequisites themselves.

## Template fit record

The common sections fit the battery evidence, including negative outcomes. Three seams need explicit representation in a future exporter: evidence from multiple historical score rules must not be joined as one artifact; a readiness catalogue can lag later experiments without its approvals changing; and reference-relative verification/validation must coexist with a physical-validation gap. NASA capability and results factors belong in a cross-index annex, not a second hand-written dossier. The short JSON schema represents section coverage/findings/tier gaps; a production exporter still needs typed requirement rows, quantitative uncertainty and audience-specific projections. No template or scientific contract was changed by this sample.
