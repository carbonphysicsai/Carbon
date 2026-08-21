# Carbon Challenge Instance Distribution Architecture

**Status:** DESIGN INTEGRATION DRAFT — architecture-level, pending tech/science-lead review.  
**Purpose:** Define a durable, model-family-neutral architecture for scientifically defensible Challenge instance generation and distribution qualification across Carbon's full vision.  
**Does not override:** current P0 wire contracts, `Generator_Creation.md`, `Generator_Validation.md`, `Data_Management.md`, `Scoring.md`, `Build_Out.md`, LIVE Challenge semantics, or product qualification rules.  
**Simulation basis:** `docs/context/DISTRIBUTION_GAUNTLET_SIMULATION.md`.

---

# 1. Design objective

Carbon's current generator architecture is correctly built around fresh seeded draws, train/eval/stress separation, a declared envelope, reference backends, and a Validation Dossier. Those principles survive the broader Carbon architecture.

The missing abstraction is that the **distribution itself is part of the scientific task**.

A generator can be deterministic, reproducible, and numerically correct while still sampling the wrong problem population. Carbon therefore needs an explicit contract for what population the generator is intended to implement.

The durable rule is:

> **The scientific task owns the distribution. The generator is a qualified implementation of that distribution.**

---

# 2. Canonical architecture

```text
DOMAIN SCIENCE / ENGINEERING INTENT
                ↓
        PhysicalSystemSpec
                +
      CandidateOutputContract
                +
      Claim / Operating Envelope
                ↓
   InstanceDistributionContract
                ↓
     ChallengeInstanceGenerator
                ↓
      CanonicalChallengeInstance
                ↓
  representation / construction adapters
                ↓
             Candidate
                ↓
      protected official evaluation
                ↓
 MeasurementContracts + reference truth
                ↓
          ExperimentRecord
                ↓
   Landscape / qualification / lifecycle
```

This architecture standardizes the **physical task and its sampled population**, not the candidate's internal model family.

---

# 3. `InstanceDistributionContract`

## 3.1 Purpose

`InstanceDistributionContract` is the versioned scientific definition of the physical-case population used by a Challenge.

It is distinct from:

- `PhysicalSystemSpec`, which describes the physical system;
- the claim/operating envelope, which defines admissible support and exclusions;
- `ChallengeInstanceGenerator`, which implements the sampling process;
- `CandidateOutputContract`, which defines what the candidate must accept/return;
- `MeasurementContract`, which defines how a property is measured;
- the Score Pack, which defines score-bearing use.

## 3.2 Conceptual contents

The exact serialization is deferred, but the contract should be capable of representing:

```text
InstanceDistributionContract {
  distribution_id
  version

  physical_system_spec_ref
  candidate_output_contract_ref
  claim_envelope_ref

  intended_population_semantics

  variable_populations[] {
    semantic_ref
    support
    sampling_rule
    parameters
    conditional_dependencies
    correlations
    constraints
  }

  geometry_population
  boundary_condition_population
  initial_condition_population
  coefficient / material population
  forcing / source population
  query / observation population

  role_policies {
    construction
    evaluation
    stress
    qualification
  }

  stress_taxonomy
  rare_event_policy
  exclusions
  coverage_requirements
  weighting / consequence semantics

  provenance
  validation_evidence_refs
  limitations
  disclosure_class
}
```

## 3.3 Scientific meaning

The contract should distinguish at least:

```text
support / envelope
       !=
probability or sampling measure
       !=
stress/consequence distribution
```

Two Challenges may share the same physical system and envelope while representing materially different scientific tasks because their distributions differ.

---

# 4. `ChallengeInstanceGenerator`

## 4.1 Universal interface, Challenge-specific implementation

Carbon should **not** attempt to create one universal physical generator implementation.

The universal contract is conceptual:

```text
generate(
    seed,
    role,
    distribution_contract_version,
    generator_version,
) -> CanonicalChallengeInstance
```

Each Challenge may implement generation using the scientifically appropriate mechanism:

- analytic sampling;
- procedural PDE setup;
- CAD/geometry synthesis;
- dataset-backed sampling where justified;
- experimental campaign selection;
- coupled-system assembly;
- stochastic-process realization;
- partner-controlled generation.

## 4.2 Required invariants

Every official generator must preserve:

1. versioned identity;
2. role separation;
3. deterministic replay where the Challenge requires it;
4. support inside the registered claim semantics;
5. generator/distribution binding;
6. no miner control of official eval/stress realization;
7. no hidden-seed leakage;
8. reference provenance separation;
9. distribution qualification before LIVE;
10. no silent material distribution change.

---

# 5. `CanonicalChallengeInstance`

## 5.1 Purpose

A `CanonicalChallengeInstance` represents one sampled physical problem independent of how a particular model family consumes it.

