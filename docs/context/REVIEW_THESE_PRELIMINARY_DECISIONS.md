# Review These Preliminary Decisions — Symbolic-Numeric Integration

**Branch:** `design/symbolic-numeric-integration`  
**Status:** owner preliminary decisions; tech/science lead may accept, modify, or reject later.  
**Purpose:** Record the best current decisions so ordinary Carbon build work can continue without waiting for immediate review.  
**Scope:** These decisions govern the symbolic-numeric design branch only. They do not silently change P0 scoring, A4/A5 scope, LIVE Challenge semantics on `main`, or product qualification.

---

## Executive recommendation

Proceed on the design branch as though **R1–R7 are accepted provisionally**, with the modifications and guardrails below. The decisions are mutually coherent and preserve Carbon's existing authority model:

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

The decisions below are deliberately reversible until ratified. If the tech/science lead changes a scientific value such as R1 or R2, the source Challenge/generator/reference artifacts must be changed/versioned first; the semantic representation follows them.

---

# Preliminary decisions

## R1 — Burgers stress-viscosity lower bound

### Preliminary decision: **ACCEPT `5e-4`**

Use:

```text
stress viscosity = [5e-4, 5e-3]
```

### Why

- `poc/configs/challenge_burgers1d.yaml` is the executable Challenge configuration currently consumed by `generate_batch()`.
- It uses `5e-4` as the lower stress-viscosity bound.
- `poc/generators/justification.py` contains a conflicting explanatory value of `3e-4`.
- A semantic artifact should describe current executable behavior rather than claim a larger stress region than the generator currently samples.
- Moving to `3e-4` may be scientifically reasonable, but it would be a deliberate Challenge-envelope/generator change requiring versioning and evidence, not a metadata-only correction.

### Follow-up if ratified

Repair the stale explanatory justification to `5e-4`. If the physics lead prefers `3e-4`, version the executable Challenge semantics and re-run the relevant generator/dossier qualification before changing the semantic spec.

### Confidence

**High as a provenance/implementation decision; not a claim that `5e-4` is the scientifically optimal stress boundary.**

---

## R2 — Burgers governing relation

### Preliminary decision: **ACCEPT**

Canonical scientific relation for the current Burgers prototype:

```text
d_t(u) + u*d_x(u) = nu*d_xx(u)
```

Display form:

```text
∂u/∂t + u ∂u/∂x = ν ∂²u/∂x²
```

### Why

The current reference implementation advances explicit nonlinear advection `-u*u_x` plus viscous diffusion `nu*u_xx`, which is algebraically equivalent to the relation above. This is also the standard 1D viscous Burgers form intended by the Challenge label.

### Required scope metadata

The relation must be read together with:

- one spatial dimension;
- scalar state `u(x,t)`;
- viscosity parameter `nu`;
- periodic spatial domain for the current P0 realization;
- the separately registered initial-condition family and parameter domains.

The equation does **not** by itself define a Carbon residual metric, discretization, conservation gate, threshold, or claim of real-world adequacy.

### Confidence

**Very high for the intended current mathematical model.**

---

## R3 — Carbon relation IR

### Preliminary decision: **ACCEPT WITH ONE DESIGN TIGHTENING**

Keep both:

1. a human-readable display string; and
2. a small Carbon-owned structured expression tree.

Initial grammar:

```text
leaves:       var, param, const
algebra:      add, mul, pow, neg
relations:    eq
calculus:     partial, derivative
```

### Tightening

Treat the structured relation as the machine-semantic representation, but **do not call the human-readable string canonical for identity purposes**. Call it `display_text` or equivalent. It exists for scientific review and publication; it should not determine equality or artifact identity.

Also keep operator semantics explicit rather than relying on parser conventions. A derivative node should identify its independent variable and order. Do not add automatic algebraic/symbolic equivalence in the first version.

### Why

A small neutral IR gives Carbon a stable adapter target without binding the protocol to ModelingToolkit, SymPy, Modelica, or another modeling language. Starting smaller is preferable. Additional operators should be added only when a real Challenge requires them and their semantics can be defined unambiguously.

### Explicit non-features

The IR contains no:

