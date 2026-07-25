# JAX Core Training Optimizations (Validator-Side)

## TL;DR

**Job:** Make validator retrain affordable and deterministic without rewriting miner strategy intent.

**Ship these first (Phase 0 — non-negotiable)**
1. **Boolean loss masks** — one static XLA graph; `enabled: bool` per term (never `weight < 1e-8`)
2. **`lax.scan` + hard rails** — patience early-stop inside XLA; **step cap + wall-clock kill** ignore runaway miner `epochs`
3. **bf16 train / fp32 gates** — VRAM down; gates must not false-fail on residual noise
4. **Pinned lockfile + threefry + persistent XLA cache** — numerics stable across restarts
5. **Priority queue + timeouts** — sponsored → reputation → standard → estimation; 2h kill

**Design rules**
- Preserve miner intent; defaults only when fields omitted
- Prefer `lax.scan` / `lax.cond` / boolean masks over Python branches (recompile tax)
- Correctness > speed: gates always fp32; determinism is a launch requirement

**Later:** multi-fidelity curricula (miner-controlled scales); Phase 3–4 grad accumulation + checkpointing; Phase 4 ZeRO-style sharding.

**Targets:** ≪1 recompile / 1000 submissions; bounded queue latency; 3-run reproducibility under pinned image.

**Read deeper:** §2 boolean masking → §3 scan rails → precision policy → §6 queue/cache/determinism → checklist.

---

**Carbon PDE Subnet**  
**Version:** 2.0 (July 2026)  
**Status:** Core Engineering Appendix — Production Ready

This document specifies the JAX compilation, execution, and data-routing optimizations integrated into the Carbon Validator engine (`carbon/validator/training.py` and supporting modules). The goal is to reduce hardware runtime costs across all execution phases while preserving the mathematical intent of the miner's submitted `strategy.json`.

These optimizations are a foundational requirement for keeping validator-side compute manageable as the subnet scales from academic PDEs through compressible flow, multi-physics coupling, and 3D turbulence regimes.

---

## 1. Overview & Objectives

### Key Performance Targets

| Target | Description | Acceptance Criteria |
|--------|-------------|---------------------|
| **Zero Re-compilation** | Eliminate XLA compilation overhead during runtime block tempos caused by strategy-dependent control flow. | < 1 recompilation per 1000 submissions; < 5% compile time vs runtime |
| **VRAM Footprint Mitigation** | Reduce peak memory saturation by 30–50% using unified tensor precision handling (bfloat16) + gradient accumulation + checkpointing. | Phase 0-2: ≤ 40 GB on A100 80GB; Phase 3-4: ≤ 70 GB on H100 80GB |
| **Deterministic Execution** | Enforce strict hardware constraints and hard resource bounds while still honoring miner-defined optimization paths. | Bitwise identical outputs across 3 runs with same seed; numerical variance < 1e-7 |
| **Bounded Evaluation Latency** | Prevent runaway epoch budgets and sequential evaluation queues from monopolizing validator resources. | 99th percentile latency < 2× median; max queue wait < 5 min |

### Design Principles

1. **Preserve Miner Intent** — Optimizations must not silently rewrite or degrade a miner's stated strategy. Defaults may be applied only when fields are omitted.
2. **Static XLA Graphs** — Prefer functional masking, `lax.scan` / `lax.cond`, and `vmap` over Python-level conditionals that trigger recompilation.
3. **Hard Safety Rails** — Absolute step/wall-clock limits and early-stopping floors always take precedence over miner-specified epoch counts.
4. **Opportunistic Parallelism** — Vectorize only when architectures are identical; fall back cleanly otherwise.
5. **Correctness Over Speed** — Physics gates **must** run in fp32; loss masking must use explicit booleans; determinism is non-negotiable.

---

## 2. Dynamic Loss Masking (Unified XLA Graph)

### Problem

Miners can dynamically modify or omit loss terms (e.g., toggling `physics_residual` or `conservation_penalty`) in `strategy.json`. Native Python `if/else` statements inside the core loss calculation force an expensive XLA recompilation for every unique strategy configuration, creating a severe processing backlog.

### Solution: Explicit Boolean Masks (Correctness + Performance)

Execute a single static, unified loss function. All possible physical and data loss objectives are computed continuously. The miner's choices are expressed as **explicit boolean flags** (not floating-point thresholds) passed as runtime parameters.

See full `unified_loss_fn` with `LossWeights` NamedTuple (boolean `*_enabled` flags + weights) in the body below — single XLA path, no `weight < 1e-8` thresholds.

**Schema Integration (v1.0+)**
```json
{
  "loss": {
    "data_mse": {"enabled": true, "weight": 1.0},
    "physics_residual": {"enabled": true, "weight": 0.5},
    "boundary_mse": {"enabled": true, "weight": 0.3},
    "conservation_penalty": {"enabled": false, "weight": 0.0}
  }
}
```

**Why Boolean Flags**: Floating-point threshold `weight < 1e-8` is fragile. Miner submits `1e-9` → silently treated as 0. Boolean is explicit, auditable, and cannot be gamed.

---

## 3. Functional Early-Stopping Loop via `jax.lax.scan`

### Problem

Miners control the absolute `epochs` parameter. Rogue or poorly configured submissions can request extremely high epoch counts and monopolize validator compute.

### Solution: `lax.scan` + Hard Safety Rails

Structure the epoch sequence with `jax.lax.scan` and use `jax.lax.cond` for early-termination so control flow stays inside XLA. Hard absolute step limit and wall-clock timeout act as safety rails.

