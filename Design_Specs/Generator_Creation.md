# Generator Creation — Human Build Guide, Reference Verification, and Incentive Defensibility

**Carbon Subnet**  
**Version:** 5.0  
**Status:** OWNER-RECOMMENDED architecture; Challenge-specific scientific acceptance remains evidence- and reviewer-owned.  
**Purpose:** Explain, in human-readable form, exactly what Carbon builds when it creates a Challenge data generator, how the code is structured, how generated cases are tied to qualified reference values, how the generator is verified, and why this can support a scientifically defensible incentive mechanism.  
**Related:** [`Generator_Validation.md`](./Generator_Validation.md), [`Challenge_Instance_Distribution.md`](./Challenge_Instance_Distribution.md), [`Evidence_and_Envelope_Standards.md`](./Evidence_and_Envelope_Standards.md), [`Data_Management.md`](./Data_Management.md), [`Scoring.md`](./Scoring.md), [`Physical_System_Representation.md`](./Physical_System_Representation.md), [`Build_Out.md`](./Build_Out.md), `SPEC.md`.

---

# 0. Read this first

The phrase **data generator** can be misleading because it sounds like one program both invents a physics case and declares the correct answer.

Carbon must not work that way.

For an authoritative Challenge, the end-to-end data pipeline is split into two independent scientific jobs:

```text
A. CASE GENERATOR
   creates a physical problem instance

B. REFERENCE REALIZER
   computes or obtains the best qualified answer for that exact instance
```

Only after both are bound together do we obtain a training or evaluation example:

```text
CanonicalChallengeCase
        +
QualifiedReferenceRealization
        ↓
Reference-labelled scientific example
```

That separation is foundational.

> **The generator creates the question. The qualified reference process supplies the answer. The generator is never allowed to grade itself.**

Carbon also does **not** claim that a Validation Dossier creates absolute physical truth. The defensible claim is narrower:

> **For an exact registered physical task and population, Carbon may use a reference process only after evidence shows that its uncertainty, disagreement, applicability, and failure regions are sufficiently characterized to support the comparison the Challenge intends to make.**

The complete project therefore produces four things:

1. **Scientific task definition** — what physical problem and population Carbon claims to test.
2. **Executable case generator** — code that produces fresh, reproducible cases from that population.
3. **Reference-evidence package** — hard evidence showing why the answer path is trustworthy enough, and to what resolution.
4. **Implementation-evidence package** — tests showing the software actually implements the registered task without silently changing it.

The full flow is:

```text
DEFINE THE PHYSICAL JOB
        ↓
DEFINE THE TARGET POPULATION
        ↓
DESIGN THE CASE PARAMETERIZATION
        ↓
IMPLEMENT THE CASE GENERATOR
        ↓
IMPLEMENT / QUALIFY THE REFERENCE PATH
        ↓
VERIFY GENERATOR + REFERENCE TOGETHER
        ↓
QUALIFY THE MEASUREMENTS
        ↓
PROVE THE EXAM CAN RESOLVE REAL DIFFERENCES
        ↓
VALIDATION DOSSIER
        ↓
SCORE PACK
        ↓
LIVE INCENTIVE MECHANISM
```

The governing principle is:

> **The exam must earn the right to create economic consequences.**

---

# 1. What we actually build

A Carbon generator is not a magical PDE-data machine. It is a deliberately bounded software pipeline that turns registered random material into a fully specified physical case.

The simplest representation is:

```text
registered task
+ registered population
+ registered SamplingPlan
+ authorized random seed/context
        ↓
CASE GENERATOR
        ↓
CanonicalChallengeCase
```

A `CanonicalChallengeCase` contains the complete physical question needed by a candidate and by the reference system.

Depending on the Challenge, that can include:

- domain and geometry;
- physical parameters;
- material properties;
- initial conditions;
- boundary conditions;
- forcing;
- requested prediction times or query locations;
- internal stratum/category metadata;
- exact provenance and version bindings.

It does **not** yet contain a candidate score and does not need to contain the authoritative answer.

The reference system then consumes the exact same canonical case:

```text
CanonicalChallengeCase
        ↓
ReferenceRunner
        ↓
ReferenceRealization
```

A dataset row or evaluation case is therefore assembled from two separately auditable objects:

```text
INPUT / PHYSICAL CASE    = generator output
TARGET / REFERENCE VALUE = qualified reference output
```

This distinction is the easiest way to explain Carbon's architecture to a skeptical reviewer.

---

# 2. How the generator is built — step by step

This section describes the actual build process, not just the abstract interfaces.

