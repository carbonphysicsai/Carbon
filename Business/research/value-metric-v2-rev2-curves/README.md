# Rev-2 owner-choice curves — RES-09

DEVELOPMENT research. Start with [OWNER_SUMMARY](OWNER_SUMMARY.md),
[REPORT](REPORT.md), [working contract](WORKING_CONTRACT.md),
[rev-1 archive](REV1_ARCHIVE.md) and [source pins](source-pin.json).
All production values stay HUMAN_INPUT.

The committed `public-measurements.json` is an explicit new replay asset:
measured scalar outcomes from the authorized public EV4 arrays, reference
status/objective/check summaries, and the original public bundle inventory.
It contains no model weights, prediction traces, sealed cases or hidden seeds.
It makes the aggregate curves reproducible without the operator's input folder.
It is versioned separately from RES-08's uncommitted intermediates.

## Aggregate and chart replay

Use NumPy and SciPy; plotting also requires Matplotlib. Measured native
environment: CPython 3.12.14, NumPy 2.5.4, SciPy 1.18.1, Matplotlib 3.11.2.
These are recorded analysis dependencies, not solver pins or canonical-host
claims. No install, download, solver or model execution is performed by the
analysis. From the repository root:

```text
python -X utf8 Business/research/value-metric-v2-rev2-curves/analyze.py --measurements Business/research/value-metric-v2-rev2-curves/public-measurements.json --output tmp/res09-replay-results.json
python -X utf8 Business/research/value-metric-v2-rev2-curves/plot_curves.py --results tmp/res09-replay-results.json --output tmp/res09-replay-charts --preview tmp/res09-preview.png
python -X utf8 -m unittest discover -s Business/research/value-metric-v2-rev2-curves -p test_analysis.py -v
```

Aggregate replay must match `results.json` byte-for-byte. Source pins bind
the inherited RES-08 helper files and measurement asset. The local bootstrap
reuses its exact random weights; it is not fresh independent evidence.
The test suite includes synthetic fixtures that cannot enter production.
These native diagnostics supplement canonical CI, never replace it.

## Optional raw-public-input replay

Supply only the owner's explicitly public EV4 development copy and historical
source assets, whose hashes/Git blobs are pinned in the inherited adapter.
Use the new draft matching source-pin, never substitute rev 1. Example:

```text
python -X utf8 Business/research/value-metric-v2-rev2-curves/analyze.py --res07-code Business/research/value-metric-audit/res07-analyze.py.txt --reference-helper <pinned-historical-decision.py> --ev4-contract <pinned-ev4-contract.json> --res07-results Business/research/value-metric-audit/results.json --res06-json <original-public-res06-metadata.json> --public-inputs <public-ev4-input-directory> --draft <rev2-draft.md> --cache tmp/res09-old-cohort-cache.json.gz --output tmp/res09-raw-replay/results.json
```

Use the original RES-08 cache if retained, or a nonexistent cache path to
rebuild its public cohort metadata. Cached proposal orders are never used
for rev-2 selection. The output folder must exist. The raw replay writes
scalar summaries alongside its result; raw arrays remain outside the PR.
Both predicted-fallback and known-reference-fallback selector interpretations
are measured. A missing or changed source identity fails closed.

The historical source is loaded only as selected, digest-bound functions;
top-level RES-07 experiments/writes are not executed. The separate rev-2
adapter records the precise AST reuse in REPORT. It never imports Carbon's
runtime, a reconstruction worker or a solver.

## Checks and delivery boundary

Pinned local formatting: Black 26.5.1 formatter API, Python 3.10 target,
and Ruff 0.16.3. Compare formatter output for equality after formatting.
Run delivery hygiene and the explicit owned-path text scan; canonical CI
validates the actual PR tree. Keep owner queue, inputs, temporary caches and
previews uncommitted. Only this directory belongs to this ticket. PR Head
owns merge; the Carbon Validator reviews the proposed definitions. This work
cannot earn scientific, commercial, security, network or production qualification.
