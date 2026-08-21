# Distribution Gauntlet Simulation — Universal Challenge-Instance Generation

**Branch:** `design/symbolic-numeric-integration`  
**Status:** design-forward simulation; no P0 runtime or scoring change.  
**Purpose:** Stress-test whether Carbon can elevate data/distribution generation into a scientifically defensible architecture that survives the full long-term vision: multiple physics families, multiple model families, industry-defined workloads, multiphysics, stochastic systems, sparse experimental truth, agentic construction, product qualification, and physics-intelligence learning.  
**Related:** `Design_Specs/Generator_Creation.md`, `Design_Specs/Generator_Validation.md`, `Design_Specs/Data_Management.md`, `Design_Specs/Physical_System_Representation.md`, `Design_Specs/System_Identity_and_Roadmap.md`, `docs/context/SYMBOLIC_NUMERIC_GATE_9_FINAL_SYSTEM_REVIEW.md`.

---

# 1. Executive conclusion

The current generator architecture contains the correct seed/role and qualification instincts, but it is still too tightly shaped around learned PDE surrogates.

The durable abstraction should be:

> **Carbon qualifies a physical task distribution, then samples canonical Challenge instances from that qualified distribution. Model-specific representations are derived downstream.**

The generator itself should therefore be generalized conceptually from a **data generator** into a **Challenge Instance Generator** implementing a versioned **Instance Distribution Contract**.

The most important discovery is:

> **The generator does not define the scientific task by accident. The scientific task owns the distribution; the generator is a qualified implementation of that distribution.**

A deterministic generator can still generate scientifically irrelevant nonsense. Carbon therefore needs to distinguish:

1. instance integrity;
2. distribution adequacy;
3. reference/truth adequacy;
4. representation fidelity;
5. evaluation secrecy;
6. product-use relevance.

All six must remain separately reviewable.

---

# 2. Proposed durable architecture

```text
DOMAIN SCIENCE / ENGINEERING INTENT
                ↓
        PhysicalSystemSpec
                +
         Task / I-O Contract
                +
      Operating / Claim Envelope
                ↓
   Instance Distribution Contract
                ↓
     Challenge Instance Generator
                ↓
      Canonical ChallengeInstance
        ┌──────────┼──────────┐
        ↓          ↓          ↓
 construction   evaluation   stress / qualification
 access         access       access
        │          │          │
        ↓          ↓          ↓
 representation/materialization adapters
        │          │          │
        └────── candidate common I/O ──────┐
                                            ↓
                                   MeasurementContracts
                                            ↓
                                   Reference / truth path
                                            ↓
                                     ExperimentRecord
```

### Authority rule

No object above may silently certify the next one.

- `PhysicalSystemSpec` describes the physical system.
- `CandidateOutputContract` defines the job exposed to candidates.
- `InstanceDistributionContract` defines the intended population of physical cases.
- `ChallengeInstanceGenerator` implements that population.
- Validation Dossier qualifies the implementation and its evidence.
- Score Pack defines score-bearing use of measurements.
- Product qualification defines the later job-shaped claim.

---

# 3. Core conceptual objects

## 3.1 `InstanceDistributionContract`

A versioned scientific contract describing the population from which Challenge instances are drawn.

Conceptual fields:

```text
InstanceDistributionContract {
  distribution_id
  version
  physical_system_spec_ref
  candidate_output_contract_ref
  claim_envelope_ref

  variables {
    name
    semantic_ref
    support / allowed domain
    distribution_family_or_sampling_rule
    parameters
    conditional_dependencies
    correlations
    constraints
  }

  geometry_population
  boundary_condition_population
  initial_condition_population
  parameter_population
  forcing / source population
  observation / query population

  role_policies {
    construction
    evaluation
    stress
    qualification
  }

  stress_taxonomy
  rare_event_policy
  exclusion_policy
  coverage_requirements
  weighting / consequence policy
  provenance
  intended_population_semantics
  limitations
  validation_evidence_refs
  disclosure_class
}
```

