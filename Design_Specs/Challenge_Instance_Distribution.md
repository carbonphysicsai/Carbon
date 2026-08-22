# Carbon Challenge Instance Distribution Architecture

**Status:** LOCKED ARCHITECTURE — owner-ratified on 2026-08-21; implementation/schema details remain subject to tech/science review and domain-spec integration.  
**Purpose:** Define a durable, model-family-neutral architecture for scientifically defensible Challenge population definition, finite sampling, instance generation, representation, truth realization, and provenance across Carbon's full vision.  
**Scope:** This locks the architectural invariants and authority boundaries. It does not by itself change current P0 wire contracts, seed derivation, scoring mathematics, LIVE Challenge semantics, or product qualification rules; those change only through their domain-owning specifications.  
**Simulation basis:** `docs/context/DISTRIBUTION_GAUNTLET_SIMULATION.md`.

---

# 1. Design objective

Carbon's current generator architecture has the right foundational instincts: fresh seeded draws, train/eval/stress separation, declared envelopes, reference backends, versioning, hidden official realizations, and a Validation Dossier before LIVE.

The broader architecture requires one critical generalization:

> **The distribution itself is part of the scientific task.**

A generator can be deterministic, reproducible, numerically correct, and well matched to a reference solver while still sampling the wrong scientific population. Therefore the executable generator must not become the scientific definition of the task by accident.

The durable authority rule is:

> **The scientific task owns the population. The sampling plan defines how finite evidence is drawn. The generator is a qualified implementation of that plan.**

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

For any finite scientific exam, Carbon distinguishes:

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

> **Sampling prevalence, target-population prevalence, and score importance are separate semantics.**

---

# 4. `InstanceDistributionContract`

`InstanceDistributionContract` is the versioned scientific definition of the population of admissible physical cases associated with a Challenge.

It is distinct from:

- `PhysicalSystemSpec` — what physical system is represented;
- claim/operating envelope — what support and exclusions are claimed;
- `SamplingPlan` — how finite evidence is drawn from the population;
- `ChallengeInstanceGenerator` — executable sampler/instance constructor;
- `CandidateOutputContract` — what a candidate must accept/return;
- `MeasurementContract` — how a property is numerically measured;
- Score Pack — how qualified measurements become score-bearing.

Conceptually it must be able to represent population semantics, variable supports, conditional dependencies/correlations, geometry/topology populations, BC/IC/forcing/material populations, query/observation populations, temporal/episode populations, strata/hierarchies, exclusions, rare-event semantics, role-population references, provenance, uncertainty, evidence maturity, limitations, and disclosure class.

The exact serialization remains deferred.

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

A scientifically meaningful population does not determine how much finite evidence is needed or how that evidence should be allocated.

`SamplingPlan` is the prospective finite-evidence design. It may bind:

- target distribution reference;
- proposal/sampling policy;
- sample budget;
- strata allocation;
- tail/rare-event allocation;
- replication policy;
- query allocation;
- reference-fidelity allocation;
- uncertainty/tail-resolution/minimum-subgroup objectives;
- stopping/extension rules;
- duplicate/near-duplicate policy;
- censoring policy;
- provenance.

No universal power threshold is implied. Requirements are Challenge/evidence-type specific and scientifically reviewed.

A Challenge can be correctly specified and still produce weak evidence if the sample plan is too small or badly allocated. The Validation Dossier must evaluate statistical sufficiency for the intended estimands.

---

# 6. `ChallengeInstanceGenerator`

Carbon does **not** create one universal physics generator. It standardizes the interface and invariant set while allowing Challenge-specific implementations.

Conceptual interface:

```text
generate(
    seed,
    role,
    distribution_contract_version,
    sampling_plan_version,
    generator_version,
) -> CanonicalChallengeCase
```

Challenge-specific implementations may use analytic sampling, procedural PDE construction, CAD/geometry synthesis, dataset-backed sampling where justified, experimental campaign selection, stochastic realization, coupled-system assembly, partner-controlled generation, or high-fidelity simulation services.

Every official generator must preserve:

1. versioned identity/content binding;
2. registered distribution + SamplingPlan binding;
3. role separation;
4. deterministic replay where required;
5. support/exclusion compliance;
6. no miner control of official eval/stress realization;
7. no hidden-realization leakage;
8. reference provenance separation;
9. conformance qualification before LIVE;
10. no silent material population change;
11. preservation of strata/tail allocation;
12. explicit failure/censoring semantics.

