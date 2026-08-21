# Review These Preliminary Decisions — Distribution / Challenge-Instance Architecture

**Branch:** `design/symbolic-numeric-integration`  
**Status:** owner preliminary decisions; tech/science lead may accept, modify, or reject.  
**Purpose:** Distill the distribution/generator gauntlet into a compact review queue.  
**Scope:** Architecture-level decisions only. These do **not** change current P0 generator wire contracts, seeding rules, scoring, LIVE Challenge semantics, or product qualification until ratified into their domain-owning specifications.

---

# Executive disposition

The distribution gauntlet supports elevating the data/distribution layer to first-class architecture.

Master recommendation:

> **Do not treat the generator as the scientific definition of the task. Define the physical-case distribution explicitly, then qualify a generator implementation against it.**

Review model:

```text
G1  ACCEPT / MODIFY / REJECT
...
G10 ACCEPT / MODIFY / REJECT
```

---

# G1 — Introduce `InstanceDistributionContract`

### Preliminary decision: **ACCEPT**

Create a future versioned scientific object that defines the intended physical-case population for a Challenge.

It should be capable of expressing:

- support / envelope relationship;
- marginal sampling rules;
- joint/conditional dependencies;
- correlations and constraints;
- geometry population;
- BC/IC/forcing populations;
- query/observation population;
- role-specific policies;
- rare/stress sampling;
- exclusions;
- coverage requirements;
- provenance and limitations.

### Why

Envelope bounds alone do not determine the scientific task. A deterministic generator can still concentrate on the wrong regime or generate unrealistic combinations.

### Guardrail

Exact serialization is deferred. Do not make `InstanceDistributionContract` a score or qualification certificate.

### Confidence

**Very high.**

---

# G2 — Ratify the authority rule: scientific task owns distribution; generator implements it

### Preliminary decision: **ACCEPT**

Use the authority chain:

```text
scientific / engineering intent
        ↓
InstanceDistributionContract
        ↓
ChallengeInstanceGenerator
        ↓
Validation Dossier qualification
        ↓
registered LIVE use
```

### Guardrail

Generator code/config cannot silently redefine the intended population.

### Confidence

**Very high.**

---

# G3 — Introduce representation-neutral `CanonicalChallengeInstance`

### Preliminary decision: **ACCEPT AS ARCHITECTURE; DEFER RUNTIME SHAPE**

One sampled physical problem should have a canonical identity upstream of model-family representation.

Conceptually it may bind:

- physical inputs;
- parameters;
- geometry/topology refs;
- initial/boundary conditions;
- forcing/source terms;
- requested observables;
- reference/truth request;
- measurement applicability;
- provenance.

### Why

Mixed model families must not receive subtly different physical realities merely because they consume different representations.

### Guardrail

No P0 requirement to introduce a heavy runtime object where arrays are sufficient.

### Confidence

**Very high.**

---

# G4 — Representation adapters may change encoding, not sampled physical reality

### Preliminary decision: **ACCEPT**

Allow downstream materialization into grids, meshes, graphs, point sets, reduced-basis snapshots, solver configs, or other family-specific forms.

### Constitutional rule

> **Representation conversion cannot silently change the physical instance being graded.**

Lossy/approximate conversion must carry provenance and qualification where material.

### Confidence

**Very high.**

---

# G5 — Generalize long-term roles from `train/eval/stress` to `construction/evaluation/stress/qualification`

### Preliminary decision: **ACCEPT CONCEPTUALLY; DO NOT CHANGE P0 ROLE NAMES YET**

P0 remains:

```text
construction == train
```

Long term, construction access may mean training samples, basis snapshots, calibration data, adaptive truth-query budgets, public symbolic semantics, or no sampled data.

### Why

Non-learned methods and adaptive construction algorithms do not naturally fit a universal "training data" ontology.

### Confidence

**High.**

---

# G6 — Separate generator qualification into integrity, distribution, reference, and task-relevance evidence

### Preliminary decision: **ACCEPT**

Future Validation Dossiers should distinguish:

1. implementation integrity;
2. distribution adequacy;
3. reference/truth adequacy;
4. task relevance.

### Why

"Generator valid" currently risks collapsing different scientific claims.

### Examples

A generator can be reproducible but sample the wrong population. A distribution can be appropriate while its numerical reference is weak. A reference can be excellent while requested outputs fail to measure the intended claim.

