# Conditional brief-to-product offer scenarios

**ASSUMPTION / recommendation**, not a price list or launch commitment. Reuse the [intake model](../intake-spec-and-quote-model/INTAKE_AND_QUOTE.md) and [deliverable framework](../deliverable-framework/FRAMEWORK.md). All numerical scenario choices below have low/base/high in [evidence.json](evidence.json). Acceptance thresholds, intended use, rights and achievable physical claims are **HUMAN_INPUT**.

## Common scope and budget calculation

One bounded design family, existing usable geometry/material/history data, a credible reference route, reusable authoring adapters, documented buyer decision and cheap baseline. The proposed work covers intake, feasibility/reference checks, data preparation, construction/search, held-out requirement evidence, adverse findings, a development model artifact and a dossier or explicit gap report. A **decision tool plus dossier** is delivered only if its actual entry criteria are accepted; paying cannot guarantee that outcome.

For planning only:

**budget = total expert hours × transferred service-rate proxy + nonlabor allowance.**

Rate proxy **USD 75/125/165 per hour** comes from [one FEA supplier](https://josephwebb.net/pricing.html); applying it to these jobs is **ASSUMPTION**, not an observed blended surrogate-team rate. Nonlabor allowance is **ASSUMPTION USD 500/2,000/10,000**, a placeholder for reference/training compute and incidentals, not a measured entitlement to a fixed solve bank. Required third-party licenses, data acquisition or tests must be quoted explicitly; if unknown, a binding full-programme total stays **HUMAN_INPUT**. These envelopes exclude new physical experiments, certification/regulatory acceptance, unusual IP/security/integration terms, production support, tax and profit/value-based markup.

| Job | ASSUMPTION total expert hours L/B/H | Derived ASSUMPTION USD budget L/B/H | ASSUMPTION elapsed weeks L/B/H |
| --- | --- | --- | --- |
| Battery fast-charge | 80 / 240 / 640 | 6,500 / 32,000 / 115,600 | 2 / 5 / 12 |
| PM motor | 64 / 160 / 400 | 5,300 / 22,000 / 76,000 | 2 / 4 / 8 |
| Burst thermal | 48 / 120 / 320 | 4,100 / 17,000 / 62,800 | 1 / 3 / 8 |
| AI-chip cooling | 64 / 200 / 480 | 5,300 / 27,000 / 89,200 | 2 / 5 / 12 |
| Silencer | 80 / 240 / 640 | 6,500 / 32,000 / 115,600 | 2 / 6 / 16 |
| Warpage | 160 / 400 / 1,200 | 12,500 / 52,000 / 208,000 | 4 / 10 / 26 |

These are correlated low/base/high scenarios, **not probabilistic coverage bands**. They assume reusable workflow in the low case and increasing rework/reference/review burden toward high. Increasing money never relaxes a hard limit. A proposed week is **ASSUMPTION 5 business days**; team capacity is **ASSUMPTION 1/1.5/2 full-time equivalents**, with **8 productive hours/day** for the scheduling check. Specialist effort and independent review remain distinct even if they share a budget. Targets allow reference/review critical-path delays; missing buyer data or reference failure can make completion unbounded.

The nominal **base targets** are therefore burst thermal **3 weeks**, motor **4**, battery/cooling **5**, silencer **6**, warpage **10**. They are hypotheses for a measured internal delivery ledger, not “typical market delivery” or an SLA. Re-estimate from stage receipts, agreed case counts/refinement, solver cost, construction budget and integration before making an offer.

## Exact inputs, scope and failure paths

Every job needs the intended decision/action set, explicit hard limits and units, P/Q/w separately, domain/strata, geometry/material versions, reference/referent provenance and uncertainty, rights, existing baseline/latency, buyer decision volume, deployment/fallback expectations and acceptance authority. Missing essentials produce an itemized gap report or a narrower agreed assessment, never invented defaults.

| Buyer job and bounded product hypothesis | Required specific inputs and readiness test | What fails or changes the quote |
| --- | --- | --- |
| **Battery controls/calibration engineer:** choose a fast-charge protocol and cooling map for one cell family | Coherent cell parameters/calibration and history; initial SOC/temperature/ageing state; duty/ambient; action constraints; temperature/voltage/plating observers and sourced limits. Reproduce supplied examples, check domain coverage and known adverse cases | Without a credible cell/reference/measurement route, offer only a development gap report. Repeated decision volume and actual baseline cost are still buyer evidence gaps. Independent solver verification of proposed designs stays in the product workflow |
| **PM motor electromagnetic designer:** choose geometry/winding/skew for a stated duty and envelope | CAD/stack, winding, B–H and magnet data, electrical/thermal limits, speeds/angles and manufacturing ranges. Define loaded versus holding ripple, peak-to-peak versus RMS, cogging units; establish at least one jointly feasible design | No feasible design or inconsistent torque/ripple definitions blocks a decision-tool quote. Do not move buyer limits to sell the job. Flux's [published workflow](https://help.altair.com/flux/flux/help/english/ReleaseNote/2026Release/Flux/topics/ListOfNewFeaturesFlux2026.0.htm) confirms DOE/control/full-solver checks, not Carbon's feasibility |
| **Thermal reliability engineer:** choose burst power/cooling timing for one thermal assembly | CAD, temperature-dependent properties, interfaces/contact resistance, initial/ambient state, power history and specified temperature/time observers. Check energy accounting and refinement | Unmeasured interfaces or unknown heat paths downgrade the claim; full conjugate flow or phase change changes scope. The base offer assumes an existing bounded thermal route |
| **Accelerator cooling engineer:** choose a cold plate/flow setting for one device and inlet envelope | Package/lid and plate geometry, heat maps/power history, effective conductivities/interfaces, fluid properties, flow and pressure-drop limits, inlet conditions, fabrication envelope. Match cached FE/response-map baseline at equal admissibility | If a library/map already makes the decisions, deliver the negative value finding before training. Room-CFD software prices do not price this device-level tool. Unvalidated heat transfer/flow physics blocks physical claims |
| **Acoustics/NVH engineer:** choose silencer geometry in a specified frequency band | Geometry/ports/impedances, fluid/state, boundary conditions and losses; explicit attenuation/power measurement. Verify energy accounting and convergence; compare transfer-matrix/correlation and cached responses | Acoustic ranking with inadequate energy accounting cannot establish credibility. Flow/backpressure requires an additional reference/measurement route if part of the buyer decision; it is not silently included in a no-flow acoustic offer |
| **Package mechanics/process engineer:** choose an AI-accelerator package/process configuration | Coherent rights-cleared architecture, cure/relaxation/solder calibration, stress-free state and process/temperature history; warpage/stress definitions, measured referents and uncertainty. Reproduce the coherent source family before expanding it | Missing coherent material/process data means no internal launch job and no completion quote. Customer acquisition/calibration of data is additional scope, with unknown upper cost/time. Mixing unrelated published coefficients is not readiness |

The method and intended-use checks follow Carbon's existing intake research, **not six newly qualified scientific contracts**. A customer with a small existing DOE may need analysis/optimization only; a reusable fast tool carries independent evidence, deployment and maintenance work beyond a consulting report. A standards rendering organizes evidence and gaps; it does not create regulatory compliance.

## Offers to test with actual buyer receipts

Recommend an initial intake/evidence-gap assessment with **ASSUMPTION 8/24/64 expert hours**, the same transferred rate proxy and no assumed external cost: **USD 600/3,000/10,560 labor-only**, elapsed **1/3/10 business days** after inputs. Unknown reference/testing expenses are additional explicit gaps. Then scope an EvidenceAudit of an existing model or a model-development programme; preserve [framework tier prerequisites](../deliverable-framework/FRAMEWORK.md). No paid launch customer pilot is proposed.

Capture buyer receipts for incumbent paid study price and scope; internal staff hours/roles; data preparation; evaluations/refinements per decision; decisions per year; actual critical-path waiting; physical test and licenses; acceptance/rights/security demands. Break-even should use **incremental annual decision benefit minus verification/deployment/maintenance**, not inference speed alone. Quantity, benefit and willingness-to-pay remain **HUMAN_INPUT** until supported. Price may be value-based eventually; this research supplies a cost/scoping sanity check, not that authority.
