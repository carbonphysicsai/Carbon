# VALUE-METRIC-V2 public stress — RES-08

**DEVELOPMENT / NOT REGISTERED. Reviewer: Carbon Validator.** The unchanged owner draft is the review target. No parameter, gate, winner, payment, qualification or new question law is selected here.

Read [OWNER_SUMMARY](OWNER_SUMMARY.md), [REPORT](REPORT.md), [definition questions](VALIDATOR_QUESTIONS.md), [protocol](MEASUREMENT_PROTOCOL.md) and [sources](SOURCES.md). [results.json](results.json) contains all real-member primary scores/pointwise intervals, controls, rank intervals, parameter sensitivities and tau matrices. Finite-panel counts are MEASURED (low = base = high); the grids and bootstrap model are ASSUMPTION / HUMAN_INPUT, with intervals reported separately.

## Bounded offline replay

The adapter reuses unchanged hash-bound RES-07 function bodies. It does not import Carbon runtime or execute a submitted model. The original RES-07 executable was retained locally rather than committed with its reports. A fresh checkout alone therefore cannot reproduce the raw replay: the exact source, helper, contract, draft and authorized public input copy listed in SOURCES are required. Missing or changed identities fail closed. This is a reproducibility gap for the Validator to resolve, not permission to substitute another version.

The analysis used CPython 3.12.14, NumPy 2.5.4 and SciPy 1.18.1. These are execution versions, not solver or model dependencies. Substitute the explicit paths below with the preserved, hash-identical public assets. No automatic download or external host access occurs. Store caches and sufficient statistics outside this publication directory; never add them to a PR.

```text
python -X utf8 Business/research/value-metric-v2-stress/analyze_public.py --res07-code tmp/res07-value-metric-audit/analyze.py --res07-results Business/research/value-metric-audit/results.json --res06-json tmp/res06-physics-consistency/measured.json --public-inputs codex-queue/inputs/ev4-public-proof --draft codex-queue/inputs/value-metric-v2/VALUE_METRIC_V2_DRAFT.md --cache tmp/res08-v2-stress/prefix-cache.json.gz --output tmp/res08-v2-stress/sufficient-statistics.json
python -X utf8 Business/research/value-metric-v2-stress/aggregate.py --input tmp/res08-v2-stress/sufficient-statistics.json --output tmp/res08-v2-stress/replayed-results.json
python -X utf8 -m unittest discover -s Business/research/value-metric-v2-stress -p test_analysis.py -v
```

The raw replay must preserve input/draft hashes, the original bundle manifest and duplicate exclusions. Aggregate replay is byte-deterministic. The tests exercise accounting and semantic counterexamples without public inputs. Native diagnostics are separate from exact-head canonical CI. Formatting uses pinned Black 26.5.1 / Ruff 0.16.3; Black's formatter API with the repository's Python 3.10 target was used locally because the formatter CLI stalled. No quality requirement is waived; CI checks the final files.

## Interpretation boundary

The draft cannot numerically score all offered questions until it defines non-feasible fallback handling. The all-offered tables are an explicit zero-rescue-credit bookkeeping proxy; safe-fallback-only and complete-reference-bank subsets are separate sensitivities. Unknown physical gain is not asserted to be zero. G-FEAS and reference bands remain unchanged; the raw member panel is not an eligibility receipt. The finite historical EV4 charge proxy is not current battery-v3 charge-time, physical safety, buyer price, reusable-model qualification or a VALUE-BAR-V1 pass.
