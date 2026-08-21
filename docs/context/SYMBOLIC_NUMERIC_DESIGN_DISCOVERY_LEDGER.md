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

| ID | Discovery | Source gate | Class | Design consequence | Canon/paper/pitch consequence | Confidence |
|---|---|---|---|---|---|---|
| D-001 | Executable Challenge semantics can drift from explanatory scientific metadata. | Burgers reconciliation | HARDEN | PhysicalSystemSpec preserves conflicts and follows versioned executable semantics until science owner changes them. | Supports provenance/traceability case; not stage-pitch material. | High |
| D-002 | A governing physical relation is not itself a score-bearing metric. | Burgers traceability | KEEP | Relation IR remains descriptive; diagnostics require separate numerical definition, dossier evidence, calibration, and Score Pack registration. | Strengthens 'symbolic model does not certify physics' doctrine. | Very high |
| D-003 | The current Burgers `residual_diagnostic` omits `d_t(u)` and is therefore a final-state spatial-balance proxy, not a full PDE residual. | Burgers traceability | REVISE | Preserve metric utility if desired, but classify/name it accurately; future full residual is a distinct qualified primitive. | Scientific-credibility improvement; no need to teach on stage. | Very high |
| D-004 | A physics-family label such as 'Poisson' is insufficient physical identity: repository sources can encode materially different model variants. | Poisson generality | HARDEN | PhysicalSystemSpec identity binds explicit relations/fields/conditions, not family label alone. | Strengthens structured-physical-context argument in whitepaper. | Very high |
| D-005 | Field-valued scientific quantities are a genuine core semantic class distinct from scalar parameters. | Poisson generality | EXTEND | Add `field(name, role)` to v0.1 relation IR and field declarations to PhysicalSystemSpec. | Minor canon/whitepaper detail; not pitch material. | High |
| D-006 | Manufactured/reference cases must be separated from the general physical-system definition. | Poisson generality | HARDEN | Reference cases live in provenance/numerical realization, not governing model identity. | Supports evidence hierarchy. | Very high |
| D-007 | Pre-designing all future physics variables would overfit imagined systems; no extension path would create repeated schema migrations. | v0.1 minimization | HARDEN | Small demonstrated core plus namespaced, non-authoritative extensions. Promotion requires repeated real use. | Supports disciplined extensibility; not pitch material. | High |
| D-008 | Structural machine validation is useful only if explicitly denied scientific authority. | Validator design | KEEP | Validator checks references/shape/forbidden content, never scientific correctness or numerical adequacy. | Reinforces no-layer-certifies-itself doctrine. | Very high |
| D-009 | Semantic authoring readiness is not binary. | Validator simulation | EXTEND/HARDEN | Distinguish structurally invalid, structurally valid-with-gaps, reviewable, and externally scientifically qualified states. Validator owns only structural boundary. | Useful whitepaper epistemic/maturity detail; probably not litepaper/pitch. | High |
| D-010 | Coupled systems will likely require scoped symbol namespaces. | Validator simulation | DEFER | Keep global uniqueness in v0.1; revisit during multiphysics crash test. | None yet. | Medium-high |
| D-011 | Units/dimensional analysis are promising authoring/evaluation primitives but current Carbon sources do not justify core unit semantics. | Validator simulation | DEFER | Keep as extension/research candidate until a real Challenge requires it. | Possible future scientific-method contribution; not yet integrate. | High |
| D-012 | Structural validity cannot establish mathematical well-posedness. | Validator simulation | HARDEN | Any future model linter is advisory; scientific qualification remains external. | Strengthens bounded-automation doctrine. | Very high |
| D-013 | Opaque extensions still need global secrecy invariants. | Validator simulation | HARDEN | Scan full artifact for forbidden protected-material classes; do not treat extension validation as public-safety proof. | Internal architecture only. | Very high |

## Gate template

For each remaining simulated implementation gate, record:

1. intended component;
2. happy-path simulation;
3. adversarial/failure simulations;
4. newly required semantics;
5. authority-boundary pressure;
6. implementation/economic consequences;
7. discoveries using the classification above;
8. impact on canon, whitepaper, litepaper, Summit deck;
9. whether the discovery is mature enough to integrate now.

## Remaining simulated gates

1. ~~Structural validator execution/hardening.~~ **PASS**
2. ModelingToolkit adapter.
3. Physics Evaluation Primitive Library.
4. Challenge Compiler / dossier authoring integration.
5. Landscape physical-context integration.
6. Hybrid model-construction search.
7. Coupled/multiphysics crash test.
8. Carbon-without-neural-networks test.
9. Final system-level design review.

**Publication rule:** do not edit the canon/papers/deck from individual speculative findings. Complete the discovery simulation first, then integrate the stable findings in one reconciled pass.
