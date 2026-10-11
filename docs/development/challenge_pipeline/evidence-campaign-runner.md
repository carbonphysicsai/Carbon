# EVIDENCE-CAMPAIGN-RUNNER-01 — development campaign

This is an orchestration contract and fixture dry run for battery v3, motor
10p/12s and f02. It does not authorize a reference solve, TRAIN run, server
rental, scientific qualification or LIVE use. The physical solvers and public
TRAIN generation remain Data Collection's code and authority.

## Prerequisites and registration gaps

The seven readiness items are **exactly** EVIDENCE-READINESS-CHECK-01
([#1039](https://github.com/carbonphysicsai/Carbon/pull/1039), head
`98a236bf6d891d4383b85ec0f511949a31a5fbf7` at ticket start). They are:
registered and reuse-checked panel; current solver image; applicable convergence,
conservation and code verification; kit coverage; physically disjoint registered
TRAIN; strongest cheap adapter; Challenge-supported equal-budget route. These are
distinct from Graphite readiness. The plan byte-pins one native
`carbon.onboarding.evidence-readiness.v1` JSON report per Challenge. Every item
must be `YES`; the summary is recomputed. Before a public development run, the
runner regenerates #1039's read-only report on the exact merged main and refuses
if any status changed. Its image observation is rechecked by that tool. A YES
observation is neither spend permission nor scientific qualification.

Real stage modules are **not registered in this PR**. Data Collection's
`EVIDENCE_ENTRYPOINTS.md` was available in the owner's checkout on 2026-10-11
and was updated during this work. It identifies Data Collection's registered
`scripts.dev.evidence_runs` commands: f02 in open #1077, battery and motor in
open #1078, the latter following #1050. Those commands bind specific
plans/manifests and image digests and can export TRAIN records. They are **not
yet on main** and their `check|solve|export-train` CLI does not produce the
campaign's `--context`/`--output` stage receipt or the #975/#1056 assembled
comparison panel. That is the precise remaining integration gap. Data
Collection owns the registered reference/TRAIN execution; the panel/arm
assembly contract must be registered before real dispatch. A script without
that registered bridge cannot be treated as a campaign adapter. No invented
solver adapter stands in for battery v3, motor 10p/12s or f02.

## One command and exact inputs

The command is:

```sh
python -m carbon.development_comparison.evidence_campaign \
  --plan /approved/campaign/plan.json \
  --plan-sha256 sha256:<exact-64-hex-byte-digest> \
  --workspace /approved/campaign/work \
  --execute \
  --approval /approved/campaign/owner-approval.json \
  --approval-sha256 sha256:<exact-64-hex-byte-digest>
```

`--sheet-only` produces the prospective single server sheet without dispatch;
it accepts incomplete readiness and unregistered stage modules for planning,
and lists each non-YES item and module registration gap. `--dry-run`
uses only `SYNTHETIC_FIXTURE` plans and the toy module. Public development
execution requires Linux, exact merged main, all seven live YES observations,
registered trusted modules and an exact plan/cap approval receipt. The current
tree intentionally refuses real execution because the Data Collection modules
are not registered. The approval receipt is an operator attestation to the
plan and cap, **not** cryptographic proof of human identity. The operator must
validate the actual owner's approval and provider quote outside this command.

The plan pins #1047's budget registration and VALUE-BAR-V1. Each Challenge has
complete `reference`, `train` and `assemble` shard sets; a pinned optional
`score` stage can collect a future verify-aware top-k score. The score output is
reported as `RECORDED_NOT_ADOPTED` and never mutates the value rule. The
assembler supplies #975's manifest and #1056's adaptive panel; both must bind
the same solved replay and source export. All four arms consume the same
half/base/double registered ledger. Only solver-verified design values count.
The value report contains each tier's result and retains
`INSUFFICIENT_EVIDENCE` where the public panel lacks required inputs.

Each stage's command is a pinned in-repository module, not plan-provided shell
text. The stage receives a closed context with byte-pinned inputs, same-family
prior artifacts and a fixed vCPU allotment. TRAIN cannot receive held-out
reference artifacts. Completion receipts pin every output and give CPU and peak
RAM costs. Failed reference stages remain infrastructure/reference failures,
never candidate failures. On resume, pins are checked before a task is skipped;
a failed attempt gets a new directory. The phase scheduler grants at most 48
vCPUs at once, with a per-stage wall bound and global in-run euro deadline.

## Server sheet for the owner's one-figure approval

The generated `owner-server-sheet.json` has one battery, motor and f02 row plus
the combined total. Each row shows planned CPU-hours, isolated wall-hours and
allocated euros. The total shows 48-vCPU scheduled wall-hours, node euros,
fixed euros, total estimate, exact hard cap and headroom. The node is billed
once; proportional CPU-hours allocation is accounting only. The sheet labels
unmeasured stage durations and server price `ASSUMPTION`; it never turns 48
advertised vCPUs into a measured speedup. An operator must supply an actual
CCX63 quote, boot/teardown/storage reserve, stage cost estimates and the owner
approved cap before a real plan exists. The in-run meter cannot bound charges
after an abrupt host failure; the paid host must have an independent provider
spend cap and shutdown procedure. Until Data Collection's registered stages and
cost estimates exist, **there is no defensible euro figure for the owner to
approve**. The fixture sheet demonstrates arithmetic, not a production quote.

## Reproduction and boundary

`tests/cpu/test_evidence_campaign.py` builds a sealed toy plan with all three
families. It tests the full dry run, value/evidence outputs, checkpoint resume,
readiness refusal, cross-role isolation, caps and tamper refusal. No hidden,
AX42, customer or real solver material enters these fixtures. The generated
evidence pack is marked synthetic and cannot qualify a Challenge. For a public
run, the owner separately decides whether the exact server estimate and
registered inputs justify spend; VALUE-BAR-V1's observed verdict belongs to
the evidence, not this orchestration ticket.
