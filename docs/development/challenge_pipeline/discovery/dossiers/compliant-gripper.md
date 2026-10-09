# Compliant gripper: conditional common design packet

CHALLENGE-DISCOVERY-01 / D071; conditional queue position 5. **No admitted finalist; no dispatch/spend grant; adoption HUMAN_INPUT.** This follows the [common packet's ten sections](../sources.md) and adds a question-law sketch, first panel and comparison. This is a research draft for a possible customer packet; it does not prove actual fit without the required customer inputs. Every estimate/count proposal below is **ASSUMPTION**, with low/base/high shown or a degenerate range for a fixed draft count. No scientific limit is set.

## 1. Engineering job

A robot end-effector engineer chooses a compliant finger/frame geometry to grasp a specified family of known objects while respecting actuator, strain, package and object-contact limits. Independent gripper research shows FE-driven geometry optimisation (GRIP1) and contact-based soft-gripper/frame search (GRIP2). These are adjacent jobs: public research does not yet establish the same current customer's decision.

Buyer role: **Robot end-effector engineer**. Proposed decision: **Choose finger/frame geometry for known objects**. Independent role/workflow evidence: [GRIP1: Monolithic-gripper research authors](https://pmc.ncbi.nlm.nih.gov/articles/PMC6843576/); [GRIP2: Xie, Wang, Iida and Howard](https://arxiv.org/abs/2311.12477); [GRIP3: Reduced gripper modelling authors](https://arxiv.org/abs/2303.12987). Manufacturer and independent research origins are distinguished; neither is a confirmed Carbon customer. Buyer identity/authorised contact, actual current simulation tool, decision latency/cadence, allowed materials/data rights, acceptance criteria and value interview are **HUMAN_INPUT — business/customer owner; blocks G1/adoption**.

V2 proposed avoidable effort 2.00 / 6.00 / 16.00 hours/revision × 60.00 / 90.00 / 120.00 EUR/hour gives 120.00 / 540.00 / 1920.00 EUR/revision. V3 assumes 5.00 / 20.00 / 50.00 teams × 4.00 / 12.00 / 24.00 revisions/team/year = 20.00 / 240.00 / 1200.00 revisions/year. These are conditional cohort scenarios, not buyers/market size, actual savings or willingness to pay. Demonstrated commercial floor is zero.

## 2. Physical system

A bounded compliant/soft-finger gripper with approved elastomer/flexure material, frame geometry, prescribed approach/actuation sequence, rigid or explicitly modelled objects and contact. Fix the finger architecture and object family before any bank. Do not claim general grasp success, human contact safety or unknown-object transfer.

Mandatory-stratum hypothesis (count [3,3,3]):

- approved nominal object/friction family: numerical endpoints, joint conditions and source HUMAN_INPUT.
- approved low-friction/geometry-tolerance family: numerical endpoints, joint conditions and source HUMAN_INPUT.
- approved delicate/high-contact-load object family: numerical endpoints, joint conditions and source HUMAN_INPUT.

Scientific owner must confirm that these strata cover the unchanged customer job. Initial/boundary conditions, histories, idealisations, material applicability, neglected physics and manufacture/assembly tolerances are HUMAN_INPUT. A missing safety/material requirement stops the affected job; it is never relaxed to save compute. No physical population claim follows from deterministic execution.

## 3. Population P, Q and w

**P — customer request population.** The buyer's actual object and grasp-job population, including object shape/size, friction, allowable contact force, actuator history, material and manufacturing variation. Job/object correlations and probabilities are HUMAN_INPUT. Geometric object variety in a paper is not a production law.

**Q — diagnostic/acquisition proposal.** Enrich changes in contact topology, object loss, excessive strain and force limits. Include adversarial cases for the reduced gripper model, within approved object/material support. Q object frequencies remain separate from the buyer's P.

**w — evidence/score use.** Sampling/evidence weighting and any correction from Q to P are **HUMAN_INPUT — scientific owner**. Prospective per-stratum admissibility and reporting precede any ranking. Equal diagnostic counts are a collection convenience, not deployment weights. No soft objective can compensate for a mandatory failure.

Freeze a versioned population contract with joint variables, support, dependencies, strata/mixture probabilities, rights, exclusions, time validity and applicability. Keep request-job law distinct from the finite design menu conditional on that job. Request population and design-generation process are not interchangeable. No public draw is a hidden/protected exam draw; this researcher defines or accesses neither.

## 4. Case contract

Owned finger/frame CAD; material curves and applicable strain range; actuator limits/sequence; object models and compliance; friction/contact law; package/manufacturing constraints; object-force and gripper-strain limits. All numeric limits, movement histories and safety constraints are HUMAN_INPUT.

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

## 5. Reference policy

Primary SOFA scene consistent with GRIP2's contact FE route, with individually reviewed LGPL/plugin/material dependencies and headless Linux build. Pin scene, contact formulation and extractors for force/strain. Independent buyer mechanical FE (possibly CalculiX if applicable) or existing non-clinical mechanical measurements is the planned witness. Reference damping/quasi-static limits and all tolerances are HUMAN_INPUT.

Open route: [SOFA: SOFA consortium](https://www.sofa-framework.org/). Pin reviewed open licence/dependencies, source revision, container digest, compiler/math environment, meshing/solver/deck/material versions and extraction definition. None is supplied here as a fake immutable pin. Reproducibility within documented tolerances is necessary; physical adequacy is separate.

Credibility **earned: NOT_DEMONSTRATED**; target: framework Tier 2 via an applicable independent buyer tool. Tier 3 would require applicable physical experiments and their own rights/budget/acceptance; it is not priced or earned by this report. A successful balance or cross-tool check is evidence for an owner, not qualification itself.

Infrastructure failures preserve FAILED_INFRA/retry/non-scientific semantics. Nonconvergence, inappropriate constitutive law, extraction ambiguity or failed physical balance are reference inadequacy/UNRESOLVED and never candidate scientific failure. Stop grading until the affected reference is adequate. Tolerances, uncertainty bands, convergence thresholds and credibility acceptance are **HUMAN_INPUT — reference/science owners**.

## 6. Output and measurement contract

Force/displacement/strain/contact state through the complete prescribed approach/actuation/grasp history for the case's registered object set. A single stable final pose is not a complete dynamic or quasi-static grasp decision. Define retention metric and field sampling prospectively; do not grade a paper's fitness without the buyer contract.

Hard-limit family: Customer minimum retention/required displacement, maximum object contact force and material strain, actuator load/travel and package/manufacturing limits. No delicate-object limit or robot safety limit is relaxed. If human contact/dynamic safety is the actual job, this mechanical screening packet is incomplete and must be rejected or expanded by owners.

Freeze each quantity's units, sample locations, aggregation, sign convention, mask, extrema treatment, applicability and reference uncertainty. Register output field/array shape and the decision projection prospectively. The same definitions and limits apply to reference, strongest cheap baseline and model. Measurement definition, qualification, applicability and score use are distinct approvals.

Admissibility must be established for **every required output in every mandatory stratum** before the customer's objective can rank actions. Near-infeasible means outside a prospectively approved uncertainty/refinement band for a specified hard limit while other mandatory conditions are respected; ambiguous reference signs remain UNRESOLVED. No new scalar score, scientific tolerance, safety factor or loss-based exemption is authorised. Customer objective: Customer tradeoff among fully admissible fingers, such as material/actuation effort or object-contact margin, is HUMAN_INPUT. No universal grasp-quality scalar is invented.

## 7. Construction contract

Research a fast model predicting the frozen physical outputs/decision projection from allowed geometry, condition and material inputs. The current bounded Carbon search surface is neural-operator **TrainingStrategy**, subject to its current contracts. This draft does not widen it to arbitrary solver/code execution or a future ModelConstructionStrategy.

Parameterised geometry generation, meshing, reference runs and official grading remain owner-controlled. Learners can use only authorised public research examples/features under reviewed licences; exact permitted inputs, architecture/dependency/compute bounds, training split and geometry-to-fixed-output representation are **HUMAN_INPUT — construction/security owners**. No private samples, hidden seeds or reference authority are provided to participants. Any prototype stays developmental and structurally unable to emit LIVE ranking/frontier/treasury/product authority.

Strong baseline: **pseudo-rigid-body/co-rotational gripper model (GRIP3) plus contact-aware response surface and the buyer's existing family library**. Incremental-value hypothesis: object-dependent contact topology may leave a decision residual beyond a calibrated reduced model. SOFA's interactive speed is itself a warning that full reference decisions could already be cheap. Complete acquisition/build/fit/search/verification and retained high-fidelity calls must be counted for both alternatives. A good imitation of an inadequate reference is not a useful model.

## 8. Research kit

Proposed public kit only: source-linked solver documentation, independently licensed geometry/material examples, canonical explanatory schema, output/measurement definitions, baseline specification, openly generated diagnostic cases and failure-report format. Release actual files only after owner rights/applicability review. It contains no official bank, private metadata, seeds, protected samples, reversible draw identities or AX42 material.

Training/support/domain claims require separate authorisation. Include both cheap-baseline and reference costs, convergence diagnostics and known limitations in public research reports where disclosure allows. A practice kit remains incomplete and cannot substitute for the independent exam. No kit is built or solver installed by this researcher.

## 9. Evidence plan

Before any new collection: get a real customer job with unchanged sourced limits and rights; confirm the open route exactly produces the needed outputs; check independent reference applicability and the buyer's actual current latency; and obtain the baseline's cheapest complete decisions. Source-first work may reject the candidate without a solve.

Then a separately authorised Data Collection task can run the panel below. It must demonstrate refined feasible witnesses and prospective contested counts per stratum before a full bank. Qualification owners choose tolerances, T3 power, alpha, effect severity, question law and reference acceptance. These are HUMAN_INPUT, not selected from cheap runtimes.

Full-bank hypothesis: designs [24,24,24], strata [3,3,3], primary cases [72,72,72], refined cases [24,24,24] at multiplier [2,2,2], charged failed attempts [15,15,15], independent witness pairs [8,8,8] with two tools each. Total equivalent complete cases U=[151,151,151]. This draft budget is not proof that the menu has the required feasible/near-infeasible counts.

C1 complete-case CPU-hours **0.03 / 0.08 / 0.20**, RAM GiB **1.00 / 4.00 / 12.00**; p50/p95 and elapsed/CPU ratio are NOT_MEASURED. Charged startup C2 **EUR 23.91 / 36.22 / 65.76**, under the [common formula](../methodology.md). All estimates are ASSUMPTION. Witness licence assumption is zero incremental charge only if the buyer has rights/access; otherwise reprice and reject if the cap fails. No spend is authorised.

V4 compares analytical/library, interpolation, calibrated response surface, reduced physics and actual buyer tool at matched admissibility, with complete overhead and retained verification over M=[1,10,100] served revisions (ASSUMPTION sensitivity). Acceptable false-feasible rate, regret/decision agreement and economic threshold are HUMAN_INPUT. An equal cheap decision, infeasible stratum or unqualified reference stops admission. The discovery estimate screen fits EUR100, but an actual bill above the cap stops the proposed bank.

## 10. Readiness and claim record

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

## 11. Question-law sketch

**One question** is one real customer request/job version, unchanged hard limits and all mandatory strata, together with a finite approved geometry/action menu. The answer selects an admissible action according to the approved customer objective, or returns NONE_FEASIBLE/UNRESOLVED. Registered finger/frame geometry variants for the same actuator, object ensemble and material family. Objects, required retention and permissible strain are not participant-controlled actions.

Propose menu N=[24,24,24] for the bank scenario; this is a candidate count, **not k**. Propose exploratory question batch k=[4,8,12] complete questions as an ASSUMPTION sensitivity; k is neither a power calculation nor adopted law. Test Lead owns final k, question pool size, alpha/control/effect choices and question turnover. The first triage panel below is one diagnostic job/menu, not evidence of question diversity or k independent buyer questions.

P draws actual jobs; Q enriches diagnostic jobs/actions with separately reported strata. Freeze valid menu eligibility and prospective question/answer rule versions. Report distinct winners/actions, active limits, ties, duplicate exposure, feasible/NONE_FEASIBLE/UNRESOLVED counts and per-stratum P/Q coverage. A nearly constant winner is a value/learning warning even if every design solves.

Proposed NONE_FEASIBLE handling: retain valid forward P questions; never redraw until feasible. NONE_FEASIBLE requires every eligible menu action to have a certified hard failure in its full registered conditions. A single unresolved action/reference prevents that terminal conclusion unless it is already independently proven infeasible on another mandatory limit. Infrastructure failure never counts as infeasibility. No global physical infeasibility is inferred beyond the menu. This is a draft recommendation; actual status/score treatment remains HUMAN_INPUT.

Require at least five feasible and five near-infeasible designs in **each** mandatory stratum under the prospective one-band screen, plus explicit full-job all-strata feasibility. Counts or question diversity cannot be manufactured by widening limits, uncertainty bands, changing objects/current/load or dropping a required stratum. Report any two-band draft sensitivity separately without changing admission.

## 12. First feasibility and value-check panel

**Recommendation for Data Collection after separate owner authorisation; no runs or spend here.** Start with the source/customer-limit/reference preflight. If it fails, stop with HUMAN_INPUT; do not buy compute.

Proposed minimal triage budget (each fixed count has a degenerate low/base/high):

| Work | Count proposal | Purpose |
| --- | --- | --- |
| Registered action candidates | [10,10,10] across every proposed stratum | Mix handbook/circuit-selected and plausible boundary actions without presupposing feasible labels |
| Primary full cases | [30,30,30] | Complete outputs/limits per stratum; test any feasible witness first |
| Refined full cases | [6,6,6] at [2,2,2] cost | Recheck prospective boundary/witness designs; do not certify all cases from this subset |
| Diagnostic controls | [4,4,4] complete-case equivalents | contact-free compliance, known simple-object contact balance, actuator work balance and contact-topology transition within approved force/strain bounds |
| Independent witnesses | [4,4,4] case equivalents, two paired designs | Independent mechanical model or owned fixture measurements on contrasting object/finger pairs. Force/strain applicability and object rights must be established before claiming Tier 2 or Tier 3. |
| Charged failed attempts | [4,4,4] case equivalents | Bound the cost hypothesis; real failures beyond allowance are charged and reprice the panel |

Equivalent complete cases U_panel=[54,54,54]. Using the same C1 and setup/tax/reserve/serial assumptions gives **first-panel EUR 19.16 / 23.56 / 34.13**, low/base/high ASSUMPTION, including the baseline fit/benchmark allowance in the common setup reserve. If independent-tool charges, fit time, extra conditions or retries exceed allowances, reprice before approval. This is an alternative early-stop bill; do not add its setup twice when reusing cases in the full bank. Physical experiments and human labour are not priced.

Return: sourced unchanged limits, every action's per-stratum margins and unresolved states, converged feasible witness or explicit lack thereof, actual feasible/near-infeasible counts, reference checks and discrepancy, complete CPU/wall/RAM/failure ledger, actual bill, and strongest cheap-baseline same-decision audit. Ten actions are only the theoretical minimum for five plus five; no successful counts are presumed. If inadequate, stop or propose a priced additional panel within the cap; never enlarge scientific bands to reach counts.

Only after this triage should a separately approved bank proceed with all necessary refinements, witnesses and power/coverage evidence. First-panel cost is not a full-bank C2 receipt and its small timing sample cannot establish a p95 tail.

## 13. Comparison with current eight and #921

New hypothesis, base scenario index above #921 air-heat-sink/duct and below solenoid/seal/joint. It has weaker exact-buyer evidence and a strong cheap reduced-model incumbent. Frontier/robotics excitement cannot repair that gap or justify replacing a current task.

Under the same explicit index `I=(V2×V3)/(C2+52×C3_weekly)`, this dossier's **ASSUMPTION** index is **1.67 / 577.19 / 41902.45** and C3 is **EUR 0.60 / 3.62 / 26.30/week**. The scenario base diagnostic rank is 6; excitement 3.33 / 4.33 / 5.00 is a tiebreaker only. No eligible/admitted rank exists.

See the [complete same-index comparison](../comparison.md): all eight current tasks have missing complete C2/C3 and a USD scenario basis, so their index is NOT_COMPUTABLE. No exchange rate, absent cost or scientific-score comparison is invented. Existing motor feasibility, f08/cooling cheap-baseline, f13 reference/cost and f06 latency failures inform this preflight. No new candidate is demonstrated to beat them. The owner may retain current tasks or #921 and reject this proposal.
