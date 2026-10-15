# SCORELAB-REFERENCE-SENTINEL-CLI

Status: implementation in progress; no execution or qualification claimed.
Authority: explicit bounded Test Lead assignment, current queue owner amendment,
CONSTITUTION.md and expanded invariants. OPERATOR permits remote CI only.
Starting base: edefd8eb9e56b1e884bd82ae7b4434ce18177b4e.
Numerical source base: bc465b1d1807eb4b0cdeb299ceb7d70da784e52b.

## Working contract and decision

KEEP the existing solve and study behavior; WRAP solve in one closed run-probe
subcommand. Optimizer and Research confirmed the frozen nine-probe contract.
Do not add a solver framework, numerical setting, retry or adequacy judgment.

`python -m scripts.dev.battery.plating_convergence run-probe --jobs PATH
--probe-index N --out NEW_FILE` selects zero-based N in 0..8. Accept only the
frozen sentinel manifest with SHA256
`2dd3884d1b9428997ef080415265182f5dd1d8723ddc8088069b53ad1107aa7f`.
Reject any changed bytes, extra fields, other method/case/scope or unsupported
index before solve. Pass the selected case and job unchanged; job.case is
catalogue metadata (100/77/9), never the probe index. Create the output
exclusively before the one solve call, so an existing output cannot cause
duplicate work. Preserve raw result identity and typed solver failure. Add
probe/manifest provenance; downstream execution receipts bind image/overlay
and exact adapter head. No caller numerical overrides or external retries.
Lifecycle success never asserts scientific adequacy.

Decision: pin the complete manifest bytes instead of accepting arbitrary
descriptors plus caller-supplied hashes. This closes method and scope tampering
with one reviewed immutable authority. A future panel requires a prospective
source change and independent review, not a runtime override. Reversible within
this module and its tests; no human-reserved scientific value is selected.

## Plan, scope and conditional completion

1. Add the closed adapter and argparse route without changing solve or run.
2. Add public frozen fixture and solver-free positive/negative contract tests.
3. Submit one non-draft PR to main, remote canonical CI and complete-diff review;
   deliver exact source head/CLI to Research, Optimizer, Data Collector and Root.

Expected manifest: this ticket, scripts/dev/battery/plating_convergence.py,
tests/cpu/test_plating_sentinel_cli.py and
tests/fixtures/battery/REFERENCE_SENTINELS_RESEARCH_V1.json.
Required validation: canonical CPU tests for plating convergence and sentinel
CLI; repository lint/static/delivery checks and exact-head Merge gate remotely.
No local baseline/tests/solver under OPERATOR; remote results remain pending.
Negative controls cover all nine exact solve calls, tampered bytes/descriptors,
invalid indices, output collision, typed failure and nonfinite raw results.

Invariants: research/public scope only, pinned numerical identity, failure of
reference never candidate failure, no mock-to-LIVE promotion or score change.
Maturity ceiling: implemented and engineering-tested only after actual CI.
No numerical/reference/security/production qualification or execution granted.
Primary map_ref: SYSTEM/DEVELOPMENT-HUB; current OWNER-DX-03 explicitly suspends
Hub work and receipt ceremony; existing scientific boundaries remain binding.
Root owns review/merge, actual provider/host execution and TEST transition.

## Prospective extension: frozen one-command pilot

Root explicitly authorized this same-PR extension after Data Collector identified
the existing one-module/one-provider-create constraint. Research and Data
Collector agreed the existing frozen order: two new triples first, then nine
serial probes. `run-pilot --cases PATH --jobs PATH --out NEW_DIR` pins both
complete input byte strings before any solve and reserves a new owner-only
output directory. Workers and mid-workers are fixed at four. The pilot cases
manifest SHA256 is
`90441fae89461a1efdbe141fdb415eb37d83a58493857ba61f8b4541ad3998e1`.

Snapshot inputs inside the new output root before calling existing run once;
this prevents a caller-path change between validation and run's second read.
Run only the cold and warm registered 40/80/160 triples (six nominal rungs);
require six compatible finite OK terminal records before any sentinel. Then
call existing run_probe for indices 0..8 serially and stop on first non-OK or
invalid result. Retain the existing single-probe interface unchanged. Output:
study/records.jsonl, study/summary.json, sentinels/probe-N.jsonl, input snapshots
and pilot.json lifecycle receipt. No adequacy flag or remaining batch dispatch.

Exactly 15 nominal solves; maximum 21 attempts only through existing documented
fallback on the six triple rungs. Sentinel calls have zero retries. Root's
external executor owns actual CPU/wall/cost enforcement; four workers and a
90-minute wall cap alone do not enforce the three CPU-hour research ceiling.
The saved third sentinel baseline is reused downstream, never recomputed here.
Add the frozen public pilot-cases fixture to the expected manifest and cover
pre-solve validation, fixed worker binding/order, complete/missing/failed/
nonfinite triples, exclusive output, snapshots and sentinel early stop.
This is reversible orchestration within the same module; science is unchanged.
