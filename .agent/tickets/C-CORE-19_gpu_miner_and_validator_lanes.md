# C-CORE-19: split GPU execution into a miner lane and a validator lane

Status: authorized by owner direction of 2026-09-20.
**Authority: `docs/development/GPU_EXECUTION_LANES.md`** (recorded as `ec869dbc`
on `agent/gpu-execution-lane-design`, PR #248). That document is the authority;
this ticket is the bounded engineering scope under it and does not extend it.
Base: `8ef19b7a` on `agent/core-platform-18-development-observation` (PR #247).
Primary Hub map_ref: `SYSTEM/AGENT-EXECUTION`; impact `map_structural`.
Dependencies: C-CORE-03 controller, C-CORE-17 telemetry capability, and
C-CORE-18's host records, effective controls, attempt settlement and retained
profile compatibility.

## Authority and its limits

Accelerator admission applied validator requirements to miners. It now splits by
`AcceleratorRole`, which has carried both values all along.

This ticket qualifies no hardware, registers no telemetry contract, creates no
grant, authorizes no attempt, sets no tolerance, and changes nothing about what
evaluation accepts. It changes which requirements apply to which role.

Not authorized: GPU attachment, numerical GPU initialization, benchmarks, image
publication, rentals, paid API use, installing or modifying any host grant,
starting a lease, creating or resetting quarantine, adding an entry to
`ESTABLISHED_OBSERVATION_CONTRACTS`, or resuming C-CORE-15.

## Why the roles differ

Carbon's submission is a **declarative training strategy**, not a trained
checkpoint. Validators reconstruct and train from scratch under pinned
contracts, and a miner may submit without training locally at all.

So **miner GPU output never enters the scientific record.** Nothing a miner
computes locally is submitted, verified or scored. There is nothing on a miner
host to protect and nothing for device side-channels to defend, and Carbon's
only interest is that more of that search happens. A miner who contends with
their own GPU wastes their own time and harms nobody.

A validator's GPU run is the training that counts, and a wrong verdict there
enters the record. That is a different problem and it is not solved here.

Carbon ships the miner tooling for **fidelity, not gatekeeping**: a miner
exercising a strategy in the same pinned environment a validator will use can
predict what the validator gets. Restricting it subtracts search capacity and
adds nothing, because the output is not evidence.

## Scope

KEEP the strict path for `VALIDATOR_RECONSTRUCTION` exactly as it is, the CPU
contract, the TPU rejection, every strict rejection test, the independent
scientific judge, effective controls, attempt settlement, and the retained
profile and allocation read paths from C-CORE-18.

WRAP the existing controller in a role dispatch. No parallel scheduler, no second
accounting system, no permissive bypass.

### Miner research lane — `MINER_RESEARCH`

Required, and no more: the pinned immutable worker image matching its labels;
worker containment exactly as the CPU lane has it (no network, read-only root,
capabilities dropped, non-root, seccomp, cgroup CPU/memory/PID bounds, bounded
scratch, bounded output, a deadline); content-bound inputs; an installed
`HostDeviceRecord`; `doctor` passing; effective controls resolved before the
run; and task-owned cleanup of exactly this launch's container and allocation.

Removed for this role, and not to be reintroduced: exclusivity, compute-process
enumeration, the owner-signed grant, verified whole-device release, and global
quarantine. Any NVIDIA device, any platform, any provider. Admission is
self-service, because no human can sign a record per run for a network of
miners.

### Validator reconstruction lane — `VALIDATOR_RECONSTRUCTION`

Unchanged, and **not qualified here.** It plugs into the mechanism that already
exists: `compare_r1` returns `INDETERMINATE` unless `backend_support` is
`SUPPORTED`, so a GPU backend profile stays a candidate until **MQ-008** supplies
evidence under R0/R1/R2 at gate G4, owned by SCI + SRE. Nothing in this ticket
routes around that.

**This ticket takes no position on validator exclusivity.** Whether device
contention perturbs kernel selection or allocation enough to affect numerical
outcomes is an empirical question MQ-008 owns. Do not remove the strict
machinery, and do not argue for it either.

`ESTABLISHED_OBSERVATION_CONTRACTS` stays empty.

## Rules that must not bend

1. **Exact stays exact.** R0 identities, schemas, provenance and artifact byte
   integrity remain exact on both lanes. Only repeat-execution numerics admit a
   registered tolerance.
2. **Never choose a tolerance.** If a comparison needs one and none is
   registered, the answer is `INDETERMINATE` or development evidence. Do not pick
   an epsilon to make a test pass; MQ-008 explicitly rejects broadening hardware
   support by loosening tolerances.
3. **Never relabel B as A.** A fresh reconstruction is its own artifact with its
   own identity. Matching predictions do not establish the same artifact.
4. **Keep protected material off this path**, as a named invariant with a test
   rather than an accident of the current design.
5. Existing bit-exact regression tests stay where they assert a deliberately
   exact property. Changing such a promise needs an explicit migration, never a
   quiet edit.

## Definition of done

- `controller.execute()` dispatches on role. **No fallback in either
  direction**: a refused strict admission must never degrade into a miner run,
  and a miner run must never be presentable as strict. Same discipline the local
  diagnostic entry already has.
- Miner admission uses the host record, `doctor` and effective controls. No
  `AcceleratorHostAdmission.load()`, no `exclusive_lease()`.
- A local per-device lock so one miner's concurrent runs cannot corrupt each
  other. Plain mutual exclusion, not the shared Carbon slot, and no quarantine
  semantics.
- The worker profile publishes the lane. Strict and CPU bodies stay
  byte-identical, asserted.
- A miner result is not presentable as strict or official evidence, asserted.
- `run`, `cancel` and `recover` in `scripts/dev/carbon_accelerator.py`, over the
  same controller — no second scheduler. Ordinary permitted operation must not
  require hand-built internal Python objects. Documented and tested end to end.
- **The protected-material invariant test**, which fails if any of these three
  stops holding: `carbon/reconstruction/accelerators` is imported only by
  `carbon/reconstruction`, `carbon/reconstruction/worker` and
  `carbon/development_session`; the staged worker request field set is closed;
  and `PublicTrainingArchive` rejects any role but `TRAIN` and any format but
  `carbon.public-trajectories.v1`.
- Compatibility per the rules already applied in C-CORE-18: explicit versions,
  bounded read paths for legacy shapes, frozen baseline fixtures from accepted
  `main`, unknown records fail closed, and no historical allocation reclassified
  to escape its strict cleanup obligation.

## Known follow-up, deliberately not done here

`PublicGPUPractice` in `carbon/development_session/gpu_research.py` is the one
production caller that already ran the controller with `MINER_RESEARCH`, and it
still loads a strict host grant through `AcceleratorHostAdmission.load()` before
it gets there. Under the split that requirement no longer applies to its role.
It is left alone in this ticket rather than changed in passing: it is a working,
tested path, and rewiring it is its own change with its own evidence.

## The local development approval

The miner lane subsumes it. **Two lanes, not three.** The owner's four-attempt
authorization is unchanged: that is batch authority, not a lane, and it is not
dissolved by this ticket. It remains a bound layered onto a miner-lane run.

## What the four attempts are for

Evidence production for MQ-008: the same registered strategy under identical R0
identities, executed on CPU and on the GPU, with observed divergence recorded for
SCI + SRE. Not a demonstration. "The GPU ran something" is not a result; a
measured divergence under pinned identities is.

The envelope is unchanged: four attached attempts total including failures and
retries, 32 training steps per invocation, 600 s productive with a 120 s cleanup
reserve, 1800 s per attempt, 3600 s per batch from first admission with no
restart reset, worker RAM at the lower registered ceiling, 64 MiB per attempt and
256 MiB per batch of output and retained logs, worker network disabled, zero paid
spending. Hardware still requires its existing implementation, image and
acceptance prerequisites.

## Completion work package W1-W5

Executed under `docs/development/GPU_COMPLETION_WORK_PACKAGE.md`. W6 is
**withdrawn**: no attempt is planned on the owner's device, because a laptop GPU
under WSL2 verifies neither the launchpad nor a validator backend profile, and
spending attempts on it would repeat in evidence the mistake that demoting
`RTX3060_LAPTOP_PROFILE` corrected in the registry.

| | Item | Result |
| --- | --- | --- |
| W1 | Close stage 1 | CPU acceptance green at `b0b04d44`: 6882 passed, 10 skipped, exit 0, 0 modified paths at start and finish. Log retained. Worker image rebuilt against the revision. |
| W2 | MQ-008 evidence specification | Drafted for SCI + SRE acceptance: `docs/development/MQ008_EVIDENCE_SPECIFICATION.md`. Not accepted; sets no tolerance. |
| W3 | CPU determinism across configurations | Measured. `.agent/evidence/wave_c/c-core-19-cpu-determinism-across-configurations.md`. |
| W4 | Prescribed exam environment | Declared and published: `docs/development/VALIDATOR_EXAM_ENVIRONMENT.md`. Declared, not qualified. |
| W5 | Gate margin analysis | `.agent/evidence/wave_c/c-core-19-gate-margin-analysis.md`. No threshold changed. |
| W6 | First GPU attempt | **Withdrawn — none planned.** `.agent/plans/C-CORE-19_no_local_gpu_attempt.md`. 0 of 4 attempts consumed. |

**W3 returned a finding that outranks the GPU programme.** The same registered
strategy under identical R0 identities produces different trained weights
depending on the CPU instruction-set level the backend compiles to, and every
identity Carbon records - `observed_environment_digest`, `environment_digest`,
`profile_digest`, `plan_digest` - is identical across the divergent runs. This is
a cross-host reproducibility question on CPU, independent of any device. It is
recorded with the owner decisions it raises; nothing was changed in response to
it here.

## Determinism work package D1-D5

Executed under `docs/development/GPU_DETERMINISM_WORK_PACKAGE.md`, on the owner's
device under the owner's explicit authorization to spend GPU attempts for Carbon
development testing.

| | Item | Result |
| --- | --- | --- |
| D1 | Record what determines numerics | `carbon/reconstruction/numerics_environment.py`; artifact manifest versioned v3/v4 -> v5/v6 with the old versions still readable. |
| D2 | Achievable determinism configuration | Pinned in `worker_environment()`; every flag verified against the pinned build, not recalled. |
| D3 | Test it on the device | `.agent/evidence/wave_c/c-core-19-gpu-determinism.md` and its raw per-session records. |
| D4 | Validator policy | `docs/development/VALIDATOR_GPU_DETERMINISM_POLICY.md` - declared, not qualified. |
| D5 | Gate robustness options | `.agent/evidence/wave_c/c-core-19-gate-robustness-options.md` - **implemented nowhere**. |

**The measurement.** An unpinned GPU reconstruction does not reproduce across
processes: four sessions of the same registered strategy under identical R0
identities produced four different weight digests, each session internally
bit-identical. Under the pinned configuration, three sessions produced one
digest. Pinning also changes the numbers, and costs about +1.0 s of compile time
(+63%) with execution overhead unmeasurable at this workload size.

It qualifies nothing. A laptop GPU under WSL2 qualifies no hardware, and this was
a determinism check rather than MQ-008 evidence. It does verify that the settings
function, which is a claim about the settings and transfers.

It also verified D1 directly: the pinned and unpinned runs computed different
weights and now record different environments, differing in exactly the three
keys responsible. Before D1 they would have been indistinguishable - the same
failure the CPU instruction-set finding exposed, reproduced on a GPU.

## Acceptance

Role dispatch in both directions with no fallback; miner admission without a
grant or lease; strict admission still refusing without one; the local device
lock excluding a second local run without touching the shared slot or
quarantine; byte-identical strict and CPU worker-profile bodies; a miner result
no strict or official consumer accepts; `run`, `cancel` and `recover` driven
through the real controller; the protected-material invariant test; and the
C-CORE-18 compatibility guards still passing.

Host metadata is not a compatibility or security certificate. No accelerator is
initialized and no device is attached by this ticket's tests.

## Why `run` claims rather than assembles

The launch manifest carries **materials**, not identity. Which execution a run
is, who requested it and what seed it is pinned to already exist in the durable
queue, put there by whoever admitted the work - and the seed pin could not be
carried in a file even if that were wanted, because `EvaluationBinding` is
deliberately opaque and exposes no accessor. `run` therefore claims an admitted
execution and checks the manifest's plan, profile and policy digests against the
binding that execution already committed to, so materials for different work are
refused rather than run. Reconstructing identity host-side would have meant
inventing a second, weaker version of it beside the real one.
