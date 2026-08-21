# Symbolic-Numeric Design Simulation — Gate 7: Coupled / Multiphysics Crash Test

**Status:** design-forward crash test; no P0/runtime changes.  
**Objective:** Intentionally stress the emerging Carbon semantic/evidence architecture with hierarchical components, shared variables, interface laws, algebraic constraints, mixed time scales, multiple solvers, and partial learned replacement.

## Crash-test system

Use a deliberately demanding hypothetical system rather than pretending it is a current Carbon Challenge:

```text
fluid subsystem
  pressure p_f, velocity u_f, temperature T_f
       ↕ interface: heat + force transfer
thermal subsystem
  temperature T_s, heat flux q_s
       ↕ thermal expansion / material properties
structural subsystem
  displacement d_s, stress sigma_s
       ↕ actuator / sensor interface
controller subsystem
  sensor y, command a
```

Possible candidate construction:

```text
fluid reduced model + learned closure
        ↕
thermal mechanistic model
        ↕
structural surrogate
        ↕
controller
```

The purpose is to see which previously deferred concepts are now unavoidable.

## External symbolic-numeric pressure test

Modern compositional symbolic systems support hierarchical subsystems, scoped variables/parameters, shared/parent/global quantities, and connector equations. Acausal component composition can generate differential-algebraic systems whose connection laws are part of the model. Unit validation is also available in current symbolic-numeric tooling.

Carbon should consume these ideas without adopting any framework as protocol authority.

## Crash 1 — global symbol uniqueness fails

Fluid and structure both use `T`, `p`, `u`, or similarly common names. Flattening to globally unique strings either invents names or loses component identity.

**Verdict:** the previously deferred namespace feature is now mandatory for composition-capable `PhysicalSystemSpec` v0.2+.

Provisional identity:

```text
SymbolRef {
  scope_path: ["fluid", "boundary_layer"]
  local_name: "T"
}
```

Display names may flatten; semantic identity must not depend on display flattening.

## Crash 2 — shared quantities / aliases

At an interface, two subsystem-local names may represent the same physical quantity or be related by an interface law. A shared ambient parameter may intentionally belong to a parent/global scope.

String equality is insufficient.

**Verdict:** promote explicit relationship semantics:

```text
SymbolRelation {
  relation_type: same_quantity | interface_relation | derived_from
  refs[]
  relation_ref?
}
```

Do not equate `same_quantity` with `equal_value_at_all_times` unless the physical relation actually says so.

## Crash 3 — coupling is itself scientific semantics

A multiphysics system is not just a bag of subsystem equations. The interface/coupling laws define the assembled physical system:

- temperature continuity / heat-flux balance;
- traction/force transfer;
- sensor/actuator mapping;
- conservation across interfaces;
- contact or constitutive relations.

**Verdict:** introduce a first-class `CouplingContract` concept rather than hiding interface laws inside generic provenance.

```text
CouplingContract {
  coupling_id
  participant_scopes[]
  semantic_relations[]
  directionality: acausal | causal | mixed
  interface_variables[]
  assumptions[]
  applicability
  provenance
}
```

This is descriptive physical semantics, not score authority.

## Crash 4 — DAE / algebraic constraints

Component composition can produce differential-algebraic systems. Carbon v0.1 relation IR can represent equalities but its system metadata and authoring assumptions are PDE-oriented.

**Verdict:** `system_class` must eventually admit DAE/algebraic/hybrid composition without pretending every state has an explicit time derivative. Structural index, solvability, and consistent initialization remain numerical/scientific evidence, not generic schema truth.

No universal DAE solver semantics are promoted into core.

## Crash 5 — multiple time scales and clocks

Controller may run at a discrete control rate while fluid/thermal/structural dynamics evolve on different numerical time scales. A single independent variable `t` is not enough to describe execution semantics.

**Verdict:** distinguish **physical time semantics** from **numerical/execution schedules**.

PhysicalSystemSpec may share a physical time coordinate; numerical realization provenance owns solver steps/subcycling. CandidateOutputContract owns query/update cadence exposed to evaluation. Do not put solver `dt` into physical identity unless it is itself part of the claimed system.

## Crash 6 — units become necessary

Cross-domain coupling makes dimensional mistakes materially easier: heat flux, temperature, stress, displacement, force, control signals and geometric scales interact.

Unlike normalized Burgers, this system demonstrates a real need for units/dimensions in semantic authoring.

**Verdict:** promote **unit/dimension metadata capability** for composition-capable schema, but retain two boundaries:

1. unit consistency is structural/scientific lint, not proof the physical model is correct;
2. normalized/dimensionless Challenges may explicitly declare a nondimensionalization contract instead of fabricated SI units.

Earned object:

```text
DimensionalSemantics {
  quantity_ref
  unit_or_dimension
  basis/system
  source
}
```

and for nondimensional systems:

```text
NondimensionalizationContract {
  reference_scales[]
  mapping
  applicability
  provenance
}
```