The exact serialization is deferred. The conceptual separation is the important decision.

## 3.2 `ChallengeInstanceGenerator`

A versioned executable implementation of the registered distribution contract.

Conceptual interface:

```text
generate(
    seed,
    role,
    distribution_contract_version,
    generator_version,
) -> CanonicalChallengeInstance
```

The implementation is Challenge-specific. The interface and invariants are universal.

## 3.3 `CanonicalChallengeInstance`

A representation-neutral record of one sampled physical task.

Conceptually:

```text
CanonicalChallengeInstance {
  challenge_id
  instance_id_internal
  role
  distribution_version
  generator_version

  physical_inputs
  parameters
  geometry / topology refs
  boundary / initial conditions
  forcing / sources
  requested observables / queries
  applicability metadata

  reference_truth_request
  measurement_applicability
  provenance
}
```

It is not necessarily a tensor, mesh, file, or training batch.

## 3.4 Representation adapters

A separate adapter materializes the same canonical instance for a candidate family or backend:

```text
CanonicalChallengeInstance
        ↓
  grid adapter
  mesh adapter
  graph adapter
  point/query adapter
  solver-config adapter
  experimental-instrument adapter
```

Representation adapters must not change the underlying sampled physical case.

---

# 4. Gauntlet 1 — simple analytic PDE

### Case

Burgers / Poisson with clean parameter ranges and analytic or high-confidence numerical truth.

### Test

Can the architecture reproduce current P0 behavior without unnecessary complexity?

### Result

**PASS.**

For P0:

```text
construction role = training samples
 evaluation role  = hidden evaluation samples
 stress role      = hidden edge/regime samples
```

`CanonicalChallengeInstance` can remain lightweight and immediately materialize to arrays. No need to expose the new abstractions on the current wire contract.

### Learning

The abstraction can exist architecturally while P0 implementation remains simple.

---

# 5. Gauntlet 2 — same envelope, wrong density

### Case

A CFD Challenge publishes Mach 0.6–0.9 and AoA -2°–8°, but the sampler places almost all probability mass around an easy central regime.

### Failure

A deterministic generator and accurate reference solver still produce a scientifically weak competition because the rewarded objective is dominated by the wrong population.

### Result

**FAIL without an explicit distribution contract.**

### Learning

Envelope bounds are necessary but insufficient.

Carbon must record the distinction:

```text
support / envelope
!=
probability or sampling measure over that support
```

A model claim is therefore conditional on both.

---

# 6. Gauntlet 3 — correlations and physically impossible combinations

### Case

Temperature, pressure, geometry, material state, Mach, Reynolds number or operating state are sampled independently even though the real system has strong dependencies.

### Failure

Independent box sampling can create physically meaningless cases or overweight unrealistic combinations.

### Result

**FAIL if the distribution cannot express conditional structure.**

### Learning

`InstanceDistributionContract` needs conditional/correlated sampling semantics and explicit physical constraints.

For industrial tasks, partner workload statistics may be evidence for the joint distribution without becoming the sole authority.

---

# 7. Gauntlet 4 — rare but consequential regimes

### Case

A regime occurs only 0.1% of the time but is safety-critical or economically catastrophic.

### Failure

Naive empirical-frequency sampling may almost never test it. Uniform stress oversampling may distort the ordinary workload.

### Result

**PASS only if ordinary population and consequence-weighted stress are separate roles.**

### Learning

Carbon should distinguish:

```text
nominal / workload distribution
stress / consequence distribution
```

The stress distribution is not automatically the deployment frequency distribution.

Its role must be declared prospectively.

---

# 8. Gauntlet 5 — distribution shift and OOD language

### Case

Training/construction cases cover one subpopulation, evaluation cases another, stress cases the difficult edge of the same declared claim envelope.

### Risk

Calling all stress tests "OOD" is ambiguous. Some are deliberately rare but still inside the declared envelope; others may be truly outside the claim domain and should not be score-bearing under the current Challenge.

