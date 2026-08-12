# IMPLEMENTATION.md — Carbon Physics Intelligence Subnet

## TL;DR

**What this is:** Engineering index for building Carbon components — gates, generators, validator pipeline, miner toolkit, MCP, genesis contracts, and the Julia/SciML ground-truth service.

**Ownership rule:** Do not duplicate large designs here.

| Concern | Canonical doc |
|---------|----------------|
| JAX train loop, bf16/fp32, queue, determinism | `JAX_Optimization.md` |
| Seeds, train≠eval, stress, entropy floor | `Data_Management.md` |
| Compute strategy / kernels | `Compute_Optimization.md` |
| K8s, monitoring, incidents | `Operations.md` |
| Landscape / specialists / product jobs | `Landscape_Agent.md`, `Specialist_Bank.md`, `Use_Cases_by_Phase.md` |
| Gates, generators (high-level), MCP, SciML, miner toolkit | **This file** |

**Dual threshold (do not collapse)**

| Workload | Path | Purpose |
|----------|------|--------|
| **Lean eval** | Every full submission | Gates + stress + short rollout → score + Model Card → emissions |
| **Product battery** | Specialist Bank promotion only | INV / deep ROLL / ADV / LAT / ONNX — **not** default per submission |

**Critical invariants:** Physics gates in **fp32**; loss terms use **explicit boolean enables**; hard step/wall-clock limits independent of miner epochs; pinned lockfile + threefry determinism; MCP priors are **noisy-only** (never full SKU).

**Validator lean path:** derive seeds → generate train data → JAX train from strategy → hidden stress → fp32 gates → optional SciML check → Model Card + score.

**SciML role:** Julia service for reference solves, adjoint consistency, symbolic losses — validators call via `SciMLClient`.

---

**Version:** 3.2 (July 2026)  
**Status:** Core Engineering Implementation Guide  
**Audience:** Tech lead + engineering  
**Purpose:** Build-level index for `SPEC.md` components — aligned with dual threshold and Landscape flywheel

---

# TABLE OF CONTENTS

1. JAX Core Training Optimizations → **Canonical: `JAX_Optimization.md`**
2. Physics Gates Implementation
3. Procedural Generators
4. Validator Training Pipeline (lean)
5. Landscape Agent Pipeline
6. Miner Toolkit & SDK
7. Genesis Contracts
8. MCP Protocol
9. Reproducibility & Determinism → **`JAX_Optimization.md`**
10. Operational Infrastructure → **`JAX_Optimization.md`** + **`Operations.md`**
11–13. Julia/SciML Ground Truth Service

---

# Document Ownership (Post-Consolidation)

| Concern | Canonical Document |
|---------|--------------------|
| JAX training loop, boolean loss masking, fp32 gates, curricula, queue, determinism | [`JAX_Optimization.md`](./JAX_Optimization.md) |
| Data generation, seeds, train≠eval, stress, entropy floor, **PB seed separation** | [`Data_Management.md`](./Data_Management.md) |
| Physics gates (code), generators (high-level), MCP, SciML, miner toolkit | **This file** |
| Compute efficiency | [`Compute_Optimization.md`](./Compute_Optimization.md) |
| Ops / K8s | [`Operations.md`](./Operations.md) |
| Landscape four ports + flywheel | [`Landscape_Agent.md`](./Landscape_Agent.md) |
| Product battery, dual egress, anti-distillation | [`Specialist_Bank.md`](./Specialist_Bank.md) |
| Inverse design / plant / UQ / hybrid truth teaching | [`Use_Cases_by_Phase.md`](./Use_Cases_by_Phase.md) |
| High-level architecture | `SPEC.md` |

**Rule:** Do not re-copy large designs from specialized appendices. Link instead.

---

# 1. JAX CORE TRAINING OPTIMIZATIONS

> **Canonical:** [`JAX_Optimization.md`](./JAX_Optimization.md)

