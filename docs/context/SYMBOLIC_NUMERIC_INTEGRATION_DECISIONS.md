# Symbolic-Numeric Integration Design Decisions

**Status:** DESIGN INTEGRATION — owner-directed exploration initiated 2026-08-20; reconciled against `main` after A3 closeout. Exact schema/runtime changes remain reviewable; no P0 scoring or execution change is ratified by this file.  
**Primary draft spec:** `Design_Specs/Physical_System_Representation.md`.  
**Reconciliation:** `docs/context/SYMBOLIC_NUMERIC_RECONCILIATION.md`.

---

## Decision summary

The symbolic-numeric SciML review identifies a missing physical semantic layer in Carbon's long-term physics-intelligence architecture. The integration is additive: it does not replace the Challenge, generator, Score Pack, Validation Dossier, Landscape ports, or Specialist Bank.

### SN-D1 — Carbon should be representation-aware, not framework-bound

Carbon should support a canonical `PhysicalSystemSpec` abstraction that may be populated by symbolic-numeric ecosystems or manual scientific authoring. ModelingToolkit is a candidate reference adapter, not a protocol dependency or scientific authority.

### SN-D2 — Physical structure is descriptive, not automatically authoritative

A `PhysicalSystemSpec` may record equations, variables, parameters, constraints, assumptions, invariants, and regime features. It cannot create authoritative gates, thresholds, scores, or qualification claims by itself.

### SN-D3 — Scientific authority remains where it already lives

- Score mathematics remain owned by `Scoring.md`.
- Generator science remains owned by generator/dossier/envelope specifications.
- Landscape remains evidence-learning, not scientific authority.
- Product qualification remains owned by the Specialist Bank/product qualification path.

### SN-D4 — Completed A1-A3 remain closed

Repository reconciliation confirms Build-Out tickets A1, A2, and A3 are complete. Symbolic-numeric future-proofing must not reopen or silently widen them.

The completed A3 registry already exposes a generic content-addressed artifact map. The preferred P0-compatible attachment is therefore:

```text
ChallengeRecord.artifacts["physical_system_spec"]
```

rather than new top-level A3 fields.

If declared, A3's existing fail-closed artifact-integrity checks apply to the exact spec bytes. Absence remains valid. No new qualification slot or scoring input is implied.

### SN-D5 — A4 and A5 remain clean protocol boundaries

Repository reconciliation confirms A4 and A5 are still `todo` on `main`.

- **A4** remains seed-domain separation and leakage protection. `PhysicalSystemSpec` must not participate in official seed derivation or contain secret/realized exam state.
- **A5** remains deterministic ScoreEngine + registered Score Pack. `PhysicalSystemSpec` must not be parsed by the ScoreEngine to invent gates, thresholds, weights, or `S_combined` behavior.

Symbolic-numeric functionality should not be added to either ticket.

### SN-D6 — P0 receives only bounded compatibility hooks

The Burgers vertical slice should not gain a symbolic runtime dependency. Near-term work is limited to:

- the optional A3 artifact-binding convention above;
- later A6 internal evidence provenance when A6 is implemented;
- a non-runtime Burgers semantic prototype using only repository-supported scientific facts;
- A12 invariants proving no score/disclosure privilege crossing.

### SN-D7 — Reusable evaluation primitives are a Challenge-authoring capability

Structured physical metadata may later support candidate residual, conservation/invariant, admissibility, boundary/initial consistency, dimensional, and regime-feature primitives. Every score-bearing use still requires explicit scientific qualification through the generator/dossier/Score-Pack path.

### SN-D8 — Structured physical context is a Landscape transfer substrate

Long-term Landscape evidence should be able to connect modeling interventions and outcomes to identifiable physical structure/regimes rather than only Challenge IDs. Physical similarity does not itself establish causal transfer.

### SN-D9 — Neural operators are the first model class, not the permanent ontology

Carbon should preserve a path from `TrainingStrategy` toward future Challenge-specific `ModelConstructionStrategy` objects and from learned operators toward a broader `FastPhysicalModel` concept. Hybrid mechanistic/learned models are a later model class, not a P0 requirement.