### Result

**REVISE terminology.**

### Learning

Use explicit relationships:

```text
construction distribution
 evaluation distribution
 stress distribution
 claim envelope
```

Score-bearing cases must remain inside the registered Challenge claim envelope unless the task explicitly defines extrapolative competence.

---

# 9. Gauntlet 6 — multiple model families

### Case

FNO, GNN, ROM, symbolic approximation and hybrid solver compete on the same physical task.

### Failure mode

If each model family has its own generator, the physical competition can silently change across candidates.

### Result

**PASS only with canonical physical instances upstream of representation.**

### Learning

The invariant should be:

> **Model-family adapters may change representation, never the sampled physical reality.**

This is the data-generation counterpart of `CandidateOutputContract`.

---

# 10. Gauntlet 7 — no-learning candidate

### Case

An analytic approximation or symbolic reduction requires no training set.

### Failure

A universal `train/eval/stress` ontology assumes every candidate learns from samples.

### Result

**REVISE role abstraction.**

### Learning

Long term use:

```text
construction
 evaluation
 stress
 qualification
```

where `construction` may expose:

- training examples;
- basis snapshots;
- solver-query budget;
- calibration observations;
- public equations;
- or no sampled data at all.

P0 may continue mapping `construction = train`.

---

# 11. Gauntlet 8 — adaptive construction / active truth queries

### Case

A construction algorithm adaptively chooses high-fidelity solver calls.

### Failure

A static training dataset no longer captures the information available to the producer.

### Result

**PASS only if construction access itself is contracted and metered.**

### Learning

`ConstructionInputPolicy` and `InstanceDistributionContract` must interoperate.

The true intervention includes:

```text
what information was available
+
what query budget was available
+
what adaptivity was permitted
```

Truth access is a resource, not free scientific authority.

---

# 12. Gauntlet 9 — stochastic physical systems

### Case

Intrinsic stochasticity, uncertain forcing, random material microstructure, stochastic boundary conditions or experimental noise.

### Failure

One seed may mix:

- sampling of the physical realization;
- numerical solver randomness;
- candidate randomness;
- measurement noise.

### Result

**PASS only with domain-separated randomness semantics.**

### Learning

Future contracts need distinct randomness domains, for example:

```text
physical_realization_seed
instance_sampling_seed
measurement_noise_seed
reference_solver_seed (if needed)
construction_randomness
candidate_randomness
```

Not all need to be public; all material roles need provenance.

---

# 13. Gauntlet 10 — geometry and topology populations

### Case

Industrial CAD/mesh families where geometry itself is a high-dimensional random object.

### Failure

Scalar parameter ranges cannot define the task distribution.

### Result

**PASS if geometry population is a first-class distribution component with reference identity and generation provenance.**

### Learning

Do not force geometry into a universal numeric vector schema.

Allow versioned geometry-population references and Challenge-specific generators/adapters.

---

# 14. Gauntlet 11 — multiphysics composition

### Case

Fluid, thermal and structural components with coupled interface states.

### Failure

Independent subsystem sampling can create incompatible interface conditions and an invalid joint physical population.

### Result

**PASS only if coupled distribution generation is joint or explicitly conditionally composed.**

### Learning

A future `CouplingContract` and `InstanceDistributionContract` must define compatible joint sampling at interfaces.

Component distributions do not automatically compose into a valid system distribution.

---

# 15. Gauntlet 12 — sparse experiments as truth

### Case

Industrial system has limited experimental observations and no perfectly trusted solver.

### Failure

Treating the simulator as unquestioned truth or the sparse measurements as a full population creates false authority.

### Result

**PASS with explicit reference hierarchy and uncertainty.**

### Learning

`reference_truth_request` should support:

- analytic truth;
- numerical reference;
- multi-code consensus;
- experiment;
- partner golden;
- hybrid reference;
- uncertainty-bearing truth.

Reference source and uncertainty are separate from the sampled instance distribution.

---

