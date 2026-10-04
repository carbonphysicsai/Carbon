# AI accelerator cooling — customer decision design packet

**Status:** RUNNABLE DEVELOPMENT STUDY; COUNTED CFD NOT YET AUTHORIZED

**Challenge:** `chip-cold-plate`

**Scientific families:** f04 laminar internal flow, supported by f03 steady
conduction

**Current physical scope:** periodic straight-channel cell v1

**Pipeline state:** bounded engineering study outside LIVE authority; this
packet does not enter the challenge pipeline, sign a scientific gate, assert
customer acceptance, or bypass the battery-defined protocol lock

**Authority:** OWNER-CHALLENGE-FOUNDATION-01; existing physical values remain
under OWNER-CHALLENGE-DESIGN-01

**Implementation:** `carbon/cold_plate/customer_decision.py`,
`carbon/cold_plate/decision_study.py`,
`carbon/cold_plate/reference_campaign.py`,
`scripts/dev/cold_plate/decision_study.py`, and
`scripts/dev/cold_plate/reference/run_batch.py`

**Frozen study configuration:**
`docs/development/studies/AI_ACCELERATOR_COOLING_SYNTHETIC_V1.json`

## End goal

The customer should be able to submit a manufacturable cooling design space,
an accelerator heat-load envelope, coolant and facility limits, and receive:

1. a fast model's proposed cold-plate design and operating control;
2. its predicted die-temperature and hydraulic-power margins over the whole
   declared envelope;
3. an immutable proposal commitment made before expensive reference access;
4. independent verification of every operating condition, with false-feasible
   and unavailable cases exposed rather than averaged away; and
5. a reusable model that makes the next design cycle substantially faster.

The commercially valuable target is the **full cooling decision**: channel and
manifold topology, nonuniform two-dimensional heat maps, pump/control settings,
manufacturing constraints, uncertainty, and later experimental confirmation.
The current code is an honest first vertical slice of that target. It evaluates
only the periodic interior of straight channels and cannot yet recommend a
manifold or a production plate.

The plan's burst-power thermal-envelope problem remains a separate transient
heat-conduction challenge (f02). It should eventually feed time-dependent heat
loads and safe operating envelopes into this cooling program, but its score,
reference, population, evidence and qualification must not be merged with the
fluid/steady-conduction challenge.

## 1. Engineering job

**User.** An accelerator thermal architect or cold-plate supplier choosing a
plate geometry and flow control for a declared die, coolant loop and workload.
The buyer identity is still a hypothesis; no customer demand, pilot or revenue
is claimed.

**Decision.** Choose straight-channel geometry and coolant flow that minimize
worst-case hydraulic power while satisfying customer-supplied maximum die
temperature and hydraulic-power limits at every declared operating condition.
The implementation accepts no default limits. The customer must supply both
values and a requirement reference.

**Design/control variables in v1.** Channel width, fin width, channel depth and
flow per kW. **Operating variables in v1.** Coolant inlet temperature, heat
load, hot-spot ratio, axial hot-spot centre and axial hot-spot width.

**Consequence of error.** A false-feasible result can lead to an overheated die,
an undersized pump or a late redesign. A false-infeasible result can reject a
lower-power design. Reference unavailability is neither outcome and is reported
separately. The v1 objective is lowest worst-case pumping power among designs
predicted feasible everywhere; it is not a weighted thermal/hydraulic score.

**Customer requirements still open.** The executable study deliberately uses
the synthetic DEVELOPMENT assumptions 100 °C maximum die temperature and
0.25 W maximum periodic-cell hydraulic power. They make the first comparison
concrete; they are not customer requirements, acceptance values, or production
limits. `HUMAN_INPUT(customer)` remains required for the actual die limit,
hydraulic/facility envelope, manufacturing rules, reliability margin and
acceptable verification uncertainty. None is inferred from the DEVELOPMENT
population screen.

