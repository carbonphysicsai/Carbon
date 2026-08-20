# Burgers Physical-System Traceability — SN-1

**Status:** design integration / authoring analysis / non-runtime / non-scoring  
**Branch:** `design/symbolic-numeric-integration`  
**Purpose:** Test whether `PhysicalSystemSpec` materially improves scientific traceability for the existing Burgers P0 Challenge before Carbon ratifies a general physical-system schema.

---

## 1. Test question

The symbolic-numeric integration earns its complexity only if one physical statement can be followed cleanly through Carbon's existing scientific authority chain:

```text
physical relation / assumption
        ↓
generator + numerical realization
        ↓
Validation Dossier evidence
        ↓
qualified metric definition
        ↓
Score Pack
        ↓
A5 ScoreEngine
```

This document performs that test using the current `burgers1d_v0` implementation. It does **not** create new gates, thresholds, metric definitions, or dossier evidence.

---

## 2. Governing physical relation

The current reference implementation is consistent with the 1D viscous Burgers equation

```text
d_t(u) + u*d_x(u) = nu*d_xx(u)
```

or, for human display,

```text
∂u/∂t + u ∂u/∂x = ν ∂²u/∂x².
```

The relation is descriptive scientific semantics. It does not by itself specify how Carbon should discretize a residual, aggregate an error, set a tolerance, or score a model.

Relevant physical context currently implemented/configured:

- one spatial dimension;
- periodic spatial domain `x ∈ [0,1)`;
- scalar state `u`;
- viscosity parameter `nu`;
- final time `T=1.0` in normal mode;
- operator target: initial condition → final-time solution;
- Fourier-family initial conditions;
- role-separated train/eval/stress viscosity and IC-amplitude distributions.

---

## 3. Traceability chain A — governing relation → numerical reference

### Physical semantic object

`PhysicalSystemSpec.governing_relations.burgers_viscous_1d`

```text
d_t(u) + u*d_x(u) = nu*d_xx(u)
```

### Current numerical realization

`poc/generators/burgers1d.py::burgers_reference_solve()` implements:

- explicit nonlinear advection corresponding to `-u*u_x`;
- implicit viscous diffusion corresponding to `nu*u_xx`;
- Fourier spatial differentiation;
- 2/3 dealiasing;
- periodic spatial representation.

### What this establishes

It establishes a traceable implementation relationship between the descriptive PDE and the current reference code.

### What this does **not** establish

It does not establish:

- the reference solver's convergence order over the declared envelope;
- a dossier reference rank;
- that its discretization error is below any proposed model gate;
- equivalence to an independent solver;
- an authoritative model-residual metric.

Those require Validation Dossier evidence under `Generator_Validation.md` and `Evidence_and_Envelope_Standards.md`.

---

## 4. Traceability chain B — periodicity → conservation candidate

### Physical implication

For the provisional Burgers relation on a periodic domain, integrating over one period gives a conserved spatial integral of `u`, assuming the represented relation and periodic boundary semantics apply. Carbon's current PoC uses a discrete mean as a proxy for this property.

### Current implementation

`poc/train/losses.py::conservation_error()` computes:

```text
mean_batch( abs(mean_x(u_T_pred) - mean_x(u_0)) )
```

The current PoC Score Pack identifies this as:

```text
definition: periodic_mass_proxy
error_key: e_cons
```

and uses `tau = 0.08` in the fixture/PoC scoring configuration.

### Scientific classification

**Classification: physically motivated proxy, not yet dossier-qualified production conservation gate.**

The physical relation + periodic domain provide a defensible scientific reason to examine conservation of the domain integral. The current metric is nevertheless a discrete proxy whose numerical behavior and threshold still require explicit calibration.

### Evidence required before production authority

A future dossier should establish at least:

1. the reference solver's own conservation floor over the registered envelope;
2. sensitivity of the discrete mean proxy to grid resolution / numerical precision;
3. behavior across train/eval/stress parameter boundaries;
4. a justified normalization and aggregation convention;
5. threshold calibration above numerical/reference noise and below scientifically irrelevant slack.

Only after that chain is explicit should a production Score Pack treat the metric as authoritative.

---

## 5. Traceability chain C — current “residual” diagnostic

This test exposed an important semantic mismatch.

### Current implementation

`poc/train/losses.py::residual_diagnostic()` computes at the predicted **final state**:

```text
mean | u*u_x - nu*u_xx |
```

It does not compute `u_t`.

The function itself documents that it is:

> a cheap Burgers residual proxy at final time; not a full spacetime residual.

The current PoC Score Pack labels this metric:

```text
definition: burgers_residual_mean
error_key: e_res
```

with a PoC threshold `tau = 2.0`.

### Reconciliation finding SN-BURGERS-004

**The current diagnostic must not be represented in `PhysicalSystemSpec` or future dossier traceability as the residual of the full Burgers governing equation.**

For the governing relation

```text
d_t(u) + u*d_x(u) - nu*d_xx(u) = 0,
```

a governing-equation residual requires a time-derivative term or another scientifically justified equivalent formulation. The current final-state-only diagnostic omits `d_t(u)` because the P0 model maps `u_0 → u_T` rather than producing a time trajectory.

### Recommended semantic name

Until a full residual is implemented and qualified, describe the current metric as something like:

```text
final_state_spatial_balance_proxy
```

or retain `burgers_residual_mean` only with an explicit `proxy` classification and the documented limitation.

### Impact on A5

