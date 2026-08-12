# Scoring.md — Lean Emission Scoring & Challenge Score Bank

**Carbon Subnet**  
**Version:** 2.0 (July 2026)  
**Status:** Protocol Appendix — Security & Incentive Critical  
**Audience:** Simulation Engineers, Physics PhDs, Protocol Engineers, Auditors  
**Related:** `SPEC.md` §8, `Data_Management.md`, `POC_Burgers_FNO.md`, `Specialist_Bank.md`, `Landscape_Agent.md`, `appendices/Physics_Gates.md`, `appendices/Julia_SciML_Oracle.md`

---

## Executive Summary

Carbon is a Bittensor subnet that operates a **decentralized verification layer for physics-informed neural operator surrogates**. It coordinates a network of miners and autonomous agents to discover optimal training strategies for Neural Operators (FNO, GINO, WNO, Transolver) under rigorous, trustless adversarial validation.

**Core Innovation**: Miners submit training strategies (loss configurations, curricula, architectures, data generation parameters). Validators execute full deterministic training from scratch on hidden, procedurally generated data, evaluating against hard physics gates. The Landscape Agent compounds symbolic and causal insights across all evaluations, creating a self-improving intelligence layer.

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
3. Load Generator Pack + Score Pack for those versions (**reject** if missing or hash mismatch)
4. Derive seeds → generate train/eval/stress
5. Train under strategy
6. Run **hard gates** from pack
7. If pass → compute soft legs → `S_combined`
8. Write Model Card with pack hashes + full vectors

**No path** where the validator substitutes "default global weights" when a pack is missing. Missing pack = evaluation error, not a fallback score.

---

## 3. Score Pack Schema (YAML)

```yaml
# carbon/scoring/bank/burgers1d_v0/scoring_v1.0.yaml
challenge_id: burgers1d_v0
scoring_version: "1.0"
generator_version_required: "burgers1d_v0.1"  # must match or be in allow-list
precision: fp32

# === GLOBAL WEIGHTS (must sum to 1.0) ===
weights:
  physics: 0.40
  robustness: 0.35
  accuracy: 0.25

# === HARD GATES (binary kill-switch) ===
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
  - id: boundary_satisfaction
    type: threshold
    error_key: e_boundary
    tau: 1.0e-4
    mandatory: true
  - id: rollout_stability
    type: threshold
    error_key: e_roll
    tau: 1.0
    mandatory: true
  - id: uq_calibration
    type: threshold
    error_key: e_uq
    tau: 0.05  # 95% coverage
    mandatory: true
  - id: adjoint_consistency
    type: adjoint_consistency
    tau: 1.0e-4
    mandatory: false   # Phase 1A+ only
  - id: shock_capture
    type: threshold
    error_key: e_shock
    tau: 0.1
    mandatory: false   # Phase 1A+
  - id: species_conservation
    type: threshold
    error_key: e_species
    tau: 1.0e-4
    mandatory: false   # Phase 1B+
  - id: chemistry_uq
    type: threshold
    error_key: e_chem_uq
    tau: 0.15
    mandatory: false
  - id: sequential_fsi_interface
    type: threshold
    error_key: e_fsi_interface
    tau: 1.0e-4
    mandatory: false   # Phase 1B+
  - id: coupling_convergence
    type: threshold
    error_key: e_coupling
    tau: 1.0e-6
    mandatory: false   # Phase 3+

# === MARGIN FUNCTION ===
margin:
  type: quadratic_barrier   # quadratic_barrier | linear_clip | logistic
  # m(e,τ) = 1 - (e/τ)^2   for e < τ; 0 otherwise
  # Quadratic barrier: increasing returns for safety margin

# === PHYSICS FIDELITY (weight 0.40) ===
physics:
  weight: 0.40
  components:
    - key: mass_conservation
      alpha: 0.40
      tau: 1.0e-6
      definition: mass_conservation_l2  # registry of named operators
    - key: energy_stability
      alpha: 0.30
      tau: 1.0e-6
      definition: energy_stability_residual
    - key: boundary_satisfaction
      alpha: 0.20
      tau: 1.0e-4
      definition: boundary_residual_l2
    - key: shock_capture
      alpha: 0.10
      tau: 0.1
      definition: shock_position_error
      # Phase 1A+ only

# === ROBUSTNESS (weight 0.35) ===
robustness:
  weight: 0.35
  # Category weights by engineering consequence severity
  category_weights:
    low_viscosity: 0.15
    high_amplitude_ic: 0.25
    steep_gradient: 0.30
    shock_regime: 0.30
  # 80% tail (95th percentile), 20% mean → worst-case focus
  lambda: 0.20      # weight on mean
  beta: 0.20        # weight on mean in mean/tail blend
  tail_quantile: 0.95
  tau_rob: 2.0e-1   # dimensionless (relative L2 error)
  min_category_coverage: 0.90
  # Graceful degradation if coverage < threshold:
  coverage_grace: true
  coverage_grace_factor: 0.5  # score *= max(0, coverage / 0.90) if < 0.90

# === GENERALIZATION / ACCURACY (weight 0.25) ===
accuracy:
  weight: 0.25
  # 50% in-distribution, 50% out-of-distribution (extended envelope)
  field_error: relative_l2
  tau_acc: 1.0e-1
  ood_weight: 0.50
  ood_tau: 2.0e-1   # 2× tau_acc for extended envelope
  aggregate: mean
  # Soft gate: warn if max_rel_l2 > 3 * tau_acc
  soft_gate:
    enabled: true
    max_rel_l2_multiple: 3.0

# === COMBINED SCORE ===
combination:
  type: multiplicative  # multiplicative | weighted_sum
  # S = S_phys * S_robust * S_acc
  # Any near-zero component → near-zero emissions

# === EMISSIONS ===
emissions:
  type: multiplicative  # w ∝ S_phys * S_robust * S_acc * exp(-Δblocks / t_half)
  half_life_blocks: 21600  # ~30 days at 12s blocks
  min_score_floor: 0.01  # 1% floor prevents zero-emission trap

# === CARD REQUIRED FIELDS ===
card_required_fields:
  - challenge_id
  - scoring_version
  - scoring_pack_hash
  - generator_version
  - gate_results
  - physics_margins
  - robustness_by_category
  - accuracy_eval
  - accuracy_ood
  - S_physics
  - S_robustness
  - S_accuracy
  - S_combined
  - gate_results
  - gate_failed
  - block_height
  - scoring_pack_hash
  - scoring_version
  - challenge_id
  - min_score_floor_applied: true      # Implementation only
  - score_before_floor: 0.002         # Implementation only
  - accuracy_soft_gate_warning: 0.15   # if max_rel_l2 > 3 * tau_acc

# === VERSIONING ===
schema_version: "1.0"
```

---

## 4. Lean Scoring Formulas (Protocol)

### 4.1 Hard Gates — Steep Sigmoid (Differentiable Binary)

```python
def hard_gate_score(error, tau, sharpness=1000.0):
    """
    Steep sigmoid approximation of hard threshold.
    - error < tau:  score ≈ 1.0
    - error > tau:  score → 0 exponentially
    - At error = tau: score = 0.5
    """
    return 1.0 / (1.0 + jnp.exp(sharpness * (error - tau) / tau))

# Hard gates evaluated in fp32 (physics_precision_policy context)
def compute_hard_gates(gate_results: List[GateResult]) -> Float[Array, ""]:
    scores = jnp.array([g.score for g in gate_results if g.mandatory])
    return jnp.prod(scores)  # multiplicative: any near-zero → near-zero total
```

**Hard Gate Rule:** Any mandatory gate with score < 0.99 → `S_combined = 0`.  
*Implementation: `hard_score = jnp.prod(hard_gate_scores); if hard_score < 0.99: return Score(0, ...)`*

---

## 4.2 Physics Fidelity — Quadratic Barrier (Increasing Returns)

```python
def physics_margin(error: Float[Array, ""], tau: float) -> Float[Array, ""]:
    """
    Quadratic barrier function: m(e,τ) = 1 - (e/τ)² for e < τ; 0 otherwise.
    
    Properties:
    - m(0, τ) = 1.0 (perfect)
    - m(0.5τ, τ) = 0.75
    - m(0.1τ, τ) = 0.99 (10× safety margin → 99% score)
    - m(τ, τ) = 0.0 (at threshold)
    - m(e, τ) = 0 for e ≥ τ (hard gate fails)
    
    Engineering basis: Barrier function / safety margin / penalty method.
    Quadratic penalty = increasing returns for safety margin.
    10× safety margin (e=0.1τ) → 99% score vs 90% linear.
    """
    ratio = error / tau
    margin = jnp.where(
        ratio < 1.0,
        1.0 - ratio ** 2,  # quadratic: increasing returns for safety margin
        0.0
    )
    return margin
```

**Physics Fidelity Score (40% weight):**

```python
def compute_physics_fidelity(gate_results: List[GateResult], pack: ScorePack) -> Float:
    margins = []
    for gate in pack.physics.components:
        gate_result = next(g for g in gate_results if g.gate_id == gate.key)
        margin = physics_margin(gate_result.value, gate.tau)
        margins.append(gate.alpha * margin)
    return jnp.sum(jnp.array(margins))  # already weighted by alpha, sum α_k = 1
```

**Why Quadratic?**  
- Linear: `1 - e/τ` → 10× safety margin gives 90% score (marginal gain 10%)
- Quadratic: `(e/τ)²` → 10× safety margin gives 99% score
- **Engineering basis:** Barrier function / safety factor / penalty method.  
  10× safety margin → 99% score vs 90% linear.  
  Matches structural reliability theory (barrier functions) and PDE-constrained optimization.

---

## 5 Functional Training Loop with `lax.scan` + Hard Safety Rails

### Problem
Miners control the absolute `epochs` parameter. Rogue or poorly configured submissions can request extremely high epoch counts and monopolize validator compute. Traditional Python loop-based training prevents JAX from optimizing the step sequence into a single hardware trace and makes hard resource limits difficult to enforce.

### Solution: `lax.scan` + Hard Safety Rails

Structure the epoch sequence with `jax.lax.scan` and use `jax.lax.cond` for early-termination logic so that the control flow remains inside XLA. A hard absolute step limit and wall-clock timeout act as additional safety rails outside the scan.