`flow_lpm_per_kw` now has one explicit operating-control meaning:

```text
total_flow_lpm = flow_lpm_per_kw * heat_load_w / 1000
```

It represents steady-state feed-forward control using commanded or measured
heat load, with pump flow settled before each operating point. The comparison
assumes such a supervisory controller is implementable. It does not demonstrate
sensor latency/error, actuator dynamics, transient response or controller
safety. The controller must remain within the declared coefficient bounds, the
synthetic hydraulic constraint, PG25/reference applicability, the reference's
laminar Reynolds applicability, and future owner-approved pump flow, pressure
and slew limits.

## 2. Physical system

The implemented system is a copper C11000 cold plate cooled by PG25 over a
30 x 30 mm heated footprint. The steady reference solves conjugate heat
transfer in one repeating cell: half a channel and half a fin between symmetry
planes. It uses straight parallel channels, laminar incompressible flow, an
axial Gaussian hot band on a uniform floor, and a uniform TIM resistance added
after the solve.

The nine existing input bounds and their units are canonical in
`carbon/cold_plate/domain.py`. They are provisional DEVELOPMENT choices, not a
qualified customer envelope. Material and coolant provenance, the current
property fits and their limitations are in
`scripts/dev/cold_plate/DESIGN_BASIS.md`.

**Explicitly absent from v1:** inlet/outlet headers, manifolds, plate edges,
serpentine bends, spanwise heat-map variation, contact nonuniformity, boiling,
turbulence, fouling, structural stress, manufacturability/cost, pump curves,
facility-loop interaction and time dependence. The first high-value physical
expansion is a multi-channel domain with bounded manifold topology and
two-dimensional heat maps. It is a new challenge version, not a silent
reinterpretation of this one.

## 3. Population P, Q and w

The intended customer population `P` is not yet authored. It must represent the
customer's actual geometry, workload, coolant/facility and manufacturing
envelope, including correlations rather than merely copying independent bounds.

The current DEVELOPMENT population is
`carbon.cold-plate.development-population.v1`: independent uniform draws over
the nine-input box, admitted when the closed-form model predicts a hottest
wetted wall no greater than the provisional screen and Reynolds number no
greater than the provisional laminar screen. This is prior evidence and a test
population only; it is not the customer population.

The current public TRAIN and PRACTICE generation law `Q` is the recorded public
draw of that DEVELOPMENT population. The private pool uses an operator-held
root and must remain protected. No customer-specific proposal distribution or
adaptive acquisition law has been selected.

Evidence weights `w` for a customer decision are `HUMAN_INPUT(science/customer)`.
The search objective and the exam score do not define `P`, `Q` or `w`. A future
customer study must pre-register scenario groups, sampling, inclusion,
missingness, censoring and weighting before results are observed.

The first executable study is a finite scenario set rather than a claim about
customer `P`: eight straight-channel designs cross six steady conditions. Four
conditions are labelled `REPRESENTATIVE` and two are labelled
`BOUNDARY_STRESS`. Those groups are reported separately. Their combined
weighting is `null`; no combined pass result is computed.

## 4. Case contract

One v1 case contains exactly the nine finite inputs declared by
`carbon/cold_plate/domain.py`; extra, missing, out-of-range or Boolean values are
refused. The first four values form the declared design/control point and the
remaining five form an operating condition. A design study is a Cartesian grid
of unique design points crossed with a unique condition set.

The customer-decision request additionally binds:

- the exact decision-contract digest and customer-requirement reference;
- model member, recipe digest and seed;
- candidate-space and condition-space digests;
- registered search method plus code/configuration digests;
- query and verification budgets; and
- a deterministic seed policy.

Only `DEVELOPMENT` material and mode `PB-INV` are served. The model-query budget
unit is one **attempted model point**. A point is charged before inference;
infrastructure failure, malformed output or prediction-validity failure cannot
be caught and followed by more queries in the same oracle. Duplicate points are
forbidden both within a batch and across calls, so commitment construction
cannot collapse repeated evidence. There is no in-oracle retry; a separately
identified future attempt requires a new oracle.

