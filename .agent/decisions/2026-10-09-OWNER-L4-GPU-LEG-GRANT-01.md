## 2026-10-09 — OWNER-L4-GPU-LEG-GRANT-01: a capped GPU run of the Level 4 B′ leg

**Authority.** The owner, 2026-10-09, in the Test Lead session. Replying to
the Test Lead's "approve Level 4 GPU leg, own grant $3", the owner said, as
relayed verbatim to the Level 4 engineer session:

> Approve … 4

The Test Lead proposed it as its own grant because the A40 acceptance grant's
remaining cap is taken by the parity run's worst case. Recorded by the Level 4
engineer session.

**Decision.**

| Field | Value |
|---|---|
| Purpose | The A40 harness's Level 4 B′ leg only (#874; `level4/PHASE1_PLAN.md` §3). JAX pods; per pod, each trained recipe's native repeats and one B′ rebuild, plus the forward-only kNN |
| Platform | RunPod, NVIDIA RTX 4090, 1 GPU per pod, through the harness's operator layer |
| Pods | 2 concurrent, plus at most 2 replacements (one relaunch each, for a GPU-less host or a mismatched driver) |
| Rate ceiling | USD 0.95 per pod-hour |
| Deadline per pod | The smoke's measurement × 1.5 (the harness's rule). The CPU-measured upper bound is about 0.71 h |
| Smoke | 1 pod on the largest pick, with the leg, before the run (the harness's own deadline, 0.75 h) |
| **Monetary cap** | **USD 3.00**, including the smoke, every replacement and the cleanup allowance |
| Runs | 1 |
| Model spend | none |

**The cap binds through the harness.** Its budget gate refuses the run unless
the following, at USD 0.95 per hour, fits under USD 3.00:

> (2 pods + 2 replacements) × the measured deadline + the smoke pod's
> reservation + the 0.25 cleanup allowance

On the CPU timings that is 2.70 + 0.71 + 0.25 = 3.66, which does not fit, so
the run proceeds only if the GPU smoke measures a deadline under about
0.54 h. If it does not fit, the run is refused: nothing is spent past the
smoke, and a new grant is needed.

**Entry conditions.** The run launches only when all of these hold:
- this record is on main;
- the 4090 parity run's results are in (Test Lead, 2026-10-09);
- #874 is on main, with the B′ documents committed and pinned in a sealed run
  record (`select --level4`);
- the harness supports a JAX-only real run, so no PyTorch pods are launched
  under this grant.

**Not decided here.**
- Any tolerance: acceptance is digest equality, reported descriptively, and a
  mismatch is a recorded R1 finding.
- Any Level 4 live run. That still needs the owner's and the security owner's
  permission.
- Any other device class.

**No execution** happens through this record. Spend is booked privately,
never in the repository.
