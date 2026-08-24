# Generator Creation — Reference-Evidence and Implementation Architecture

**Carbon Subnet**  
**Version:** 3.0  
**Status:** OWNER-RECOMMENDED generator/reference creation and implementation architecture; Challenge-specific scientific acceptance remains evidence- and reviewer-owned.  
**Purpose:** Define how Carbon creates a Challenge generator, why the implementation is separated into distinct authorities, the software contracts required to build it safely, and the hard evidence package required to defend the reference used to evaluate it.  
**Related:** [`Generator_Validation.md`](./Generator_Validation.md), [`Challenge_Instance_Distribution.md`](./Challenge_Instance_Distribution.md), [`Evidence_and_Envelope_Standards.md`](./Evidence_and_Envelope_Standards.md), [`Data_Management.md`](./Data_Management.md), [`Scoring.md`](./Scoring.md), [`Physical_System_Representation.md`](./Physical_System_Representation.md), [`Build_Out.md`](./Build_Out.md), `SPEC.md`.

---

# 0. Executive rule

Carbon does **not** claim that a Validation Dossier creates absolute physical truth.

Carbon's defensible claim is narrower:

> **For an exact registered physical task and population, Carbon may use a reference process only after the evidence shows that its uncertainty, disagreement, applicability, and failure regions are sufficiently characterized to support the scientific comparison the Challenge intends to make.**

The generator project therefore has four distinct outputs:

```text
A. SCIENTIFIC TASK DEFINITION
   what population and physical mapping the Challenge claims

B. EXECUTABLE CHALLENGE GENERATOR
   fresh seeded canonical cases from the registered population/SamplingPlan

C. REFERENCE-EVIDENCE PACKAGE
   hard data showing why the reference path is adequate for those cases

D. IMPLEMENTATION-EVIDENCE PACKAGE
   tests proving the software realizes the registered task without silently changing it
```

The generator is not truth by definition. A solver is not truth by brand name. Agreement between a candidate and the generator is not sufficient evidence of physical correctness.

> **Narrowing the physical job makes a defensible reference claim possible; the evidence package determines whether that claim is actually earned.**

If the reference evidence cannot support the desired envelope or resolution, Carbon must **shrink the envelope, coarsen the scientific claim, mark the comparison indeterminate, or block LIVE**.

---

# 1. Why the build is intentionally separated

A single `generate(seed)` function would be simpler to code, but scientifically dangerous because it would silently collapse several different authorities:

```text
what physics is claimed
what population is claimed
how finite evidence is sampled
how one physical case is represented
how truth/reference is produced
how measurements are computed
how evidence becomes score
```

Carbon separates these because each can fail independently.

Examples:

- the PDE can be correct while the sampled population is wrong;
- the population can be correct while the finite exam under-samples a critical stratum;
- the sampled case can be correct while a tensor adapter changes a boundary condition;
- the generator can be perfectly deterministic while the reference is numerically biased;
- the reference can be credible while the measurement is ill-defined;
- every component can work while the finite evidence is too noisy to resolve a winner.

Therefore the implementation follows the same authority separation as the scientific architecture:

```text
PhysicalSystemSpec / CandidateOutputContract
        ↓ defines meaning
InstanceDistributionContract P(x)
        ↓ defines population
SamplingPlan Q(x)
        ↓ defines finite evidence allocation
ChallengeInstanceGenerator
        ↓ realizes canonical physical cases
CanonicalChallengeCase
        ↓ representation-neutral handoff
ReferencePolicy / ReferenceRunner
        ↓ produces qualified comparison values
MeasurementContracts
        ↓ produce qualified evidence
Validation Dossier
        ↓ qualifies the exam
Score Pack
        ↓ governs evidence use
ScoreEngine
```

This is not abstraction for abstraction's sake. It is how Carbon makes it possible to ask **which layer was wrong** when something fails.

---

# 2. Core implementation principles

## 2.1 The scientific task owns the population

The executable sampler does not define scientific meaning merely because it exists.

```text
InstanceDistributionContract
        !=
Generator implementation
```

The contract says what should be sampled. The generator is tested against it.

## 2.2 Sampling and truth are separate

The generator may construct a physical case without itself deciding the authoritative answer.

```text
case construction
        !=
reference realization
```

This prevents generator bias from becoming truth by construction.