## Crash 7 — geometry/topology is not optional forever

Fluid-structure and thermal interfaces depend on where components meet, mesh/geometry mappings, coordinate frames, and possibly moving boundaries.

A scalar `spatial_dimension=3` cannot describe this.

**Verdict:** geometry/topology deserves a future referenced artifact/extension, not immediate bloating of PhysicalSystemSpec core.

Provisional:

```text
GeometryContextRef
CoordinateFrameRef
InterfaceRegionRef
```

Exact geometry bytes belong in content-addressed artifacts; semantic spec references them.

## Crash 8 — interface measurements require coupled observability

A heat-balance measurement may require values from both fluid and solid sides. A traction-continuity measurement may require mapped interface quantities.

**Verdict:** MeasurementContract must support multi-source observables and explicit mapping/alignment operations. CandidateOutputContract for a mixed-family Challenge must guarantee the required interface observables or provide a qualified evaluator-side derivation.

This is a direct extension of Gate 6 comparability.

## Crash 9 — subsystem passes, assembled system fails

Each subsystem can independently satisfy its local metrics while the coupled model violates interface energy balance or becomes unstable.

**Verdict:** qualification/evaluation must support **hierarchical evidence**:

```text
component evidence
+ coupling/interface evidence
+ assembled-system evidence
```

Passing components does not imply passing composition.

This is the multiphysics analogue of 'no layer certifies itself'.

## Crash 10 — one learned component changes another subsystem's validity

A learned fluid closure shifts loads on the structure outside the structural surrogate's qualified envelope.

**Verdict:** qualification envelopes are compositional only with explicit proof. The assembled system needs a **CompatibilityEnvelope** / interface compatibility check; subsystem certificates cannot simply be concatenated.

Provisional concept:

```text
CompatibilityEnvelope {
  participant_qualification_refs[]
  interface_variable_ranges
  coupling_assumptions
  joint_stress_evidence_refs[]
}
```

Do not assume this becomes a standalone protocol artifact until product design earns it.

## Crash 11 — solver choice can alter coupled behavior

Partitioned vs monolithic coupling, interpolation, relaxation, time synchronization, and convergence tolerances can materially affect the assembled result.

**Verdict:** numerical coupling realization is first-class provenance and may be qualification-relevant. It is not part of the authored physical relation unless scientifically intended.

This confirms Gate 2's representation-level separation at a harder scale.

## Crash 12 — causal controller + acausal plant

The plant may be represented acausally while the controller has explicit signal direction.

**Verdict:** Carbon must not impose one global causality convention on physical semantics. CouplingContract needs causal/acausal/mixed relation typing. Candidate runtime interface may be causal even when underlying physical composition is acausal.

## Crash 13 — component replacement search

Miner replaces only the structural surrogate while fluid/thermal components remain fixed.

**Verdict:** Gate 6 `ConstructionPolicy` needs **replaceable component slots scoped to the component graph**. This is exactly where scoped identities and fixed/trainable component hashes become operationally necessary.

## Crash 14 — hidden partner subsystem

One proprietary subsystem is controlled/private while the rest is public.

**Verdict:** disclosure classification must be compositional too. Public scientific semantics cannot accidentally reveal a controlled subsystem through aliases, interface ranges, generated diagnostics, or Landscape outputs. A public Challenge may be impossible if meaningful evaluation cannot remain auditable without exposing the proprietary core.

## Crash 15 — dimensional correctness becomes a Goodhart target

A model can be dimensionally consistent and physically useless.

**Verdict:** dimensional consistency is a useful authoring/gate candidate in appropriate systems but never sufficient physics evidence. It belongs below substantive physical measurements in epistemic authority.

## Crash 16 — local versus global conservation

Each component may conserve locally while interface transfer is wrong; conversely numerical partitioning may create small local imbalances while global behavior remains acceptable.

**Verdict:** MeasurementContract needs explicit **measurement scope**:

```text
component | interface | assembled_system | product_context
```

Do not infer scope from metric name.

## Crash 17 — composition versioning

Changing one subsystem or coupling relation changes the assembled system even if all other artifact hashes are stable.

**Verdict:** assembled physical-system identity needs a **composition manifest/root identity** binding:

- component semantic identities;
- CouplingContract identities;
- geometry/context refs where material;
- authored assumptions.

Likewise, assembled FastPhysicalModel identity binds its candidate component graph.

This is Merkle-like conceptually but no hashing format is ratified here; A3 remains byte-binding authority for registered artifacts.

## Crash 18 — physical context explodes combinatorially

Landscape could encode every component, interface, unit, geometry feature, solver and regime, creating sparse high-dimensional metadata.

**Verdict:** do not flatten multiphysics semantics into one giant feature vector by default. ContextFeatureSet should support hierarchical/graph-derived representations and must still earn value by prospective decision lift.

## New architecture discoveries

### D-056 — Scoped symbol identity is now mandatory for composition-capable semantics
**Class:** EXTEND.

