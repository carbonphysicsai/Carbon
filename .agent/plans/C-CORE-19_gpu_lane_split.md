# Design: split GPU execution into a miner lane and a validator lane

Owner direction, 20 September 2026: *"Maximum and efficient GPU execution access
on the miner side. Safe and controlled and SOTA GPU access on the validator
side."*

This supersedes the single-lane accelerator admission model. It does not relax
the validator lane, and it does not create new hardware authority.

## The mistake being corrected

`AcceleratorRole` has had `MINER_RESEARCH` and `VALIDATOR_RECONSTRUCTION` from
the beginning. Both were routed through one admission path, and that path was
written to validator requirements: a strict host grant asserting
`EXCLUSIVE_SINGLE_DEVICE` and `DEDICATED_NO_DISPLAY_OR_OTHER_COMPUTE`.

That profile also shipped `admission_enabled: False` and
`allocation: EXCLUSIVE_REQUIRED_NOT_VERIFIED` - a placeholder meaning "require
the strictest thing, we have not checked it is achievable." Because dispatch was
disabled, nobody had to find out. When WSL2 turned out to be unable to enumerate
compute processes, every miner host was blocked by a requirement that was never
argued for on the miner side.

**The decisive comparison: the CPU lane has no such requirement.** A miner runs
CPU reconstruction with no host grant, no exclusive lease and no proof that
nothing else is using their CPU. Containment, input binding and validator
reconstruction carry the trust. The GPU lane should match that model, plus a
device. It should not invent a stricter one.

## Why the asymmetry is principled

**Miners are given nothing secret.** They receive a public construction plan and
public TRAIN material. There is nothing on a miner host to leak, so device
side-channels protect nothing. The real question - did this miner actually
compute the artifact they submitted - is answered by content binding and by
validator reconstruction, not by device exclusivity. If a miner's own run is
slowed or killed by their own contention, they lose; nobody else is harmed.

**Validators are the arbiter and may hold protected material.** Hidden cases and
seeds, and a decision that binds others. There, contamination, nondeterminism and
side channels matter, and exclusivity earns its cost. Validator hosts can
reasonably be required to be dedicated Linux machines.

So: miner requirements derive from *containment and attribution*; validator
requirements derive from *isolation and determinism*.

## Miner lane: `MINER_RESEARCH`

### Required

Everything the CPU lane already requires, unchanged - the pinned immutable image,
no network, read-only root filesystem, all capabilities dropped, non-root user,
seccomp, cgroup CPU/memory/PID limits, bounded scratch, bounded output, a fixed
deadline - plus:

1. **An installed `HostDeviceRecord`** describing the device. Already built.
   Provider- and vendor-independent; no source edit for new hardware.
2. **`doctor` passing**: a container runtime exposing the device, the pinned
   image present and matching its labels, the device visible.
3. **Per-run device binding**: `CUDA_VISIBLE_DEVICES` from the record, carried
   through the worker profile, container labels and cleanup. Already built.
4. **Effective controls**: resolved from policy and registered ceilings before
   the run. Already built.
5. **Task-owned cleanup**: remove exactly this launch's container and release its
   own allocation record. Already built.

### Explicitly NOT required

- **No exclusivity.** No proof that nothing else is on the device. No
  `DEDICATED_NO_DISPLAY_OR_OTHER_COMPUTE`. A miner may game, render or run other
  work on the same GPU.
- **No compute-process enumeration.** WDDM, `N/A`, unknown - all acceptable. The
  observation is recorded as unknown and that is the end of it.
- **No owner-signed grant.** Admission is self-service from local policy. No
  human signs a record per run; that model cannot work for a network of miners.
- **No verified whole-device release.** Cleanup confirms this launch's own
  resources are gone. It does not assert the device is idle.
- **No global quarantine on uncertain device state.** A miner's own machine is
  not a shared Carbon slot. Failure to clean up blocks *that miner's* next run
  until reconciled; it does not invoke strict quarantine semantics.

### What a miner result carries

An assurance label naming the lane and what was and was not established. It is a
candidate submission, verified downstream by validators - exactly as CPU results
are today. It must never present as validator-grade evidence, and strict
consumers must reject it on its own terms.

## Validator lane: `VALIDATOR_RECONSTRUCTION`

Unchanged from the current strict path, which is correct for this role:
operator-installed host grant, exclusive single device, dedicated host with no
display or other compute, established compute-process enumeration, verified
device release, and quarantine when release cannot be confirmed.

`ESTABLISHED_OBSERVATION_CONTRACTS` stays empty until a source is genuinely
established. Nothing in this split is a reason to register one. That gate belongs
to validators, where it is worth paying for, and its emptiness is now a validator
problem rather than a platform-wide block.

## Implementation

Dispatch on role rather than on the presence of a grant.

- `controller.execute()`: `MINER_RESEARCH` takes the miner path;
  `VALIDATOR_RECONSTRUCTION` takes the existing strict path. No fallback in
  either direction: a refused strict admission must never degrade into a miner
  run, and a miner run must never be presentable as strict. This is the same
  no-fallback discipline the local diagnostic entry already has.
- Miner admission: `HostDeviceRecord` + `doctor` + effective controls. No
  `AcceleratorHostAdmission.load()`, no `exclusive_lease()`.
- Keep a **local per-device lock** so a miner's own two runs cannot contend and
  corrupt each other. Plain mutual exclusion, not the shared Carbon slot, and no
  quarantine semantics.
- Worker profile: publish the lane and its assurance label, and the effective
  controls. Strict and CPU bodies stay byte-identical.
- Operator commands: `run`, `cancel`, `recover` in `carbon_accelerator.py` become
  the miner's actual entry point. This makes them the highest-value item in the
  current review list, not the lowest.

### The existing local development approval

The miner lane subsumes it: a diagnostic on the owner's laptop is a miner-lane
run. Two lanes, not three. **The owner's four-attempt authorisation is unchanged
and is not dissolved by this** - it remains the authority for that specific
hardware batch, and the batch still requires its prerequisites.

### Compatibility

Governed by the rules already recorded in the handoff appendix: explicit
versions, bounded read paths for legacy shapes, frozen baseline fixtures taken
from accepted `main`, unknown records fail closed, and no historical allocation
reclassified to escape its strict cleanup obligation.

## Work already in flight is not wasted

- **Portability / host records / doctor / onboarding** - the miner lane's
  foundation. Keep as is.
- **Effective controls** - needed by both lanes.
- **Attempt settlement** - needed by both; the miner lane uses the same
  reconciliation without strict quarantine.
- **Batch accounting** - primarily a validator and authorised-batch concern;
  miners are bounded per run.
- **Compatibility / `HISTORICAL_PROFILES`** - needed either way.
- **Successful result path** - needed before any lane is real.

## Decisions the owner still owns

1. **Scoring.** Whether miner-lane results are weighted, tiered by host
   capability, or treated identically to CPU submissions. This spec labels the
   assurance; it does not decide what the label is worth.
2. **Validator host requirements.** Whether validators must be bare-metal Linux,
   and who provisions them.
3. **Whether `ESTABLISHED_OBSERVATION_CONTRACTS`** ever admits an entry, and on
   what evidence.

## What this does not do

It does not qualify any hardware, register a telemetry contract, create a grant,
authorise an attempt, or change what evaluation accepts. It changes which
requirements apply to which role, so that a miner is not blocked by a validator's
threat model.
