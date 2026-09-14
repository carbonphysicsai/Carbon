# Carbon Fit: Feasibility, Qualification and Roadmap Decisions

**Working proposal v0.2 | 11 September 2026 | Carbon Science & Research**

**Purpose:** decide which opportunity deserves the next unit of effort, which evidence to obtain first, and which claim Carbon can defend. This is the decision companion to `Carbon_Model_Construction_Neutrality_Roadmap_v0_1.md`, not a replacement for its construction taxonomy.

**Authority:** planning only. No repository edit, active ticket selection, production threshold, sampling law, solver tolerance, cadence, reference-reuse authorization or scientific qualification follows from this document or the companion workbook.

## 1. Recommendation

Use a **bottleneck-first feasibility review** with a six-check Carbon Fit Card and a small calculator. Keep the engineering evidence behind the card. Rank the next decision-changing investigation, rather than assign one universal numerical score to architectures.

The unit of assessment is an exact proposal:

> Client job + intended claim + deployable baseline + candidate construction + reference process + resource/cadence profile.

A reusable component can have a capability record. It earns Carbon fit only in a compatible job and execution context. A reference is not fast, accurate or independent merely because its method has those associations in another setting. A construction can fit a long-form program while failing the turnaround requirement of a frequent program.

The card should let the owner state: **proceed to a bounded test; seek pilot review; redesign; park until a named dependency arrives; decline the present scope; or use the existing baseline.** None means LIVE or product-qualified.

## 2. Six checks, without compensating averages

| Check | Decision question | Main evidence owner |
|---|---|---|
| Job and permissions | Can we define the output, causal inputs, operating population, decision and lawful/permitted access? | Client owner, Science, Security/rights owners |
| Reference | Can we produce evidence of adequate accuracy and independence at the required decision resolution, within the reference program's resources? | Science with reference implementer |
| Construction | Can validators reconstruct this exact method under a pinned, bounded, isolated contract? | Engineering with Science/Security |
| Exam | Can we complete the required evidence program within its budget and cadence, including difficult cases and failures? | Science and Operations |
| Deployment | Does the exact resulting system meet the client's physical, latency, throughput, memory and escalation requirements? | Engineering and product qualification owners |
| Value | Does the candidate improve a declared requirement against a credible deployable alternative, with defensible lifecycle economics or a separately evidenced capability benefit? | Strategy/client owner, informed by Science |

Use three evidence states on each check: **SUPPORTED FOR THIS STAGE**, **UNKNOWN**, or **BLOCKED FOR THIS SCOPE**. Attach the claim, source, scope, date and accountable owner. "Supported" at scoping means enough evidence to justify a bounded investigation; it does not establish a product claim.

Keep all blockers visible. Identify one next decision-changing test, but do not hide a second fatal prerequisite. A cheap experiment on an irrelevant secondary issue does not resolve a reference or rights blocker.

A numerical margin cannot compensate for a mandatory physical failure, missing permissions, reference inadequacy or an unqualified exam. Unknown is not a failure and not a favorable default. [C1–C5]

## 3. The small set of computable terms

### 3.1 Margin to an entered requirement

For a positive upper limit L and a nonnegative quantity x with an evidence-supported range [x_low, x_high], report:

    worst_headroom = 1 - x_high / L
    best_headroom  = 1 - x_low / L

For a positive minimum requirement L, report:

    worst_headroom = x_low / L - 1
    best_headroom  = x_high / L - 1

Examples include reconstruction time, peak memory, full exam turnaround, cost and deployment throughput. The workbook keeps the comparator explicit: <, <=, > or >=. Zero headroom is a boundary whose treatment comes from that comparator. It does not override Carbon's official Score Pack semantics.

Positive headroom means the entered range lies on the favorable side, subject to the comparator. A negative worst margin can mean either a conflict across the whole range or an unresolved overlap. The workbook distinguishes these cases.

The smallest known margin helps locate numerical pressure. It is not a readiness score or a calibrated risk measure. Missing rows remain UNKNOWN; qualitative blockers can dominate known numeric margins. Bands are scenarios unless the evidence defines their statistical coverage. Do not call several independent marginal bands a joint confidence guarantee.

### 3.2 Physical decision resolution

Record the uncertainty in the actual comparison, not just a solver's residual or tolerance. Reference bias, discretization, representation, measurement, finite sampling and reconstruction variation may all matter. Their dependence must inform the combination; do not add standard deviations or error components without a justified model.