## 2.3 Canonical cases precede model-specific tensors

The generator produces a representation-neutral `CanonicalChallengeCase`. FNO/JAX/mesh/graph/ROM adapters materialize that case later.

This is required for eventual model-family neutrality and to prevent the first model family from defining the scientific task.

## 2.4 Train, eval, and stress are separate roles

Role separation is structural and seed-domain-owned. The generator consumes an already authorized role/context; it does not invent or downgrade role semantics.

## 2.5 Failures are typed and visible

Generator failure, reference failure, measurement non-applicability, infrastructure failure, and invalid scientific case are different states. None may be silently dropped.

## 2.6 No module certifies itself

The generator does not declare its own conformance. The reference does not declare itself authoritative. The measurement does not decide its own score role. Qualification happens through external evidence and review.

---

# 3. Recommended software architecture

The first production-capable generator implementation should converge toward this package boundary:

```text
carbon/generators/
    __init__.py
    model.py
    contracts.py
    sampling.py
    service.py
    evidence.py
    conformance.py
    failures.py
    burgers/
        __init__.py
        generator.py
        population.py
        canonical_case.py
        reference_cole_hopf.py
        reference_witness.py
        measurements.py
        evidence_campaign.py
```

This is a recommended ownership map, not a requirement to create empty modules before they are needed. Build the smallest coherent vertical slice and preserve these boundaries conceptually.

## 3.1 `model.py` — immutable shared values

Owns closed, immutable values such as:

- `GeneratorId` / version / digest references;
- `DistributionId`;
- `SamplingPlanId`;
- `GeneratorRole` closed enum (`TRAIN`, `EVAL`, `STRESS`, plus separately typed future roles if required);
- case identity metadata;
- generator status/failure categories;
- safe provenance values.

**Why:** identity and status semantics should not be recreated differently in each PDE generator.

## 3.2 `contracts.py` — interfaces, not scientific decisions

Defines structural protocols such as:

```text
ChallengeInstanceGenerator.generate(...) -> CanonicalChallengeCase
ReferenceRunner.solve(case, ...) -> ReferenceRealization
DistributionConformanceRunner.run(...) -> ConformanceReport
ReferenceEvidenceRunner.run(...) -> ReferenceEvidenceBundle
```

**Why:** Carbon standardizes what must be observable and testable while allowing Burgers, CFD, experiments, geometry generation, or customer-hosted truth to use different implementations.

## 3.3 `sampling.py` — realization of the registered SamplingPlan

Owns finite case-selection logic from the already registered distribution/SamplingPlan.

It may implement:

- iid sampling;
- stratified sampling;
- importance/proposal sampling;
- tail allocation;
- replication;
- deterministic case ordering;
- duplicate policy.

It does **not** own:

- the scientific population definition;
- Score Pack weights;
- production seed derivation;
- reference labels.

**Why:** separating `P(x)` from `Q(x)` allows Carbon to oversample difficult regimes without falsely claiming they are naturally common.

## 3.4 `service.py` — trusted composition boundary

Composes exact version-pinned contracts, seed/context authority, sampler, generator implementation, and evidence hooks.

Its job is to reject identity mismatches before a case is produced.

It should verify, as applicable:

```text
challenge identity
PhysicalSystemSpec identity
DistributionContract identity
SamplingPlan identity
generator version/digest
role/context compatibility
requested case ordinal / draw identity
```

**Why:** scientific objects must be bound to the exact implementation being executed. A correct generator with the wrong distribution version is still the wrong exam.

## 3.5 `evidence.py` — machine-readable evidence artifacts

Owns data structures for audit output, never the scientific approval itself.

Examples:

```text
GeneratorCaseEvidence
ReferenceCaseEvidence
ReferenceDisagreementRecord
GeneratorReferenceComparison
MeasurementFloorRecord
AuditRunManifest
```

**Why:** a Validation Dossier must be reproducible from retained case-level evidence rather than screenshots or prose summaries.

## 3.6 `conformance.py` — generator implementation audit

Runs the generator repeatedly against the registered distribution and SamplingPlan and computes:

- support compliance;
- marginal/joint/conditional conformance;
- stratum frequencies;
- duplicate/near-duplicate rates;
- deterministic replay;
- exclusion compliance;
- realized-vs-intended population after failures/censoring;
- role isolation tests.

