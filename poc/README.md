# Carbon PoC — Burgers-1D × FNO-1D

Smallest end-to-end proof of Carbon’s atomic loop — **fully offline** (no Bittensor validator):

```text
strategy.json → schema check → seeded train/eval/stress data
  → retrain (FNO-1d) → metrics → hard physics gates
  → 45/30/25 score → Model Card
```

Full design: [`appendices/POC_Burgers_FNO.md`](../appendices/POC_Burgers_FNO.md).

## Install

```bash
python -m pip install -e ".[dev,poc]"
export PYTHONPATH=.   # from repo root
```

### Train backends

| Backend | When | What’s trained |
|---------|------|----------------|
| **JAX** (preferred) | `jax` importable | Full FNO params via `jax.grad` |
| **NumPy FD** (fallback) | no `jax` | Lift/proj only via finite differences |

Card `budget_used.backend` reports `jax` or `numpy_fd`.

## One-command smoke (recommended)

```bash
POC_FAST=1 bash poc/scripts/smoke.sh
```

Runs all three fixtures + pytest T1–T7 under `POC_FAST=1`.

## Manual run

```bash
POC_FAST=1 python -m poc.validator.run_once poc/fixtures/strategy_physics.json \
  --local-nonce 42 --run-id poc_repro_1 --fast

POC_FAST=1 python -m poc.validator.run_once poc/fixtures/strategy_broken.json --fast
# expect: gate_failed=true, combined=0, failures includes loss_signal
```

Cards: `artifacts/model_cards/<card_id>.json` + `registry.jsonl`.

Exit codes: `0` completed · `2` schema reject · `3` internal error.

## Hard gates (offline zero path)

Any fail → `combined = 0`:

| Gate | Check |
|------|--------|
| `finite` | no NaN/Inf |
| `conservation` | mass proxy ≤ τ |
| `residual_ceiling` | Burgers residual diagnostic ≤ τ |
| `accuracy_ceiling` | eval rel-L2 ≤ τ |
| `loss_signal` | ≥1 loss term enabled in strategy |

Broken fixture (`strategy_broken.json`) disables all losses → `loss_signal` fails by construction.

## Tests (T1–T7)

```bash
POC_FAST=1 PYTHONPATH=. python -m pytest poc/tests -q
```

## Layout

```text
poc/
  configs/   challenge, gates, validator limits
  schema/    strategy_poc_v1.json
  generators/ models/ train/ eval/ validator/
  fixtures/  data_only | physics | broken
  tests/     T1–T7
  scripts/   smoke.sh
```

## Proof claims (when smoke green)

1. Submission unit is a **strategy**, not weights.  
2. System **retrains** under a hard budget.  
3. Train/eval/stress data are **seed-derived** and role-separated.  
4. **Hard gates** zero the combined score (verified offline).  
5. Scoring uses **45/30/25**.  
6. Every run emits a **Model Card**.  
7. Fixed seeds are **reproducible** within tolerance.