Science should determine whether that uncertainty permits the registered decision. A cheap reference unable to resolve the claimed improvement is inadequate for that claim. A ratio of uncertainty to a proposed improvement can help diagnose the issue, but no universal ratio establishes qualification. An unresolved comparison remains indeterminate. [C1, C2]

### 3.3 Exam time and expenditure

Maintain two quantities:

    elapsed turnaround = completion time of the authorized dependency graph
    expenditure = sum of attributed resource costs under a stated pricing model

Turnaround includes actual queue, startup, compilation, data readiness, construction, reference, inference, measurements, evidence finalization and registered retry/replication behavior where applicable. Estimate it with a measured or simulated dependency/resource schedule. Adding each stage's tail percentile does not produce an end-to-end percentile. Parallelism can shorten elapsed time without reducing resource expenditure.

A homogeneous program planning model is:

    number_of_batches = ceil(planned_comparisons / permitted_comparisons_per_batch)
    program_cost = setup_cost
                 + number_of_batches * reference_batch_cost
                 + planned_comparisons * (reconstruction_cost + other_comparison_cost)

This arithmetic assumes the stated batch sharing is allowed and the comparison class is homogeneous. It does not authorize a cohort or reuse of protected reference assets. Charge required reconstruction replicates, failures, audits and candidate-owned solver calls to the appropriate term. A partially used last reference batch still costs money.

Reference computation during a candidate's training belongs to construction. A solver inside the deployed system belongs to serving. Neither is shared official reference work by default.

Report cold reference creation and permitted amortization separately. New inputs, a new reference version, a changed population or exhausted hidden evidence can require new work. Protected reuse requires its own commitment, provenance, decontamination and disclosure design. [C4]

### 3.4 Client value and break-even

Use the credible deployable baseline B at acceptable accuracy, not an unnecessarily costly reference configuration. Measure the candidate's physical adequacy against the qualified reference R. B and R can share a method while using different configurations. [D1]

For incremental fixed lifecycle cost C0, baseline cost per query cB, effective candidate-system cost cM and queries N before material rebuild:

    net_saving(N) = N * (cB - cM) - C0

For C0 >= 0 and cB > cM:

    break_even_queries = ceil(C0 / (cB - cM))

For a sequential surrogate-plus-fallback workflow:

    cM = core_cost_per_query
       + escalation_fraction * conditional_fallback_cost
       + other_recurring_query_cost

Include data acquisition, search, qualification, integration, serving and requalification where relevant, without double-counting. Use the same currency and lifecycle. Record sunk assets separately from incremental cost. Stationary expected costs cannot establish a tail-latency guarantee.

No positive per-query cost saving means no positive-cost break-even through serving savings under this model. A separate latency, deployment or capability benefit needs its own requirement and evidence. A client whose baseline meets the job with no worthwhile candidate advantage may fit an evidence audit but not an acceleration program.

## 4. Realistic qualification follows the claim

Do not require a complete industrial product dossier to authorize a small feasibility investigation. Do not sell feasibility evidence as product qualification.

| Spend/claim stage | Evidence needed to justify moving on | Claim ceiling |
|---|---|---|
| Scoping | Named physical job and baseline; initial access and evidence inventory; critical unknowns; bounded next test and stop condition | Worth investigating, or not under current scope |
| Feasibility probe | Targeted reference and/or reconstruction checks on declared development material; measured costs; uncertainty and limitations; plausible program economics | Observed feasibility within the probe's tested conditions |
| Official exam review | Applicable qualified task, population, finite sampling, generator, reference, representation, measurement, secrecy and decision-resolution evidence; named approval | Exact registered exam may judge candidates after authorization |
| Product review | Exact artifact/system and runtime; job-shaped battery; operating envelope; latency/throughput and failure behavior; escalation and requalification conditions | Exact bounded context-of-use claim |

These stages are a spend discipline, not four new protocol states. Carbon already owns the official scientific and product qualification objects. [C1–C5]

### Construction evidence

Bind source, configuration, artifacts, data rights, environment and allowed information. Reconstruct under validator control and measure runtime, peak memory, compilation and output behavior. Establish reproducibility at the resolution needed for the comparison; demand bitwise identity only when the governing execution contract requires it. Retain infrastructure, resource, reference and scientific failures separately.

A solver-learning composition needs joint evidence. A differentiable construction also needs gradient checks and an account of solver convergence, conditioning and discretization effects when gradients matter to the construction claim. A correct forward call alone does not verify the gradient. Component qualification does not imply system qualification. [C1, C4, C7]

### Reference evidence

Record equations, assumptions, regime, boundary conditions, physical envelope, exact method and asset identity. Qualify the appropriate role through analytic/manufactured checks, refinement, numerical verification, independent corroboration and physical observations as applicable. No requirement here makes two solvers mandatory for every task; independence and evidence roles are task-specific.

