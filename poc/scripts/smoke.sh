#!/usr/bin/env bash
# Offline PoC smoke — no Bittensor validator required.
#
# Layers:
#   PROTOCOL  — schema, seeds, gates, score, card
#   ORACLE    — generator vs refined integrator
#   TRAIN     — claim only if jax + loss + L2 + beats null
#   GOLD      — optional longer budget (POC_GOLD=1)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
export POC_FAST="${POC_FAST:-1}"
export POC_GOLD="${POC_GOLD:-0}"

echo "=== Carbon PoC smoke (POC_FAST=$POC_FAST POC_GOLD=$POC_GOLD) ==="
echo "ROOT=$ROOT"

if ! python -c "import numpy, yaml" 2>/dev/null; then
  echo "Missing deps. Run: pip install -r poc/requirements.txt"
  exit 1
fi

BACKEND="numpy_fd"
if python -c "import jax" 2>/dev/null; then
  BACKEND="jax"
fi
echo "Train backend available: $BACKEND"
if [[ "$BACKEND" == "numpy_fd" ]]; then
  echo "WARNING: no jax → PROTOCOL_ONLY (no train-quality claim)"
fi

echo ""
echo "--- ORACLE: generator quality cross-check ---"
python - <<'PY'
from poc.eval.oracle_check import cross_check_generator
import json, sys
r = cross_check_generator(n_samples=6, seed_nonce=0, fast=True)
print(json.dumps({k: r[k] for k in ("passed", "mean_rel", "max_rel", "tau")}, indent=2))
if not r["passed"]:
    print("ORACLE FAIL", file=sys.stderr)
    sys.exit(1)
PY

echo ""
echo "--- PROTOCOL: strategy_broken.json (expect gate zero) ---"
python -m poc.validator.run_once poc/fixtures/strategy_broken.json \
  --local-nonce 42 --run-id smoke_broken --fast

echo ""
echo "--- PROTOCOL + TRAIN attempt: strategy_data_only.json ---"
python -m poc.validator.run_once poc/fixtures/strategy_data_only.json \
  --local-nonce 42 --run-id smoke_data --fast

echo ""
echo "--- PROTOCOL + TRAIN attempt: strategy_physics.json ---"
python -m poc.validator.run_once poc/fixtures/strategy_physics.json \
  --local-nonce 42 --run-id smoke_phys --fast

if [[ "$POC_GOLD" == "1" ]]; then
  echo ""
  echo "--- GOLD budget: strategy_gold.json (no --fast; longer train) ---"
  POC_FAST=0 python -m poc.validator.run_once poc/fixtures/strategy_gold.json \
    --local-nonce 42 --run-id smoke_gold
fi

echo ""
echo "--- pytest poc/tests ---"
python -m pytest poc/tests -q

echo ""
if [[ "$BACKEND" == "jax" ]]; then
  echo "=== SMOKE DONE (jax present — inspect train_quality_claim / reasons) ==="
else
  echo "=== SMOKE DONE (PROTOCOL_ONLY — install jax for train-quality proof) ==="
fi
echo "Cards: $ROOT/artifacts/model_cards/"
echo "Gold run: POC_GOLD=1 bash poc/scripts/smoke.sh"
