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
| Physics gates run in **fp32** | `physics_precision_policy()` |
| Loss masking uses **explicit booleans** | `enabled: bool` in schema |
| Gradient clipping inside JIT | `optax.clip_by_global_norm` inside `@jax.jit` |
| Hard step + wall-clock limits | Independent of miner `epochs` |
| Determinism | Pinned lockfile + `threefry` + CUBLAS workspace |

---

# 2. Physics Gates Implementation

*(Catalogue and phase thresholds: `SPEC.md`. Code: `carbon/validator/physics_gates.py`.)*

**Lean path (every full submission) — Phase 0 core**

| Gate family | Role |
|-------------|------|
| Mass / energy / boundary | Hard physics |
| Finite / NaN | Hard |
| **Short rollout stability** | Cheap multi-step signal — **not** full HIL-horizon plant suite |
| Regime gates (shock, species, coupling, …) | As challenge requires |

**UQ policy (aligned with SPEC)**

- **Lean path Phase 0–1A:** do **not** treat universal conformal UQ as a hard gate on every submission. Stress margins + residual/conservation gates carry the physics claim.
- **Regime model-form UQ** (turbulence/chemistry budgets) applies when those challenges are live (1A/1B+).
- **Product / specialist tier:** KPI conformal or ensemble bands when `product_jobs` include UQ or safety-margin claims (`Specialist_Bank.md` PB path).

All gate math **must** run under fp32 `physics_precision_policy()` from `JAX_Optimization.md`.

**Product battery gates** (PB-INV, PB-ROLL deep, PB-ADV, PB-LAT, PB-ART, PB-ESC) are **not** implemented as default validator scoring hooks — they run on Specialist Bank promotion workers. See `Specialist_Bank.md`.

---

# 3. Procedural Generators

> Full architecture: [`Data_Management.md`](./Data_Management.md).

High-level generators live under `carbon/generators/`. Bank/PB draws must use **separate seed material** from lean eval/stress when feasible (decontamination).

---

# 4. Validator Training Pipeline (Lean)

Official **emissions** path — every full submission:

1. Derive seeds from `hash(challenge_id + block_hash + run_nonce)`
2. Generate training data (miner params within envelope)
3. Train under JAX patterns in `JAX_Optimization.md`
4. Hidden stress (validator config only)
5. fp32 physics gates + short rollout
6. Optional SciML oracle checks
7. Emit Model Card + lean score → Landscape ingest (D1)

```python
# carbon/validator/training.py (skeleton)
async def evaluate_submission(self, submission, block_hash: str, run_nonce: int):
    master_seed = derive_master_seed(...)
    seeds = derive_pipeline_seeds(master_seed)
    train_data = generate_training_data_with_miner_params(...)
    state = self.train(state, train_data, submission.strategy)
    stress_data = generate_stress_variants(seed=seeds["stress_seed"], ...)
    gate_results = self._run_physics_gates(state, stress_data)  # fp32, lean set
    return EvaluationResult(gate_results=gate_results, model_card=...)
```

Do **not** call full product battery from this path.

---

# 5. Landscape Agent Pipeline

> **Canonical:** [`Landscape_Agent.md`](./Landscape_Agent.md) v1.1+

Implementation responsibilities here are **glue only**:

| Component | Behavior |
|-----------|----------|
| Card ingest | Queue Model Cards from lean evals |
| Prior pack publisher | **Noisy + lagged** scaffolds, masks, diagnostics |
| Opportunity ranker | Feeds Specialist Bank queue (effects, not winner weights) |
| Promotion outcome ingest | D11 PB pass/fail → graph |
| Eval signals | **Private** validator RPC only |

```python
class LandscapeAgent:
    def ingest_model_card(self, model_card): ...
    def get_noisy_prior(self, challenge: str, backbone: str): ...  # never full SKU
    def rank_opportunities(self): ...  # → bank queue
    def ingest_promotion_outcome(self, pb_result): ...
```

**Forbidden:** export full specialist weights on miner API; override gates; sell eval outcomes.

Specialist construction / product battery: [`Specialist_Bank.md`](./Specialist_Bank.md).

---

# 6. Miner Toolkit & SDK

Docker image, CLI (`carbon-miner run / submit / pull-prior / doctor`), Estimation / Light / Full modes as in SPEC.

**Prior pull contract:** `pull-prior` / MCP `get_noisy_prior` returns **noisy derivatives only**. Never ONNX, exact bank recipe, or PB seeds.

---

# 7. Genesis Contracts

Treasury, bounty, verification registry, verification gas, partner staking — as previously specified. Registry may attest lean cards and later PB certs; attestation ≠ free SKU download.

---

# 8. MCP Protocol

Message types: `get_noisy_prior`, `submit_strategy`, `get_diagnostics`, `estimate`.

| Method | Returns |
|--------|--------|
| `get_noisy_prior` | Noisy scaffold + masks + optional sparse bands |
| `get_diagnostics` | Tiered failure labels (black-box) |
| `estimate` | Proxy score from noisy prior — not official score |
| `submit_strategy` | Queue for lean validator path |

No MCP method serves full `specialist_bank_item`.

---

# 9. Reproducibility & Determinism

> **Canonical:** [`JAX_Optimization.md`](./JAX_Optimization.md)

Pinned lockfile, threefry, persistent XLA cache, 3-run harness.

---

# 10. Operational Infrastructure

> Queue / timeouts: [`JAX_Optimization.md`](./JAX_Optimization.md)  
> Day-to-day ops: [`Operations.md`](./Operations.md)

**Job classes (must not share budgets blindly):**

| Class | Trigger | Notes |
|-------|---------|-------|
| `lean_eval` | Full submission | Default queue; emissions path |
| `bank_retrain` | Opportunity promote | Controlled retrain |
| `product_battery` | After lean re-gate on candidate | Rare; INV/ROLL/ADV/LAT/ART |

---

# 11–13. Julia/SciML Ground Truth Service

DifferentialEquations.jl / ModelingToolkit.jl / SciMLSensitivity.jl via `SciMLClient` — reference solves, adjoint checks, symbolic loss bridge. Deployable public and air-gapped as previously specified.

**Integration points:** gates (adjoint), generators (reference), Landscape (MT bridge), validators (optional oracle).

---

*v3.2: dual threshold, UQ phasing, Landscape ports, noisy-only MCP, job classes. Large designs live in the ownership-table appendices.*