### Confidence

**Very high.**

---

# G7 — Treat nominal/workload and stress/consequence distributions as distinct

### Preliminary decision: **ACCEPT**

Rare high-consequence cases may be intentionally oversampled for stress testing without being represented as deployment frequency.

### Guardrail

Score Pack use of stress evidence must remain explicit and registered.

### Confidence

**Very high.**

---

# G8 — Distribution identity becomes part of authoritative experimental provenance

### Preliminary decision: **ACCEPT**

Experiment records / Landscape context should eventually bind the exact distribution identity/version used for construction and evaluation.

### Why

"Same PDE" or "same envelope" does not imply the same scientific task if the sampling measures differ.

### Product implication

Search, qualification and deployment populations must remain distinguishable.

### Confidence

**Very high.**

---

# G9 — Material distribution changes are versioned, qualified and prospective

### Preliminary decision: **ACCEPT**

Landscape, sponsors or protocol owners may propose improved distributions/stress categories, but current LIVE exam semantics cannot mutate silently.

Required path:

```text
proposed distribution change
        ↓
new distribution version
        ↓
qualification evidence
        ↓
registry binding
        ↓
prospective use
```

Historical experiments remain bound to their original distribution version.

### Confidence

**Very high.**

---

# G10 — Universalize the generator interface, not the physics implementation

### Preliminary decision: **ACCEPT**

Carbon should support a universal conceptual interface/invariant set while allowing Challenge-specific generation backends.

Examples:

- analytic PDE generator;
- procedural solver configuration;
- CAD family generator;
- stochastic physical realization;
- partner-controlled instance service;
- experimental campaign sampler;
- coupled-system generator.

### Preferred summary

> **Carbon should not universalize the physics generator. It should universalize what it means to generate a qualified physical examination instance.**

### Confidence

**Very high.**

---

# Consolidated review table

| ID | Decision | Preliminary verdict | Confidence | Scope |
|---|---|---|---:|---|
| G1 | InstanceDistributionContract | ACCEPT | Very high | architecture / future authoring |
| G2 | task owns distribution | ACCEPT | Very high | constitution |
| G3 | CanonicalChallengeInstance | ACCEPT ARCH | Very high | future mixed-family runtime |
| G4 | representation cannot change reality | ACCEPT | Very high | constitution |
| G5 | construction/eval/stress/qualification roles | ACCEPT CONCEPT | High | future role ontology |
| G6 | four-part generator qualification | ACCEPT | Very high | future dossier evolution |
| G7 | nominal vs stress distributions | ACCEPT | Very high | Challenge/scoring design |
| G8 | distribution in experiment provenance | ACCEPT | Very high | Landscape / qualification |
| G9 | distribution changes versioned/prospective | ACCEPT | Very high | governance |
| G10 | universal interface, specific implementation | ACCEPT | Very high | architecture |

---

# Decisions intentionally deferred

Acceptance of G1–G10 would **not** settle:

- exact serialization/schema;
- exact distribution DSL;
- geometry-population representation;
- universal stochastic-process semantics;
- exact correlation/conditional syntax;
- exact coverage metrics by physics family;
- exact sensitivity tests for distribution adequacy;
- production role-name migration;
- exact `CanonicalChallengeInstance` runtime type;
- exact adapter API;
- private partner distribution transport/storage;
- whether distribution artifacts become mandatory for all future Challenge classes;
- any current P0 seed derivation change;
- any current Score Pack threshold/weight change.

---

# Recommended tech/science lead review questions

1. Is a first-class distribution contract scientifically necessary, or can current generator config remain the authority?
2. Should canonical physical instances exist as an explicit future object or only as a conceptual invariant?
3. Is `construction` the right long-term generalization of `train`?
4. Should distribution adequacy become an explicit Validation Dossier section/status?
5. What evidence should be required before claiming a partner workload distribution is representative?
6. Which parts of this architecture are cheap enough to preserve as P0 hooks without introducing runtime complexity?

---

# Owner preliminary conclusion

> **Carbon's scientific credibility depends on qualifying not only the model and not only the generator implementation, but the physical-case distribution the generator is intended to represent.**

The recommended posture is to ratify the architecture now, preserve inexpensive hooks in P0, and defer heavy runtime/schema generalization until mixed-family or industry Challenge requirements make it necessary.
