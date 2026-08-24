# Generator Creation — Human Guide, Reference Verification, and Implementation Architecture

**Carbon Subnet**  
**Version:** 4.0  
**Status:** OWNER-RECOMMENDED architecture; Challenge-specific scientific acceptance remains evidence- and reviewer-owned.  
**Purpose:** Explain, in plain language and implementation detail, how Carbon creates a Challenge generator, how that generator is checked against a qualified reference, what hard data must be retained, and why the software is separated into distinct scientific authorities.  
**Related:** [`Generator_Validation.md`](./Generator_Validation.md), [`Challenge_Instance_Distribution.md`](./Challenge_Instance_Distribution.md), [`Evidence_and_Envelope_Standards.md`](./Evidence_and_Envelope_Standards.md), [`Data_Management.md`](./Data_Management.md), [`Scoring.md`](./Scoring.md), [`Physical_System_Representation.md`](./Physical_System_Representation.md), [`Build_Out.md`](./Build_Out.md), `SPEC.md`.

---

# 0. Read this first

Carbon does **not** claim that a Validation Dossier creates absolute physical truth.

The claim is narrower and more defensible:

> **For an exact registered physical task and population, Carbon may use a reference process only after evidence shows that its uncertainty, disagreement, applicability, and failure regions are sufficiently characterized to support the comparison the Challenge intends to make.**

The generator project therefore has four outputs:

```text
1. SCIENTIFIC TASK
   What physical problem and population are we claiming to test?

2. EXECUTABLE GENERATOR
   Can we reproducibly create fresh cases from that registered population?

3. REFERENCE-EVIDENCE PACKAGE
   Why should we trust the comparison values for those cases, and to what precision?

4. IMPLEMENTATION-EVIDENCE PACKAGE
   Does the software actually implement the registered task without silently changing it?
```

The shortest mental model is:

```text
DEFINE THE JOB
      ↓
DEFINE THE POPULATION
      ↓
BUILD THE GENERATOR
      ↓
QUALIFY THE REFERENCE
      ↓
VERIFY GENERATOR AGAINST REFERENCE
      ↓
QUALIFY THE MEASUREMENTS
      ↓
PROVE THE EXAM CAN RESOLVE REAL DIFFERENCES
      ↓
VALIDATION DOSSIER
      ↓
LIVE
```

The key rule is:

> **The generator is not truth by definition. The reference is not truth by brand name. The exam must earn the right to judge candidates.**

---

# 1. What the generator actually does

A Challenge generator creates physical cases. It does **not** decide what the correct answer is.

Conceptually:

```text
(seed + registered role + registered distribution + SamplingPlan)
        ↓
ChallengeInstanceGenerator
        ↓
CanonicalChallengeCase
```

For Burgers, a canonical case might contain:

- the periodic spatial domain;
- fixed viscosity;
- the sampled initial condition;
- requested prediction time;
- exact case identity and provenance;
- the stratum or sampling role used internally.

The correct solution for that case is produced separately by a `ReferenceRunner`.

That separation is deliberate:

```text
CASE CONSTRUCTION
      !=
REFERENCE / ANSWER CONSTRUCTION
```

If one implementation did both, a bug or numerical bias in the generator could silently become the answer key.

---

# 2. Why the build is separated into multiple authorities

A single `generate(seed)` function would be easier to code but scientifically dangerous. It would collapse several questions that can fail independently:

```text
What physics are we claiming?
What population are we claiming?
How are finite cases sampled?
How is one physical case represented?
How is the reference answer produced?
How are physical properties measured?
How does evidence become score?
```

Examples of independent failure:

- the PDE can be correct while the sampled population is wrong;
- the population can be correct while the finite exam misses an important stratum;
- the case can be correct while a tensor adapter changes a boundary condition;
- the generator can be deterministic while the reference is biased;
- the reference can be credible while the measurement is poorly defined;
- all components can work while the finite exam is too noisy to distinguish two candidates.

So Carbon preserves this authority chain:

```text
PhysicalSystemSpec + CandidateOutputContract
        ↓
InstanceDistributionContract P(x)
        ↓
SamplingPlan Q(x)
        ↓
ChallengeInstanceGenerator
        ↓
CanonicalChallengeCase
        ↓
ReferencePolicy / ReferenceRunner
        ↓
MeasurementContracts
        ↓
Validation Dossier
        ↓
Score Pack
        ↓
ScoreEngine
```

