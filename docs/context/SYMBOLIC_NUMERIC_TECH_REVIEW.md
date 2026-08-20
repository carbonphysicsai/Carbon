# Symbolic-Numeric Integration — Tech/Science Review Handoff

**Branch:** `design/symbolic-numeric-integration`  
**Status:** review handoff; no P0 runtime/scoring changes requested.  
**Purpose:** Concentrate the small set of provisional decisions that require technical/scientific review before broader ratification.

---

## Review verdict requested

For each item, choose **ACCEPT / MODIFY / REJECT** and record the reason.

### R1 — Burgers stress-viscosity lower bound

**Provisional decision:** `5e-4`.

Current source conflict:

```text
poc/configs/challenge_burgers1d.yaml:      stress = [5e-4, 5e-3]
poc/generators/justification.py:          stress = [3e-4, 5e-3]
```

Reason for provisional choice: `generate_batch()` consumes the YAML, so `5e-4` describes current executable P0 behavior. Using `3e-4` only in the semantic layer would claim a stress region the current generator does not produce.

**If ACCEPT:** later repair the stale justification metadata to `5e-4`.  
**If MODIFY to `3e-4`:** deliberately version/change the executable Challenge config/generator and then update semantics. Do not edit only `PhysicalSystemSpec`.

---

### R2 — Burgers governing relation

**Provisional scientific relation:**

```text
d_t(u) + u*d_x(u) = nu*d_xx(u)
```

Display form:

```text
∂u/∂t + u ∂u/∂x = ν ∂²u/∂x²
```

Basis: current `burgers_reference_solve()` implements explicit `-u*u_x` advection plus implicit `nu*u_xx` viscosity, equivalent to the relation above.

This is descriptive physical semantics only. It does not define a residual discretization, gate, threshold, or score.

**Review questions:**

- Is this the intended physical equation for `burgers1d_v0`?
- Is the notation/scoping adequate for the Challenge?
- Are additional assumptions needed in the semantic artifact?

---

### R3 — Provisional Carbon relation IR

**Decision:** represent each governing relation with both:

1. human-readable text;
2. a tiny Carbon-owned expression tree.

Prototype grammar:

```text
leaves:       var, param, const
algebra:      add, mul, pow, neg
relations:    eq
calculus:     partial, derivative
```

Burgers example is encoded in `Design_Specs/physical_system_specs/burgers1d_v0.prototype.yaml`.

**Important non-features:** no solver/discretization state, no threshold, no residual normalization, no gate, no score semantics, no automatic symbolic equivalence.

Review source: `Design_Specs/physical_system_specs/RELATION_IR.md`.

**Review questions:**

- Is the minimal AST sufficient as the first representation-agnostic contract?
- Should any operator be removed before prototype ratification?
- Is there any missing operator required even for the first PDE/ODE authoring cases?
- Should `canonical_text` be identity-bearing or presentation-only? Current recommendation: presentation/review only; structured representation carries machine semantics.

---

### R4 — Identity model

**Provisional decision:**

```text
semantic identity = physical_system_spec_id + version
byte identity     = ChallengeRecord.artifacts["physical_system_spec"].digest
```

Do not add a second canonical content hash inside the physical-system artifact.

Reason: completed A3 already supplies fail-closed content-addressed byte identity. Duplicating hash authority creates unnecessary disagreement modes.

---

### R5 — A3 integration

**Provisional decision:** no A3 schema/code migration.

Use existing generic artifact binding:

```text
ChallengeRecord.artifacts["physical_system_spec"]
```

Absence remains valid. If present, ordinary A3 artifact-integrity checks apply. No ninth qualification slot is introduced.

Later A12/integration tests should prove that the extra artifact cannot influence score or protected disclosure.

---

### R6 — Public/private boundary

**Provisional default:** a registered `PhysicalSystemSpec` is `public_challenge_semantics` when it contains only public scientific structure.

Rationale: current generator doctrine already publishes generator code + parameter ranges, Score Packs, and Validation Dossiers, while keeping materialized live eval/stress tensors protected.

Public semantic artifact may include:

- governing relations;
- variables/parameters;
- public envelope descriptions;
- boundary/initial-condition family descriptions;
- assumptions;
- reference/dossier links;
- public regime metadata.

It must not include:

- official seeds/draw IDs;
- master-secret material;
- live eval/stress tensors;
- reconstruction-sensitive protected exam state;
- unauthorized partner-private semantics.

Public artifact status does not mean automatic inclusion in miner `EvaluationCard` / MCP responses. Those surfaces remain separately allow-listed.

For private partner science, prefer a separate controlled artifact/class rather than silently mixing private fields into the public semantic object.

---

## Architecture boundaries that are not under review unless a contradiction is found

- A1-A3 remain completed and closed.
- A4 remains seed-domain/leakage work only.
- A5 remains ScoreEngine + Score Pack only.
- `Scoring.md` remains sole scoring authority.
- `PhysicalSystemSpec` cannot create gates or thresholds.
- ModelingToolkit is a possible authoring adapter, not a validator/miner runtime dependency.
- A6 is the first planned internal-evidence propagation point.
- Landscape physical-context use remains later and evidence-gated.
- Hybrid `ModelConstructionStrategy` / `FastPhysicalModel` concepts remain post-P0.

---

## Suggested review order

```text
R2 governing physics
  ↓
R1 envelope value
  ↓
R3 representation form
  ↓
R4 identity
  ↓
R5 registry integration
  ↓
R6 disclosure classification
```

If R1/R2 change scientific semantics, update/version the source generator/reference artifacts first; the semantic layer follows those sources rather than overriding them.

---

## Current files to review

```text
Design_Specs/Physical_System_Representation.md
Design_Specs/physical_system_specs/RELATION_IR.md
Design_Specs/physical_system_specs/burgers1d_v0.prototype.yaml
Design_Specs/physical_system_specs/README.md
docs/context/SYMBOLIC_NUMERIC_INTEGRATION_DECISIONS.md
docs/context/SYMBOLIC_NUMERIC_RECONCILIATION.md
```

---

## Recommended acceptance posture

Accept the integration only if it remains a **semantic/provenance layer around existing scientific authority**, not a second scientific authority.

The intended invariant is:

```text
PhysicalSystemSpec
    describes / links
        ↓
Generator + envelope + dossier
        qualify
        ↓
Score Pack
        defines authoritative evaluation semantics
```

not:

```text
symbolic parser → automatic physics truth
```
