# Scoring.md — Lean Emission Scoring & Challenge Score Bank

**Carbon Subnet**  
**Version:** 2.0 (July 2026)  
**Status:** Protocol Appendix — Security & Incentive Critical  
**Audience:** Simulation Engineers, Physics PhDs, Protocol Engineers, Auditors  
**Related:** `SPEC.md` §8, `Data_Management.md`, `POC_Burgers_FNO.md`, `Specialist_Bank.md`, `Landscape_Agent.md`, `appendices/Physics_Gates.md`, `appendices/Julia_SciML_Oracle.md`

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
3. Load Generator Pack + Score Pack for those versions (**reject** if missing or hash mismatch)
4. Derive seeds → generate train/eval/stress
8. Train under strategy
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

# === CARD REQUIRED FIELDS ===
card_required_fields:
  - challenge_id
  - scoring_version
  - scoring_pack_hash
  - generator_version
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

### 4.2 Physics Fidelity — Quadratic Barrier (Increasing Returns)

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

### 4.3 Robustness — Worst-Case Focus (80% Tail)

```python
def compute_robustness(stress_errors: Dict[str, Array], pack: ScorePack) -> Float:
    """
    Robustness = weighted sum over categories.
    80% tail (95th percentile) + 20% mean → worst-case focus.
    Category weights by engineering consequence severity.
    """
    lambda_mean = 0.20   # weight on mean
    beta = 0.20          # weight on mean in blend
    q = 0.95             # 95th percentile = tail
    
    category_weights = {
        "low_viscosity": 0.15,
        "high_amplitude_ic": 0.25,
        "steep_gradient": 0.30,
        "shock_regime": 0.30,
    }
    
    scores = []
    for cat, weight in category_weights.items():
        errors = stress_errors[cat]  # relative L2 errors per variant
        mean_err = jnp.mean(errors)
        tail_err = jnp.percentile(errors, 95)  # 95th percentile
        
        # Blend: 20% mean + 80% tail (95th percentile)
        r = 0.20 * jnp.mean(errors) + 0.80 * jnp.percentile(errors, 95)
        
        # Steep sigmoid mapping to [0,1] with sharpness
        r_score = 1.0 / (1.0 + jnp.exp(20.0 * (r - pack.tau_rob) / pack.tau_rob))
        
        scores.append(pack.category_weights[cat] * r_score)
    
    S_robust = 0.35 * jnp.sum(jnp.array(scores))
    return S_robust
```

**Why 80% Tail / 95th Percentile?**  
- **Engineering basis:** Design for worst-case / safety factor / extreme value theory / ASME V&V 40.  
- A model that fails catastrophically in 5% of regimes is **unsellable** for HIL/control/digital twin.  
- Mean-dominant metrics hide catastrophic tails; tail-dominant exposes them.

**Category Weights by Consequence Severity:**
| Category | Weight | Rationale |
|----------|--------|-----------|
| `shock_regime` | 0.30 | Shock capture failure → non-physical solutions, instability |
| `steep_gradient` | 0.30 | High-gradient regimes → loss of accuracy, instability |
| `high_amplitude_ic` | 0.25 | Large perturbations → nonlinear breakdown |
| `low_viscosity` | 0.15 | Well-resolved regime; lower consequence |

---

### 4.4 Generalization / Accuracy — 50% In-Dist + 50% OOD