## Step 1 — Freeze the physical mapping

First define exactly what the candidate is being asked to learn or predict.

For the recommended first Burgers Challenge:

```text
PDE:
    u_t + u u_x = ν u_xx

Domain:
    periodic 1D

Viscosity:
    fixed ν = 5×10⁻³

Input:
    initial field u(x,0)

Output:
    field u(x,T) at registered T
```

Why fixed viscosity first?

Because if viscosity varies but is not supplied to the candidate, the same apparent input can correspond to different correct outputs. That makes the learning problem underdetermined. The first Challenge should remove that ambiguity rather than hide it inside the generator.

**Build output:** `PhysicalSystemSpec` + `CandidateOutputContract`.

---

## Step 2 — Define the target population before writing the sampler

Next decide what kinds of initial conditions count as members of the Challenge.

For Burgers v1, Carbon should use a bounded family of **smooth periodic initial conditions**. A practical implementation can represent an initial field through a finite Fourier basis, for example conceptually:

```text
u₀(x) = c₀ + Σ_k [a_k cos(kx) + b_k sin(kx)]
```

The exact number of modes, coefficient distributions, amplitude limits, smoothness constraints, correlations, exclusions, and strata must be registered and scientifically reviewed rather than improvised in code.

The important distinction is:

```text
PARAMETERIZATION
How we represent possible cases

TARGET POPULATION P(x)
How physically relevant cases are distributed over that representation
```

The generator implementation must consume this population definition. It does not get to define it accidentally by whatever random-number calls are convenient.

**Build output:** `InstanceDistributionContract`.

---

## Step 3 — Define how the finite data are drawn

The target population does not automatically tell us how many finite cases to draw or how to allocate them.

Carbon therefore defines a separate `SamplingPlan Q(x)`.

For example, suppose edge-of-envelope steep-gradient cases are rare under the target population but scientifically important. Carbon may deliberately oversample them in evaluation so that their failure rate can actually be measured.

That means:

```text
P(x) = population the claim concerns
Q(x) = how finite cases are drawn
w(x) = how sampled evidence contributes to the estimand / score
```

These must not be silently collapsed.

**Build output:** versioned `SamplingPlan`.

---

## Step 4 — Implement deterministic latent-variable sampling

Now write the sampling code.

The sampler receives only authorized random material and exact registered identities. It uses those to draw the latent variables required by the population and SamplingPlan.

For a Fourier-based Burgers initial condition that may mean drawing, in a registered order:

```text
stratum
mean / offset if allowed
active spectral modes
mode amplitudes
a_k coefficients
b_k coefficients
phase-like quantities if part of the parameterization
```

The implementation must use a deterministic RNG profile and deterministic draw order. It must not depend on ambient process state such as:

- system clock;
- Python `hash()`;
- filesystem ordering;
- mutable global RNG state;
- validator identity;
- leaderboard state.

Given the same exact authorized request, the same canonical case must be reproduced.

**Build output:** deterministic sampler code + golden-vector tests.

---

## Step 5 — Convert latent variables into a physical initial condition

The next function maps sampled latent variables into the actual physical field.

For Burgers this means constructing the periodic field `u₀(x)` on the canonical physical representation, then applying any registered normalization or amplitude/smoothness constraints.

The constructor verifies structural requirements such as:

- periodicity;
- finite values;
- allowed amplitude;
- allowed spectral complexity;
- valid parameter signs;
- no excluded regime;
- exact fixed viscosity;
- required domain and query semantics.

A failed construction is recorded as a typed failure. The implementation may not silently keep drawing until it happens to find an easier case unless that retry/rejection behavior is itself part of the registered SamplingPlan and accounted for in conformance evidence.

**Build output:** physics-specific case constructor.

---

## Step 6 — Produce a representation-neutral canonical case

The physical case is then bound into an immutable `CanonicalChallengeCase`.

Conceptually:

```text
CanonicalChallengeCase {
    case_identity
    challenge_identity
    distribution_identity
    sampling_plan_identity
    generator_identity
    role
    physical_domain
    parameters
    initial_conditions
    boundary_conditions
    forcing
    requested_outputs
    internal_stratum_metadata
    provenance
}
```

Why not immediately turn this into an FNO tensor?

Because the scientific problem should not be defined by the first model architecture Carbon happens to use. The same canonical case should later be materializable for an FNO, graph network, ROM, symbolic method, finite-volume surrogate, or other future model family without changing the underlying physics question.

**Build output:** immutable canonical case + stable identity.

---

## Step 7 — Materialize the case for the intended consumer

