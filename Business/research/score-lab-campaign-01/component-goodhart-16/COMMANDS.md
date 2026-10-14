# Actual command and source sequence

Both executions ran through `scripts/dev/canonical.sh` from native Linux clones,
with locked `dev science-jax` groups and `OPENBLAS_NUM_THREADS=1`,
`OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`. Immutable images, raw source/artifact
hashes and Bash user/system/wall measurements are in each run's receipts.
The trusted local candidate payload was copied into the isolated clone and
verified against PROSPECTIVE.json before evaluation; it is not committed.

The existing `campaign-gate` command ran first in each execution, using
`Business/research/value-metric-audit/results.json`,
`Business/research/value-metric-v2-stress/results.json` and
`scripts/dev/score_lab/campaign-gate-toy.json`, with `--questions 6 --cap 3`.
Both returned CONTROL_PASS. A nonzero command would stop the entire tranche.

Each result command was:

```bash
time (ulimit -t 160 -v 1048576;
      timeout 240 .venv/bin/python -m scripts.dev.score_lab campaign-goodhart \
        --config scripts/dev/score_lab/physics-error-example.json \
        --search scripts/dev/score_lab/goodhart-search-example.json \
        --candidates tmp/candidates.py \
        --components tmp/components16/SPEC_<index>.json \
        --out tmp/components16/RESULTS_<index>.json.gz)
```

The baseline omits `--components`. Specifications are the exact subsets in the
precommitted catalogue, not coefficients fitted to the results. The initial
source-9311 execution ran indices 00-15 in order, with a 3,100-second outer wall
cap. An EXIT trap retained status and completed artifacts on failure/cap.
It finished successfully; status COMPLETE means commands completed, not that
all candidates were scorable.

After canonical focused validation of source-fe2f33, only indices
**01, 05, 06, 07, 11, 12, 13, 15** reran, in that order, with the same commands,
specification bytes and per-command caps, a separate output directory and a
1,800-second outer wall cap. Both pre-repair and repair controls/status files
remain available. No valid non-cheap result was repeated or overwritten.

Canonical regression before the repair replay was:

```bash
.venv/bin/python -m pytest -q tests/cpu/test_score_lab*.py
.venv/bin/python -m black --check scripts/dev/score_lab/campaign_goodhart.py \
  scripts/dev/score_lab/candidates.py scripts/dev/score_lab/components.py \
  tests/cpu/test_score_lab_campaign_goodhart.py
.venv/bin/python -m ruff check scripts/dev/score_lab/campaign_goodhart.py \
  scripts/dev/score_lab/candidates.py scripts/dev/score_lab/components.py \
  tests/cpu/test_score_lab_campaign_goodhart.py
```

Results: 167 tests passed; Black and Ruff passed. Completed outputs were exported
from the validation container in a framed bundle and decoded/verified locally.
`MATRIX_INDEX.json` selects original files for the eight non-cheap settings and
repaired files for the eight cheap settings. `SUMMARY.csv` is a direct projection
of each selected file's status, losses, gap and captured calls. Null/uncaptured
values are not converted to zero. All comparison inputs and settings remain
synthetic development assumptions; no new scientific definition is introduced.
