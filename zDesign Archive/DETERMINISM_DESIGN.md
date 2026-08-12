# Determinism Design Specification

**Document:** `docs/DETERMINISM_DESIGN.md`
**Version:** 1.1
**Date:** July 2026
**Focus:** Full determinism guarantees across the Hydrogen evaluation pipeline

---

## 1. Purpose

Determinism is a foundational requirement for Phase 0. Without it, the system cannot credibly claim robustness, reproducibility, or auditability. Every evaluation run for the same submission on the same validator must produce identical results.

This document defines a rigorous, state-of-the-art approach to achieving **full pipeline determinism** in Hydrogen.

---

## 2. Scope

Determinism must cover the entire evaluation pipeline:

- Data loading and preprocessing
- Data augmentation (when used)
- Model training / fine-tuning
- Stress test generation and evaluation
- Physics gate computation
- Scoring and `ChallengeWinnerTracker` updates

Future extensions (preCICE coupling, Landscape Agent) must also respect determinism.

---

## 3. Sources of Non-Determinism

Modern ML frameworks and hardware introduce many sources of non-determinism:

| Source | Example | Impact |
|--------|---------|--------|
| PyTorch / JAX random ops | `torch.randn`, dropout, weight init | High |
| GPU operations | Atomic operations, cuDNN algorithms | High |
| Data loading order | Multiprocessing, shuffling | High |
| External libraries | NumPy, SciPy, custom CUDA kernels | Medium |
| System-level | CUDA version, cuDNN version, driver | Medium |
| Distributed training | NCCL, all-reduce order | High (if used) |

A SOTA determinism strategy must systematically close all these vectors.

---

## 4. Core Design Principles

| Principle | Requirement |
|-----------|-------------|
| **Hierarchical Seeding** | Every random operation must derive from a single, challenge-specific master seed. |
| **Framework-Level Control** | Use all available determinism flags in PyTorch/JAX. |
| **Container & Environment Pinning** | Pin CUDA, cuDNN, and library versions. |
| **Reproducibility Harness** | Provide a way to verify that a full run is deterministic. |
| **Auditability** | Any validator must be able to reproduce another validator’s results. |

---

## 5. Hierarchical Seeding Strategy (SOTA Approach)

We adopt a **hierarchical, challenge-bound PRNG key system** inspired by modern JAX practices and reproducible scientific computing.

### 5.1 Master Seed Derivation

```python
def get_master_seed(challenge_id: str, validator_hotkey: str) -> int:
    combined = f"{challenge_id}:{validator_hotkey}"
    return hash(combined) & 0xFFFFFFFF
```

### 5.2 Sub-Key Hierarchy

```python
master_seed = get_master_seed(challenge_id, validator_hotkey)

seeds = {
    "data_loading": hash(master_seed + "data"),
    "augmentation": hash(master_seed + "aug"),
    "training": hash(master_seed + "train"),
    "stress_generation": hash(master_seed + "stress"),
    "noise": hash(master_seed + "noise"),
}
```

Each subsystem receives its own sub-seed. This prevents cross-contamination and makes debugging easier.

### 5.3 JAX Best Practice (Recommended Long-Term)

For JAX-based backbones, use the modern PRNG key system:

```python
key = jax.random.PRNGKey(master_seed)
key, subkey = jax.random.split(key)
```

This is considered state-of-the-art for reproducible scientific ML.

### 5.4 PyTorch Determinism Flags

```python
import torch

torch.manual_seed(seed)
torch.cuda.manual_seed_all(seed)
torch.use_deterministic_algorithms(True)
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False
```

Note: `use_deterministic_algorithms(True)` can reduce performance. This is acceptable for evaluation determinism.

---

## 6. Data Loading & Augmentation Determinism

- Use `torch.Generator` with explicit seeds for all `DataLoader` shuffling.
- Fix multiprocessing worker seeds.
- Make augmentation pipelines (if used) fully deterministic by seeding every random transform.
- Prefer deterministic alternatives to non-deterministic operations (e.g., avoid `torch.rand` in favor of seeded generators).

---

## 7. External Library & System Determinism (Gap Fill)

### 7.1 NumPy / SciPy

```python
import numpy as np

np.random.seed(sub_seed)
```

All NumPy random operations must be explicitly seeded from the hierarchy.

### 7.2 Custom CUDA Kernels (Future)

Any custom CUDA kernels must be compiled with deterministic flags and avoid atomic operations where possible. Their behavior must be validated in the Reproducibility Harness.

### 7.3 Future preCICE / External Solver Determinism

preCICE and coupled solvers introduce significant non-determinism risks (communication order, floating-point reductions, solver internal randomness). For Phase 2+ we will:

- Pin solver versions and random seeds inside each specialist container.
- Record all solver configuration in the evaluation provenance.
- Accept small floating-point tolerance in cross-validator audits for coupled runs.

### 7.4 Floating-Point Tolerance Strategy

For audit purposes we define two tiers:

- **Bit-level reproducibility** (same validator, same hardware): Must be exact.
- **Cross-validator audit** (different hardware): Accept small tolerance (e.g., `1e-6` relative) on final scores only. All intermediate tensors should still match within tolerance.

Tolerance values and comparison logic will be implemented in the Reproducibility Harness.

---

## 8. Environment & Full Provenance (Gap Fill)

Every evaluation run must record:

- Docker image digest
- Python version + exact package versions (`pip freeze` or `conda list`)
- CUDA driver + runtime version
- cuDNN version
- Host OS + architecture
- Git commit hash of the validator code

This information is stored alongside the evaluation result and can be used during audits to detect environment-induced non-determinism.

---

## 9. Reproducibility Harness (Detailed Design)

The `ReproducibilityHarness` will:

1. Run a submission twice (or across two validators).
2. Compare:
   - Final scores and gate outcomes
   - Stress evaluation results
   - Intermediate tensor statistics (mean, std, max) for key layers
3. Report any deviation above defined tolerance.
4. Log full environment provenance.

This harness will be used both in development CI and for validator-to-validator audits.

---

## 10. Integration with Stress Testing

The stress generation system (see `docs/STRESS_TEST_DESIGN.md`) must use the same master seed hierarchy. This ensures that stress conditions themselves are deterministic and auditable.

---

## 11. Success Criteria

| Criterion | Target |
|-----------|--------|
| Same submission, same validator → identical scores | 100% |
| Same submission, different validator (same image) → identical scores | 100% |
| Full pipeline reproducibility test passes | Yes |
| All random operations derive from challenge-specific seed | Yes |
| Environment is fully recorded per evaluation | Yes |
| Floating-point tolerance policy defined and implemented | Yes |

---

## 12. Phased Rollout

| Phase | Scope | Notes |
|-------|-------|-------|
| Phase 0 | Core pipeline (data, training, scoring, basic stress) | Must be solid |
| Phase 1 | Add preCICE / multi-physics runs | Higher complexity |
| Phase 2+ | Advanced adversarial stress generation | Requires careful seeding |

---

## 13. Summary

This updated design closes the major practical gaps:

- External library control
- Floating-point tolerance strategy
- Full environment provenance
- Concrete Reproducibility Harness
- Future preCICE considerations

Combined with the stress test design, this gives Hydrogen one of the strongest determinism and auditability guarantees among decentralized evaluation systems.

---

*This document should be treated as the authoritative reference for determinism in Hydrogen and updated as implementation evolves.*