```python
def compute_accuracy(model_fn, eval_data, ood_data, pack):
    # In-distribution
    pred_in = model_fn(eval_data.inputs)
    rel_l2_in = jnp.mean(jnp.abs(pred_in - eval_data.targets) / (jnp.abs(eval_data.targets) + 1e-8))
    
    # Out-of-distribution (extended envelope stress variants)
    pred_ood = model_fn(ood_data.inputs)
    rel_l2_ood = jnp.mean(jnp.abs(pred_ood - ood_data.targets) / (jnp.abs(ood_data.targets) + 1e-8))
    
    # Soft gate: warn if max_rel_l2 > 3 * tau_acc
    max_rel_l2 = jnp.max(jnp.abs(pred_ood - ood_data.targets) / (jnp.abs(ood_data.targets) + 1e-8))
    soft_gate_warning = jnp.maximum(0.0, rel_l2_ood - 3.0 * pack.tau_acc) / (3.0 * pack.tau_acc)
    
    S_in = 1.0 / (1.0 + rel_l2_in / pack.tau_acc)
    S_ood = 1.0 / (1.0 + rel_l2_ood / pack.ood_tau)
    
    # 50% in-dist, 50% OOD → forces generalization
    S_acc = 0.25 * (0.5 * (1.0 / (1.0 + rel_l2_in / pack.tau_acc)) + 
                    0.5 * (1.0 / (1.0 + rel_l2_ood / pack.ood_tau)))
    
    # Soft gate warning on card (not hard fail)
    soft_gate_warning = jnp.maximum(0.0, max_rel_l2 - 3.0 * pack.tau_acc) / (3.0 * pack.tau_acc)
    
    return S_acc, soft_gate_warning
```

**Why 50% OOD?**  
- Eval set is hidden but from *same distribution* as training → measures interpolation.  
- **OOD (extended envelope) measures extrapolation** — what matters for inverse design, extrapolation, digital twins.  
- 50/50 split forces miners to optimize for **extrapolation**, not interpolation.

---

### 4.5 Adjoint Consistency Gate — Steep Sigmoid (Only Differentiable Signal)

```python
def adjoint_gate_score(rel_error: float, tau: float = 1e-4, sharpness: int = 20) -> float:
    """
    Steep sigmoid around threshold.
    - rel_error = |adjoint_grad - fd_grad| / |fd_grad|
    - At rel_error = tau: score = 0.5
    - sharpness=20: usable gradient ~±2τ around threshold
    """
    return 1.0 / (1.0 + jnp.exp(sharpness * (rel_error - tau) / tau))

# Called via SciMLClient → SciMLSensitivity.jl (Julia/SciML oracle)
async def adjoint_consistency_gate(model_fn, params, loss_fn, tau=1e-4):
    adjoint_result = await sciml_client.compute_adjoint_sensitivity(
        model_fn=model_fn, params=params, loss_fn="physics_residual"
    )
    rel_error = adjoint_result["rel_error"]
    score = adjoint_gate_score(rel_error, tau=1e-4, sharpness=20)
    return GateResult(
        gate_id="adjoint_consistency",
        threshold=1e-4,
        result=rel_error,
        score=score,
        status="PASS" if score > 0.5 else "FAIL"
    )
```

**Why Sigmoid?**  
- Only gate with **exact gradient signal** (adjoint vs finite-difference).  
- Binary PASS/FAIL gives zero gradient → miners can't optimize toward it.  
- Steep sigmoid (sharpness=20) gives usable gradient in ±2τ band around threshold.  
- **Only gate with true gradient signal** — miners can optimize toward it.

---

### 4.6 Combined Score — Multiplicative (Series System Reliability)

```python
def compute_combined_score(S_phys: float, S_robust: float, S_acc: float,
                           hard_gate_score: float) -> float:
    """
    Multiplicative combination = series system reliability.
    Any near-zero component → near-zero total.
    No compensation: excellent physics cannot compensate for zero robustness.
    """
    if hard_gate_score < 0.99:  # any mandatory gate near failure
        return 0.0
    
    S_combined = S_phys * S_robust * S_acc
    return S_combined
```

**Why Multiplicative?**  
- **Series system reliability:** All subsystems must work.  
- **No compensation:** Excellent physics cannot compensate for zero robustness.  
- **No gaming:** Miners must excel in *all* dimensions.  
- **Series system reliability theory** (reliability engineering).

---

### 4.7 Emissions — Multiplicative in Components

