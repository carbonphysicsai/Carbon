# C-EP1 implementation evidence

**Status:** implementation in progress
**Baseline:** `150ab9313c4cc7cd23e032aebd78bce829db7675`
**Branch:** `agent/c-ep1-development-evaluation-packs`
**Issue:** https://github.com/carbonphysicsai/Carbon/issues/142
**PR / accepted head / merge:** pending

## Artifact provenance

The supplied gauntlet ZIP exists and its SHA-256 matches
`088d3e1182cbd8974c14ba6614a470cdcf3d5f3e6335c1db085699789ec5ffcb`.
The separately supplied `outputs/GAUNTLET_REPORT.md` is byte-identical to both
report copies in the archive. The archive was listed before extraction. Its
report, source manifest, protocol, configuration, commands, model, operating
and publication scripts, tests, result summaries, dispositions and
counterexample traces were inspected before any script was considered.

The historical counts remain source claims: 12 policy checks, 26 gauntlet
tests, 277 existing-interface tests, 25 model rejections, and five blocked
claims. C-EP1 does not copy them into its acceptance counts and does not claim
to reproduce the gauntlet. The exact blocked attacks remain AT-09, AT-16,
AT-19, AT-22, and AT-30. The reported 72.5% finite publication overlap is a
deliberately finite synthetic proxy, not Carbon freshness evidence.

## What exists

Pending final acceptance, C-EP1 adds one private child pack per NET-3 candidate
job, an additive/checksum-pinned receipt-database migration, immutable
materialization and result associations, C-01-backed dispatch/result closure,
and pack-gated delivery of the existing A6 fixture card. Copies and repeated
reads converge on the same association. New pack rows are excluded from legacy
`AcceptedFixtureRecord` and reward consumers.

The miner-visible behavior remains: submit the immutable Strategy, retain the
receipt and candidate status, then read the permitted fixture card only after
the corresponding pack is closed. Pack/case-selection identities and private
evidence are not projected.

## Current validation

Mac-host noncanonical focused validation under the available Python 3.11.11
runtime currently reports:

```text
61 passed in 0.67s
```

Command:

```text
/Users/nickfitzpatrick/.pyenv/versions/3.11.11/bin/python -m pytest -q tests/cpu/test_c_ep1_evaluation_packs.py tests/cpu/test_c01_durable_execution.py tests/cpu/test_net3_candidates.py
```

The selected A4/A5/A6/A7/A8, NET-2/NET-3, C-01, and reward regression set
reports `1298 passed, 7 deselected in 21.58s`; the seven deselected cases need
the optional pinned Bittensor SDK, which is absent from this local Python 3.11
environment. The same runtime passes the four packaging/binary64 cases that are
known to fail under unsupported Python 3.13. Pinned Black 26.5.1 and Ruff
0.16.3 pass the changed Python paths. Canonical acceptance, Hub checks, CI, and
Merge gate remain pending.

## Worked trace classes

- Success: assignment, attempt binding, C-01 dispatch/result, pack result seal,
  C-01-confirmed closure, one summary delivery.
- Duplicate: another hotkey commits the same Strategy; NET-3 returns the same
  candidate and the ledger records one pack/attempt/result/delivery.
- Crash/recovery: a crash after result sealing leaves `RESULT_RECORDED`; replay
  checks C-01 and closes without redispatch. A crash after closure leaves
  `CLOSED`; replay performs one idempotent delivery.
- Rejection: wrong pack binding, mutated materialization, premature closure,
  late mutation and forged schema/authority state fail before a new result.

## Remaining barriers and Variant B

Privileged-host integrity, independent execution audit, production entropy and
event/finality, protected custody, real references, C-EA2, rights, lineage,
freshness and cross-pack comparability remain unavailable. A4 fixture identities
demonstrate context separation, not independent physical draws. The current A8
interface does not expose qualified per-phase timing/evidence, so phase-level
reference/prediction accounting is not invented.

Variant B is not ready to implement. After C-EP1 acceptance it may be ready for
a separately selected measurement-design task only if that task first defines
actual A8 phase observations, common-comparison semantics, matched resource
accounting, and admission/load inputs without enabling sharing in production.

The repeatable fixture demo is
`scripts/dev/evaluation_pack_fixture_demo.py`; its retained first Mac-host sample
is `docs/development/evaluation_pack_baseline_v1.json`. On one arm64 Darwin host
with eight logical CPUs, 8 GiB memory, Python 3.13.0, no GPU use and concurrency
one, the two fixture jobs measured 7.629 ms cold and 7.685 ms warm; an idempotent
read measured 0.502 ms. These are noncanonical fixture timings, not solver
capacity or exams/day. Per-operation SQLite timings are retained separately in
the manifest.

## Hub Impact

Primary map_ref: `WAVE-C/C-EP1`. Selection, placement, boundary, dependency and
maturity state are map-structural, so Hub source and generated projections must
be updated before closeout. No production activation is claimed.
