# Review These Preliminary Decisions — Distribution / Validation-Dossier Architecture

**Branch:** `design/symbolic-numeric-integration`  
**Status:** owner preliminary decisions; tech/science lead may accept, modify, or reject.  
**Purpose:** Distill the distribution/generator gauntlet and Validation Dossier synchronization into a compact review queue.  
**Scope:** Architecture-level decisions only. These do **not** change current P0 generator wire contracts, seeding rules, scoring, LIVE Challenge semantics, or product qualification until ratified into their domain-owning specifications.

---

# Executive disposition

The combined distribution + dossier review supports a stronger scientific chain:

```text
PhysicalSystemSpec
+ CandidateOutputContract
+ Claim / Envelope
        ↓
Target Population
        ↓
InstanceDistributionContract
        ↓
SamplingPlan
        ↓
ChallengeInstanceGenerator
        ↓
CanonicalChallengeCase
        ↓
Reference / Truth + Measurements
        ↓
Validation Dossier
        ↓
Score Pack
        ↓
Registry LIVE
```

Master recommendation:

> **Define the scientific population prospectively; design how finite evidence will be sampled; qualify the generator, truth path, representations and measurements against those definitions; only then allow a Score Pack to use that evidence for ranking.**

Review model:

```text
G1  ACCEPT / MODIFY / REJECT
...
G18 ACCEPT / MODIFY / REJECT
```

---

# G1 — Introduce `InstanceDistributionContract`

### Preliminary decision: **ACCEPT**

Use a future versioned scientific object for the intended physical-case population of a Challenge, including support relationship, marginal/joint/conditional structure, geometry/query populations, strata, exclusions, rare-event semantics, provenance, uncertainty and limitations.

### Guardrail

The object defines population semantics; it is not a score, generator implementation, or certificate.

### Confidence

**Very high.**

---

# G2 — Scientific task owns target population; generator implements it

### Preliminary decision: **ACCEPT**

Generator code/config cannot silently define the scientific task.

```text
scientific intent
→ distribution contract
→ SamplingPlan
→ generator
→ Validation Dossier
→ LIVE
```

### Confidence

**Very high.**

---

# G3 — Separate target population `P(x)`, proposal/sampling `Q(x)`, and score weighting `w(x)`

### Preliminary decision: **ACCEPT**

Rare/high-consequence regimes may be intentionally oversampled without being represented as ordinary workload frequency.

### Constitutional rule

> **Sampling prevalence, target-population prevalence, and score importance are separate semantics.**

### Confidence

**Very high.**

---

# G4 — Introduce a separate `SamplingPlan`

### Preliminary decision: **ACCEPT AS ARCHITECTURE**

Population definition should not absorb finite-evidence design.

A SamplingPlan may govern sample budget, strata allocation, tails, repeats, query allocation, fidelity allocation, stopping rules, duplicate policy and uncertainty/power objectives.

### Guardrail

No universal sample-size/power threshold is implied.

### Confidence

**Very high.**

---

# G5 — Generalize `CanonicalChallengeInstance` to `CanonicalChallengeCase`

### Preliminary decision: **ACCEPT AS LONG-TERM ARCHITECTURE; DEFER RUNTIME SHAPE**

The durable object should support:

```text
CanonicalChallengeCase
  ├─ StaticInstance
  └─ SequentialEpisode / Trajectory
```

P0 may remain static array-based.

### Why

Control, rollout, digital twins, adaptive experiments and agentic engineering are not naturally IID rows.

### Confidence

**High.**

---

# G6 — Representation adapters may change encoding, not physical reality

### Preliminary decision: **ACCEPT**

Mixed-family candidates must consume authorized materializations of the same canonical physical case.

Lossy representation conversion requires provenance and, where material, qualification.

### Confidence

**Very high.**

---

# G7 — Query / observation distribution is first-class task semantics

### Preliminary decision: **ACCEPT**

Where/when/what is queried can materially change difficulty even for the same physical case.

Distribution design should therefore support spatial/temporal query populations, observable selection, sensor distributions and episode horizons where relevant.

### Confidence

**Very high.**

---

# G8 — Generalize long-term roles to `construction/evaluation/stress/qualification`

### Preliminary decision: **ACCEPT CONCEPTUALLY; DO NOT CHANGE P0 ROLE NAMES YET**

P0 remains `construction == train`.

Long-term construction access may include training examples, basis snapshots, calibration data, adaptive truth-query budgets, experiments, symbolic equations, or no sampled data.

### Confidence

**High.**

---

# G9 — Seed separation may require semantic decontamination

### Preliminary decision: **ACCEPT**

Different seeds are necessary but may not be sufficient for a claimed generalization test.

Challenge-specific decontamination may require geometry-family, specimen/entity, time-window, mission, parameter-distance, or source-data separation.

### Confidence

**Very high.**

---

# G10 — Validation Dossier must qualify distinct evidence classes

### Preliminary decision: **ACCEPT**

The dossier should separately review, where applicable:

1. physical-system adequacy;
2. claim/envelope adequacy;
3. target-population adequacy;
4. SamplingPlan adequacy;
5. generator implementation integrity;
6. generator distribution conformance;
7. reference/truth adequacy;
8. representation fidelity;
9. measurement adequacy/applicability;
10. statistical sufficiency/estimand clarity;
11. secrecy/role separation;
12. residual uncertainty/limitations.

### Confidence

**Very high.**

---

# G11 — Generator distribution conformance is separate from reference correctness

### Preliminary decision: **ACCEPT**

A physically correct solver does not prove that the executable sampler implements the registered population.