Adapters convert the canonical case into the representation needed by a particular consumer:

```text
CanonicalChallengeCase
        ├──→ training tensor adapter
        ├──→ candidate evaluation adapter
        ├──→ Cole–Hopf reference adapter
        └──→ numerical witness adapter
```

Each adapter must preserve the same physical case.

Representation-parity tests check that parameters, ICs, BCs, coordinates, units, query times, and geometry identity are not changed during materialization.

**Build output:** tested representation adapters.

---

## Step 8 — Run the independent reference path

The same canonical case is supplied to the primary reference implementation.

For Burgers v1:

```text
CanonicalChallengeCase
        ↓
periodic Cole–Hopf reference implementation
        ↓
ReferenceRealization
```

An independent high-resolution conservative numerical solver is used as a corroborating witness on the registered audit campaign.

The case generator does not import or control either reference implementation.

**Build output:** primary reference + independent witness, separately versioned and pinned.

---

## Step 9 — Assemble training/evaluation examples

Only now can Carbon form a labeled example:

```text
CanonicalChallengeCase.input
        +
ReferenceRealization.output
        ↓
reference-labelled example
```

For **training**, reference-labelled cases can be generated from the TRAIN role and used by the independently reconstructed candidate according to the allowed training budget.

For **evaluation**, validators create fresh hidden EVAL cases and corresponding qualified reference values. Miners do not receive those hidden realizations.

For **stress**, validators create fresh hidden cases from prospectively registered difficult in-envelope strata.

So the same scientific generator architecture supports all three roles, while the seed domains and visibility rules remain separate.

---

## Step 10 — Verify the implementation before it can be authoritative

The implementation now undergoes two different campaigns:

```text
CAMPAIGN G — DISTRIBUTION CONFORMANCE
Did we build the questions correctly?

CAMPAIGN R — REFERENCE + NUMERICAL ADEQUACY
Are the answers and generated realizations accurate enough?
```

Both must pass before LIVE.

---

# 3. What the code should look like

A production-capable implementation should converge toward this ownership map:

```text
carbon/generators/
    model.py
    contracts.py
    sampling.py
    service.py
    evidence.py
    conformance.py
    failures.py
    burgers/
        population.py
        generator.py
        canonical_case.py
        reference_cole_hopf.py
        reference_witness.py
        measurements.py
        evidence_campaign.py
```

This is not a requirement to create empty files. It describes where authority belongs.

### `model.py`

Owns immutable IDs, versions, roles, case metadata, and failure/status values.

**Why:** identity semantics must be shared rather than reimplemented differently for each PDE.

### `contracts.py`

Defines structural interfaces such as:

```text
ChallengeInstanceGenerator.generate(...) -> CanonicalChallengeCase
ReferenceRunner.solve(...) -> ReferenceRealization
DistributionConformanceRunner.run(...) -> ConformanceReport
ReferenceEvidenceRunner.run(...) -> ReferenceEvidenceBundle
```

**Why:** Carbon standardizes what must be observable and auditable while allowing different physics families to use different numerical methods.

### `sampling.py`

Implements the registered finite SamplingPlan and deterministic draw mechanics.

**Why:** finite evidence design is not the same thing as the scientific population.

### `service.py`

Checks exact identities and composes the authorized seed context, sampler, generator, and evidence hooks.

It rejects a request if the challenge, distribution, SamplingPlan, generator version, or role do not match.

**Why:** correct code executed against the wrong scientific version is still the wrong exam.

### `evidence.py`

Defines machine-readable case evidence, reference evidence, disagreement records, generator-reference comparisons, measurement floors, and run manifests.

**Why:** a scientific claim should be rebuildable from retained evidence rather than screenshots and prose.

### `conformance.py`

Runs large generator campaigns and tests support, marginals, joints, conditionals, strata, duplicates, replay, exclusions, censoring, and role isolation.

**Why:** agreement with a reference solver does not prove that the generator samples the intended population.

### `burgers/population.py`

Owns the Burgers-specific parameterization and implementation of the registered smooth periodic IC population.

### `burgers/generator.py`

Maps authorized sampled latent variables into a validated canonical Burgers case.

### `burgers/canonical_case.py`

Defines the representation-neutral Burgers physical case and its stable identity.

### `burgers/reference_cole_hopf.py`

Implements the primary reference path independently from case generation.

### `burgers/reference_witness.py`

Wraps the independent high-resolution conservative numerical witness.

### `burgers/measurements.py`

Implements only qualified Burgers measurements. It does not choose their score weights or invent thresholds.

### `burgers/evidence_campaign.py`

