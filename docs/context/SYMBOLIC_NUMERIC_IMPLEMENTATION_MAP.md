# Symbolic-Numeric Integration Implementation Map

**Status:** planning/context only — reconciled against `main` at A3 closeout; does not override `Design_Specs/Build_Out.md` sequencing.  
**Design draft:** `Design_Specs/Physical_System_Representation.md`.  
**Design decisions:** `docs/context/SYMBOLIC_NUMERIC_INTEGRATION_DECISIONS.md`.  
**Reconciliation record:** `docs/context/SYMBOLIC_NUMERIC_RECONCILIATION.md`.

---

## Goal

Integrate structured physical semantics into Carbon without expanding P0 scope, reopening completed tickets, or creating a parallel scientific authority. The implementation is split into **bounded compatibility hooks** and **post-P0 authoring / Landscape / model-class extensions**.

---

# 1. Reconciled current state

A1, A2, and A3 are complete on the reviewed base. They remain closed.

The completed A3 `ChallengeRecord` already provides a generic content-addressed artifact map. Reconciliation therefore rejects a needless A3 top-level schema migration for physical-system identity.

Preferred attachment convention:

```text
ChallengeRecord.artifacts["physical_system_spec"]
    → ArtifactBinding(path, sha256:<digest>)
```

The artifact bytes carry their own semantic identity/version. A3 binds the exact bytes but does not interpret their scientific meaning.

Important A3 behavior:

- absence of `physical_system_spec` remains valid;
- if present, the artifact is checked like every other declared artifact;
- missing / invalid / mismatched bytes fail LIVE eligibility for that exact Challenge record;
- no new qualification slot is required merely to bind the artifact;
- the binding does not enter `S_combined` or authorize scientific claims.

This is intentional fail-closed provenance, not an automatic physics gate.

---

# 2. Near-term compatibility hooks

The old labels `SN-A1/A2/A3` are retired because they collide semantically with completed Build-Out tickets A1-A3.

## SN-H1 — Challenge physical-system artifact binding

**Owner:** additive convention around completed A3; do not reopen A3.  
**Implementation need:** potentially zero code if the existing generic artifact map is sufficient.

Reserve canonical artifact id:

```text
physical_system_spec
```

Acceptance direction:

- artifact is optional;
- exact bytes are content-bound by existing A3 SHA-256 semantics;
- semantic id/version live inside the artifact and must agree with any later parser;
- no official seed/draw information enters the artifact;
- no scoring behavior depends on it;
- no new LIVE qualification slot is introduced;
- old Challenge records remain valid unchanged.

**Reconciliation test still required:** prove with A3 tests that a valid extra artifact does not alter eligibility beyond the ordinary artifact-integrity rule and that absence remains valid.

## SN-H2 — Evidence provenance propagation

**Natural owner:** A6 Card store / InternalResult provenance.  
**Status at reviewed base:** A6 not implemented; depends on A5.

When a Challenge binds `physical_system_spec`, preserve a stable internal reference sufficient for future Landscape joins. Prefer artifact id + digest / semantic identity; do not expose trusted-root paths to miners.

Acceptance direction:

- internal provenance only by default;
- `EvaluationCard` disclosure remains allow-listed;
- no new miner-visible information is implied;
- no historical backfill is invented without explicit migration;
- full internal object remains distinguishable from budgeted miner output.

## SN-H3 — Burgers authoring-only semantic prototype

**Natural owners:** SciML / generator authoring; no validator dependency.

Create a non-runtime `PhysicalSystemSpec` prototype for the existing 1D viscous Burgers P0 Challenge using only ratified scientific facts.

Current supported facts from `POC_Burgers_FNO.md` include:

- 1D viscous Burgers system;
- operator map initial condition → solution at final time;
- initial model class FNO-1d;
- procedural train/eval/stress data with role-separated seeds;
- candidate physics checks listed by the PoC.

Current source explicitly delegates the full numeric envelope/schema to in-repo generator and Score Pack artifacts when implemented. Therefore unresolved viscosity ranges, IC distributions, boundary semantics, conservation interpretation, or regime thresholds must remain explicit `HUMAN_INPUT` / unresolved fields unless another semantic owner supplies them.