It does not call candidate models or produce a candidate score.

**Why:** numerical correctness of labels cannot detect a population-sampling bug.

## 3.7 PDE-specific modules

A PDE-specific package owns only the scientific implementation that truly differs by Challenge family.

For Burgers:

- construction of periodic smooth initial conditions;
- canonical Burgers case representation;
- fixed-viscosity semantics;
- Cole–Hopf implementation;
- independent numerical witness wrapper;
- Burgers-specific physical diagnostic implementations;
- Burgers evidence campaign configuration.

**Why:** common security/identity/evidence plumbing should not be copied into each PDE, while physics-specific logic should not be hidden inside generic infrastructure.

---

# 4. Canonical interfaces

The exact Python signatures may evolve during implementation review, but the semantic contracts should remain.

## 4.1 Generator request

Conceptually:

```text
GeneratorRequest {
  challenge_key
  distribution_pin
  sampling_plan_pin
  generator_pin
  authorized_role_context
  sample_index / draw_identity
}
```

The request does not contain arbitrary caller-selected physical ranges that can override the registered population for official eval/stress.

## 4.2 Generator result

```text
GeneratorResult =
    GeneratedCase(CanonicalChallengeCase)
  | GeneratorScientificInvalidCase(...)
  | GeneratorConstructionFailure(...)
  | GeneratorInfrastructureFailure(...)
```

A hard physical case is not silently retried until an easy one appears.

## 4.3 Canonical challenge case

At minimum, conceptually:

```text
CanonicalChallengeCase {
  identity / provenance
  physical_system_ref
  physical inputs
  parameters
  ICs / BCs
  forcing if any
  geometry/topology if any
  requested output/query semantics
  stratum metadata safe for internal use
  representation requirements
  reference request metadata
  measurement applicability metadata
}
```

It should contain the scientific case, not an FNO tensor or a solver-specific mesh object as the primary identity.

## 4.4 Reference result

```text
ReferenceRealization {
  case_identity
  reference_policy_pin
  implementation/environment identity
  status
  output_artifact_ref
  coordinates/query representation
  numerical/experimental diagnostics
  uncertainty/floor metadata
}
```

Reference failures do not become candidate failures.

---

# 5. Dependency direction

The generator architecture should preserve one-way ownership:

```text
scientific contracts
      ↓
sampling + case construction
      ↓
canonical case
      ↓
reference / representation / measurement consumers
```

Forbidden dependency patterns include:

- generator importing ScoreEngine to decide what cases matter;
- generator reading leaderboard or frontier state;
- reference implementation using candidate predictions to decide solver tolerance;
- sampler adapting official hidden distribution after seeing miner failures without a prospectively versioned protocol;
- Score Pack rewriting generator population semantics;
- model-specific adapter mutating canonical case identity.

**Why:** these dependencies would allow downstream economic or candidate information to influence the scientific exam definition.

---

# 6. How the generator actually builds a case

A single official case should be produced in a traceable sequence:

```text
1. RECEIVE exact authorized GeneratorRequest
2. VERIFY all pins and role/context compatibility
3. DERIVE/RECEIVE role-separated random material through A4-owned interfaces
4. SELECT stratum according to SamplingPlan Q(x)
5. DRAW latent/random variables from registered population conditionals
6. APPLY physical constraints and exclusions deterministically
7. CONSTRUCT canonical IC/BC/parameter/geometry values
8. VALIDATE structural physical-case invariants
9. ASSIGN immutable case identity/provenance
10. RETURN CanonicalChallengeCase
11. RECORD success/failure/censoring evidence
```

The generator should not call the candidate, ScoreEngine, frontier logic, treasury, or public disclosure path.

---

# 7. Why validation occurs at multiple layers

The implementation should support at least four independent test layers.

## 7.1 Unit correctness

Does each transformation do what its code contract says?

Examples:

- a bounded amplitude draw remains inside support;
- periodic IC construction is actually periodic;
- exclusions reject the intended forbidden cases;
- the same authorized seed/context reproduces the same case.

## 7.2 Property/invariant testing

Do broad classes of generated cases satisfy structural truths that should always hold?

Examples:

- finite values;
- dimensional shapes;
- valid parameter signs;
- periodic endpoint consistency;
- canonical serialization stability;
- no role-crossing.

## 7.3 Distribution conformance

