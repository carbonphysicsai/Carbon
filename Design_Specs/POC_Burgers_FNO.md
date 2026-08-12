# PoC Build Guide — Burgers-1D × FNO-1D Full Loop

## TL;DR

**What this is:** The build plan for Carbon’s smallest end-to-end proof — one PDE, one backbone, full **lean** validator loop.

**The loop:** `strategy.json` → schema check → seeded train/eval/stress data → JAX retrain (FNO-1d) → metrics → hard physics gates → 45/30/25 score → Model Card on disk.

**Choices:** 1D viscous Burgers; operator map IC → solution at final time; FNO-1d only; no chain, MCP, Landscape, specialists, or product battery.

**Path class:** **Lean eval only.** Product battery (INV / deep plant / ADV / ONNX certs) is out of scope — see `Specialist_Bank.md`.

**Why it matters:** Proves the mechanism (strategy in, not weights; train ≠ eval seeds; gates can zero score; card out) before scaling Phase 0.

**Done when:** Acceptance tests T1–T7 pass (schema reject, seed separation, full loop, gate fail, reproducibility, strategy discrimination, budget cap).

**Build order:** Milestone A data → B train → C protocol spine → D scoring → E harden. Do not expand scope until green.

**Read next if implementing:** §5 schema, §13 repo layout, §15 tests, §16 milestones.

---

**Carbon Subnet**  
**Version:** 1.1 (July 2026)  
**Status:** Phase-0 proof-of-concept build specification  
**Related:** `SPEC.md`, `appendices/Data_Management.md`, `appendices/JAX_Optimization.md`, `docs/TRUSTLESS_VERIFICATION_AND_DATA_GENERATION.md`

---

## 1. Purpose

Build the **smallest complete Carbon lean loop**:

```text
strategy.json → schema check → seeded train/eval/stress data
  → JAX retrain (FNO-1d) → metrics → hard physics gates
  → 45/30/25 score → Model Card
```

**Goal:** prove the *mechanism*, not SciML SOTA, not full subnet ops, not commercial productization.

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
- **Product battery** (PB-INV, deep PB-ROLL, PB-ADV, PB-LAT, PB-ART)  
- Multi-challenge, multi-backbone, multi-physics  
- TPU, multi-GPU, full ONNX commercial pipeline  
- Adaptive stress, D9 routing, multi-fidelity curricula  
- “Best possible Burgers accuracy”  
- Any package path named `hydrogen/` — use **`poc/`** only

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

All values live in `poc/configs/challenge_burgers1d.yaml`.

### 3.4 Reference solver

Classical, stable solver for labels. **Not** the neural operator. Generator version string must change if the reference solver changes.

---

## 4. Backbone

**FNO-1d only.** Reject any `backbone != "fno1d"`. Clamp modes/width/layers in validator limits.

---

## 5. Strategy Schema (`poc_v1`)

Minimal schema with boolean loss enables, optim, budget — as previously specified in `poc/schema/strategy_poc_v1.json`. Unknown keys reject; validator hard-caps steps and batch.

---

## 6. Seed Hierarchy & Data Roles

```text
seed_material = challenge_id || role || local_nonce || run_id
seed = SHA256(seed_material) → uint64
```

| Role | Purpose |
|------|---------|
| `train` | training pairs |
| `eval` | held-out accuracy |
| `stress` | robustness (harder envelope) |

Train ≠ eval ≠ stress. Miner cannot supply eval/stress tensors.

---

## 7–12. Losses, Train, Eval, Gates, Score, Model Card

Unchanged policy from v1.0: boolean-masked losses; JAX train with budget cap; fp32 gates; 45/30/25 only if gates pass; Model Card on disk under `artifacts/model_cards/`.

Gates: `finite`, `conservation`, `residual_ceiling`, optional `boundary`. No conformal UQ hard gate in PoC.

---

## 13. Repository Layout

**Canonical root: `poc/` only.** Do not use `hydrogen/` paths.

```text
poc/
  configs/
  schema/
  generators/
  models/
  train/
  eval/
  validator/
  fixtures/
  tests/
  scripts/smoke.sh
```

---

## 14–18. Entry Points, Acceptance Tests, Build Sequence, Limits, Determinism

As v1.0: `run_once` CLI; T1–T7 acceptance; milestones A–E; validator limits YAML; CPU stricter for repro.

---

## 19. Mapping to Full Carbon (forward compatibility)

| PoC element | Full subnet successor |
|-------------|----------------------|
| `run_once` | Validator lean train worker |
| `local_nonce` | block hash / session seed hierarchy |
| `registry.jsonl` | verification registry |
| Fixtures | Miner MCP submissions |
| Single stress envelope | ProceduralStressGenerator families |
| Card JSON | Landscape Agent ingest (D1) |
| *(not in PoC)* | Product battery / Specialist Bank |

Do not implement successors inside `poc/` until T1–T7 pass.

---

## 20. Proof Statement (after green tests)

1. A **strategy** (not weights) is the submission unit.  
2. The system **retrains** under that strategy with a hard budget.  
3. Train/eval/stress data are **seed-derived** and role-separated.  
4. **Hard physics gates** can zero the combined score.  
5. Scoring uses **physics / robustness / accuracy** weights.  
6. Every completed run emits a **Model Card**.  
7. Results are **reproducible** under fixed seeds within documented tolerance.

That is Carbon’s **lean** atomic loop for one PDE and one backbone.

---

## 21. Thesis

Build **Burgers-1D + FNO-1D** as a vertical slice of validator-controlled, trustless, gated training. Keep surface area small enough to finish; keep the protocol faithful so Phase-0 multi-challenge work is multiplication—not reinvention. Productization (gauntlet, dual egress) comes after the lean loop is green.

---

*Canonical build specification for the Carbon Phase-0 mechanism proof (v1.1). Lean path only; `poc/` namespace only.*