Conformance testing may include marginals, joints, conditionals, strata, geometry/query coverage, tails, constraints, duplicates/effective sample size, and intended-vs-realized population.

### Confidence

**Very high.**

---

# G12 — Reference failure is not candidate failure

### Preliminary decision: **ACCEPT**

Reference/truth realization needs explicit states for available, uncertain, disagreement, numerical failure, infrastructure failure and non-applicability.

Score-bearing eligibility must follow a registered policy rather than silently treating Carbon's truth failure as candidate incompetence.

### Confidence

**Very high.**

---

# G13 — Censoring and realized evidence population must remain visible

### Preliminary decision: **ACCEPT**

The final valid-evidence population may differ from intended sampling because of reference failures, infrastructure failures, timeouts, invalid cases or measurement non-applicability.

Hard regimes must not silently disappear from the exam.

### Confidence

**Very high.**

---

# G14 — Hierarchical / stratified populations require subgroup evidence where material

### Preliminary decision: **ACCEPT**

Aggregate performance must not hide critical subgroup failure.

Future Challenges may require minimum per-stratum evidence, stratum reporting or stratum-level mandatory gates.

### Confidence

**High.**

---

# G15 — Distribution provenance and uncertainty remain explicit

### Preliminary decision: **ACCEPT**

Telemetry, simulations, expert elicitation, test matrices, requirements and future-use scenarios have different evidentiary status.

The contract/dossier should retain source period, selection, missingness, uncertainty, assumptions and extrapolation where material.

### Confidence

**Very high.**

---

# G16 — Search, stress, product qualification and deployment populations are distinct

### Preliminary decision: **ACCEPT**

```text
search/evaluation population
!=
stress population
!=
product qualification population
!=
deployment population
```

They may overlap but are never automatically interchangeable evidence.

### Confidence

**Very high.**

---

# G17 — Material population changes are versioned, qualified and prospective

### Preliminary decision: **ACCEPT**

Material changes include density, correlation, geometry-family, strata, stress prevalence, query population, exclusions or product-use population.

Required path:

```text
new material semantics
→ new version
→ requalification as required
→ registry binding
→ prospective use
```

No silent historical reinterpretation.

### Confidence

**Very high.**

---

# G18 — Universalize the examination-instance interface, not the physics implementation

### Preliminary decision: **ACCEPT**

Challenge-specific physical generation backends remain appropriate.

Preferred summary:

> **Carbon should not universalize the physics generator. It should universalize what it means to define, sample, generate, and qualify a physical examination case.**

### Confidence

**Very high.**

---

# Consolidated review table

| ID | Decision | Preliminary verdict | Confidence |
|---|---|---|---:|
| G1 | InstanceDistributionContract | ACCEPT | Very high |
| G2 | task owns target population | ACCEPT | Very high |
| G3 | P/Q/weight separation | ACCEPT | Very high |
| G4 | SamplingPlan | ACCEPT ARCH | Very high |
| G5 | CanonicalChallengeCase | ACCEPT ARCH | High |
| G6 | representation preserves physical reality | ACCEPT | Very high |
| G7 | query/observation population | ACCEPT | Very high |
| G8 | generalized role ontology | ACCEPT CONCEPT | High |
| G9 | semantic decontamination beyond seeds | ACCEPT | Very high |
| G10 | 12-part dossier qualification | ACCEPT | Very high |
| G11 | generator conformance separate from truth | ACCEPT | Very high |
| G12 | reference failure ≠ candidate failure | ACCEPT | Very high |
| G13 | censoring visibility | ACCEPT | Very high |
| G14 | hierarchical/stratum evidence | ACCEPT | High |
| G15 | population provenance/uncertainty | ACCEPT | Very high |
| G16 | search/stress/product/deployment separation | ACCEPT | Very high |
| G17 | material-change versioning | ACCEPT | Very high |
| G18 | universal interface, specific physics backend | ACCEPT | Very high |

---

# Decisions intentionally deferred

Acceptance of G1–G18 would **not** settle:

- exact serialization / DSL;
- exact P0 runtime classes;
- exact probability-model representation;
- exact geometry/topology population schema;
- exact statistical tests per distribution family;
- universal power/sample-size thresholds;
- exact duplicate/near-duplicate metric;
- exact sequential-episode runtime API;
- exact representation-adapter API;
- exact reference-status enum;
- private partner distribution transport/storage;
- exact material-change classifier automation;
- any P0 seed derivation change;
- any current Score Pack threshold/weight change.

---

# Tech/science lead review questions

1. Is the P/Q/score-weight separation scientifically correct for Carbon's intended exam design?
2. Should SamplingPlan be a distinct object rather than part of the distribution contract?
3. Is `CanonicalChallengeCase` the right durable abstraction beyond static PDE instances?
4. Which distribution-conformance tests are mandatory for the first Burgers/Poisson implementations?
5. What minimum finite-sample evidence is appropriate for the P0 discrimination claim?
6. Which semantic decontamination constraints are required for P0 versus later geometry/industry Challenges?
7. Are the 12 Validation Dossier evidence classes the right decomposition?
8. Which parts should be preserved as cheap P0 identity/provenance hooks now?

---

# Owner preliminary conclusion

> **Carbon's exam is scientifically defensible only if it can state what physical population is being judged, how finite cases were drawn, whether the generator conformed to that plan, what truth and measurements supported the evidence, and what uncertainty/censoring remains.**

If G1–G18 are accepted, the next architecture layer to review is the **Score Pack**: how qualified measurements over a qualified finite sample become hard admissibility decisions, soft ranking components, estimands, aggregation, uncertainty treatment, and emissions without collapsing scientific meaning into one opaque number.