Does a large generated campaign statistically match the registered `P/Q` design?

A unit test cannot prove this. It requires empirical conformance evidence.

## 7.4 Reference adequacy

Are the comparison values good enough to judge candidates at the intended resolution?

This is separate again and feeds the Validation Dossier.

> **Passing software tests does not scientifically qualify the generator; scientific qualification also does not excuse failing software tests.**

---

# 8. Test architecture required before LIVE

## 8.1 Determinism and identity

Test:

- same exact request → same canonical case;
- any material identity/version change → different binding or explicit rejection;
- no ambient clock, process-global RNG, environment variable, filesystem ordering, or Python `hash()` changes scientific draws;
- canonical case serialization is deterministic where used for identity.

## 8.2 Role isolation

Test all illegal crossings:

```text
TRAIN context -> EVAL request   reject
TRAIN context -> STRESS request reject
MOCK context  -> official role reject
fixture context -> production role reject
```

No generic `mode="official"` string should be trusted as authority.

## 8.3 Boundary and exclusion testing

For every registered support/exclusion:

- values just inside boundary are representable;
- values outside are rejected/not drawn;
- edge cases do not overflow or produce malformed physical cases;
- exclusion logic is versioned and tested.

## 8.4 Distribution golden tests

Use deterministic golden vectors for selected seeds to detect accidental algorithm changes.

These prove implementation stability, **not** distribution adequacy by themselves.

## 8.5 Distribution statistical tests

Run an audit campaign large enough to assess:

- marginals;
- joint dependencies;
- conditional distributions;
- stratum frequencies;
- support coverage;
- duplicate rate;
- effective sample size where relevant;
- realized distribution after failures.

Tests should compare against prospectively chosen acceptance bands appropriate to the sampling design. Do not blindly rely on a single generic goodness-of-fit p-value.

## 8.6 Censoring tests

Intentionally inject/locate generator and reference failures and verify that:

- each failure is recorded;
- the case is not silently replaced in a way that changes the exam population;
- realized population diagnostics expose any distortion;
- failure policy is deterministic and prospectively specified.

## 8.7 Mutation/aliasing tests

Ensure callers cannot mutate a generated case after identity/evidence binding and thereby create a different physical problem under the same ID.

## 8.8 Representation parity tests

For every supported model-family adapter, round-trip or cross-check that materialization preserves:

- parameters;
- ICs/BCs;
- coordinates/frames;
- geometry identity;
- query points/times;
- units/scaling.

---

# 9. Hard data required for reference claims

Every Challenge-specific reference-evidence package must retain raw or reconstructible case-level data, not only narrative conclusions or plots.

Required provenance includes:

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
compiler/runtime/library versions where material
hardware profile where material
precision policy
reference configuration
measurement implementation identities
case IDs / audit-seed commitments
creation timestamp / run manifest
```

For each audit case retain:

- canonical physical input;
- parameters, ICs, BCs, forcing, geometry/topology where relevant;
- requested outputs/query locations/times;
- stratum/category;
- reference status;
- reference output artifact or values;
- numerical/experimental diagnostics;
- uncertainty estimate;
- generator-vs-reference and reference-vs-witness discrepancies;
- measurement values;
- failure/censoring states.

Aggregate plots must be reproducible from retained case-level evidence.

---

# 10. Reference classes and required evidence

## 10.1 Analytic / semi-analytic reference

Required where applicable:

1. equation recovery / defect checks;
2. IC/BC recovery;
3. known invariant or monotonicity checks;
4. limiting/simple cases;
5. independent implementation or numerical witness;
6. precision/quadrature/transform/refinement sensitivity;
7. failure/ill-conditioning map.

Mathematical exactness of a derivation is distinct from numerical error in Carbon's implementation of that derivation.

## 10.2 Qualified numerical reference

Required:

1. independently checkable verification cases;
2. spatial/time refinement study;
3. observed convergence data;
4. solver-tolerance sensitivity;
5. scheme/configuration sensitivity where material;
6. conservation/balance evidence;
7. conditioning/failure map;
8. independent witness or stronger evidence where warranted;
9. documented reference uncertainty/floor.

## 10.3 Experimental / partner / telemetry reference

Retain as applicable:

- instrument calibration/identity;
- measurement uncertainty;
- resolution/sampling frequency;
- preprocessing/filtering;
- synchronization;
- conditions/environment;
- missingness/censoring;
- repeats;
- drift/recalibration;
- chain of custody;
- transformation to Challenge observables;
- systematic-bias information;
- applicability limits.

Partner goldens are evidence, not unquestioned truth.

---

# 11. Reference disagreement and scientific resolution

Reference disagreement is first-class evidence.

Permitted statuses include:

```text
AGREE_WITHIN_QUALIFIED_UNCERTAINTY
PRIMARY_SUPPORTED_BY_WITNESS
REFERENCE_UNCERTAIN
REFERENCE_DISAGREEMENT
REFERENCE_NUMERICAL_FAILURE
REFERENCE_FAILED_INFRA
REFERENCE_NOT_APPLICABLE
```

If credible references disagree beyond qualified uncertainty, Carbon investigates, narrows the envelope, increases uncertainty, weakens the claim, or blocks LIVE. It does not average incompatible references for convenience.

Reference uncertainty constrains scientific resolution:

```text
reference uncertainty
+ measurement uncertainty
+ reconstruction variance
+ evaluation-sampling variance
        ↓
