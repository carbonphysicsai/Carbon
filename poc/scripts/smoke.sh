#!/usr/bin/env bash
# Offline PoC smoke — no Bittensor validator required.
#
# Two layers:
#   PROTOCOL  — schema, seeds, gates, score, card (always)
#   TRAIN     — only claimed if backend=jax AND loss drops ≥5%
#
# numpy_fd runs are PROTOCOL_ONLY. They must never be treated as learning proof.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
export POC_FAST="${POC_FAST:-1}"

echo "=== Carbon PoC smoke (POC_FAST=$POC_FAST) ==="
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
  echo "WARNING: no jax → this smoke is PROTOCOL_ONLY (no train-quality claim)"
fi

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

echo ""
echo "--- pytest poc/tests ---"
python -m pytest poc/tests -q

echo ""
if [[ "$BACKEND" == "jax" ]]; then
  echo "=== SMOKE DONE (jax present — check train_quality_claim in JSON above) ==="
else
  echo "=== SMOKE DONE (PROTOCOL_ONLY — install jax for train-quality proof) ==="
fi
echo "Cards under: $ROOT/artifacts/model_cards/"
