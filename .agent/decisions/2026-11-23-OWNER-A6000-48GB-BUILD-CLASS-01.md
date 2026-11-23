# OWNER-A6000-48GB-BUILD-CLASS-01: the Lambda RTX A6000 48 GB VM accepted as a Carbon GPU build class

Date: 2026-11-23, 18:51:18Z.
Status: ACCEPTED by the owner, typed in the Lead seat. Recorded verbatim in codex-queue/ops/OWNER_LINES.md as G-LEAD-60
(RECEIPTS 5459).

Owner's words: "I guess that's the move", answering block 57: "approved: OWNER-A6000-48GB-BUILD-CLASS-01: Motor 1.9 and
RB 2.0 miner builds may run on Lambda RTX A6000 48 GB VMs (gpu_1x_a6000) with the door's pinned engine, after infra's
class record passes; on demand, same pool rules as the A100."

Context (G-LEAD-59, 17:52:56Z, "No we're going RTX6000. I approve whatever we need to get there"): the Lium RTX 6000 Ada
pods are sysbox containers that cannot run the door's pinned engine (runc 1.5.x) for hostile builds (infra 5288). gVisor
on them was measured NOT feasible (infra 5449). The Lambda A6000 is a VM, so it runs the pinned engine.

## Condition met: infra's class record (RECEIPTS 5505)

- `codex-queue/reports/INFRA/A6000_CLASS_20261123/a6000-class-check.json`, sha256
  `54446e4a6675e2e67466961af8ada2d26da2b904ebb0f615d77d80ee4f2e1535`.
- Ops record `a6000-ops-record.json`, sha256 `a2887c4af2f9e36c914d6160962393d49bc8df9eaf7dd29eddcdcbb12d202a22`.
- Verdict GPU_REPEATS 16/16, all bit-identical, all on GPU; a full repeat run equal.
- Slots 1 / 2 / 3 at once (4-core cpusets) digest-equal, memory shared ("capped" not measured).
- Run with the door's own class check (`gpu_box_up` cmd_class_check, JAX image 613b4e6a by digest, `--no-torch`) on docker
  29.1.3 / containerd 2.4.2.

## Scope

- **Device class:** the exact name `nvidia-smi` reports, `NVIDIA RTX A6000`.
- **Profile:** JAX GPU builds only. The record measured JAX, not PyTorch, so the PyTorch profile is not entered.
- **Network:** finney (mainnet 116) only.
- **Doors:** Motor 1.9 and RB 2.0. Values rows `"electric-motor-magnetics 1.9"` and `"f08-ribbed-bracket 2.0"` in
  `scripts/validator_host_classes/remote_gpu_build.json`. The Ada row it replaces, and the Ada acceptance, stay as record
  history, unused. Motor 1.8 and Cooling 1.8 stay on the A100.
- **Role:** GPU BUILDS on the remote GPU build lane only. Grading, inference and the speed gate do not move.
- **Comparability:** a new class. Its digests are not comparable with the A100 or Ada records.

## Slots

- 2 shared slots per box at the first admission. The record shows 3 digest-equal, but 3 x the 16 GiB build memory plus
  8 GiB for the host needs about 56 GiB of RAM (`gpu_box_up.vm_slot_cpusets`).
- The row goes to 3 once infra's MemTotal reading of the VM shows at least 56 GiB. That is a values change at a door
  restart.