This is not abstraction for abstraction's sake. It lets Carbon identify **which layer failed** and prevents downstream economics from defining upstream science.

---

# 3. Generator-to-Reference Verification Procedure

This is the explicit procedure for answering:

> **How do we verify that the generator is accurate enough relative to the strongest reference evidence available?**

It is separate from distribution conformance. A generator must pass **both**.

## 3.1 First qualify the reference itself

Before generator error can mean anything, Carbon must establish that the reference path is credible enough for the intended decision.

For each prospectively selected audit case:

```text
CanonicalChallengeCase
        ↓
PRIMARY REFERENCE
        ↓
INDEPENDENT WITNESS where required
        ↓
REFERENCE AGREEMENT / UNCERTAINTY ANALYSIS
```

For Burgers v1 the intended hierarchy is:

```text
PRIMARY
periodic Cole–Hopf implementation
        ↓ cross-check
SECONDARY
independently implemented high-resolution conservative numerical solver
```

The witness is not automatically truth because it is a different solver. It is evidence about the primary reference and helps expose implementation, discretization, or regime-specific failure.

Before using a case as authoritative comparison evidence, record one of:

```text
AGREE_WITHIN_QUALIFIED_UNCERTAINTY
PRIMARY_SUPPORTED_BY_WITNESS
REFERENCE_UNCERTAIN
REFERENCE_DISAGREEMENT
REFERENCE_NUMERICAL_FAILURE
REFERENCE_FAILED_INFRA
REFERENCE_NOT_APPLICABLE
```

Cases with unresolved reference disagreement do not silently become candidate failures.

## 3.2 Then run the exact same case through the generator/reference path

For every audit case, bind the **same canonical physical problem** to all paths:

```text
REGISTERED AUDIT CASE
        ├──────────────→ primary reference
        ├──────────────→ independent witness
        └──────────────→ generator / production realization under test
```

The comparison is case-by-case, not merely an aggregate dashboard.

Retain:

- exact canonical case identity;
- generator identity/version/environment;
- primary reference identity/version/environment;
- witness identity/version/environment;
- generator output;
- primary reference output;
- witness output;
- coordinates/query representation;
- generator-vs-primary discrepancy;
- generator-vs-witness discrepancy;
- primary-vs-witness discrepancy;
- physical diagnostics;
- stratum/regime;
- failure/censoring status;
- uncertainty attached to the reference realization.

## 3.3 Compare the quantities Carbon will actually use

Verification must be performed on the observables and measurements that matter for the Challenge, not on a convenient unrelated norm.

For Burgers this should include, where qualified:

- field error against Cole–Hopf;
- field error against the independent witness;
- periodic mean/mass conservation;
- energy evolution / non-increase behavior;
- maximum-principle consistency where applicable;
- error as a function of time/query if multiple times are used;
- error by population stratum;
- error near the qualified envelope boundaries.

A single global mean error is insufficient because it can hide a systematic failure in the hard part of the envelope.

## 3.4 Repeat across the whole qualified envelope

The audit set is chosen **before** looking at generator performance and must cover:

```text
interior / ordinary cases
boundary-near cases
registered stress strata
known numerical-risk regions
simple / limiting cases where useful
```

Carbon should examine both the central tendency and the tails of generator-reference error.

Questions the audit must answer include:

- Does error increase near an envelope boundary?
- Are steep-gradient cases systematically worse?
- Does one stratum have materially higher generator failure?
- Does reference disagreement cluster in the same hard region?
- Are hard cases disappearing through timeout or retry?
- Are there rare but large errors hidden by a small mean?

## 3.5 Derive a generator error budget

The result of the campaign is not merely `generator_valid = true`.

Carbon should characterize a bounded error budget by relevant measurement and stratum, for example conceptually:

```text
measurement / stratum
    ↓
generator-reference discrepancy distribution
    ↓
reference uncertainty
    ↓
qualified generator contribution to exam uncertainty
```

No universal formula or tolerance is assumed. The values are derived from the evidence campaign and reviewed scientifically.

The important comparison is:

> **Is generator/reference uncertainty materially smaller than the candidate differences Carbon intends to reward?**