Runs the prospectively registered conformance/reference audit plan and emits the machine-readable evidence package.

---

# 4. Generator-to-reference verification procedure

Once the generator exists, Carbon has to show that the end-to-end generated/reference-labelled data are accurate enough to support an incentive decision.

This is not a single `assert error < X` test.

## 4.1 Qualify the primary reference first

For prospectively selected audit cases:

```text
CanonicalChallengeCase
        ↓
PRIMARY REFERENCE
        ↓
INDEPENDENT WITNESS
        ↓
REFERENCE AGREEMENT / UNCERTAINTY ANALYSIS
```

For Burgers v1:

```text
PRIMARY
periodic Cole–Hopf implementation

SECONDARY WITNESS
independently implemented high-resolution conservative solver
```

The witness is corroborating evidence, not truth by brand name.

Each case receives a reference status such as:

```text
AGREE_WITHIN_QUALIFIED_UNCERTAINTY
PRIMARY_SUPPORTED_BY_WITNESS
REFERENCE_UNCERTAIN
REFERENCE_DISAGREEMENT
REFERENCE_NUMERICAL_FAILURE
REFERENCE_FAILED_INFRA
REFERENCE_NOT_APPLICABLE
```

Unresolved reference failure does not become candidate failure.

---

## 4.2 Run all relevant paths on the exact same physical case

For every audit case:

```text
REGISTERED CANONICAL CASE
        ├──→ primary reference
        ├──→ independent witness
        └──→ production generator/reference path under test
```

Retain at minimum:

- exact case identity;
- all software/environment identities;
- primary output;
- witness output;
- production generated/reference output;
- primary-vs-witness discrepancy;
- production-vs-primary discrepancy;
- production-vs-witness discrepancy;
- physical diagnostics;
- stratum/regime;
- uncertainty;
- every failure/censoring state.

The comparison is case-level first and aggregate second.

---

## 4.3 Compare what Carbon will actually score

The verification must use the same scientific quantities that matter to the Challenge.

For Burgers this should include, where qualified:

- field error versus Cole–Hopf;
- field error versus the numerical witness;
- periodic mean/mass conservation;
- energy non-increase/dissipative behavior;
- maximum-principle consistency where applicable;
- time/query-specific error if multiple outputs are used;
- error by stratum;
- error near envelope boundaries.

A convenient global norm is not enough if the incentive mechanism depends on properties that norm can hide.

---

## 4.4 Audit the whole qualified envelope

The audit set is registered before inspecting generator performance and should deliberately cover:

```text
ordinary interior cases
boundary-near cases
hard / stress strata
known numerical-risk regions
simple / limiting cases
```

The audit asks whether error or failure systematically grows in particular regions.

A small average error does not rescue a generator that fails exactly where the Challenge claims robustness.

---

## 4.5 Build a measurement-specific error budget

The result is not `generator_valid = true`.

Carbon records an error/uncertainty budget by measurement and relevant stratum:

```text
reference uncertainty
+ production generator/reference discrepancy
+ measurement numerical floor
        ↓
qualified exam uncertainty for that quantity
```

The exact statistical treatment is Challenge-specific.

The critical test is:

> **Is the exam's uncertainty materially smaller than the candidate differences Carbon intends to reward?**

If not, the incentive mechanism is attempting to pay for distinctions the scientific system cannot actually resolve.

---

## 4.6 Run the generator-oracle adversarial test

Construct, where feasible, two controlled candidates:

```text
Candidate A follows generator-specific bias
Candidate B follows the stronger qualified physical reference
```

Then run both through the proposed measurements and scoring path.

If Candidate A can win because the scoring system has mistaken generator error for physical truth, the Challenge is STOP-SHIP.

> **A self-consistent wrong answer must not beat a better physical answer merely because the wrong answer was produced by Carbon's generator stack.**

---

## 4.7 Explicit qualification outcomes

The generator/reference campaign ends in one of the following:

```text
QUALIFIED
Evidence supports the intended envelope and resolution.

QUALIFIED_WITH_LIMITATIONS
Usable only with a narrower envelope or coarser scientific claim.

REPAIR_REQUIRED
Generator/reference implementation must improve.

REFERENCE_BLOCKED
The reference itself is too uncertain to judge the generator.

LIVE_BLOCKED
Combined uncertainty is too large or poorly characterized to support incentives.
```

Weak evidence never becomes a convenient lower standard after seeing candidate results.

---

# 5. Why this is defensible for the incentive mechanism

The incentive mechanism creates the strongest burden of proof in the architecture because Carbon is not merely publishing a benchmark score; it is assigning economic consequences to the result.