---

# 7. Generator conformance is distinct from reference correctness

Reference-solver agreement does **not** prove that the generator samples the registered population.

Distribution-conformance evidence may include marginal, joint, conditional and constraint conformance; geometry-family/stratum/tail/query coverage; duplicate/near-duplicate rate; effective sample size; role separation; determinism; and intended-versus-realized population after failures/censoring.

Example:

```text
contract: ν ~ log-uniform
implementation bug: ν ~ uniform
```

Every physical solve may be correct while the Challenge is still scientifically wrong.

---

# 8. `CanonicalChallengeCase`

The durable abstraction is a representation-neutral physical case upstream of model-family materialization.

```text
CanonicalChallengeCase
    ├─ StaticInstance
    └─ SequentialEpisode / Trajectory
```

P0 may continue using simple arrays/static cases.

A canonical case may bind challenge/role/population/SamplingPlan/generator identity; physical inputs; parameters; geometry/topology; BCs/ICs; forcing; requested outputs and query locations/times; episode semantics; reference-truth request; measurement applicability; representation requirements; and provenance.

It is not required to be a tensor, mesh, or file.

---

# 9. Query / observation population is part of the task

The same physical state can be easy or hard depending on what is queried. Distribution architecture must be capable of representing spatial/temporal query population, observable selection, resolution/fidelity request, sensor/observation population, and episode horizon where relevant.

`CandidateOutputContract` defines what queries are admissible. `InstanceDistributionContract` and `SamplingPlan` define which admissible queries are actually sampled for evidence.

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

> **Representation adapters may change encoding; they must not change the sampled physical reality.**

Adapters preserve provenance. Lossy transformations or representation-induced measurement limitations require explicit evidence and, where material, qualification.

---

# 11. Role semantics and semantic decontamination

P0 uses `train / eval / stress`. Long-term roles generalize to `construction / evaluation / stress / qualification`, where construction access may include training examples, basis snapshots, calibration observations, solver-query budget, experiments, symbolic equations, or no sampled data.

Seed separation is necessary but not always sufficient. Some Challenges may require semantic decontamination such as geometry-family, specimen/entity, parameter-distance, mission/time-window, source-data, or cutoff separation.

---

# 12. Populations across search and product

These populations answer different questions:

```text
TARGET / WORKLOAD POPULATION
SEARCH / EVALUATION POPULATION
STRESS POPULATION
PRODUCT QUALIFICATION POPULATION
DEPLOYMENT POPULATION
```

They may overlap. They are never automatically equivalent.

> **Rank nominates. Evidence qualifies.**

---

# 13. Hierarchical and stratified populations

Real engineering populations are often hierarchical. Flattened global averages can hide important subgroup failure and create Simpson-type effects.

The architecture therefore supports explicit strata/hierarchies, minimum per-stratum evidence, stratum-level reporting, stratum-specific gates where required, and aggregate weighting that cannot erase mandatory subgroup failure.

---

# 14. Reference / truth realization

Reference truth is separate from population definition and generator conformance. A case may use analytic truth, numerical reference, multi-code consensus, experiment, partner golden, hybrid reference, or uncertainty-bearing truth.

Reference status remains distinguishable from candidate outcome, including available, uncertain, disagreement, numerical failure, infrastructure failure, or not applicable.

A candidate must not be punished for Carbon's own failed truth path.

---

# 15. Multi-fidelity truth allocation

Industrial Challenges may allocate different reference fidelities across cases. Physical-case population and reference-fidelity allocation are separate semantics; otherwise difficult regions can systematically receive weaker truth and bias evidence.

Reference-fidelity allocation belongs in SamplingPlan/ReferencePolicy provenance and qualification.

---

# 16. Distribution provenance and uncertainty

The intended population may be inferred/authored from physical constraints, engineering requirements, historical telemetry, simulation campaigns, expert elicitation, test matrices, regulatory/qualification matrices, and future-use scenarios. These are not equivalent evidence sources.

Population provenance should preserve source type, observation period, sample size, selection mechanism, missingness, uncertainty, maturity/confidence, and assumptions/extrapolations where applicable.

A historical workload distribution is observational evidence, not automatically the desired future evaluation population.

