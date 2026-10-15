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