The scientific design is defensible only if the following chain holds.

## 5.1 The rewarded objective is prospectively defined

Before miners compete, Carbon registers:

- the physical task;
- target population;
- finite SamplingPlan;
- reference policy;
- measurements;
- admissibility conditions;
- score-use contract.

**Why this matters for incentives:** nobody can change the scientific meaning after seeing who would win.

This guards against retrospective benchmark design and favoritism.

---

## 5.2 The producer does not control the official exam

Miners may influence allowed training strategy choices, but the official EVAL and STRESS realizations are generated by validators from protected role-separated randomness.

**Why this matters for incentives:** a miner cannot simply memorize or manufacture the answer key it will later be rewarded for passing.

---

## 5.3 The case generator does not control the reference answer

Carbon separates:

```text
question generation
        !=
answer generation
```

The reference path is separately implemented, versioned, evidenced, and checked by an independent witness where required.

**Why this matters for incentives:** the system does not economically reward conformity to a single unverified software artifact.

---

## 5.4 Reference uncertainty is visible rather than hidden

The dossier records where the reference agrees, disagrees, becomes uncertain, fails numerically, or is not applicable.

**Why this matters for incentives:** uncertainty is not silently converted into miner failure or an arbitrary winner.

If Carbon cannot distinguish two candidates scientifically, the economic layer must not pretend it can.

---

## 5.5 Mandatory physical failure cannot be bought back with accuracy

Qualified mandatory physics conditions are checked before ranking.

A model that obtains low average field error while violating a mandatory physical property can be made inadmissible rather than compensated by another score component.

**Why this matters for incentives:** miners are not rewarded for exploiting a scalar average while producing scientifically unacceptable behavior.

---

## 5.6 Hidden stress evidence attacks brittle optimization

Stress cases are fresh, hidden, prospectively defined, and remain inside the declared envelope.

**Why this matters for incentives:** a strategy that overfits ordinary/easy cases but breaks in decision-relevant hard regimes cannot rely on the average benchmark distribution to hide that weakness.

Stress is not arbitrary punishment; it is deeper evidence inside the job Carbon already said the candidate should handle.

---

## 5.7 Scientific resolution limits economic resolution

Carbon estimates reference uncertainty, measurement floors, reconstruction variance, and finite-exam variance.

Conceptually:

```text
reference uncertainty
+ generator/reference error
+ measurement uncertainty
+ reconstruction variance
+ evaluation-sampling variance
        ↓
SCIENTIFIC RESOLUTION
```

**Why this matters for incentives:** Carbon should not pay Candidate A for a 0.1% apparent lead if the experiment itself fluctuates by 1%.

Economic reward concentration must not be sharper than scientific resolution.

---

## 5.8 Frontier promotion uses common fresh evidence

Ordinary Challenge scoring can nominate contenders. A proposed new leader should then be compared with the incumbent on the **same fresh common promotion evidence** under the registered resolution rule.

Possible outcomes are:

```text
SUPERIOR
NOT_SUPERIOR
INDETERMINATE
```

Only `SUPERIOR` creates a frontier advance.

**Why this matters for incentives:** Carbon does not replace a frontier leader because two candidates happened to see different random exams or because of a meaningless floating-point lead.

---

## 5.9 Provenance makes the economic event auditable

Every material scientific object is version- and content-bound:

```text
Challenge
Population
SamplingPlan
Generator
ReferencePolicy
Measurements
Score Pack
Case identities
Evaluation evidence
```

**Why this matters for incentives:** the economic event can be traced back to the exact scientific contract and evidence that created it. A later software update cannot silently reinterpret an old reward.

---

## 5.10 The system fails closed

If a required reference is unresolved, the generator is nonconformant, a measurement is unqualified, censoring distorts the exam, or evidence is too weak, LIVE is blocked or the claim is narrowed.

**Why this matters for incentives:** absence of evidence does not become a score of zero for a miner, and protocol pressure to emit rewards does not create scientific authority.

---

## 5.11 The actual defensible IM claim

Carbon should not claim:

> “The network always knows physical truth.”

The defensible statement is:

> **Carbon only creates an incentive-bearing scientific comparison when the task, population, generator, reference process, measurements, uncertainty, and finite resolution have been prospectively qualified strongly enough to support that bounded comparison. When the evidence cannot resolve a winner, the protocol must not manufacture one.**

That is the epistemic basis of the incentive mechanism.

---

# 6. Two validation campaigns that must both pass

## Campaign G — Distribution conformance

**Question:** Did we build the questions correctly?

