# RES-12: public EV4 plating-onset sensitivity

Read [OWNER_SUMMARY.md](OWNER_SUMMARY.md), [REPORT.md](REPORT.md), then the
[machine-readable results](results.json). The [working contract](WORKING_CONTRACT.md)
defines scope and the two censoring interpretations. This is DEVELOPMENT
research, never a scoring registration or a relabeling of historical evidence.

All finite-panel quantities are MEASURED with low=base=high. The inclusive
2 mV sensitivity and five bins are OWNER_REQUESTED diagnostics, also fixed
low=base=high. Population uncertainty, error calibration, new gates and
physical validity remain HUMAN_INPUT. No confidence interval is inferred
from repeated model picks of the same physical case.

## Source identities and reuse

| Public source | Required identity | Use |
| --- | --- | --- |
| [Original EV4 results](https://github.com/carbonphysicsai/Carbon/blob/1238dd3471f73d3fc0df375de1d63c4663e380b3/docs/development/evidence/ev4-2026-10-01/results.json) | Git blob `67ca13b966a2f6fb4b2e68b084e2909657e7ba7f` | Frozen original selections, rule scores and eligibility |
| [EV4 contract](https://github.com/carbonphysicsai/Carbon/blob/1238dd3471f73d3fc0df375de1d63c4663e380b3/carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json) | Git blob `3961b89a98c8877190bc010579852497057d3518` | Original constraints, 35 actions, bands and mistake costs |
| [Isolated decision helper](https://github.com/carbonphysicsai/Carbon/blob/1238dd3471f73d3fc0df375de1d63c4663e380b3/carbon/battery/value/decision.py) | Git blob `b1d899d116317bd190ad6812f0aae5d3e8a16c0c` | Unchanged measurement, reference assessment and outcome functions |
| [Retained RES-07 source](../value-metric-audit/res07-analyze.py.txt) | SHA-256 `e91f89f9cae53cd7b5e1f252910f197f8a0334adbf47e2bb492d7601dffa91ff` | Unchanged candidates, read_refs, qdef and ref_assessment functions; AST selects definitions only, skips top-level campaign |
| [Committed RES-07 results](../value-metric-audit/results.json) | SHA-256 `a1473c98baaf2352c02db38b1aeef3938c41b2a958fd1f568cff0c5e29e975b0` | CPU member summaries and public prediction bundle manifest |
| Owner-authorized read-only public EV4 references | SHA-256 `72ea300b42fe1ca4e54b9c6131cb126ca7217ebddd5f1dddca8044a7bcef2dbf` | Original standard references, 840 registered D/V case keys only |
| Retained RES-07 derived-public-outcomes.json | SHA-256 `7452a1a0ac65bfb0638743bebac2a36655dbb61d996988630d99763245e76660` | Frozen CPU selections, bound to all 148 raw public bundle hashes and checked against committed summaries |

Original PR ancestry, current main and measurement identities are in
[source-pin.json](source-pin.json). Git identities normalize native CRLF to LF;
SHA-256 identities require exact bytes. The retained CPU outcome file is an
intermediate from the prior authorized public analysis; it remains outside
the PR, as do predictions, reference arrays and queue inputs. To regenerate
it, follow [RES-07's staging/replay contract](../value-metric-audit/REPLAY.md).
Do not run the old source in its publication directory. A differing cache
digest stops this analysis; it is not silently accepted as a new cohort.

This reuses the original outcome logic behind RES-07/08 rather than rewriting
the decision law. RES-08's V2 utility and rev-1 draft are not needed: the
question concerns old SELECTED_INFEASIBLE events and frozen-pick loss.
EV5, refined overlays, beyond-envelope probes, current runtime scores and
sealed evidence are outside the estimand.

## Replay

Environment used: CPython 3.12.14, NumPy 2.5.4, SciPy 1.18.1;
Black 26.5.1 and Ruff 0.16.3. Existing research dependencies only.
Stage the exact public files above in a task-specific temporary directory;
never substitute protected material or run a solver/model to fill a gap.
Use repository root as the working directory:

```text
python -X utf8 Business/research/plating-onset-sensitivity/analyze.py --res07-source Business/research/value-metric-audit/res07-analyze.py.txt --public-inputs codex-queue/inputs/ev4-public-proof --ev4-results tmp/res02-public-inputs/ev4.json --helper tmp/res07-value-metric-audit/decision.py --contract tmp/res07-value-metric-audit/ev4-contract.json --cpu-outcomes tmp/res07-value-metric-audit/derived-public-outcomes.json --res07-results Business/research/value-metric-audit/results.json --output tmp/res12-plating/replay.json
python -X utf8 Business/research/plating-onset-sensitivity/test_analysis.py
ruff check Business/research/plating-onset-sensitivity
```

Compare the replay bytes with results.json. Windows diagnostics are not
canonical acceptance; pinned GitHub CI supplies it. All outputs remain
reference-relative and retrospective. No thresholds, historical files,
runtime scoring, Challenge population, P/Q/w, qualifications or economics
are changed. The Development Hub remains frozen.
