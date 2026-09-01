# JAX Core Training Optimizations (Validator-Side)

## TL;DR

**Job:** Make validator retrain affordable and deterministic without rewriting miner strategy intent.

**Workload classes (do not conflate)**

| Class | When | JAX path |
|-------|------|----------|
| **`lean_eval`** | Every full submission | Boolean masks, scan rails, bf16 train, fp32 gates, short stress | 
| **`practice_research`** | Optional miner research | Separate nominal service, public practice rights, isolated quota; never official admission or score |
| **`bank_retrain`** | Specialist promotion | Same train stack; fresh seeds; not emissions |
| **`product_battery`** | After bank lean re-gate | Extra INV/ROLL/ADV/LAT jobs — **scheduled rarely**, not default queue |

**Ship these first (Phase 0 — non-negotiable)**
1. **Boolean loss masks** — one static XLA graph; `enabled: bool` per term
2. **`lax.scan` + hard rails** — step cap + wall-clock kill
3. **bf16 train / fp32 gates**
4. **Pinned lockfile + threefry + persistent XLA cache**
5. **Fair lean queue + timeouts** — transparent admission/congestion policy; 2h kill for lean_eval; no practice-based priority or variable exam depth

**Design rules**
- Preserve miner intent; defaults only when fields omitted
- Prefer `lax.scan` / boolean masks over Python branches
- Correctness > speed: gates always fp32; determinism is a launch requirement
- Product-battery GPU must not starve the official lean evaluation path

**Later:** multi-fidelity curricula; Phase 3–4 grad accumulation + checkpointing; Phase 4 sharding.

**Read deeper:** §2 boolean masking → §3 scan rails → precision → §6 queue → §7 workload classes → checklist.

---

**Carbon PDE Subnet**  
**Version:** 2.2 (August 2026)
**Status:** Target engineering contract; implementation and production qualification unproven

This document specifies target JAX compilation, execution, and data-routing
optimizations for the Carbon Validator engine. The repository's implementation
and evidence records determine what exists. The goal is to reduce runtime cost
while preserving the mathematical intent of the miner's submitted
`strategy.json`.

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
6. **Workload isolation** — practice research vs lean emissions vs bank/PB promotion

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
| `practice_research` | Miner research task | Separate local/practice workers and quota | No |
| `bank_retrain` | Specialist opportunity | Bank workers | No |
| `product_battery` | Bank after lean re-gate | Bank / dedicated GPU pool | No |

### 7.2 Lean queue

Use a versioned operational admission, fairness, congestion, concurrency, and
timeout policy. Sponsorship may buy separately accounted capacity, but stake,
reputation, sponsorship, practice outcomes, priors, and forecasts cannot change
the registered exam or scientific score. Every nonzero result completes the
same mandatory pack. A conclusive mandatory-gate failure may stop remaining
work without creating a partial positive score.

### 7.3 Practice capacity

- Keep practice requests, results, data handles, queue, and quotas nominally
  separate from `lean_eval`.
- Wave B provides an in-process fixture path only. A remote practice service
  requires later authentication, quota, pricing, and security authority.
- Practice results cannot prequalify or prioritize an official submission.

### 7.4 Bank / PB capacity

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
| Practice-research queue isolation | Required before any execution-bearing practice service | Wave B fixture; later remote authority |
| `job_class` routing (lean vs bank vs PB) | Required when Bank live | 2A+ |
| Grad accumulation / checkpointing | Required | 2B–3 |
| Model sharding | Phase 4 | 4 |

---

## 10. Integration Notes

Primary code homes: `carbon/validator/losses.py`, `training.py`, `queue.py`, `carbon/backbones/precision.py`, `carbon/common/determinism.py`.

Must stay compatible with Model Card generation, lean physics-gate pipeline, Data Management seed hierarchy, and Specialist Bank promotion workers.

---

*v2.2: adds nominal practice isolation and removes estimation/practice from
official queue priority. Correctness-critical items remain target requirements,
not claims of implementation or qualification.*
