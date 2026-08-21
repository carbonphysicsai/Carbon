# Review These Preliminary Decisions — Symbolic-Numeric Integration

**Branch:** `design/symbolic-numeric-integration`  
**Status:** owner preliminary decisions; tech/science lead may accept, modify, or reject later.  
**Purpose:** Record the best current decisions so ordinary Carbon build work can continue without waiting for immediate review.  
**Scope:** These decisions govern the symbolic-numeric design branch only. They do not silently change P0 scoring, A4/A5 scope, LIVE Challenge semantics on `main`, or product qualification.

---

## Executive recommendation

Proceed on the design branch as though **R1–R9 are accepted provisionally**, with the modifications and guardrails below. The decisions preserve Carbon's existing authority model:

```text
physical semantics
    describe
      ↓
generator / envelope / reference
    produce evidence
      ↓
Validation Dossier
    qualifies
      ↓
Score Pack
    defines score-bearing semantics
```

`PhysicalSystemSpec` is therefore a semantic/provenance artifact, not a second scientific authority.

---

## R1 — Burgers stress-viscosity lower bound

**Decision: ACCEPT `5e-4`.**

Use `[5e-4, 5e-3]` because the executable Challenge configuration consumed by the generator currently uses `5e-4`. The conflicting `3e-4` explanatory value should be repaired if the lead accepts this decision. If `3e-4` is scientifically preferred, change/version the executable Challenge and repeat relevant qualification rather than changing semantic metadata alone.

**Confidence:** high as implementation/provenance reconciliation; not an optimality claim.

---

## R2 — Burgers governing relation

**Decision: ACCEPT.**

```text
d_t(u) + u*d_x(u) = nu*d_xx(u)
```

Display:

```text
∂u/∂t + u ∂u/∂x = ν ∂²u/∂x²
```

It describes the implemented mathematical model and does not itself define a residual metric, gate, threshold, or real-world adequacy claim.

**Confidence:** very high.

---

## R3 — Carbon relation IR

**Decision: ACCEPT WITH TIGHTENING.**

Keep a human-readable `display_text` plus a small Carbon-owned structured expression tree. The structured representation carries machine semantics; display text is presentation/review only and does not define identity or equivalence.

Current core operators after the Poisson generality test:

```text
leaves:       var, param, field, const
algebra:      add, mul, pow, neg
relations:    eq
calculus:     partial, derivative
```

No discretization, residual normalization, gate, threshold, score semantics, or automatic symbolic equivalence belongs in the IR.

**Confidence:** high on the architecture; medium on the eventual complete grammar.

---

## R4 — Identity model

**Decision: ACCEPT.**

```text
semantic identity = physical_system_spec_id + version
byte identity     = ChallengeRecord.artifacts["physical_system_spec"].digest
```

Do not add a second canonical content hash inside `PhysicalSystemSpec`.

**Confidence:** very high.

---

## R5 — A3 integration

**Decision: ACCEPT.**

Do not reopen A3. Use the existing optional generic binding:

```text
ChallengeRecord.artifacts["physical_system_spec"]
```

A12/integration testing should later prove ordinary artifact integrity, no score influence, and no disclosure privilege.

**Confidence:** very high.

---

## R6 — Public/private boundary

**Decision: ACCEPT WITH INSTANCE-LEVEL CLASSIFICATION GUARDRAIL.**

Use `public_challenge_semantics` only when every included field is authorized public science. Controlled partner semantics require a separate classification and later transport/storage/disclosure policy. No spec may contain official seeds, materialized hidden exam tensors, master-secret material, or other protected realized exam state.

**Confidence:** high.

---

## R7 — Current Burgers “residual” metric semantics

**Decision: ACCEPT AS A PROXY; DO NOT CALL IT A FULL PDE RESIDUAL.**

The current PoC computes approximately:

```text
mean |u*u_x - nu*u_xx|
```

on the predicted final-time field and omits `d_t(u)`. It is therefore a physics-sensitive final-state spatial-balance proxy, not the residual of the full governing relation. A future full residual requires a separate implementation and dossier qualification.

**Confidence:** very high on mathematical classification.

---

## R8 — Future model/scientific variables in PhysicalSystemSpec v0.1

### Decision: **LEAVE THEM OUT OF THE CORE; RESERVE A CONTROLLED EXTENSION NAMESPACE**

Do not pre-populate the core schema with anticipated future concepts such as:

- dimensionless-group ontology;
- regime taxonomy;
- tensor/geometry representation;
- DAE index metadata;
- stochastic-process semantics;
- events/hybrid automata;
- learned-component locations;
- product context-of-use;
- evaluation primitives.

Poisson demonstrated the correct promotion rule: add a concept to core only when a real second system shows it is genuinely required. That test justified field-valued quantities; it did not justify the other future concepts.

To avoid needless core migrations, reserve:

```text
extensions:
  <namespace>:
    extension_version: <version>
    payload: <experimental content>
```

Extension payloads are non-core, non-authoritative, and may be opaque to the core validator. A concept may be promoted later only after repeated real-Challenge use demonstrates stable semantics and clear ownership.

### Why this is preferable to both alternatives

- **Preloading future variables now** risks freezing speculative ontology and creates false precision.
- **Forbidding extensions entirely** would make every legitimate new modeling class require a core-schema migration.
- **Minimal core + namespaced extensions** preserves scientific humility while allowing experimentation.

### Confidence

**Very high as the v0.1 schema-evolution policy.**

---

## R9 — Structural validator authority

### Decision: **BUILD AN AUTHORING-ONLY STRUCTURAL VALIDATOR NOW**

The next integration objective is a pure structural validator that checks:

- required fields;
- unique symbol declarations;
- relation-tree operator support;
- symbol resolution;
- derivative axes/order;
- condition target resolution;
- extension-envelope shape;
- explicit unresolved states;
- known forbidden secret-bearing keys.

It must not check or imply:

- scientific correctness;
- equation equivalence;
- numerical adequacy;
- dossier validity;
- gate/threshold correctness;
- Score Pack authority;
- Challenge LIVE status;
- product qualification.

The reference implementation intentionally accepts an already parsed Python mapping and has no YAML, generator, scoring, validator, Julia, or network runtime dependency.

### Confidence

**Very high.** This is the correct next machine-contract proof before any ModelingToolkit adapter.

---

# Consolidated preliminary disposition

| Decision | Preliminary verdict | Confidence | Important qualifier |
|---|---|---:|---|
| R1 stress lower bound | ACCEPT `5e-4` | High | Current executable behavior, not optimality |
| R2 Burgers equation | ACCEPT | Very high | Descriptive model, not scoring |
| R3 relation IR | ACCEPT WITH TIGHTENING | High | `field` added after Poisson; display text non-identity-bearing |
| R4 identity | ACCEPT | Very high | A3 digest owns exact bytes |
| R5 A3 integration | ACCEPT | Very high | No migration |
| R6 public/private | ACCEPT WITH GUARDRAIL | High | Instance-level classification |
| R7 current residual | ACCEPT AS PROXY | Very high | Omits `d_t(u)` |
| R8 future variables | KEEP OUT OF CORE + EXTENSIONS | Very high | Promote only from demonstrated need |
| R9 structural validator | BUILD NOW | Very high | Structure only, never scientific truth |

---

# Decisions intentionally deferred

These decisions do not settle:

- final serialization format;
- universal physical ontology;
- complete DAE/multiphysics/tensor/stochastic operator grammar;
- ModelingToolkit adapter implementation;
- units where current Carbon sources do not define them;
- which conserved quantities become qualified Carbon metrics;
- full PDE residual discretization/normalization/thresholds;
- whether `PhysicalSystemSpec` becomes required for future Challenge classes;
- private-partner artifact transport/storage policy;
- any change to P0 scoring, emissions, A4, A5, or miner strategy schema.

---

# Tech/science lead review

Mark each preliminary decision:

```text
R1  ACCEPT / MODIFY / REJECT
R2  ACCEPT / MODIFY / REJECT
R3  ACCEPT / MODIFY / REJECT
R4  ACCEPT / MODIFY / REJECT
R5  ACCEPT / MODIFY / REJECT
R6  ACCEPT / MODIFY / REJECT
R7  ACCEPT / MODIFY / REJECT
R8  ACCEPT / MODIFY / REJECT
R9  ACCEPT / MODIFY / REJECT
```

For modifications, record the replacement decision, affected semantic owner, required versioning, P0/runtime/scoring/secrecy impact, and evidence/tests that must be repeated.

---

# Owner preliminary conclusion

> **Carbon should carry the smallest demonstrated physical semantic core, provide namespaced non-authoritative extensions for future experimentation, structurally validate that contract without claiming scientific truth, and promote new concepts only when real Challenge families demonstrate that they belong in the shared ontology.**
