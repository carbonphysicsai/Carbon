# OWNER-GPU-LANE-NO-OP-GATE-01: every graph on an accepted GPU class builds on the GPU (no per-op gate)

Date: 2026-11-17.
Status: ORDERED by the owner. Typed in the Lead session and relayed verbatim by the Lead to TE3.

Owner's words: "No. We've proven WEEKS ago that builds on the same GPU class are identical. This is absolute garbage
overprotection that's killing our subnet again. Drop it now"

The Lead's reading, which TE3 implements: drop the per-op eligibility gate of the graph GPU lane. On an accepted,
class-checked GPU class, every Motor 1.8 graph builds on the GPU; no per-op eligibility. What stays: the box's class
check passing, and a GPU build that errors is Carbon's (FAILED_INFRA, never charged) or a CPU rebuild.

## Why it was needed

Live 116 (Deploy-B, 17 Nov): 686 retained graphs, 95 queued, ZERO eligible under the 20-op record (ops record
952b01b7): every graph used an op outside it (concatenate, sin, cos, convert_element_type, slice, ...). The accepted
A100 built nothing.

## What changes in code

- `carbon/development_session/graph_gpu_lane.device_for`: on a lane with a JAX GPU worker and a loaded ops record (the
  class check's own PASS), every READABLE graph returns the GPU. A graph's ops are no longer compared with the record.
  An unreadable graph stays a CPU rebuild (fail closed).
- Unchanged:
  - the record is still required, loaded against Motor 1.8's served allowlist, and bound by the door
    (`graph_gpu_ops_digest`) and the provider binding;
  - the per-task GPU repeat check (two more GPU rebuilds must be bit-identical, else a CPU rebuild,
    GPU_REBUILD_RULINGS rule 1);
  - a lost link or GPU is FAILED_INFRA (`remote_gpu_build`);
  - grading on the CPU image;
  - retained evidence notes (`graph_op_not_gpu_repeatable`) are still read.

## Deployment

Code-only. It needs no door migration and no worker image: `graph_gpu_lane.py` is not a worker-image build input, and
no door key changes. It is a grading path (`direct_receiver.GRADING_PATHS`), so the deploy declares the exam change.

## Open for the owner / Lead

The per-task GPU repeat check (rule 1) is kept: the order names the per-op gate. Dropping it too would make each GPU
task one GPU build instead of three. That needs the owner's word.
