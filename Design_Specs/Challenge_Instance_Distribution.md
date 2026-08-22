# Carbon Challenge Instance Distribution Architecture

**Status:** DESIGN INTEGRATION DRAFT — architecture-level, pending tech/science-lead review.  
**Purpose:** Define a durable, model-family-neutral architecture for scientifically defensible Challenge population definition, finite sampling, instance generation, representation, truth realization, and provenance across Carbon's full vision.  
**Does not override:** current P0 wire contracts, `Generator_Creation.md`, `Generator_Validation.md`, `Data_Management.md`, `Scoring.md`, `Build_Out.md`, LIVE Challenge semantics, or product qualification rules until ratified into those domain-owning specifications.  
**Simulation basis:** `docs/context/DISTRIBUTION_GAUNTLET_SIMULATION.md`.

---

# 1. Design objective

Carbon's current generator architecture has the right foundational instincts: fresh seeded draws, train/eval/stress separation, declared envelopes, reference backends, versioning, hidden official realizations, and a Validation Dossier before LIVE.

The broader architecture requires one critical generalization:

> **The distribution itself is part of the scientific task.**

A generator can be deterministic, reproducible, numerically correct, and well matched to a reference solver while still sampling the wrong scientific population. Therefore the executable generator must not become the scientific definition of the task by accident.

The durable authority rule is:

> **The scientific task owns the population. The sampling plan defines how finite evidence is drawn. The generator is a qualified implementation of that plan.**

This document defines that separation.

---

# 2. Canonical scientific chain

```text
DOMAIN SCIENCE / ENGINEERING INTENT
                ↓
        PhysicalSystemSpec
                +
      CandidateOutputContract
                +
       Claim / Operating Envelope
                ↓
       TARGET POPULATION
                ↓
   InstanceDistributionContract
                ↓
          SamplingPlan
                ↓
     ChallengeInstanceGenerator
                ↓
       Generator Conformance
                ↓
       CanonicalChallengeCase
                ↓
  representation / construction adapters
                ↓
             Candidate
                ↓
      Reference / Truth Realization
                ↓
      Measurement Applicability
                ↓
      protected official evaluation
                ↓
          MeasurementContracts
                ↓
            Score Pack
                ↓
          ExperimentRecord
                ↓
   Landscape / qualification / lifecycle
```

The **Validation Dossier** is the evidence package that qualifies the relevant links in this chain before LIVE. It does not define the chain retroactively.

---

# 3. Three distributions that must not be collapsed

For any finite scientific exam, Carbon should distinguish:

```text
TARGET POPULATION      P(x)
What scientific/engineering population does the claim concern?

SAMPLING / PROPOSAL    Q(x)
How are cases actually drawn efficiently for finite evaluation?

EVALUATION WEIGHTING   w(x)
How does evidence from sampled cases contribute to the estimand / score?
```

These may be identical for a simple P0 Challenge. They are not universally identical.

Example: a rare catastrophic regime may have very low real-world prevalence under `P(x)` but be deliberately oversampled under `Q(x)` so Carbon obtains enough evidence. Raw sample frequency must not then be confused with deployment prevalence.

### Constitutional rule

> **Sampling prevalence, target-population prevalence, and score importance are separate semantics.**

The Score Pack may use stress evidence strongly, but only under explicit registered semantics.

---

# 4. `InstanceDistributionContract`

## 4.1 Purpose

`InstanceDistributionContract` is the versioned scientific definition of the population of admissible physical cases associated with a Challenge.

It is distinct from:

- `PhysicalSystemSpec` — what physical system is represented;
- claim/operating envelope — what support and exclusions are claimed;
- `SamplingPlan` — how finite evidence is drawn from the population;
- `ChallengeInstanceGenerator` — executable sampler/instance constructor;
- `CandidateOutputContract` — what a candidate must accept/return;
- `MeasurementContract` — how a property is numerically measured;
- Score Pack — how qualified measurements become score-bearing.

## 4.2 Conceptual information classes

The exact serialization remains deferred. The contract should be able to represent:

```text
InstanceDistributionContract {
  distribution_id
  version

  physical_system_spec_ref
  candidate_output_contract_ref
  claim_envelope_ref

  intended_population_semantics
  intended_estimand_context

  variable_populations[] {
    semantic_ref
    support
    population_model
    conditional_dependencies
    correlations
    constraints
    provenance
    uncertainty
  }

  geometry_population
  topology_population
  boundary_condition_population
  initial_condition_population
  coefficient / material population
  forcing / source population
  query / observation population
  temporal / episode population

  strata[]
  hierarchical_population
  exclusions
  rare_event_semantics

  role_population_refs {
    construction
    evaluation
    stress
    qualification
  }

  provenance
  evidence_maturity
  limitations
  disclosure_class
}
```

## 4.3 Envelope is not distribution

```text
support / envelope
       !=
population measure over support
       !=
stress/consequence sampling
       !=
score weighting
```

Two Challenges can use the same PDE and same envelope while representing materially different scientific tasks.

---

# 5. `SamplingPlan`

## 5.1 Why it is separate

A scientifically meaningful population does not determine how much finite evidence is needed or how that evidence should be allocated.

`SamplingPlan` is the prospective finite-evidence design.

Conceptually it should bind:

```text
SamplingPlan {
  sampling_plan_id
  version
  target_distribution_ref

  proposal_distribution / sampler policy
  sample_budget
  strata allocation
  tail / rare-event allocation
  replication policy
  query allocation
  reference-fidelity allocation

  finite-sample objectives {
    uncertainty targets
    tail-resolution targets
    minimum per-stratum evidence
    detectable-effect assumptions where appropriate
  }

  stopping / extension rules
  duplicate / near-duplicate policy
  censoring policy
  provenance
}
```

No universal power threshold is implied. Requirements must be Challenge/evidence-type specific and scientifically reviewed.

## 5.2 Statistical sufficiency

A Challenge can be correctly specified and still produce weak evidence if the sample plan is too small or badly allocated. The Validation Dossier must therefore evaluate whether the registered SamplingPlan is sufficient for the claims/estimands the Challenge intends to support.

---

# 6. `ChallengeInstanceGenerator`

## 6.1 Universal interface, Challenge-specific implementation

Carbon should **not** create one universal physics generator.

The universal abstraction is the interface and invariant set:

```text
generate(
    seed,
    role,
    distribution_contract_version,
    sampling_plan_version,
    generator_version,
) -> CanonicalChallengeCase
```

Challenge-specific implementations may use:

- analytic sampling;
- procedural PDE construction;
- CAD/geometry synthesis;
- dataset-backed sampling where justified;
- experimental campaign selection;
- stochastic-process realization;
- coupled-system assembly;
- partner-controlled generation;
- high-fidelity simulation services.

## 6.2 Required invariants

Every official generator must preserve:

1. versioned identity and content binding;
2. registered distribution + SamplingPlan binding;
3. role separation;
4. deterministic replay where the Challenge requires it;
5. support/exclusion compliance;
6. no miner control of official eval/stress realization;
7. no hidden-realization leakage;
8. reference provenance separation;
9. generator conformance qualification before LIVE;
10. no silent material population change;
11. preservation of intended strata and tail allocation;
12. explicit failure/censoring semantics.

---

# 7. Generator conformance is its own qualification problem

Reference-solver agreement does **not** prove that the generator samples the registered population.

A separate distribution-conformance audit should test, where applicable:

- marginal conformance;
- joint/dependence conformance;
- physical constraint satisfaction;
- conditional distribution conformance;
- geometry-family coverage;
- stratum frequencies;
- tail/stress frequencies;
- query distribution;
- duplicate / near-duplicate rate;
- effective sample size;
- role separation;
- sampler determinism;
- intended-vs-realized population after failures/censoring.

Example failure:

```text
contract: ν ~ log-uniform
implementation bug: ν ~ uniform
```

Every physical solve may be correct while the Challenge is still scientifically wrong.

---

# 8. `CanonicalChallengeCase`

## 8.1 Why `Case`, not permanently `Instance`

A static PDE query is one case type, but Carbon's long-term commercial scope includes rollouts, control, digital twins, agentic optimization, and adaptive experiments.

Therefore the durable concept is:

```text
CanonicalChallengeCase
    ├─ StaticInstance
    └─ SequentialEpisode / Trajectory
```

P0 may continue using simple arrays and static cases.

## 8.2 Conceptual contents