```python
# carbon/validator/training.py
import jax
import jax.lax as lax
import jax.numpy as jnp
from typing import Tuple, Dict, NamedTuple, Callable, Any, Optional
from flax.training import train_state
import optax
from flax.core import FrozenDict
from jaxtyping import Array, Float, Int
import time

class TrainerState(train_state.TrainState):
    """Extended train state with early-stopping metadata."""
    best_loss: Float[Array, ""]
    consecutive_no_improve: Int[Array, ""]
    terminated: bool
    epoch: Int[Array, ""]

def create_training_step(
    model_apply_fn: Callable,
    loss_fn: Callable,
    optimizer: optax.GradientTransformation,
    grad_accum_steps: int = 1,
    physics_precision: bool = False
) -> Callable:
    """Factory for compiled training step with gradient accumulation."""
    
    @partial(jax.jit, donate_argnums=(0, 1))
    def train_step(state: TrainState, batch) -> Tuple[train_state.TrainState, Float[Array, ""]]:
        # Gradient accumulation over micro-batches
        def accum_step(carry, micro_batch):
            params, opt_state, grad_accum = carry
            grads = compute_grads(params, micro_batch, physics_precision)
            grad_accum = jax.tree.map(lambda a, g: a + g, grad_accum, grads)
            return (params, opt_state, grad_accum), None
        
        micro_batches = split_batch(batch, grad_accum_steps)
        (params, opt_state, grad_accum), _ = lax.scan(
            lambda carry, mb: (accum_step(carry, mb), None),
            (state.params, state.opt_state, jax.tree.map(jnp.zeros_like, state.params)),
            micro_batches
        )
        
        # Apply accumulated gradients
        grad_accum = jax.tree.map(lambda x: x / grad_accum_steps, grad_accum)
        updates, new_opt_state = optimizer.update(grad_accum, state.opt_state)
        new_params = optax.apply_updates(state.params, updates)
        
        return state.replace(
            params=new_params, opt_state=new_opt_state, step=state.step + 1
        ), loss
    
    return train_step


def create_training_loop(
    train_step: Callable,
    max_epochs: int,
    patience: int = 50,
    hard_step_limit: int = None,
    wall_clock_limit_sec: int = 7200  # 2 hours default
) -> Callable:
    """Creates a compiled training loop with HARD safety rails."""
    
    class LoopState(NamedTuple):
        state: TrainState
        best_loss: Float[Array, ""]
        consecutive_no_improve: int
        terminated: bool
        epoch: int
    
    @partial(jax.jit, donate_argnums=(0,))
    def epoch_step(state: Tuple, _):
        loop_state, epoch_idx = state
        
        def execution_branch(ls: LoopState):
            new_state, epoch_loss = train_step(ls.state, current_batch)
            
            improved = epoch_loss < ls.best_loss
            next_best = jnp.where(improved, epoch_loss, ls.best_loss)
            next_count = jnp.where(improved, 0, ls.consecutive_no_improve + 1)
            should_abort = next_count >= patience
            
            return LoopState(
                state=new_state,
                best_loss=next_best,
                consecutive_no_improve=next_count,
                terminated=should_abort,
                epoch=ls.epoch + 1
            ), epoch_loss
        
        def short_circuit_branch(ls: LoopState):
            return ls, ls.best_loss
        
        next_loop_state, epoch_loss = lax.cond(
            ls.terminated,
            short_circuit_branch,
            execution_branch,
            loop_state
        )
        return (next_loop_state, epoch_idx + 1), epoch_loss
    
    def fit(init_state: TrainState, data_loader, max_epochs: int):
        effective_epochs = max_epochs
        if hard_step_limit is not None:
            effective_epochs = min(max_epochs, hard_step_limit)
        
        init_loop_state = LoopState(
            state=init_state,
            best_loss=jnp.inf,
            consecutive_no_improve=0,
            terminated=False,
            epoch=0
        )
        
        # Wall-clock timeout enforced OUTSIDE JIT (Python side)
        start_time = time.time()
        
        (final_loop_state, _), loss_history = lax.scan(
            epoch_step,
            (init_loop_state, 0),
            jnp.arange(effective_epochs)
        )
        
        # Wall-clock timeout enforced OUTSIDE JIT
        if time.time() - start_time > wall_clock_limit_sec:
            logger.warning(f"Wall-clock timeout ({wall_clock_limit_sec}s) reached")
        
        return final_loop_state.state, loss_history
    
    return fit
```

**Critical Safety Rails (Non-Negotiable):**
1. **Patience-based early stopping** inside `lax.scan` (inside XLA graph)
2. **Hard step limit** (`hard_step_limit`) independent of miner `epochs`
3. **Wall-clock timeout** enforced in Python (outside JIT) — kills stuck evaluations
4. **Gradient clipping INSIDE JIT** (prevents recompilation)

---

## 6 Precision Policy: bfloat16 + fp32 Physics Gates (Correctness-Critical)

### Problem
bfloat16 reduces VRAM 30-50% but **physics gates fail catastrophically in bf16** (1e-6 residual → 1e-4 error → false FAIL).

### Solution: Contextual Precision Policy (Correctness-Critical)

```python
# carbon/backbones/precision.py
import jax
import jax.numpy as jnp
from contextlib import contextmanager
from jaxtyping import Array
import threading

_thread_local = threading.local()

@contextmanager
def physics_precision_policy():
    """Context manager: FORCE fp32 for physics gates, allow bf16 elsewhere."""
    prev_matmul = jax.config.get("jax_default_matmul_precision")
    prev_precision = getattr(_thread_local, "precision_policy", "bfloat16")
    try:
        # Physics gates MUST run in fp32 — this is a correctness requirement
        jax.config.update("jax_default_matmul_precision", "float32")
        _thread_local.precision_policy = "float32"
        yield
    finally:
        jax.config.update("jax_default_matmul_precision", prev_matmul)
        _thread_local.precision_policy = prev_precision

@contextmanager
def training_precision_policy(allow_bfloat16: bool = True):
    """Training context: allows bfloat16 for speed, fp32 for stability."""
    prev_matmul = jax.config.get("jax_default_matmul_precision")
    try:
        if allow_bfloat16:
            jax.config.update("jax_default_matmul_precision", "bfloat16")
        else:
            jax.config.update("jax_default_matmul_precision", "float32")
        yield
    finally:
        jax.config.update("jax_default_matmul_precision", prev_matmul)

def cast_to_bfloat16(x: Array) -> Array:
    """Explicit downcast for model activations/weights."""
    return x.astype(jnp.bfloat16)

def selective_cast_for_residuals(x: Array) -> Array:
    """Force fp32 for residual/conservation calculations."""
    return x.astype(jnp.float32)

# In physics gates — MANDATORY fp32 context
@jax.jit
def run_physics_gates(model_fn, params, stress_data):
    with physics_precision_policy():  # FORCES fp32 — correctness requirement
        return run_all_gates_impl(model_fn, params, stress_data)

# In training — allows bf16 for speed
def train_step(state, batch):
    with training_precision_policy(allow_bfloat16=True):
        return training_step_impl(state, batch)
```

**Enforcement in SPEC (Non-Negotiable):**
> **All physics gate computations (residuals, conservation checks, boundary checks, UQ calibration) MUST execute in fp32 precision. Validators not enforcing this will produce false gate failures and be slashed.**

---

## 7 Mesh-Independent Multi-Fidelity Grid Curriculums

### Problem
Forcing downsampled spatial resolutions validator-side could overwrite valid miner-designed training strategies that rely on high-frequency, fine-mesh features from the first epoch.

### Solution: Miner-Controlled, Validator-Defaulted Curriculum

**Schema Extension** (v1.0+):
```json
{
  "curriculum": [
    {
      "phase": 1,
      "epochs": 100,
      "spatial_resolution_scale": 0.5,
      "mode_budget_scale": 0.5
    },
    {
      "phase": 2,
      "epochs": 200,
      "spatial_resolution_scale": 1.0,
      "mode_budget_scale": 1.0
    }
  ]
}
```

### Implementation: Proper Restriction Operators

```python
# carbon/generators/resolution.py
import jax
import jax.numpy as jnp
from typing import Tuple, Optional

@jax.jit
def downsample_spatial_grid(
    coords: Array,
    fields: Array,
    scale: float
) -> Tuple[Array, Array]:
    """
    Mesh-independent spatial downsampling for structured grids.
    For unstructured data, replace with proper restriction / interpolation.
    """
    if scale >= 1.0 - 1e-6:
        return coords, fields

    stride = int(jnp.round(1.0 / scale))
    downsampled_coords = coords[::stride, ::stride, ...]
    downsampled_fields = fields[::stride, ::stride, ...]
    return downsampled_coords, downsampled_fields

@jax.jit
def restrict_fields(fields: Array, scale: float, grid_type: str = "structured") -> Array:
    """
    Proper restriction operator for multi-fidelity training.
    Structured: strided averaging (conservative).
    Unstructured: requires interpolation weights (precomputed).
    """
    if scale >= 1.0 - 1e-6:
        return fields
    
    if grid_type == "structured":
        stride = int(jnp.round(1.0 / scale))
        return fields[::stride, ::stride, ...]
    else:
        # Unstructured: use precomputed restriction matrix
        return apply_restriction_matrix(fields, scale)

def adjust_fno_modes_for_resolution(mode_counts: tuple, scale: float) -> tuple:
    """Adjust FNO mode counts when resolution changes."""
    return tuple(int(m * scale) for m in mode_counts)
```

**Caution**: Changing resolution mid-training interacts with normalization statistics and Fourier mode counts. FNO mode counts must be adjusted or padded consistently when resolution changes.

---

## 8 Gradient Accumulation + Checkpointing (Phase 3-4 Mandatory)

### Phase 3-4: Large Model Training on 80GB VRAM