A model must return exactly peak temperature, the 30-segment temperature
profile and pressure drop. Each successful prediction records the existing
prediction-validity gates. A failed batch is atomic and seals the study arm.

## 5. Reference policy

The current reference is OpenFOAM v2512
`chtMultiRegionSimpleFoam` in the image digest pinned by
`carbon/cold_plate/openfoam.py`. It solves steady laminar conjugate heat
transfer in the periodic cell with the recorded mesh, fluid-property model,
convergence checks and applicability checks. Reference outcomes preserve
`FAILED_INFRA`, timeout/solver failure and `REFERENCE_INVALID` semantics rather
than charging them to a design.

Existing evidence includes the rung verification, a 16-case pilot with paired
refinement, and complete 400 TRAIN / 100 PRACTICE / 200 private pools. That
evidence supports the bounded numerical implementation; it does not establish
model adequacy for a full plate or decision reliance for a customer.

Reference access is classified. `ANALYTICAL_FIXTURE` wraps callbacks for smoke
tests and can never count as CFD. `COUNTED_CFD` is constructed only by the
study's artifact importer. For every successful counted case the importer binds
the pinned image, exact plan/configuration, generated `case.json`, mesh,
analysis, convergence and applicability evidence, run identity, solver logs,
written fluid/solid fields, and a digest of every retained artifact. Missing or
tampered provenance becomes unavailable evidence rather than a plausible CFD
result.

The verification-budget unit is one **condition evidence evaluation**. A
six-condition proposal costs six units whether the underlying case is newly
loaded or cached. The same commitment cannot be verified twice. Cache reuse can
avoid another solver execution but never another evidence-evaluation charge.
The counted plan has 48 initial reference executions, at most one retry for a
failed case, a 12-execution retry reserve, and a hard cap of 60.

That cap is enforced before launch by a durable SQLite campaign ledger. The
runner atomically reserves every case before dispatch, binds attempt 1 and the
sole optional retry attempt to their output directories, and records each
finished typed status. `BEGIN IMMEDIATE`, campaign/attempt uniqueness and
case/attempt uniqueness prevent concurrent launchers from oversubscribing the
allowance. A restart sees retained reservations and cannot rerun the campaign
under a new output directory. Only `FAILED_INFRA`,
`REFERENCE_SOLVER_FAILED` and `REFERENCE_TIMEOUT` are retry eligible. Ambiguous
reserved work remains consumed and fails closed rather than being launched
again. The importer requires the ledger snapshot and reconciles it with the
plan, records and campaign limits.

Before the full-manifold version can be used, the science owner must approve a
new reference policy covering topology/mesh rules, turbulence or transition
applicability, two-dimensional heat maps, convergence/refinement, failed-case
handling, hardware timing and reference uncertainty. Experimental confirmation
needs its own instrument, calibration, uncertainty and applicability contract.

## 6. Output and measurement contract

The model predicts heated-face peak temperature, a 30-segment axial
temperature profile and inlet-to-outlet pressure drop. Carbon derives heated-
face mean and outlet bulk temperature. The decision layer derives the hottest
die temperature through the TIM, hydraulic power, each constraint margin and a
Boolean feasibility result from the exact customer limits.

The baseline selects the predicted-feasible design with the lowest worst-case
hydraulic power over all declared conditions. Thermal and hydraulic feasibility
are decision properties, not candidate physical gates and not score inputs.

A proposal commitment is written with exclusive creation before classified
reference access. Verification evaluates the committed design at every declared
condition and reports `FEASIBLE`, `INFEASIBLE` or `REFERENCE_UNAVAILABLE`.
`INFEASIBLE` after a model-feasible proposal is a visible false-feasible event.
Unavailable evidence is never counted safe or unsafe. The result explicitly
denies global-optimum, customer-acceptance, scientific-qualification and
production-qualification claims.

