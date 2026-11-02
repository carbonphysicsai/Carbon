#!/usr/bin/env bash
# CHECKS BATCH: one custody launch per version: checks (1)-(3) + the G1-G9 reports (checks_batch.py).
#   checks_batch.sh run VERSION_DIR OUT     VERSION_DIR holds config.json, report-inputs.json and optionally g-inputs.json
#   checks_batch.sh dry VERSION_DIR         every input checked, nothing graded
#   checks_batch.sh selftest OUT            the chain on fake data of the real shapes
# Threads are pinned (BLAS thread count changes scores); run from the repo checkout at the receipted head.
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
export PYTHONPATH="$repo${PYTHONPATH:+:$PYTHONPATH}"
py="${PYTHON:-python3}"
cmd="${1:?usage: checks_batch.sh run|dry|selftest ...}"
case "$cmd" in
  run|dry)
    dir="${2:?VERSION_DIR required}"
    g=()
    if [ -f "$dir/g-inputs.json" ]; then g=(--g-inputs "$dir/g-inputs.json"); fi
    args=(--config "$dir/config.json" --inputs "$dir/report-inputs.json" "${g[@]}")
    if [ "$cmd" = run ]; then args+=(--out "${3:?OUT required}"); fi
    exec "$py" "$here/checks_batch.py" "$cmd" "${args[@]}"
    ;;
  selftest)
    exec "$py" "$here/checks_batch.py" selftest --out "${2:?OUT required}"
    ;;
  *)
    echo "usage: checks_batch.sh run|dry|selftest ..." >&2
    exit 2
    ;;
esac
