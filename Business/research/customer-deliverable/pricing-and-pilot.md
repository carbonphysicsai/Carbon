# Pricing evidence and the first credibility-dossier pilot

Ticket CUSTOMER-DELIVERABLE-01. Research/recommendation only; this is **not a quote, execution plan, spending approval or customer commitment**. Commercial acceptance, terms and claims remain the owner's decisions.

## Pricing evidence

| Comparable work/tool | What the public primary source supports | What it does not establish |
| --- | --- | --- |
| **Independent V&V service, ARKE, UK G-Cloud listing** | Advertised **GBP 546.36 / HUMAN_INPUT / 1,326.57 per unit/day** low/base/high. No central rate is reported. The service offers independent model/use review and an evidence audit trail. [S23](https://www.applytosupply.digitalmarketplace.service.gov.uk/g-cloud/services/403132573695999). | Actual paid day rate, grade mix, billed-unit/person-day equivalence, tax treatment or total programme price. The pricing PDF was unavailable; no hidden commercial terms were inferred. |
| **Ansys SimAI** | The current FAQ directs pricing/licensing enquiries to sales. [S24](https://ansys.synopsys.com/products/ai/simai). Comparable annual or project price: **HUMAN_INPUT null/null/null**. | A public fixed price, invoice, total modelling effort or standard-specific V&V service price. |
| **NVIDIA PhysicsNeMo** | Open Apache-2.0 framework. Framework licence fee **USD 0/0/0**, sourced licence basis; data, compute, construction, deployment and support remain separate. [S25](https://github.com/NVIDIA/physicsnemo). | Free end-to-end engineering or assurance, zero total cost or qualification of a particular physical model. |
| **PhysicsX / Siemens PhysicsAI** | Reviewed product/release pages describe enterprise engineering software and simulation-data-based surrogates; no comparable contract price observed on those pages. **HUMAN_INPUT null/null/null** for each. [S27](https://www.physicsx.ai/), [S28](https://news.siemens.com/en-us/siemens-simcenter-physicsai/). | A claim that no prices are published anywhere, actual commercial spend, or a fair-price ceiling for Carbon. |
| **Medical V&V value** | ASME's primary conference abstracts give qualitative examples of credible modelling avoiding extra testing and insufficient credibility leading to additional testing. [S22](https://www.asme.org/wwwasmeorg/media/resourcefiles/events/vandv/2018v-v_program.pdf). | Typical effort/cost, general savings, WTP or independent proof that every submitted model was accepted. No monetary amount is derived. |

The public-rate anchor is stronger than guessing a “standards-grade dossier price”, but it still cannot answer what buyers actually paid for completed V&V or fast-model programmes. Those exact quantities remain **HUMAN_INPUT null/null/null**. The [standards map](standards.md) therefore leaves each typical programme cost unknown.

## Transparent workload scenarios

For illustration only, assume one billed unit is a person-day and rates of **GBP 546.36 / 1,000 / 1,326.57 per person-day**. The central rate and unit interpretation are **ASSUMPTION**; endpoints reuse the published advertised interval. All effort ranges below are **ASSUMPTION**, not sourced industry averages. Endpoint cost = corresponding effort × corresponding rate; uncertainty/correlation is not statistically calibrated.

| Illustrative scope | Assumed person-days low/base/high | Assumed labour cost GBP low/base/high |
| --- | --- | --- |
| L1: diagnostic evidence/gap audit, candidate first-pilot scope | 5 / 10 / 20 | **2,731.80 / 10,000 / 26,531.40** |
| L2: model integration + reference-bounded dossier | 20 / 60 / 120 | **10,927.20 / 60,000 / 159,188.40** |
| L3: high-consequence evidence programme | 100 / 250 / 500 | **54,636 / 250,000 / 663,285** |

These are deliberately scope illustrations, not estimates of a NASA/FDA/DoD project's typical cost. They exclude physical experiments, solver/tool licences, compute, taxes, data rights, legal/export work, secure infrastructure, deployment support, contingency and project-specific accreditation. **Total costs have no verified low/base/high bound**: HUMAN_INPUT null/null/null. Retaining precise advertised rate endpoints makes the arithmetic auditable; it does not make the effort precise.

L1 is a provisional manual-review workload hypothesis. Battery's executed development evidence makes it the most defensible place to test that hypothesis; the author has neither performed the proposed audit nor verified its duration. The research performed for this ticket spent nothing.

The discovery framework's compute-bank cap is separate from these costs. A cheap initial reference bank does not fund customer V&V, test rigs, programme assurance or production support. Cross-currency conversion is unnecessary and was not guessed.

## First pilot

**Recommendation:** battery, with a **NASA-STD-7009B-structured voluntary engineering audit**, initially covering offline charge/cooling-map screening and its evidence gaps. ASME V&V 20 can organise a thermal component crosswalk where applicable; it is not a full electrochemical-model qualification. No NASA involvement, project adoption, external accreditation, BMS deployment, EV safety or warranty claim follows.

This choice optimises **first demonstrable evidence assembly**, not investor excitement or an assumed highest-paying sector. NASA's broad framework allows the surrogate/reference relationship and makes the limits visible. For the newer v3 ambient-indexed map, current evidence supports a prospective audit plan, not completed credibility. Historical battery results retain their original task/contract identity.

| Challenge | Available public basis | Most relevant first framework | Gap and consequence |
| --- | --- | --- | --- |
| **Battery** | Pinned PyBaMM development reference; executed EV studies, reproducibility/provenance and explicit adverse decision results. EV5 construction integrity passed while adversarial scoring failed. [R19](https://github.com/carbonphysicsai/Carbon/blob/4578d20b27f3d88641a8fe06b3bdbbde8aca17f7/docs/development/evidence/ev5-2026-10-03/README.md). | NASA-STD-7009B for the whole decision/evidence lifecycle; applicable thermal analysis can add ASME V&V 20. | Exact customer P, cell/material history, buyer limits, reference tier and physical corroboration remain open; v3 is a different specified job. Best first **diagnostic** dossier; an affirmative safety dossier is unavailable. |
| **Motor** | Open magnetic reference and verification work; prior envelope lacked a peak-torque-feasible design, while revised feasibility is not settled in the public scorecard. [R18](https://github.com/carbonphysicsai/Carbon/blob/4578d20b27f3d88641a8fe06b3bdbbde8aca17f7/docs/development/challenge_pipeline/value-cost/motor.md). | NASA-style decision assessment; do not force magnetic physics into ASME solid/thermal coverage. | Demonstrate an admissible actuator in each claimed stratum, matched buyer-tool evidence, and thermal/control/bench scope as required. Package assembly now would be dominated by feasibility gaps. |
| **Warpage** | Source-confirmed buyer workflow and original full-3D architecture; proposed open thermoelastic route. No executed container/deck/output adapter, earned reference tier or demonstrated feasibility. [R24](https://github.com/carbonphysicsai/Carbon/blob/8879529d959bf81472e120f4430a65651afb552a/docs/development/challenge_pipeline/discovery/warpage-packet/PACKAGE_WARPAGE_DESIGN_PACKET.md). | **ASME V&V 10**, with relevant package metrology and thermal evidence. | Customer-specific stress/warpage/temperature limits, material/history law and numerical/physical validation remain required. Strongest next discipline-specific dossier once its source/acceptance and reference work is authorised. Retain full 3D and full history. |

This is a different question from which Challenge ranks highest on conditional annual value/compute cost. It does **not** rescore warpage, solenoid, seal or the current eight, and it grants no adoption/replacement authority.

## Concrete first step — an acceptance-and-gap worksheet

The first useful artefact would be a worksheet filled jointly by a nominated **EV cell/BMS simulation lead**, a **customer validation/assurance reviewer**, and Carbon's **science/reference/evaluation owners**. This is proposed work; no outreach is authorised by this research request.

| Worksheet field | Starting proposal | Required input before an affirmative model claim |
| --- | --- | --- |
| Decision and reliance | Offline selection/revision of supported fast-charge and cooling maps; engineer reviews outputs and retains the current qualified solver/testing workflow. | Named customer, precise action/outputs, real tool workflow, frequency/latency, consequence of wrong advice and intended simulation reliance. |
| Exact physical/task scope | Use the current v3 packet/law as proposal, with historical evidence clearly separate. | Cell identity, initial/age/history support, causal inputs, map observer, temperature/SOC scope, sourced hard limits and acceptance owner. Unsupported conditions are excluded explicitly. |
| Population and observations | Separate deployment P, enriched near-limit/diagnostic Q and evidence w. | Customer strata and coverage, sampling/power, censoring/unresolved policy; a uniform parameter envelope is not verified deployment volume. |
| Reference and measurement | Pinned PyBaMM model, numerical verification/refinement and independent matched witnesses. | Earned reference tier, uncertainty adequacy, physical comparison required for the claim, measurement applicability and unresolved-error treatment. |
| Requirements and audit | Requirement → observer → gate → evidence → outcome, with adverse findings retained. | Accepted edition/clauses and reviewer access. Dossier says “not assessed” or “insufficient evidence” where appropriate. |
| Baseline/value | Direct current tool, cached map, interpolation/response surface and adequate reduced-order model. | Same supported domain and mandatory conditions, honest fallback, total elapsed workflow and construction cost; public case counts do not establish annual programme cadence. |
| Product identity and custody | Artefact/runtime identities and approved evidence projections. | Product retrain/new Model Card where required, fresh job-shaped evidence, rights/security controls and non-self-certifying judgment. |
| Escalation and change | Reject unsupported or unresolved queries; return no recommendation when no admissible action is established. | Agreed decision/uncertainty rules, high-fidelity/human fallback and re-evidence triggers. NONE_FEASIBLE and reference failure stay distinct. |

**Proposed sequence, no execution:** assemble the source/artefact index and licence/rights inventory; have the owners freeze the question and acceptance contract; assess numerical/physical/exam gaps; pre-register independent public diagnostic studies and strongest-baseline comparisons; obtain a separate authorised evidence budget; then run and review evidence under its own owners. Samples, repetitions, tolerances, pass criteria, physical-test cost and total budget stay **HUMAN_INPUT null/null/null** here. No scientific bar is relaxed to produce a favourable pilot.

## What completion would mean

A first **diagnostic** dossier is complete when every adopted customer requirement traces to evidence or an explicit gap, current adverse findings remain visible, use/applicability and reviewer roles are agreed, and rights permit the evidence projection. Its conclusion may be that the model is not adequate.

A deliverable fast-model package additionally requires exact product-artifact/runtime evidence, accepted reference/exam/measurement adequacy, qualified coverage and uncertainty, credible improvement over the buyer's adequate baseline and the appropriate scoped qualification judgment. Regulatory/tool/accreditation obligations must be fulfilled separately where applicable. Commercial acceptance is not scientific acceptance.

Before setting prices or claiming a buyer pays “a lot”, obtain a buyer-owned budget/scope, actual past V&V invoices or effort records, specific tool pricing and an attributable business case. Public evidence currently does not establish these. The owner decides adoption, customer terms, prices and funding.