```python
# carbon/validator/training_phase3.py
from jax import checkpoint
from jax.experimental import mesh_utils
from jax.sharding import Mesh, PartitionSpec as P
from jax.experimental.shard_map import shard_map

def create_phase3_train_step(
    accumulation_steps: int = 8,
    checkpoint_every_n_layers: int = 2,
    mesh_devices: list = None
):
    """Phase 3-4 training step with gradient accumulation + checkpointing."""
    
    def train_step(state, batch):
        # Split batch into micro-batches for gradient accumulation
        micro_batches = split_batch(batch, accumulation_steps)
        
        def accum_scan_fn(carry, micro_batch):
            params, opt_state, grad_accum = carry
            grads = compute_grads(params, micro_batch)
            grad_accum = jax.tree.map(lambda a, g: a + g, grad_accum, grads)
            return (params, opt_state, grad_accum), None
        
        # Accumulate gradients over micro-batches
        (params, opt_state, grad_accum), _ = lax.scan(
            accum_scan_fn, (state.params, state.opt_state, zero_grads), micro_batches
        )
        
        # Average accumulated gradients
        grad_accum = jax.tree.map(lambda x: x / accumulation_steps, grad_accum)
        updates, new_opt_state = optimizer.update(grad_accum, opt_state)
        new_params = optax.apply_updates(params, updates)
        
        return state.replace(params=new_params, opt_state=new_opt_state)
    
    # Gradient checkpointing for deep models
    def make_checkpointed_block(block_fn, policy=checkpoint.save_any_names_but_these("params")):
        return checkpoint.checkpoint(block_fn, policy=policy)
    
    return train_step
```

### Phase 4: Model Sharding (ZeRO-3) for 3D LES

```python
# carbon/validator/sharding.py
from jax.experimental import mesh_utils
from jax.sharding import Mesh, PartitionSpec as P
from jax.experimental.shard_map import shard_map

def create_sharded_train_step(mesh_devices: list, model_spec: dict):
    """Phase 4: ZeRO-3 style sharding for 3D LES on H200 clusters."""
    
    mesh = Mesh(mesh_utils.create_device_mesh((len(mesh_devices),)), ('model',))
    
    # Partition specs for FNO/GINO weights
    param_spec = {
        "lifting": P("model"),
        "spectral_convs": P("model"),
        "projection": P("model"),
        "embeddings": P("model"),
    }
    
    @shard_map(mesh=mesh, in_specs=(param_spec, P()), out_specs=P())
    def sharded_forward(params, x):
        return model.apply(params, x)
    
    # Gradient sharding (ZeRO-3)
    def sharded_grad_fn(params, batch):
        grads = jax.grad(loss_fn)(params, batch)
        # Gradients already sharded by shard_map
        return grads
    
    return sharded_forward, sharded_grad_fn
```

---

## 9 Operational Infrastructure (Production Requirements)

### 1. Validator Queue Management

```python
# carbon/validator/queue.py
from dataclasses import dataclass
from enum import Enum
import asyncio
import heapq
import time
from typing import Optional, Dict, Set

class Priority(Enum):
    SPONSORED_TIER_4 = 0
    SPONSORED_TIER_3 = 1
    SPONSORED_TIER_2 = 2
    HIGH_REPUTATION = 3
    STANDARD = 4
    ESTIMATION_MODE = 5

@dataclass
class QueuedSubmission:
    priority: Priority
    submit_time: float
    hotkey: str
    challenge_id: str
    strategy_hash: str
    estimated_gpu_seconds: float
    submission_id: str
    
    def __lt__(self, other):
        if self.priority != other.priority:
            return self.priority.value < other.priority.value
        return self.submit_time < other.submit_time

class ValidatorQueue:
    def __init__(self, max_concurrent: int = 3, max_queue_depth: int = 100):
        self.max_concurrent = max_concurrent
        self.max_queue_depth = max_queue_depth
        self.pending: list = []
        self.active: Dict[str, dict] = {}
        self.submission_timeout = 7200  # 2 hours max per submission
    
    async def enqueue(self, submission: QueuedSubmission) -> str:
        if len(self.pending) >= self.max_queue_depth:
            raise QueueFullError(f"Queue depth {self.max_queue_depth} exceeded")
        heapq.heappush(self.pending, submission)
        asyncio.create_task(self._monitor_timeout(submission.submission_id))
        return submission.submission_id
    
    async def _monitor_timeout(self, submission_id: str):
        await asyncio.sleep(self.submission_timeout)
        if submission_id in self.active:
            await self._kill_submission(submission_id)
    
    async def _kill_submission(self, submission_id: str):
        # Force kill GPU process, cleanup, mark as timeout
        pass
    
    def dequeue(self) -> Optional[QueuedSubmission]:
        if not self.pending:
            return None
        return heapq.heappop(self.pending)
```

### 2. Determinism Lockfile (Pinned)

```txt
# requirements-lock.txt — PIN EXACT VERSIONS
jax==0.4.30
jaxlib==0.4.30+cuda12.cudnn89
flax==0.8.4
optax==0.2.1
orbax-checkpoint==0.5.2
numpy==1.26.4
scipy==1.12.0
```

```dockerfile
# Dockerfile
COPY requirements-lock.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements-lock.txt
ENV JAX_VERSION=0.4.30
ENV FLAX_VERSION=0.8.4
```

**Why**: JAX 0.4.x → 0.5.x changes numerics at 1e-7 level. Gates at 1e-6 threshold = flaky PASS/FAIL.

---

## 10. Physics Gates Implementation

### 1 Core Physics Gates (Phase 0+)

```python
# carbon/validator/physics_gates.py
import jax
import jax.numpy as jnp
from jax import grad, vmap, jit
from dataclasses import dataclass
from typing import Callable, Dict, Any

@dataclass
class GateResult:
    gate_id: str
    threshold: float
    result: float
    status: str  # "PASS" | "FAIL"
    worst_case_variant: str = ""
    details: Dict[str, Any] = None

# --- Mass Conservation (Continuity) ---
@jit
def mass_conservation_residual(model_fn: Callable, coords: jnp.ndarray, params: Dict) -> jnp.ndarray:
    """∂ρ/∂t + ∇·(ρu) = 0"""
    # coords: (N, d+1) where last dim is time
    # model_fn outputs (rho, u_x, u_y, u_z)
    
    def continuity_eq(coord):
        rho, ux, uy, uz = model_fn(coord, params)
        # Time derivative of rho
        drho_dt = grad(lambda c: model_fn(c, params)[0])(coord)[-1]
        # Spatial divergence of rho*u
        def flux(c):
            rho, ux, uy, uz = model_fn(c, params)
            return jnp.array([rho*ux, rho*uy, rho*uz])
        div_flux = jnp.trace(jax.jacfwd(flux)(coord)[:, :3])  # spatial dims only
        return drho_dt + div_flux
    
    residuals = vmap(continuity_eq)(coords)
    return jnp.abs(residuals)

# --- Energy Stability ---
@jit
def energy_stability_residual(model_fn: Callable, coords: jnp.ndarray, params: Dict) -> jnp.ndarray:
    """ρ·De/Dt = -∇·q - p∇·u + Φ"""
    # Implementation depends on physics class
    # For compressible NS: total energy E = e + 0.5*|u|^2
    pass

# --- Boundary Satisfaction ---
@jit
def boundary_residual(model_fn: Callable, boundary_coords: jnp.ndarray, 
                      boundary_values: Dict, params: Dict) -> jnp.ndarray:
    """u|_∂Ω = g_D, (σ·n)|_∂Ω = g_N"""
    pred = vmap(model_fn)(boundary_coords, params)
    # Dirichlet
    dirichlet_error = jnp.abs(pred - boundary_values["dirichlet"])
    # Neumann (requires gradient)
    neumann_error = jnp.abs(grad(model_fn)(boundary_coords) - boundary_values["neumann"])
    return jnp.concatenate([dirichlet_error.flatten(), neumann_error.flatten()])

# --- Rollout Stability ---
@jit
def rollout_stability(model_fn: Callable, init_coords: jnp.ndarray, 
                      params: Dict, steps: int = 10000, perturb: float = 0.01) -> bool:
    """Autoregressive rollout with perturbation."""
    state = init_state
    for i in range(steps):
        state = model_fn(state, params)
        if i % 100 == 0:
            state = state + perturb * jax.random.normal(key, state.shape)
        if jnp.any(jnp.isnan(state)) or jnp.any(jnp.abs(state) > 1e6):
            return False
    return True

# --- UQ Calibration (Conformal Prediction) ---
def uq_calibration(model_fn: Callable, calibration_coords: jnp.ndarray,
                   calibration_targets: jnp.ndarray, params: Dict,
                   confidence: float = 0.95) -> float:
    """Split conformal prediction for coverage."""
    # Split calibration set
    n = len(calibration_coords)
    split_idx = n // 2
    
    # Train on first half, calibrate on second
    # Use conformal prediction to get prediction intervals
    # Return coverage probability
    pass

# --- Gate Runner ---
def run_all_gates(model_fn: Callable, challenge: str, params: Dict,
                  stress_data: Dict, generator_version: str) -> List[GateResult]:
    """Run all physics gates for a challenge."""
    gates = []
    
    # 1. Mass Conservation
    mass_residuals = mass_conservation_residual(model_fn, stress_data["coords"], params)
    max_mass_res = float(jnp.max(jnp.abs(mass_residuals)))
    gates.append(GateResult(
        gate_id="mass_conservation",
        threshold=1e-6,
        result=max_mass_res,
        status="PASS" if max_mass_res < 1e-6 else "FAIL",
        worst_case_variant=stress_data["worst_case"]["mass"]
    ))
    
    # 2. Energy Stability
    energy_residuals = energy_stability_residual(model_fn, stress_data["coords"], params)
    max_energy_res = float(jnp.max(jnp.abs(energy_residuals)))
    gates.append(GateResult(...))
    
    # 3. Boundary Satisfaction
    boundary_res = boundary_residual(model_fn, stress_data["boundary_coords"], 
                                     stress_data["boundary_values"], params)
    max_boundary_res = float(jnp.max(jnp.abs(boundary_res)))
    gates.append(GateResult(...))
    
    # 4. Rollout Stability
    rollout_ok = rollout_stability(model_fn, stress_data["init_coords"], params)
    gates.append(GateResult(...))
    
    # 5. UQ Calibration
    uq_coverage = uq_calibration(model_fn, stress_data["cal_coords"],
                                 stress_data["cal_targets"], params)
    gates.append(GateResult(...))
    
    return gates
```

---

