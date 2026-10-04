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
`carbon/cold_plate/decision_study.py`, and
`scripts/dev/cold_plate/decision_study.py`

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
   reference-feasible design in all 8 × 6 declared pairs. Regret is the selected
   minus comparator worst-case reference hydraulic power. Infeasible,
   unresolved and abstaining selections receive typed nonnumeric outcomes, not
   a favorable substitute value.

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
fixture regret was 0 W and observed false-feasible counts were 0/4 proposals
(Wilson 95% upper bound 0.4899) and 0/24 selected-condition decisions (upper
bound 0.1380). This confirms the workflow and illustrates the uncertainty from
small denominators. Because the pseudo-reference is the analytical model, it
does **not** establish learned-model accuracy, independent feasibility or
engineering value.

### Runnable first decision experiment

The scenario, constraints, model identities, registered methods, equal declared
budgets, reference allocation, retry cap, group policy, comparator, regret
policy and analysis rules are frozen before evidence access. The runner reports:

- reference-confirmed feasibility across all registered conditions;
- false-feasible proposals and condition decisions, each with an explicit
  denominator and Wilson 95% interval;
- abstention rate, resolved decision coverage and unavailable/invalid evidence;
- worst-case reference hydraulic power for feasible proposals and finite-set
  regret;
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
| Comparator/regret | Best reference-feasible design in the complete finite set; nonnumeric regret for infeasible, unresolved or abstaining selections | Checking all 48 pairs avoids judging only the selected design and avoids favorable imputation | Produces meaningful finite-set regret without a global-optimum claim | Science owner | Freeze authorization before counted analysis |
| Counted compute | 48 initial OpenFOAM executions; at most one retry per failed case; 12 retries reserved; hard cap 60; 2 CPUs/case; 6 parallel; 3600 s/case; retain all artifacts | Existing pinned runner and prior approximately 0.4 core-hour/case basis | Expected about 19.2 initial core-hours, never more than about 24 core-hours under the estimate | Compute/spend owner | Launch `reference.run_batch`; this is the smallest currently blocking approval |
| Group weighting and pass threshold | Keep representative and boundary groups separate; no combined weighting and no pass threshold | No approved customer population or acceptable error rate exists | Evidence remains descriptive; no pass/qualification claim | Science/customer owner | Only required before combining groups or declaring adequacy |
| Customer requirements and rights | Keep all actual customer values/data absent until supplied and rights-cleared | No customer evidence or rights were provided | Blocks customer acceptance, commercial validation and confidential-data use, but not the synthetic study | Customer/rights owner | Any customer-specific rerun or claim |

After the science and compute/spend owners approve the exact frozen plan, the
ready-to-run Linux commands are:

```bash
python -m scripts.dev.cold_plate.reference.run_batch \
  docs/development/studies/AI_ACCELERATOR_COOLING_SYNTHETIC_V1_CFD_PLAN.json \
  --out .carbon-artifacts/ai-cooling-cfd-attempt-1 \
  --parallel 6 --cpus 2 --timeout-s 3600 --keep all

# Only when attempt 1 has non-OK records; refuses more than the 12-case reserve.
python -m scripts.dev.cold_plate.decision_study plan-retry \
  --initial-dir .carbon-artifacts/ai-cooling-cfd-attempt-1 \
  --out .carbon-artifacts/AI_ACCELERATOR_COOLING_CFD_RETRY_PLAN.json
python -m scripts.dev.cold_plate.reference.run_batch \
  .carbon-artifacts/AI_ACCELERATOR_COOLING_CFD_RETRY_PLAN.json \
  --out .carbon-artifacts/ai-cooling-cfd-attempt-2 \
  --parallel 6 --cpus 2 --timeout-s 3600 --keep all

# Omit the second --reference-dir when no retry was needed.
python -m scripts.dev.cold_plate.decision_study counted \
  --reference-dir .carbon-artifacts/ai-cooling-cfd-attempt-1 \
  --reference-dir .carbon-artifacts/ai-cooling-cfd-attempt-2 \
  --out .carbon-artifacts/ai-cooling-counted-result
```

The plan file is repository-controlled; the heavy solver artifacts stay in the
ignored `.carbon-artifacts/` directory and must be retained for import/audit.

### Review-finding disposition

| Hypothesis | Disposition and code evidence |
| --- | --- |
| Duplicate queries can collapse at commitment | Confirmed and repaired. `Oracle.query` forbids duplicates within and across calls; focused tests cover both. |
| Failed model attempts do not consume budget and callers can continue | Confirmed and repaired. Attempts are reserved before inference, every failed batch seals the oracle, infrastructure remains typed, and commit refuses a sealed oracle. |
| Arbitrary callbacks can look like counted CFD | Confirmed and repaired. Callbacks require the `ANALYTICAL_FIXTURE` wrapper; counted records require importer-sealed artifact provenance. |
| Verification budget/cache/retry accounting is undefined | Confirmed and repaired. The unit is condition evidence evaluation; repeat verification is refused, cache hits are charged, solver executions and retries are separate. |
| Reynolds number and velocity are enforced prediction gates | Rejected as a description of the implementation. Reynolds is a reference-applicability/population-screen check; velocity is diagnostic. The prior completion claim is corrected here. |