A canonical case may bind:

```text
challenge identity
role
population/distribution identity
sampling-plan identity
generator identity

physical inputs
parameters
geometry/topology
boundary conditions
initial conditions
forcing/source terms
requested outputs
query locations/times
sequence/episode semantics if applicable

reference-truth request
measurement applicability
representation requirements
provenance
```

It is not required to be a tensor, mesh, or file.

---

# 9. Query / observation population is part of the task

The same physical state can be easy or hard depending on what is queried.

The distribution architecture must be capable of representing:

- spatial query population;
- temporal query population;
- observable selection;
- resolution/fidelity request;
- sensor/observation distribution;
- episode horizon where relevant.

`CandidateOutputContract` defines what queries are admissible. `InstanceDistributionContract` / SamplingPlan define which admissible queries are actually sampled for evidence.

---

# 10. Representation and materialization

Model families may consume different encodings of one canonical physical case:

```text
CanonicalChallengeCase
    ├─> regular grid
    ├─> unstructured mesh
    ├─> graph
    ├─> point/query set
    ├─> reduced-basis snapshots
    └─> solver/configuration input
```

### Invariant

> **Representation adapters may change encoding; they must not change the sampled physical reality.**

Adapters must preserve provenance. Lossy transformations or representation-induced measurement limitations require explicit evidence and, where material, qualification.

---

# 11. Role semantics and semantic decontamination

P0 uses:

```text
train
eval
stress
```

Long-term roles are more generally:

```text
construction
evaluation
stress
qualification
```

where construction access may include training examples, basis snapshots, calibration observations, solver-query budget, experiments, symbolic equations, or no sampled data.

### Seed separation is necessary but not always sufficient

Different seeds can still create nearly identical scientific information. Some Challenges may require semantic decontamination constraints such as:

- geometry-family separation;
- specimen/entity separation;
- parameter-distance rules;
- mission/time-window separation;
- source-data separation;
- pre/post cutoff separation.

The exact rule is Challenge-dependent and belongs in the registered task/distribution design.

---

# 12. Nominal, evaluation, stress, qualification, deployment

These populations answer different questions:

```text
TARGET / WORKLOAD POPULATION
What population does the scientific or engineering claim concern?

SEARCH / EVALUATION POPULATION
What finite population best discriminates candidates under the Challenge objective?

STRESS POPULATION
What difficult / rare / consequence-heavy cases must be probed deliberately?

PRODUCT QUALIFICATION POPULATION
What job-shaped population supports a bounded commercial claim?

DEPLOYMENT POPULATION
What actually occurs after deployment?
```

They may overlap. They are never automatically equivalent.

> **Rank nominates. Evidence qualifies.**

---

# 13. Hierarchical and stratified populations

Real engineering populations are often hierarchical:

```text
fleet
  → product / geometry family
  → mission class
  → operating regime
  → condition
```

Flattened global averages can hide important subgroup failure and create Simpson-type effects.

The architecture should therefore support:

- explicit strata/hierarchies;
- minimum per-stratum evidence;
- stratum-level reporting;
- stratum-specific gates where scientifically required;
- aggregate weighting that cannot erase mandatory subgroup failure.

---

# 14. Reference / truth realization

Reference truth is separate from population definition and generator conformance.

A case may use:

- analytic truth;
- numerical reference;
- multi-code consensus;
- experiment;
- partner golden;
- hybrid reference;
- uncertainty-bearing truth.

Reference status must remain distinguishable from candidate outcome.

Conceptual statuses include:

```text
REFERENCE_AVAILABLE
REFERENCE_UNCERTAIN
REFERENCE_DISAGREEMENT
REFERENCE_NUMERICAL_FAILURE
REFERENCE_FAILED_INFRA
REFERENCE_NOT_APPLICABLE
```

A candidate must not be punished for Carbon's own failed truth path. Score-bearing eligibility must follow a registered reference-availability policy.

---

# 15. Multi-fidelity truth allocation

Industrial Challenges may allocate different reference fidelities across cases.

The architecture should separate:

```text
physical-case population
       !=
reference-fidelity allocation policy
```

Otherwise costly or difficult regions can be systematically evaluated at weaker fidelity and bias the evidence.

