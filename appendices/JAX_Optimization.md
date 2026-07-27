# JAX Core Training Optimizations (Validator-Side)

## TL;DR

**Job:** Make validator retrain affordable and deterministic without rewriting miner strategy intent.

**Workload classes (do not conflate)**

| Class | When | JAX path |
|-------|------|----------|
| **`lean_eval`** | Every full submission | Boolean masks, scan rails, bf16 train, fp32 gates, short stress | 
| **`bank_retrain`** | Specialist promotion | Same train stack; fresh seeds; not emissions |
| **`product_battery`** | After bank lean re-gate | Extra INV/ROLL/ADV/LAT jobs — **scheduled rarely**, not default queue |

**Ship these first (Phase 0 — non-negotiable)**
1. **Boolean loss masks** — one static XLA graph; `enabled: bool` per term
2. **`lax.scan` + hard rails** — step cap + wall-clock kill
3. **bf16 train / fp32 gates**
4. **Pinned lockfile + threefry + persistent XLA cache**
5. **Priority queue + timeouts** — sponsored → reputation → standard → estimation; 2h kill for lean_eval

**Design rules**
- Preserve miner intent; defaults only when fields omitted
- Prefer `lax.scan` / boolean masks over Python branches
- Correctness > speed: gates always fp32; determinism is a launch requirement
- Product-battery GPU must not starve lean emissions path

**Later:** multi-fidelity curricula; Phase 3–4 grad accumulation + checkpointing; Phase 4 sharding.

**Read deeper:** §2 boolean masking → §3 scan rails → precision → §6 queue → §7 workload classes → checklist.

---

**Carbon PDE Subnet**  
**Version:** 2.1 (July 2026)  
**Status:** Core Engineering Appendix — Production Ready

This document specifies the JAX compilation, execution, and data-routing optimizations integrated into the Carbon Validator engine. Goal: reduce hardware runtime costs while preserving the mathematical intent of the miner's submitted `strategy.json`.

---

## 1. Overview & Objectives

### Key Performance Targets

| Target | Acceptance Criteria |
|--------|---------------------|
| **Zero Re-compilation** | < 1 recompilation per 1000 lean submissions |
| **VRAM Footprint** | Phase 0–2 ≤ 40 GB on A100 80GB class |
| **Deterministic Execution** | 3-run reproducibility under pinned image |
| **Bounded lean latency** | Hard step + wall-clock; queue timeouts |
| **PB isolation** | Product-battery jobs cannot block lean_eval SLO |

### Design Principles

1. **Preserve Miner Intent**  
2. **Static XLA Graphs**  
3. **Hard Safety Rails**  
4. **Opportunistic Parallelism**  
5. **Correctness Over Speed** — physics gates **must** run in fp32  
6. **Workload isolation** — lean emissions path vs bank/PB promotion path

---

## 2. Dynamic Loss Masking (Unified XLA Graph)

Explicit boolean flags per loss term; single static unified loss; never `weight < 1e-8` as enable logic. Schema uses `enabled: bool` + weight.

---

## 3. Functional Early-Stopping Loop via `jax.lax.scan`

Hard step limit and wall-clock timeout independent of miner `epochs`. Gradient clipping inside JIT.

---

## 4. Precision Policy: bfloat16 + fp32 Physics Gates

- Train may use bf16  
- **All lean physics gate computations in fp32**  
- Product-battery numeric checks likewise fp32 for pass/fail claims  

---

## 5. Mesh-Independent Multi-Fidelity Grid Curriculums

Miner-controlled `spatial_resolution_scale` / `mode_budget_scale` with validator defaults.

---

## 6. Gradient Accumulation + Checkpointing (Phase 3–4)

As previously specified for large multiphysics / 3D regimes.

---

## 7. Workload Classes & Queue Policy

### 7.1 Classes

| `job_class` | Producer | Consumer | Counts toward emissions? |
|-------------|----------|----------|---------------------------|
| `lean_eval` | Miner full submission | Validator workers | **Yes** |
| `bank_retrain` | Specialist opportunity | Bank workers | No |
| `product_battery` | Bank after lean re-gate | Bank / dedicated GPU pool | No |

### 7.2 Lean queue (production)

Priority: SPONSORED_TIER_4 → … → ESTIMATION_MODE. Max concurrent, max depth, ~2h submission timeout with force-kill.

### 7.3 Bank / PB capacity

- Schedule on separate pool or off-peak quota  
- Hard GPU-second budget per promotion candidate  
- Failure returns `promotion_outcome` to Landscape; does not zero miner lean score  

### Determinism Lockfile & XLA Cache

Pin `jax`/`jaxlib`/`flax`/`optax`/`numpy`/`scipy`. Persistent `JAX_COMPILATION_CACHE_DIR`. threefry PRNG; `CUBLAS_WORKSPACE_CONFIG=:4096:8`.

---

## 8. Cost Estimates (Realistic)

Phase cost tables remain guidance for **lean_eval** density. Add **10–20%** headroom in planning for occasional bank_retrain/PB once Specialist Bank is live — do not bake PB into per-submission unit cost.

| Phase | Physics | Hardware | Lean runtime order | Monthly lean-centric (order-of-magnitude) |
|-------|---------|----------|--------------------|---------------------------------------------|
| **Phase 0** | Academic PDEs | A100 class | ~10–20 min | ~$20k-scale |
| **Phase 1A–2B** | Compressible → air-gap | H100 class | grows with physics | scale with challenge mix |
| **Phase 3–4** | Coupled / 3D | multi-GPU | hours | plan 2–3× safety margin |

---

## 9. Implementation Checklist

| Component | Status | Phase |
|-----------|--------|-------|
| Boolean loss masking | Required | 0 |
| fp32 physics gate context | Required | 0 |
| `lax.scan` training loop | Required | 0 |
| Compilation cache + determinism lockfile | Required | 0 |
| Lean validator queue | Required | 0 |
| `job_class` routing (lean vs bank vs PB) | Required when Bank live | 2A+ |
| Grad accumulation / checkpointing | Required | 2B–3 |
| Model sharding | Phase 4 | 4 |

---

## 10. Integration Notes

Primary code homes: `carbon/validator/losses.py`, `training.py`, `queue.py`, `carbon/backbones/precision.py`, `carbon/common/determinism.py`.

Must stay compatible with Model Card generation, lean physics-gate pipeline, Data Management seed hierarchy, and Specialist Bank promotion workers.

---

*v2.1: explicit workload classes so product battery never pretends to be a per-submission JAX cost. Correctness-critical items (fp32 gates, boolean masks, determinism) remain non-negotiable.*