Proposal outcome and reference availability are separate:

- `CONFIRMED_INFEASIBLE` means at least one condition has a confirmed
  constraint violation, even when another condition is unavailable;
- `CONFIRMED_FEASIBLE` requires usable feasible reference evidence for every
  required condition;
- `UNRESOLVED` means no violation is known but at least one condition lacks
  usable evidence; and
- `ABSTAIN` means no design was proposed.

False-feasible proposal counts use every proposal as their denominator, so a
known violation cannot disappear merely because another condition timed out.

Three different gates/constraints are intentionally not conflated:

1. **Prediction-validity gates** in `exam.gates` check exact output shape,
   finiteness, face temperature above inlet, peak/profile consistency, positive
   pressure drop and paired-repeat behavior where a twin is supplied. They do
   **not** enforce Reynolds number or velocity.
2. **Reference-applicability checks** in `analysis.py` include the PG25
   temperature interval, `re_outlet <= 2000`, mass/energy balance and convergence
   evidence. A failure makes the reference invalid; it is not candidate failure.
3. **Synthetic customer feasibility constraints** in the decision contract are
   die temperature no greater than 100 °C and periodic-cell hydraulic power no
   greater than 0.25 W. They determine study feasibility but carry no customer
   authority.

There is no velocity feasibility gate in the current execution path. The inlet
velocity is a derived diagnostic, not an enforced limit.

Measurement definition for a physical rig is `HUMAN_INPUT(science)`: sensor
locations, spatial/temporal aggregation, pressure/flow measurement, calibration,
uncertainty, repeatability, missing data and model-to-instrument comparison.

## 7. Construction contract

The existing physics-aware analytical model is the v1 fixed engineering
baseline. A real DEVELOPMENT learned model is also available: the Gaussian
kernel-ridge baseline selected previously on TRAIN/PRACTICE evidence. The study
reconstructs it from the pinned 400-record TRAIN artifact with the previously
selected length 8.0 and ridge 1e-6. Reconstruction time is measured separately;
the historical training/tuning cost was not recorded and remains explicitly
unavailable. An analytical callback is never relabelled as learned-model
evidence.

The frozen experiment separates three questions:

A. `analytic-v1/fixed_grid` versus `learned-krr-v1/fixed_grid` measures model
   value with the same search, space, conditions and 48-point declared budget.
B. `learned-krr-v1/fixed_grid` versus
   `learned-krr-v1/screen_then_confirm` measures registered search-method value
   with the same model and equal declared budgets; actual query use is reported.
C. Every selected design is compared with the best independently
   reference-feasible design observed in all 8 × 6 declared pairs. Exact
   finite-set regret is reported only when every design that remains
   potentially feasible is sufficiently resolved. A candidate with a confirmed
   violation is excluded even if some of its other conditions are unavailable;
   a candidate with no confirmed violation and missing evidence keeps the
   comparator unresolved. In that case the report may show an explicitly
   labelled difference from the best observed feasible design, but exact regret
   remains nonnumeric. Infeasible, unresolved and abstaining selections receive
   typed nonnumeric outcomes, not a favorable substitute value.

The comparator is best-known only in this finite grid and physical scope. It is
not a global optimum.

The proposed screen condition is `boundary-01` (40 °C inlet, 1200 W, 2× axial
hot spot). It is the highest-load declared condition and is therefore a useful
deterministic stress screen; the method must still confirm every other condition
before selecting. This configuration is frozen before counted evidence and is
not retuned on the final results.

The public 400-record TRAIN artifact and its prior calibration report retain
their training/tuning roles. The six named study conditions are frozen as final
decision-evaluation cases and are not used to fit or select the learned model or
search configuration.