### SN-D10 — Equation discovery is a separate epistemic regime

Symbolic regression, closure discovery, and governing-equation discovery may become future Challenge classes, but they are not folded into the initial surrogate-discovery architecture because the object being discovered would overlap with the scientific model used to define evaluation.

### SN-D11 — Separate semantic identity from byte identity

For a registered physical-system artifact:

```text
semantic identity = physical_system_spec_id + version
byte identity     = A3 ArtifactBinding.digest
```

A3's tagged SHA-256 digest is the canonical identity of the exact registered bytes. `PhysicalSystemSpec` should not carry a competing canonical `content_hash` field. Authoring tools may compute temporary hashes, but they do not become protocol identity unless a future explicit migration ratifies that change.

### SN-D12 — PhysicalSystemSpec is public-safe scientific semantics by design

Current generator doctrine makes generator code and parameter ranges public while keeping realized exam data and official seed material protected. The representation should therefore be safe to publish when it contains only public Challenge semantics.

The schema must forbid official realized seeds/draws, master-secret material, hidden tensors, and unauthorized partner-private information. Actual publication of a particular artifact remains a Challenge/governance decision.

### SN-D13 — Source conflicts are first-class reconciliation objects

The Burgers prototype exposed a real source mismatch: `poc/configs/challenge_burgers1d.yaml` uses stress viscosity `[0.0005, 0.005]`, while `poc/generators/justification.py` documents `[0.0003, 0.005]`.

A `PhysicalSystemSpec` must preserve such disagreement explicitly rather than silently choosing or averaging values. Scientific owners resolve the source; the semantic layer records the state of evidence.

---

## Ratification boundaries

This integration does **not** ratify:

- a final serialization format;
- a final physical ontology;
- ModelingToolkit as mandatory infrastructure;
- automatic derivation of gates or thresholds;
- H16-H19 as true;
- hybrid strategy classes in P0;
- equation-discovery Challenges;
- any change to `S_combined`, emissions, or current Challenge thresholds;
- reopening A1-A3;
- widening A4 or A5;
- a ninth LIVE qualification slot for `PhysicalSystemSpec`;
- miner disclosure of trusted-root artifact paths or protected digests;
- the unresolved Burgers stress-viscosity metadata mismatch;
- a canonical symbolic Burgers equation string/AST before scientific-owner ratification.

---

## New invariants

> **The symbolic model does not certify the physical model.**

> **Derived evaluation primitives remain candidates until scientifically qualified.**

> **Physical metadata cannot silently mutate a registered scientific contract.**

> **Symbolic equivalence does not imply numerical or operational equivalence.**

> **Carbon owns the semantic contract, not the modeling language.**

> **Completed implementation boundaries are not reopened when an existing generic provenance hook is sufficient.**

> **A3 owns exact artifact bytes; the spec owns semantic meaning.**

> **Source disagreement is recorded, not normalized away.**

---

## KEEP / WRAP / REPAIR / REPLACE disposition

- **KEEP:** completed A1-A3; A4/A5 narrow contracts; all current P0 scoring, generator, hidden-evaluation, strategy, validator, evidence, Landscape-port, and product-separation invariants.
- **WRAP:** A3 generic artifact binding with optional `physical_system_spec`; later A6 internal evidence provenance with the same immutable byte + semantic identity.
- **REPAIR/EXTEND:** long-term Challenge semantics, reusable scientific authoring primitives, source-conflict traceability, Landscape physical-context features, qualification physical-context provenance.
- **REPLACE:** none.

---

## Strategic consequence

The long-term Carbon research object becomes broader than a neural-network training recipe while remaining narrower than a general-purpose symbolic modeling platform:

> **Carbon is an experimental system for learning which model-construction interventions work for identifiable physical structures, regimes, and engineering contexts.**

For near-term public communication, continue to describe the system through fast learned physics models and independent physics exams. The broader abstraction is architecture future-proofing, not a requirement that stage audiences learn symbolic-numeric modeling.
