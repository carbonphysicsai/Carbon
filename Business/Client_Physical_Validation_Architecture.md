# Carbon Client Physical Validation Architecture v1

**Status:** OWNER-CANONICAL strategic architecture.  
**Decision date:** 2026-08-31.  
**Owner:** Founders; scientific semantics owned by Science & Research.  
**Implementation status:** strategic architecture only; explicitly outside the current development chain.  
**Purpose:** define where physical experimental validation belongs in Carbon's product and scientific architecture without expanding the current subnet Challenge or Wave-B implementation scope.

---

# 1. Founder decision

Carbon will keep physical experimental validation outside the default subnet discovery, Challenge evaluation, ranking, and frontier loop.

The subnet and core discovery/evidence system may first establish computational evidence against a qualified computational reference. A model that earns enough evidence to justify the cost and consequence of physical testing may then advance into a separate **Carbon + Client Product Battery / physical-validation program** tied to the client's exact physical system and intended engineering use.

Canon law:

> **Carbon uses computational evidence to determine which fast physical models are worth advancing to expensive physical validation. Physical validation is a downstream Carbon + Client Product Battery activity tied to the client's exact engineering use, not a default authority inside the subnet discovery exam.**

A model being worth physical validation does not mean Carbon has already established physical validity.

---

# 2. Authority boundary

Default architecture:

```text
SUBNET / DISCOVERY + COMPUTATIONAL EVIDENCE
qualified computational problem
        ↓
construction-method discovery
        ↓
producer-independent reconstruction
        ↓
protected evaluation
        ↓
qualified computational reference evidence
        ↓
candidate earns sufficient evidence to justify further investment
        ↓
WORTH ADVANCING TO PHYSICAL VALIDATION

CARBON + CLIENT PRODUCT BATTERY
exact intended engineering use
        ↓
client physical system / test article
        ↓
qualified experimental observations
        ↓
solver ↔ experiment evidence
surrogate ↔ experiment evidence
        ↓
discrepancy / uncertainty / limitations
        ↓
bounded Product Qualification decision
        ↓
deployment / lifecycle where supported
```

The following claims remain distinct:

```text
COMPUTATIONAL CLAIM
The artifact or construction method survives the registered computational evidence program.

PHYSICAL-VALIDATION CLAIM
Qualified experimental evidence supports the relevant model chain within a stated physical context.

PRODUCT-QUALIFICATION CLAIM
The combined evidence supports this exact artifact/system for this exact engineering use, subject to stated limitations and escalation rules.
```

Evidence for one claim does not silently establish another.

---

# 3. Evidence Audit boundary

The Carbon Evidence Audit remains the preferred first commercial wedge. This decision does not redefine the minimum Audit to require a physical test campaign.

An Evidence Audit may establish what the existing qualified evidence supports, including computational-reference evidence, failure strata, limitations, and the next evidence required.

Where the Audit or discovery program identifies a candidate that merits stronger job-shaped evidence, the account may expand into a Product Battery / Qualified Model Program. Physical experimental validation enters there when the intended use requires it.

Default commercial progression:

```text
Evidence Audit / Sponsored Discovery
        ↓
computationally credible candidate
        ↓
Product Battery
        ↓
Carbon + Client physical validation where required
        ↓
bounded Qualification Record
        ↓
Lifecycle / requalification
```

A customer may enter at another point where the evidence state and product need justify it.

---

# 4. Carbon + Client responsibility model

Carbon does not need to become the owner or operator of every physical test facility.

The client or an authorized third party may own or operate:

- the physical system and test article;
- wind tunnel, rig, bench, laboratory, field test, or other facility;
- instrumentation and calibration systems;
- test execution and safety authority;
- proprietary operating conditions and physical data;
- domain-specific engineering acceptance authority.

Carbon's intended role is to own or co-author, subject to scientific authority and contract:

- the exact model/artifact identity under evaluation;
- context-of-use and claim definition;
- evidence-plan structure;
- separation of calibration/construction evidence from protected validation evidence;
- provenance and evidence identity;
- comparison and discrepancy analysis;
- uncertainty/dependence treatment appropriate to the claim;
- evidence boundary, limitations, and answerability/escalation logic;
- Product Battery record and bounded qualification recommendation/record under the applicable authority.

Customer payment, test ownership, or facility authority cannot alter the scientific meaning of the evidence.

---

# 5. Experimental evidence doctrine

Physical observations are not treated as anonymous or automatically perfect ground truth.

Where material to the claim, Carbon should preserve the identity and adequacy of:

- test article / physical-system configuration;
- operating and boundary conditions;
- instrumentation;
- calibration;
- acquisition procedure;
- preprocessing / data reduction;
- repeatability;
- measurement uncertainty;
- mapping between measured and modeled quantities;
- representation differences between test and intended use;
- rights, confidentiality, and disclosure class.

Preferred terminology distinguishes:

```text
COMPUTATIONAL REFERENCE
qualified numerical/solver reference for a registered computational claim

EXPERIMENTAL OBSERVATION
qualified measurement of a physical system

PHYSICAL VALIDATION EVIDENCE
registered comparison between model prediction and qualified experimental observation
```

Use `ground truth` only where the scientific context warrants that stronger term.

---

# 6. Calibration and protected physical validation

Carbon should preserve distinct evidence roles where experiments participate in model development:

```text
CONSTRUCTION / CALIBRATION EVIDENCE
may influence model construction or tuning

EXAM / BATTERY DESIGN EVIDENCE
may influence prospective evidence design and qualification

PROTECTED PHYSICAL VALIDATION EVIDENCE
reserved for independent evaluation of the registered physical claim

LIFECYCLE EVIDENCE
new observations generated after deployment or change
```

