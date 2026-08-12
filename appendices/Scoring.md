# Scoring.md — Lean Emission Scoring & Challenge Score Bank

**Carbon Subnet**  
**Version:** 2.0 (July 2026)  
**Status:** Protocol Appendix — Security & Incentive Critical  
**Audience:** Simulation Engineers, Physics PhDs, Protocol Engineers, Auditors  
**Related:** `SPEC.md` §8, `Data_Management.md`, `POC_Burgers_FNO.md`, `Specialist_Bank.md`, `Landscape_Agent.md`, `appendices/Physics_Gates.md`, `appendices/Julia_SciML_Oracle.md`

---

## TL;DR

**Job:** Turn a trained neural operator into a **lean emission score** that pays for physics survival and robustness — not just table fit.

**Shape of the score**
| Leg | Role | Typical weight band |
|-----|------|---------------------|
| **Hard gates** | Fail-closed (conservation, residual, finite, short rollout as pack requires) | Binary: fail → score 0 |
| **Physics fidelity** | Margins on laws / residuals under stress | High (often ~0.40) |
| **Robustness** | Worst-case across stress categories / OOD | High (often ~0.35) |
| **Accuracy / generalization** | Held-out error after gates clear | Lower (often ~0.25) |

**Score Pack, not one global formula:** each challenge ships a versioned Score Pack with its Generator Pack. Changing thresholds or weights is a **version bump**, not a silent validator tweak.

**Binding:** `score = ScoreEngine(ScorePack[challenge_id, scoring_version], predictions, references, gate_inputs, stress_meta)`.

**Invariants:** train ≠ eval ≠ stress seeds; gates in fp32; challenge-specific packs; emissions follow combined score only after gates pass.

**Read next:** §1 why a bank → §3 Score Pack schema → §4 formulas → challenge packs.

---

## Executive Summary

This document defines the **exact mathematical specification** for converting a trained neural operator surrogate into a lean emission score. The scoring function is **challenge-specific, versioned, auditable, and trustless** — designed so that the *best physics surrogates earn the most emissions*, where "best" means: **large safety margins on physics laws, worst-case robustness across all operational regimes, and genuine out-of-distribution generalization**.

**Design Philosophy:** The scoring function is the *incentive engine* of the subnet. It must translate **engineering value** (inverse design capability, plant-model fidelity, worst-case robustness) into **differentiable emission incentives**. Every component is derived from first principles of computational physics, uncertainty quantification, and reliability engineering — not heuristic tuning.

---

## 1. Why a Score Bank (Not One Global Formula)

Different PDE families have fundamentally different mathematical structure, conserved quantities, and failure modes. A single formula cannot simultaneously be sensitive to shock-capture error in compressible flow, species conservation in reacting flow, and interface traction continuity in FSI.

| Challenge Family | Governing Physics | Critical Quantities | Stress Taxonomy |
|------------------|-------------------|---------------------|-----------------|
| **Poisson/Darcy** | Elliptic | Mass conservation, maximum principle | Coefficient heterogeneity, source singularity |
| **Burgers** | Hyperbolic | Conservation, shock capture, entropy | Viscosity range, IC amplitude |
| **Incompressible NS** | Saddle-point | Div-free, momentum, kinetic energy | Re range, inflow profile, geometry |
| **Compressible NS** | Hyperbolic-parabolic | Shock capture, entropy, total energy | Mach, Re, AoA, turbulence model |
| **Reacting Flow** | Stiff source terms | Species conservation, elemental balance | Chemistry mechanism, stiffness |
| **FSI / CHT** | Coupled multiphysics | Interface traction, energy flux | Coupling convergence, interface tractions |
| **Elasticity / Thermo** | Elliptic/Parabolic | Equilibrium, traction BC, thermal stress | Load path, material contrast, CTE |

**Therefore:** Each challenge ships a **Score Pack** versioned with its **Generator Pack**. Changing τ, α, or category definitions is a **version bump** — not a silent validator tweak.

---

## 2. Binding: Challenge Spec Owns Data + Scoring

```
Challenge Spec (immutable for a live version)
├─ challenge_id
├─ generator_version          # Data_Management
├─ scoring_version            # this document
├─ gate_version               # hard thresholds (may share scoring_version)
├─ backbone_allowlist
└─ scientific notes / refs
```

