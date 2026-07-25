# Carbon PoC — Burgers-1D × FNO-1D

Smallest end-to-end proof of Carbon’s atomic loop:

```text
strategy.json → schema check → seeded train/eval/stress data
  → retrain (FNO-1d) → metrics → hard physics gates
  → 45/30/25 score → Model Card
```

Full design: [`appendices/POC_Burgers_FNO.md`](../appendices/POC_Burgers_FNO.md).

## Install

```bash
pip install -r poc/requirements.txt
# from repo root so `poc` and `carbon` import
export PYTHONPATH=.
```

## Run

```bash
# Full loop (fast CI profile)
POC_FAST=1 python -m poc.validator.run_once poc/fixtures/strategy_physics.json \
  --local-nonce 42 --run-id poc_repro_1 --fast

# Data-only fixture
POC_FAST=1 python -m poc.validator.run_once poc/fixtures/strategy_data_only.json --fast

# Broken path (expect low score / gate pressure)
POC_FAST=1 python -m poc.validator.run_once poc/fixtures/strategy_broken.json --fast
```

Cards land in `artifacts/model_cards/<card_id>.json` and `artifacts/model_cards/registry.jsonl`.

Exit codes: `0` completed · `2` schema reject · `3` internal error.

## Tests (T1–T7)

```bash
POC_FAST=1 PYTHONPATH=. pytest poc/tests -q
```

| ID | Test |
|----|------|
| T1 | Schema reject (wrong backbone / unknown key) |
| T2 | Seed separation + fixed-seed label determinism |
| T3 | Full loop writes Model Card |
| T4 | Broken strategy still emits card |
| T5 | Reproducibility under fixed seeds |
| T6 | Strategy discrimination (hash / card) |
| T7 | Budget cap enforced |

## Layout

```text
poc/
  configs/          challenge, gates, validator limits
  schema/           strategy_poc_v1.json
  generators/       Burgers-1D + reference solver
  models/           FNO-1d
  train/            losses + budget-capped loop
  eval/             metrics, gates, score
  validator/        schema_check + run_once
  fixtures/         data_only / physics / broken
  tests/            T1–T7
```

## Proof claims (when tests green)

1. Submission unit is a **strategy**, not weights.  
2. System **retrains** under a hard budget.  
3. Train/eval/stress data are **seed-derived** and role-separated.  
4. **Hard gates** can zero the combined score.  
5. Scoring uses **45/30/25**.  
6. Every run emits a **Model Card**.  
7. Fixed seeds are **reproducible** within documented tolerance.