A physical dataset used to tune a model does not become independent validation evidence merely because it came from an experiment.

---

# 7. Advancement into physical validation

`WORTH_ADVANCING_TO_PHYSICAL_VALIDATION` is a future evidence/investment decision state, not a physical qualification state.

The advancement decision should eventually consider, as applicable:

- computational evidence strength;
- reference-solver qualification and known limitations;
- relevance to a valuable client use case;
- unresolved failure strata;
- expected information value of physical testing;
- test cost, time, safety, and feasibility;
- consequence of model error;
- availability and quality of existing experimental evidence;
- whether the proposed physical test can resolve the decision Carbon and the client care about.

Exact thresholds and decision procedures are **not established by this document**. They require later Science & Research design and prospective qualification.

---

# 8. Prospective re-entry into discovery

Physical-validation results may create new scientific questions and later re-enter Carbon discovery **prospectively**.

Example:

```text
Product Battery identifies physical discrepancy
        ↓
Science & Research determines whether the discrepancy supports a new scientific problem
        ↓
new Challenge / new reference architecture / new model-construction objective
        ↓
prospectively qualified discovery program
```

Potential future architectures include hybrid multi-fidelity references, experiment-anchored discrepancy models, corrected computational references, or discovery over model-form correction itself.

Canon law:

> **Physical evidence may inform future discovery prospectively. It does not retroactively rewrite a completed Challenge, frontier event, score, or computational evidence record.**

Experimental or hybrid truth may enter a future Challenge only after its scientific authority, measurement, population, secrecy, statistical, and qualification requirements have been designed and qualified for that Challenge. This document does not authorize such a runtime mode today.

---

# 9. Development-chain boundary

This founder decision creates **no current Wave-B implementation requirement**.

It does not expand or modify the active implementation scope of:

- Challenge authoring;
- generator construction/qualification;
- reference-solver implementation;
- measurement / Score Pack work;
- miner research;
- validator execution;
- frontier promotion;
- settlement;
- current network runtime.

Near-term development should continue to solve the already-hard problem of a qualified computational exam and producer-independent evidence without importing client experimental-validation complexity into that loop.

Future implementation work belongs to the Product Battery / Product Qualification plane after the relevant scientific contracts and customer need justify it.

---

# 10. Strategic rationale

The architecture creates an evidence funnel:

```text
MANY CONSTRUCTION METHODS
        ↓
discovery

FEWER COMPUTATIONALLY CREDIBLE CANDIDATES
        ↓
qualified computational evidence

VERY FEW PHYSICAL-VALIDATION CANDIDATES
        ↓
Carbon + Client Product Battery

BOUNDED PHYSICAL USE
        ↓
Product Qualification where earned
```

This structure protects three things:

1. **Subnet tractability.** Carbon does not make sparse, heterogeneous, client-specific physical experiments a default dependency of the discovery exam.
2. **Scientific claim discipline.** Solver-relative evidence cannot masquerade as physical validation, and physical validation cannot automatically become product qualification.
3. **Commercial expansion.** Carbon can land with an Evidence Audit or discovery program, then justify higher-value physical qualification work only for candidates that merit the investment.

---

# 11. Strategic hypotheses to test later

The following are hypotheses, not Carbon evidence:

1. Carbon's computational evidence can select candidates that survive expensive physical validation at a higher rate than credible alternative selection workflows.
2. The computational-to-physical evidence relationship can become a useful qualification-prioritization signal.
3. Carbon can identify physical experiments that reduce engineering decision uncertainty more efficiently than credible baseline experiment-allocation methods.
4. Rights-permitted computational-to-physical evidence can become a defensible input to future Physics Intelligence.

These hypotheses require prospective experiments. Architecture alone does not establish them.

---

# 12. Risks and controls

## Risk — Carbon remains solver-relative

If Carbon never closes the physical loop where the intended engineering use requires it, customers may reasonably treat Carbon as computational benchmarking infrastructure rather than engineering evidence infrastructure.

**Control:** Product Qualification must state its truth/evidence authority and require physical evidence when the registered use requires it.

## Risk — physical validation contaminates discovery

Client-specific test evidence could make Challenge authoring, secrecy, statistics, and reference qualification unmanageably complex.

**Control:** keep physical validation downstream by default; re-enter discovery only through a new prospectively authored and qualified Challenge.

## Risk — Carbon becomes a bespoke test consultancy

Physical programs could create facility-specific expert work that does not scale.

**Control:** Carbon owns reusable evidence architecture, provenance, Product Battery semantics, adapters, and qualification workflows rather than assuming it must own physical test execution.

## Risk — experimental observations are treated as infallible truth

Instrumentation, test representation, preprocessing, and measurement uncertainty can distort the physical evidence.

**Control:** qualify experimental observations and preserve their uncertainty, provenance, applicability, and limitations.

---

# 13. Dependencies

Future implementation depends on maturity in the relevant scientific owners, including:

- reference/truth qualification;
- measurement qualification;
- Validation Dossier / evidence sufficiency;
- Product Battery semantics;
- Product Qualification;
- privacy, rights, and customer-controlled truth interfaces;
- lifecycle/requalification.

This architecture must not be used to pull those future layers into the current development chain ahead of their gates.

---

# 14. Affected company architecture

This decision informs:

- Carbon Evidence Audit expansion logic;
- Qualified Model Program;
- Product Battery;
- Product Qualification;
- Model Lifecycle;
- experimental/test-system integrations;
- future experiment allocation and Physics Intelligence;
- future hybrid multi-fidelity Challenge design where independently justified.

It does not change the company identity:

> **Carbon is building the discovery, evidence, and qualification infrastructure for fast physical models.**

It sharpens the boundary between discovering a computationally credible model and earning the right to use that model against a real physical engineering decision.
