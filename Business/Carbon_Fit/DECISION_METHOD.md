# Carbon Fit decision method

**Version 0.3. Working proposal.** See [status and authority](README.md). This is an internal feasibility method; public self-assessment has the stricter claim ceiling in [Client Fit Tool](CLIENT_FIT_TOOL.md).

## 1. Assessment identity

Record the client job, intended claim, deployable baseline, candidate construction, qualified-reference proposal and resource/cadence profile. Attach versions, source, scope, date and accountable owner. Keep reference, deployable baseline and candidate roles distinct even when they use the same method.

A component capability record is reusable evidence, not a blanket claim of fit. The assembled job can fail because of incompatible inputs, physical envelope, reference uncertainty, deployment conditions or rights. Current availability, hypothetical design and demonstrated capability must remain distinct.

## 2. Six checks and dispositions

| Check | Question | Evidence owner |
|---|---|---|
| Job and access | Is the causal input/output task defined, and may Carbon use the required data and tools? | Client owner, Science, rights/Security |
| Reference | Can the comparison obtain adequate independent evidence at its intended resolution? | Science and reference implementer |
| Construction | Can validators rebuild the exact method under a pinned, bounded, isolated contract? | Engineering, Science/Security |
| Exam | Can the complete mandatory evidence program fit this profile, including difficult cases and failures? | Science and Operations |
| Deployment | Can the exact system meet physical, latency, throughput, memory and escalation requirements? | Product qualification and Engineering |
| Value | Does it improve a declared requirement against a credible alternative enough to justify the program? | Strategy/client owner, informed by Science |

Internal evidence states: `SUPPORTED_FOR_THIS_STAGE`, `UNKNOWN`, `BLOCKED_FOR_THIS_SCOPE`. Each state needs a rationale and source. Scoping support permits a bounded investigation, not scientific qualification. Keep all blockers visible; do not average them into a fit score. Missing input never becomes zero, favorable evidence or an invented default.

Owner dispositions: proceed to a bounded test; seek pilot review; redesign prospectively; park until a named dependency; decline present scope; or use the existing baseline. The card cannot create official eligibility, LIVE, a frontier result, payment or product qualification.

## 3. Computable terms

Every number binds a unit, comparator, source, evidence class, physical/workload scope and numerical or scenario uncertainty. A range is a scenario range unless its source defines statistical coverage. Correlated marginal ranges do not imply joint coverage.

For positive upper limit L and nonnegative consumption interval [lo, hi]:

```text
worst_headroom = 1 - hi/L
best_headroom  = 1 - lo/L
```

For positive minimum requirement L:

```text
worst_headroom = lo/L - 1
best_headroom  = hi/L - 1
```

Keep `<`, `<=`, `>` and `>=` explicit. Classify the input range as within the entered requirement, limit conflict, overlap or unknown using that comparator. Zero headroom is not automatically pass. A smallest known headroom identifies numerical pressure, not overall readiness. Zero limits require a direct predicate or an explicitly defined calculation, not division by zero.

Reference adequacy cannot be reduced to a solver tolerance. Science must account for bias, discretization, representation, measurement, sampling and reconstruction uncertainty relevant to the claim. Do not add uncertainty terms without a justified dependence model. A fast reference that cannot resolve the comparison is inadequate for that claim.

### Whole-program expenditure

For a homogeneous scenario with n planned comparisons and k permitted comparisons per reference batch:

```text
batch_count = ceil(n/k)
program_cost = setup_cost
             + batch_count * reference_batch_cost
             + n * (reconstruction_cost + other_comparison_cost)
```

Here n is a nonnegative integer and k a positive integer. A partially used final batch still costs money. Include required replication, failed attempts, audits, storage and delivery in declared terms without double-counting. If costs or sharing vary by batch, sum the actual batch schedule instead. This formula does not authorize reference reuse; use the [reuse review](PROTECTED_REFERENCE_REUSE.md).

Record reference qualification/setup cost, fresh answer creation, and amortized cost separately. Training-time solver calls are construction cost; a solver retained in the deployed candidate is serving cost. Neither is official-reference work by default. Elapsed turnaround follows the dependency/resource schedule, not this cost equation; see [Runtime Profiles](RUNTIME_PROFILES.md).

### Client economics

Compare a credible deployable baseline B at accepted accuracy against the complete candidate system M. Do not claim a speedup against an unnecessarily refined reference when a cheaper acceptable numerical baseline exists.

```text
saving(N) = N * (cB - cM) - C0
```