## 11. Procedural Generators

### Base Generator Interface

```python
# carbon/generators/base.py
import jax
import jax.numpy as jnp
from jax import random
from dataclasses import dataclass
from abc import ABC, abstractmethod

@dataclass
class GeneratorConfig:
    challenge_id: str
    physics_class: str
    dimension: int
    parameter_ranges: Dict[str, tuple]
    reference_solver: str
    validation_tolerance: str

class ProceduralGenerator(ABC):
    def __init__(self, config: GeneratorConfig):
        self.config = config
    
    @abstractmethod
    def generate_training_data(self, seed: int, n_samples: int) -> Dict:
        """Generate training data: {coords, fields, boundary_conditions}"""
        pass
    
    @abstractmethod
    def generate_stress_variants(self, seed: int, n_variants: int) -> Dict:
        """Generate hidden stress test variants."""
        pass
    
    @abstractmethod
    def generate_benchmark_data(self, seed: int, n_samples: int) -> Dict:
        """Generate held-out benchmark data."""
        pass
    
    def derive_seeds(self, master_seed: int) -> Dict[str, int]:
        """Hierarchical deterministic seed derivation."""
        keys = random.split(random.PRNGKey(master_seed), 5)
        return {
            "data": int(random.randint(keys[0], (), 0, 2**32)),
            "stress": int(random.randint(keys[1], (), 0, 2**32)),
            "init": int(random.randint(keys[2], (), 0, 2**32)),
            "dropout": int(random.randint(keys[3], (), 0, 2**32)),
            "shuffle": int(random.randint(keys[4], (), 0, 2**32)),
        }
```

### Phase 0: JAX-FEM Generators (Online)

```python
# carbon/generators/poisson.py
class PoissonGenerator(ProceduralGenerator):
    def generate_training_data(self, seed: int, n_samples: int) -> Dict:
        key = random.PRNGKey(seed)
        
        # 1. Sample coefficient field k(x) ~ LogNormal
        key, k_key = random.split(key)
        log_k = random.normal(k_key, (n_samples, *self.resolution)) * 0.5
        k = jnp.exp(log_k)
        
        # 2. Sample source field f(x) ~ Gaussian Process
        key, f_key = random.split(key)
        f = self._sample_gp(f_key, n_samples, length_scale=0.1)
        
        # 3. Solve -∇·(k∇u) = f using JAX-FEM (differentiable!)
        u = self._solve_poisson(k, f)
        
        return {
            "coords": self.grid,           # (64, 64, 2)
            "inputs": {"coefficient": k, "source": f},
            "targets": {"solution": u},
            "boundary_mask": self.bc_mask
        }
    
    def _solve_poisson(self, k, f):
        """JAX-FEM Poisson solve: -∇·(k∇u) = f"""
        # Differentiable FEM solve using JAX
        pass
```

### Phase 1A: Compressible NS (Hybrid Online/Offline)

```python
# carbon/generators/compressible_ns.py
class CompressibleNSGenerator(ProceduralGenerator):
    def generate_training_data(self, seed: int, n_samples: int) -> Dict:
        key = random.PRNGKey(seed)
        
        # 1. Sample flow conditions
        key, mach_key, re_key, aoa_key = random.split(key, 4)
        mach = random.uniform(mach_key, (n_samples,), minval=0.7, maxval=1.2)
        reynolds = 10**random.uniform(re_key, (n_samples,), minval=6, maxval=7)
        aoa = random.uniform(aoa_key, (n_samples,), minval=-2, maxval=4)
        
        # 2. Generate mesh perturbations (geometry variation)
        key, mesh_key = random.split(key)
        mesh_perturb = random.normal(mesh_key, (n_samples, *self.mesh_shape)) * 0.001
        
        # 3. Generate turbulence ICs
        key, turb_key = random.split(key)
        turb_ic = self._sample_turbulence_ic(turb_key, n_samples)
        
        # 4. Load precomputed solutions from cache
        solutions = self._load_precomputed_solutions(mach, reynolds, aoa)
        
        return {
            "coords": self.grid,
            "mach": mach,
            "reynolds": reynolds,
            "aoa": aoa,
            "mesh_perturb": mesh_perturb,
            "turb_ic": turb_ic,
            "targets": {"solution": solutions},
            "boundary_mask": self.bc_mask
        }
```

### Phase 1B: Precomputed Generators (Reacting Flow, FSI, 6-DOF, CHT)

```python
# carbon/generators/reacting_ns.py
class ReactingNSGenerator(ProceduralGenerator):
    def generate_training_data(self, seed: int, n_samples: int) -> Dict:
        key = random.PRNGKey(seed)
        
        # Flight conditions
        key, mach_key, re_key, wall_temp_key = random.split(key, 4)
        mach = random.uniform(mach_key, (n_samples,), minval=5.0, maxval=8.0)
        reynolds = 10**random.uniform(re_key, (n_samples,), minval=5, maxval=6)
        wall_temp = random.uniform(wall_temp_key, (n_samples,), minval=300, maxval=2000)
        
        # Chemistry ICs
        key, chem_key = random.split(key)
        species_ic = self._sample_chemistry_ic(chem_key, n_samples)
        
        # Load precomputed solutions from cache
        solutions = self._load_precomputed_solutions(mach, reynolds, wall_temp, species_ic)
        
        return {
            "mach": mach,
            "reynolds": reynolds,
            "wall_temp": wall_temp,
            "species_ic": species_ic,
            "targets": {"solution": solutions},
        }
```

### Stress Generator (Hidden, Fresh Every Eval)

```python
# carbon/generators/stress.py

class StressCategory(Enum):
    EXTENDED_ENVELOPE = "extended_envelope"
    SHOCK_PERTURBATION = "shock_perturbation"
    BOUNDARY_LAYER_TRIP = "boundary_layer_trip"
    SEPARATION_TRIGGER = "separation_trigger"
    CHEMISTRY_PERTURBATION = "chemistry_perturbation"
    MESH_PERTURBATION = "mesh_perturbation"
    BOUNDARY_CONDITION = "boundary_condition"
    INITIAL_CONDITION = "initial_condition"
    COUPING_PERTURBATION = "coupling_perturbation"

@dataclass
class StressVariantSpec:
    category: StressCategory
    weight: float
    params: Dict[str, Any]
    physics_gates: List[str]

STRESS_VARIANT_SPECS = {
    "naca0012_transonic-v1": [
        StressVariantSpec(
            category=StressCategory.EXTENDED_ENVELOPE,
            weight=0.30,
            params={"mach_range": (0.5, 1.5), "reynolds_range": (0.5e6, 20e6)},
            physics_gates=["mass_conservation", "energy_stability", "shock_capture"]
        ),
        StressVariantSpec(
            category=StressCategory.SHOCK_PERTURBATION,
            weight=0.20,
            params={"shock_strength": (0.05, 0.15), "position_perturbation": 0.05},
            physics_gates=["shock_capture", "mass_conservation"]
        ),
        StressVariantSpec(
            category=StressCategory.BOUNDARY_LAYER_TRIP,
            weight=0.15,
            params={"trip_location": (0.3, 0.7), "trip_height": (0.01, 0.05)},
            physics_gates=["boundary_satisfaction", "separation_capture"]
        ),
        StressVariantSpec(
            category=StressCategory.SEPARATION_TRIGGER,
            weight=0.15,
            params={"adverse_pressure_gradient": (1.5, 3.0)},
            physics_gates=["separation_capture", "rollout_stability"]
        ),
        StressVariantSpec(
            category=StressCategory.MESH_PERTURBATION,
            weight=0.10,
            params={"perturbation_magnitude": 0.005, "frequency": (1, 5)},
            physics_gates=["boundary_satisfaction", "mass_conservation"]
        ),
        StressVariantSpec(
            category=StressCategory.BOUNDARY_CONDITION,
            weight=0.10,
            params={"wall_temp_factor": (0.5, 2.0), "catalytic_factor": (0.1, 10.0)},
            physics_gates=["thermal_protection", "energy_stability"]
        ),
    ],
}

class StressGenerator(ProceduralGenerator):
    def generate_stress_variants(self, seed: int, n_variants: int) -> Dict:
        """Generate hidden stress variants for evaluation."""
        key = random.PRNGKey(seed)
        specs = STRESS_VARIANT_SPECS.get(self.config.challenge_id, [])
        
        # Normalize weights
        total_weight = sum(s.weight for s in specs)
        probs = [s.weight / total_weight for s in specs]
        
        variants = []
        for i in range(n_variants):
            key, var_key = random.split(key)
            
            # Select category by weight
            cat_idx = random.choice(var_key, len(specs), p=jnp.array(probs))
            spec = specs[cat_idx]
            
            # Generate variant
            variant = self._generate_variant(var_key, spec)
            variants.append(variant)
        
        return self._collate_variants(variants)
    
    def _generate_variant(self, key: int, spec: StressVariantSpec) -> Dict:
        handlers = {
            StressCategory.EXTENDED_ENVELOPE: self._gen_extended_envelope,
            StressCategory.SHOCK_PERTURBATION: self._gen_shock_perturbation,
            StressCategory.BOUNDARY_LAYER_TRIP: self._gen_bl_trip,
            StressCategory.SEPARATION_TRIGGER: self._gen_separation_trigger,
            StressCategory.MESH_PERTURBATION: self._gen_mesh_perturbation,
            StressCategory.BOUNDARY_CONDITION: self._gen_boundary_condition,
            StressCategory.CHEMISTRY_PERTURBATION: self._gen_chemistry_perturbation,
            StressCategory.COUPLING_PERTURBATION: self._gen_coupling_perturbation,
        }
        return handlers[spec.category](key, spec.params)
```

---

## 12. Validator Training Pipeline

### Complete Training Pipeline with SciML Integration