### Quick Reference — Critical Invariants

| Invariant | Enforcement |
|-----------|-------------|
| Physics gates always **fp32** | Validator gate path; no bf16 residual checks |
| Loss terms **boolean-enabled** | Static XLA graph; no Python branch per term |
| Hard step + wall-clock rails | Independent of miner-requested epochs |
| Determinism | Pinned lockfile + threefry + persistent XLA cache |
| Workload isolation | `lean_eval` must not be starved by `product_battery` |

Full design, code patterns, and phase rollout live in `JAX_Optimization.md`.

---

# 2. Physics Gates Implementation

Hard gates are fail-closed checks evaluated after train on hidden stress/eval draws.

**Typical gate families (challenge-specific Score Pack owns thresholds):**
- Finite / non-NaN fields
- Conservation residuals (mass, energy, momentum as applicable)
- PDE residual ceilings
- Short rollout stability
- Boundary / interface constraints where defined

**Rules:**
- Gates run in **fp32**
- Fail → combined lean score = 0 for emissions
- Gate definitions and thresholds are part of the versioned Score Pack (`Scoring.md`)
- Generator validation (dossier) is separate and must pass before a challenge goes live (`Generator_Validation.md`)

Implementation detail for residual operators and challenge packs: `Scoring.md` + challenge Score Pack YAML.

---

# 3. Procedural Generators

Generators produce train / eval / stress fields inside a declared envelope.

**Invariants (see `Data_Management.md`):**
- Train seeds ≠ eval seeds ≠ stress seeds
- Stress tensors never returned to miners
- Miner may influence train distribution params inside envelope only
- Challenge generator config is frozen for a live version

**Onboarding:** every new generator completes a Validation Dossier before LIVE (`Generator_Validation.md`).

---

# 4. Validator Training Pipeline (Lean)

```text
submission (strategy.json)
  → schema / allowlist check
  → derive train / eval / stress seeds
  → generate train data
  → JAX retrain from strategy (rails + precision policy)
  → hidden stress + eval
  → fp32 physics gates
  → Score Pack soft legs (if gates pass)
  → Model Card + lean score → emissions weights
```

**Skeleton reference:** `carbon/validator/training.py` patterns in `JAX_Optimization.md`.

**Not in lean path:** product battery (INV/ROLL/ADV/LAT), commercial ONNX export, full specialist distillation.

---

# 5. Landscape Agent Pipeline

Landscape consumes verified Model Cards and routes value through four ports (search, eval, economy, product). Canonical design: `Landscape_Agent.md`.

**Do not** implement Landscape as a score override. Gates remain protocol truth.

---

# 6. Miner Toolkit & SDK

Miner-facing loop: noisy prior → estimate → optional light train → submit.

Canonical contract: `Miner_MCP.md`.

---

# 7. Genesis Contracts

On-chain / subnet registration, challenge registry pointers, and emissions binding to lean scores. Keep genesis thin; pin Score Pack and generator versions in the Challenge Registry.

---

# 8. MCP Protocol

Agent-friendly tools for priors and local estimation. Priors are lagged, noisy, and redacted. Estimation never replaces the validator exam.

Canonical: `Miner_MCP.md`.

---

# 9. Reproducibility & Determinism

Canonical: `JAX_Optimization.md` (lockfile, threefry, XLA cache, fixture tests).

---

# 10. Operational Infrastructure

Canonical: `Operations.md` + queue / precision notes in `JAX_Optimization.md`.

**Job classes:** `lean_eval` (emissions), `bank_retrain`, `product_battery` (isolated capacity).

---

# 11–13. Julia/SciML Ground Truth Service

Canonical runtime contract: `Runtime_Julia_Truth_Oracle.md`.

**Phase 0–1A:** mock client acceptable. **1A+:** live service for reference solves / adjoints when gates require them.

Validators integrate via `SciMLClient`; oracle health is on the critical path when oracle checks are enabled.
