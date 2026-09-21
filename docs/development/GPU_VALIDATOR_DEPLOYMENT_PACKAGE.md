# Work package N: make a validator deployable, and establish scale

Authority is `GPU_DETERMINISM_WORK_PACKAGE.md` on `agent/gpu-execution-lane-design`
(PR #248). **Read Amendment 3 first - it governs where earlier clauses conflict**,
and the pointer at the top of that file says so. Do not act on the withdrawn E3
median fallback, and do not implement an aggregator.

Implementation head when this was written: `376e7763` on
`agent/core-platform-19-gpu-lane-split`.

---

## Already done. Do not redo any of it

Verify against the branch before starting; if something below is further along
than this says, trust the branch.

| Item | State |
| --- | --- |
| D1 numerics record | IMPLEMENTED and TESTED. Records effective ISA, XLA flags, TF32 and cuBLAS controls, device facts. Schema v3/v4 to v5/v6, both readable. |
| D2 determinism configuration | IMPLEMENTED and verified against jaxlib 0.10.2 in the pinned image. Cost recorded: about +1.0 s compile, +63%. |
| D3 same-device determinism | **CHARACTERIZED.** Unpinned, four sessions produced four weight digests. Pinned, three sessions produced one. Nine runs, one answer. |
| D4 validator policy | Written and reconciled with Amendment 3. |
| D5 gate robustness options | Written, none implemented, reconciled. |

Nothing above is QUALIFIED. Keep SPECIFIED, IMPLEMENTED, TESTED, CHARACTERIZED
and QUALIFIED distinct in everything you write.

---

## N1. Unpin the cpuset

`carbon/reconstruction/worker/docker_runtime.py:459` still rejects any allocation
that is not exactly cores 0 and 1:

```python
if (cpuset != "0,1" or ...):
    raise WorkerFailure(WorkerCode.INVALID)
```

`CPU_COUNT = 2` and `MEMORY_BYTES = 4 GiB` are unchanged, and `:788` also compares
an observed cpuset against an eligible set - reconcile both paths, not just the
create path.

This is the defect class the portability work already removed for device
identity. `HostDeviceRecord` and `require_host_device()` are the pattern. Resolve
the allocation from the host; do not replace one hardcoded constant with another.

The consequence that matters most for a validator: **two concurrent
reconstructions are impossible today**, because both demand the same two cores. A
validator scoring a queue is serialised by a string literal.

Free. No device, no attempt, no spend.

## N2. Does the usable core count change the weights?

**This gates N1's sizing and N3's workload choice. Run it early.**

W3 established that `OMP_NUM_THREADS` at 1, 2, 4 and 8 leaves weights unchanged,
because these operations do not go through the OpenMP or BLAS pools, and that
XLA's Eigen threading *mode* does change them. It never varied **Eigen's
thread-pool size**, which tracks the cores actually available to the process.

> Does the number of usable cores change `checkpoint/state.npz`?

If it does, core count joins the declared execution class and a validator cannot
be sized freely - a significant constraint, and better known now than discovered
after an envelope is published. If it does not, validators can be given whatever
the host has.

Vary the container's actual CPU allocation, not just an environment variable, so
the pool genuinely sees a different core count. Record intended, effective and
observed settings separately, as D1 does.

CPU only, free, no device. Apply the same question to the memory ceiling and to
two simultaneous in-class runs on one host.

## N3. Widen the step-count fixture so scale can be measured

Every determinism result so far - W3, W5 and the GPU characterization - is on
**two training steps and 4,696 parameters**. The GPU evidence says so itself: a
larger workload exercises reduction sizes and op mixes this one does not, and
could behave differently.

The C-02 compile fixture pins the step count to 2 through both its parameter
domain and its static resource table. Widening it is a deliberate fixture change,
which W3 correctly declined to make inside a measurement.

Make that change properly, as its own piece of work with its own tests. It
unblocks every question about realistic scale, including the margin rule in W5,
which currently has only a floor from the shortest possible run.

Free. It is a fixture and test change, not a measurement.

## N4. The validator deployment path

The owner asked for this to be as easy and efficient as possible for a validator.
Today it is inferable from source and nowhere written down.

Two pieces, because the worker does not score - it has no scoring imports, it
reconstructs and exports an artifact, while A5 scoring is dependency-free float64
outside the container:

| Piece | Needs | Envelope |
| --- | --- | --- |
| Reconstruction | GPU, pinned image, declared execution class | from N2 and N1 |
| Scoring | no GPU, no accelerator libraries | negligible |

Write the operator sequence end to end: prerequisites, check the host, obtain and
verify the image, run a reconstruction, score it, recover from an interruption.
`carbon_accelerator.py` already has `doctor`, `status`, `run`, `cancel` and
`recover`; what is missing is the documented path through them.

**No host grant, no exclusivity, no admission ceremony.** The strict apparatus
stays out of the validator lane as it stays out of the miner lane. State the
Docker daemon requirement and the driver build from the declared class honestly.

Free.

## N5. Propose the next device experiments, then stop

**No new GPU run, rental or paid call follows from this package.** P7 still
requires the evidence specification, explicit attempt and repeat counts, and owner
and domain acceptance. Prepare; do not spend.

Three experiments to specify, in priority order:

1. **Localization on one device.** Stages 1 and 2 of the staged design, which the
   same-device work skipped by going straight to full reconstructions: replay
   from a saved state with no training, then first updates only. These say
   *where* divergence enters, which the existing result does not.
2. **Representative workload, same device.** Repeat the D3 characterization at the
   scale N3 unblocks. Whether pinned determinism holds at realistic reduction
   sizes is unknown, and it is the assumption the policy currently rests on.
3. **Matched two-host test.** Two actual same-class physical devices, not two
   container configurations and not two names for one device. This is the
   milestone the whole exactness strategy rests on and nothing to date touches
   it.

For each, state: the finite coverage, invocation and repeat counts, elapsed-time
and output limits, what would count as a failed run worth not repeating, and the
required acceptance. Batching repeats inside one admission economises admissions
only - every other envelope limit still applies, so give the full resource
profile.

For the two-host test additionally: an actual available host, device and
partition, host and CPU-side conditions, exact software, and all-in costs
including provisioning, download, setup, idle and cleanup. **Make no comparative
cost claim without a quote.**

Compare at every layer the divergence passes through - numerical state,
predictions, the physical measurements a Score Pack consumes, gate outcomes, and
the ranking between candidates. Include several admissible strategies, not one
convenient baseline: two devices may agree on a reference model and still favour
different submissions, and repeated runs of one baseline cannot see that. State
what difference the study could have detected; a study that could not have found
a decision-changing effect has not ruled one out.

---

## Rules that do not bend

1. **Exact stays exact.** R0 identities, schemas, provenance, artifact byte
   integrity. Only repeat-execution numerics admit a registered tolerance.
2. **Never choose a tolerance** to make hardware agree.
3. **Never relabel B as A.** A fresh reconstruction is its own artifact.
4. **Do not erase device or run identities** to make a cross-host comparison
   pass, and do not relax an R0 check for it. Class identity and per-run identity
   are different things.
5. **A mismatch is an incident with cause unestablished.** Diagnose it; never
   average it away and never select a favourable repeat.
6. **Do not widen `ScoreStatus`**, and never record an execution incident as a
   mandatory physics failure to fit the closed enum.
7. **Protected material stays off this path**, invariant test holding.
8. **Do not build on the strict host apparatus.**
9. Do not edit a worktree while a suite or experiment consumes it.
