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

## Compatibility with records accepted on main

The portable-host change was the right direction and it rewrote accepted
contracts to reach it. Compared against `0a9dbaaf` - the merge of PR #240, on
`main` - five records changed meaning without changing name. Each is repaired by
versioning the new shape and retaining a bounded read path for the old one, not
by restating the old expectation:

1. The registered RTX-3060 profile was replaced in `PROFILES`, so a record
   naming it no longer resolved at all. It is retained as `HISTORICAL_PROFILES`
   with its original body and therefore its original digest
   (`sha256:8408adc8…`). Retention is interpretation: `resolve_profile` finds
   it, and `_registered` refuses it wherever execution is decided, so it cannot
   be dispatched, given a worker overlay, admitted, or staged into new work.
2. The common profile body dropped three serialized keys while still calling
   itself `carbon.accelerator-profile.v1`, which moved the TPU digest under an
   unchanged profile id. The host-pinned shape keeps `v1` and its exact key set;
   the portable shape is `carbon.accelerator-profile.v2` and omits those keys
   rather than writing them as null. The TPU profile is back to
   `sha256:b88d9f6f…`.
3. The worker reader stopped accepting the three-field strict accelerator block
   `{profile_id, grant_digest, role}` for a GPU profile, while reusing the
   `worker-request.v2` label for a new four-field body. v2 is restored to the
   body it was accepted with; naming a device is `worker-request.v5`.
4. The active-allocation decoder began requiring an `authority` key that
   retained records do not carry, which stranded any host still holding a real
   allocation. A two-field record is read as the strict allocation it was -
   deliberately not as a development one, which would discharge a whole-device
   release obligation that was never satisfied. An unrecognised shape still
   fails closed.
5. Surfaced by the frozen fixture rather than by inspection: the worker profile
   body stamped the current profile's digest and the launch's device onto a
   request that named an earlier profile, moving `worker_profile_digest` for an
   already-accepted request. It now derives both from the profile the request
   actually names.

The evidence is `tests/fixtures/accelerator_baseline/`: a complete staged worker
request produced by `0a9dbaaf`'s own `stage_request`, frozen as bytes. Two
constructors from the current implementation compared against each other cannot
show historical compatibility; only bytes that predate the change can. No
historical expected digest was updated to make a new serialization pass.

The documentation claim that a shared workload-profile digest leaves two runs
comparable is also corrected. It establishes that they requested the same
configuration; comparability is a scientific judgement about measurements.

Two guard tests assert that this preparation leaves the strict contract
untouched: `ESTABLISHED_OBSERVATION_CONTRACTS` remains empty and
`require_accelerator_admission()` still refuses.

No accelerator is initialized, no numerical backend is imported, no Docker
command runs, and no real host grant or quarantine storage is touched. Fixture
success is not hardware acceptance, and merging this ticket ratifies no security
contract and starts no work.