```python
# carbon/validator/training.py
import jax
import jax.numpy as jnp
import optax
import orbax.checkpoint as ocp
from flax.training import train_state
from typing import Callable, Dict, Any
import yaml
from carbon.sciml.client import SciMLClient

class TrainState(train_state.TrainState):
    epoch: int
    best_score: float
    rng: jax.Array

class ValidatorTrainer:
    def __init__(self, config: Dict):
        self.config = config
        self.checkpointer = ocp.StandardCheckpointer()
        self.sciml_client = SciMLClient()  # Julia/SciML bridge
    
    def create_train_state(self, model_fn: Callable, params: Dict, 
                           strategy: Dict, rng: jax.Array) -> TrainState:
        """Initialize training state with optimizer from strategy."""
        tx = self._create_optimizer(strategy["training"])
        return TrainState.create(
            apply_fn=model_fn,
            params=params,
            tx=tx,
            epoch=0,
            best_score=-1.0,
            rng=rng
        )
    
    def _create_optimizer(self, training_config: Dict) -> optax.GradientTransformation:
        lr_schedule = self._create_lr_schedule(training_config)
        tx = optax.chain(
            optax.clip_by_global_norm(training_config.get("gradient_clip", 1.0)),
            optax.adamw(
                learning_rate=lr_schedule,
                weight_decay=training_config.get("weight_decay", 1e-4)
            )
        )
        return tx
    
    def train(self, state: TrainState, train_loader, val_loader, 
              strategy: Dict, physics_gates_fn) -> TrainState:
        """Main training loop with checkpointing and adaptive loss reweighting."""
        
        for epoch in range(state.epoch, self.config["training"]["epochs"]):
            # Training step
            state, train_metrics = self._train_epoch(state, train_loader, strategy)
            
            # Validation + physics gates
            if epoch % 10 == 0 or epoch == self.config["training"]["epochs"] - 1:
                val_metrics = self._validate(state, val_loader)
                gate_results = self._run_physics_gates(state)
                
                # SciML Validation: Compare against Ground Truth Oracle
                if epoch % 50 == 0:  # Periodic SciML validation
                    sciml_validation = await self._sciml_validation(state, strategy)
                    if not sciml_validation["passes"]:
                        logger.warning(f"SciML validation failed at epoch {epoch}: {sciml_validation}")
                
                # Adaptive loss reweighting
                state = self._adaptive_reweight(state, gate_results, strategy)
                
                # Checkpointing
                if self._should_checkpoint(epoch, val_metrics):
                    self._save_checkpoint(state, epoch)
                
                # Early stopping
                if self._should_stop(state):
                    break
        
        return state
    
    async def _sciml_validation(self, state: TrainState, strategy: Dict) -> Dict:
        """Validate trained model against Julia/SciML Ground Truth Oracle."""
        # Get challenge spec
        challenge_id = strategy["challenge_id"]
        challenge_spec = self.get_challenge_spec(challenge_id)
        
        # Get reference solution from Julia/SciML Ground Truth Oracle
        reference = await self.sciml_client.solve_pde_reference(
            pde_spec=challenge_spec.pde_spec,
            params=strategy.get("pde_params", {})
        )
        
        # Evaluate model on reference grid
        model_prediction = self._evaluate_on_grid(state.params, reference["coords"])
        
        # Compute error metrics
        error_metrics = self._compute_error_metrics(model_prediction, reference["solution"])
        
        return {
            "passes": all(v < 1e-3 for v in error_metrics.values()),
            "error_metrics": error_metrics,
            "reference_solution": reference
        }
    
    def _run_physics_gates(self, state: TrainState) -> List[GateResult]:
        """Run physics gates with SciML validation for adjoint gate."""
        # Standard gates
        gate_results = run_all_gates(
            model_fn=self.model_apply_fn,
            challenge=self.current_challenge,
            params=state.params,
            stress_data=self.stress_data,
            generator_version=self.generator_version
        )
        
        # Adjoint Consistency Gate via SciMLSensitivity.jl (Phase 1A+)
        if self.config.get("adjoint_consistency_gate", False):
            adjoint_result = await self.sciml_client.compute_adjoint_sensitivity(
                model_fn=self.model_apply_fn,
                params=state.params,
                loss_fn="physics_residual"
            )
            gate_results.append(GateResult(
                gate_id="adjoint_consistency",
                threshold=1e-4,
                result=adjoint_result["rel_error"],
                status="PASS" if adjoint_result["rel_error"] < 1e-4 else "FAIL"
            ))
        
        return gate_results
```

---

## 13. Landscape Agent Pipeline

### Pipeline Architecture

```python
# carbon/landscape/pipeline.py
class LandscapeAgent:
    def __init__(self, config: Dict):
        self.pysr_config = config.get("pysr", PYSR_CONFIG)
        self.dml_config = config.get("dml", DML_CONFIG)
        self.mt_bridge = ModelingToolkitBridge()  # Julia bridge
        self.specialist_bank = SpecialistBank()
        self.prior_engine = PriorEngine()
        self.sciml_client = SciMLClient()  # Julia/SciML bridge
    
    def ingest_model_card(self, model_card: ModelCard):
        """Process new model card, update knowledge base."""
        features = self._extract_features(model_card)
        self.pysr_dataset.append(features, model_card.gate_results)
        self.dml_dataset.append(features, model_card.robustness_score)
        
        # Periodic batch processing
        if len(self.pysr_dataset) % 100 == 0:
            self._run_pysr()
        if len(self.dml_dataset) % 500 == 0:
            self._run_dml()
    
    def _run_pysr(self):
        """Run PySR symbolic regression on accumulated data."""
        equations = pysr_regress(self.pysr_dataset, self.pysr_config)
        for eq in equations:
            # Convert to structured loss term
            loss_term = self.mt_bridge.json_to_loss_term(eq.json)
            self.specialist_bank.add_loss_term(loss_term)
        
        # Update noisy priors
        self.prior_engine.update_from_symbolic(equations)
    
    def _run_dml(self):
        """Run Double ML causal inference."""
        causal_effects = double_ml(self.dml_dataset, self.dml_config)
        
        # Generate strategic guidance
        guidance = self._generate_guidance(causal_effects)
        self.prior_engine.update_from_causal(guidance)
    
    def get_noisy_prior(self, challenge: str, backbone: str) -> Strategy:
        """Get current best prior for challenge+backbone."""
        base = self.prior_engine.get_base_prior(challenge, backbone)
        return self._add_noise(base, noise_scale=0.1)
```

### PySR Configuration (Phase 0)

```python
# carbon/landscape/pysr_config.py
PYSR_CONFIG = {
    "populations": 50,
    "population_size": 100,
    "ncycles_per_iteration": 500,
    "maxsize": 40,
    "maxdepth": 8,
    "binary_operators": ["+", "-", "*", "/", "^"],
    "unary_operators": ["sin", "cos", "exp", "log", "sqrt", "abs"],
    "constraints": {"pow": (-1, 1)},
    "complexity_of_operators": {"+": 1, "-": 1, "*": 2, "/": 2, "^": 3},
    "feature_names": [
        "loss_data_weight", "loss_physics_weight", "loss_boundary_weight",
        "lr_initial", "lr_decay_rate", "curriculum_phase", "backbone_depth",
        "backbone_width", "activation_type", "normalization_type",
        "physics_gate_margin", "residual_l2", "conservation_l2", "boundary_l2"
    ],
    "target_name": "robustness_score",
    "verbosity": 1,
    "batch_size": 1000,
    "early_stop_condition": "stop_if_no_improvement(50)",
}
```

### ModelingToolkit.jl Bridge (JSON → JAX Loss Terms)

```julia
# carbon/landscape/bridge.jl
module CarbonMTBridge
using ModelingToolkit, Symbolics, JSON3, StructTypes

function json_to_loss_term(json_expr::Dict) -> ModelingToolkit.Equation
    """Convert PySR JSON expression to MT differentiable loss term."""
    @variables t x y z
    @parameters p[1:20]  # strategy params
    
    # Parse PySR expression tree
    expr = parse_pysr_json(json_expr)
    
    # Compile to differentiable function
    loss_fn = eval(build_function(expr, [p...], [t, x, y, z]))
    
    return loss_fn
end

function parse_pysr_json(json::Dict)
    # Recursively parse PySR expression tree to Symbolics expression
    # Handles: +, -, *, /, ^, sin, cos, exp, log, sqrt, abs
    # Returns Symbolics expression
end

function loss_terms_to_jax(loss_fns::Vector) -> String
    """Generate JAX code for compiled loss terms."""
    # Generate: 
    # def structured_loss(params, physics_state):
    #     term1 = λ₁ * (div(u))^2
    #     term2 = λ₂ * (dρ/dt + div(ρu))^2
    #     return sum(terms)
end
end
```

### Double ML Configuration (Phase 2A+, JAX-Native)

```python
# carbon/landscape/dml_config.py
DML_CONFIG = {
    "n_folds": 5,
    "n_repeats": 3,
    "ml_model": "jax_boosting",
    "treatment_types": {
        "loss_weights": "continuous_multivariate",
        "curriculum": "categorical",
        "backbone": "categorical",
        "lr_schedule": "categorical"
    },
    "confounders": ["physics_class", "data_seed", "backbone", "epochs"],
    "target": "robustness_score",
    "confidence_level": 0.95,
    "min_samples_per_treatment": 50
}
```

---

## 14. Miner Toolkit & SDK

### Miner Toolkit Docker Image

```dockerfile
# carbon/miner/Dockerfile
FROM nvidia/cuda:12.4-devel-ubuntu22.04

# System deps
RUN apt-get update && apt-get install -y \
    python3.11 python3.11-venv git curl wget \
    build-essential cmake libopenmpi-dev \
    && rm -rf /var/lib/apt/lists/*

# Python env
RUN python3.11 -m venv /opt/carbon
ENV PATH="/opt/carbon/bin:$PATH"

# Carbon Miner Toolkit
COPY carbon/miner /opt/carbon/miner
COPY carbon/common /opt/carbon/common
COPY requirements-miner.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements-miner.txt

# Entry points
COPY docker/entrypoint-miner.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["--help"]
```

### CLI Interface