- numerical discretization;
- solver method;
- residual normalization;
- tolerance;
- gate status;
- Score Pack weight;
- automatic simplification/equivalence authority.

### Confidence

**High as a first representation contract; medium on the exact final grammar because coupled/DAE/multiphysics Challenges will eventually require extension.**

---

## R4 — Identity model

### Preliminary decision: **ACCEPT**

Use:

```text
semantic identity = physical_system_spec_id + version
byte identity     = ChallengeRecord.artifacts["physical_system_spec"].digest
```

Do not add a second canonical `content_hash` inside `PhysicalSystemSpec`.

### Why

A3 already supplies content-addressed, fail-closed byte identity for registered artifacts. A second canonical hash inside the artifact would create two authorities that can disagree while adding no useful security property.

Semantic version identity and exact byte identity answer different questions and should remain separate.

### Confidence

**Very high.**

---

## R5 — A3 integration

### Preliminary decision: **ACCEPT**

Do not migrate or reopen A3. Use:

```text
ChallengeRecord.artifacts["physical_system_spec"]
```

as the optional binding.

### Why

The completed A3 registry already accepts generic canonical artifact identifiers and content-addresses declared artifacts. `physical_system_spec` fits that contract. Absence can remain valid, while a declared artifact receives the same fail-closed integrity behavior as other Challenge artifacts.

Adding new top-level fields or a ninth qualification slot would duplicate capability and unnecessarily modify a completed strict registry boundary.

### Required future proof

At A12/integration testing, prove at minimum that:

- absence remains valid where the Challenge does not require the artifact;
- a valid bound spec behaves like an ordinary artifact;
- missing/digest-mismatched bytes fail artifact integrity;
- the artifact cannot alter `S_combined` when metrics and Score Pack are unchanged;
- the artifact does not create a miner disclosure privilege.

### Confidence

**Very high.**

---

## R6 — Public/private boundary

### Preliminary decision: **ACCEPT WITH CLASSIFICATION GUARDRAIL**

Default a registered `PhysicalSystemSpec` to:

```text
public_challenge_semantics
```

**only when every included field is already authorized public Challenge science.**

Do not make `public` an unconditional property of the schema or artifact type. Publication is an instance-level classification decision.

### Public-safe content may include

- governing relations;
- variables and public parameter definitions;
- published envelope/range descriptions;
- initial/boundary-condition family descriptions;
- assumptions and exclusions;
- public reference/dossier identifiers;
- public regime metadata.

### Forbidden from a public spec

- official seeds or draw identifiers;
- master-secret material;
- materialized live eval/stress tensors;
- reconstruction-sensitive protected exam state;
- unauthorized partner-private equations, geometry, parameters, constitutive relations, or operating envelopes.

### Private partner science

Prefer a separately classified controlled artifact/representation rather than mixing private semantics into an object labeled public. A public Challenge may reference a controlled semantic artifact only if the protocol and governance rules explicitly support that mode later.

### Why

Carbon's current generator doctrine already treats generator code and parameter ranges, Score Packs, and Validation Dossiers as public while keeping materialized live evaluation/stress tensors protected. A public-safe semantic description is consistent with that transparency model and helps external scientific audit. However, sponsored/partner Challenges may contain proprietary physical semantics, so publication cannot be a universal type-level invariant.

Public artifact status also does not imply automatic inclusion in miner EvaluationCards, MCP responses, or leaderboard surfaces. Those remain separately allow-listed.

### Confidence

**High with the instance-level classification guardrail.**

---

## R7 — Current Burgers “residual” metric semantics

### Preliminary decision: **ACCEPT AS A PROXY; DO NOT TREAT AS FULL PDE RESIDUAL**

The current PoC function `poc/train/losses.py::residual_diagnostic()` computes:

```text
mean |u*u_x - nu*u_xx|
```

on the predicted final-time field.

It does **not** compute `d_t(u)`. The implementation itself states that it is a cheap final-time proxy and not a full spacetime residual.

### Decision

For symbolic-numeric traceability, classify the current quantity as:

```text
final_state_spatial_balance_proxy
```

or retain the legacy name `burgers_residual_mean` only when the metadata explicitly carries:

```text
semantic_class: proxy
limitation: omits d_t(u); not the full governing-equation residual
```

Do not allow the existence of the governing-relation IR to upgrade this metric into a full PDE residual automatically.

### Why

The accepted governing relation is:

```text
d_t(u) + u*d_x(u) - nu*d_xx(u) = 0.
```

A metric that omits `d_t(u)` is not mathematically the residual of that full relation. Since the current P0 model maps initial condition directly to final-time state rather than producing a time trajectory, the missing derivative cannot be recovered honestly from the current output alone without introducing another modeling/approximation assumption.

The current metric can still be useful as a heuristic physics-sensitive proxy. Its utility and PoC discriminative behavior are separate questions from its mathematical name.

### A5 implication

Do **not** widen A5. A5 should still consume registered metrics + Score Pack. But when its fixture Score Pack is implemented, the metric definition should preserve this proxy limitation rather than silently presenting it as a fully qualified PDE residual. A future full residual metric would be a separately defined, implemented, dossier-qualified quantity.

### Confidence

**Very high on the mathematical classification; medium on the preferred final naming.**

---

# Consolidated preliminary disposition

| Decision | Preliminary verdict | Confidence | Important qualifier |
|---|---|---:|---|
| R1 stress lower bound | ACCEPT `5e-4` | High | Describes current executable behavior; not an optimality claim |
| R2 Burgers equation | ACCEPT | Very high | Descriptive physical model, not a score metric |
| R3 relation IR | ACCEPT WITH TIGHTENING | High | Structured tree machine-semantic; display text non-identity-bearing |
| R4 identity | ACCEPT | Very high | A3 digest owns exact bytes |
| R5 A3 integration | ACCEPT | Very high | No migration; invariant tests later |
| R6 public/private | ACCEPT WITH GUARDRAIL | High | Public by default only for public-authorized instances |
| R7 current “residual” metric | ACCEPT AS PROXY | Very high | Omits `d_t(u)`; never call it a full PDE residual without a new implementation |

---

# Decisions intentionally deferred

The preliminary acceptance above does **not** decide:

- the final serialization format for `PhysicalSystemSpec`;
- a universal physical ontology;
- the full operator grammar needed for DAEs, coupled systems, events, integral relations, tensors, geometry, or stochastic systems;
- a ModelingToolkit adapter implementation;
- units for the current dimensionless/normalized Burgers prototype where Carbon sources do not yet specify them;
- which Burgers conserved/invariant quantities should become qualified Carbon metrics;
- a full PDE residual discretization, normalization, or threshold;
- whether `PhysicalSystemSpec` becomes required for future Challenge classes;
- private-partner artifact transport/storage policy;
- any change to P0 scoring, emissions, A4, A5, or miner strategy schema.

Those should be decided when a concrete downstream requirement makes the choice testable.

---

# Recommended tech/science lead review

The lead does not need to re-derive the architecture. Review these preliminary decisions for hidden implementation or scientific problems and mark each:

```text
R1  ACCEPT / MODIFY / REJECT
R2  ACCEPT / MODIFY / REJECT
R3  ACCEPT / MODIFY / REJECT
R4  ACCEPT / MODIFY / REJECT
R5  ACCEPT / MODIFY / REJECT
R6  ACCEPT / MODIFY / REJECT
R7  ACCEPT / MODIFY / REJECT
```

For a modification, record:

1. the replacement decision;
2. which source/semantic owner changes;
3. whether existing Challenge bytes or evidence require versioning;
4. whether the change affects P0 runtime, scoring, secrecy, or disclosure;
5. which tests/dossier evidence must be repeated.

---

# Owner preliminary conclusion

Until review says otherwise, proceed with the following design doctrine:

> **Carbon should carry a small, public-safe when authorized, representation-agnostic description of the physical system; bind its exact bytes through the existing A3 artifact mechanism; keep its machine relation semantics in a minimal neutral IR; accurately classify physics-sensitive proxies rather than upgrading them by name; and require all score-bearing scientific meaning to pass through the existing generator, dossier, and Score-Pack authority chain.**

This preserves the value of symbolic-numeric integration while preventing it from becoming a second protocol or a source of automatic scientific truth.
