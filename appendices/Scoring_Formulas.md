# Scoring Formulas & Score Pack Detail

**Parent:** [`Scoring.md`](./Scoring.md)

This file holds the full Score Pack schemas, soft-leg formulas, and implementation notes that pair with the lean scoring overview in `Scoring.md`.

---

## 3. Score Pack Schema (YAML)

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
  - id: short_rollout
    type: rollout_stable
    steps: 10
    mandatory: true

margin:
  type: quadratic_barrier
  # see §4 soft-leg formulas

stress_categories:
  min_coverage: 1.0
  categories: [viscosity_range, ic_amplitude, boundary_shift]

card_required_fields:
  - pack_hash
  - gate_vector
  - physics_vector
  - robustness_vector
  - accuracy_scalar
  - S_combined
```

Changing weights, τ, or category sets is a **scoring_version** bump.

---

## 4. Lean Scoring Formulas (Protocol)

### 4.1 Hard Gates — Steep Sigmoid (Differentiable Binary)

Hard gates evaluated in **fp32**. Critical failures zero the submission.

A pure binary PASS/FAIL provides zero gradient for search diagnostics; a steep sigmoid (sharpness ≈ 20) provides usable gradient in a ±2τ band while remaining fail-closed for emissions:

- If any mandatory gate fails → `gate_failed = true`, `S_combined = 0`
- Soft legs are still recorded on the Model Card for Landscape diagnostics when useful

### 4.2 Physics Fidelity — Quadratic Barrier (Increasing Returns)

Physics leg rewards **margin** under conservation / residual thresholds across stress draws, not average table fit alone.

### 4.3 Robustness

Worst-case (or category-pooled) performance across required stress categories. Missing category coverage fails or zeros the robustness leg per pack policy.

### 4.4 Accuracy / Generalization

Held-out error after gates pass. Lowest weight by design so pure memorization cannot dominate emissions.

### 4.5 Combined Score

```text
if gate_failed:
    S_combined = 0
else:
    S_combined = w_p * S_physics + w_r * S_robustness + w_a * S_accuracy
```

Weights from the active Score Pack (must sum to 1.0).

---

## 5–15. Implementation Notes

- All metric definitions pure functions of `(pred, ref, config)` in fp32
- Seeds from public derivation path (`Data_Management.md`)
- No miner fields enter gate thresholds or τ
- Card records pack hash + vectors
- Missing/mismatched pack → hard fail, not silent default
- Unit tests: monotonic margins, gate zero, category coverage enforce

## 16. Implementation Order

1. Schema + `ScoreEngine` + margin/gate unit tests  
2. Burgers pack + wire PoC `run_once`  
3. Model Card vector fields  
4. Registry hash pin (even local JSON registry for PoC)  
5. Bank consistency CI vs generator category IDs  
6. Remaining Phase-0 PDE packs  

---

*Lean scoring is a versioned, challenge-bound exam: hard gates kill, soft margins rank, vectors train the Landscape, scalars pay emissions. Validators only execute the registered Score Pack — they never improvise the exam.*

> **Note for maintainers:** The pre-split monofile Scoring appendix at commit `21f38f4` contained the full expanded YAML examples and derivation notes. If any challenge-specific pack tables are missing from this condensed formulas file, restore them from that commit into this document before freeze.