Execution is a five-stage protocol: freeze; reconstruct/search without a
reference object; persist all four commitments or explicit abstentions in a
construction artifact; acquire and evaluate reference evidence; then generate
the report. `construction.json` is written last and binds the exact freeze,
model identities, four proposal commitments and reconstruction-cost artifact.
Evaluation restores and validates every commitment before it can receive a
reference session. The counted plan and campaign bind the construction
identity, so proposals cannot be regenerated after CFD is observed.

This is a **prospective Level 0 foundation**, not a pipeline entry or a signed
construction contract. The challenge protocol is still defining, battery must
finish the worked protocol, and f04 remains queued. When the family is admitted,
the construction owner must map the actual model recipe and capabilities onto
Levels 0-5, pin supported JAX/PyTorch reconstruction, resources, data, seeds,
dependencies and artifact identity, and file the required expansion record.

Future construction freedom may improve the surrogate or search policy. It may
not change customer constraints, reference outputs, evidence accounting or the
official exam.

## 8. Research kit

The reusable kit now consists of:

- the nine-input domain, analytical baseline and population;
- the pinned OpenFOAM writer/reader and batch runner;
- public TRAIN and PRACTICE pools plus aggregate private-pool evidence;
- the cold-plate exam, physical gates and feasibility calculation;
- `carbon/cold_plate/customer_decision.py`, which adapts the challenge to the
  existing equal-budget design-search harness; and
- `carbon/cold_plate/decision_study.py`, the configuration validator, model
  reconstruction, finite comparator, artifact importer, analysis and report;
- `carbon/cold_plate/reference_campaign.py`, durable pre-dispatch execution and
  retry accounting;
- `scripts/dev/cold_plate/decision_study.py`, the fixture, plan and counted-run
  CLI; and
- tests that exercise customer-contract binding, grid/condition scope, budgeted
  access, physical-gate refusal, selection, write-once commitment, reference
  separation, provenance, verification accounting, finite regret, false-
  feasible reporting and generic search reuse.

No protected cases, private root, official seed, customer data or reference
answers are added to the research surface. A future research kit may add a
physics-aware learned correction baseline; the generic kernel model's small
private improvement over the analytical baseline is not evidence that the
challenge is ready.

## 9. Evidence plan

### Existing bounded evidence

- Numerical verification and refinement for the periodic cell.
- A 16-case reference pilot with all recorded cases `OK`.
- Complete DEVELOPMENT pools and two baselines scored through the existing
  exam.
- Deterministic customer-decision contract and proposal-before-reference
  enforcement in CPU tests.

The labelled analytical fixture smoke exercised all four arms and the complete
finite comparator. All arms selected `d03` (0.25 mm channel, 0.3 mm fin,
2.5 mm depth, 1.25 L/min/kW), the fixture comparator's best design. Fixed grid
used 48 queries per model; screen-then-confirm used 13 analytical and 18 learned
queries. All four fixture proposals were feasible at all six conditions, so
fixture regret was 0 W and the descriptive false-feasible proposal count was
0/4. The 24 arm-condition uses are not 24 independent trials: all four arms
selected the same design, producing six unique selected design-condition
reference cases and 18 evidence reuses. The representative group contains four
unique cases reused 12 times across 16 arm uses; the boundary-stress group
contains two unique cases reused six times across eight arm uses. The four arms
also share one decision problem. No population-level reliability or
generalisation confidence follows from these counts. A future uncertainty
estimate requires an approved sampling design and a justified unit of
independent observation. Because the pseudo-reference is the analytical model,
it does **not** establish learned-model accuracy, independent feasibility or
engineering value.

Agreement is itself the fixture outcome: all four arms selected `d03`. The
learned model changed predicted margins but did not change or improve the
selected design in this study. Screen-then-confirm reduced fixture model-query
use from 48 to 13 for the analytical model and from 48 to 18 for the learned
model. No settings were changed to manufacture a learned-model advantage.

### Runnable first decision experiment

The scenario, constraints, model identities, registered methods, equal declared
budgets, reference allocation, retry cap, group policy, comparator, regret
policy and analysis rules are frozen before evidence access. The runner reports:

- reference-confirmed feasibility across all registered conditions;
- per-arm proposal outcomes and descriptive false-feasible proposal counts,
  with every proposal in the denominator so missing evidence cannot hide a
  confirmed violation;
- unique selected design-condition reference cases separately from arm-level
  evidence reuse, with representative and boundary-stress groups separate;
- abstention rate, resolved decision coverage and unavailable/invalid evidence;
- worst-case reference hydraulic power for feasible proposals, exact finite-set
  regret only for a sufficiently resolved complete comparison set, and an
  explicitly labelled best-observed difference otherwise;
- attempted model queries, reference evidence evaluations, solver executions,
  cache reuse and retries;
- end-to-end, model-inference and solver wall time, with monetary cost left null
  until an owner-approved resource rate exists; and
- model reconstruction cost separately from per-decision cost.

Each arm contains an inspectable row for every scenario: selected geometry,
control assumption and calculated flow, predicted margins, reference margins,
feasibility, hydraulic cost and analytical fixed-grid baseline comparison.
Abstentions and unavailable reference evidence are never successes. No pass
threshold has been introduced.

The fixed pilot asks four bounded questions: do the selected designs satisfy
the registered constraints according to CFD; how do they compare with the
finite-set reference comparator; do the registered search methods reduce
queries or computational cost; and does the learned model change or improve the
decision in this particular study?

The analytical fixture smoke is useful only for testing the workflow. Counted
CFD remains pending the specific approvals below.

### Expansion evidence

1. Demonstrate the multi-channel/manifold reference against analytical controls
   and mesh/refinement studies.
2. Show that periodic-cell conclusions do and do not transfer across headers,
   maldistribution and spanwise heat maps.
3. Run a declared plate-level feasibility panel and measure p50/p95 reference
   cost on the approved hardware.
4. Use a separately contracted heater/plate rig to test model adequacy and
   decision reliance.
5. Keep the burst-power transient challenge separate, then test the composed
   cooling-plus-workload decision only after both component contracts are
   qualified for that use.

## 10. Readiness and claim record

| Dimension | Current state | What is still required |
| --- | --- | --- |
| Customer decision | CONTRACT + DEVELOPMENT implementation | Actual customer limits, envelope, manufacturing constraints and review |
| Periodic-cell reference | PILOTED / numerically verified in bounded scope | Independent numerical-reference review |
| Customer design search | IMPLEMENTED, tested, fixture-smoked | Counted CFD under the frozen capped plan |
| Full plate/manifold | NOT IMPLEMENTED | New version, reference, population, packet and evidence |
| Burst-power linkage | NOT IMPLEMENTED here | Separate f02 challenge and later composition contract |
| Experimental validation | NOT STARTED | Instrument/measurement contract and rig evidence |
| Challenge pipeline | QUEUED PRIOR WORK | Battery protocol lock, queue entry and owner gates |
| Scientific qualification | NO | Human science approval on exact evidence |
| Security qualification | NO | Dedicated review of any untrusted execution surface |
| Commercial validation | NO | Customer evidence and rights-cleared study |
| Production qualification / LIVE | NO | All applicable scientific, security, customer and launch gates |

### Owner decisions for the first counted experiment

