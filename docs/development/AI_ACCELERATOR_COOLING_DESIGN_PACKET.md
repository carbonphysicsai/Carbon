# AI accelerator cooling — customer decision design packet

**Status:** PROSPECTIVE DEVELOPMENT FOUNDATION

**Challenge:** `chip-cold-plate`

**Scientific families:** f04 laminar internal flow, supported by f03 steady
conduction

**Current physical scope:** periodic straight-channel cell v1

**Pipeline state:** prior work only; this packet does not enter the challenge
pipeline, sign a gate, or bypass the battery-defined protocol lock

**Authority:** OWNER-CHALLENGE-FOUNDATION-01; existing physical values remain
under OWNER-CHALLENGE-DESIGN-01

**Implementation:** `carbon/cold_plate/customer_decision.py`

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

**Customer requirements still open.** `HUMAN_INPUT(customer)` for the die limit,
hydraulic limit, actual facility envelope, manufacturing rules, reliability
margin and acceptable verification uncertainty. These values are not inferred
from the DEVELOPMENT population screen.

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

Only `DEVELOPMENT` material and mode `PB-INV` are served. Every model query must
be one declared design-condition point and fit inside the query budget. A model
must return exactly peak temperature, the 30-segment temperature profile and
pressure drop, and pass the existing physical gates. A malformed or physically
invalid prediction stops the study; it cannot disappear from the denominator.

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

A proposal commitment is written with exclusive creation before the reference
callback can run. Verification evaluates the committed design at every declared
condition and reports `FEASIBLE`, `INFEASIBLE` or `REFERENCE_UNAVAILABLE`.
`INFEASIBLE` after a model-feasible proposal is a visible false-feasible event.
Unavailable evidence is never counted safe or unsafe. The result explicitly
denies global-optimum, customer-acceptance, scientific-qualification and
production-qualification claims.

Measurement definition for a physical rig is `HUMAN_INPUT(science)`: sensor
locations, spatial/temporal aggregation, pressure/flow measurement, calibration,
uncertainty, repeatability, missing data and model-to-instrument comparison.

## 7. Construction contract

The existing physics-aware analytical model is the v1 fixed engineering
baseline. Carbon's challenge-neutral design-search harness can compare its
exhaustive fixed-grid rule with registered, bounded search methods at equal
model-query budgets. It reconstructs only registered Python code and treats a
found design as best-known within the declared candidate grid, never globally
optimal.

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
- tests that exercise customer-contract binding, grid/condition scope, budgeted
  access, physical-gate refusal, selection, write-once commitment, reference
  separation, false-feasible reporting and generic search reuse.

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

### Next counted decision evidence

After protocol lock and admission, pre-register independent design scenarios,
customer constraints, fixed model/search budgets, the baseline, tie policy,
reference allocation and failure handling. Compare model-selected and
reference-backed decisions at equal budgets. Report at least rank agreement,
regret, false-feasible count and its uncertainty bound, abstentions, unavailable
references, inference/reference cost and latency. Thresholds and acceptable
uncertainty remain `HUMAN_INPUT(science/customer)`.

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
| Customer design search | IMPLEMENTED and locally testable | Counted decision study under a frozen protocol |
| Full plate/manifold | NOT IMPLEMENTED | New version, reference, population, packet and evidence |
| Burst-power linkage | NOT IMPLEMENTED here | Separate f02 challenge and later composition contract |
| Experimental validation | NOT STARTED | Instrument/measurement contract and rig evidence |
| Challenge pipeline | QUEUED PRIOR WORK | Battery protocol lock, queue entry and owner gates |
| Scientific qualification | NO | Human science approval on exact evidence |
| Security qualification | NO | Dedicated review of any untrusted execution surface |
| Commercial validation | NO | Customer evidence and rights-cleared study |
| Production qualification / LIVE | NO | All applicable scientific, security, customer and launch gates |

### Owner decisions required before the next physical version

1. `HUMAN_INPUT(customer)`: die-temperature and hydraulic-power requirements,
   facility/coolant envelope and manufacturing constraints.
2. `HUMAN_INPUT(science)`: target population, sampling/weighting, reference
   applicability, uncertainty treatment, measurement contract and acceptance
   thresholds.
3. `HUMAN_INPUT(technical)`: bounded manifold/topology grammar, construction
   level contract and execution/isolation resources.
4. `HUMAN_INPUT(process)`: protocol lock, queue entry, budgets and stage gates.
5. `HUMAN_INPUT(rights/customer)`: permission for any customer geometry,
   workload, test data or confidential facility constraints.