scientific resolution / contested band
```

If candidate differences are smaller than that resolution, Carbon has no authority to claim scientific superiority.

---

# 12. Generator conformance and reference adequacy are separate campaigns

Run two campaigns:

```text
CAMPAIGN G — GENERATOR CONFORMANCE
Does the executable generator implement P/Q/constraints/strata correctly?

CAMPAIGN R — REFERENCE ADEQUACY
Are the authoritative comparison values reliable enough for the claim?
```

Campaign G retains:

- marginal/joint/conditional conformance;
- support/exclusion violations;
- range coverage;
- stratum/tail frequency;
- duplicate rates;
- invalid/failure rates;
- intended-vs-realized distribution after censoring;
- deterministic replay;
- role-separation evidence.

Campaign R retains the reference evidence in §§9–11 over a prospectively defined audit set covering interior, boundaries, hard strata, and known numerical-risk regions.

---

# 13. ReferenceAuditPlan

Before evidence generation, register:

```text
audit objective
target population / strata references
case-selection policy
interior allocation
boundary allocation
stress/risk allocation
replication/refinement plan
required reference paths
measurements recorded
uncertainty objective
failure/censoring policy
stopping/extension rule
```

There is no universal correct audit sample count.

> **Increase audit depth until the reference/measurement uncertainty and observed disagreement are stable enough to support the intended scientific resolution with margin.**

---

# 14. Burgers v1 implementation and evidence blueprint

For the recommended first authoritative Challenge:

```text
u_t + u u_x = ν u_xx
periodic 1D
ν = 5×10⁻³ fixed
smooth periodic registered IC population
input: u0
output: u(T) / registered trajectory queries
```

## 14.1 Burgers generator implementation

Recommended vertical slice:

```text
burgers/population.py
  deterministic construction of registered smooth periodic IC latent variables

burgers/generator.py
  latent variables -> canonical u0 / parameters / query definition

burgers/canonical_case.py
  immutable Burgers physical-case representation

burgers/reference_cole_hopf.py
  primary periodic Cole–Hopf realization

burgers/reference_witness.py
  independently implemented conservative high-resolution witness

burgers/measurements.py
  qualified measurement implementations only

burgers/evidence_campaign.py
  Campaign G + Campaign R orchestration for dossier evidence
