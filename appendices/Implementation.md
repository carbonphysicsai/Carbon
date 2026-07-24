# IMPLEMENTATION.md — Carbon Physics Intelligence Subnet

**Version:** 3.1 (July 2026)  
**Status:** Core Engineering Implementation Guide  
**Audience:** Harshdeep Sharma (Tech Lead) + Engineering Team  
**Purpose:** Build-level implementation details for components in `SPEC.md` — with Julia/SciML Ground Truth Oracle integration

---

# TABLE OF CONTENTS

1. [JAX Core Training Optimizations](#1-jax-core-training-optimizations) → **Canonical: [`JAX_Optimization.md`](./JAX_Optimization.md)**
2. [Physics Gates Implementation](#2-physics-gates-implementation)
3. [Procedural Generators](#3-procedural-generators)
4. [Validator Training Pipeline](#4-validator-training-pipeline)
5. [Landscape Agent Pipeline](#5-landscape-agent-pipeline)
6. [Miner Toolkit & SDK](#6-miner-toolkit--sdk)
7. [Genesis Contracts](#7-genesis-contracts)
8. [MCP Protocol](#8-mcp-protocol)
9. [Reproducibility & Determinism](#9-reproducibility--determinism) → **Canonical: [`JAX_Optimization.md`](./JAX_Optimization.md)**
10. [Operational Infrastructure](#10-operational-infrastructure) → **Queue/determinism/cache: [`JAX_Optimization.md`](./JAX_Optimization.md)** · **Ops: [`Operations.md`](./Operations.md)**
11. [Julia/SciML Ground Truth Service](#11-juliasciml-ground-truth-service)
12. [Python-Julia Bridge (SciMLClient)](#12-python-julia-bridge-scimlclient)
13. [Julia/SciML Service Deployment](#13-juliasciml-service-deployment)

---

# Document Ownership (Post-Consolidation)

| Concern | Canonical Document |
|---------|--------------------|
| JAX training loop, boolean loss masking, fp32 physics-gate precision, multi-fidelity curricula, gradient accumulation/checkpointing, model sharding, validator queue, determinism lockfile, XLA compilation cache | [`JAX_Optimization.md`](./JAX_Optimization.md) |
| Data generation architecture, seed hierarchy, train vs eval separation, stress categories, entropy floor, custom-dataset validation | [`Data_Management.md`](./Data_Management.md) |
| Physics gates (code), generators (high-level), Landscape Agent, Miner Toolkit, Genesis Contracts, MCP, SciML service | **This file** |
| Compute efficiency strategy & prioritization | [`Compute_Optimization.md`](./Compute_Optimization.md) |
| Day-to-day ops, K8s, monitoring, incident response | [`Operations.md`](./Operations.md) |
| High-level architecture, phases, commercial GTM | `SPEC.md` |

**Rule:** Do not re-copy large code blocks that already live in a specialized appendix. Link to the canonical source instead.

---

# 1. JAX CORE TRAINING OPTIMIZATIONS

> **Canonical source of truth: [`appendices/JAX_Optimization.md`](./JAX_Optimization.md)**
>
> All detailed designs, code, safety rails, and acceptance criteria for the following live **exclusively** in that document:
>
> - Unified loss masking with **explicit boolean flags** (zero recompilation)
> - Functional training loop via `jax.lax.scan` + hard step / wall-clock limits
> - Precision policy: **bfloat16 training + mandatory fp32 physics gates**
> - Mesh-independent multi-fidelity curricula (`spatial_resolution_scale`, `mode_budget_scale`)
> - Gradient accumulation + checkpointing (Phase 3–4)
> - Model sharding (ZeRO-3 style) for Phase 4
> - Validator queue management & prioritization
> - Determinism lockfile, XLA compilation cache persistence, and reproducibility harness
>
> **Do not duplicate these sections in this file.** Implementation work should reference and extend `JAX_Optimization.md`.

### Quick Reference — Critical Invariants

| Invariant | Enforcement |
|-----------|-------------|
| Physics gates run in **fp32** | `physics_precision_policy()` context manager |
| Loss masking uses **explicit booleans** | `enabled: bool` in schema (no fp thresholds) |
| Gradient clipping inside JIT | `optax.clip_by_global_norm` inside `@jax.jit` |
| Hard step + wall-clock limits | Independent of miner `epochs` |
| Determinism | Pinned lockfile + `threefry` + `CUBLAS_WORKSPACE_CONFIG=:4096:8` |

---

# 2. Physics Gates Implementation

*(Full gate catalogue and thresholds remain in SPEC.md. Implementation lives in `carbon/validator/physics_gates.py`.)*

Core Phase-0 gates (mass conservation, energy stability, boundary satisfaction, rollout stability, UQ calibration) and advanced gates (adjoint consistency via SciMLSensitivity.jl, turbulence/chemistry UQ, sequential FSI interface, coupling gates, 3D turbulence gates) are implemented as previously specified. All gate computations **must** run under the fp32 `physics_precision_policy()` defined in `JAX_Optimization.md`.

---

# 3. Procedural Generators

> Full data-generation architecture, seed hierarchy, training-vs-evaluation separation, stress categories, entropy floor, and custom-dataset validation live in **[`Data_Management.md`](./Data_Management.md)**.

High-level generator interface and phase-specific generators (Poisson, Compressible NS, Reacting NS, FSI, stress variants) remain under `carbon/generators/`.

---

# 4. Validator Training Pipeline

The official training path is owned by the validator. It must:

1. Derive seeds from `hash(challenge_id + block_hash + run_nonce)`
2. Generate training data (miner-influenced params allowed within envelope)
3. Train under the JAX optimizations defined in [`JAX_Optimization.md`](./JAX_Optimization.md)
4. Generate **hidden** stress variants (validator config only)
5. Run physics gates under **fp32**
6. Optionally validate against the Julia/SciML Ground Truth Oracle
7. Emit Model Card + score

```python
# carbon/validator/training.py (high-level skeleton)
class ValidatorTrainer:
    def __init__(self, config: Dict):
        self.config = config
        self.checkpointer = ocp.StandardCheckpointer()
        self.sciml_client = SciMLClient()

    async def evaluate_submission(self, submission, block_hash: str, run_nonce: int):
        master_seed = derive_master_seed(submission.challenge_id, block_hash, run_nonce)
        seeds = derive_pipeline_seeds(master_seed)

        # Training path (miner-influenced)
        train_data = generate_training_data_with_miner_params(...)
        state = self.create_train_state(...)
        state = self.train(state, train_data, submission.strategy)  # JAX_Optimization patterns

        # Evaluation path (validator-controlled, hidden)
        stress_data = generate_stress_variants(seed=seeds["stress_seed"], ...)
        gate_results = self._run_physics_gates(state, stress_data)  # fp32 enforced

        if self.config.get("sciml_validation", False):
            sciml_result = await self._sciml_validation(state, submission.strategy)

        return EvaluationResult(gate_results=gate_results, ...)
```

---

# 5. Landscape Agent Pipeline

```python
# carbon/landscape/pipeline.py
class LandscapeAgent:
    def __init__(self, config: Dict):
        self.pysr_config = config.get("pysr", PYSR_CONFIG)
        self.dml_config = config.get("dml", DML_CONFIG)
        self.mt_bridge = ModelingToolkitBridge()   # Julia bridge
        self.specialist_bank = SpecialistBank()
        self.prior_engine = PriorEngine()
        self.sciml_client = SciMLClient()

    def ingest_model_card(self, model_card): ...
    def _run_pysr(self): ...          # → structured losses via MT.jl
    def _run_dml(self): ...           # causal effects → guidance
    def get_noisy_prior(self, challenge: str, backbone: str): ...
```

ModelingToolkit.jl bridge and Double-ML configuration remain as previously specified.

---

# 6. Miner Toolkit & SDK

Miner Toolkit Docker image, CLI (`carbon-miner run / submit / pull-prior / doctor`), and the agent-friendly `CarbonMiner` / `AsyncCarbonMiner` SDK remain as previously specified. Local loops use Estimation Mode and Light Training; official scoring only occurs on Full Submission.

---

# 7. Genesis Contracts

`CarbonTreasury.sol`, `BountyPool.sol`, `VerificationRegistry.sol`, `VerificationGas.sol`, and `PartnerStaking.sol` remain as previously specified.

---

# 8. MCP Protocol

MCP message types, `MCPClient`, and convenience methods (`get_noisy_prior`, `submit_strategy`, `get_diagnostics`, `estimate`) remain as previously specified.

---

# 9. Reproducibility & Determinism

> **Canonical implementation:** [`JAX_Optimization.md`](./JAX_Optimization.md) (Determinism Lockfile, XLA Compilation Cache, Determinism Enforcement).

Summary requirements:
- Pinned `requirements-lock.txt` (JAX/jaxlib/Flax/Optax/…)
- `PYTHONHASHSEED=0`, `CUBLAS_WORKSPACE_CONFIG=:4096:8`, `jax_default_prng_impl="threefry"`
- Persistent compilation cache volumes
- 3-run reproducibility harness for critical paths

---

# 10. Operational Infrastructure

> **Canonical queue, timeout, and priority logic:** [`JAX_Optimization.md`](./JAX_Optimization.md) § Validator Queue Management.  
> **Day-to-day ops, K8s, monitoring, incident response:** [`Operations.md`](./Operations.md).

---

# 11–13. Julia/SciML Ground Truth Service

The Julia/SciML Ground Truth Oracle (DifferentialEquations.jl, ModelingToolkit.jl, SciMLSensitivity.jl, …), the Python `SciMLClient`, and deployment (Dockerfile, K8s, docker-compose) remain as previously specified.

**Key integration points:**
1. Physics Gates → Adjoint Consistency Gate via `SciMLSensitivity.jl`
2. Generators → validated against `DifferentialEquations.jl` reference solutions
3. Landscape Agent → `ModelingToolkit.jl` bridge for symbolic loss terms
4. Validators → `SciMLClient` for reference-solution validation

---

*This document is deliberately free of large duplicated code blocks that belong in the specialized appendices listed in the ownership table above.*
