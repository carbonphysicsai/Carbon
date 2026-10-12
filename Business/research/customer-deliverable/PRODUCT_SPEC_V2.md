# Carbon Model Package — product specification v2

**Ticket:** PRD-00 / PRODUCT-SPEC-V2. **Date:** 2026-10-12.
**State:** PROPOSED / DESIGN ONLY. No runtime implementation or qualification
is delivered by this ticket. Reviewer route: Carbon Validator; Data Collection
for reference, measurement and data joins. Adoption and acceptance: HUMAN_INPUT.

PRD-01 amendment (2026-10-12): incorporates the
[Carbon Validator follow-ups](https://github.com/carbonphysicsai/Carbon/pull/1195#issuecomment-6129429811).
Guard and Assistant development implementations are recorded in the prospective
PRD-02/03 notes below; PRD-01 implements only
DEVELOPMENT_SAMPLE document automation.

The Carbon Model Package is one versioned engineering product: an exact fast
model, the contract describing its supported job, evidence explaining where its
answers hold, and a guarded design workflow that escalates doubtful answers to
the verified solver or a responsible engineer. Its useful output is a decision
with an inspectable basis. An adverse audit remains a useful deliverable.

This specification extends [D01–D11](../deliverable-framework/FRAMEWORK.md) and
[Q0–Q8](../../../Design_Specs/Build_Out_Product_Qualification_Extension.md).
[Product Qualification Evidence](../../../Design_Specs/Product_Qualification_Evidence.md)
owns the evidence objects; [Specialist Bank](../../../Design_Specs/Specialist_Bank.md)
owns Product Battery modules and packaging; [Business Canon §§5–7,13](../../Business_Canon.md)
owns the commercial sequence and rights. None is replaced by the package name.
Their future product path remains separate from the current scientific judge.

## 1. Authority, reuse and evidence meaning

Repository baseline inspected: `27aa3f8cf381eb7bd4aec08fe1c7589c512436a0`
on main. The required shared operator design draft was read at SHA-256
`3de29124d7b34542b45107bb224322036876d5e0e474c6fac90677c1ed213369`;
it remains a design input, not committed runtime authority. Links below name
the homes to extend; maturity observations refer to that baseline. A delivered
package must pin its own source revision, evidence
cut-off and exact objects rather than treat a mutable path as evidence.

KEEP the existing [deliverable design](deliverable-design.md),
[evidence map](evidence-map.md), [pricing/pilot plan](pricing-and-pilot.md),
[standards map](standards.md), [template](../deliverable-framework/TEMPLATE.md)
and [crosswalk](../deliverable-framework/STANDARDS.md). WRAP the current
[generator](../../../scripts/dev/customer_deliverable/generate.py),
[generator contract](../deliverable-generator/WORKING_CONTRACT.md),
[trust-map library](../../../carbon/trust_map/core.py),
[VALUE-BAR evaluator](../../../carbon/development_comparison/value_bar.py) and
[equal-budget replay](../../../carbon/design_search/equal_budget.py).
PRD-01 extends that generator rather than forking it. This ticket changes none
of those implementations, schemas, scientific rules or historical records.

Every requirement or measurement row retains these separate fields:

| Field | Meaning |
| --- | --- |
| Identity | Exact model/runtime, Challenge, question law, context of use, contract, reference, observer, evidence role and version |
| Coverage | EVIDENCED, PARTIAL or GAP; a measured failure can be EVIDENCED |
| Outcome | Source PASS, FAIL, UNRESOLVED, NOT_ASSESSED, FAILED_REFERENCE or FAILED_INFRA; NOT_APPLICABLE requires recorded human rationale |
| Basis | Verification, reference-relative, physical validation or decision value; basis is never promoted by document completeness |
| Criterion | Rule, units, provenance, approving authority and date; absent criterion is null / HUMAN_INPUT |
| Evidence | Immutable safe source locator, denominator, missing/uninspected coverage, uncertainty method, dependencies and adverse-finding links |
| Judgment | Named authority, signed decision reference or HUMAN_INPUT; a formatter cannot issue this judgment |

The three tiers remain **admissibility gates → registered decision-value score
→ measured model-card deliverables**. This product document creates no score
term. Mandatory failure cannot be offset by value, speed or purchase. A floor
becomes a gate only after the governing owner registers and screens it. No
scoring or crown rule is imported from the operator draft by this specification.

Two seams are explicit. **DOCUMENTATION_LAG resolved prospectively:** the shared
`PHYSICS_CONTRACT_01_DRAFT.md` §1/§2 now says gates or measured deliverables,
never scored laws. PRD-01 read that update at SHA-256
`362d9fc397865dd66c065107bcddad724bc4f4c72deb1eaad0a3659b2148f5c1`.
The earlier digest above remains PRD-00's historical input. The
[committed packet drafts](../../../docs/development/challenge_pipeline/physics_contracts/README.md)
adopt only the format and solver-calibration principle. The wording repair
does not adopt a gate; law adoption, floors and score use remain HUMAN_INPUT.
**IMPLEMENTATION_LAG:** the merged
[MMS owner decision](../../../.agent/decisions/2026-10-11-OWNER-CODE-VERIFICATION-ACCEPT-01.md)
accepts bounded battery/motor/f02 code checks, while the older
[battery verdict](../../../docs/development/evidence/battery-feasibility-02/code-verification/pybamm-verdict.json)
still has `accepted_development_pass: false`. Retain both identities and show
the discrepancy. Do not rewrite the old verdict or bypass a consumer's required
accepted input. Data Collection owns a prospective reconciliation.

## 2. One package, mapped to existing homes

The following IDs are document requirement IDs, not new runtime enums or
registered public APIs. Supporting sections can index the same immutable fact;
there is no second fact store or second qualification authority.

| Package element | D-section homes | Q-step homes | Existing PB homes | Additive work |
| --- | --- | --- | --- | --- |
| CMP-01 Exact artifact and rebuild recipe | D08, D11 | Q0, Q5, Q8 | PB-ART, PB-LAT, PB-PHYS | Bind full runtime and wrapper identity, parity and cost evidence |
| CMP-02 Physics contract and law-check report | D02–D05, D07 | Q0, Q1, Q2, Q8 | PB-PHYS, PB-ADV; PB-ROLL where required | Join adopted laws, required outputs and image-bound calibration to results |
| CMP-03 Model card and floor register | D05–D08, D10 | Q0, Q1, Q2 | PB-PHYS, PB-ADV, PB-LAT; applicable PB-ROLL | Region accuracy, robustness, stretch error, calibration and full cost |
| CMP-04 Trust map | D03, D05–D07, D09 | Q1, Q4, Q5 | PB-PHYS, PB-ADV, PB-ESC | Add law and later interval layers; accepted query-time interpretation |
| CMP-05 Decision evidence | D01, D02, D05, D07 | Q1, Q2 | PB-INV, PB-ADV, PB-LAT | Safe VERIFY-R/top-k and equal-budget evidence joins |
| CMP-06 Credibility dossier | D01–D11 | Q1, Q2, Q4 | Index all applicable PB-* | Risk plan, requirements matrix and separate defense VV&A view |
| CMP-07 Provenance and audit | D08, D10, D11 | Q0–Q5, Q7, Q8 | PB-ART and all result records | Runtime SBOM, build provenance, correction and human-decision slots |
| CMP-08 Envelope Guard | D02, D03, D06, D09 | Q0, Q1, Q2, Q5, Q8 | PB-ESC, PB-ADV, PB-ART, PB-LAT | New runtime wrapper; proposed home `carbon/product/envelope_guard/` |
| CMP-09 Decision Assistant | D01, D02, D05, D06, D09 | Q0, Q1, Q2, Q5, Q8 | PB-INV, PB-ADV, PB-ESC, PB-LAT, PB-ART | New budgeted search/verification workflow; proposed home `carbon/product/decision_assistant/` |
| CMP-10 Lifecycle | D03, D09–D11 | Q3, Q6–Q8 | Re-run every affected PB module | Guard/map/assistant changes join material-change assessment |
| CMP-11 Offline deployment and disclosure | D08–D11 | Q4, Q5, Q8 | PB-ART, PB-LAT, PB-ESC; offline install checks | Customer-host custody and deployment evidence; legal decisions remain HUMAN_INPUT |

Q0 owns future schema compatibility; Q1 preserves every Product Battery
attempt; Q2 owns bounded human qualification judgment; Q3/Q6 own lifecycle;
Q4 owns disclosure; Q5 verifies delivered identity; Q7 preserves failure
learning under decontamination; Q8 tests those boundaries. Guard or Assistant
component tests do not establish system qualification. All mandatory modules
for a full surrogate SKU still apply; this document grants no reduced battery.

## 3. CMP-01 — exact executable artifact

Deliver a manifest binding weights, architecture, pre/postprocessing, export,
I/O contract, Guard, Assistant and runtime dependency identities. Record units,
coordinate/sign conventions, geometry/material/history inputs, valid shapes,
precision, hardware profile and failure behavior. Resolve each delivered file
to a digest; verify transport/install digests against the manifest and, for a
qualified package, the exact Qualification Record.

Carbon rebuilds. Include a controlled reproduction recipe: source strategy
identity, permitted data-generation route and digest, training environment,
configuration, public/development randomness where disclosure permits, measured
compute and comparison procedure. Protected seeds and proprietary recipe details
follow their disclosure policy; missing rights are an explicit gap. A recipe
does not guarantee bitwise-identical trained weights. Rebuild agreement must be
measured within a documented HUMAN_INPUT tolerance. A new retrain gets a fresh
Product Candidate Model Card and fresh qualification evidence.

PB-ART records round-trip export parity on agreed observables, especially at
limits, including precision and wrapper effects. PB-LAT records cold start,
warm per-query and batch median/tail latency on pinned hardware, query shape and
load. Report raw model latency and end-to-end guarded workflow latency
separately. Parity tolerance, latency class/SLA and supported runtime acceptance
are HUMAN_INPUT. No unmeasured performance claim is filled from a library name.

## 4. CMP-02 — physics contract and law-check report

The contract binds laws and their scientific sources, mathematical assumptions,
validity envelope, required inputs/outputs and observers, calibration route,
probe law, and adopted mandatory gates. Law types are a closed registered
vocabulary; descriptive mathematics is data, never customer-supplied executable
code. A missing model output is a GAP even if the reference computes it.
An algebraic output derived from inputs is not independent conservation evidence.

The pinned, verified reference is the comparison yardstick. Calibration records
must bind image, solver/deck, equation/discretisation route, materials, observer,
units and mesh/time/frequency refinement. MMS or analytic code verification
checks implementation against equations. Application solution convergence and
reference adequacy are separate prerequisites. Heat MMS cannot verify acoustics;
particle/heat MMS cannot verify full DFN/plating; linear motor MMS cannot verify
nonlinear materials, torque or skew.

Measure law residuals and observable-level numerical uncertainty on matched
public development cases/pairs/paths for development. Quantile, multiplier,
absolute denominator floors, sampling uncertainty, probe density and gate
adoption are HUMAN_INPUT. Refuse calibration that demands precision beyond the
verified observable-specific reference error, or that uses incompatible image
or observer identities. A global MMS norm is not a °C, N·m or dB error budget.
Physical simplification discrepancy is separately justified and reported;
inflating a numerical tolerance cannot hide it. Use a scientifically sourced
physical bound where a simplified solver's behavior is an inadequate law proxy.

The report lists every required law: applicability, adoption state, outputs
available, sample/probe count, residual or violation distribution, uncertainty,
criterion/owner and typed result. Reference or observer failure produces no
candidate failure; missing validity is UNRESOLVED. Unrun checks cannot pass.
Retain failures and the conditions that exposed them. Required gate screening
uses reference, known-good, known-bad and adversarial controls before adoption.

The f02, cooling-cell, motor and f13 packet JSONs remain DRAFT/HUMAN_INPUT with
runtime disabled. Their listed input support is not physical validation.
Cooling point C does not replace point B, 10p/12s motor does not become the
8p/24s runtime, and f13's lossless quiescent scope does not become hot exhaust.
Historical development battery laws/results do not become evidence for a new
map or output contract by relabeling.

## 5. CMP-03 — model card and floors

Reuse the canonical Model Card with explicit product-candidate role and
lineage. Each row carries artifact, evidence domain, observer, reference/image,
denominator, source, uncertainty and measured/not-run state. Comparison is to
the pinned verified solver, with its applicability and uncertainty stated.

| Deliverable | Measurement and evidence basis | Required floor record; all values HUMAN_INPUT |
| --- | --- | --- |
| Accuracy overall and near limits | Error in output units by registered region/stratum, mandatory-limit error and false feasibility; exact common resolved mask and reference uncertainty | Maximum admissible overall/near-limit error, approved regions, aggregation and any comparator-relative factor |
| Robustness | Local sensitivity on matched probe pairs; median/tail distribution and ratio to matched reference sensitivity, with an absolute treatment at zero reference sensitivity | Sensitivity ceiling, normalization, approved cheap-comparator factor where adopted |
| Extrapolation | Error growth by distance/region beyond training support but within declared physical validity; separately show unsupported out-of-validity diagnostics | Stretch/in-range growth ceiling and absolute error budget; no trust permission outside validity |
| Uncertainty calibration | If intervals exist: width, nominal coverage, observed coverage and sample/dependence basis against reference answers; physical uncertainty separately | Accepted coverage band, width/use rule and interval output contract; absent intervals remain GAP |
| Speed at equal accuracy | Paired same-job solver/model timings at accepted accuracy/admissibility; full Guard, verification, I/O and fallback cost | Latency ceiling and equal-accuracy/speed rule for the declared device/workflow |
| Training cost | Controlled rebuild CPU/GPU and wall seconds, device class, data generation, repeated attempts and verification costs; monetary conversion only with a sourced price | Build/resource ceiling or explicitly justified nonmandatory status, signed by the responsible owner |

Floor records exist for all rows: criterion and authority are null until
registered. Any mandatory missing measurement makes eligibility unresolved;
an optional or inapplicable row requires an explicit policy decision, never a
formatter's default. No floor is adopted by this table. Accuracy cannot be
required beyond the reference's observable-level resolution.

The shared draft §5.5 proposes a no-regression ratchet: value improvement and
no *proven material worsening* of a deliverable beyond its registered delta,
using paired fresh evidence where applicable. That differs from demanding
proof of noninferiority. Deltas, inferential level, evidence/crossing rule and
adoption are HUMAN_INPUT. This is compatibility context only, not an implemented
leader, frontier or qualification rule. A product successor separately shows
regressions and requires the governing Q2/Q6 decision before retaining claims.

## 6. CMP-04 — trust map

Use decision-relevant axes declared by the job; show additional axes as bands
or small multiples and disclose what is marginalized. Each cell binds the model,
contract, source panel, reference verification, evidence cut-off, units, count
and missing coverage. Layers: reference error, disagreement, law violations,
and later own uncertainty and calibration. Distinguish solved-case evidence
from model-only probes. Disagreement is not calibrated uncertainty; consensus
can be wrong. NO_DATA is unknown, never zero error or trustworthy interpolation.

Current [PLT-05](../../../docs/development/TRUST_MAP.md) implements DEVELOPMENT
error/disagreement maps from expressly PUBLIC or RELEASED projections. It does
not implement law, interval or TRUST layers, and its provenance is an operator
assertion rather than cryptographic attestation. A cell is a pooled observation,
not a guarantee about every query. Guard use requires an accepted map policy,
coverage adequacy, marginalized-context applicability and exact identity join.

Use public/released data only for this lane. Future buyer projections of richer
evidence require Q4 authorization and rights; buyer status alone grants no
access to hidden scored history. Suppression, coarsening, delay and repeated-
disclosure review must precede any hidden-derived public/miner projection.
Fresh customer evidence is a separate route. Maps may guide public TRAIN data
or product verification, never select official scored cases or alter P/Q/w.

## 7. CMP-05 — decision evidence

Report reference-verified top-k choices, retained pre-verification ranks,
post-verification feasible picks, regret in buyer units, false feasibility,
abstention and unresolved/reference failures. Bind the question law, constraints,
model, reference, selection freeze, evidence role, folds and exact policy.
Hidden-question studies are produced by the independent authorized evaluator;
the package consumes only approved aggregates/receipts. This ticket reads or
produces no hidden questions, labels, probes or reconstructable identifiers.

Keep fixed-k VERIFY-R distinct from uncertainty-directed verification and from
budgeted search. Reuse VALUE-BAR's evidence/owner-rule identities and equal-
budget replay with solver-alone, strongest adequate cheap-baseline-then-solver,
and model-then-solver arms. Match job, admissibility, supported domain, wall/core
budget, solver-evaluation cap and objective units. Include screening, Guard,
startup, solver verification and failed/fallback calls in measured workflow
cost; separately report one-time construction/amortization assumptions.

Curves show best verified feasible value, regret, feasible-pick fraction,
paired effects and valid dependence-aware intervals across registered budgets.
No feasible verified pick means no invented value/regret; preserve its frequency
and distinction from proven NONE_FEASIBLE. An incomplete bank does not prove
global optimality. Replay is not a measured live Assistant search.

The existing VALUE-BAR-V1 limits are a distinct registered DEVELOPMENT rule,
not universal product floors or customer acceptance. Reuse its unchanged
verdict when its exact prerequisites are met; otherwise report
INSUFFICIENT_EVIDENCE. Customer budgets, minimum value and acceptance authority
remain HUMAN_INPUT. Preserve losses to cheap baselines, infeasible selections,
negative results and unmet assumptions as prominently as favorable curves.

## 8. CMP-06 — risk-informed credibility dossier

The dossier is a requirements-to-evidence matrix plus a plan of evidence needed
for the declared reliance. It consumes the same D01–D11 facts and Q1 records;
the Q2 judgment remains separate. Each claim also identifies its authority,
limitations, failure/falsification conditions and next required proof, following
[Defensibility and Diligence](../../../Design_Specs/Defensibility_and_Diligence_Architecture_v1.md).

Start with the decision/context of use and assess **model influence × decision
consequence** as two documented axes. The multiplication symbol denotes a
joint assessment, not an invented numeric risk score. The customer/assurance
owner sets categories, required credibility, criteria and acceptance authority
(all HUMAN_INPUT). Then plan code verification, solution verification,
reference-relative evidence, physical referents, uncertainty, applicability,
robustness, independent review and closure for each affected requirement.
Higher reliance/consequence informs stronger evidence needs; no automatic
severity-to-sample-count or risk-to-approval formula is supplied.

| Requirement / use | Model influence / consequence / required credibility | Verification evidence | Reference-relative evidence | Physical-validation evidence | Outcome, gap, adverse link / authority |
| --- | --- | --- | --- | --- | --- |
| CMP-PILOT-LIMIT: agreed buyer limit, units and observer HUMAN_INPUT | HUMAN_INPUT / HUMAN_INPUT / HUMAN_INPUT | Exact-image MMS plus application convergence: cite or GAP | Exact product/panel/observer law checks: cite or GAP | Customer-host referent, measurement uncertainty and applicability: GAP / HUMAN_INPUT | NOT_ASSESSED; no limit or acceptance inferred |
| CMP-PILOT-DECISION: offline design selection under agreed budget | HUMAN_INPUT / HUMAN_INPUT / HUMAN_INPUT | Export/Guard/Assistant code and integration evidence: cite or GAP | Solver-verified decision value, false feasibility and adequate baseline: cite or GAP | Real-system corroboration needed for a physical claim: GAP / HUMAN_INPUT | Historical adverse results retained; customer acceptance HUMAN_INPUT |

These are proposed requirement slots, not completed customer assessments. Code
MMS/rebuilds, reference-relative fidelity and physical validation occupy different
columns. Calibration data and independent physical validation data must be
distinguished. Neither digests, solver agreement nor EV5 reconstruction supplies
physical validation. Evidence adequacy/independence needs its own judgment.

**Standards crosswalk only, not compliance.** ASME V&V 40-2018 is a medical-device
framework; its risk-informed planning style is a proposed analogy for other
industries, not an assertion of applicability or cross-domain certification.
Public [ASME scope](https://www.asme.org/codes-standards/find-codes-standards/assessing-credibility-of-computational-modeling-through-verification-and-validation-application-to-medical-devices/2018/print-book)
and [risk rationale](https://www.asme.org/wwwasmeorg/media/government-relations/publicpolicy/fact-sheet-modeling-and-simulation.pdf)
support the topic mapping; exact clauses/licensed review remain HUMAN_INPUT.

Use the existing [NASA-STD-7009B crosswalk](../deliverable-framework/STANDARDS.md)
for intended use, acceptance criteria, verification/validation domains, separate
capability/results assessments, uncertainty, technical review and records.
[NASA's registry](https://standards.nasa.gov/standard/NASA/NASA-STD-7009)
assigns program/project criteria and delegated Technical Authority approval;
Carbon cannot grant them. Retain applicable edition, mapping-verification
status, clause/topic, D-section, evidence, gap and human tailoring fields.
Do not equate eleven D-sections with NASA's separate assessment factors.

For defense, provide a supporting VV&A view under
[DoDI 5000.61](https://www.esd.whs.mil/Portals/54/Documents/DD/issuances/dodi/500061p.pdf)
and [MIL-STD-3022](https://quicksearch.dla.mil/qsDocDetails.aspx?ident_number=275961):

| Customer VV&A product | What consumes this package | What remains with the customer/assigned authority |
| --- | --- | --- |
| Accreditation Plan | D01–D03 context, requirements, reliance/consequence, gaps and evidence-access plan | Intended purpose, accreditation criteria, roles and tailored plan approval: HUMAN_INPUT |
| V&V Plan | D04–D07 comparator, verification/validation/UQ work and requirements matrix | Approved tests, physical referents, independence and evidence adequacy: HUMAN_INPUT |
| V&V Report | D05–D08 outcomes, discrepancies, adverse results, limits and provenance | Assess evidence against agreed purpose and criteria; resolve remaining findings |
| Accreditation Report | D09–D11 restrictions, current qualification record if any, residual risk and change obligations | Designated accreditation authority's decision/signature: HUMAN_INPUT; Carbon never self-accredits |

MIL's public catalogue establishes these four templates. DoDI full-text retrieval
was unavailable during this ticket; detailed instruction/clause review is GAP,
not a completed compliance audit. No defense accreditation, aerospace tool
qualification or automotive safety acceptance follows. Applicable DO-330,
ISO 26262 or other tool-assurance obligations require a separate human-owned
assessment; the [existing standards map](standards.md) is the starting index.
Primary-source metadata checked 2026-10-12; adopted editions/tailoring are HUMAN_INPUT.

## 9. CMP-07 — provenance and audit

Bind the model, runtime/export, permitted data/source manifests, solver image,
MMS result and acceptance, convergence/calibration, contracts, map, policy,
Product Candidate Model Card, Product Battery Record and Qualification Record.
Use exact digests and safe locators. A hash establishes byte identity, not
physical truth, independence, disclosure clearance or signing authority.
Protected data commitments may themselves be sensitive; publish only an
approved projection, never assume hashing makes a hidden case safe.

Retain an append-only corrections log: prior object, correction/reason,
affected claims, replacement evidence, issuer, time and supersession reference.
Keep failed attempts, original meanings and dissent. Human-decision slots bind
scope, exact artifact/evidence/policy, responsible role, identity, date and
signature-verification reference. Unfilled slots are HUMAN_INPUT; CI, an agent
or a well-formed signature field cannot supply scientific/security/rights approval.

Deliver a runtime SBOM listing direct/transitive components, versions, source
and artifact hashes, licence metadata and unresolved inventory gaps. Include
SLSA-style build provenance: subject digest, pinned source/materials, builder
identity, build definition/parameters, invocation and dependencies, plus an
offline verification procedure. [SLSA v1.2 build provenance](https://slsa.dev/spec/v1.2/build-provenance)
is a field-design reference only. Do not claim a SLSA level, audited build
platform or security qualification from an SBOM/attestation. Licences, signer
trust and security acceptance remain HUMAN_INPUT; no keys are created here.

## 10. CMP-08 — Envelope Guard (new runtime design)

Ship the Guard with the model as part of the exact Q5 package. Proposed
PRD-02 inputs: validated package/contract/envelope/map identities, model callable,
query plus context/units, and an accepted guard policy. It checks every query:
input and physical/model applicability; cheap adopted-law probes around the
query; trust-map cell and marginalized-context coverage; and model uncertainty
when the policy requires or supports it. Probe construction stays inside its
declared applicability, with a deterministic probe set derived from query,
policy version and contract, and a bounded cost. Record its seed derivation and
identities in the local receipt so repeated queries replay the same verdict.
No official seeds, protected data, arbitrary contract code or solver call is
needed for an inline law check.

Only adopted laws with registered, image-bound tolerances are Guard verdict
inputs. Unadopted or uncalibrated laws remain separately labelled diagnostics;
they do not force every query into VERIFY. Their proposed thresholds cannot
become production policy through a document or source-projection flag.

| Verdict | Required meaning | Buyer workflow |
| --- | --- | --- |
| TRUST | Exact identities and approved use/policy hold; all mandatory checks resolve favorably, coverage is adequate and accepted risk rules permit the surrogate | Advisory output inside this scoped policy; still no universal accuracy/physical guarantee |
| VERIFY | Surrogate evidence is insufficient or doubtful, but an independently verified reference route supports the query and authorized verification can resolve the question | Candidate output is provisional; request solver verification before using it as an accepted decision |
| REFUSE | Invalid input, absent/mismatched controlling identities/policy, unsupported reference applicability, unavailable required authority, or no authorized path to resolve a required failure | Return no actionable recommendation; record the reason and route to the responsible human |

An in-envelope law violation or low-trust cell prevents TRUST; use VERIFY only
when the reference can resolve it. Outside the surrogate envelope, VERIFY is
permitted only if the separately accepted solver envelope supports that query;
otherwise REFUSE. Unknown physical validity cannot be treated as in-range.
Missing mandatory outputs, unresolved neighbor probes, absent/stale maps,
uncalibrated required intervals and failed checks never default to TRUST.
If uncertainty is unavailable, report GAP and apply the explicitly registered
no-interval policy, if one exists. Do not manufacture a confidence value.

Return verdict, machine-readable reasons and a human explanation, check results,
coverage/missing evidence, policy and artifact/map/contract versions, measured
latency and suggested verification route. Preserve FAILED_REFERENCE/FAILED_INFRA
as supporting outcomes. Log only customer-authorized local audit data; no
telemetry is assumed. Receipt detail and retention follow disclosure/rights policy.

TRUST eligibility, probe neighborhoods/counts, per-law budgets, map support,
uncertainty rules and latency target are HUMAN_INPUT. PRD-02 must report its
measured overhead and an owner-approved latency target in the PB-LAT record;
this design supplies no guessed milliseconds. Development tests use clearly
isolated fixture policies and cannot issue production trust or Q2 qualification.
PB-ESC/ADV/ART/LAT must assess erroneous TRUST, refusal/escalation behavior,
identity tampering, missing evidence, near-boundary cases and runtime parity.

**PRD-02 development implementation (prospective, 2026-10-12).** The
[development Guard](../../../carbon/product/envelope_guard/README.md) wraps
native trust-map aggregates and validity declarations, with fixed local probes,
explicit policy/calibration records and typed advisory receipts. It exposes
DEVELOPMENT scope only; the public battery-interface demonstration uses
synthetic predictions and synthetic policy/acceptance/validity records. Main's
actual battery Undeclared validity remains a hold. Record/digest bindings are
host assertions, not authenticated scientific acceptance or qualified runtime
parity. Supported initial primitives are bound, initial_condition and
prefix_invariance; other adopted primitives require an explicit future adapter.
The [toy timing record](../../../docs/development/product/envelope_guard/latency-fixture.json)
binds the measured implementation bytes. Actual-model PB-LAT acceptance and
the production latency target remain HUMAN_INPUT, as do product qualification
and the composition evidence needed for Assistant-selected picks.

## 11. CMP-09 — Decision Assistant (new workflow design)

Proposed PRD-03 inputs: exact question law/action grammar, buyer objectives and
mandatory constraints, guarded model/package, budget and reference-verification
route. Run search within the supported design grammar, apply Guard per candidate,
rank provisional admissible top-k, and return a verification plan and audit
record. The Assistant cannot choose acceptance limits or its own evidence ruler.

Charge model queries, probe overhead, preprocessing, search, I/O, startup and
reference requests to the declared wall/core/verification budget. Stop at the
budget with measured spend and uncompleted work visible. k, budget, search
policy and tie/abstention rules are versioned; customer values are HUMAN_INPUT.
Cheap public baselines and solver-only search use equivalent job and accounting.

Among shortlisted candidates that an applicable solver can resolve, prioritize
verification where trust is lowest; uncertainty crossing a limit can prioritize
verification only when its calibration is established. Refused designs never
become actionable picks. Freeze the search/ranking before independent decision
assessment. Keep provisional and solver-verified rankings separate; re-evaluate
feasibility on the reference before naming a verified choice. An unavailable
reference or exhausted verification budget returns unresolved/abstention and
the remaining plan, not a verified recommendation. Report proven NONE_FEASIBLE
only when the registered question law's evidence establishes it.

Search concentrates on optimistic model errors; pooled trust-map error may
understate error on the selected candidates. A map/Guard TRUST verdict can
order verification, never replace solver verification of the Assistant's
picks. PB-INV/ADV must measure false feasibility on those picks themselves.
The Validator's RES-06 bypass example keeps unsafe picks after visible law
checks pass: adopted gates still do not certify design safety.

Expected regret is an estimate requiring an independently assessed, matching
question population, units, policy and budget, with its uncertainty/basis.
Without that evidence return null / GAP, not zero and not a model's self-rated
regret. After evaluation, report realized reference-relative regret separately
and state whether the comparator optimum is finite-bank or globally established.
The audit binds inputs permitted by custody policy, question/strategy versions,
candidate/Guard summaries, spend, verification receipts, changes of rank and
adverse outcomes. Customer-local search data does not enter the official exam.

PB-INV tests the complete workflow under equal budgets; PB-ADV searches for
false feasibility/law failures; PB-ESC tests refusal and fallback; PB-ART/LAT
test the deployed composition. A model that passes its component tests does
not qualify an optimizer/Guard composition. Value is demonstrated only from
measured solver-verified workflow outcomes, including negative comparisons.

**PRD-03 development implementation (prospective, 2026-10-12).**
`carbon/product/decision_assistant/` wraps the Guard, native budget ledger,
public battery observer and equal-budget replay with bounded finite-bank search,
pre-reference ranking/plan commitment, independent selected-pick verification,
typed abstention and audit. Map TRUST never substitutes for verifying a pick.
Selected false feasibility retains resolved/unresolved denominators. Expected
regret stays null/GAP without matched independently assessed evidence; realized
regret is separate complete finite-bank reference work. Public-record replay
cannot produce a fresh verified recommendation. The synthetic demonstration
retains an adverse smallest-budget comparison and earns no physical claim.

The owner expressly permits the real battery comparison to remain GAP for this
ticket: the named public calibration copy lacks CPU core-seconds and its solver
is not accepted for that use. Its 800 byte-bound records support only a labelled
DEVELOPMENT wall-cost estimate. Show SOLVER_NOT_ACCEPTED and `accepted: false`;
do not override the current hold with older MMS/manifest text or infer core cost.
No real solver/training, protected material, qualification, deployment or LIVE
authority is exercised. Policies, physical applicability, current-use reference
acceptance, full cost metering and actual-model PB evidence remain HUMAN_INPUT.

## 12. CMP-10 — lifecycle and change handling

Retain independent versions for artifact/runtime, question/physics contract,
envelope/population, observers, map, Guard/Assistant policy, Product Battery,
qualification policy and delivery manifest. A changed physical/scoring contract
is prospective. Corrections/supersession never rescore or erase old evidence.

| Trigger | Required assessment and bounded response |
| --- | --- |
| Solver image rebuild/re-pin | New code verification/acceptance and observable calibration; hold dependent TRUST/claims until matching evidence exists |
| Envelope, material, data or usage drift | Assess evidence applicability, changed P/Q/w, map coverage and reference/physical gaps; suspend affected claims and re-evidence under the governing policy |
| Model retrain/adaptation, preprocessing, precision or export/runtime change | New artifact/card identity when materially distinct; parity and affected PB re-tests; no inherited qualification by name |
| Guard/map/Assistant or question-policy change | Assess the deployed system, decision behavior, verification cost and failure coverage; qualify composition where required |
| New adverse finding, law failure, unresolved reference or dependency incident | Preserve finding, identify affected use, refuse/escalate that scope, investigate and obtain scoped new evidence/decision |

Q3's exact lifecycle enum/transitions and Q6's material-change/continued-use
policy require human ratification. Drift thresholds, monitoring frequency,
response times and responsible roles are HUMAN_INPUT. Development can exercise
change records, not automatically renew, revoke or sign a scientific claim.
Unaffected historical observations remain attributable to their original use.

## 13. CMP-11 — high-rigour and defense deployment

Design for an offline/air-gapped package: model and wrapper, pinned runtime and
dependency lock, SBOM/build provenance, local evidence viewer and solver adapter,
installation/verification recipe and full fallback instructions. Test clean-host
offline installation, disabled network/telemetry, deterministic software builds,
artifact verification, permissions and measured runtime parity. Deterministic
builds and bounded training reproducibility are different evidence obligations.
No external service or API key is required for the proposed offline path.
Air-gap capability is designed, not demonstrated or security-audited here.

Default posture follows [Customer Bounds Specialist](../../../Design_Specs/Customer_Bounds_Specialist.md):
bounds in; customer CAD, logs, physical data and proprietary trajectories remain
on the customer's host. Validation/adaptation runs there under an approved
agreement. Any return of aggregates, reuse, retention, residency, support access
or Carbon-assisted work needs explicit rights and data policy (HUMAN_INPUT).
Customer-side adaptation does not retain the original product claim automatically.

Disclosure follows Q4: public catalog gets approved coarse identity/claims and
limitations; buyer gets approved artifact/runtime and relevant evidence;
private/authorized audit retains controlled recipes and restricted diagnostics.
Each delivered projection records its allow-list/version and approval. Never
bundle hidden exam material for transparency. Training-recipe delivery depends
on actual licensed rights, not the buyer paying a fee.

Include ITAR/EAR applicability/classification, distribution, end-use/end-user,
licence/authorization, jurisdiction, contract, IP, liability, confidentiality,
retention and acceptance-authority slots, all **HUMAN_INPUT**. Flags indicate
pending legal review, not a legal classification. If required legal/disclosure
permission is absent, affected delivery is blocked. Public-data development
does not establish export clearance, defense procurement eligibility or
customer-host security acceptance. No legal or standards-compliance claim is made.

## 14. Gap and maturity table

Designed means described here or in a cited existing specification. Implemented
and tested refer only to the narrow source component named below; they are not
whole-package maturity. This ticket runs no models, solvers or scientific tests.
No customer package in the inspected sources is established as scientifically,
security, commercially or production qualified. Later evidence must update
these observations prospectively with exact identities.

| Element | Designed | Implemented at baseline | Test/evidence basis at baseline | Qualified package state / next gap |
| --- | --- | --- | --- | --- |
| CMP-01 Artifact | Yes; Q0/Q5/PB-ART/LAT | Reconstruction/runtime pieces exist; complete product bundle not established | Historical rebuilds differ from exact customer export/Guard parity | UNESTABLISHED; fresh artifact, parity, runtime and accepted recipe rights |
| CMP-02 Physics report | Yes; four packet drafts | Draft metadata advisory; adopted general law-check report not established | Packet/checker engineering checks; limited owner-accepted MMS routes; no law calibration by this ticket | UNESTABLISHED; adopted laws/outputs/validity, matched calibration and accepted reference adequacy |
| CMP-03 Model card | Yes; existing role plus added fields | Existing evaluation/card/timing pieces; v2 product card/floors incomplete | Historical scoped development metrics; new required rows may be GAP | UNESTABLISHED; all applicable rows, registered floors, independent fresh product evidence |
| CMP-04 Map | Yes; PLT-05 plus extensions | Error/disagreement DEVELOPMENT core and battery adapter | `tests/cpu/test_trust_map.py` defines synthetic checks; no measured package map supplied by PRD-00 | UNESTABLISHED; accepted reference projection, law/interval layers and Guard policy |
| CMP-05 Decision evidence | Yes; VALUE-BAR/equal-budget | Development evaluator and replay; safe complete package join missing | Existing component tests and historical decision evidence retain adverse outcomes; replay is not live search | UNESTABLISHED; exact product/held-out joins, measured costs and customer value evidence |
| CMP-06 Dossier | Yes; D01–D11 and crosswalks | Generator indexes provenance/standards and gaps; risk plan/defense view not automated | `tests/cpu/test_customer_deliverable_generator.py`; metadata rendering does not assess credibility | UNESTABLISHED; agreed risk, licensed/tailored clause review, physical evidence and authorized judgment |
| CMP-07 Audit | Yes; Q records and extensions | Public source ledger/digests; integrated signing/corrections/SBOM package not established | Generator byte/identity/adverse-retention tests are bounded engineering evidence | UNESTABLISHED; package custody, accepted signing authorities and complete runtime inventory |
| CMP-08 Guard | Yes; new design | Not implemented by PRD-00 | NOT_RUN; PRD-02 owns development implementation and tests | UNESTABLISHED; policy, applicability, probes, verdict/system tests and measured latency |
| CMP-09 Assistant | Yes; new design | Not implemented by PRD-00; replay is an input | NOT_RUN; PRD-03 owns development workflow tests | UNESTABLISHED; actual search, verification/regret basis and complete budget accounting |
| CMP-10 Lifecycle | Yes; Q3/Q6 | Complete package transition/enforcement not established | Package lifecycle tests NOT_RUN | UNESTABLISHED; exact human-owned states, triggers, operational responsibilities |
| CMP-11 Deployment | Yes; existing air-gap/data posture | Full v2 offline composition not established | Clean-host package/air-gap/security acceptance NOT_RUN | UNESTABLISHED; offline evidence, rights, export review and customer deployment acceptance |

## 15. Minimum viable first-pilot package

The nearest useful milestone is a **battery DEVELOPMENT_SAMPLE diagnostic
package**, following the existing pilot plan: one named offline screening job,
all D01–D11 sections, an identity/source manifest, law-check skeleton,
model-card rows, public error/disagreement map if its inputs are eligible,
historical decision/adverse annex, risk/requirements matrix and standards
crosswalk. Every absent artifact, measurement, floor, physical referent and
approval remains GAP/HUMAN_INPUT. Eligible tier stays UNESTABLISHED; a sample
cannot substitute for an EvidenceAudit's agreed and qualified prerequisites.
PRD-01 automates this assembly, battery first then f02/motor/cooling.

The first executable shadow pilot additionally needs a fresh exact candidate,
accepted applicability/reference and adopted required checks, tested Guard and
Assistant, an authorized solver route and budget, PB-ART/LAT/INV/ADV/ESC evidence
plus every other mandatory PB module, and a customer-owned comparison/review
plan. It runs advisory offline search and verification on authorized public or
customer-host data. No critical operational use, physical acceptance or
production claim is inferred. An adverse result or a cheap-baseline win remains
a legitimate pilot outcome. Any stronger product claim follows the Q1 → Q2 →
Q5 chain and appropriate human acceptance, rather than a pilot-success flag.

PRD-00 completion is a design-only PR to main, applicable green automated
acceptance, an exact-head Ready for PR Head handoff and the local queue report.
It does not complete Q0–Q8, start PRD-01, merge, change LIVE or grant deployment.
The current delivery protocol retires the Hub: no map/event/regeneration change.

## 16. HUMAN_INPUT decisions for the owner

| Decision | Smallest required input / responsible route | Affected use while absent |
| --- | --- | --- |
| Intended first job and reliance | Named customer/engineering decision, action grammar, error consequence, accepted population/envelope and pilot scope; customer plus science | Diagnostic sample only; customer claims unestablished |
| Physics and reference | Adopted laws, output/validity contract, verified route/observable uncertainty and calibration/gate-screening acceptance; science/Carbon Validator and Data Collection | Required law/applicability unresolved; no TRUST or scientific pass |
| Floors and evolution | Each card floor, applicability/mandatory status, tolerances and any proposed ratchet adoption; science/owner | Null criteria; no automatic eligibility or crown decision |
| Guard policy and latency | Coverage, uncertainty/no-interval policy, reference fallback, probe budget and latency target; product/science/customer authority | Missing required policy prevents TRUST; unsupported resolution REFUSE |
| Artifact/runtime evidence | Export-parity and rebuild-agreement tolerances, supported runtime/hardware acceptance; product/runtime and science owners | Exact deployable artifact claim unestablished |
| Disclosure projections | Q4 public/buyer allow-lists and their designated approver; rights/security/product owners | Affected evidence projection or delivery blocked |
| Standards review | Applicable editions, tailoring, licensed clause review and responsible acceptance authority; customer/assurance owner | Crosswalk only; compliance/accreditation unestablished |
| Guard audit handling | Local audit-log retention, telemetry policy and responsible approver; customer/privacy/security owners | No telemetry or retention authority inferred |
| Assistant/value | Search/verification budget, k, abstention and expected-regret evidence; question/value and customer owners | No accepted recommendation or claimed value; missing regret null |
| Credibility/physical evidence | Risk categories, required credibility, referents, independence, uncertainty and acceptance authority; assurance/customer | Physical validation and accreditation unestablished |
| Lifecycle/security/deployment | Exact Q3 states, material-change/drift triggers, incident responsibility, signing trust and deployment/security acceptance; owners | Affected continued-use/delivery blocked or explicitly development-only |
| Legal, data and rights | Licence terms, recipe/artifact/evidence rights, customer-host/aggregate access, ITAR/EAR/export flags and distribution authority; owner/counsel/customer | No rights inferred; affected transfer or reuse blocked |
| Commercial scope and price | Pilot SOW, deliverables, funding/budget, price, SLA/support and commercial acceptance owner | No tariff, sale, paid pilot or traction claim |

These missing inputs constrain later use, not completion of this bounded design.
The owner can review the package proposal without being asked to qualify its
science, accredit a model or authorize implementation of every subsequent item.