```python
def compute_emission_weight(S_combined: float, blocks_since_win: int, 
                            half_life_blocks: int = 21600) -> float:
    """
    Emission weight ∝ S_combined * exp(-Δblocks / t_half)
    Multiplicative in components → no component can be near-zero.
    """
    decay = jnp.exp(-blocks_since_win / half_life_blocks)
    return S_combined * jnp.exp(-blocks_since_win / half_life_blocks)
```

---

## 5. Validator Selection Logic (Deterministic)

```python
# carbon/validator/registry_client.py

def load_score_engine(challenge_id: str, registry: ChallengeRegistry) -> ScoreEngine:
    meta = registry.active(challenge_id)  # scoring_version, generator_version, content hashes
    pack = ScoreBank.load(challenge_id, meta.scoring_version)
    
    # Cryptographic binding
    assert pack.content_hash == meta.scoring_pack_hash, "Score pack hash mismatch"
    assert pack.generator_version_required == meta.generator_version, \
        "Generator/scoring version skew"
    
    return ScoreEngine(pack, metric_registry)
```

| Failure Mode | Result |
|--------------|--------|
| Unknown challenge_id | Reject submission |
| Score pack hash ≠ registry | Halt eval (validator misconfig) |
| Generator/scoring version skew | Halt eval |
| Metric `definition` string unknown | Halt eval |
| Hard gate FAIL | Score = 0, write card with `gate_failed: true` |

**Consensus:** Validators loading different pack hashes produce divergent scores → caught by score mismatch / weight disagreement. Pack hashes pinned in validator image + registry.

---

## 6. Model Card Requirements (Lean Path)

Every scored run writes:

```json
{
  "challenge_id": "burgers1d_v0",
  "scoring_version": "1.0",
  "scoring_pack_hash": "sha256:...",
  "generator_version": "burgers1d_v0.1",
  "gate_results": [
    {"id": "conservation", "pass": true, "value": 0.001, "tau": 0.01}
  ],
  "physics_margins": {
    "e_res": 0.82, "e_cons": 0.91, "e_roll": 0.70
  },
  "S_physics": 0.81,
  "robustness_by_category": {
    "low_viscosity": {"mean": 0.04, "tail": 0.09, "r": 0.75},
    "high_amplitude_ic": {"mean": 0.06, "tail": 0.12, "r": 0.60},
    "steep_gradient": {"mean": 0.08, "tail": 0.15, "r": 0.55},
    "shock_regime": {"mean": 0.12, "tail": 0.22, "r": 0.45}
  },
  "S_physics": 0.81,
  "S_robustness": 0.68,
  "accuracy_eval": {"rel_l2_mean": 0.03, "S": 0.70, "ood": {"rel_l2_mean": 0.08, "S": 0.65}},
  "S_accuracy": 0.67,
  "S_combined": 0.65,
  "gate_failed": false,
  "scoring_pack_hash": "sha256:...",
  "scoring_version": "1.0",
  "challenge_id": "burgers1d_v0",
  "block_height": 1234567,
  "scoring_pack_hash": "sha256:...",
  "scoring_version": "1.0"
}
```

**Landscape ingests vectors (D1). Emissions use `S_combined` only.**

---

## 7. Explicit Non-Goals (Lean Path)

| Item | Where It Lives Instead |
|------|------------------------|
| Train loss curves as score | Training diagnostics only |
| Full inverse-design bakeoff | Product battery (Specialist Bank) |
| Deep HIL-horizon plant suite | PB-ROLL (Specialist Bank) |
| ONNX latency class | PB-LAT (Specialist Bank) |
| Landscape causal similarity | Forbidden as score term |
| Miner-supplied eval metrics | Ignored |

---

## 8. Score Bank Layout (Repo)

```
carbon/scoring/
  bank/
    burgers1d_v0/
      scoring_v1.0.yaml
      SCIENTIFIC_NOTES.md      # why τ and categories
    poisson2d_v0/
      scoring_v1.0.yaml
    ...
  metrics/
    residual.py                # named definitions
    conservation.py
    field_error.py
    rollout.py
  engine.py                    # load pack → run gates → soft legs
  registry_client.py           # resolve active versions + hashes
  tests/
    test_pack_schema.py
    test_bank_generator_alignment.py
    test_margin_monotonic.py
    test_hard_gate_zero.py
```