A5 should not silently promote this PoC diagnostic into a scientifically authoritative “PDE residual” merely because the legacy/PoC Score Pack uses the word residual. Production fixture semantics should preserve the limitation, and any future production gate should be dossier-calibrated under its actual mathematical definition.

This is a **semantic hardening finding**, not a request to widen A5's scope.

---

## 6. Traceability chain D — periodic boundary semantics

The current Challenge uses a periodic spatial grid with the endpoint excluded, and the reference solver uses Fourier differentiation.

The PoC gate configuration explicitly disables a separate boundary gate:

```text
boundary:
  enabled: false
```

### Reconciliation finding

This is currently sensible. The existence of `boundary_conditions.spatial = periodic` in `PhysicalSystemSpec` should **not** automatically generate a boundary gate.

A future boundary diagnostic would need an explicit numerical definition appropriate to a periodic sampled representation. Merely comparing endpoint values is not directly meaningful when the grid is `[0,1)` and `x=1` is not separately represented.

Therefore:

```text
periodic semantic fact
    ≠ automatic boundary metric
    ≠ automatic gate
```

---

## 7. Traceability chain E — viscosity envelope and stress semantics

The executable Challenge config currently uses:

```text
train/eval nu: [1e-3, 1e-2]
stress nu:     [5e-4, 5e-3]
```

The `5e-4` stress lower bound is the current provisional integration decision because it matches executable behavior. A conflicting justification source states `3e-4`; that remains a review item rather than being silently normalized.

### Dossier evidence needed

Before the viscosity envelope supports a LIVE scientific claim, the dossier should establish that the numerical reference remains credible across the registered range, including the lower stress boundary. Under current standards this should include appropriate convergence/reference evidence and coverage reporting.

### Score relationship

The physical-system representation may describe the range and stress regime. It does not decide:

- how much lower viscosity should be sampled;
- what robustness category weight it receives;
- what model-error threshold is acceptable;
- whether a viscosity boundary is score-bearing.

Those remain generator/Score-Pack decisions after dossier qualification.

---

## 8. Current authority-state matrix

| Object | Current state | Can `PhysicalSystemSpec` describe it? | Can it affect score now? |
|---|---|---:|---:|
| Burgers governing relation | provisional scientific relation matched to implementation | yes | no |
| periodic domain | implemented/configured fact | yes | no |
| viscosity role domains | implemented/configured fact; one source mismatch recorded | yes | only through already registered generator/Score-Pack semantics |
| Fourier IC family | implemented/configured fact | yes | no direct score authority |
| IMEX Fourier reference method | implemented numerical provenance | yes, by reference | no |
| mean conservation proxy | implemented PoC metric; physically motivated | yes as linked candidate/proxy metadata | only under explicit Score Pack |
| final-state spatial-balance proxy | implemented PoC metric; **not full PDE residual** | yes as linked proxy metadata | only under explicit Score Pack |
| full Burgers PDE residual | not implemented/qualified for final-state-only model | yes as a candidate scientific concept | no |
| boundary gate | disabled in PoC | semantic periodicity only | no |
| production thresholds | not established by PhysicalSystemSpec | no | Score Pack + dossier only |
| dossier reference rank | not established by existence of solver code | link only | no |

---

## 9. Minimum dossier links Carbon should eventually record

To make symbolic-numeric traceability operational without creating a second authority, a future dossier format should be able to reference stable semantic IDs such as:

```text
relation_id: burgers_viscous_1d
assumption_id: spatial_periodic_v1
parameter_domain_id: nu_stress_v1
metric_id: periodic_mass_proxy_v1
metric_id: final_state_spatial_balance_proxy_v1
```

Those IDs are provenance links, not scoring authority.

A future score-bearing chain should be auditable as:

```text
relation / assumption ID
      ↓
metric mathematical definition + implementation version
      ↓
reference / convergence / calibration evidence
      ↓
registered Score Pack metric + threshold
      ↓
A5 deterministic ScoreEngine
```

The exact ID schema is **not ratified by this document**.

---

## 10. SN-1 verdict

The Burgers test supports continuing the integration.

`PhysicalSystemSpec` has already produced two forms of value:

1. it exposed the `5e-4` vs `3e-4` stress-envelope metadata conflict;
2. it exposed that the current `residual_diagnostic` is not a full governing-equation residual and therefore should not be promoted semantically without qualification.

These are exactly the kinds of drift a physical semantic layer is intended to reveal.

### Decision

**SN-1 PASS — proceed to a minimal `PhysicalSystemSpec v0.1` candidate after tech-lead review, without changing P0 runtime behavior.**

### Before schema freeze

Preserve the following as explicit review items:

- SN-BURGERS-001: `5e-4` vs `3e-4` stress lower bound;
- SN-BURGERS-004: current final-state spatial diagnostic is not a full PDE residual;
- whether semantic relation/assumption IDs should be part of v0.1 or remain an extension;
- what second physics family should test schema generality.

---

## 11. Recommended second-system test

Use an elliptic or diffusion-dominated Challenge, preferably **Poisson** if the existing Carbon science is sufficiently specified when the test is run.

Reason: a second evolutionary nonlinear PDE would not stress the abstraction enough. An elliptic system tests whether the proposed schema handles:

- no time variable;
- boundary-condition-dominant semantics;
- different operator mapping;
- different admissibility/invariant structure;
- different reference/dossier evidence.

Do not author the second prototype until its Carbon source semantics are sufficiently qualified; unknown fields should remain unknown rather than being filled from generic textbook knowledge.