If not, the exam is too coarse to support that economic distinction.

## 3.6 Run the generator-oracle adversarial test

A required stop-ship thought experiment and, where feasible, executable test is:

```text
Candidate A reproduces generator bias
Candidate B follows the stronger qualified physical reference
        ↓
run both through the proposed measurement + scoring path
```

If Candidate A can outrank Candidate B because Carbon's scoring path rewards generator bias, the Challenge is not ready.

> **A generator-oracle must not outrank a qualified physical-reference oracle because the exam mistakes generator error for physics.**

This test directly guards against self-referential grading.

## 3.7 Decide the outcome explicitly

The verification campaign may end in only defensible outcomes:

```text
QUALIFIED
Generator error is bounded and small enough for the intended comparison.

QUALIFIED_WITH_LIMITATIONS
Generator is usable only inside a narrower envelope / coarser resolution.

REPAIR_REQUIRED
Implementation or numerical method must improve before qualification.

REFERENCE_BLOCKED
Reference itself is too uncertain to judge the generator.

LIVE_BLOCKED
The combined generator/reference uncertainty is too large or poorly characterized.
```

The response to weak evidence is never to quietly loosen the meaning of the claim.

---

# 4. Two different generator validation campaigns

It is essential not to collapse these.

## Campaign G — Distribution conformance

**Question:** Does the executable generator sample the physical population and finite SamplingPlan we registered?

Retain:

- marginal distributions;
- joint and conditional checks;
- support/exclusion compliance;
- stratum/tail frequencies;
- duplicate/near-duplicate rates;
- invalid-case rates;
- failure rates by stratum;
- intended-versus-realized distribution after censoring;
- deterministic replay results;
- train/eval/stress isolation results.

A generator can produce numerically accurate cases and still fail Campaign G if it samples the wrong population.

## Campaign R — Reference and generator numerical adequacy

**Question:** Are the comparison values and generator realizations accurate enough for the intended scientific decision?

This campaign contains the procedure in Section 3 and retains:

- primary-reference evidence;
- witness evidence;
- refinement/precision studies;
- reference disagreement;
- generator-vs-reference discrepancies;
- physical diagnostics;
- uncertainty/floors;
- failure maps;
- decision-resolution consequences.

A generator must pass both Campaign G and Campaign R before it can support a LIVE exam.

---

# 5. What “reference truth” means in Carbon

Use precise language.

Prefer:

- **reference**;
- **reference realization**;
- **qualified reference evidence**;
- **authoritative reference within a stated uncertainty**.

Reserve “truth” for cases where the underlying mathematics or physical evidence genuinely supports unusually strong language.

Practical classes:

### Class A — analytic / semi-analytic reference

Strongest case when assumptions and implementation are controlled. The mathematical derivation may be exact while Carbon's numerical implementation still has transform, quadrature, truncation, interpolation, or precision error.

### Class B — qualified numerical reference

A numerical solution with convergence, verification, uncertainty, applicability, and failure evidence.

### Class C — engineering evidence reference

Experimental, telemetry, partner-golden, calibrated multi-fidelity, or hybrid evidence with explicit measurement/model uncertainty.

The strength of the public claim must decrease as reference uncertainty and model-form dependence increase.

---

# 6. Hard evidence required for the reference

Every reference campaign retains raw or reconstructible evidence, not just screenshots or plots.