| Decision | Recommended value or policy | Source or rationale | Consequence | Responsible owner | Execution step requiring approval |
| --- | --- | --- | --- | --- | --- |
| Status of study limits | Approve 100 °C die and 0.25 W cell hydraulic limits **only as synthetic DEVELOPMENT assumptions** | Concrete values create feasible/infeasible separation in the existing bounded grid; no customer requirement is known | Makes counted results interpretable only for this synthetic scenario | Science owner; customer owner for any later customer use | Freeze authorization before `counted` evidence analysis |
| Finite comparison set | Approve the declared eight designs × six conditions, with four representative and two boundary-stress cases | Covers low/high load, inlet and hot-spot severity while staying within the existing domain and reference | Enables bounded comparator/regret; does not support global or population claims | Science owner | Freeze authorization before 48-case CFD plan execution |
| Flow control | Use steady-state feed-forward `flow = coefficient × heat load`, subject to declared/reference limits | Matches the existing `flow_lpm_per_kw` variable and makes its controller assumption explicit | Supports only settled points; no transient or controller qualification | Thermal/control owner | Freeze authorization; later controller study before customer reliance |
| Comparator/regret | Report the best observed reference-feasible design; report exact finite-set best/regret only when every potentially feasible design is sufficiently resolved | Missing evidence for a candidate with no known violation can hide a better feasible member; a confirmed violation remains decisive | Prevents false exact-regret claims while preserving useful best-observed differences | Science owner | Freeze authorization before counted analysis |
| Counted compute | Approve 48 initial OpenFOAM executions plus at most 12 registered retries, one per eligible failed case; hard cap 60; 2 CPUs/case; 6 parallel; 3600 s/case; retain all artifacts; durable ledger required | Planning estimate is 0.4 core-hour/case, but the configured allocation permits 2 CPUs for the full one-hour wall limit | Estimate: 19.2 initial / 24.0 hard-cap core-hours. Enforced allocation ceilings: 96 initial / 120 hard-cap core-hours. Actual CPU use and orchestration/container/storage overhead require separate measurement | Compute/spend owner | Launch attempt 1 with `reference.run_batch`; this corrected 120 allocated-core-hour hard ceiling requires explicit approval and is the smallest compute block |
| Group weighting and pass threshold | Keep representative and boundary groups separate; no combined weighting and no pass threshold | No approved customer population or acceptable error rate exists | Evidence remains descriptive; no pass/qualification claim | Science/customer owner | Only required before combining groups or declaring adequacy |
| Customer requirements and rights | Keep all actual customer values/data absent until supplied and rights-cleared | No customer evidence or rights were provided | Blocks customer acceptance, commercial validation and confidential-data use, but not the synthetic study | Customer/rights owner | Any customer-specific rerun or claim |

After the science and compute/spend owners approve the exact frozen plan, the
ready-to-run Linux commands are:

```bash
# Stages 1-3: freeze, reconstruct/search without reference access, and persist
# all four commitments. The output directory must not already exist.
python -m scripts.dev.cold_plate.decision_study construct \
  --out .carbon-artifacts/ai-cooling-construction

# Build the construction-bound, still-unauthorized 48-case reference plan.
python -m scripts.dev.cold_plate.decision_study plan-cfd \
  --construction .carbon-artifacts/ai-cooling-construction \
  --out .carbon-artifacts/AI_ACCELERATOR_COOLING_CFD_PLAN.json

# STOP here until the science and compute/spend approvals in the table exist.

# Stage 4, attempt 1: reserve all 48 executions in the durable ledger before
# any solver dispatch.
python -m scripts.dev.cold_plate.reference.run_batch \
  .carbon-artifacts/AI_ACCELERATOR_COOLING_CFD_PLAN.json \
  --out .carbon-artifacts/ai-cooling-cfd-attempt-1 \
  --campaign-ledger .carbon-artifacts/ai-accelerator-cooling-synthetic-v1-campaign.sqlite3 \
  --parallel 6 --cpus 2 --timeout-s 3600 --keep all

# Only when attempt 1 has registered retry-eligible failures. The planner and
# ledger refuse more than 12 retries, an ineligible status, or a second retry.
python -m scripts.dev.cold_plate.decision_study plan-retry \
  --initial-dir .carbon-artifacts/ai-cooling-cfd-attempt-1 \
  --out .carbon-artifacts/AI_ACCELERATOR_COOLING_CFD_RETRY_PLAN.json
python -m scripts.dev.cold_plate.reference.run_batch \
  .carbon-artifacts/AI_ACCELERATOR_COOLING_CFD_RETRY_PLAN.json \
  --out .carbon-artifacts/ai-cooling-cfd-attempt-2 \
  --campaign-ledger .carbon-artifacts/ai-accelerator-cooling-synthetic-v1-campaign.sqlite3 \
  --parallel 6 --cpus 2 --timeout-s 3600 --keep all

# Stage 5: import retained evidence, evaluate the already committed proposals
# and complete finite comparator, and generate the report. Omit the second
# --reference-dir when no retry was needed.
python -m scripts.dev.cold_plate.decision_study counted \
  --construction .carbon-artifacts/ai-cooling-construction \
  --reference-dir .carbon-artifacts/ai-cooling-cfd-attempt-1 \
  --reference-dir .carbon-artifacts/ai-cooling-cfd-attempt-2 \
  --out .carbon-artifacts/ai-cooling-counted-result
```