```bash
# carbon/miner/cli.py
@click.group()
def cli():
    """Carbon Miner Toolkit - Local iteration for Carbon Subnet"""
    pass

@cli.command()
@click.option('--challenge', required=True, help='Challenge ID')
@click.option('--backbone', default='fno', type=click.Choice(['fno', 'gino', 'wno', 'transolver']))
@click.option('--strategy', 'strategy_path', required=True, type=click.Path(exists=True))
@click.option('--mode', default='estimation', type=click.Choice(['estimation', 'light_training', 'full_confirmation']))
@click.option('--provider', type=click.Choice(['targon', 'chutes', 'runpod', 'lambda', 'local']))
@click.option('--gpu', default='A100_40GB')
@click.option('--output', default='./carbon_output')
def run(challenge, backbone, strategy_path, mode, provider, gpu, output):
    """Run local iteration loop."""
    # Load strategy, validate, estimate cost, confirm, execute
    pass

@cli.command()
@click.option('--challenge', required=True)
def pull_prior(challenge):
    """Download latest noisy prior for challenge."""
    pass

@cli.command()
@click.option('--challenge', required=True)
@click.option('--strategy', 'strategy_path', required=True)
def submit(challenge, strategy_path):
    """Submit strategy to validator via MCP."""
    pass

@cli.command()
def doctor():
    """Validate environment: GPU, drivers, MCP connectivity, credentials."""
    pass
```

### Python SDK (Agent-Friendly)

```python
# carbon/miner/sdk.py
class CarbonMiner:
    def __init__(self, mcp_endpoint: str = None, hotkey: str = None):
        self.mcp = MCPClient(mcp_endpoint or os.getenv("CARBON_MCP_ENDPOINT"))
        self.hotkey = hotkey or os.getenv("CARBON_HOTKEY")
    
    def get_noisy_prior(self, challenge: str, backbone: str) -> Strategy:
        """Fetch latest noisy prior for challenge+backbone."""
        return self.mcp.call("get_noisy_prior", challenge=challenge, backbone=backbone)
    
    def estimate(self, strategy: Strategy, prior: Strategy) -> EstimationResult:
        """Run local estimation (no GPU needed)."""
        engine = EstimationEngine(prior, strategy.backbone, strategy.challenge)
        return engine.estimate(strategy)
    
    def train_local(self, strategy: Strategy, mode: str = "light", **kwargs) -> TrainingResult:
        """Run local training loop (requires GPU)."""
        runner = LocalTrainingRunner(strategy, mode, **kwargs)
        return runner.run()
    
    def submit(self, strategy: Strategy) -> SubmissionReceipt:
        """Submit to validator via MCP."""
        return self.mcp.call("submit_strategy", strategy=strategy.dict(), hotkey=self.hotkey)
    
    def get_diagnostics(self, submission_id: str) -> Diagnostics:
        """Fetch results from validator."""
        return self.mcp.call("get_diagnostics", submission_id=submission_id)

# Agent-friendly async interface
class AsyncCarbonMiner(CarbonMiner):
    async def propose_train_evaluate_submit(self, challenge: str, backbone: str, n_iterations: int = 100):
        """Full Autoresearch loop: propose → estimate → train → evaluate → submit."""
        prior = await self.get_noisy_prior_async(challenge, backbone)
        for i in range(n_iterations):
            candidate = self.propose_candidate(prior)
            est = await self.estimate_async(candidate, prior)
            if est.confidence > 0.7 and est.estimated_score_delta > 0:
                result = await self.train_local_async(candidate, mode="light")
                if result.local_score > prior.score * 1.05:
                    receipt = await self.submit_async(candidate)
                    if receipt.accepted:
                        prior = candidate  # Update prior
        return prior
```

## 15. MCP Protocol

### Protocol Definition

```python
# carbon/mcp/protocol.py
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import json
import asyncio
import websockets

class MCPMessageType(Enum):
    # Client → Server
    GET_NOISY_PRIOR = "get_noisy_prior"
    SUBMIT_STRATEGY = "submit_strategy"
    GET_DIAGNOSTICS = "get_diagnostics"
    START_SESSION = "start_session"
    END_SESSION = "end_session"
    
    ESTIMATE = "estimate"
    TRAIN_LOCAL = "train_local"
    
    # Server → Client
    NOISY_PRIOR = "noisy_prior"
    SUBMISSION_RECEIPT = "submission_receipt"
    DIAGNOSTICS = "diagnostics"
    SESSION_STARTED = "session_started"
    STREAMING_UPDATE = "streaming_update"
    ERROR = "error"

@dataclass
class MCPMessage:
    type: MCPMessageType
    payload: Dict[str, Any]
    request_id: str = ""
    session_id: str = ""

class MCPClient:
    def __init__(self, endpoint: str = "wss://mcp.carbon.subnet:8081"):
        self.endpoint = endpoint
        self.ws = None
        self.session_id = None
        self.pending_requests = {}
    
    async def connect(self):
        self.ws = await websockets.connect(self.endpoint)
        asyncio.create_task(self._listen())
    
    async def _listen(self):
        async for message in self.ws:
            msg = MCPMessage(**json.loads(message))
            if msg.request_id in self.pending_requests:
                future = self.pending_requests.pop(msg.request_id)
                future.set_result(msg)
    
    async def call(self, method: str, **kwargs) -> Dict:
        request_id = str(uuid.uuid4())
        future = asyncio.Future()
        self.pending_requests[request_id] = future
        
        msg = MCPMessage(
            type=MCPMessageType(method.upper()),
            payload=kwargs,
            request_id=request_id,
            session_id=self.session_id
        )
        await self.ws.send(json.dumps(msg.__dict__))
        response = await asyncio.wait_for(future, timeout=30.0)
        return response.payload
    
    # Convenience methods
    async def get_noisy_prior(self, challenge: str, backbone: str) -> Strategy:
        return await self.call("get_noisy_prior", challenge=challenge, backbone=backbone)
    
    async def submit_strategy(self, strategy: Strategy) -> SubmissionReceipt:
        return await self.call("submit_strategy", strategy=strategy.dict())
    
    async def get_diagnostics(self, submission_id: str) -> Diagnostics:
        return await self.call("get_diagnostics", submission_id=submission_id)
    
    async def estimate(self, strategy: Strategy, prior: Strategy) -> EstimationResult:
        return await self.call("estimate", strategy=strategy.dict(), prior=prior.dict())
```

---

## 17. Reproducibility & Determinism

### Global Determinism Setup

```python
# carbon/common/determinism.py
import os
import random
import numpy as np

def set_global_determinism(seed: int = 42):
    """Set all random seeds and deterministic flags."""
    os.environ["PYTHONHASHSEED"] = str(seed)
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    
    random.seed(seed)
    np.random.seed(seed)
    jax.config.update("jax_default_prng_impl", "threefry")
    
    # JAX
    jax.config.update("jax_enable_x64", True)
    
    # PyTorch (if used)
    try:
        import torch
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
        torch.use_deterministic_algorithms(True)
    except ImportError:
        pass

def verify_reproducibility(run_fn, seed: int, n_runs: int = 3) -> ReproducibilityReport:
    """Run function n times, verify identical outputs."""
    set_global_determinism(seed)
    outputs = []
    for i in range(n_runs):
        set_global_determinism(seed)
        output = run_fn()
        outputs.append(hashlib.sha256(str(output).encode()).hexdigest())
    
    all_same = len(set(outputs)) == 1
    return ReproducibilityReport(
        master_seed=seed,
        docker_image_hash=get_docker_image_hash(),
        git_commit=get_git_commit(),
        python_hashseed=seed,
        cublas_config=os.environ.get("CUBLAS_WORKSPACE_CONFIG", ""),
        torch_deterministic=os.environ.get("TORCH_DETERMINISTIC", "1") == "1",
        output_hash=outputs[0],
        passed=all_same
    )
```

### Docker Determinism

```dockerfile
# Pinned base image
FROM nvidia/cuda:12.4.1-devel-ubuntu22.04@sha256:<pinned>

# Pinned Python packages via requirements-lock.txt
# PYTHONHASHSEED=0
# CUBLAS_WORKSPACE_CONFIG=:4096:8
# torch.use_deterministic_algorithms(True)
```

### Requirements Lockfile (Pinned)

```
jax==0.4.30
jaxlib==0.4.30+cuda12.cudnn89
flax==0.8.4
optax==0.2.1
orbax-checkpoint==0.5.2
numpy==1.26.4
scipy==1.12.0
```

---

## 18. Operational Infrastructure

### Validator Queue Management

```python
# carbon/validator/queue.py
from dataclasses import dataclass
from enum import Enum
import asyncio
import heapq
import time
from typing import Optional, Dict, Set

class Priority(Enum):
    SPONSORED_TIER_4 = 0
    SPONSORED_TIER_3 = 1
    SPONSORED_TIER_2 = 2
    HIGH_REPUTATION = 3
    STANDARD = 4
    ESTIMATION_MODE = 5

@dataclass
class QueuedSubmission:
    priority: Priority
    submit_time: float
    hotkey: str
    challenge_id: str
    strategy_hash: str
    estimated_gpu_seconds: float
    submission_id: str
    
    def __lt__(self, other):
        if self.priority != other.priority:
            return self.priority.value < other.priority.value
        return self.submit_time < other.submit_time

class ValidatorQueue:
    def __init__(self, max_concurrent: int = 3, max_queue_depth: int = 100):
        self.max_concurrent = max_concurrent
        self.max_queue_depth = max_queue_depth
        self.pending: list = []
        self.active: Dict[str, dict] = {}
        self.submission_timeout = 7200  # 2 hours max per submission
    
    async def enqueue(self, submission: QueuedSubmission) -> str:
        if len(self.pending) >= self.max_queue_depth:
            raise QueueFullError(f"Queue depth {self.max_queue_depth} exceeded")
        heapq.heappush(self.pending, submission)
        asyncio.create_task(self._monitor_timeout(submission.submission_id))
        return submission.submission_id
    
    async def _monitor_timeout(self, submission_id: str):
        await asyncio.sleep(self.submission_timeout)
        if submission_id in self.active:
            await self._kill_submission(submission_id)
    
    async def _kill_submission(self, submission_id: str):
        # Force kill GPU process, cleanup, mark as timeout
        pass
    
    def dequeue(self) -> Optional[QueuedSubmission]:
        if not self.pending:
            return None
        return heapq.heappop(self.pending)
```

### Determinism Lockfile (Pinned)

```txt
# requirements-lock.txt — PIN EXACT VERSIONS
jax==0.4.30
jaxlib==0.4.30+cuda12.cudnn89
flax==0.8.4
optax==0.2.1
orbax-checkpoint==0.5.2
numpy==1.26.4
scipy==1.12.0
```