Retain:

- realized marginals;
- joint and conditional checks;
- support/exclusion compliance;
- stratum/tail frequencies;
- duplicate/near-duplicate rates;
- invalid-case rates;
- failure rates by stratum;
- intended-versus-realized distribution after censoring;
- deterministic replay;
- TRAIN/EVAL/STRESS isolation.

A generator can produce excellent numerical solutions and still fail Campaign G because it samples the wrong scientific population.

## Campaign R — Reference and numerical adequacy

**Question:** Are the answers accurate enough for the decision?

Retain:

- primary-reference verification;
- independent-witness evidence;
- refinement/precision studies;
- reference disagreement;
- generator/reference discrepancy;
- physical diagnostics;
- uncertainty/floors;
- failure maps;
- implications for scientific resolution.

A generator must pass both campaigns before supporting a LIVE exam.

---

# 7. What “reference truth” means

Prefer the terms:

- **reference**;
- **reference realization**;
- **qualified reference evidence**;
- **authoritative reference within a stated uncertainty**.

Reserve “truth” for cases where the mathematics or physical evidence justifies unusually strong language.

Three practical classes are useful:

### Class A — analytic / semi-analytic

Strongest case when assumptions and implementation are controlled. Even an exact derivation still has implementation error from quadrature, transforms, truncation, interpolation, or finite precision.

### Class B — qualified numerical

A numerical solution with verification, convergence, uncertainty, applicability, and failure evidence.

### Class C — engineering evidence

Experimental, telemetry, partner-golden, calibrated multi-fidelity, or hybrid evidence with explicit measurement and model uncertainty.

The claim must become narrower as reference uncertainty and model-form dependence increase.

---

# 8. Hard evidence required for the reference

Every authoritative reference campaign retains reconstructible case-level data.

## Identity and provenance

At minimum:

```text
challenge_id / challenge_version
PhysicalSystemSpec identity + digest
CandidateOutputContract identity
InstanceDistributionContract identity + digest
SamplingPlan identity + digest
generator version + digest
reference policy identity + version
reference implementation source/version
container/environment digest
runtime/library/compiler versions where material
hardware profile where material
precision policy
reference configuration
measurement implementation identities
case IDs / audit commitments
run manifest / timestamp
```

## Case-level inputs

Retain enough to reconstruct the exact physical problem:

- parameters;
- ICs;
- BCs;
- forcing;
- geometry/topology where relevant;
- output/query times or locations;
- stratum/category;
- population/proposal metadata;
- reference applicability status.

## Case-level outputs

Retain:

- field/trajectory values or content-addressed artifact;
- coordinates/query representation;
- units/scaling;
- solver status;
- convergence/termination information;
- scientifically meaningful residual/defect data;
- invariant/balance diagnostics;
- interpolation/materialization steps;
- uncertainty estimate.

## Additional evidence by reference class

Analytic/semi-analytic references should include, as applicable:

- governing-equation recovery;
- IC/BC recovery;
- invariants/monotonicity;
- limiting/simple cases;
- independent implementation checks;
- transform/quadrature/truncation/precision sensitivity;
- failure/ill-conditioning map.

Numerical references should include, as applicable:

- manufactured/analytic/benchmark verification cases;
- spatial and temporal refinement;
- observed convergence behavior;
- solver-tolerance sensitivity;
- scheme/configuration sensitivity where material;
- conservation/balance evidence;
- failure/conditioning map;
- independent witness;
- reference uncertainty estimate.

Experimental/telemetry references should include, as applicable:

- instrument identity/calibration;
- measurement uncertainty;
- sampling rate/resolution;
- preprocessing/filtering;
- synchronization;
- test/environment conditions;
- missingness/censoring;
- replicates;
- drift/recalibration history;
- provenance/chain of custody;
- transformation to Challenge observable;
- known systematic bias and applicability limits.

---

# 9. Reference disagreement is evidence

When credible reference paths disagree, retain the disagreement explicitly:

```text
case identity
reference A identity/config/output
reference B identity/config/output
discrepancy by qualified measurement
spatial/temporal structure of discrepancy
stratum/regime
uncertainty of each path
investigation status
supported cause if known
resolution / unresolved status
impact on claim/envelope
```

Permitted responses are to investigate, increase uncertainty, narrow the envelope, weaken the measurement claim, mark the comparison indeterminate, or block LIVE.

Forbidden: silently average incompatible references to manufacture a convenient answer.

---

# 10. Burgers v1 concrete build and verification

The recommended first authoritative Challenge is fixed-viscosity 1D periodic viscous Burgers:

```text
u_t + u u_x = ν u_xx
ν = 5×10⁻³
periodic 1D domain
registered smooth periodic IC population
```

A practical first implementation should therefore be built as follows:

```text
registered smooth-periodic IC parameterization
        ↓
deterministic latent coefficient sampler
        ↓
Fourier / registered basis IC constructor
        ↓
structural validation
(periodic, finite, amplitude/spectral bounds)
        ↓
CanonicalBurgersCase
        ├──→ candidate/training adapter
        ├──→ Cole–Hopf primary reference
        └──→ independent conservative numerical witness
```

The exact Fourier-mode count, coefficient law, normalization, amplitude range, spectral-complexity range, prediction horizon, numerical representation, and stratum allocations remain scientific inputs to be ratified and qualified. They must not be invented merely to complete the code.

### Primary reference evidence

For Cole–Hopf retain:

- exact source/environment identity;
- IC recovery at `t=0` or nearest meaningful limit;
- periodicity error;
- spatial-mean conservation;
- dissipative energy behavior;
- maximum-principle consistency where applicable;
- separately qualified equation-defect diagnostics if used;
- transform/quadrature/truncation/resolution sensitivity;
- precision sensitivity where material;
- ill-conditioning/failure cases;
- content-addressed audit outputs.

### Independent witness evidence

Retain:

- solver/version/environment;
- numerical scheme;
- grid/time-step refinement sequence;
- solver tolerances;
- outputs at each refinement;
- convergence behavior;
- conservation diagnostics;
- failure/status;
- witness-vs-Cole–Hopf discrepancy by case and stratum.

### Production generator/reference evidence

Retain:

- exact canonical case;
- production output/reference realization;
- production-vs-Cole–Hopf discrepancy;
- production-vs-witness discrepancy;
- physical diagnostics;
- stratum;
- failure/censoring state;
- error concentration near boundaries/hard regimes.

Burgers v1 is STOP-SHIP if material evidence shows:

- generator/reference error comparable to the candidate differences Carbon intends to reward;
- generator-oracle bias can beat a qualified physical-reference oracle;
- primary and witness disagree materially without bounded explanation;
- hard strata systematically coincide with reference failure/censoring;
- score thresholds fall below the qualified reference/measurement floor;
- a final-state spatial-balance proxy is presented as a full PDE residual despite missing `u_t`;
- reconstruction/evaluation variation materially flips decisions without an indeterminate policy.

---

# 11. Required test layers before LIVE

### A. Unit correctness

Examples: bounds, Fourier/IC construction, exclusion logic, deterministic replay.

### B. Property / invariant tests

Examples: finite values, valid dimensions/signs, periodic consistency, stable serialization, no role crossing.

### C. Distribution conformance

Empirically verify marginals, joints, conditionals, strata, support coverage, duplicates, and realized distribution after failures.

### D. Reference adequacy and generator-to-reference verification

Run the procedure in Section 4 and show that uncertainty is small enough for the intended scientific/economic decision.

Also require explicit tests for:

- TRAIN/EVAL/STRESS role isolation;
- version mismatch rejection;
- boundary/exclusion behavior;
- censoring/failure visibility;
- mutation after case identity binding;
- representation parity across model-family adapters.

> **Passing software tests does not scientifically qualify the exam. Scientific qualification also does not excuse failing software tests.**

---

# 12. Measurement qualification uses the same evidence

Each score-eligible `MeasurementContract` should have a qualification record containing:

```text
measurement_id / version
scientific property claimed
required observables
reference path
numerical operator/discretization
normalization/aggregation
reference/numerical floor
applicability rule
known failure modes
uncertainty summary
role: mandatory / soft / diagnostic
threshold or scale derivation method
```

A governing equation does not automatically justify a residual metric. A conservation law does not automatically justify a universal tolerance.

The Score Pack uses qualified evidence. The ScoreEngine does not invent scientific truth.

---

# 13. Evidence tables required in the Validation Dossier

At minimum:

| Table | Contents |
|---|---|
| **R0 — Identity** | exact software, environment, configuration, artifacts, hashes |
| **R1 — Audit coverage** | cases by stratum, boundary/risk region, reference path, status |
| **R2 — Reference implementation checks** | IC/BC, invariants, precision/refinement, limiting cases |
| **R3 — Numerical convergence / witness** | per-refinement outputs, convergence, tolerance sensitivity, failures |
| **R4 — Reference disagreement** | primary-vs-witness discrepancy, uncertainty, disposition, envelope impact |
| **R5 — Generator-vs-reference** | case/stratum discrepancies, failures, boundary concentration |
| **R6 — Measurement floors** | qualified floor/uncertainty for every score-eligible measurement |
| **R7 — Decision resolution** | repeated reconstruction/evaluation, gate/rank flips, contested band |
| **R8 — Limitations** | every weakened or blocked region/quantity/measurement |

