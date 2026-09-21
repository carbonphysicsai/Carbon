# C-CORE-20: validator GPU reconstruction orchestration

Status: authorized by owner direction of 2026-09-21.
**Authority: `docs/development/C_CORE_20_VALIDATOR_ORCHESTRATION.md`** on
`agent/gpu-execution-lane-design` (PR #248). That document is the authority; this
ticket is the bounded engineering scope under it and does not extend it.
Base: `dbfaec1d` on `main` (the C-CORE-19 merge, PR #249).
Primary Hub map_ref: `SYSTEM/AGENT-EXECUTION`; impact `map_structural`.
Dependencies: C-CORE-19 admission decision and dispatch, C-CORE-03 controller,
the durable execution queue and the durable worker launch store.

The ID was verified free before it was claimed: no remote branch, no ticket file
and no reference on `main` at `dbfaec1d`. C-CORE-19 was the highest existing, so
C-CORE-20 is the correct successor.

## The gap this closes

C-CORE-19 made `VALIDATOR_RECONSTRUCTION` admissible on a GPU and then recorded,
in its own delivery, that **nothing constructed one**. `repeats.py` calls
`reconstruct()` in process and that module contains no backend, accelerator,
profile or device selection of any kind, so validator reconstruction was direct
CPU with no seam through which a validator run could reach the accelerator
controller. Admission was unblocked and unreachable at the same time.

This ticket builds the caller.

## Scope

KEEP then WRAP. `carbon/reconstruction/validator_launch.py` is the validator
counterpart of the working `miner_launch.py`, using the same controller, the same
durable queue and the same launch store.

**No second orchestration system.** Cancellation and recovery are properties of
the host and its launch store rather than of a lane, so both entry points call
one implementation and differ only in the label on the record they write. A
second copy could only drift from the first.

**No backend parameter on the `repeats.py` path.** A parameter there would be
exactly the role laundering the design forbids.

## What makes it a validator entry point

1. **The role is fixed and is not a parameter**, exactly as the miner path fixes
   its own: a caller that could choose the role could choose the lane.
2. **The execution class is Carbon's, not the submitter's.** The image is
   resolved from an operator-installed registered record through the existing
   image mechanism. The manifest has **no image field at all** - absent rather
   than ignored, so there is nothing to smuggle and nothing to disagree with.
3. **Identity comes from the queue, never from the file.** The manifest supplies
   materials; every one is checked against the digests the binding already holds.

## Not authorized by this ticket

GPU attachment, device invocation, benchmarks, image publication, rentals, paid
API use, host grants, leases, quarantine, any entry in
`ESTABLISHED_OBSERVATION_CONTRACTS`, any change to `compare_r1`, any tolerance,
any scoring gate change, and any median or consensus evaluator.

Everything delivered here is device-free. The hardware test is **proposed, not
run**: `docs/development/VALIDATOR_TWO_HOST_EXACT_REPLAY_PLAN.md`.

## Definition of done

- The validator orchestration exists and reaches the real controller launch
  boundary carrying the validator role, the validator lane, the registered image
  identity and the exact committed work binding.
- Every negative in the authority document refuses, each with a test that states
  what it proves.
- The successful result path is carried as far as it goes device-free, with the
  one step that genuinely requires hardware isolated and named rather than
  approximated.
- Protected-material negatives retained and extended to the new module.
- Hub reconciled from source; CI green; merged.

## Maturity, reported as distinct states

`SPECIFIED`, `IMPLEMENTED`, `TESTED` are earned here. `HARDWARE_EXERCISED`,
`SCIENTIFICALLY_QUALIFIED`, `SECURITY_QUALIFIED` and `PRODUCTION_QUALIFIED` are
not, and none may be inferred from the others.

The strongest permitted statement is:

> Validator GPU orchestration is implemented and engineering-tested; official
> backend qualification remains unresolved.

**Not** "GPU validator deployable."

## Kept separate

#242 archive/tamper defect, #246 Linux workspace delivery, #248 GPU design
documents, #251 Launchpad product integration, and the Workbench successor's
repairs. None is touched here and none is a gate for this delivery.
