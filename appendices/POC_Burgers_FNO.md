# PoC Build Guide — Burgers-1D × FNO-1D Full Loop

## TL;DR

**What this is:** The build plan for Carbon’s smallest end-to-end proof — one PDE, one backbone, full validator loop.

**The loop:** `strategy.json` → schema check → seeded train/eval/stress data → JAX retrain (FNO-1d) → metrics → hard physics gates → 45/30/25 score → Model Card on disk.

**Choices:** 1D viscous Burgers; operator map IC → solution at final time; FNO-1d only; no chain, MCP, Landscape, or multi-challenge.

**Why it matters:** Proves the mechanism (strategy in, not weights; train ≠ eval seeds; gates can zero score; card out) before scaling Phase 0.

**Done when:** Acceptance tests T1–T7 pass (schema reject, seed separation, full loop, gate fail, reproducibility, strategy discrimination, budget cap).

**Build order:** Milestone A data → B train → C protocol spine → D scoring → E harden. Do not expand scope until green.

**Read next if implementing:** §5 schema, §13 repo layout, §15 tests, §16 milestones.

---

**Carbon Subnet**  
**Version:** 1.0 (July 2026)  
**Status:** Phase-0 proof-of-concept build specification  
**Related:** `SPEC.md`, `appendices/Data_Management.md`, `appendices/JAX_Optimization.md`, `docs/TRUSTLESS_VERIFICATION_AND_DATA_GENERATION.md`

---

## 1. Purpose

Build the **smallest complete Carbon loop**:

```text
strategy.json → schema check → seeded train/eval/stress data
  → JAX retrain (FNO-1d) → metrics → hard physics gates
  → 45/30/25 score → Model Card
```

**Goal:** prove the *mechanism*, not SciML SOTA and not full subnet ops.

If this PoC passes its acceptance tests, Carbon’s atomic unit is real: miners submit **strategies**, validators **retrain**, eval data is **seed-generated**, gates can **zero** a run, and every run emits a **Model Card**.

---

## 2. Scope Lock

### In scope

| Item | Detail |
|------|--------|
| PDE | 1D viscous Burgers |
| Backbone | FNO-1d only |
| Operator form | IC → solution at final time \(u(\cdot,T)\) |
| Strategy JSON | Minimal but real schema |
| Data | Procedural generator; train ≠ eval ≠ stress seeds |
| Train | JAX, budget-capped |
| Gates | Finite, conservation, residual ceiling (+ BC if used) |
| Score | 45% physics / 30% robustness / 25% accuracy |
| Output | Model Card JSON on disk |
| Entry point | CLI `run_once` (no chain required) |

### Out of scope (explicit non-goals)

- Bittensor neuron / Yuma / emissions  
- MCP, Estimation Mode, Light Training productization  
- Landscape Agent, PySR, specialists, noisy prior service  
- Multi-challenge, multi-backbone, multi-physics  
- TPU, multi-GPU, full ONNX product pipeline  
- Adaptive stress, D9 routing, multi-fidelity curricula  
- “Best possible Burgers accuracy”

---

## 3. Challenge Definition

### 3.1 PDE

Viscous Burgers (1D):

\[
\partial_t u + u \, \partial_x u = \nu \, \partial_{xx} u
\]

- Domain: \(x \in [0,1]\), \(t \in [0, T]\)  
- Periodic or fixed BC — **pick one and freeze** in config (recommend periodic for FNO-1d simplicity)  
- \(\nu\) drawn from a closed interval in the generator envelope  

### 3.2 Operator learning task

Map initial condition to solution at final time:

\[
\mathcal{G}: u_0(x) \mapsto u(x, T)
\]

This avoids full spacetime rollout complexity in v0 while still supporting residual and conservation checks on the predicted field (and optional residual-in-time via a cheap diagnostic if implemented later).

### 3.3 Grid & envelope (freeze in YAML)

| Parameter | PoC default | Notes |
|-----------|-------------|-------|
| \(N_x\) | 128 | power-of-two friendly |
| \(T\) | 1.0 | fixed |
| \(\nu\) range | \([10^{-3}, 10^{-2}]\) | stress may use lower \(\nu\) |
| IC family | sum of sines, bounded coeffs | documented in generator |
| \(N_{\mathrm{train}}\) | 256–512 | keep wall-clock small |
| \(N_{\mathrm{eval}}\) | 64–128 | |
| \(N_{\mathrm{stress}}\) | 32–64 | harder envelope |