Reference-fidelity allocation belongs in SamplingPlan / ReferencePolicy provenance and must be qualified.

---

# 16. Distribution provenance and uncertainty

The intended population may be inferred or authored from:

- physical constraints;
- engineering requirements;
- historical telemetry;
- simulation campaigns;
- expert elicitation;
- test matrices;
- regulatory/qualification matrices;
- future-use scenarios.

These are not equivalent evidence sources.

Distribution provenance should preserve, where applicable:

```text
source type
observation period
sample size
selection mechanism
known missingness
uncertainty
maturity/confidence
assumptions/extrapolations
```

A historical workload distribution is observational evidence, not automatically the desired future evaluation population.

---

# 17. Measurement applicability is population-dependent

Some measurements apply only to subsets of the physical population.

Example: a shock-location metric is not meaningful on a case where no shock exists.

Measurement applicability must be independently determined where possible and must not be controllable by the candidate.

Aggregation should record the eligible population for each measurement rather than silently treating non-applicable cases as pass, fail, or missing.

---

# 18. Estimands must be explicit

A score component can only be scientifically interpreted if Carbon knows what it estimates.

Possible estimands include:

- expected error under target operation;
- physical-failure probability;
- tail risk;
- worst-stratum performance;
- consequence-weighted performance;
- answerability/coverage conditional on a registered population.

`InstanceDistributionContract` defines the population; `MeasurementContract` defines the measurement; the Score Pack defines the score-bearing estimand/aggregation.

---

# 19. Censoring and realized evidence population

The intended sample population may differ from the final valid-evidence population because of:

- reference solver failure;
- infrastructure failure;
- timeout;
- invalid case generation;
- measurement non-applicability;
- corrupted experiment;
- resource limits.

Carbon must preserve:

```text
intended sampled population
       !=
realized valid-evidence population
```

Censoring provenance must be recorded. Hard physical cases must not disappear silently because they are expensive or failure-prone to evaluate.

---

# 20. Construction information budgets and external pretraining

For future broad construction search, the information available to the producer is part of the intervention.

A future `ConstructionInputPolicy` should bind:

- accessible construction distributions;
- dataset / observation rights;
- high-fidelity query budget;
- fidelity levels;
- adaptivity;
- data retention;
- external/pretraining allowance;
- licensed/proprietary sources;
- resource accounting.

Fresh official seeds reduce contamination risk but do not make pretraining/data provenance irrelevant for narrow task distributions.

---

# 21. Randomness domains

Stochastic Challenges may require distinct randomness domains:

```text
instance_sampling_randomness
physical_realization_randomness
measurement_noise_randomness
reference_solver_randomness
construction_randomness
candidate_randomness
```

These should not be collapsed when independence/provenance matters. Exact seed derivation remains owned by security/data specs.

---

# 22. Multiphysics and composition

Component distributions do not automatically compose into a valid joint system population.

Coupled Challenges may require:

- joint sampling;
- conditional subsystem sampling;
- interface compatibility constraints;
- correlated uncertain inputs;
- coupled geometry/topology rules.

A future `CouplingContract` and `InstanceDistributionContract` must compose explicitly rather than assume independent subsystem draws are valid.

---

# 23. Privacy and disclosure

Scientific authority does not require public disclosure of every distribution parameter.

A private partner population may reveal proprietary operating profiles, mission mix, geometry frequency, process recipes, or failure modes.

Therefore distribution artifacts need disclosure classes. A public surface may expose identity, digest, high-level claim scope, validation status, and limitations while exact densities/conditional rules remain controlled where contractually required.

Hidden official realizations remain protected regardless of whether population semantics are public.

---

# 24. Material-change semantics

Not every generator refactor creates a new scientific population, but material population changes must be explicit.

Candidate material changes include:

- marginal density changes;
- correlation/conditional changes;
- geometry family changes;
- stratum additions/removals;
- stress prevalence changes;
- query population changes;
- exclusion changes;
- qualification-population changes.

Required path:

```text
material change
    → new distribution / SamplingPlan version
    → requalification as required
    → new registry binding
    → prospective use
```

Historical evidence is never silently reinterpreted.

---

# 25. Governance separation

The producer of a candidate must not define the official distribution that proves its own success.

Recommended authority split:

```text
DOMAIN / CHALLENGE AUTHOR
    defines intended task/population

GENERATOR IMPLEMENTER
    implements sampling/generation

SCIENCE / DOSSIER REVIEW
    qualifies task distribution, SamplingPlan, generator, truth and measurements

MINERS / AGENTS
    optimize construction methods

VALIDATORS
    execute registered sampling/evaluation

SCORE PACK
    converts qualified measurements into registered ranking semantics
```

No layer certifies itself.

---

# 26. Validation Dossier synchronization

The Validation Dossier should qualify at least the following evidence classes where applicable:

1. physical-system adequacy;
2. claim/envelope adequacy;
3. target-population adequacy;
4. SamplingPlan / finite-evidence adequacy;
5. generator implementation integrity;
6. generator distribution conformance;
7. reference/truth adequacy;
8. representation fidelity;
9. measurement adequacy/applicability;
10. statistical sufficiency;
11. secrecy / role-separation integrity;
12. unresolved limitations and residual uncertainty.

The dossier **does not invent** the population, SamplingPlan, measurement, or score after observing candidate results. It evaluates prospectively registered objects.

---

# 27. Landscape and physics intelligence

Distribution identity is a first-class experimental context variable.

Future experimental memory should preserve, at minimum:

```text
physical system identity
claim/envelope identity
distribution identity
SamplingPlan identity
construction-access policy
candidate construction intervention
representation adapter identity
reference policy / status
measurement identity
selection provenance
outcome / censoring
reproducibility
qualification result
```

A transfer claim that ignores population shape can confuse "same PDE" with "same scientific task."

---

# 28. P0 compatibility

This architecture is designed to be backward-compatible with the narrow P0 loop.

P0 may continue implementing:

```text
(seed, role=train/eval/stress)
        ↓
Burgers generator
        ↓
arrays + reference solution
```

Recommended cheap hooks now:

- separate distribution identity/version from generator identity/version;
- explicit role metadata;
- bind official results to generator/distribution versions;
- preserve reference provenance separately;
- avoid assuming future cases are always tensors;
- avoid assuming all future construction access is training data;
- record censoring/failure class distinctly;
- keep generator code unable to silently redefine score semantics.

No generalized runtime object is required before tech/science review and implementation need.

---

# 29. Commercial framing

A strong partner formulation is:

> **A partner defines the physical job, operating population, outputs that matter, and trusted evidence sources. Carbon turns that into a qualified procedural task distribution, opens controlled competition over how to construct the fast model, and independently tests candidates on fresh cases from that qualified distribution.**

This is not simply "training on customer data." Carbon helps make the **scientific search problem itself explicit, versioned, reproducible, and independently defensible**.

---

# 30. Constitutional additions proposed for review

1. **The scientific task owns the target population; the generator implements it.**
2. **Target population, sampling/proposal distribution, and score weighting are separate semantics.**
3. **Envelope and distribution are distinct scientific objects.**
4. **SamplingPlan is separate from population definition.**
5. **Generator conformance is distinct from reference correctness.**
6. **Canonical physical cases precede model-family materialization.**
7. **Representation adapters may change encoding, not physical reality.**
8. **Construction access is broader than training data.**
9. **Seed separation may require additional semantic decontamination.**
10. **Nominal, stress, search, qualification, and deployment populations are not automatically equivalent.**
11. **Reference failure is not candidate failure.**
12. **Distribution uncertainty and provenance must remain visible.**
13. **Hierarchical/stratified populations require subgroup evidence where scientifically material.**
14. **Query population is part of the scientific task.**
15. **Finite-sample/statistical sufficiency is part of Challenge qualification.**
16. **Censoring must not silently reshape the realized exam.**
17. **Distribution identity is authoritative experiment provenance.**
18. **Material population changes are versioned, qualified, and prospective.**
19. **No candidate producer controls the official population that grades itself.**
20. **Universal generator means universal interface/invariants, not one universal physics implementation.**

---

# 31. Final design statement

> **Carbon does not merely generate data. Carbon defines and qualifies a physical task population, designs a finite sampling plan, verifies that a generator conforms to it, and then produces fresh canonical cases for independent scientific evaluation.**

This is the distribution-side foundation required for Carbon's model-construction, evidence, qualification, and physics-intelligence vision.