Acceptance direction:

- manually inspectable;
- content-addressable/versionable;
- links to Challenge/generator/dossier identities where those identities exist;
- produces no score and changes no runtime behavior;
- does not expose official realized draws;
- does not require ModelingToolkit, Symbolics.jl, Modelica, or another symbolic engine.

---

# 3. Post-P0 scientific-authoring implementation

## SN-S1 — Canonical `PhysicalSystemSpec` schema

Define and ratify a serialization-neutral schema and validation rules.

Required properties:

- representation-agnostic;
- explicit assumptions;
- explicit missing/unknown/not-applicable semantics;
- internal semantic identity/version plus content binding;
- no automatic score/gate semantics;
- extensible scientific feature namespace;
- compatibility with A3 content-addressed artifact provenance rather than a second competing hash authority.

## SN-S2 — Reference ModelingToolkit adapter

Build an authoring adapter that can map supported ModelingToolkit systems into the canonical representation.

Requirements:

- adapter output is reviewable before registration;
- unsupported semantics fail explicitly rather than being fabricated;
- no Julia dependency in miner/validator runtime merely because the adapter exists;
- round-trip semantic-equivalence claims are scoped and tested, not assumed.

Possible later adapters: Modelica, SBML, CellML, SymPy, manual/JSON authoring.

## SN-S3 — Physics Evaluation Primitive Library

Create reusable candidate evaluators for authoring / dossier workflows.

Primitive families may include:

- governing-relation residuals;
- conservation/invariant diagnostics;
- admissibility diagnostics;
- boundary/initial-condition diagnostics;
- dimensional checks;
- physical regime feature extraction.

Required controls:

- primitive definition is versioned;
- numerical implementation/discretization is explicit;
- normalization/aggregation is explicit;
- no threshold/gate status is invented by code;
- scientific qualification links the primitive to a Challenge/Score Pack.

## SN-S4 — Dossier traceability integration

Permit dossier artifacts to trace:

```text
PhysicalSystemSpec relation/assumption
  → reference implementation
  → validation evidence
  → evaluation primitive
  → human-qualified metric / gate / threshold
```

This is provenance and scientific traceability, not automatic qualification.

---

# 4. Landscape implementation

## SN-L1 — Physical-context FeatureStore

**Target:** after PI-L0 evidence ingestion is stable.

Add qualified physical context features to Landscape-private evidence.

Potential initial feature classes:

- system family;
- equation/relation family labels;
- nonlinearity class;
- transport/diffusion/stiffness features;
- boundary topology;
- human-qualified dimensionless groups;
- known physical phenomena / regime tags.

Prefer explicit human-qualified features before symbolic-expression embeddings.

## SN-L2 — Physical graph linkage

Represent a physical-context graph separately from the experimental graph initially.

```text
Experimental:
strategy → execution → outcome → qualification

Physical:
system → structure/components → regime features → constraints/invariants
```

Link evidence through immutable physical-system artifact identity/version.

## SN-L3 — H16 transfer-prediction test

Run a prospective comparison:

```text
baseline:
strategy/intervention + Challenge ID + ordinary metadata

vs

physical-context model:
strategy/intervention + qualified physical features + ordinary metadata
```

Primary question: does structured physical context improve prediction of intervention transfer to future/held-out Challenges?

No production Port A/B/C/D dependency should be created before measurable lift exists.

## SN-L4 — Physical-context Port C experiment design

Only after H16-style prospective value is demonstrated, allow physical context to inform information-experiment proposals for transfer testing, regime coverage, mechanism discrimination, or underrepresented physical structures.

Port C remains proposal-only until governance registration.

---

# 5. Product / qualification implementation

## SN-P1 — Physical-system identity in qualification evidence

When relevant, allow Product Candidate Model Cards / Product Battery Records / Qualification Records to bind the exact `PhysicalSystemSpec` artifact/semantic identity.

No physical-system reference expands context of use automatically.

## SN-P2 — Regime-aware answerability inputs