All values live in `poc/configs/challenge_burgers1d.yaml` — no magic numbers in code.

### 3.4 Reference solver

Classical, stable solver for labels (Fourier pseudo-spectral or conservative FD).  
**Not** the neural operator. Generator version string must change if the reference solver changes.

---

## 4. Backbone

**FNO-1d only** for PoC.

| Hyperparameter | Allowed in strategy | Validator clamp |
|----------------|---------------------|-----------------|
| modes | yes | max 32 |
| width | yes | max 64 |
| layers | yes | max 6 |

Default fixture: `modes=16, width=32, layers=4`.

Reject any `backbone != "fno1d"`.

---

## 5. Strategy Schema (`poc_v1`)

```json
{
  "schema_version": "poc_v1",
  "challenge_id": "burgers1d_v0",
  "backbone": "fno1d",
  "backbone_cfg": {
    "modes": 16,
    "width": 32,
    "layers": 4
  },
  "loss": {
    "data_mse": true,
    "data_mse_weight": 1.0,
    "physics_residual": true,
    "physics_residual_weight": 0.1,
    "conservation_penalty": false,
    "conservation_penalty_weight": 0.0
  },
  "optim": {
    "name": "adam",
    "lr": 0.001,
    "weight_decay": 0.0
  },
  "budget": {
    "max_steps": 2000,
    "batch_size": 32
  }
}
```

### Validation rules

1. JSON Schema draft enforced (`poc/schema/strategy_poc_v1.json`).  
2. Unknown keys → reject.  
3. `challenge_id` must equal `burgers1d_v0`.  
4. `backbone` must equal `fno1d`.  
5. Numeric fields clipped to safe ranges (lr, weights, modes, …).  
6. Validator **hard-caps** `max_steps` and `batch_size` regardless of miner request.

### Fixture strategies

| File | Intent |
|------|--------|
| `fixtures/strategy_data_only.json` | physics flags off |
| `fixtures/strategy_physics.json` | data + residual on |
| `fixtures/strategy_broken.json` | absurd lr / disabled safeguards → expect gate fail or NaNs |

---

## 6. Seed Hierarchy & Data Roles

Align with Data Management principles, simplified for local PoC:

```text
seed_material = challenge_id || role || local_nonce || run_id
seed = SHA256(seed_material) → uint64
```

| Role | Purpose |
|------|---------|
| `train` | training pairs |
| `eval` | held-out accuracy |
| `stress` | robustness (harder envelope) |

**Invariants**

- Same generator code for all roles  
- `train` seed material ≠ `eval` ≠ `stress`  
- Miner cannot supply eval/stress tensors  
- For reproducibility tests: fix `local_nonce` and `run_id`  
- For “fresh eval” demo: change `local_nonce` and show new eval hash  

Generator version: `burgers1d_v0.1` (bump on any envelope or solver change).

---

## 7. Losses

Boolean-masked unified loss from strategy flags:

```text
L = 1_data * w_data * MSE(pred, u_T)
  + 1_phys * w_phys * residual_loss(pred, u0, ν context)
  + 1_cons * w_cons * conservation_penalty(pred, u0)
```

**PoC residual:** enforce Burgers residual on a differentiable reconstruction or on a fixed time-diagnostic — keep implementation simple and documented in `train/losses.py`. Prefer clarity over perfect weak-form elegance.

**Conservation penalty (optional enable):** e.g. \(|\int \hat{u}_T - \int u_0|\) for periodic mass-style proxy appropriate to the frozen BC choice.

---

## 8. Training Loop

| Item | PoC policy |
|------|------------|
| Framework | JAX + Flax or Equinox |
| Device | 1× GPU preferred; CPU allowed for CI |
| Precision | compute bf16 optional; **gates and residual checks fp32** |
| Steps | `min(strategy.budget.max_steps, VALIDATOR_MAX_STEPS)` |
| Batch | clamped |
| Logging | step loss every N steps to card dynamics summary |
| Checkpoint | optional last params in memory for eval; disk optional |

No multi-host. No `lax.scan` requirement for PoC (allowed if it helps); simple Python step loop is fine if JIT’d step is clear.

---

## 9. Evaluation & Stress

After training:

1. Predict on eval set → relative L2 (or MSE) aggregate  
2. Predict on stress set → same metric  
3. Compute residual and conservation stats in fp32  
4. Run gates  
5. If gates pass → score; else combined = 0  

**Stress envelope (example):** lower \(\nu\), higher IC amplitude bounds, or both — fixed in challenge YAML under `stress_envelope`.

---

## 10. Gates (hard)

Config: `poc/configs/gates_burgers1d.yaml`

| Gate ID | Check | On fail |
|---------|-------|---------|
| `finite` | no NaN/Inf in predictions | combined = 0 |
| `conservation` | mass-proxy error ≤ `tau_mass` | combined = 0 |
| `residual_ceiling` | mean residual ≤ `tau_residual` | combined = 0 |
| `boundary` | only if non-periodic BC frozen | combined = 0 |

Thresholds are constants with short scientific notes in the YAML comments.  
Gate results always written to the Model Card even on failure.

---

## 11. Scoring

Only if all critical gates pass:

```text
accuracy   = norm_map(eval_error)      # higher is better
robustness = norm_map(stress_error)
physics    = norm_map(residual, conservation_stats)

combined = 0.45 * physics + 0.30 * robustness + 0.25 * accuracy
```

`norm_map`: frozen piecewise or logistic curves in config (not learned). Document reference points in YAML.

---

## 12. Model Card Schema (PoC)

```json
{
  "card_id": "uuid",
  "challenge_id": "burgers1d_v0",
  "backbone": "fno1d",
  "strategy_hash": "sha256:...",
  "strategy": {},
  "seeds": {
    "train": "...",
    "eval": "...",
    "stress": "...",
    "local_nonce": "...",
    "run_id": "..."
  },
  "generator_version": "burgers1d_v0.1",
  "software": {
    "git_commit": "...",
    "jax": "...",
    "python": "..."
  },
  "metrics": {
    "eval_rel_l2": 0.0,
    "stress_rel_l2": 0.0,
    "residual_mean": 0.0,
    "conservation_error": 0.0
  },
  "gates": [
    {"id": "finite", "pass": true},
    {"id": "conservation", "pass": true, "value": 0.0, "tau": 0.0},
    {"id": "residual_ceiling", "pass": true, "value": 0.0, "tau": 0.0}
  ],
  "score": {
    "physics": 0.0,
    "robustness": 0.0,
    "accuracy": 0.0,
    "combined": 0.0,
    "gate_failed": false
  },
  "budget_used": {
    "steps": 0,
    "wall_s": 0.0
  }
}
```

Write path: `artifacts/model_cards/<card_id>.json`  
Optional: append `card_id` + `strategy_hash` + `combined` to `artifacts/registry.jsonl` (local registry stub).

---

## 13. Repository Layout

```text
poc/
  README.md
  configs/
    challenge_burgers1d.yaml
    gates_burgers1d.yaml
    validator_limits.yaml      # max_steps, max_batch, lr clips
  schema/
    strategy_poc_v1.json
  generators/
    burgers1d.py               # IC sampling, reference solve, seed API
  models/
    fno1d.py
  train/
    loop.py
    losses.py
  eval/
    metrics.py
    gates.py
    score.py
  validator/
    schema_check.py
    run_once.py                # main entry
  fixtures/
    strategy_data_only.json
    strategy_physics.json
    strategy_broken.json
  tests/
    test_schema.py
    test_seed_separation.py
    test_gate_fail.py
    test_reproducibility.py
    test_full_loop.py
    test_strategy_discrimination.py
```

Package path may live under transitional `hydrogen/` or top-level `poc/` — pick one and document in `poc/README.md`. Prefer **`poc/`** for clarity until namespace rename is complete.

---

## 14. Entry Points

```bash
# Full loop
python -m poc.validator.run_once poc/fixtures/strategy_physics.json

# Explicit nonce for reproducibility
python -m poc.validator.run_once poc/fixtures/strategy_physics.json \
  --local-nonce 42 --run-id poc_repro_1

# Broken path
python -m poc.validator.run_once poc/fixtures/strategy_broken.json
```

Exit codes:

| Code | Meaning |
|------|--------|
| 0 | Completed; card written (even if gate failed / score 0) |
| 2 | Schema / validation reject |
| 3 | Internal train/eval error |

---

## 15. Acceptance Tests (Definition of Done)