```

The fixed viscosity is not randomly drawn in v1; it is challenge identity/configuration. Variable viscosity is a future Challenge only when `ν` is an explicit candidate input.

## 14.2 IC construction rationale

Use a registered smooth periodic family because it gives Carbon controlled spectral complexity and steep-gradient formation while avoiding discontinuous initial data and inviscid-shock ambiguity in the first trust proof.

The IC construction must expose enough latent metadata internally to audit amplitude/spectral complexity/stratum realization, while hidden official draw identities remain protected.

## 14.3 Cole–Hopf evidence

Retain:

- exact code/environment identity;
- IC recovery near `t=0`;
- periodicity error;
- mean conservation;
- energy evolution consistent with unforced viscous dissipation;
- maximum-principle consistency where applicable;
- equation-defect diagnostics only through a separately qualified differentiation method;
- transform/quadrature/truncation/resolution sensitivity;
- precision sensitivity if material;
- failure/ill-conditioning map;
- content-addressed outputs for audit cases.

## 14.4 Independent witness evidence

For the same audit cases retain:

- solver/version/environment;
- discretization/scheme;
- grid/time-step refinement sequence;
- solver tolerances;
- outputs at each refinement;
- convergence data for the quantities Carbon measures;
- conservation/balance diagnostics;
- failures;
- final witness-vs-Cole–Hopf discrepancy by stratum.

## 14.5 Generator-under-test evidence

Retain:

- canonical case identity;
- generator realization;
- generator-vs-Cole–Hopf discrepancy;
- generator-vs-witness discrepancy;
- error by time/query;
- physical diagnostics;
- stratum;
- failure/censoring state;
- concentration of error near boundaries/risk regions.

## 14.6 Burgers stop-ships

Do not go LIVE if:

- generator/reference error is comparable to candidate differences Carbon intends to reward;
- a generator-oracle can outrank a qualified physical-reference oracle because of generator bias;
- Cole–Hopf and witness disagree materially without bounded explanation;
- hard strata coincide systematically with reference failure/censoring;
- thresholds sit below qualified numerical/reference floors;
- the old final-state spatial-balance proxy is represented as a full PDE residual despite missing `u_t`;
- reconstruction/evaluation noise materially flips decisions without an indeterminate policy.

---

# 15. Measurement qualification interface

Each score-eligible measurement should expose a versioned implementation and an evidence record containing:

```text
measurement_id / version
scientific property
required observables
reference path
numerical operator/discretization
normalization/aggregation
reference/numerical floor
applicability rule
known failure modes
uncertainty
role: mandatory / soft / diagnostic
threshold/scale derivation method
```

For Burgers v1 the current recommended measurement set includes:

- finite output;
- periodic mean/mass conservation;
- energy non-increase;
- maximum-principle consistency where applicable;
- field error against Cole–Hopf;
- stress-stratum field error.

The ScoreEngine consumes already-authorized scalar evidence. It does not discover scientific measurements or thresholds.

---

# 16. Evidence artifacts required by the Validation Dossier

At minimum retain machine-readable forms of:

```text
R0 Reference identity
R1 Audit coverage
R2 Analytic/reference implementation checks
R3 Numerical convergence / witness data
R4 Reference disagreement
R5 Generator-vs-reference
R6 Measurement floors
R7 Decision-resolution study
R8 Limitations / unresolved regions
R9 Generator conformance statistics
R10 Censoring / realized-population report
R11 Representation parity report
R12 Software implementation test manifest
```

`R12` should identify exact test suites, implementation commit/tree, environment, and pass/fail outcome. Scientific reviewers should be able to distinguish **software correctness evidence** from **scientific qualification evidence**.

---

# 17. Build sequence and why this order matters

```text
1. DEFINE PHYSICAL JOB
   WHY: without fixed semantics there is no stable claim to validate.

2. DEFINE TARGET POPULATION P(x)
   WHY: an envelope alone does not define what an average or failure rate means.

3. DEFINE SAMPLING PLAN Q(x)
   WHY: finite evidence needs deliberate allocation and sufficient hard-regime coverage.

4. WRITE REFERENCE CLAIM / POLICY
   WHY: evidence must test a prospective claim, not justify a solver after the fact.

5. DEFINE CANONICAL CASE CONTRACT
   WHY: prevents FNO/JAX/mesh representation from becoming the scientific identity.

6. IMPLEMENT SAMPLER + GENERATOR
   WHY: turns the registered task into reproducible cases without owning truth.

7. IMPLEMENT PRIMARY REFERENCE
   WHY: establishes candidate-comparison values independently of candidate behavior.

8. IMPLEMENT INDEPENDENT WITNESS WHERE REQUIRED
   WHY: catches implementation/numerical bias in the primary reference.

9. RUN SOFTWARE / IDENTITY / ROLE TESTS
   WHY: scientific evidence is meaningless if the implementation can silently change cases.

10. RUN CAMPAIGN G — CONFORMANCE
    WHY: proves the executable generator really realizes P/Q.

11. RUN CAMPAIGN R — REFERENCE ADEQUACY
    WHY: establishes uncertainty, disagreement, and failure regions.

12. QUALIFY MEASUREMENTS
    WHY: a trustworthy reference does not automatically make every metric meaningful.