---

# 17. Measurement applicability is population-dependent

Some measurements apply only to subsets of the population. Applicability must be independently determined where possible and must not be controllable by the candidate. Aggregation records the eligible population for each measurement rather than silently treating non-applicable cases as pass, fail, or missing.

---

# 18. Estimands must be explicit

Possible estimands include expected error under target operation, physical-failure probability, tail risk, worst-stratum performance, consequence-weighted performance, and answerability/coverage conditional on a registered population.

`InstanceDistributionContract` defines the population; `MeasurementContract` defines measurement; Score Pack defines score-bearing estimand/aggregation.

---

# 19. Censoring and realized evidence population

The intended sample population may differ from the final valid-evidence population because of reference/generator/infrastructure failures, timeout, invalid cases, non-applicable measurements, corrupted experiments, or resource limits.

```text
intended sampled population
       !=
realized valid-evidence population
```

Censoring provenance remains visible. Hard physical cases must not disappear silently because they are expensive or failure-prone to evaluate.

---

# 20. Construction information budgets and external pretraining

For future broad construction search, information available to the producer is part of the intervention. A future `ConstructionInputPolicy` may bind accessible construction distributions, data/observation rights, high-fidelity query budget, fidelity/adaptivity, retention, external/pretraining allowance, licensed/proprietary sources, and resource accounting.

Fresh official seeds reduce contamination risk but do not make pretraining/data provenance irrelevant for narrow task distributions.

---

# 21. Randomness domains

Stochastic Challenges may require distinct randomness domains for instance sampling, physical realization, measurement noise, reference solver, construction, and candidate randomness. These are not collapsed when independence/provenance matters. Exact seed derivation remains owned by security/data specs.

---

# 22. Multiphysics and composition

Component distributions do not automatically compose into a valid joint system population. Coupled Challenges may require joint/conditional sampling, interface compatibility constraints, correlated uncertainty, and coupled geometry/topology rules.

A future `CouplingContract` and `InstanceDistributionContract` compose explicitly rather than assuming independent subsystem draws are valid.

---

# 23. Privacy and disclosure

Scientific authority does not require public disclosure of every distribution parameter. Private partner populations may reveal proprietary operating profiles, mission mix, geometry frequency, process recipes, or failure modes.

Distribution artifacts therefore require disclosure classes. Public surfaces may expose identity, digest, claim scope, validation status, and limitations while controlled exact densities/conditional rules remain protected. Hidden official realizations remain protected regardless.

---

# 24. Material-change semantics

Not every generator refactor creates a new scientific population, but material population changes are explicit. Examples include marginal-density, correlation/conditional, geometry-family, stratum, stress-prevalence, query-population, exclusion, and qualification-population changes.

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

The Validation Dossier qualifies, where applicable:

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

The dossier does **not** invent population, SamplingPlan, measurement, or score after observing candidate results.

---

# 27. Landscape and physics intelligence

Distribution identity is a first-class experimental context variable. Future experimental memory preserves physical system, claim/envelope, distribution, SamplingPlan, construction-access policy, construction intervention, representation adapter, reference policy/status, measurement identity, selection provenance, outcome/censoring, reproducibility, and qualification result.

A transfer claim that ignores population shape can confuse “same PDE” with “same scientific task.”

---

# 28. P0 compatibility

This architecture is backward-compatible with the narrow P0 loop:

```text
(seed, role=train/eval/stress)
        ↓
Burgers generator
        ↓
arrays + reference solution
```

Recommended cheap hooks now: separate distribution identity/version from generator identity/version; explicit role metadata; bind results to generator/distribution versions; preserve reference provenance; avoid assuming cases are always tensors or construction access always means training data; record censoring/failure class distinctly; prevent generator code from redefining score semantics.

No generalized runtime object is required merely because the architecture is locked.

---

# 29. Commercial framing

> **A partner defines the physical job, operating population, outputs that matter, and trusted evidence sources. Carbon turns that into a qualified procedural task distribution, opens controlled competition over how to construct the fast model, and independently tests candidates on fresh cases from that qualified distribution.**

Carbon helps make the scientific search problem itself explicit, versioned, reproducible, and independently defensible.

---

# 30. Locked constitutional invariants

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
12. **Distribution uncertainty and provenance remain visible.**
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