## 6.1 Identity and provenance

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
case IDs / audit-seed commitments
run manifest / timestamp
```

## 6.2 Case-level inputs

Retain enough to reconstruct exactly what physical problem was solved:

- parameters;
- ICs;
- BCs;
- forcing;
- geometry/topology where relevant;
- requested output/query times/locations;
- stratum/category;
- population/proposal metadata;
- reference applicability status.

## 6.3 Case-level outputs

Retain:

- field/trajectory values or content-addressed artifact;
- coordinates/query grid;
- units/scaling;
- solver status;
- convergence/termination information;
- residual/defect information where scientifically meaningful;
- invariant/balance diagnostics;
- interpolation/materialization steps;
- uncertainty estimate.

## 6.4 Reference-class-specific evidence

For analytic/semi-analytic references, include as applicable:

- governing-equation recovery;
- IC/BC recovery;
- invariants/monotonicity;
- limiting/simple cases;
- independent implementation check;
- transform/quadrature/truncation/precision sensitivity;
- failure/ill-conditioning map.

For numerical references, include as applicable:

- manufactured/analytic/benchmark verification cases;
- spatial and temporal refinement studies;
- observed convergence behavior;
- solver-tolerance sensitivity;
- scheme/configuration sensitivity where material;
- conservation/balance evidence;
- conditioning/failure map;
- independent witness;
- reference uncertainty estimate.

For experimental/telemetry references, include as applicable:

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
- transformation from raw measurement to Challenge observable;
- known systematic bias and applicability limits.

---

# 7. Reference disagreement is evidence

When credible reference paths disagree, retain the disagreement explicitly:

```text
case identity
reference A identity/config/output
reference B identity/config/output
absolute/relative discrepancy
spatial/temporal structure of discrepancy
stratum/regime
uncertainty of each path
investigation status
supported cause, if known
resolution or unresolved status
impact on claim/envelope
```

Permitted responses are to investigate, increase uncertainty, narrow the envelope, weaken the measurement claim, mark the comparison indeterminate, or block LIVE.

Forbidden: silently average incompatible references to create a convenient answer.

---

# 8. Reference uncertainty constrains scientific resolution

Carbon cannot make economic distinctions finer than its scientific evidence can resolve.

Conceptually:

```text
reference uncertainty
+ generator/reference error
+ measurement uncertainty
+ reconstruction variance
+ finite-evaluation variance
        ↓
SCIENTIFIC RESOLUTION / CONTESTED BAND
```

The exact combination is Challenge-specific and requires statistics/scientific review.

If Candidate A and Candidate B differ by less than the qualified resolution, Carbon has no authority to claim that one is scientifically superior for frontier promotion.

---

# 9. How the generator builds one case

A single official case should be created in a traceable sequence:

```text
1. Receive exact authorized GeneratorRequest
2. Verify all challenge/distribution/SamplingPlan/generator pins
3. Verify role/context compatibility
4. Receive role-separated random material through the A4-owned seed interface
5. Select the SamplingPlan stratum
6. Draw latent variables from the registered population conditionals
7. Apply physical constraints and exclusions deterministically
8. Construct canonical IC/BC/parameter/geometry values
9. Validate structural case invariants
10. Bind immutable case identity/provenance
11. Return CanonicalChallengeCase
12. Record success/failure/censoring evidence
```

The generator does not call the candidate, ScoreEngine, leaderboard, frontier logic, treasury, or commercial path.

---

# 10. Recommended software architecture

The implementation should converge toward:

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
        generator.py
        population.py
        canonical_case.py
        reference_cole_hopf.py
        reference_witness.py
        measurements.py
        evidence_campaign.py
```

This is an ownership map, not a requirement to create empty files prematurely.

### `model.py`
Owns immutable IDs, versions, roles, case metadata, and status/failure categories.

**Why:** identity semantics must not be reinvented differently by every PDE generator.

### `contracts.py`
Defines interfaces such as:

```text
ChallengeInstanceGenerator.generate(...) -> CanonicalChallengeCase
ReferenceRunner.solve(...) -> ReferenceRealization
DistributionConformanceRunner.run(...) -> ConformanceReport
ReferenceEvidenceRunner.run(...) -> ReferenceEvidenceBundle
```

**Why:** Carbon standardizes what must be observable and testable without forcing every physics family into the same numerical implementation.

### `sampling.py`
Implements the registered finite SamplingPlan `Q(x)`—iid, stratified, importance, tail allocation, replication, duplicate policy, deterministic ordering.

**Why:** `P(x)` and `Q(x)` are different scientific objects. Carbon can deliberately oversample rare hard cases without pretending they are naturally common.

### `service.py`
Verifies exact identities and composes authorized seed context, sampler, generator, and evidence hooks.

**Why:** the correct code with the wrong distribution version is still the wrong exam.

### `evidence.py`
Defines machine-readable case evidence, disagreement records, generator-reference comparisons, measurement floors, and run manifests.

**Why:** the dossier must be reconstructible from case-level data, not prose.

### `conformance.py`
Audits support, distribution, strata, duplicates, replay, exclusions, censoring, and role isolation.

**Why:** numerical agreement with a reference cannot detect a population-sampling bug.

### PDE-specific package
Owns only the scientific logic that actually differs by PDE family.