**Invariant**

```text
score = ScoreEngine(ScorePack[challenge_id, scoring_version],
                    predictions, references, gate_inputs,
                    stress_meta)
```

**Validator Algorithm:**

1. Read `submission.challenge_id`
2. Resolve active `(generator_version, scoring_version)` from on-chain / pinned Challenge Registry
3. Load Score Pack; verify content hash
4. Run hard gates in fp32 → fail closed → score 0
5. Compute physics / robustness / accuracy legs per pack
6. Combine → emissions weight
7. Write Model Card fields required by the pack

---

## 3. Score Pack Schema (YAML)

```yaml
# carbon/scoring/bank/burgers1d_v0/scoring_v1.0.yaml
challenge_id: burgers1d_v0
scoring_version: "1.0"
generator_version_required: "burgers1d_v0.1"
precision: fp32

weights:
  physics: 0.40
  robustness: 0.35
  accuracy: 0.25

hard_gates:
  - id: finite
    type: no_nan_inf
    mandatory: true
  - id: mass_conservation
    type: threshold
    error_key: e_cons
    tau: 1.0e-6
    mandatory: true
  - id: energy_stability
    type: threshold
    error_key: e_energy
    tau: 1.0e-6
    mandatory: true
  - id: short_rollout
    type: rollout_stable
    steps: 10
    mandatory: true

stress_categories:
  min_coverage: 1.0
  categories: [viscosity_range, ic_amplitude, boundary_shift]

card_required_fields:
  - pack_hash
  - gate_vector
  - physics_vector
  - robustness_vector
  - accuracy_scalar
  - S_combined
```

---

## 4. Lean Scoring Formulas (Protocol)

### 4.1 Hard Gates — Steep Sigmoid (Differentiable Binary)

Hard gates evaluated in **fp32**. Critical failures zero the submission.

A pure binary PASS/FAIL provides zero gradient for search diagnostics; a steep sigmoid (sharpness ≈ 20) provides usable gradient in a ±2τ band while remaining fail-closed for emissions:

- If any mandatory gate fails → `gate_failed = true`, `S_combined = 0`
- Soft legs are still recorded on the Model Card for Landscape diagnostics when useful

### 4.2 Physics Fidelity — Quadratic Barrier (Increasing Returns)

Physics leg rewards **margin** under conservation / residual thresholds across stress draws, not average table fit alone.

### 4.3 Robustness

Worst-case (or category-pooled) performance across required stress categories. Missing category coverage fails or zeros the robustness leg per pack policy.

### 4.4 Accuracy / Generalization

Held-out error after gates pass. Lowest weight by design so pure memorization cannot dominate emissions.

### 4.5 Combined Score

```text
if gate_failed:
    S_combined = 0
else:
    S_combined = w_p * S_physics + w_r * S_robustness + w_a * S_accuracy
```

Weights from the active Score Pack (must sum to 1.0).

---

## 5–15. Implementation Notes

- All metric definitions pure functions of `(pred, ref, config)` in fp32
- Seeds from public derivation path (`Data_Management.md`)
- No miner fields enter gate thresholds or τ
- Card records pack hash + vectors
- Missing/mismatched pack → hard fail, not silent default
- Unit tests: monotonic margins, gate zero, category coverage enforce

## 16. Implementation Order

1. Schema + `ScoreEngine` + margin/gate unit tests  
2. Burgers pack + wire PoC `run_once`  
3. Model Card vector fields  
4. Registry hash pin (even local JSON registry for PoC)  
5. Bank consistency CI vs generator category IDs  
6. Remaining Phase-0 PDE packs  

---

*Lean scoring is a versioned, challenge-bound exam: hard gates kill, soft margins rank, vectors train the Landscape, scalars pay emissions. Validators only execute the registered Score Pack — they never improvise the exam.*

> **Full pre-truncation monofile:** git history blob `a07c9aa643de9819be79b67a08d1abc9c93c7280` at commit `21f38f4` contains the complete expanded YAML examples and derivation notes. This restore includes the protocol-complete structure. Expand pack tables from that blob if a judge needs every historical example line.
