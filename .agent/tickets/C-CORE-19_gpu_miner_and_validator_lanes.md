# C-CORE-19: split GPU execution into a miner lane and a validator lane

Status: authorized by owner direction of 2026-09-20 — *"Maximum and efficient GPU
execution access on the miner side. Safe and controlled and SOTA GPU access on
the validator side."* The design record is `.agent/plans/C-CORE-19_gpu_lane_split.md`.
Base: `8ef19b7a` on `agent/core-platform-18-development-observation` (PR #247).
Primary Hub map_ref: `SYSTEM/AGENT-EXECUTION`; impact `map_structural`.
Dependencies: C-CORE-03 controller, C-CORE-17 telemetry capability, and
C-CORE-18's host records, effective controls, attempt settlement and retained
profile compatibility.

## Authority

This supersedes the single-lane accelerator admission model for **which
requirements apply to which role**. It does not relax the validator lane, does
not qualify hardware, does not register a telemetry contract, does not create a
grant, does not authorize an attempt, and does not change what evaluation
accepts.

The owner's four-attempt hardware authorization is unchanged and is not
dissolved by this ticket. It remains the authority for that specific hardware
batch, and the batch still requires its prerequisites.

Not authorized here: GPU attachment, numerical GPU initialization, benchmarks,
image publication, rentals, paid API use, installing or modifying any host
grant, starting a lease, creating or resetting quarantine, adding an entry to
`ESTABLISHED_OBSERVATION_CONTRACTS`, or resuming C-CORE-15.

## The mistake being corrected

`AcceleratorRole` has carried `MINER_RESEARCH` and `VALIDATOR_RECONSTRUCTION`
from the beginning, and both were routed through one admission path written to
validator requirements: a host grant asserting `EXCLUSIVE_SINGLE_DEVICE` and
`DEDICATED_NO_DISPLAY_OR_OTHER_COMPUTE`. Because dispatch was disabled, nobody
had to find out whether that was achievable on a miner host. When WSL2 turned
out to be unable to enumerate compute processes, every miner host was blocked by
a requirement that had never been argued for on the miner side.

The decisive comparison is the CPU lane, which requires none of it. A miner runs
CPU reconstruction with no host grant, no exclusive lease and no proof that
nothing else is using their CPU. Containment, input binding and validator
reconstruction carry the trust. The GPU lane should match that model plus a
device, not invent a stricter one.

Miner requirements derive from **containment and attribution**. Validator
requirements derive from **isolation and determinism**.

## Scope

KEEP the strict path exactly as it is for `VALIDATOR_RECONSTRUCTION`, the CPU
contract, the TPU rejection, every strict rejection test, the independent
scientific judge, effective controls, attempt settlement, and the retained
profile and allocation read paths from C-CORE-18.

WRAP the existing controller in a role dispatch. No parallel scheduler, no
second accounting system, and no permissive bypass.

### Miner lane — `MINER_RESEARCH`

Required: everything the CPU lane already requires (pinned immutable image, no
network, read-only root, capabilities dropped, non-root, seccomp, cgroup
CPU/memory/PID limits, bounded scratch, bounded output, a fixed deadline), plus
an installed `HostDeviceRecord`, `doctor` passing, per-run device binding
carried through the worker profile and cleanup, resolved effective controls, and
task-owned cleanup.

Explicitly not required, and not to be reintroduced: exclusivity, compute-process
enumeration, an owner-signed grant, verified whole-device release, or global
quarantine on uncertain device state. Unknown telemetry is recorded as unknown
and that is the end of it. A miner's failure to clean up blocks that miner's
next run until reconciled; it does not invoke strict quarantine semantics.

### Validator lane — `VALIDATOR_RECONSTRUCTION`

Unchanged: operator-installed host grant, exclusive single device, dedicated host
with no display or other compute, established compute-process enumeration,
verified device release, and quarantine when release cannot be confirmed.
`ESTABLISHED_OBSERVATION_CONTRACTS` stays empty; nothing here is a reason to
register an entry.

## Definition of done

- `controller.execute()` dispatches on role. **No fallback in either
  direction**: a refused strict admission must never degrade into a miner run,
  and a miner run must never be presentable as strict. Same no-fallback
  discipline the local diagnostic entry already has.
- Miner admission uses the host record, doctor and effective controls. No
  `AcceleratorHostAdmission.load()`, no `exclusive_lease()`.
- A local per-device lock so one miner's own two runs cannot contend. Plain
  mutual exclusion, not the shared Carbon slot, and no quarantine semantics.
- The worker profile publishes the lane and its assurance label. Strict and CPU
  bodies stay byte-identical, asserted.
- A miner result carries an assurance label naming the lane and what was and was
  not established. Strict and official consumers reject it on its own terms,
  asserted by test.
- `run`, `cancel` and `recover` in `scripts/dev/carbon_accelerator.py`, wired to
  the existing controller with the smallest wrappers. Ordinary permitted
  operation must not require hand-built internal Python objects. Documented and
  tested end to end.
- Compatibility per the rules already applied in C-CORE-18: explicit versions,
  bounded read paths for legacy shapes, frozen baseline fixtures taken from
  accepted `main`, unknown records fail closed, and no historical allocation
  reclassified to escape its strict cleanup obligation.

## The existing local development approval

The miner lane subsumes it: a diagnostic on the owner's laptop is a miner-lane
run. **Two lanes, not three.** The development approval remains as the bounded
authority over the owner's authorized hardware batch — it is a constraint
layered onto a miner-lane run, not a third execution model.

## Reserved to the owner, and not decided here

1. **Scoring.** Whether miner-lane results are weighted, tiered by host
   capability, or treated identically to CPU submissions. This ticket labels the
   assurance; it does not decide what the label is worth.
2. **Validator host requirements.** Whether validators must be bare-metal Linux,
   and who provisions them.
3. **Whether `ESTABLISHED_OBSERVATION_CONTRACTS` ever admits an entry**, and on
   what evidence.

Each stays explicit and fail closed. Work that depends on one stops; the rest
continues.

## Acceptance

Role dispatch in both directions with no fallback; miner admission without a
grant or lease; strict admission still refusing without one; the local device
lock excluding a second local run without touching the shared slot or
quarantine; byte-identical strict and CPU worker-profile bodies; a miner
assurance label that no strict or official consumer accepts; `run`, `cancel` and
`recover` driven through the real controller; and the C-CORE-18 compatibility
guards still passing.

Host metadata is not a compatibility or security certificate. Simulated
other-device and cloud inventories are fixture coverage only. No accelerator is
initialized and no device is attached by this ticket's tests.
