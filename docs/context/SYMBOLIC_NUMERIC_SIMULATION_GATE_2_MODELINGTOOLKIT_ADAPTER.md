# Symbolic-Numeric Design Simulation — Gate 2: ModelingToolkit Adapter

**Status:** design-forward simulation; no Julia/ModelingToolkit runtime dependency added.  
**Objective:** Simulate conversion of symbolic-numeric systems into Carbon `PhysicalSystemSpec` / relation IR and identify what scientific identity must survive framework transformations.

## External framework facts used for this simulation

Current ModelingToolkit documentation describes symbolic systems as separable from numerical problems; PDE systems carry equations, boundary conditions, domains, independent/dependent variables and parameters, while discretization converts that mathematical specification into a numerical problem. ModelingToolkit also supports hierarchical composition/namespacing and structural simplification that can eliminate state variables while retaining reconstruction relationships as observed variables.

These framework capabilities are used as pressure tests only. Carbon remains representation-agnostic.

## Proposed adapter boundary

```text
ModelingToolkit system
        ↓
MTK inspection / extraction
        ↓
AdapterReport
  source identity
  supported constructs
  unsupported constructs
  transformations observed
  information-loss warnings
        ↓
PhysicalSystemSpec candidate
        ↓
Carbon structural validator
        ↓
HUMAN SCIENTIFIC REVIEW
```

The adapter is a translator, not an authority.

## Happy-path simulations

### A. Simple Burgers-style PDE

MTK source exposes independent variables, dependent state `u`, parameter `nu`, equations, boundary conditions and domains. Adapter maps these into Carbon declarations + relation IR.

**Result:** straightforward if the source system is inspected before destructive/semantic-changing transformations.

### B. Poisson-style PDE

MTK source exposes `u(x,y)`, domains, BCs and equation structure. A spatially varying coefficient represented as a symbolic function/field must map to Carbon `field`, not scalar `param`.

**Result:** Carbon's `field` extension from Poisson was necessary and sufficient for this case.

## Adversarial / discovery simulations

### C. Structural simplification eliminates a variable

MTK may remove an algebraic state from the solved state vector while retaining it as an observed/reconstructable relation.

If Carbon adapts only the simplified solved state vector, it may lose scientifically meaningful variables and produce a different physical identity from the authored model.

**Discovery:** Carbon must distinguish at least:

- `authored_physical_semantics`;
- `transformed_symbolic_semantics`;
- `numerical_realization_semantics`.

The canonical physical description should normally derive from the reviewed authored/pre-discretization system. Transformations belong in provenance and may have their own artifact identity.

### D. Algebraic equivalence after simplification

MTK may rearrange, substitute, eliminate, factor, or otherwise transform equations while preserving intended mathematical behavior.

Carbon must not use framework-transformed expression bytes as the identity of the original scientific claim.

**Discovery:** source relation provenance must preserve both the source semantic object and any transformation chain. Mathematical equivalence is a claim with provenance, not automatic Carbon identity.

### E. Hierarchical composition / duplicate local symbols

Composed MTK systems namespace subsystem variables. Carbon v0.1 global symbol uniqueness cannot faithfully round-trip a composed system with repeated local names without flattening or renaming.

**Discovery:** the earlier deferred namespace issue is now independently confirmed by a real framework capability. Scoped symbol identity should be promoted from 'likely future' to a required v0.2/composition feature, but not retrofitted into v0.1 Burgers/Poisson.

### F. Parent/global/shared parameters

MTK composition can intentionally share parameters across subsystem scopes. Naive flattening either duplicates one scientific quantity or collapses distinct local quantities.

**Discovery:** future scoped symbols need explicit ownership/scope semantics and alias/shared-identity relations. String renaming alone is insufficient.

### G. Defaults versus scientific domains

Framework parameters may have default values. Carbon Challenge semantics often need admissible ranges/envelopes.

**Discovery:** a framework default is not a Carbon parameter domain, prior, or qualification envelope. Adapter may import a default as provenance metadata only; it must never infer a scientific range from it.

### H. Metadata and units

Framework metadata may contain useful units/descriptions. Carbon cannot assume metadata are complete, authoritative, or public-safe.