| ID | Test | Pass criteria |
|----|------|----------------|
| T1 | Schema reject | Invalid backbone / unknown key → exit 2 |
| T2 | Seed separation | Train/eval/stress sample payload hashes differ |
| T3 | Full loop | Valid strategy → Model Card on disk with all required fields |
| T4 | Gate fail | Broken strategy → `gate_failed=true`, `combined=0`, failed gate listed |
| T5 | Reproducibility | Same strategy + same seeds twice → combined within ε (e.g. 1e-5 relative or exact on CPU) |
| T6 | Discrimination | data-only vs physics fixtures produce different scores or different gate outcomes |
| T7 | Budget cap | Strategy with huge `max_steps` still stops at validator cap; card reports capped steps |

CI should run T1–T7 on CPU with reduced `N_train` / steps if needed via env `POC_FAST=1`.

---

## 16. Build Sequence

Execute in order; do not skip ahead to MCP or Landscape.

### Milestone A — Data truth

1. Challenge + gates YAML  
2. Seed API + Burgers generator + reference solver  
3. Unit test: seed separation + fixed-seed determinism of labels  

**Exit:** generated batches stable under fixed seed.

### Milestone B — Train path

4. FNO-1d model  
5. Data-MSE-only train loop  
6. Eval relative L2  

**Exit:** data-only fixture trains and writes metrics (gates may still be stubbed).

### Milestone C — Protocol spine

7. Schema check  
8. Gates + zero-score path  
9. Model Card writer + registry.jsonl stub  
10. `run_once` CLI  

**Exit:** T3, T4 green.

### Milestone D — Carbon scoring

11. Physics residual + conservation loss terms  
12. Stress envelope split  
13. 45/30/25 scoring  
14. Fixtures + T5–T7  

**Exit:** all acceptance tests green.

### Milestone E — Harden

15. Validator limit clamps  
16. Software version stamping on card  
17. `poc/README.md` with exact commands and expected card paths  
18. Optional: pin JAX version in `poc/requirements.txt`  

**Exit:** external contributor can clone and run fixtures without tribal knowledge.

---

## 17. Validator Limits (defaults)

`poc/configs/validator_limits.yaml`:

```yaml
max_steps: 5000
max_batch_size: 64
max_modes: 32
max_width: 64
max_layers: 6
lr_min: 1.0e-5
lr_max: 1.0e-2
max_wall_s: 600
```

PoC may use lower limits under `POC_FAST=1` for CI.

---

## 18. Determinism Notes

- Document device used on the card (`cpu` / `gpu`).  
- Reproducibility acceptance may be **stricter on CPU** than GPU.  
- Prefer fixed seeds for all dropout-free FNO paths.  
- Gate math in fp32 with explicit reductions.  

Full multi-validator consensus profiles are **out of scope**; note on card is enough for PoC.

---

## 19. Mapping to Full Carbon (forward compatibility)

| PoC element | Full subnet successor |
|-------------|----------------------|
| `run_once` | Validator neuron train worker |
| `local_nonce` | block hash / session seed hierarchy |
| `registry.jsonl` | on-chain verification registry |
| Fixtures | Miner MCP submissions |
| Single stress envelope | ProceduralStressGenerator families |
| Manual fixtures discrimination | ChallengeWinnerTracker |
| Card JSON | Landscape Agent ingest (D1) |

Do not implement successors inside `poc/` until T1–T7 pass.

---

## 20. Proof Statement (after green tests)

The PoC is complete when we can truthfully claim:

1. A **strategy** (not weights) is the submission unit.  
2. The system **retrains** an FNO-1d under that strategy with a hard budget.  
3. Train/eval/stress data are **seed-derived** and role-separated.  
4. **Hard physics gates** can zero the combined score.  
5. Scoring uses **physics / robustness / accuracy** weights.  
6. Every completed run emits a **Model Card** with strategy, seeds, gates, and scores.  
7. Results are **reproducible** under fixed seeds within documented tolerance.

That is Carbon’s atomic loop for one PDE and one backbone.

---

## 21. Thesis

Build **Burgers-1D + FNO-1D** as a vertical slice of validator-controlled, trustless, gated training. Keep the surface area small enough to finish, and the protocol faithful enough that Phase-0 multi-challenge work is multiplication—not reinvention.

---

*Canonical build specification for the Carbon Phase-0 mechanism proof. Implementation should follow milestones A–E and must not expand scope until acceptance tests T1–T7 are green.*
