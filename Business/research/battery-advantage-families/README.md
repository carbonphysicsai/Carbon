# RES-10 battery advantage families

DEVELOPMENT research only. Read [OWNER_SUMMARY](OWNER_SUMMARY.md),
[REPORT](REPORT.md), [reference budgets](REFERENCE_BUDGETS.md),
[working contract](WORKING_CONTRACT.md) and [source pins](source-pin.json).
The shortlist is a research priority order; Carbon Validator and the owner
retain bank authoring and adoption. No production value is selected.

## Clean aggregate replay

`measurements.json` contains public scalar sufficient statistics from the
authorized EV4 arrays: per-actor verified gain, complete-condition token and
unsafe-count arrays for the declared question variants; coverage; actor labels;
and public timing summaries. It has no traces, weights, protected samples or
hidden seeds. Unpriced gain entries are bookkeeping zeros and never enter a
buyer-gain mean; explicit coverage masks preserve that distinction.

```text
python -X utf8 Business/research/battery-advantage-families/analyze.py --measurements Business/research/battery-advantage-families/measurements.json --output tmp/res10-replayed-results.json
python -X utf8 -m unittest discover -s Business/research/battery-advantage-families -p test_analysis.py -v
```

Aggregate replay must match `results.json` byte-for-byte. Every one of the
840 profiles retains aggregate counts/means and empty-bank gaps. Per-member
scores/paired intervals are published at k=3, κ=0.1 to keep the review small;
all other scores can be reconstructed from the measured arrays. The display
anchor, cost/cap/β grids, masks and public tuning history are explicit.

Measured native environment: CPython 3.12.14, NumPy 2.5.4, SciPy 1.18.1.
Pinned local quality checks: Black 26.5.1 (formatter API, Python 3.10 target)
and Ruff 0.16.3. Native diagnostics do not replace canonical CI acceptance.
Dependencies are analysis libraries, not solver dependencies. No automatic
download, solver, model execution or training occurs.

## Optional raw-public-input replay

Use only the owner's explicitly public EV4 copy, historical helper/contract,
original RES-06 public metadata and the unchanged rev-2 draft, with the
inherited RES-07/08/09 identity guards. Cache orders are used only for inventory
and metadata; the new family selections are computed from the public arrays.
Raw inputs/caches stay uncommitted and outputs go to a writable temporary folder.

```text
python -X utf8 Business/research/battery-advantage-families/analyze.py --res07-code Business/research/value-metric-audit/res07-analyze.py.txt --reference-helper <pinned-historical-decision.py> --ev4-contract <pinned-ev4-contract.json> --res07-results Business/research/value-metric-audit/results.json --res06-json <original-public-res06-metadata.json> --public-inputs <public-ev4-input-directory> --draft <rev2-draft.md> --cache tmp/res10-cohort-cache.json.gz --output tmp/res10-raw-replay/results.json
```

Create the output parent beforehand. A nonexistent cache rebuilds the old
public cohort; a retained matching RES-08 cache also works. The new wrapper
never executes the original script's top-level experiments or changes its bytes.
Reference assessment and verification remain the original helper functions.
The trace-map AST adapter changes prediction interpolation representation only,
retaining original D node weights; reference truth and bands are not modified.

Budget-envelope policy selection is retrospective and answer-informed. It
cannot substitute for onboarding selection before a fresh fold. The four fixed
solver-alone controls do not implement adaptive industrial design search.
Statistical independence, active G-FEAS eligibility, buyer preferences,
whole-workflow costs and new-v3 scientific adequacy remain gaps. No new bank,
LIVE state, scoring law, launch claim or commercial qualification is created.