Summary plots are useful explanations, but the authoritative decision must be reproducible from underlying data.

---

# 14. Human-review checklist

A skeptical reviewer should be able to answer:

1. What exact physical mapping is being tested?
2. How are possible cases parameterized?
3. What target population exists over those cases?
4. How does the finite SamplingPlan draw from it?
5. Which exact code turns a seed into a physical case?
6. Can that exact case be reproduced?
7. What code independently computes the answer?
8. What evidence validates that reference implementation?
9. What independently checks it?
10. How far is the production generated/reference data from the strongest reference?
11. Does that error grow in difficult regimes?
12. Can hard cases disappear through retries or censoring?
13. Could a generator-specific bias make the wrong candidate win?
14. What is the numerical/measurement floor?
15. How small a candidate difference can the exam actually resolve?
16. What happens if the evidence cannot resolve a winner?
17. Can any miner, validator, treasury component, or score code silently change the scientific task?
18. Can the eventual economic reward be traced to the exact evidence and versions that justified it?

If these cannot be answered from code and retained evidence, the Challenge is not ready to carry incentives.

---

# 15. Creation sequence

```text
1. DEFINE PHYSICAL JOB
2. DEFINE TARGET POPULATION P(x)
3. CHOOSE CASE PARAMETERIZATION
4. DEFINE SAMPLING PLAN Q(x)
5. IMPLEMENT DETERMINISTIC SAMPLER
6. IMPLEMENT PHYSICS-SPECIFIC CASE CONSTRUCTOR
7. BIND CANONICAL CASE IDENTITY
8. IMPLEMENT MODEL/REFERENCE ADAPTERS
9. IMPLEMENT PRIMARY REFERENCE
10. IMPLEMENT INDEPENDENT WITNESS WHERE REQUIRED
11. RUN DISTRIBUTION-CONFORMANCE CAMPAIGN
12. RUN REFERENCE-QUALIFICATION CAMPAIGN
13. RUN GENERATOR-TO-REFERENCE VERIFICATION
14. QUALIFY MEASUREMENTS
15. RUN SCIENTIFIC-RESOLUTION STUDY
16. ASSEMBLE VALIDATION DOSSIER + R0–R8
17. BIND SCORE PACK
18. HUMAN LAUNCH-BAR SIGN-OFF
19. REGISTRY LIVE
```

Candidate leaderboard outcomes do not choose the population, reference policy, or scientific thresholds except through a separately versioned prospective redesign.

---

# 16. Definition of Done

## Implementation-ready for scientific review

- physical mapping is explicit;
- target population and parameterization are explicit;
- SamplingPlan is versioned;
- deterministic sampler exists;
- physics-specific case constructor exists;
- canonical case identity is stable;
- TRAIN/EVAL/STRESS isolation is tested;
- representation adapters preserve the same case;
- failures/censoring are typed and retained;
- distribution-conformance data exist;
- primary reference and witness are independently pinned;
- generator-to-reference evidence exists case by case;
- evidence artifacts are machine-readable and content-addressed.

## Scientifically ready for LIVE consideration

- target population is scientifically justified;
- primary reference has been verified to the required depth;
- witness disagreement is resolved or bounded;
- production generator/reference error is bounded relative to intended candidate resolution;
- no systematic hard-stratum censoring exists;
- measurement floors are derived from evidence;
- generator-oracle adversarial test does not expose self-referential grading;
- finite exam resolution is quantified;
- all limitations are explicit;
- no claim is wider or sharper than the evidence;
- the incentive mechanism cannot create a winner where the scientific evidence says `INDETERMINATE`.

This means **ready for human scientific review**, not automatically LIVE.

---

# 17. Final principle

The question Carbon must be able to answer is not simply:

> “Can we generate PDE data?”

It is:

> **Can we show exactly how each physical case is constructed, independently establish the best available answer for that case, quantify the uncertainty in that process, and prove that the resulting exam is precise enough to justify the economic distinction the incentive mechanism is about to make?**

If yes, the Challenge can be considered for LIVE qualification.

If no, Carbon should narrow the task, improve the reference/generator stack, increase evidence, or refuse to create the economic event.

> **The scientific process creates the entitlement. The incentive mechanism only acts on evidence the scientific process can actually defend.**