PoC may inline a single pack under `poc/configs/scoring_burgers1d.yaml` until the bank directory exists — same schema.

---

## 9. Versioning & Governance

| Change | Action |
|--------|--------|
| Tune τ or α | Bump `scoring_version`; old live challenges unchanged |
| Add stress category | Generator bump **and** scoring bump together |
| Change 40/35/25 split | Governance + scoring major version |
| Fix metric bug in code | Metric code version in card; consider rescoring policy |

**Historical scores remain comparable only within `(challenge_id, scoring_version)`.**

### Rescoring Policy (Immutable Scores at Eval Time)

> **Scores are immutable at evaluation time.**  
> A metric bug fix in `residual.py` creates a new `scoring_version`; only *future* evaluations use it. Historical scores are never rewritten. Emissions already paid are never clawed back.  
> *Rationale: Emissions already paid = economic finality. Re-scoring creates tax/accounting/legal nightmare.*

### Tie-Breaking in ChallengeWinnerTracker

```python
# Tie-breaking for identical S_combined (to 1e-6):
# 1. Lower physics_residual (better physics)
# 2. Lower blocks_since_win (more recent)
# 3. Miner hotkey hash (deterministic)
```

---

## 10. Phase 0 Reference Pack (Burgers-1D)

```yaml
# carbon/scoring/bank/burgers1d_v0/scoring_v1.0.yaml
challenge_id: burgers1d_v0
scoring_version: "1.0"
generator_version_required: "burgers1d_v0.1"
precision: fp32

weights:
  physics: 0.40
  robustness: 0.35
  accuracy: 0.25

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
    tau: 0.05
    mandatory: true

margin:
  type: quadratic_barrier

weights:
  physics: 0.40
  robustness: 0.35
  accuracy: 0.25

physics:
  weight: 0.40
  components:
    - key: mass_conservation
      alpha: 0.40
      tau: 1.0e-6
      definition: burgers_mass_conservation_l2
    - key: energy_stability
      alpha: 0.30
      tau: 1.0e-6
      definition: burgers_energy_stability_residual
    - key: boundary_satisfaction
      alpha: 0.20
      tau: 1.0e-4
      definition: boundary_residual_l2
    - key: rollout_stability
      alpha: 0.10
      tau: 1.0
      definition: short_rollout_rel_l2

robustness:
  weight: 0.35
  category_weights:
    low_viscosity: 0.15
    high_amplitude_ic: 0.25
    steep_gradient: 0.30
    shock_regime: 0.30
  lambda: 0.20
  beta: 0.20
  tail_quantile: 0.95
  tau_rob: 2.0e-1
  min_category_coverage: 0.90
  coverage_grace: true
  coverage_grace_factor: 0.5

accuracy:
  weight: 0.25
  field_error: relative_l2
  tau_acc: 1.0e-1
  ood_weight: 0.50
  ood_tau: 2.0e-1
  aggregate: mean
  soft_gate:
    enabled: true
    max_rel_l2_multiple: 3.0

combination:
  type: multiplicative

emissions:
  type: multiplicative
  half_life_blocks: 21600

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
```

---

## 11. Trustlessness Checklist

- [ ] Score Pack content hash pinned in Challenge Registry
- [ ] Generator version required by pack matches eval generators
- [ ] All metric definitions pure functions of (pred, ref, config) in fp32
- [ ] Seeds from public derivation path (Data Management)
- [ ] No miner fields enter gate thresholds or τ
- [ ] Card records pack hash + vectors
- [ ] Missing/mismatched pack → hard fail, not silent default
- [ ] Unit tests: monotonic margins, gate zero, category coverage enforce

---

## 12. Implementation Order

