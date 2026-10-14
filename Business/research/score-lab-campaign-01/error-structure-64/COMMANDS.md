# Actual error-structure tranche commands

Source/contract: `69e39b42e5ee06e84d7fa3058fca2e2f530418ec`. The command sequence
ran through `scripts/dev/canonical.sh` from a native Linux clone, with
`CARBON_UV_GROUPS=science-jax`, one numerical-library thread and the candidate
file copied read-only from its trusted local source. Its exact payload SHA256
is in `IDENTITY.json`; this file does not supply or reconstruct that source.

Inside the canonical validation checkout, each `run_cli` invoked the existing
CLI in a subshell with `ulimit -t 800 -v 1048576` and `timeout 900`. Bash's
`TIMEFORMAT` recorded each command's user/system/wall seconds. The outer wrapper
had a 3,600-second wall cap. These are execution caps, not scientific values.

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
mkdir -p tmp/error64
run_cli() {
  local label="$1"
  shift
  TIMEFORMAT="RESOURCE ${label} user=%U system=%S wall=%R"
  time (ulimit -t 800 -v 1048576;
        timeout 900 .venv/bin/python -m scripts.dev.score_lab "$@")
}
run_cli controls campaign-gate \
  --audit Business/research/value-metric-audit/results.json \
  --stress Business/research/value-metric-v2-stress/results.json \
  --toy-problem scripts/dev/score_lab/campaign-gate-toy.json \
  --questions 6 --cap 3 --out tmp/error64/CONTROL_GATE.json
for shard in 0 1 2 3; do
  run_cli "plan${shard}" campaign-plan \
    --base-config scripts/dev/score_lab/physics-error-example.json \
    --axes scripts/dev/score_lab/campaign-axes-error-example.json \
    --count 64 --seed 20261014 --shard "${shard}" --shards 4 \
    --out "tmp/error64/PLAN_${shard}.json.gz"
  run_cli "run${shard}" campaign-run \
    --plan "tmp/error64/PLAN_${shard}.json.gz" \
    --candidates tmp/candidates.py --out "tmp/error64/RESULTS_${shard}.json.gz"
done
run_cli atlas campaign-atlas \
  --result tmp/error64/RESULTS_0.json.gz --result tmp/error64/RESULTS_1.json.gz \
  --result tmp/error64/RESULTS_2.json.gz --result tmp/error64/RESULTS_3.json.gz \
  --out tmp/error64/ATLAS.json.gz
```

The controls command returned `CONTROL_PASS`; every command exited successfully.
Its failure would have stopped the `set -euo pipefail` driver before evaluation.
The driver exported completed files from the isolated validation container via
a framed base64 bundle, decoded locally and checked against `IDENTITY.json`.
No hidden data or host material was present in the clone.

`SUMMARY.csv` is a column projection of `candidate_switch_summaries` in the
existing atlas. `PAIRED_SWITCH_SUMMARY.json` groups raw rows by profile/candidate,
subtracts OFF neighbour-blend tau from each switched tau, retains null pairs,
counts positive/exact-equal/negative deltas and computes the median of defined
deltas. It sums the existing `good_wrongly_excluded` event field; it does not
recompute scores, reinterpret gates or supply a new value definition.