C0 is incremental fixed lifecycle expenditure; cB and cM use the same currency and workload. For C0 > 0 and cB > cM, `ceil(C0/(cB-cM))` is the first integer query count reaching nonnegative savings. Strictly positive savings can require the next query at exact equality. A nonpositive denominator does not yield a serving-cost break-even for positive C0. Handle C0 <= 0 as a separate scenario rather than force this quotient.

For a sequential core-plus-fallback workflow:

```text
cM = core_cost + escalation_fraction * conditional_fallback_cost
   + other_recurring_query_cost
```

Include search, reference data, integration, qualification, deployment and requalification where material. Compare query volume before a material rebuild, not an unsupported infinite lifetime. Stationary expected costs do not establish tail latency; conditional fallback cost may correlate with difficult cases. A separate latency, hardware or capability advantage needs its own evidence.

## 4. Four spend stages

| Stage | Required decision evidence | Claim ceiling |
|---|---|---|
| Scope | Defined job/baseline, access inventory, consequential unknown, bounded next test | Worth investigating under stated conditions |
| Feasibility probe | Targeted checks on declared development material, measured resources and explicit limitations | Feasibility observed only in the probe's scope |
| Exam qualification | Applicable task/population/sampling, reference, representation, measurement, secrecy and decision-resolution evidence, followed by domain approval | Exact registered exam may judge candidates after authorization |
| Product qualification | Exact system/runtime, job-shaped battery, envelope, deployment behavior, escalation and requalification | Bounded context-of-use claim for the exact system |

These are spending stages, not new official lifecycle states. Use the existing Dossier, Score Pack and product evidence objects in the [authority crosswalk](README.md).

### Construction evidence

Bind code, configuration, permitted information and data rights, dependency/environment pins and output artifact. Demonstrate producer-independent reconstruction and resource enforcement. Measure variability at the scientific decision resolution. Bitwise equality is required only where the controlling contract requires it. For composed systems, test the composition; for differentiated constructions, verify gradients and their solver/convergence assumptions where the claim depends on them. Preserve resource, reference, infrastructure and scientific failures as distinct evidence.

### Reference evidence

Record equations, assumptions, physical regime, boundary conditions, numerical method, implementation/asset identity, and scope. Use analytic/manufactured checks, refinement, convergence, independent corroboration and physical observations as appropriate to the claimed role. No universal two-code rule follows. Record uncertainty and failure by relevant observable/stratum; assess code/data/method/personnel correlation. Measure fresh-answer and difficult-case costs. Emulation of a numerical model is a narrower claim than validation of the physical system. Qualify population generation and reference adequacy separately.

### Client Challenge evidence

Define the intended decision, causal inputs, outputs, envelope/exclusions and target population before implementation. Register finite sampling, measurements, evidence use and uncertainty treatment before protected instances become knowable. Qualify the exam before using it to qualify candidates. Mandatory physical failure remains disqualifying. Do not discard slow or failed reference cases to make the exam look cheaper. A client payment, intake answer, fit result or winning score cannot bypass qualification.

## 5. Ranked limiting factors

For each gap retain: requirement at risk; evidence state; consequence; investigation; engineering/cash/elapsed-time cap; dependencies; continue condition; stop/redesign condition; owner; restart trigger. Resolve cheap categorical deal-breakers before expensive work when they can change the decision. Do not invent probabilities to manufacture a precise expected-value ranking.

Among viable profiles, Strategy selects the portfolio from cost, value, risk, effort and reusable capability evidence. Science owns claim limits. Engineering implements selected work. A slower valid profile stays on the roadmap; a longer deadline cannot cure inadequate physical evidence.

External decision-method analogy: [NASA, Decision Analysis](https://www.nasa.gov/reference/6-8-decision-analysis/) separates mandatory criteria, uncertainty and the value of additional analysis. This package claims no NASA compliance and imports no numerical acceptance limits.

## 6. Small arithmetic regression cases for implementation

These are synthetic calculation checks, not production requirements:

| Inputs | Expected output |
|---|---|
| Upper `<=8`, interval [14,23] | Limit conflict |
| Upper `<=24`, interval [14,23] | Within entered limit; reference may still be unknown |
| Upper `<8`, interval [8,8] | Limit conflict |
| Upper `<=8`, interval [8,8] | Within entered limit |
| n=5, k=2, setup=100, batch=30, per-comparison total=10 | 3 batches; total=240 |
| C0=100, cB=5, cM=3 | Nonnegative saving first at N=50; positive first at N=51 |
| Missing baseline cost or invalid unit conversion | Unknown/invalid input; no invented saving |

Engineering must add boundary, unit, interval, overflow, invalid-input and uncertainty tests for the chosen implementation. These illustrative checks do not establish scientific adequacy or certify the earlier workbook.