**Discovery:** adapter output needs per-field provenance/confidence/origin rather than a single blanket 'imported from MTK' claim. Unit metadata can populate an extension candidate but does not become core authority automatically.

### I. Unsupported symbolic construct

An MTK system contains an operator Carbon IR cannot represent.

**Correct behavior:** fail conversion for the affected relation or emit explicit `UNSUPPORTED`/typed unresolved output. Never stringify the unknown expression and pretend conversion succeeded.

**Discovery:** adapter completeness must be measurable. Every conversion should emit a coverage report: mapped relations/symbols/conditions, dropped/unsupported constructs, and transformations.

### J. Discretized numerical system supplied instead of physical system

A user gives Carbon the output of symbolic discretization / numerical problem conversion rather than the original PDE system.

**Discovery:** Carbon must identify representation level. A discretized stencil/system is numerical-realization provenance, not automatically the canonical physical-system semantics.

### K. Observed variable needed for engineering interpretation

A variable eliminated from numerical states remains meaningful to downstream qualification or product interpretation.

**Discovery:** Carbon's `observed` class is not merely convenience. It can preserve engineering-semantic variables that need not be independent numerical states. This validates keeping `observed` in v0.1 even though Burgers/Poisson barely use it.

## Proposed AdapterReport

Every adapter conversion should return a report separate from the spec:

```text
AdapterReport {
  adapter_name
  adapter_version
  source_framework
  source_framework_version
  source_system_identity?
  representation_level
  transformation_state
  mapped_symbols[]
  mapped_relations[]
  mapped_conditions[]
  unsupported_constructs[]
  dropped_metadata[]
  warnings[]
}
```

This report is provenance/evidence about translation quality. It is not part of physical truth and should not silently modify the semantic identity of the PhysicalSystemSpec.

## New architecture findings

### D-014 — Preserve authored, transformed, and numerical semantic layers separately
**Class:** EXTEND/HARDEN.

A symbolic-numeric framework can legitimately transform a model before numerical execution. Carbon needs to know which representation a statement came from. Canonical physical semantics should not be reconstructed solely from a post-simplification solver representation.

### D-015 — Scoped symbol identity is required for composition
**Class:** EXTEND (future v0.2).

The validator's namespace concern is confirmed by actual compositional modeling behavior. Future component models need stable scoped identities, not ad hoc flattened names.

### D-016 — Shared/aliased scientific quantities require explicit identity relations
**Class:** DEFER/EXTEND.

Multiphysics systems can share parameters/variables across scopes. A future composition model needs alias/shared-identity semantics; do not add to v0.1 until coupled-system gate defines the minimum.

### D-017 — Framework defaults are not scientific envelopes
**Class:** HARDEN.

Never promote default parameter values into Carbon ranges, priors, stress domains, or qualification claims.

### D-018 — Adapter conversion requires explicit coverage/provenance reporting
**Class:** EXTEND.

No adapter should return only a PhysicalSystemSpec. It should also report what was mapped, transformed, unsupported, or dropped. This prevents silent semantic loss.

### D-019 — Representation level is first-class provenance
**Class:** EXTEND/HARDEN.

Carbon must distinguish physical model, symbolic transformed model, discretized model, and numerical realization. They may be related, but they are not interchangeable evidence objects.

### D-020 — Observed variables can preserve engineering semantics across numerical elimination
**Class:** KEEP/HARDEN.

Keep `observed` in the semantic contract. Numerical state minimality must not erase quantities needed for scientific interpretation or qualification.

## Economic/product implication

A robust adapter can lower Challenge-onboarding cost for partners who already possess equation-based models, but the valuable product is not 'we parse ModelingToolkit'. The value is a provenance-preserving bridge from an existing scientific model into Carbon's Challenge/evidence workflow.

This strengthens a possible future partner workflow:

```text
bring existing scientific model
        ↓
semantic import + coverage report
        ↓
scientific review
        ↓
Challenge authoring / dossier work
        ↓
incentivized model-construction search
```

## Gate verdict

**PASS WITH ARCHITECTURE EXTENSIONS.**

Do not implement the adapter yet as a production dependency. The simulation has already earned three design changes for later integration: representation-level provenance, conversion coverage reports, and scoped symbol identity for future composition.
