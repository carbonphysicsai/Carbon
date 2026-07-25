#!/usr/bin/env bash
# Offline PoC smoke — no Bittensor validator required.
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

echo ""
echo "--- Fixture: strategy_physics.json ---"
python -m poc.validator.run_once poc/fixtures/strategy_physics.json \
  --local-nonce 42 --run-id smoke_phys --fast

echo ""
echo "--- Fixture: strategy_data_only.json ---"
python -m poc.validator.run_once poc/fixtures/strategy_data_only.json \
  --local-nonce 42 --run-id smoke_data --fast

echo ""
echo "--- Fixture: strategy_broken.json (expect gate_failed / combined=0) ---"
python -m poc.validator.run_once poc/fixtures/strategy_broken.json \
  --local-nonce 42 --run-id smoke_broken --fast

echo ""
echo "--- pytest poc/tests (T1–T7) ---"
python -m pytest poc/tests -q

echo ""
echo "=== SMOKE OK ==="
echo "Cards under: $ROOT/artifacts/model_cards/"