The checked-in
`AI_ACCELERATOR_COOLING_SYNTHETIC_V1_V2_CFD_PLAN.json` is an inspectable,
unauthorized plan bound to the tracked fixture-v2 construction identity. The
execution sequence above regenerates that plan from the exact counted
construction. Heavy solver artifacts and the durable ledger stay in the
ignored `.carbon-artifacts/` directory and must be retained for import/audit.

### Review-finding disposition

| Hypothesis | Disposition and code evidence |
| --- | --- |
| Duplicate queries can collapse at commitment | Confirmed and repaired. `Oracle.query` forbids duplicates within and across calls; focused tests cover both. |
| Failed model attempts do not consume budget and callers can continue | Confirmed and repaired. Attempts are reserved before inference, every failed batch seals the oracle, infrastructure remains typed, and commit refuses a sealed oracle. |
| Arbitrary callbacks can look like counted CFD | Confirmed and repaired. Callbacks require the `ANALYTICAL_FIXTURE` wrapper; counted records require importer-sealed artifact provenance. |
| Verification budget/cache/retry accounting is undefined | Confirmed and repaired. The unit is condition evidence evaluation; repeat verification is refused, cache hits are charged, solver executions and retries are separate. |
| Reynolds number and velocity are enforced prediction gates | Rejected as a description of the implementation. Reynolds is a reference-applicability/population-screen check; velocity is diagnostic. The prior completion claim is corrected here. |
| Four arm outcomes / 24 condition uses support binomial reliability bounds | Confirmed as unsupported and repaired. The fixed pilot now reports descriptive arm outcomes, six unique selected cases and 18 reuses; no confidence bound or population/generalisation claim remains. |
| A known violation can disappear when another condition is unavailable | Confirmed and repaired. Explicit proposal outcomes make any confirmed violation `CONFIRMED_INFEASIBLE`; reference completeness remains separate and every proposal stays in the false-feasible denominator. |
| A best resolved feasible design always supports exact finite-set regret | Confirmed as incorrect and repaired. Potentially competitive unresolved designs withhold exact regret; a confirmed-infeasible design may be excluded despite unrelated missing evidence. |
| Comparator reference may be read before all proposal commitments exist | Confirmed and repaired. Construction and evaluation are separate CLI stages; evaluation restores all four commitment files before the first reference acquisition. |
| The 24-core-hour estimate is an enforced launch maximum | Confirmed as incorrect and repaired. Estimates are 19.2/24.0 core-hours; allocation ceilings are 96/120 core-hours. A durable pre-dispatch ledger enforces 48+12 executions, output binding, concurrency exclusion and retry eligibility. |
| Fixture agreement demonstrates a learned-model design-quality advantage | Rejected. The valid fixture outcome is agreement: all arms select `d03`; the learned model does not change or improve this decision, while screen-then-confirm uses fewer model queries. |

No review hypothesis in this focused repair was dismissed without a code or
evidence correction. The two rejected *claims* above are rejected because the
execution path and regenerated fixture show they are not supported.
