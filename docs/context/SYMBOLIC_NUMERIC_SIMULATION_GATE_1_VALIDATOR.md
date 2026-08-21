# Symbolic-Numeric Design Simulation — Gate 1: Structural Validator

**Status:** design-forward simulation; no P0 runtime integration.  
**Inputs:** PhysicalSystemSpec v0.1 candidate, Burgers prototype, Poisson prototype, validator design/reference code/tests.

## Objective

Simulate the validator as if it were being hardened for authoring use and identify architecture discoveries before proceeding to a symbolic-framework adapter.

## Happy-path simulations

### Evolutionary PDE
A declared `u(x,t)`, scalar `nu`, and relation `d_t(u)=nu*d_xx(u)` is structurally expressible and valid.

### Elliptic PDE with fields
A declared `u(x,y)`, coefficient field `k(x,y)`, source field `f(x,y)`, and explicit derivative representation of `-div(k grad u)=f` is structurally expressible without adding convenience operators.

**Finding:** Burgers + Poisson remain representable with the same small core plus the earned `field` leaf.

## Adversarial simulations

### A. Undeclared symbols
A relation references `v` when only `u` exists.

Expected: fail structurally. This is mechanical and does not require physics authority.

### B. Undeclared derivative axis
`partial(u,wrt=z)` when only `x,t` are declared.

Expected: fail structurally.

### C. Plausible but wrong physics
A perfectly well-formed equation uses the wrong sign or coefficient.

Expected: PASS structural validation. Scientific review/dossier must reject it if wrong.

**Discovery:** a passing structural validator must never be presented as 'validated physics'. Naming/UI/API language matters as much as code authority.

### D. Algebraically equivalent representations
`u_t + u*u_x = nu*u_xx` versus `u_t + u*u_x - nu*u_xx = 0`.

Expected: both may validate; no automatic equivalence is inferred.

**Discovery:** semantic identity and mathematical equivalence must remain separate. A future normalizer can aid authoring but must not rewrite historical registered identity.

### E. Unsupported future construct
A coupled/tensor/integral/stochastic operator appears.

Expected: core validator fails unsupported core operator, or the construct remains in a namespaced extension with extension-specific validation.

**Discovery:** fail-closed core semantics plus opaque extensions is preferable to silently accepting unknown mathematics.

### F. Secret-looking material inside extension
`official_seed` appears under an extension payload.

Expected: forbidden-key scan fails.

**Discovery:** extension opacity cannot bypass global secrecy invariants. However, key scanning is only defense-in-depth and cannot prove prose/opaque payload safety.

### G. Typed unresolved science
The governing relation is `UNRESOLVED_SCIENTIFIC_OWNER`.

Expected: warning rather than fabricated default.

**Discovery:** authoring validity and LIVE eligibility are distinct states. The semantic toolchain needs an explicit maturity/state model rather than one boolean `valid` flag.

### H. Symbol namespaces in future coupled systems
Two components both contain a state called `T` or `p`.

Current v0.1 global uniqueness would reject this.

**Discovery:** scoped symbol namespaces are likely required for compositional/multiphysics systems, but are not needed in the v0.1 core yet. Reserve as an earned future extension/core-version candidate.

### I. Units and dimensions
A relation is structurally valid while adding quantities with incompatible units.

Current validator cannot detect this.

**Discovery:** dimensional consistency is a strong candidate future evaluation/authoring primitive, but adding units to core now would be premature because current Burgers semantics do not even ratify units. Treat units as an extension until a real Challenge demonstrates a required contract.

### J. Condition sufficiency
An elliptic PDE may have missing/insufficient boundary conditions while still being structurally parseable.

**Discovery:** structural validator cannot prove mathematical well-posedness. A later scientific-model linter may propose warnings, but well-posedness must not become an unreviewed generic protocol oracle.

## Architecture findings

### G1-D009 — Authoring maturity must be multi-state
**Class:** EXTEND/HARDEN.

Do not model semantic readiness as `valid=true/false`. Distinguish at least:

- structurally invalid;
- structurally valid with unresolved science;
- structurally reviewable;
- scientifically qualified by external dossier/Challenge process.

The structural validator owns only the first boundary.

### G1-D010 — Namespaces are likely inevitable for composition
**Class:** DEFER.

Global symbol uniqueness is correct for v0.1. Coupled systems will likely require scoped names (`thermal.T`, `fluid.p`, etc.). Do not add until the multiphysics crash test.

### G1-D011 — Units/dimensional analysis are valuable but not yet core
**Class:** DEFER.

They may become reusable authoring/evaluation primitives. Do not fabricate unit semantics for normalized/dimensionless P0 systems.

### G1-D012 — Structural validation cannot establish well-posedness
**Class:** HARDEN.

Do not market or document the validator as a physics validator. A future scientific linter can suggest missing conditions but remains advisory until qualified.

### G1-D013 — Extension opacity needs global constitutional scans
**Class:** HARDEN.

Core does not understand extension payload science, but global forbidden-material rules still apply across the full artifact.

## Economic/product implication

The validator is useful infrastructure because it can reduce authoring errors before expensive generator/dossier work begins. Its value is primarily Challenge-authoring efficiency and provenance hygiene, not a sellable 'physics verification' capability by itself.

## Gate verdict

**PASS.** Proceed to adapter simulation.

The validator earns its place if it remains boring: deterministic structural checks, explicit unresolved states, and zero scientific-authority inflation.