# 16. Gauntlet 13 — partner workload distribution

### Case

Partner says "our system operates in these ranges" and provides historical workload frequency.

### Risk

Blindly cloning historical frequency may miss future use, rare critical cases, selection bias or confidential information.

### Result

**PASS with provenance-bearing distribution authoring.**

### Learning

Distribution evidence may come from:

```text
physics constraints
engineering requirements
historical telemetry
simulation campaign statistics
expert elicitation
regulatory/test matrices
future-use scenarios
```

Each source should retain provenance and limitations.

The Challenge authoring process must distinguish "observed historical workload" from "intended evaluation population."

---

# 17. Gauntlet 14 — malicious or gameable distribution authoring

### Case

A sponsor, miner, validator or internal team benefits from a distribution that favors a known method.

### Failure

A technically valid generator can still encode a biased scientific objective.

### Result

**Requires governance separation.**

### Learning

The producer of a candidate must not control the official distribution that grades it.

Material distribution changes require:

- version change;
- prospective effect only;
- validation evidence;
- disclosure/qualification review;
- no silent historical reinterpretation.

---

# 18. Gauntlet 15 — adaptive evaluation and Landscape feedback

### Case

Landscape discovers a failure cluster and proposes more sampling there.

### Failure

Changing live evaluation distribution in response to current miners can destroy comparability and create endogenous grading.

### Result

**PASS only with discrete registered distribution versions.**

### Learning

Landscape may propose future stress/distribution changes, but cannot silently rewrite the current exam.

New distribution version -> new qualification -> prospective use.

---

# 19. Gauntlet 16 — benchmark saturation and evaluation-information leakage

### Case

Even with hidden seeds, repeated scores leak information about the fixed distribution and decision boundary.

### Result

**Current Evaluation Information Budget remains necessary.**

### Learning

Distribution diversity and procedural freshness do not eliminate adaptive overfitting.

Generator secrecy is not a substitute for disclosure governance.

---

# 20. Gauntlet 17 — product qualification

### Case

Subnet search distribution is optimized for scientific discrimination, while the deployed product sees a different customer workload.

### Failure

Leaderboard evidence is incorrectly treated as product-use evidence.

### Result

**PASS only with distinct product-use distribution.**

### Learning

Define:

```text
search distribution
!=
product qualification distribution
!=
deployment population
```

They may share the same physical envelope and generator components, but a commercial claim requires job-shaped evidence.

Product qualification should bind the exact distribution/context used for the claim.

---

# 21. Gauntlet 18 — answerability / escalation systems

### Case

Candidate is allowed to abstain or escalate some cases.

### Failure

Evaluation only conditions on answered cases, letting the candidate hide failures.

### Result

**PASS only if answerability is measured over the registered instance distribution.**

### Learning

Coverage, abstention and escalation are distribution-dependent metrics.

The task contract must define whether abstention is allowed and how coverage is measured.

---

# 22. Gauntlet 19 — physics intelligence and transfer learning

### Case

Landscape learns that a construction method transfers between "similar" Challenges.

### Failure

Similarity based only on envelope labels ignores distribution shape and selection provenance.

### Result

**Distribution identity becomes part of experimental context.**

### Learning

Future Landscape records should include:

```text
physical system identity
instance distribution identity
construction-access policy
measurement identity
selection provenance
outcome
```

Without distribution identity, cross-Challenge transfer conclusions can be badly confounded.

---

# 23. Gauntlet 20 — changing real-world population over time

### Case

Operational conditions drift after qualification.

### Failure

A previously defensible distribution becomes stale while the artifact is unchanged.

### Result

**Distribution is lifecycle state, not permanent truth.**

### Learning

Product lifecycle should support:

- population monitoring;
- drift detection;
- distribution-version update;
- restricted claim;
- requalification;
- retirement.

This mirrors Carbon's existing lifecycle qualification philosophy.

---

# 24. Strongest reconciled invariants

The simulation supports the following architecture-level principles.