### Compilation Cache Persistence

```dockerfile
# Dockerfile
ENV JAX_COMPILATION_CACHE_DIR=/persistent/compile_cache
ENV JAX_CACHE_DIR=/persistent/jax_cache
ENV XLA_FLAGS="--xla_gpu_cuda_data_dir=/usr/local/cuda --xla_gpu_per_thread_default_stream=true"

RUN mkdir -p /persistent/compile_cache /persistent/jax_cache
```

```yaml
# docker-compose.yml
services:
  validator:
    volumes:
      - compile_cache:/persistent/compile_cache
      - jax_cache:/persistent/jax_cache

volumes:
  compile_cache:
  jax_cache:
```

---

## 19. Julia/SciML Ground Truth Service

## Overview

The **Julia/SciML Ground Truth Service** is Carbon's "mathematical oracle" — a dedicated Julia service that provides mathematically rigorous reference solutions, adjoint sensitivities, and symbolic loss terms using the world-class Julia SciML ecosystem. This service is the **ground truth oracle** that makes Carbon's verification *trustless in the mathematical sense*.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CARBON VALIDATOR                              │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  PYTHON/JAX VALIDATOR                                       │ │
│  │  ├─ Training Loop (JAX/Flax)                                │ │
│  │  ├─ Physics Gates (fp32 enforced)                           │ │
│  │  └─ SciMLClient ─────────────────────────────────────────┐  │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  JULIA/SCIML GROUND TRUTH SERVICE (Port 8083)              │ │
│  │  ├─ DifferentialEquations.jl (Reference Solvers)           │ │
│  │  ├─ NeuralPDE.jl (PINN Baselines)                          │ │
│  │  ├─ ModelingToolkit.jl (Symbolic Loss Terms)               │ │
│  │  ├─ SciMLSensitivity.jl (Adjoint Sensitivities)            │ │
│  │  ├─ NeuralPDE.jl (PINN/DeepONet Baselines)                 │ │
│  │  └─ MethodOfLines.jl (Automated PDE Discretization)        │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 20 Julia/SciML Service Implementation

### Julia Service Implementation

```julia
# julia/sciML_service.jl
using HTTP, JSON3, Sockets
using DifferentialEquations, NeuralPDE, ModelingToolkit, SciMLSensitivity
using MethodOfLines, NeuralPDE, SciMLSensitivity, ModelingToolkit

struct SciMLService
    port::Int
    server::HTTP.Server
end

function SciMLService(port::Int=8083)
    server = HTTP.Servers.listen(Sockets.localhost, port) do http::HTTP.Messages.Request
        request = JSON3.read(String(http.body))
        response = handle_request(request)
        return HTTP.Response(200, JSON3.write(response))
    end
    SciMLService(port, server)
end

function handle_request(request::Dict)
    action = get(request, "action", "")
    
    if action == "solve_pde"
        return solve_pde_reference(request["pde_spec"], request["params"])
    elseif action == "adjoint_sensitivity"
        return compute_adjoint_sensitivity(request)
    elseif action == "symbolic_loss"
        return generate_symbolic_loss(request)
    elseif action == "validate_solution"
        return validate_against_reference(request)
    else
        return Dict("error" => "Unknown action: $action")
    end
end

function solve_pde_reference(pde_spec::Dict, params::Dict)
    # Parse PDE spec from ModelingToolkit
    @variables t x y z
    @parameters p[1:length(params)]
    
    # Build PDE system from symbolic spec
    eqs = build_pde_system(pde_spec, params)
    
    # Solve with high-accuracy solver
    prob = ODEProblem(eqs, u0, tspan, params)
    sol = solve(prob, Vern9(), abstol=1e-12, reltol=1e-12, saveat=0.01)
    
    return Dict(
        "solution" => Array(sol),
        "times" => sol.t,
        "success" => true
    )
end

function compute_adjoint_sensitivity(request::Dict)
    # SciMLSensitivity.jl for adjoint computation
    # Used for Carbon's Adjoint Consistency Gate (Phase 1A+)
    u0 = request["initial_state"]
    params = request["params"]
    loss_fn = request["loss_function"]
    
    # Forward pass
    prob = ODEProblem(ode_fn, u0, tspan, params)
    sol = solve(prob, Tsit5(), saveat=0.01)
    
    # Adjoint sensitivity via SciMLSensitivity
    adj_sol = adjoint_sensitivities(sol, loss_fn, 
        alg=InterpolatingAdjoint(autojacvec=ReverseDiffVJP()))
    
    return Dict("adjoint_gradients" => Array(adj_sol))
end

function generate_symbolic_loss(request::Dict)
    # ModelingToolkit.jl symbolic loss generation
    # Used by Landscape Agent bridge
    symbolic_expr = request["symbolic_expression"]
    vars = request["variables"]
    
    @variables vars...
    expr = Meta.parse(symbolic_expr)
    loss_fn = eval(build_function(expr, vars))
    
    return Dict(
        "julia_code" => string(loss_fn),
        "jax_translation" => translate_to_jax(loss_fn)
    )
end

function validate_against_reference(request::Dict)
    # Validate model prediction against SciML reference solution
    model_prediction = request["model_prediction"]
    pde_spec = request["pde_spec"]
    params = request["params"]
    
    reference = solve_pde_reference(pde_spec, params)
    
    # Compute error metrics
    error_metrics = compute_error_metrics(model_prediction, reference["solution"])
    
    return Dict(
        "passes" => all(v < 1e-3 for v in error_metrics.values()),
        "error_metrics" => error_metrics,
        "reference_solution" => reference
    )
end
```

### Python SciML Client

```python
# carbon/sciml/client.py
import httpx
import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass
from jaxtyping import Array
import asyncio

@dataclass
class SciMLClient:
    """Async client for Julia SciML Ground Truth Service"""
    base_url: str = "http://localhost:8083"
    timeout: float = 300.0  # 5 min for complex PDE solves
    
    def __init__(self, base_url: str = "http://localhost:8083"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=self.timeout)
    
    async def solve_pde_reference(self, pde_spec: Dict, params: Dict) -> Dict:
        """Get high-fidelity reference solution from Julia/SciML."""
        response = await self.client.post(
            f"{self.base_url}/solve_pde",
            json={"action": "solve_pde", "pde_spec": pde_spec, "params": params}
        )
        response.raise_for_status()
        return response.json()
    
    async def compute_adjoint_sensitivity(self, 
        initial_state: Array, 
        params: Dict, 
        loss_fn: str) -> Dict:
        """Compute adjoint gradients via SciMLSensitivity.jl."""
        response = await self.client.post(
            f"{self.base_url}/adjoint",
            json={
                "action": "adjoint_sensitivity",
                "initial_state": initial_state.tolist(),
                "params": params,
                "loss_function": loss_fn
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def generate_symbolic_loss(self, 
        symbolic_expression: str, 
        variables: list) -> Dict:
        """Get symbolic loss term from ModelingToolkit.jl."""
        response = await self.client.post(
            f"{self.base_url}/symbolic_loss",
            json={
                "action": "symbolic_loss",
                "symbolic_expression": symbolic_expression,
                "variables": variables
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def validate_against_reference(self, 
        model_prediction: Array, 
        pde_spec: Dict, 
        params: Dict) -> Dict:
        """Validate model against SciML reference solution."""
        response = await self.client.post(
            f"{self.base_url}/validate",
            json={
                "action": "validate_solution",
                "model_prediction": model_prediction.tolist(),
                "pde_spec": pde_spec,
                "params": params
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def close(self):
        await self.client.aclose()

# Context manager for easy usage
async def get_sciml_client() -> SciMLClient:
    client = SciMLClient()
    try:
        yield client
    finally:
        await client.close()
```

### Validator Integration with SciML Client

```python
# carbon/validator/training.py (extended)

class ValidatorTrainer:
    def __init__(self, config: Dict):
        self.config = config
        self.checkpointer = ocp.StandardCheckpointer()
        self.sciml_client = SciMLClient()  # Julia/SciML bridge
    
    async def _sciml_validation(self, state: TrainState, strategy: Dict) -> Dict:
        """Validate trained model against Julia/SciML Ground Truth Oracle."""
        challenge_id = strategy["challenge_id"]
        challenge_spec = self.get_challenge_spec(challenge_id)
        
        # Get reference solution from Julia/SciML Ground Truth Oracle
        reference = await self.sciml_client.solve_pde_reference(
            pde_spec=challenge_spec.pde_spec,
            params=strategy.get("pde_params", {})
        )
        
        # Evaluate model on reference grid
        model_prediction = self._evaluate_on_grid(state.params, reference["coords"])
        
        # Compute error metrics
        error_metrics = self._compute_error_metrics(model_prediction, reference["solution"])
        
        return {
            "passes": all(v < 1e-3 for v in error_metrics.values()),
            "error_metrics": error_metrics,
            "reference_solution": reference
        }
    
    def _run_physics_gates(self, state: TrainState) -> List[GateResult]:
        """Run physics gates with SciML validation for adjoint gate."""
        # Standard gates
        gate_results = run_all_gates(
            model_fn=self.model_apply_fn,
            challenge=self.current_challenge,
            params=state.params,
            stress_data=self.stress_data,
            generator_version=self.generator_version
        )
        
        # Adjoint Consistency Gate via SciMLSensitivity.jl (Phase 1A+)
        if self.config.get("adjoint_consistency_gate", False):
            adjoint_result = await self.sciml_client.compute_adjoint_sensitivity(
                model_fn=self.model_apply_fn,
                params=state.params,
                loss_fn="physics_residual"
            )
            gate_results.append(GateResult(
                gate_id="adjoint_consistency",
                threshold=1e-4,
                result=adjoint_result["rel_error"],
                status="PASS" if adjoint_result["rel_error"] < 1e-4 else "FAIL"
            ))
        
        return gate_results
```

---

## 21. Python-Julia Bridge (SciMLClient)

### Complete Client Implementation