Estimate uncertainty and failure behavior by the observables and regimes that matter. Characterize throughput, cold-start time and difficult-case runtime. Test hidden-case generation and provenance. Agreement with a numerical solver may justify emulation within its assumptions; physical adequacy needs additional evidence when the client claim depends on the actual system. [C1, C2, C4]

### Challenge and client evidence

Begin with the causal I/O, operating envelope, exclusions, target population and intended engineering decision. Define finite sampling and sufficiency before protected evaluation. Qualify measurements and derive acceptance from the client's decision and evidence resolution. Keep sample counts, solver settings and accuracy requirements unresolved until the responsible owners can justify them.

Commit the exam before protected instances become knowable. Keep mandatory physical failures disqualifying. Preserve failed/uncertain reference cases and sampling censoring. The exam must qualify before it qualifies candidates. Product evaluation must cover the actual deployment and escalation path, not just a training checkpoint. [C1–C5]

## 5. Rank limiting factors by the next decision, not by weighted appeal

For each open blocker, record the requirement at risk, evidence state, plausible effect on the decision, proposed measurement, its engineering effort/cash/elapsed time, dependencies and explicit stop/continue rule.

Select the test most likely to change a material decision at acceptable cost. Do not invent probabilities to produce a precise-looking expected-value score. Where probability and utility estimates later become defensible, a formal value-of-information analysis can refine the ordering.

An effective order is:

1. Resolve a categorical deal-breaker, such as unavailable lawful access or missing causal inputs, before expensive model construction.
2. Probe the dominant uncertain reference or construction constraint.
3. Compare credible baseline/candidate configurations after the comparison can produce useful evidence.
4. Expand only where a customer need or a reusable capability justifies the next cost.

This is not a universal fixed order. A cheap compatibility check can precede a costly reference campaign. Preserve the rationale.

Among viable profiles, retain a task-specific Pareto set of value, risk, effort and cost rather than collapse them into one global score. Strategy selects the commercial portfolio. Science owns the evidence boundary. Engineering owns implementation through selected tickets. [C1, C6, C7]

## 6. Proposed roadmap order

| Order | Work | Current decision | Evidence that changes the decision |
|---|---|---|---|
| 1 | Client job, baseline and reference feasibility | Scope first; no specific client package supplied here | A filled Fit Card and a bounded reference/cost probe identify a viable program |
| 2 | Harshdeep JAX catalog inventory | Prepare audit; repository remains unavailable | Pinned source, licenses, I/O compatibility, reconstruction and runtime evidence |
| 3 | Bounded same-job backbone comparison | Follow its reference and execution dependencies | Common evidence establishes useful cost/accuracy differences |
| 4 | One simple numerical/ROM correction | Later bounded pilot | End-to-end benefit survives added construction cost and physical tests |
| 5 | Solver-in-the-loop closure / differentiable RANS | Candidate for a separately funded long-form profile | Adequate independent reference, viable gradients/reconstruction and affordable campaign |
| 6 | Foundation-scale context / pretrained adaptation | Later profile | Provenance, information budgets, reconstruction semantics and workload advantage |
| 7 | Pareto local-optima / hyperbolic research | Preserve available lineage; defer graph model | Sufficient transition evidence and prospective improvement over simpler research policies |

The order is a research recommendation, not a measured ranking or an active implementation board. It prioritizes the user's reference-cost and onboarding concerns while preserving later construction directions. A new client or newly available code may change the order.

The source pack and current master plan preserve model-family neutrality, richer construction, generalized reconstruction and product qualification in their existing domains. Keep this work within those authorities. Optional graph research must not become a launch prerequisite. [C7]

## 7. Bound expensive opportunities without excluding them

Each profile owns its acceptable program expenditure and cadence. A frequent-round profile and a longer sponsored profile can retain the same physical requirements and differ in scheduling/resources. Material changes require a prospective identity and governing approval; do not weaken a live exam after seeing a favored candidate.

A reference that fails the required accuracy does not become adequate when given a longer deadline. A reference that is adequate but slow may fit a longer profile. A program that still costs more than the supported client value should be redesigned or declined under that scope. Preserve the option to revisit a method when an identified dependency changes.

Record a parked opportunity's restart trigger. "Revisit later" without a trigger is not a plan. Examples: the JAX repository arrives; a client provides permitted reference assets; a numerical method demonstrates the needed convergence; or a prospective workload justifies the measured fixed cost.

## 8. First use and bounded optimization

