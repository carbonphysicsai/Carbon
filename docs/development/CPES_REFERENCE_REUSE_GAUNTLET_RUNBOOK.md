# CPES reference-reuse gauntlet runbook

Run this only as detached DEVELOPMENT research. It writes a new output
directory containing synthetic traces and disposable-prototype summaries. It
does not invoke Carbon runtime evaluation or a network service.

## Original bundle verification and historical-model rerun

List and inspect the original archive before extracting or running its code:

```bash
shasum -a 256 /path/to/Carbon_CPES1_v0_2_Gauntlet_Evidence.zip
unzip -l /path/to/Carbon_CPES1_v0_2_Gauntlet_Evidence.zip
```

Expected SHA-256:

```text
088d3e1182cbd8974c14ba6614a470cdcf3d5f3e6335c1db085699789ec5ffcb
```

After safe extraction and source inspection:

```bash
python3 -m unittest -q test_gauntlet.py
python3 run_gauntlet.py --out reproduced_results
```

## Continuation harness

The output path must not exist:

```bash
python scripts/dev/cpes_reference_reuse_gauntlet.py \
  --config docs/development/cpes_reference_reuse_gauntlet_protocol_v2.json \
  --output-dir /fresh/private/cpes-reuse-evidence \
  --original-bundle /path/to/Carbon_CPES1_v0_2_Gauntlet_Evidence.zip
```

Run focused tests and quality checks:

```bash
python -m pytest -q tests/cpu/test_cpes_reference_reuse_gauntlet.py
python -m black --check \
  scripts/dev/cpes_reference_reuse_gauntlet.py \
  tests/cpu/test_cpes_reference_reuse_gauntlet.py
python -m ruff check \
  scripts/dev/cpes_reference_reuse_gauntlet.py \
  tests/cpu/test_cpes_reference_reuse_gauntlet.py
```

Every run uses temporary SQLite files that are destroyed after their JSON
transition traces are retained. Do not import the prototype into
`carbon/evaluation_packs`, use its synthetic digest as authority, or route its
outputs to candidate, score, reward, disclosure or launch owners.