It should be capable of carrying references to:

```text
physical inputs
parameters
geometry/topology
boundary conditions
initial conditions
forcing/source terms
requested outputs / query points
applicability metadata
reference-truth request
measurement applicability
provenance
```

It is not required to be a tensor.

## 5.2 Why canonical instances matter

Without a canonical instance layer, mixed-family competitions risk this failure:

```text
FNO generator -> one physical population
ROM generator -> another physical population
GNN generator -> another physical population
```

That is not a fair model-family comparison.

The required direction is:

```text
one sampled physical reality
        ↓
multiple authorized materializations
```

---

# 6. Representation and materialization

Model families may legitimately need different data structures.

Examples:

```text
canonical instance
    ├─> regular grid
    ├─> unstructured mesh
    ├─> graph
    ├─> point/query set
    ├─> reduced-basis snapshot representation
    └─> solver/configuration input
```

### Invariant

> **Representation adapters may change encoding; they must not change the sampled physical case.**

Any lossy or approximate representation conversion must carry provenance and, where material, qualification evidence.

---

# 7. Long-term role semantics

Current P0 uses:

```text
train
eval
stress
```

This remains correct for the P0 neural-training implementation.

The more durable conceptual roles are:

```text
construction
evaluation
stress
qualification
```

where `construction` may provide:

- training examples;
- basis snapshots;
- calibration cases;
- high-fidelity truth-query access;
- public symbolic/physical semantics;
- or no sampled data at all.

Thus:

```text
P0: construction == training
```

but Carbon should not bake "training data" into its terminal ontology.

---

# 8. Distribution qualification

A Challenge must not go LIVE merely because the generator is executable.

Generator/distribution qualification should separate four evidence classes.

## 8.1 Implementation integrity

Evidence that the implementation behaves as registered:

- deterministic replay where required;
- version/hash binding;
- role-domain separation;
- constraint enforcement;
- seed handling;
- no realization leakage;
- canonical-instance reproducibility.

## 8.2 Distribution adequacy

Evidence that the generated population matches the intended scientific task:

- support and exclusion compliance;
- marginal coverage;
- joint/correlated coverage;
- conditional structure;
- geometry-family coverage;
- rare/stress category coverage;
- degeneracy detection;
- workload alignment where claimed;
- sensitivity to reasonable alternate sampling measures.

## 8.3 Reference adequacy

Evidence that truth/reference outputs are defensible:

- analytic derivation where available;
- numerical convergence;
- solver-version provenance;
- cross-code agreement;
- experimental evidence;
- uncertainty characterization;
- disagreement policy;
- applicability by regime.

## 8.4 Task relevance

Evidence that the distribution and requested outputs actually test the intended claim:

- CandidateOutputContract observability;
- MeasurementContract applicability;
- intended engineering use connection;
- consequence weighting where justified;
- no unsupported extension from search to product claim.

---

# 9. Distribution provenance

The intended distribution may be authored from multiple evidence sources:

```text
physics constraints
engineering requirements
historical operating data
simulation campaign statistics
expert elicitation
test matrices
regulatory/qualification matrices
future-use scenarios
```

These sources must remain distinguishable.

A historical workload distribution is **observational evidence**, not automatically the desired future evaluation distribution.

---

# 10. Stress distributions

Stress testing must remain distinct from nominal workload sampling.

```text
nominal/workload distribution
        !=
stress / consequence-weighted distribution
```

Stress roles may deliberately oversample:

- rare physical regimes;
- boundaries/corners;
- known instability regions;
- high-consequence conditions;
- challenge-specific failure modes.

This does not imply those cases occur at the same frequency in deployment.

The Score Pack must define how stress evidence influences admissibility/ranking.

---

# 11. Extrapolation and OOD

Avoid using "OOD" as a substitute for precise Challenge semantics.

Carbon should distinguish:

- construction-population shift;
- evaluation-population shift;
- rare/stress samples inside the claim envelope;
- explicitly registered extrapolation tasks;
- truly out-of-claim conditions.

Score-bearing instances should remain inside registered claim semantics unless extrapolation competence is explicitly part of the Challenge.

---

# 12. Construction information budgets

For future non-neural or agentic construction, information access itself becomes part of the intervention.

Examples:

```text
fixed training dataset
adaptive solver-query budget
basis-building snapshots
experimental observations
public symbolic system
licensed partner data
```

A future `ConstructionInputPolicy` should therefore bind:

- what instance distribution(s) may be queried;
- query budget;
- fidelity levels;
- adaptivity;
- data retention;
- disclosure restrictions;
- cost accounting.

Official evaluation remains isolated from this construction-access domain.

---

# 13. Randomness domains

Future stochastic Challenges may require explicit separation of randomness roles.