Choose one actual onboarding opportunity. Complete the job/baseline fields before discussing backbone preference. Use the six checks to find the first consequential unknown. Author one test with its budget, owner, outputs and stop conditions. Review the result before authorizing broader integration.

In parallel, prepare Harshdeep's inventory/profiling checklist without asserting any unsupported library capability. Do not ask for unavailable source again or block the reference decision on it.

Measure whether this decision process itself earns value: predicted versus actual program costs, surprises after a positive feasibility decision, opportunities declined under a stated scope, engineering time avoided, and eventual client outcomes. Treat these as process evidence, not a new official science score. Full roadmap optimization requires actual workloads, dependencies, capacity and costs; the present order is a defensible starting proposal, not a proven global optimum.

## 9. Workbook guide

`Carbon_Fit_Workbook_v0_2.xlsx` contains:

- **Fit Card:** one opportunity, six checks, blockers, next test and owner disposition.
- **Limits:** entered requirements, low/high estimates, exact comparators, margin and unresolved/conflict results.
- **Economics:** reference amortization, whole-program cost, fallback-aware serving cost and break-even arithmetic.
- **Example:** invented values demonstrating that a slower cadence can resolve a time conflict while reference adequacy remains unknown.
- **Roadmap:** proposed acquisition order with dependencies and stop/reframe triggers.
- **Guide:** stage distinctions, evidence requirements and sources.

Production input cells remain blank. The example has no authority over real thresholds. Formula behavior is checked separately from scientific adequacy. Numeric consistency is not qualification.

## 10. Evidence categories and sources

**External guidance:** NASA's Systems Engineering Handbook Section 6.8 supports separating mandatory criteria, evaluating alternatives under uncertainty and choosing further analysis according to its effect on the decision. NASA's models-and-simulations standard landing page describes program/project-defined acceptance criteria and approval authority. These are external decision-method analogies; Carbon claims no NASA compliance or certification. No PDE-specific performance result is imported from them. [N1, N2]

**Carbon hypothesis:** a small bottleneck-first review can reduce wasted engineering while preserving expensive but valuable long-form programs.

**Proposed Carbon experiment:** apply the method to a real onboarding job and a bounded construction/reference probe; track predicted versus realized effort and the usefulness of the resulting decision.

**Qualified Carbon evidence:** none produced by this document. There is no measured client-fit ranking, newly qualified reference, benchmark, speedup, production standard or graph-utility result. Harshdeep's JAX inventory remains owner-reported and uninspected.

### Source register

- **[C1]** Supplied `docs__context__SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md` and `Design_Specs__Evidence_and_Envelope_Standards.md`: scientific authority, noncompensable failures, reference roles, bounded claims.
- **[C2]** Supplied `Design_Specs__Challenge_Instance_Distribution.md`, `Design_Specs__Generator_Validation.md`, `Design_Specs__Generator_Creation.md`: task/population/sampling, reference and measurement qualification, censoring and uncertainty.
- **[C3]** Supplied `Design_Specs__Product_Qualification_Evidence.md`: exact product identity, separate battery, escalation and requalification.
- **[C4]** Supplied `Design_Specs__Trustless_Verification.md` and `Design_Specs__Runtime_Julia_Truth_Oracle.md`: independent protected execution, reference provenance and failure rules, qualified caching.
- **[C5]** Supplied `Design_Specs__Scoring.md`: official scoring authority; planning quantities do not acquire official scoring roles.
- **[C6]** Supplied `Design_Specs__Physics_Intelligence_System.md`: evidence types, retained failures, prospective utility evidence and learned guidance boundaries.
- **[C7]** `https://github.com/carbonphysicsai/Carbon/blob/main/Design_Specs/Agentic_Development_Master_Plan.md`, read 11 September 2026, lines 1–60 and 370–645; returned blob `ac29b86227e4f17fc0f73eb2a0f794edb9f54168`. Domain placement and non-permission rules. Unrelated historical payment clauses are outside this review.
- **[D1]** Supplied `Carbon_Model_Construction_Neutrality_Roadmap_v0_1.md`, 11 September 2026: working proposal for client comparisons, reference economics and cadence. Not runtime authority or qualified performance evidence.
- **[N1]** `https://www.nasa.gov/reference/6-8-decision-analysis/`, read 11 September 2026, especially criteria, uncertainty and documentation sections. Primary external decision-analysis guidance.
- **[N2]** `https://standards.nasa.gov/standard/nasa/nasa-std-7009`, scope read 11 September 2026. The full standard was not audited. No claim about compliance or discipline-specific acceptance values.
