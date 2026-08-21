# Symbolic-Numeric Design Discovery Ledger

**Branch:** `design/symbolic-numeric-integration`  
**Status:** active design-forward simulation ledger; non-runtime and non-scoring.  
**Purpose:** Capture architecture discoveries surfaced by implementation pressure before updating Carbon's canon, papers, or Summit deck.

## Classification

- **KEEP** — confirms current design.
- **HARDEN** — current concept is right but needs another invariant/boundary.
- **EXTEND** — a new capability has been earned by a concrete design need.
- **REVISE** — an existing design is materially suboptimal.
- **DEFER** — plausible but not yet justified.
- **REJECT** — tempting idea that would weaken Carbon.

## Ledger

Earlier discoveries D-001 through D-055 remain active as recorded in prior revisions. Gate 7 adds:

| ID | Discovery | Source gate | Class | Design consequence | Canon/paper/pitch consequence | Confidence |
|---|---|---|---|---|---|---|
| D-056 | Scoped symbol identity is mandatory for composition-capable semantics. | Multiphysics crash test | EXTEND | Future PhysicalSystemSpec v0.2+ needs stable scope paths/local names; display flattening is noncanonical. | Whitepaper/canon long-term architecture; not stage detail. | Very high |
| D-057 | Shared/aliased quantities need explicit relation semantics. | Multiphysics crash test | EXTEND | Represent same-quantity/interface/derived relationships rather than string flattening. | Technical canon/whitepaper detail. | Very high |
| D-058 | CouplingContract is a first-class physical-semantic object. | Multiphysics crash test | EXTEND | Assembled physical identity includes interface/coupling laws and participants. | Major structured-physics architecture addition. | Very high |
| D-059 | Physical time and numerical execution schedule must remain distinct. | Multiphysics crash test | HARDEN | Solver dt/subcycling/control cadence live in realization/output semantics unless physically claimed. | Scientific provenance detail. | Very high |
| D-060 | Units/dimensional semantics are now earned for composition-capable authoring. | Multiphysics crash test | EXTEND | Support unit/dimension metadata or explicit nondimensionalization; never treat dimensional validity as sufficient physics evidence. | Strong SciML/canon addition; likely whitepaper supporting detail. | Very high |
| D-061 | Geometry/topology/interface regions require referenced semantic context. | Multiphysics crash test | EXTEND/DEFER | Reference content-addressed geometry/coordinate/interface artifacts rather than bloating core schema now. | Long-term engineering-system architecture. | High |
| D-062 | MeasurementContract needs multi-source observables and explicit measurement scope. | Multiphysics crash test | EXTEND | Support component/interface/assembled-system/product-context measurements and qualified mappings. | Major evidence architecture refinement. | Very high |
| D-063 | Component qualification does not compose automatically. | Multiphysics crash test | HARDEN | Require coupling/joint assembled-system evidence; certificates cannot simply be concatenated. | Strong whitepaper/qualification principle. | Very high |
| D-064 | CompatibilityEnvelope is a useful joint-qualification concept. | Multiphysics crash test | EXTEND/DEFER | Track whether subsystem qualified ranges remain mutually compatible under coupling; exact artifact shape deferred. | Potential product/engineering value thesis. | High |
| D-065 | Numerical coupling realization is qualification-relevant provenance. | Multiphysics crash test | HARDEN | Partitioning/synchronization/interpolation/relaxation/solver versions may trigger evidence or requalification consequences. | Scientific/product credibility detail. | Very high |
| D-066 | Physical semantics must support mixed causal/acausal relations. | Multiphysics crash test | EXTEND | Do not force physical composition into a single causal runtime convention. | SciML architecture detail. | High |
| D-067 | ConstructionPolicy replaceable slots must be scoped to component graph. | Multiphysics crash test | HARDEN/EXTEND | Component-level search interventions require stable scoped component identity. | Strengthens model-construction search thesis. | Very high |
| D-068 | Disclosure classification is compositional. | Multiphysics crash test | HARDEN | Controlled subsystem semantics may leak through interfaces/derived outputs; public-wrapper assumption is unsafe. | Important partner/commercial governance issue. | Very high |
| D-069 | Measurement scope is first-class. | Multiphysics crash test | EXTEND | Metric name alone cannot distinguish component/interface/system/product claims. | Strong evidence/whitepaper concept. | Very high |
| D-070 | Assembled physical identity requires a composition manifest/root. | Multiphysics crash test | EXTEND | Bind component semantic identities + CouplingContracts + material context while leaving A3 as byte-integrity authority. | Major architecture addition. | Very high |
| D-071 | Multiphysics Landscape representations should remain hierarchical/graph-aware and empirically justified. | Multiphysics crash test | HARDEN | Avoid flattening/ontology explosion; prospective decision lift remains criterion. | Strengthens physics-intelligence discipline. | Very high |

## Gate 7 promotion decisions

### Earned for future composition architecture

- scoped symbol identity;
- shared/alias relation semantics;
- CouplingContract;
- units/dimensions or explicit nondimensionalization capability;
- measurement scope and multi-source observability;
- assembled composition identity.

### Still deferred

- exact geometry schema;
- exact DAE/index metadata;
- exact CompatibilityEnvelope artifact shape;
- universal connector ontology;
- universal unit system;
- multiphysics Landscape embedding.

### Rejected approaches

- flattened component names as canonical identity;
- automatic composition of subsystem qualification;
- dimensional consistency as proof of physical correctness;
- solver timestep as physical identity by default;
- symbolic composition as proof of numerical adequacy.

## Remaining simulated gates

1. ~~Structural validator execution/hardening.~~ **PASS**
2. ~~ModelingToolkit adapter.~~ **PASS WITH ARCHITECTURE EXTENSIONS**
3. ~~Physics Evaluation Primitive Library.~~ **PASS — MEASUREMENT CONTRACT DISCOVERED**
4. ~~Challenge Compiler / dossier authoring integration.~~ **PASS — MEASUREMENT IDENTITY + EVIDENCE REQUIREMENT**
5. ~~Landscape physical-context integration.~~ **PASS AS TESTABLE INTELLIGENCE ARCHITECTURE**
6. ~~Hybrid model-construction search.~~ **PASS — MODEL-CONSTRUCTION ABSTRACTION EARNED**
7. ~~Coupled/multiphysics crash test.~~ **PASS — COMPOSITION LAYER REQUIRED**
8. Carbon-without-neural-networks test.
9. Final system-level design review.

**Publication rule:** do not edit the canon/papers/deck from individual speculative findings. Complete the discovery simulation first, then integrate the stable findings in one reconciled pass.
