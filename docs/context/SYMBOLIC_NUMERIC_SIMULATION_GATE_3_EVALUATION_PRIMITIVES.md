# Symbolic-Numeric Design Simulation — Gate 3: Physics Evaluation Primitive Library

**Status:** design-forward simulation; no score/gate changes.  
**Objective:** Simulate turning structured physical semantics into candidate diagnostics while preserving Carbon's dossier/Score-Pack authority chain.

## Proposed primitive pipeline

```text
PhysicalSystemSpec
      ↓ semantic relation/condition
Primitive proposer
      ↓ candidate definition + requirements
Numerical realization binding
      ↓ implementation
Reference/calibration experiments
      ↓ Validation Dossier evidence
Qualified Metric Definition
      ↓ optional Score Pack registration
ScoreEngine
```

A primitive is an authoring candidate, not a score.

## Primitive classes simulated

1. governing-equation residual candidate;
2. conservation/invariant candidate;
3. boundary/initial-condition consistency candidate;
4. admissibility/inequality candidate;
5. dimensional-consistency authoring check;
6. manufactured-solution/reference consistency candidate;
7. regime-feature extractor.

## Burgers simulation

### Full governing-equation residual
From:

```text
u_t + u*u_x - nu*u_xx = 0
```

a proposer can construct a symbolic candidate residual expression.

But the current Carbon P0 model outputs only final-time state. It does not supply a trajectory from which `u_t` can be directly evaluated.

**Discovery:** primitive feasibility depends on the model output contract and available evidence, not only on the physical equation. A mathematically valid diagnostic may be **unobservable** from the candidate artifact's interface.

Correct outcomes include:

- require richer model output/trajectory;
- use an independently justified approximation;
- classify a reduced proxy honestly;
- do not offer the primitive for this Challenge.

The existing final-state spatial-balance proxy demonstrates why this distinction matters.

### Mean conservation candidate
Periodic Burgers supports a physically motivated integral/mean relationship under the intended model, but numerical evaluation requires choices about quadrature/grid weighting, normalization, precision, and reference floor.

**Discovery:** even apparently simple invariants need a `MeasurementContract` before they can become evidence.

## Poisson simulation

### PDE residual
For `-div(k grad u)=f`, a residual can be proposed, but implementation differs across:

- strong-form pointwise derivatives;
- weak-form/integral residuals;
- finite-difference stencil residuals;
- FEM residuals;
- irregular meshes/geometries.

**Discovery:** 'PDE residual' is not one metric. The numerical form is part of the metric identity.

### Dirichlet boundary consistency
A boundary condition can propose `|u-g|` on the registered boundary. But the metric still requires boundary sampling, norm/aggregation, mesh handling, and tolerance calibration.

### Manufactured solution
A manufactured analytic solution is useful for generator/reference validation, but using it as a general model metric can accidentally evaluate memorization of one reference case rather than the intended operator family.

**Discovery:** generator-validation primitives and candidate-model evaluation primitives are different evidence roles and should be typed separately.

## Adversarial simulations

### A. Metric gaming
A miner can optimize a known residual/proxy while degrading true engineering usefulness.

**Decision:** primitive provenance must include intended failure mode and known gaming risk; protected stress/evaluation diversity remains necessary. No single generated primitive becomes the objective by default.

### B. Numerically noisy derivative
High-order derivatives amplify discretization/noise and can dominate residuals.

**Decision:** every numerical primitive needs uncertainty/reference-floor characterization before thresholding.

### C. Physically valid relation outside its assumptions
A conservation/admissibility property may hold only under particular BCs, source terms, constitutive assumptions, or regimes.

**Decision:** primitive applicability must bind to explicit assumptions/physical-system version, not only a generic physics-family label.

### D. Equivalent physical relation, different discretization
Two implementations compute different residual magnitudes from the same relation.

**Decision:** metric identity includes numerical measurement method/version. Relation identity alone is insufficient.

### E. Candidate diagnostic leaks protected exam construction
Automatically publishing stress-specific regime features or sampling details could increase evaluation information leakage.

**Decision:** primitive definition and realized exam instantiation have separate disclosure classes. Public scientific definition does not imply public realized sampling.

### F. Derived dimensionless group
A symbolic system plus units/parameters may allow computation of Reynolds/Peclet/etc. But the scientifically meaningful group depends on characteristic scales and assumptions that may not be inferable automatically.

**Decision:** dimensionless-group generation is candidate authoring assistance, not automatic truth. Characteristic-scale provenance is required.

## Earned design object: MeasurementContract

The simulation reveals a missing intermediate object between physical relation and Score Pack.

```text
MeasurementContract {
  measurement_id
  semantic_source_refs[]
  evidence_role
  applicability
  required_candidate_outputs
  numerical_method
  discretization_or_sampling
  normalization
  aggregation
  precision
  uncertainty_or_reference_floor
  known_limitations[]
  disclosure_class
  implementation_version
  validation_evidence_refs[]
}
```

This is not necessarily a new protocol artifact yet. It is a design concept capturing the fact that **measurement semantics are richer than the symbolic relation and narrower than the Score Pack**.

## New architecture discoveries

### D-021 — Diagnostic observability is a first-class constraint
**Class:** EXTEND/HARDEN.

A physical property may be mathematically definable but not measurable from the candidate model's output contract. Evaluation design must bind property -> required observables -> measurement method.

### D-022 — Measurement identity includes numerical method
**Class:** EXTEND.

A relation-derived metric is not fully defined until discretization/sampling, normalization, aggregation, precision, and implementation version are specified.

### D-023 — Introduce a MeasurementContract concept between semantics and scoring
**Class:** EXTEND.

This provides traceability:

```text
physical relation/condition
  -> MeasurementContract
  -> validation/calibration evidence
  -> Score Pack metric/gate
```

It may begin as dossier schema rather than a standalone registry artifact.

### D-024 — Evidence role must be typed
**Class:** HARDEN/EXTEND.

Distinguish at least:

- generator/reference validation measurement;
- candidate-model evaluation measurement;
- product-qualification measurement;
- Landscape descriptive feature.

The same mathematical quantity may be used differently, but authority and disclosure differ.

### D-025 — Primitive applicability binds to assumptions and physical-system version
**Class:** HARDEN.

Never attach a generic 'conservation metric' to a physics family without BC/source/regime assumptions.

### D-026 — Generated diagnostics create a new Goodhart surface
**Class:** HARDEN.

Making physics machine-readable can make it easier for optimizers to target proxies. Carbon's protected evaluation, diverse stress cases, hard vetoes, and independent evidence become more important, not less.

### D-027 — Dimensionless features require characteristic-scale provenance
**Class:** DEFER/HARDEN.

Do not auto-generate Reynolds/Peclet/etc. merely from symbol names/units. Record how scales are chosen and qualify the feature before Landscape relies on it.

## Commercial/economic implication

This gate strengthens the future **Challenge Compiler** opportunity. A structured physical model can generate a *candidate evaluation plan*, not an authoritative exam. That can still reduce scientific-authoring cost substantially by producing:

- candidate diagnostics;
- required observables;
- missing-evidence checklist;
- dossier scaffolding;
- known assumptions/limitations.

The valuable product is therefore not 'automatic physics verification'. It is **evidence-aware scientific test authoring**.

## Gate verdict

**PASS WITH A MAJOR DESIGN DISCOVERY: MeasurementContract.**

Do not add generated primitives directly to scoring. Carry the new concept into Gate 4, where we simulate the Challenge Compiler / Validation Dossier workflow and decide whether MeasurementContract belongs in the dossier, Score Pack metadata, or as its own versioned artifact.