1. **The scientific task owns the distribution; the generator implements it.**
2. **Envelope support and probability/sampling measure are separate scientific objects.**
3. **Instance integrity, distribution adequacy and reference adequacy are separate claims.**
4. **Canonical physical instances precede model-family representation adapters.**
5. **Representation changes must not change the sampled physical reality.**
6. **Construction access is more general than training data.**
7. **Nominal workload and stress/consequence sampling are distinct roles.**
8. **All score-bearing instances remain inside the registered claim semantics unless extrapolation is explicitly part of the task.**
9. **Distribution identity is part of experimental provenance and physics-intelligence context.**
10. **Material distribution changes are versioned and prospective.**
11. **Landscape may propose future distribution changes but cannot rewrite a live exam.**
12. **Search distribution does not automatically equal product qualification or deployment distribution.**
13. **A distribution must earn scientific adequacy through evidence before LIVE.**
14. **A generator is universal by interface and invariants, not by one physical implementation.**

---

# 25. Validation architecture implied by the simulation

Generator qualification should be decomposed into at least four evidence classes.

## A. Implementation integrity

- deterministic replay where required;
- seed-domain separation;
- version/hash binding;
- constraint satisfaction;
- no role leakage;
- canonical-instance reproducibility.

## B. Distribution adequacy

- support/envelope consistency;
- marginal and joint coverage;
- conditional/correlation fidelity;
- geometry-population coverage;
- rare/stress category coverage;
- exclusion enforcement;
- degeneracy checks;
- sensitivity to defensible alternative sampling measures;
- partner/workload alignment where claimed.

## C. Reference adequacy

- solver/experiment provenance;
- convergence;
- cross-reference agreement;
- uncertainty characterization;
- known disagreement/limitations;
- applicability by instance/regime.

## D. Task relevance

- candidate I/O observability;
- measurement applicability;
- intended-use connection;
- consequence weighting where justified;
- no unsupported expansion from search distribution to product claim.

The Validation Dossier should eventually expose these as separate sections/statuses rather than one undifferentiated "generator valid" flag.

---

# 26. What should remain P0-simple

This design does **not** require a P0 rewrite.

P0 can keep:

```text
(seed, train/eval/stress role)
        ↓
Burgers generator
        ↓
arrays / reference fields
```

provided the architecture does not hard-code assumptions that become impossible to generalize.

Recommended cheap hooks now:

- keep generator identity/version separate from Challenge identity;
- bind explicit role;
- retain envelope and distribution config as versioned artifacts;
- avoid assuming every future instance is a tensor;
- avoid assuming every future construction role is "training";
- preserve reference provenance separately from generated inputs;
- keep model-family materialization outside the scientific distribution definition where feasible.

---

# 27. Commercial consequence

The generalized architecture improves the partner proposition:

> **Bring Carbon a physical modeling job, its operating population, and trusted evidence sources. Carbon turns that into a qualified procedural task distribution, opens controlled competition over how to construct the fast model, and independently tests candidates on fresh cases from the qualified distribution.**

This is stronger than "we train on your data" because Carbon's product surface becomes the defensible definition and execution of a **model-discovery experiment**.

For partners with proprietary data, historical data may help qualify the distribution without becoming the public answer key.

---

# 28. Final design judgment

The distribution layer should be elevated to first-class architecture.

The recommended durable stack is:

```text
PhysicalSystemSpec
        ↓
CandidateOutputContract
        ↓
Claim / Operating Envelope
        ↓
InstanceDistributionContract
        ↓
ChallengeInstanceGenerator
        ↓
CanonicalChallengeInstance
        ↓
Representation / Construction Access
        ↓
Candidate
        ↓
Protected Measurement + Reference Truth
        ↓
ExperimentRecord
        ↓
Qualification / Landscape
```

The shortest statement of the discovery is:

> **Carbon should not universalize the physics generator. It should universalize what it means to generate a qualified physical examination instance.**

That abstraction survives every scenario tested here while preserving P0 simplicity.