Where human-qualified, derived physical regime features may become inputs to context-of-use / escalation logic.

Required controls:

- qualified rule is explicit/versioned;
- no self-certification by model uncertainty;
- no automatically generated regime boundaries;
- lifecycle evidence does not silently mutate old qualification claims.

---

# 6. Later model-class expansion

These items are **not** P0 or immediate post-P0 requirements.

## SN-M1 — `FastPhysicalModel` conceptual superclass

Generalize product/evidence terminology so Carbon can eventually qualify fast physical artifacts beyond neural operators without rewriting the trust model.

## SN-M2 — `ModelConstructionStrategy`

For designated future Challenges, generalize a training recipe to a construction hypothesis that may specify physical scaffold, learned component location/type, architecture, losses, curriculum, solver coupling, optimization, and resource budget.

## SN-M3 — Hybrid mechanistic/learned Challenge class

Permit controlled comparison of black-box surrogates versus hybrid mechanistic/learned models under the same external scientific contract.

## SN-M4 — Coupled/compositional Challenge authoring

Use structured physical composition to support progressively coupled scientific regimes after simpler Challenge classes are qualified.

## SN-M5 — Equation / closure discovery branch

Treat equation, constitutive-law, or closure discovery as a separate future Challenge family with its own epistemic and validation contract. Do not fold it into ordinary surrogate search by default.

---

# 7. Research hypotheses

- **H16:** qualified structured physical context improves cross-Challenge intervention-transfer prediction.
- **H17:** structured physical authoring and reusable evaluation primitives reduce Challenge-authoring time/error without weakening scientific validity.
- **H18:** hybrid mechanistic/learned search improves qualification outcomes or decision economics in appropriate regimes.
- **H19:** physical-context-aware experiment allocation improves transferable decision value relative to ordinary experiment-history baselines.

These are research hypotheses, not implementation acceptance facts.

---

# 8. Security / scientific invariants

1. No official seed/draw leakage through physical metadata.
2. No automatic gate/threshold creation from symbolic structure.
3. No symbolic model treated as proof of real-world physical validity.
4. No score changes without `Scoring.md` revision / authorized Score Pack semantics.
5. No Challenge state transition from adapter-generated judgments.
6. No Landscape causal upgrade from physical similarity alone.
7. No qualification expansion from symbolic/regime similarity alone.
8. No mandatory symbolic framework dependency in P0 runtime.
9. No silent reinterpretation of historical evidence after `PhysicalSystemSpec` revision.
10. No fabricated scientific metadata when source representations are incomplete.
11. No reopening completed A1-A3 merely to add symbolic-numeric future-proofing.
12. No duplicate hash/identity authority when A3 artifact binding already content-addresses the exact spec bytes.

---

# 9. Suggested sequencing

Current `Build_Out.md` remains authoritative. A1-A3 are complete; A4 remains the next ordinary Wave-A ticket on the reviewed base.

Near-term symbolic-numeric work:

```text
completed A3       → SN-H1 convention / tests only if needed; do not reopen A3
A6 card store      → SN-H2 internal evidence provenance when A6 is reached
SciML authoring    → SN-H3 Burgers semantic prototype (non-runtime)
A12 invariants     → verify physical metadata cannot affect score or leak exam state
```

Post-P0:

```text
SN-S1 → SN-S2 → SN-S3 → SN-S4
             ↓
PI-L0 stable → SN-L1 → SN-L2 → SN-L3
                              ↓ if evidence supports
                              SN-L4

Specialist product work → SN-P1 → SN-P2

Later scientific expansion → SN-M1 → SN-M2 → SN-M3/M4
                                      ↘ optional SN-M5
```

---

# 10. Stop conditions

Pause or simplify this integration if:

- the Burgers prototype duplicates existing metadata without improving traceability;
- a canonical schema requires framework-specific concepts to remain usable;
- authoring tools begin implicitly inventing scientific judgments;
- P0 implementation becomes dependent on post-P0 symbolic machinery;
- physical features do not improve Landscape transfer/decision performance prospectively;
- symbolic abstraction creates more ambiguity than scientific structure.

The design should earn its complexity empirically.
