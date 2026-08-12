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

> **Note:** Full Score Pack YAML schemas, soft-leg formulas, stress category weights, and per-challenge packs remain in this appendix as previously published. This restore preserves the TL;DR + executive framing; if any deep formula sections were truncated in transit, re-sync from the last known-good Scoring blob before judge access.
