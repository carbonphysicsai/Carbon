# C-EP2 study runbook

This runbook reruns the bounded DEVELOPMENT Variant-A observation and detached
counterfactual replay. It does not enable sharing or qualify an exam.

## Canonical repository environment

From the repository root after `./scripts/dev/bootstrap.sh`:

```bash
study_revision="$(git rev-parse HEAD)"
.venv/bin/python scripts/dev/run_c_ep2_study.py \
  --config .agent/preregistrations/C-EP2_measurement_study_v1.json \
  --output-dir /path/to/private-output \
  --public-output-dir /path/to/reviewed-public-output \
  --source-revision "${study_revision}"
```

`--output-dir` receives the private trace and all aggregate files.
`--public-output-dir` receives only the fixture-safe trace and aggregate files.
Never point the private output at a public repository or artifact store.

## Recorded noncanonical Mac invocation

The frozen evidence in `.agent/evidence/wave_c/c-ep2-study/` was collected on
the exact host recorded in `environment_manifest_v1.json`. The repository lock
is Linux/x86_64-only, so this Mac run used a standalone pinned Python 3.11 and
the repository's pinned pytest development dependency:

```bash
study_revision="bb009a2d8a3045fd29ea2c2c8c46aed2218c5c76"
env UV_CACHE_DIR=/private/tmp/c-ep2-uv-cache \
  UV_TOOL_DIR=/private/tmp/c-ep2-uv-tools \
  uvx --from uv==0.12.7 uv run --no-project --python 3.11 \
  --with pytest==9.1.1 python scripts/dev/run_c_ep2_study.py \
  --config .agent/preregistrations/C-EP2_measurement_study_v1.json \
  --output-dir ../c_ep2_private \
  --public-output-dir .agent/evidence/wave_c/c-ep2-study \
  --source-revision "${study_revision}"
```

The command is a DEVELOPMENT observation, not canonical acceptance.

## Focused verification

```bash
.venv/bin/python -m pytest -q \
  tests/cpu/test_c_ep2_measurement_study.py \
  tests/cpu/test_c_ep1_evaluation_packs.py \
  tests/cpu/test_c01_durable_execution.py
```

Run the repository's applicable canonical acceptance through
`./scripts/dev/canonical.sh --full` or PR CI. Keep the private trace outside the
commit. Check output digests before comparing runs; timing changes are expected,
but source/config/environment identities and reconciliation must remain explicit.
