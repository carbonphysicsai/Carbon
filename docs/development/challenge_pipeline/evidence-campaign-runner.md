# EVIDENCE-CAMPAIGN-RUNNER-01 — development campaign

This is an orchestration contract and fixture dry run for battery v3, motor
10p/12s and f02. It does not authorize a reference solve, TRAIN run, server
rental, scientific qualification or LIVE use. The physical solvers and public
TRAIN generation remain Data Collection's code and authority.

## Prerequisites and registration gaps

The seven readiness items are **exactly** merged EVIDENCE-READINESS-CHECK-01
([#1039](https://github.com/carbonphysicsai/Carbon/pull/1039)). They are:
registered and reuse-checked panel; current solver image; applicable convergence,
conservation and code verification; kit coverage; physically disjoint registered
TRAIN; strongest cheap adapter; Challenge-supported equal-budget route. These are
distinct from Graphite readiness. The plan byte-pins one native
`carbon.onboarding.evidence-readiness.v1` JSON report per Challenge. Every item
must be `YES`; the summary is recomputed. Before a public development run, the
runner regenerates #1039's read-only report on the exact merged main and refuses
if any status changed. Its image observation is rechecked by that tool. A YES
observation is neither spend permission nor scientific qualification.

Merged [#1077](https://github.com/carbonphysicsai/Carbon/pull/1077) and
[#1078](https://github.com/carbonphysicsai/Carbon/pull/1078) register battery
panel A and TRAIN, motor TRAIN stage 1, and f02 menu and TRAIN. The read-only
campaign inventory byte-pins their modules and plans and records their image
digests without touching a Docker engine. Motor reference-panel solving is not
registered. None of those `check|solve|export-train` commands produces the
campaign's `--context`/`--output` stage receipt or the #975/#1056 assembled
comparison panel. Data Collection owns those integrations. Public execution
refuses with `PRODUCER_REGISTRATION_INCOMPLETE` until they are registered. The
runner does not convert raw solver records or invent an adapter. `--sheet-only`
shows every remaining entrypoint gap.

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
registered trusted modules, a measured cost pilot per Challenge, and an exact
plan/cap approval receipt. The current tree intentionally refuses real
execution because the campaign stage ABI and comparison assembler remain
unregistered. The approval receipt is an operator attestation to the
plan and cap, **not** cryptographic proof of human identity. The operator must
validate the actual owner's approval and provider quote outside this command.

The plan pins #1047's budget registration and VALUE-BAR-V1. Each Challenge has
complete `reference`, `train` and `assemble` shard sets; a pinned optional
`score` stage can collect a future verify-aware top-k score. The score output is
reported as `RECORDED_NOT_ADOPTED` and never mutates the value rule. The
assembler supplies #975's manifest, #1056's adaptive panel, and a digest-bound
comparison bridge. The bridge binds reference and TRAIN stage receipt hashes to
the manifest, panel and export digest. This is an identity receipt, not a
scientific validity proof. All four arms consume the same
half/base/double registered ledger. Only solver-verified design values count.
The value report contains each tier's result and retains
`INSUFFICIENT_EVIDENCE` where the public panel lacks required inputs.

Each stage's command is a pinned in-repository module, not plan-provided shell
text. The stage receives a closed context with byte-pinned inputs, same-family
prior artifacts and a fixed vCPU allotment. TRAIN cannot receive held-out
reference artifacts. Completion receipts pin every output and give CPU and peak
RAM costs. Failed reference stages remain infrastructure/reference failures,
never candidate failures. On resume, pins are checked before a task is skipped;
a failed attempt gets a new directory. The scheduler respects the registered
host's vCPUs and RAM, each stage's wall bound, the campaign wall cap and the
paid host's euro deadline.

The runner now includes its registered `vcpus` allotment in each stage context.
At a wall or euro cap it sends SIGTERM to the stage process group, waits two
seconds, then sends SIGKILL to any remaining group members. Data Collection's
producer draft #1114 must accept the explicit field and compare it with the
environment allotment before its stage can run. The prospective assembler
checks the producer's sealed export and TRAIN against the exact stage receipt,
role, summary and plan pins. Its fixture route proves the comparison bridge
through the existing #975 pipeline. Public comparison remains fail closed:
#1114 has no registered model prediction, comparator calibration, per-candidate
measured cost/proposal history, replay bindings, fold or adaptive-policy
receipt. The assembler cannot make those from a reference value alone.

## Server sheet for the owner's one-figure approval

The generated `owner-server-sheet.json` has one battery, motor and f02 row plus
the combined total. Each row shows planned CPU-hours, isolated wall-hours,
allocated euros and its capped cost-pilot receipt. The pilot records stage
samples, observed spend and an at-most-€10 pilot cap. Full-campaign stage
estimates remain labelled `ASSUMPTION` extrapolations. The total shows host
scheduled wall-hours, node USD and EUR, fixed EUR, total estimate, exact hard
cap and headroom. The node is billed once; proportional CPU-hours allocation
is accounting only. The host plan names cores, RAM, USD/hour, a registered
USD-to-EUR planning conversion and fixed charges. The owner's RunPod
32-vCPU/256-GB $1.76/hour quote, the owner-only free eight-core AX42 and a
future dedicated server are possible inputs, not measured throughput or
permission for an agent to access the AX42. An operator must check the actual
provider quote, boot/teardown/storage reserve and owner-approved cap before
a real plan exists. The in-run meter cannot bound charges after an abrupt host
failure; the paid host needs an independent provider spend cap and shutdown
procedure. Until Data Collection's registered stages and ≤€10 per-Challenge
pilot measurements exist, **there is no defensible euro figure for the owner
to approve**. The fixture sheet demonstrates arithmetic, not a production quote.

## Reproduction and boundary

`tests/cpu/test_evidence_campaign.py` builds a sealed toy plan with all three
families. It tests the full dry run, value/evidence outputs, checkpoint resume,
readiness refusal, cross-role isolation, caps and tamper refusal. No hidden,
AX42, customer or real solver material enters these fixtures. The generated
evidence pack is marked synthetic and cannot qualify a Challenge. For a public
run, the owner separately decides whether the exact server estimate and
registered inputs justify spend; VALUE-BAR-V1's observed verdict belongs to
the evidence, not this orchestration ticket.