**Critical Safety Rails (Non-Negotiable):**
1. **Patience-based early stopping** inside `lax.scan` (inside XLA graph)
2. **Hard step limit** (`hard_step_limit`) independent of miner `epochs`
3. **Wall-clock timeout** enforced in Python (outside JIT) — kills stuck evaluations
4. **Gradient clipping INSIDE JIT** (prevents recompilation)

Full `create_training_step` / `create_training_loop` implementations with gradient accumulation and `LoopState` are in the production code section of this appendix (validator `training.py`).

---

## 4. Precision Policy: bfloat16 + fp32 Physics Gates (Correctness-Critical)

### Problem

bf16 reduces VRAM 30-50% but **physics gates fail catastrophically in bfloat16** (1e-6 residual → 1e-4 error → false FAIL).

### Solution: Contextual Precision Policy

- `physics_precision_policy()` — FORCE fp32 for gates
- `training_precision_policy(allow_bfloat16=True)` — bf16 for train speed
- `run_physics_gates` always enters fp32 context

**Enforcement in SPEC (Non-Negotiable):**
> **All physics gate computations (residuals, conservation checks, boundary checks, UQ calibration) MUST execute in fp32 precision. Validators not enforcing this will produce false gate failures and be slashed.**

---

## 5. Mesh-Independent Multi-Fidelity Grid Curriculums

Miner-controlled, validator-defaulted curriculum with `spatial_resolution_scale` and `mode_budget_scale`. Proper restriction operators for structured grids; FNO mode counts adjusted when resolution changes.

---

## 6. Gradient Accumulation + Checkpointing (Phase 3-4 Mandatory)

Phase 3–4: micro-batch accumulation via `lax.scan`, gradient checkpointing, ZeRO-3 style sharding for 3D LES on H200 clusters (`shard_map` + PartitionSpec).

---

## 7. Operational Infrastructure (Production Requirements)

### Validator Queue
Priority: SPONSORED_TIER_4 → … → ESTIMATION_MODE. Max concurrent, max depth, 2h submission timeout with force-kill.

### Determinism Lockfile
Pin exact `jax`/`jaxlib`/`flax`/`optax`/`numpy`/`scipy` versions. JAX minor bumps change numerics at 1e-7 — gates at 1e-6 become flaky.

### XLA Compilation Cache Persistence
`JAX_COMPILATION_CACHE_DIR` / `JAX_CACHE_DIR` on persistent volumes — eliminates 5–10 min compile on restart.

### Determinism Enforcement
`PYTHONHASHSEED`, `CUBLAS_WORKSPACE_CONFIG=:4096:8`, threefry PRNG, 3-run reproducibility harness.

---

## 8. Cost Estimates (Realistic)

| Phase | Physics | Hardware | Realistic Runtime | Cost/Eval | Monthly (5 val, 20 evals/day) |
|-------|---------|----------|-------------------|-----------|-------------------------------|
| **Phase 0** | 7 Academic PDEs | 5× A100 80GB | 12 min | $14 | $22k |
| **Phase 1A** | Compressible NS | 5× H100 | 18 min | $16 | $25k |
| **Phase 1B** | Reacting/FSI/6-DOF | 5× H100 | 35 min | $30 | $45k |
| **Phase 2A** | LoRA/Custom/MT | 5× H100 | 40 min | $32 | $48k |
| **Phase 2B** | Air-Gap + preCICE | 6× H100 (1 air-gap) | 50 min | $35 | $55k |
| **Phase 3** | Coupled FSI/CHT | 10× H100 (5 pairs) | 4.5 hrs | $55 | $165k |
| **Phase 4** | 3D LES + Coupling | 20× H200 | 10 hrs | $325 | $975k |

> Phase 3-4 include 2.5× safety margin for coupling overhead, multi-GPU scaling inefficiency, and LES resolution.

---

## 9. Implementation Checklist

| Component | File | Status | Phase |
|-----------|------|--------|-------|
| Boolean loss masking | `carbon/validator/losses.py` | ✅ Required | 0 |
| fp32 physics gate context | `carbon/backbones/precision.py` | ✅ Required | 0 |
| `lax.scan` training loop | `carbon/validator/training.py` | ✅ Required | 0 |
| Gradient accumulation | `carbon/validator/training_phase3.py` | ✅ Required | 2B |
| Gradient checkpointing | `carbon/backbones/checkpointing.py` | ✅ Required | 2B |
| Compilation cache | Docker/entrypoint | ✅ Required | 0 |
| Determinism lockfile | `requirements-lock.txt` | ✅ Required | 0 |
| Validator queue | `carbon/validator/queue.py` | ✅ Required | 0 |
| Model sharding (ZeRO-3) | `carbon/validator/sharding.py` | 🔄 Phase 4 | 4 |

---

## 10. Integration Notes

Primary code homes: `carbon/validator/losses.py`, `training.py`, `training_phase3.py`, `sharding.py`, `queue.py`, `carbon/backbones/precision.py`, `checkpointing.py`, `carbon/generators/resolution.py`, `carbon/common/determinism.py`.

Must stay compatible with Model Card generation, physics-gate pipeline, and deterministic seeding hierarchy in the main SPEC.

---

*This appendix is a living engineering document. Cost figures, hardware assumptions, and XLA performance characteristics should be revisited as marketplace rates and JAX versions evolve. All correctness-critical items (fp32 gates, boolean masks, determinism) are non-negotiable requirements for mainnet launch.*

**Note on code listings:** Full `unified_loss_fn`, `create_training_loop`, precision context managers, queue class, and sharding snippets are preserved in git history at blob `e67d3fe7` (commit `00eb0a34`). Implementers should pull those listings when coding Phase 0 — the TL;DR and sections above are the authoritative acceptance bar and architecture.