**Why:** shared security/evidence plumbing should not be copied everywhere, while physics-specific assumptions should not be hidden inside generic infrastructure.

---

# 11. Required test layers before LIVE

The implementation supports four distinct layers:

### A. Unit correctness

Examples: support bounds, periodic IC construction, exclusion logic, deterministic replay.

### B. Property / invariant tests

Examples: finite values, valid dimensions/signs, periodic endpoint consistency, serialization stability, no role crossing.

### C. Distribution conformance

Empirically verify marginals, joints, conditionals, strata, support coverage, duplicates, and realized distribution after failures.

### D. Reference adequacy + generator-to-reference verification

Run Section 3 and show the resulting uncertainty is small enough for the intended scientific decision.

> **Passing software tests does not scientifically qualify the generator. Scientific qualification also does not excuse failing software tests.**

Also require explicit tests for:

- train/eval/stress role isolation;
- identity/version mismatch rejection;
- boundary and exclusion behavior;
- censoring/failure visibility;
- mutation/aliasing after case identity binding;
- representation parity across supported model-family adapters.

---

# 12. Burgers v1 concrete verification plan

The recommended first authoritative Challenge is fixed-viscosity 1D periodic viscous Burgers:

```text
u_t + u u_x = ν u_xx
ν = 5×10⁻³
periodic 1D domain
registered smooth periodic IC population
```

Reference hierarchy:

```text
PRIMARY
periodic Cole–Hopf implementation
        ↓
SECONDARY
independently implemented high-resolution conservative solver
        ↓
GENERATOR UNDER TEST
production Challenge generator/reference realization
```

For the Cole–Hopf implementation retain:

- exact code/environment identity;
- IC recovery at `t=0` or the nearest meaningful limit;
- periodicity error;
- spatial-mean conservation;
- dissipative energy behavior;
- maximum-principle consistency where applicable;
- separately qualified equation-defect diagnostics if used;
- transform/quadrature/truncation/resolution sensitivity;
- precision sensitivity where material;
- explicit ill-conditioning/failure cases;
- content-addressed outputs for audit cases.

For the numerical witness retain:

- code/version/environment;
- numerical scheme;
- grid/time-step refinement sequence;
- solver tolerances;
- outputs at each refinement;
- observed differences/convergence;
- conservation diagnostics;
- failures/status;
- witness-vs-Cole–Hopf discrepancy by case and stratum.

For the generator-under-test retain:

- exact case identity;
- generator output;
- generator-vs-Cole–Hopf discrepancy;
- generator-vs-witness discrepancy;
- physical diagnostics;
- stratum;
- failure/censoring state;
- error concentration near boundaries/hard regimes.

Burgers v1 is STOP-SHIP if material evidence shows any of the following:

- generator/reference error is comparable to the candidate differences Carbon intends to reward;
- a generator-oracle can beat a qualified physical-reference oracle because scoring rewards generator bias;
- Cole–Hopf and the numerical witness disagree materially without bounded explanation;
- hard strata coincide with systematic reference failure/censoring;
- score thresholds sit below the qualified numerical/reference floor;
- the historical final-state spatial-balance proxy is represented as a full PDE residual despite missing `u_t`;
- reconstruction/evaluation variation flips decisions materially without an indeterminate policy.

---

# 13. Measurement qualification consumes the same hard data

Every score-eligible `MeasurementContract` should have a qualification table containing:

```text
measurement_id / version
scientific property claimed
required observables
reference path used
numerical operator/discretization
normalization/aggregation
reference/numerical floor
applicability rule
known failure modes
uncertainty summary
role: mandatory / soft / diagnostic
threshold or scale derivation method
```

A governing equation does not by itself justify a residual metric, and a conservation law does not justify a universal tolerance.

Score Pack thresholds must be traceable to these data and the scientific relevance of the property. The ScoreEngine executes the registered decision; it does not invent the scientific threshold.

---

# 14. Evidence tables required in the Validation Dossier

At minimum the dossier contains or references machine-readable forms of:

| Table | Contents |
|---|---|
| **R0 — Identity** | Exact software, environment, configuration, artifacts, hashes |
| **R1 — Audit coverage** | Cases by stratum, boundary/risk region, reference path, status |
| **R2 — Reference implementation checks** | IC/BC, invariants, precision/refinement, limiting cases |
| **R3 — Numerical convergence / witness** | Per-refinement outputs, convergence, tolerance sensitivity, failures |
| **R4 — Reference disagreement** | Primary-vs-witness discrepancy, uncertainty, disposition, envelope impact |
| **R5 — Generator-vs-reference** | Case/stratum discrepancies, failures, boundary concentration |
| **R6 — Measurement floors** | Qualified floor/uncertainty for every score-eligible measurement |
| **R7 — Decision resolution** | repeated reconstruction/evaluation, gate/rank flips, contested band |
| **R8 — Limitations** | every weakened or blocked region/quantity/measurement |

A few summary plots are not sufficient for an authoritative LIVE decision.

---

# 15. Human review questions

A skeptical reviewer should be able to answer these from the dossier and retained evidence:

1. What exact physical task does this Challenge claim?
2. What population does the exam represent?
3. How does the generator sample that population?
4. Can one case be exactly reproduced from its identity?
5. What is the primary reference and why is it credible?
6. What independently checks the primary reference?
7. Where does the reference become uncertain or fail?
8. On the same cases, how far is the generator from the reference?
9. Does that error grow in hard or boundary regimes?
10. Could generator bias make the wrong candidate win?
11. What measurement floor follows from reference/generator uncertainty?
12. What candidate difference can the exam actually resolve?
13. What happens when a case/reference fails?
14. Can difficult cases disappear through censoring or retry?
15. What exact limitation would force Carbon to shrink the envelope or block LIVE?

If those questions cannot be answered from retained data, the generator is not ready to carry economic consequences.

---

# 16. Creation sequence

```text
1. DEFINE PHYSICAL JOB
2. DEFINE TARGET POPULATION P(x)
3. DEFINE SAMPLING PLAN Q(x)
4. WRITE REFERENCE CLAIM + FAILURE POLICY
5. IMPLEMENT GENERATOR
6. IMPLEMENT PRIMARY REFERENCE
7. IMPLEMENT INDEPENDENT WITNESS WHERE REQUIRED
8. RUN DISTRIBUTION-CONFORMANCE CAMPAIGN
9. RUN REFERENCE-QUALIFICATION CAMPAIGN
10. RUN GENERATOR-TO-REFERENCE VERIFICATION
11. QUALIFY MEASUREMENTS
12. RUN SCIENTIFIC-RESOLUTION STUDY
13. ASSEMBLE VALIDATION DOSSIER + R0–R8
14. BIND SCORE PACK
15. HUMAN LAUNCH-BAR SIGN-OFF
16. REGISTRY LIVE
```

Candidate leaderboard outcomes do not participate in choosing the population, reference policy, or scientific thresholds except through a separately versioned prospective redesign.

---

# 17. Definition of Done

## Implementation-ready for scientific review

- exact challenge/distribution/SamplingPlan/generator identities are content-bound;
- deterministic replay works;
- train/eval/stress isolation is tested;
- canonical cases are representation-neutral;
- support/exclusion/boundary tests pass;
- failures/censoring are typed and retained;
- distribution conformance data exist;
- primary reference and witness are independently pinned;
- generator-to-reference evidence exists at case level;
- evidence artifacts are machine-readable and content-addressed.

## Scientifically ready for LIVE consideration

- target population is justified;
- reference uncertainty/failure regions are characterized;
- reference disagreement is resolved or bounded;
- generator error is bounded relative to intended candidate resolution;
- no systematic hard-stratum censoring exists;
- measurement floors are derived from evidence;
- generator-oracle adversarial test does not expose self-referential grading;
- finite exam resolution is quantified;
- all limitations are explicit;
- no claim is wider or sharper than the evidence;
- Validation Dossier sections can be populated without relying on leaderboard outcomes.

This means **ready for human scientific review**, not automatically LIVE.

---

# 18. Final principle

Carbon's first scientific challenge is not simply:

> “Can we generate PDE data?”

It is:

> **Can we demonstrate, with retained case-level evidence, that the generator samples the intended physical population and that its reference/measurement process is accurate, stable, applicable, and resolved enough to support the exact comparison for which Carbon intends to create economic consequences?**

Only after that question is answered should the generator participate in an authoritative exam.

> **The exam must earn the right to judge the model.**