1. Schema + `ScoreEngine` + margin/gate unit tests  
2. Burgers pack + wire PoC `run_once`  
3. Model Card vector fields  
4. Registry hash pin (even local JSON registry for PoC)  
5. Bank consistency CI vs generator category IDs  
6. Remaining Phase-0 PDE packs  

---

## 13. Relationship to Other Docs

| Doc | Boundary |
|-----|----------|
| `Data_Management.md` | Seeds, train≠eval, stress categories, entropy floor |
| `SPEC.md` §8 | High-level 45/30/25 + hard-gate rule |
| **This file** | Formulas, pack schema, validator load path |
| `Specialist_Bank.md` | Product battery — **not** lean scoring |
| `Landscape_Agent.md` | Consumes card vectors; does not grade |
| `POC_Burgers_FNO.md` | First consumer of a single pack |
| `appendices/Physics_Gates.md` | Detailed gate implementations |
| `appendices/Julia_SciML_Oracle.md` | Adjoint gate + reference solution oracle |

---

## 14. Appendix: Physics Justification Appendix

### A.1 Quadratic Margin — Engineering Derivation

The quadratic barrier `m(e,τ) = 1 - (e/τ)²` is a **log-barrier / penalty function** standard in:
- Interior-point methods (Nocedal & Wright, *Numerical Optimization*)
- PDE-constrained optimization (Hinze et al., *Optimization with PDE Constraints*)
- Structural reliability (Melchers, *Structural Reliability Analysis and Prediction*)

**Safety factor interpretation:**  
Let `SF = τ / e` (safety factor). Then `m = 1 - 1/SF²`.  
- SF=1.0 (at threshold) → m=0  
- SF=2 (2× margin) → m=0.75  
- SF=10 → m=0.99 (99% score)  
Matches structural reliability: probability of failure ∝ 1/SFᵏ.

---

### A.2 Robustness Tail Weight — Extreme Value Theory

For i.i.d. errors with tail index ξ, the 95th percentile scales as `n^ξ`.  
Weighting 95th percentile at 80% ensures the score reflects the **maximum probable error** in operational use — consistent with ASME V&V 40, NASA STD-7009, ISO 16732-1 (fire safety engineering).

---

### A.3 Adjoint Gate Sharpness — Optimization Theory

The adjoint gate is the **only gate with exact gradient information** (via SciMLSensitivity.jl).  
A binary PASS/FAIL provides zero gradient → miners cannot optimize toward it.  
Steep sigmoid (sharpness=20) provides usable gradient in ±2τ band:  
`d/dx sigmoid(k(x-τ)) |_{x=τ} = k/4`. With sharpness=20, gradient = 5 at threshold — usable for optimization.

---

### A.4 Multiplicative Combination — Series System Reliability

For a system with components in series: `R_system = ∏ R_i`.  
If any `R_i ≈ 0`, system reliability ≈ 0.  
No compensation between subsystems — matches engineering design philosophy: **a chain is only as strong as its weakest link.**

---

## 15. Trustlessness Checklist

- [ ] Score Pack content hash pinned in Challenge Registry
- [ ] Generator version required by pack matches eval generators
- [ ] All metric definitions pure functions of (pred, ref, config) in fp32
- [ ] Seeds from public derivation path (Data Management)
- [ ] No miner fields enter gate thresholds or τ
- [ ] Card records pack hash + vectors
- [ ] Missing/mismatched pack → hard fail, not silent default
- [ ] Unit tests: monotonic margins, gate zero, category coverage enforce

---

## 16. Implementation Order

1. Schema + `ScoreEngine` + margin/gate unit tests  
2. Burgers pack + wire PoC `run_once`  
3. Model Card vector fields  
4. Registry hash pin (even local JSON registry for PoC)  
5. Bank consistency CI vs generator category IDs  
6. Remaining Phase-0 PDE packs  
---

*Lean scoring is a versioned, challenge-bound exam: hard gates kill, soft margins rank, vectors train the Landscape, scalars pay emissions. Validators only execute the registered Score Pack — they never improvise the exam.*
