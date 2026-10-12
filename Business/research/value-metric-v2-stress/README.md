# VALUE-METRIC-V2 public stress — RES-08

**DEVELOPMENT / NOT REGISTERED. Reviewer: Carbon Validator.** The unchanged owner draft is the review target. No parameter, gate, winner, payment, qualification or new question law is selected here.

Read [OWNER_SUMMARY](OWNER_SUMMARY.md), [REPORT](REPORT.md), [definition questions](VALIDATOR_QUESTIONS.md), [protocol](MEASUREMENT_PROTOCOL.md) and [sources](SOURCES.md). [results.json](results.json) contains all real-member primary scores/pointwise intervals, controls, rank intervals, parameter sensitivities and tau matrices. Finite-panel counts are MEASURED (low = base = high); the grids and bootstrap model are ASSUMPTION / HUMAN_INPUT, with intervals reported separately.

## Bounded offline replay

The adapter reuses unchanged hash-bound RES-07 function bodies. It does not import Carbon runtime or execute a submitted model. Following the Validator's request, the exact [RES-07 executable](../value-metric-audit/res07-analyze.py.txt) is now committed beside its report. Its original byte digest is unchanged; the source suffix preserves the historical asset rather than reformatting its bytes. A clean checkout supplies the source; the exact helper, contract, original rev-1 draft and authorized public inputs listed in SOURCES are still required. Missing or changed identities fail closed. See [both-study staging instructions](../value-metric-audit/REPLAY.md).

The analysis used CPython 3.12.14, NumPy 2.5.4 and SciPy 1.18.1. These are execution versions, not solver or model dependencies. Substitute the explicit paths below with the preserved, hash-identical public assets. No automatic download or external host access occurs. Store caches and sufficient statistics outside this publication directory; never add them to a PR.

```text
python -X utf8 Business/research/value-metric-v2-stress/analyze_public.py --res07-code Business/research/value-metric-audit/res07-analyze.py.txt --res07-results Business/research/value-metric-audit/results.json --res06-json tmp/res06-physics-consistency/measured.json --public-inputs codex-queue/inputs/ev4-public-proof --draft codex-queue/inputs/value-metric-v2/VALUE_METRIC_V2_DRAFT.md --cache tmp/res08-v2-stress/prefix-cache.json.gz --output tmp/res08-v2-stress/sufficient-statistics.json
python -X utf8 Business/research/value-metric-v2-stress/aggregate.py --input tmp/res08-v2-stress/sufficient-statistics.json --output tmp/res08-v2-stress/replayed-results.json
python -X utf8 -m unittest discover -s Business/research/value-metric-v2-stress -p test_analysis.py -v
```

The raw replay must preserve input/draft hashes, the original bundle manifest and duplicate exclusions. Aggregate replay is byte-deterministic. The tests exercise accounting and semantic counterexamples without public inputs. Native diagnostics are separate from exact-head canonical CI. Formatting uses pinned Black 26.5.1 / Ruff 0.16.3; Black's formatter API with the repository's Python 3.10 target was used locally because the formatter CLI stalled. No quality requirement is waived; CI checks the final files.

Helper/contract lookup uses adjacent historical copies when available, otherwise the canonical checkout paths, always with the pinned Git-blob checks. To use staged copies explicitly, add `--reference-helper <path>` and `--ev4-contract <path>`. This source-publication follow-up does not re-run or reinterpret results under the Validator's rev-2 rules; that is a separately queued study.

The owner input at the draft path has since been updated to rev 2. For a rev-1 raw replay, supply an archived copy matching the recorded SHA-256 `973594923121ad177bbbd764ee94bae1d5b59b50aebe6ed0d67667250b0ffa4c`. The adapter deliberately refuses the updated draft; do not bypass that check or substitute rev 2 into these historical results. The source asset and source-identity tests are independent of this external input-version requirement.

## Interpretation boundary

The draft cannot numerically score all offered questions until it defines non-feasible fallback handling. The all-offered tables are an explicit zero-rescue-credit bookkeeping proxy; safe-fallback-only and complete-reference-bank subsets are separate sensitivities. Unknown physical gain is not asserted to be zero. G-FEAS and reference bands remain unchanged; the raw member panel is not an eligibility receipt. The finite historical EV4 charge proxy is not current battery-v3 charge-time, physical safety, buyer price, reusable-model qualification or a VALUE-BAR-V1 pass.