Conceptually:

```text
instance_sampling_randomness
physical_realization_randomness
measurement_noise_randomness
reference_solver_randomness
construction_randomness
candidate_randomness
```

These domains should not be collapsed into one universal seed if doing so obscures provenance or independence.

Exact seed derivation remains owned by current/future security specs.

---

# 14. Multiphysics and composition

Component distributions do not automatically compose into a valid joint system distribution.

Future coupled Challenges may require:

- joint sampling;
- conditional subsystem sampling;
- interface compatibility constraints;
- correlated uncertain inputs;
- coupled geometry/topology constraints.

A future `CouplingContract` and `InstanceDistributionContract` should compose explicitly rather than assume independent subsystem draws are valid.

---

# 15. Search vs product distributions

The subnet's search distribution and a customer's product-use population answer different questions.

```text
SEARCH DISTRIBUTION
scientific discrimination / efficient competition

PRODUCT QUALIFICATION DISTRIBUTION
job-shaped evidence for a defined context of use

DEPLOYMENT POPULATION
what actually occurs during operation
```

These may overlap but are never automatically equivalent.

> **Rank nominates. Evidence qualifies.**

Qualification must bind the exact product distribution/context that supports its claim.

---

# 16. Distribution lifecycle

A distribution is versioned lifecycle state, not timeless truth.

Material changes may arise from:

- new operating regimes;
- changed customer use;
- new geometry families;
- observed drift;
- newly discovered failure modes;
- corrected scientific assumptions.

Required response may include:

- new distribution version;
- new generator qualification;
- restricted claim;
- requalification;
- retirement.

Historical experiment records stay bound to the distribution version under which they were produced.

---

# 17. Landscape and physics intelligence

Distribution identity is a required context variable for scientifically useful cross-Challenge learning.

Future experimental memory should preserve at least:

```text
physical system identity
instance distribution identity
construction-access policy
candidate construction intervention
measurement identity
selection provenance
outcome / censoring
reproducibility
qualification result
```

A transfer claim that ignores distribution shape may confuse "same PDE" with "same scientific task."

Physics intelligence must therefore learn over **intervention × physical context × distribution × measurement × outcome**, not only Challenge labels.

---

# 18. Governance and change control

The candidate producer must not define the official distribution used to prove its own success.

Material distribution changes require:

1. explicit version change;
2. prospective application;
3. validation evidence;
4. disclosure review;
5. registry binding;
6. no silent historical rescore.

Landscape or agentic systems may propose new distribution/stress versions but may not silently mutate LIVE exam semantics.

---

# 19. P0 compatibility

This architecture is designed to be backward-compatible with the current P0 scientific loop.

P0 can continue implementing:

```text
(seed, role=train/eval/stress)
        ↓
Burgers generator
        ↓
arrays + reference solution
```

Recommended P0-safe design habits:

- keep distribution config versioned;
- keep generator version separate from Challenge id;
- keep roles explicit;
- keep reference provenance separate from candidate inputs;
- avoid assuming all future instances are tensors;
- avoid assuming all future construction access is training data;
- preserve a path for representation-neutral instance metadata.

No generalized runtime object is required before tech/science review and implementation need.

---

# 20. Commercial framing

The architecture supports a stronger partner proposition:

> **A partner defines the physical job, operating population, outputs that matter, and trusted evidence sources. Carbon turns that into a qualified procedural task distribution, opens controlled competition over how to construct the fast model, and independently tests candidates on fresh cases from that qualified distribution.**

This is not simply "training on customer data."

Carbon's value includes making the **scientific search problem itself explicit, versioned, reproducible, and independently defensible**.

---

# 21. Constitutional additions proposed for review

1. **The scientific task owns the distribution; the generator implements it.**
2. **Envelope and distribution are distinct scientific objects.**
3. **Instance integrity, distribution adequacy and reference adequacy are separate claims.**
4. **Canonical physical instances precede model-family materialization.**
5. **Representation adapters may change encoding, not physical reality.**
6. **Construction access is broader than training data.**
7. **Nominal and stress distributions are distinct roles.**
8. **Distribution identity is part of authoritative experimental provenance.**
9. **Search, qualification and deployment populations are not automatically equivalent.**
10. **Material distribution changes are versioned, qualified and prospective.**
11. **No producer controls the official distribution that grades itself.**
12. **A universal generator means a universal interface/invariant set, not one universal physics implementation.**

---

# 22. Final design statement

The durable architecture is:

> **Carbon does not merely generate data. Carbon qualifies a physical task distribution and then generates fresh, canonical examination instances from it.**

This makes data generation coherent with Carbon's broader model-construction, evidence, qualification, and physics-intelligence vision while preserving the simplicity of the current neural-operator P0.
