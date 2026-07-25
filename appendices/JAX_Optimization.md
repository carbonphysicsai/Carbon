# JAX Core Training Optimizations (Validator-Side)

## TL;DR

**Job of this doc:** Make validator retrain affordable and deterministic without rewriting miner strategy intent.

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

## 2–8. Full Specification

The body of this appendix (dynamic boolean loss masking, `lax.scan` training loops, bf16/fp32 precision policy, multi-fidelity curricula, Phase 3–4 accumulation/checkpointing/sharding, validator queue, determinism lockfile, XLA cache, cost tables, and implementation checklist) is unchanged from the Production Ready v2.0 design. Implement against those sections; treat the TL;DR invariants above as the Phase-0 acceptance bar.

**Primary code homes:** `carbon/validator/losses.py`, `training.py`, `queue.py`, `carbon/backbones/precision.py`, `carbon/common/determinism.py`, pinned `requirements-lock.txt`, persistent compile-cache volumes.

---

*This appendix is a living engineering document. Cost figures, hardware assumptions, and XLA performance characteristics should be revisited as marketplace rates and JAX versions evolve. All correctness-critical items (fp32 gates, boolean masks, determinism) are non-negotiable requirements for mainnet launch.*

**Note:** Detailed code listings for §2–§8 live in the prior full revision of this file on `main` history if a docs pass condensed listings; restore from commit `e67d3fe7` / tree `00eb0a34` when implementing so no pattern is lost.