Promote the previously deferred namespace requirement to future PhysicalSystemSpec v0.2+.

### D-057 — Shared/aliased quantities need explicit relation semantics
**Class:** EXTEND.

Promote alias/shared-identity handling from deferred to required for composition.

### D-058 — CouplingContract is a first-class physical-semantic object
**Class:** EXTEND.

Multiphysics identity includes interface/coupling laws, not only component equations.

### D-059 — Physical time and numerical execution schedule must remain distinct
**Class:** HARDEN.

Subcycling/control cadence/solver dt belong to realization/output contracts unless part of the physical claim.

### D-060 — Units/dimensional semantics are earned for composition-capable authoring
**Class:** EXTEND.

Support unit/dimension metadata or explicit nondimensionalization; dimensional validity remains bounded structural evidence.

### D-061 — Geometry/topology/interface regions need referenced semantic context
**Class:** EXTEND/DEFER.

Do not inline arbitrary geometry into core schema; use content-addressed referenced artifacts/contexts.

### D-062 — MeasurementContract needs multi-source observables and explicit scope
**Class:** EXTEND.

Support component/interface/assembled-system measurements and qualified mappings.

### D-063 — Component qualification does not compose automatically
**Class:** HARDEN.

Assembled systems require coupling and joint evidence; certificates cannot be concatenated.

### D-064 — CompatibilityEnvelope is a useful product/scientific concept
**Class:** EXTEND/DEFER.

Joint operation requires evidence that subsystem qualified envelopes remain mutually compatible under coupling.

### D-065 — Numerical coupling realization is qualification-relevant provenance
**Class:** HARDEN.

Partitioning, synchronization, interpolation, relaxation and solver versions may materially affect evidence.

### D-066 — Carbon physical semantics must support mixed causal/acausal relations
**Class:** EXTEND.

Do not force physical composition into the causal runtime interface model.

### D-067 — ConstructionPolicy replaceable slots must be scoped to the component graph
**Class:** HARDEN/EXTEND.

Hybrid search becomes component-level scientific intervention in coupled systems.

### D-068 — Disclosure classification is compositional
**Class:** HARDEN.

A public wrapper around a controlled subsystem can still leak protected scientific semantics through interfaces/derived outputs.

### D-069 — Measurement scope is first-class
**Class:** EXTEND.

The same named property can apply at component, interface, assembled-system, or product-context level.

### D-070 — Assembled physical identity requires a composition manifest/root
**Class:** EXTEND.

Bind component semantic identities + coupling identities + material context without replacing A3's byte-integrity authority.

### D-071 — Multiphysics Landscape representations should remain hierarchical/graph-aware and empirically justified
**Class:** HARDEN.

Avoid premature flattening/ontology explosion; prospective decision lift remains the criterion.

## Effect on earlier decisions

### Promote now in future architecture

- scoped symbol identity;
- shared/alias relation semantics;
- CouplingContract;
- unit/dimension or nondimensionalization capability;
- measurement scope + multi-source observability;
- composition identity.

### Keep deferred

- exact geometry schema;
- exact DAE/index metadata;
- exact CompatibilityEnvelope artifact shape;
- universal connector ontology;
- universal unit system;
- multiphysics Landscape embedding.

### Explicitly reject

- flattening component names into strings as canonical identity;
- assuming component certificates compose;
- treating dimensional consistency as physics correctness;
- putting solver time step into physical identity by default;
- assuming symbolic composition determines numerical adequacy.

## Scientific implication

The PhysicalSystemSpec abstraction survives the crash test, but **single-system v0.1 is not enough for composition**. The right extension is not a giant universal equation schema. It is a small set of composition primitives around the existing core:

```text
component PhysicalSystemSpecs
        +
scoped identities
        +
CouplingContracts
        +
material geometry/context refs
        ↓
composition manifest / assembled PhysicalSystemSpec identity
```

This keeps component science modular while making the assembled scientific claim explicit.

## Commercial implication

This architecture maps much better to real engineering systems than a monolithic surrogate story. A partner could eventually expose a system as components, choose which components Carbon may optimize, preserve fixed/proprietary components where governance allows, and qualify the assembled fast model under explicit interface evidence.

The opportunity is potentially larger than 'train a surrogate for one PDE':

> **Carbon can become an experimental system for deciding where learned acceleration belongs inside a larger physical system, and whether the resulting composition remains credible.**

That is a candidate strategic thesis, not yet a stage claim.

## Gate verdict

**PASS — WITH A REQUIRED COMPOSITION LAYER FOR FUTURE MULTIPHYSICS.**

The architecture did not collapse. It earned scoped identity, CouplingContract, dimensional/nondimensional semantics, hierarchical measurement scope, composition identity, and non-compositional qualification as future requirements.

Proceed to Gate 8: Carbon-without-neural-networks. The test is now stronger: remove learned models entirely and ask whether Carbon still has a coherent scientific/economic object when competitors submit reduced, symbolic, numerical, or transformed fast physical models.
