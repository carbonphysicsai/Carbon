# C-CORE-18: bounded local GPU diagnostic preparation

Status: preparation candidate under programme #209; the contract it proposes is
**PROPOSED and NOT ACTIVATED**. Canonical and delivery gates pending.
Base: `3ec404d7e33a8d7e9aabafe0aa16f9d13fdc98c8`.
Primary Hub map_ref: `SYSTEM/AGENT-EXECUTION`; impact `map_structural`.
Dependencies: C-CORE-03 accelerator reconstruction controller, C-CORE-14 public
GPU diagnostic composition, and C-CORE-17 telemetry capability.
Integration owner maintains programme/Hub and downstream delivery.

## Authority

The owner authorized read-only inspection, one conflict-safe local retention tag
for the already-built image, a proposed development-only contract and run plan
with supporting device-free tests, and normal delivery of clearly labelled
preparation.

Not authorized and not performed: GPU attachment or numerical GPU
initialization, benchmarks, new image builds, rentals, paid API use, image
publication, installing or modifying the strict host grant, starting a lease,
creating or resetting quarantine, live device-release verification, adding a
real entry to `ESTABLISHED_OBSERVATION_CONTRACTS`, resuming C-CORE-15, or any
change to host drivers, Docker defaults, display routing, power policy or
clocks.

The earlier image-build exception completed its scope and is not extended here.

## Scope

KEEP the existing controller, host grant, exclusive lease, journal, accounting,
quarantine and cleanup authorities, the CPU contract, the TPU rejection, every
strict rejection test, and the independent scientific judge. No parallel
scheduler, accounting system or permissive bypass is introduced.

WRAP the existing registered public diagnostic recipe and the registered
`Trainer.fit()` path in one proposed, finite first-run plan, and add a host-side
plan validator that refuses dispatch unconditionally.

Delivered here:

- `.agent/plans/C-CORE-18_local_gpu_diagnostic_contract.md` — the proposed
  development-only contract, the identified security seam, and the first run
  plan with its proposed limits.
- `carbon/development_session/local_diagnostic_plan.py` — plan validation,
  owner-approval binding, cleanup gating, and an unconditional dispatch refusal.
- `tests/cpu/test_local_diagnostic_plan.py` — device-free controls.

## The seam returned as a decision

A local diagnostic cannot reuse the strict admission path without redefining
that path's security contract. After C-CORE-17, `inspect_gpu_device()` refuses
unless enumeration capability is `ESTABLISHED`; this host reports `WDDM`, which
is `UNSUPPORTED`, and the registry is empty, so every other reading is
`UNESTABLISHED`.

The contract document proposes one narrow versioned extension — a separate,
explicitly weaker development observation outcome that never asserts exclusivity
and can never satisfy a strict caller. It is **described, not implemented**,
because it changes the meaning of a security boundary.

## Acceptance

Device-free regressions cover missing, expired, mismatched and malformed
approval; wrong pinned source, image, environment, profile and input identities;
unknown workload and unregistered schema; injected command, entrypoint, mount,
device, `--gpus`, privileged, URL, package, env, role, grant and host-path
fields; protected input phases; exact field-set and integer-bound enforcement
including `bool` rejection; per-process versus whole-task deadline ordering;
replayed nonce; ambiguous cleanup blocking the next run without touching strict
quarantine; and the absence of any promotion path into official or strict
acceptance.

Batch accounting is enforced, not only declared. The batch's output total is
summed across attempts and its time bound is a wall-clock window from first
admission, so a pause, a restart, a new worktree or a fresh output directory
cannot rewind either. Failed and ambiguous attempts keep their reserved worst
case; only a measurement taken from the run's own observation may reduce a
charge. A marker whose charge this journal cannot read - an older schema or a
malformed field - blocks the next attempt rather than counting as zero, which
keeps the older record's meaning intact while failing closed.

The whole-attempt deadline is enforced with it. Previously only
`productive_seconds` reached execution, so staging, image verification, export
and cleanup fell outside every deadline - and the batch window cannot be
honestly admitted on the promise that an attempt ends by a time nothing
enforces. It is observed at the same boundaries as the existing cancellation
channel and raises its own code, so an operator stopping a run and a run
outliving its deadline stay distinguishable.

Two guard tests assert that this preparation leaves the strict contract
untouched: `ESTABLISHED_OBSERVATION_CONTRACTS` remains empty and
`require_accelerator_admission()` still refuses.

No accelerator is initialized, no numerical backend is imported, no Docker
command runs, and no real host grant or quarantine storage is touched. Fixture
success is not hardware acceptance, and merging this ticket ratifies no security
contract and starts no work.