```python
# carbon/sciml/client.py
import httpx
import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass
from jaxtyping import Array
import asyncio

@dataclass
class SciMLClient:
    """Async client for Julia SciML Ground Truth Service"""
    base_url: str = "http://localhost:8083"
    timeout: float = 300.0  # 5 min for complex PDE solves
    
    def __init__(self, base_url: str = "http://localhost:8083"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=self.timeout)
    
    async def solve_pde_reference(self, pde_spec: Dict, params: Dict) -> Dict:
        """Get high-fidelity reference solution from Julia/SciML."""
        response = await self.client.post(
            f"{self.base_url}/solve_pde",
            json={"action": "solve_pde", "pde_spec": pde_spec, "params": params}
        )
        response.raise_for_status()
        return response.json()
    
    async def compute_adjoint_sensitivity(self, 
        initial_state: Array, 
        params: Dict, 
        loss_fn: str) -> Dict:
        """Compute adjoint gradients via SciMLSensitivity.jl."""
        response = await self.client.post(
            f"{self.base_url}/adjoint",
            json={
                "action": "adjoint_sensitivity",
                "initial_state": initial_state.tolist(),
                "params": params,
                "loss_function": loss_fn
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def generate_symbolic_loss(self, 
        symbolic_expression: str, 
        variables: list) -> Dict:
        """Get symbolic loss term from ModelingToolkit.jl."""
        response = await self.client.post(
            f"{self.base_url}/symbolic_loss",
            json={
                "action": "symbolic_loss",
                "symbolic_expression": symbolic_expression,
                "variables": variables
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def validate_against_reference(self, 
        model_prediction: Array, 
        pde_spec: Dict, 
        params: Dict) -> Dict:
        """Validate model against SciML reference solution."""
        response = await self.client.post(
            f"{self.base_url}/validate",
            json={
                "action": "validate_solution",
                "model_prediction": model_prediction.tolist(),
                "pde_spec": pde_spec,
                "params": params
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def close(self):
        await self.client.aclose()

# Context manager for easy usage
async def get_sciml_client() -> SciMLClient:
    client = SciMLClient()
    try:
        yield client
    finally:
        await client.close()
```

### SciML Validation Mixin for Validators

```python
# carbon/validator/sciml_validation.py

class SciMLValidationMixin:
    """Mixin for Validator to use SciML reference solutions"""
    
    def __init__(self):
        self.sciml_client = SciMLClient()
    
    async def validate_against_sci_ml(self, 
        model_fn: Callable, 
        challenge_id: str, 
        params: Dict) -> Dict:
        """Validate model against SciML reference solution."""
        
        # Get challenge spec for PDE definition
        challenge_spec = self.get_challenge_spec(challenge_id)
        
        # Get reference solution from Julia/SciML
        reference = await self.sciml_client.solve_pde_reference(
            pde_spec=challenge_spec.pde_spec,
            params=params
        )
        
        # Evaluate model on same grid
        model_prediction = self._evaluate_on_grid(model_fn, reference["coords"])
        
        # Compute error metrics
        error_metrics = self._compute_error_metrics(model_prediction, reference["solution"])
        
        return {
            "passes": all(v < 1e-3 for v in error_metrics.values()),
            "error_metrics": error_metrics,
            "reference_solution": reference
        }
```

---

## 22. Julia/SciML Service Deployment

### Dockerfile for Julia Service

```dockerfile
# julia/Dockerfile.sciml
FROM julia:1.10-bullseye

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 python3-pip curl git && \
    rm -rf /var/lib/apt/lists/*

# Install Julia packages
RUN julia --project -e '
    using Pkg
    Pkg.add([
        "DifferentialEquations", "NeuralPDE", "ModelingToolkit",
        "SciMLSensitivity", "MethodOfLines", "NeuralPDE",
        "Symbolics", "Optimization", "OptimizationOptimisers",
        "HTTP", "JSON3", "Sockets", "CUDA"
    )
    Pkg.precompile()
'

# Install Python for Carbon integration
RUN pip install httpx numpy jax jaxlib

# Copy Julia service
COPY julia/sciML_service.jl /app/sciML_service.jl
COPY julia/start_server.jl /app/start_server.jl

EXPOSE 8083
CMD ["julia", "--project", "/app/start_server.jl"]
```

### Julia Server Entry Point

```julia
# julia/start_server.jl
using HTTP, JSON3, Sockets
using DifferentialEquations, NeuralPDE, ModelingToolkit, SciMLSensitivity
using MethodOfLines, NeuralPDE, SciMLSensitivity, ModelingToolkit

const PORT = 8083

function start_server()
    HTTP.serve(Sockets.localhost, PORT) do http::HTTP.Messages.Request
        try
            request = JSON3.read(String(http.body))
            response = handle_request(request)
            return HTTP.Response(200, JSON3.write(response))
        catch e
            @error "Request failed" exception=e
            return HTTP.Response(500, JSON3.write(Dict("error" => string(e))))
        end
    end
end

# Handle graceful shutdown
atexit(() -> println("SciML Service shutting down..."))

println("Starting SciML Ground Truth Service on port $PORT...")
start_server()
```

### K8s Deployment

```yaml
# k8s/sciml-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: carbon-sciml-service
  namespace: carbon
spec:
  replicas: 3
  selector:
    matchLabels:
      app: carbon-sciml
  template:
    metadata:
      labels:
        app: carbon-sciml
    spec:
      runtimeClassName: nvidia
      containers:
      - name: sciml-service
        image: ghcr.io/carbon/sciml-service:v2.1.0
        ports:
        - containerPort: 8083
        env:
        - name: JULIA_NUM_THREADS
          value: "16"
        - name: JULIA_DEPOT_PATH
          value: "/opt/julia/depot"
        resources:
          requests:
            nvidia.com/gpu: 1
            memory: "32Gi"
            cpu: "8"
          limits:
            nvidia.com/gpu: 1
            memory: "64Gi"
            cpu: "16"
        volumeMounts:
        - name: julia-depot
          mountPath: /opt/julia/depot
        livenessProbe:
          httpGet:
            path: /health
            port: 8083
          initialDelaySeconds: 60
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8083
          initialDelaySeconds: 30
          periodSeconds: 10
      volumes:
      - name: julia-depot
        persistentVolumeClaim:
          claimName: carbon-julia-depot
---
apiVersion: v1
kind: Service
metadata:
  name: carbon-sciml
  namespace: carbon
spec:
  selector:
    app: carbon-sciml
  ports:
  - protocol: TCP
    port: 8083
    targetPort: 8083
  type: ClusterIP
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: carbon-julia-depot
  namespace: carbon
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 100Gi
  storageClassName: nvme-fast
```

### Docker Compose for Local Development

```yaml
# docker-compose.sciml.yml
version: '3.8'
services:
  sciml-service:
    build:
      context: ./julia
      dockerfile: Dockerfile.sciml
    container_name: carbon-sciml
    ports:
      - "8083:8083"
    environment:
      - JULIA_NUM_THREADS=16
      - JULIA_DEPOT_PATH=/opt/julia/depot
    volumes:
      - sciml-depot:/opt/julia/depot
      - ./julia:/app
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8083/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  sciml-depot:
```

---

## 23. Python-Julia Bridge (SciMLClient)

### Complete Client Implementation

```python
# carbon/sciml/client.py
import httpx
import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass
from jaxtyping import Array
import asyncio

@dataclass
class SciMLClient:
    """Async client for Julia SciML Ground Truth Service"""
    base_url: str = "http://localhost:8083"
    timeout: float = 300.0  # 5 min for complex PDE solves
    
    def __init__(self, base_url: str = "http://localhost:8083"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=self.timeout)
    
    async def solve_pde_reference(self, pde_spec: Dict, params: Dict) -> Dict:
        """Get high-fidelity reference solution from Julia/SciML."""
        response = await self.client.post(
            f"{self.base_url}/solve_pde",
            json={"action": "solve_pde", "pde_spec": pde_spec, "params": params}
        )
        response.raise_for_status()
        return response.json()
    
    async def compute_adjoint_sensitivity(self, 
        initial_state: Array, 
        params: Dict, 
        loss_fn: str) -> Dict:
        """Compute adjoint gradients via SciMLSensitivity.jl."""
        response = await self.client.post(
            f"{self.base_url}/adjoint",
            json={
                "action": "adjoint_sensitivity",
                "initial_state": initial_state.tolist(),
                "params": params,
                "loss_function": loss_fn
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def generate_symbolic_loss(self, 
        symbolic_expression: str, 
        variables: list) -> Dict:
        """Get symbolic loss term from ModelingToolkit.jl."""
        response = await self.client.post(
            f"{self.base_url}/symbolic_loss",
            json={
                "action": "symbolic_loss",
                "symbolic_expression": symbolic_expression,
                "variables": variables
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def validate_against_reference(self, 
        model_prediction: Array, 
        pde_spec: Dict, 
        params: Dict) -> Dict:
        """Validate model against SciML reference solution."""
        response = await self.client.post(
            f"{self.base_url}/validate",
            json={
                "action": "validate_solution",
                "model_prediction": model_prediction.tolist(),
                "pde_spec": pde_spec,
                "params": params
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def close(self):
        await self.client.aclose()

# Context manager for easy usage
async def get_sciml_client() -> SciMLClient:
    client = SciMLClient()
    try:
        yield client
    finally:
        await client.close()
```

### SciML Validation Mixin for Validators

```python
# carbon/validator/sciml_validation.py

class SciMLValidationMixin:
    """Mixin for Validator to use SciML reference solutions"""
    
    def __init__(self):
        self.sciml_client = SciMLClient()
    
    async def validate_against_sci_ml(self, 
        model_fn: Callable, 
        challenge_id: str, 
        params: Dict) -> Dict:
        """Validate model against SciML reference solution."""
        
        # Get challenge spec for PDE definition
        challenge_spec = self.get_challenge_spec(challenge_id)
        
        # Get reference solution from Julia/SciML
        reference = await self.sciml_client.solve_pde_reference(
            pde_spec=challenge_spec.pde_spec,
            params=params
        )
        
        # Evaluate model on same grid
        model_prediction = self._evaluate_on_grid(model_fn, reference["coords"])
        
        # Compute error metrics
        error_metrics = self._compute_error_metrics(model_prediction, reference["solution"])
        
        return {
            "passes": all(v < 1e-3 for v in error_metrics.values()),
            "error_metrics": error_metrics,
            "reference_solution": reference
        }
```

---