13. RUN SCIENTIFIC-RESOLUTION STUDY
    WHY: economic ranking cannot be finer than the exam can actually resolve.

14. ASSEMBLE VALIDATION DOSSIER
    WHY: independent review needs one bound evidence chain.

15. BIND SCORE PACK
    WHY: only qualified evidence should become incentive-bearing.

16. LAUNCH BAR + HUMAN SIGN-OFF

17. REGISTRY LIVE
```

The order deliberately prevents candidate results, scoring economics, or implementation convenience from deciding what the scientific task means.

---

# 18. Implementation Definition of Done

The generator implementation is ready for dossier evidence generation only when:

- [ ] exact scientific contract and population pins are consumed, not recreated internally;
- [ ] role/context authority comes from the seeding layer and cannot be caller-forged by a string flag;
- [ ] generated outputs are `CanonicalChallengeCase` values rather than model-specific tensors as primary identity;
- [ ] deterministic replay is proven for exact requests;
- [ ] support/exclusion and boundary behavior is tested;
- [ ] no ambient RNG/time/filesystem/environment ordering affects scientific draws;
- [ ] generator failures are typed and retained;
- [ ] no silent replacement/censoring reshapes the exam population;
- [ ] distribution conformance campaign code exists and produces machine-readable evidence;
- [ ] reference runners are independently versioned from generator implementation;
- [ ] reference failures remain separate from candidate/generator failure;
- [ ] case/reference/evidence artifacts are content-addressed or otherwise exactly bound;
- [ ] representation parity can be tested downstream;
- [ ] no dependency on ScoreEngine, leaderboard, frontier, treasury, or customer pricing exists in scientific generation logic;
- [ ] unit/property/integration/security tests pass;
- [ ] exact implementation/test environment is recorded.

Passing this checklist means **implementation-ready for scientific qualification**, not LIVE.

---

# 19. Scientific Definition of Done

A generator/reference package is ready for Validation Dossier review only when:

- [ ] physical task, output contract, envelope, and exclusions are explicit;
- [ ] target population `P(x)` is explicit and justified;
- [ ] SamplingPlan/audit plan is prospective;
- [ ] generator conformance hard data exist;
- [ ] primary reference policy is written and pinned;
- [ ] analytic/numerical/experimental verification data exist as applicable;
- [ ] independent witness exists where the claim requires it;
- [ ] case-level reference outputs and comparison data are retained;
- [ ] uncertainty/floors are reported by measurement and stratum;
- [ ] disagreement/failure/censoring is visible;
- [ ] measurement qualification tables exist;
- [ ] scientific-resolution/rank-stability study supports the intended comparison;
- [ ] limitations and blocked regions are explicit;
- [ ] evidence artifacts are hashed/versioned;
- [ ] no score threshold is sharper than qualified reference/measurement resolution;
- [ ] no claim is wider or sharper than the evidence;
- [ ] dossier sections can be completed without using leaderboard outcomes to retroactively redesign the exam.

---

# 20. Review questions an external technical reviewer should be able to answer

After reading the implementation and evidence, a reviewer should be able to answer:

1. What exact physical population does this Challenge claim?
2. Where is that population defined independently of code?
3. How does the finite SamplingPlan differ from population prevalence?
4. Can I reproduce one case from its exact identity and authorized seed context?
5. Can the generator silently change the distribution?
6. Can hard cases disappear through retry/censoring?
7. Is the canonical case independent of model architecture?
8. What is the primary reference and why is it credible?
9. What independent evidence checks the primary reference?
10. Where does the reference fail or become uncertain?
11. How large are generator-reference discrepancies by regime?
12. What numerical floor applies to each score-bearing measurement?
13. What candidate difference can the exam actually resolve?
14. Could generator bias make a less-physical candidate win?
15. What exact code/config/environment produced the evidence?
16. What change would force a new generator/dossier version?

If these questions cannot be answered from retained artifacts, the generator is not ready to carry authoritative economic consequences.

---

# 21. Final principles

> **The scientific task defines the population; the generator implements it.**

> **The generator constructs cases; it does not become truth by construction.**

> **Canonical physical cases come before model-family representations.**

> **Software correctness and scientific qualification are separate obligations.**

> **Reference uncertainty sets a floor on what Carbon may claim to distinguish.**

> **The exam must earn the right to judge the model.**
