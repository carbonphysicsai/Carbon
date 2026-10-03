# Challenge pools on rented CPU pods, 2026-10-02

The cold plate's and motor's **public** pool cases (TRAIN and PRACTICE) were
solved natively on RunPod CPU pods. The private pools ran only on the
owner's host.

- **Owner approval.** 2026-10-02, in session: "Go", for RunPod, public pools
  only, with a fixed cap. That cap is the `challenge-pools` campaign
  ceiling, held in the operator's configuration, not in the repository.
- **Ticket:** `.agent/tickets/CHALLENGE-POOLS-CLOUD-01.md`.

## What ran

The pod receives only a public plan, and code fetched by hash at a pushed
ref.
- `pod_phase.py` refuses any plan that carries a root commitment or a
  private batch name, and so does `pod_control.py dispatch-cpu`.
- No private root, seed or case reached rented compute.

| Run | Plan | Code ref | Cases | Outcome | Pod wall time per case, p50 / p95 |
| --- | --- | --- | --- | --- | --- |
| Cold plate smoke | `plans/cold-plate-smoke.json` | an earlier head of this branch | 2 | 2 OK | 241 s / 242 s |
| Motor smoke | `plans/motor-smoke.json` | an earlier head of this branch | 2 | 2 OK | 893 s / 913 s |
| Cold plate TRAIN remainder | `plans/cold-plate-train-remaining.json` | `7f0dfbb87ba04c76cd7b5fb5bb37f479dd3dca2b` | 308 | 308 OK | 284 s / 331 s |
| Motor public remainder (TRAIN and PRACTICE) | `plans/motor-public-remaining.json` | `ed4a8f911d0cece019122ff7c289099b62ea8be3` | 149 | 149 OK | 1,058 s / 1,504 s |

Notes on the runs:
- **Concurrency.** The full runs used 16-vCPU pods with 16 concurrent cases,
  so these wall times include contention.
- **Not reference-hardware measurements.** They are not timings on reference
  hardware in the Challenge Roadmap's sense, and do not enter the priority
  queue (OWNER-CHALLENGE-ROADMAP-01).
- **Execution record.** Every case record carries its `execution`
  environment:
  - **Cold plate:** the pinned OpenFOAM image, run natively.
  - **Motor:** the pinned Ubuntu base, replaying
    `scripts/dev/motor/reference/Dockerfile` (snapshot 20260930T000000Z;
    GetDP 3.5.0 and Gmsh 4.15.2, SHA-256 checked).

## Native execution agrees with the container

The smoke cases were also solved on the owner's host, in the pinned
containers. Comparing every output of the same cases:

- **Motor:** 2 of 2 bitwise identical.
- **Cold plate:** largest absolute difference 1.7e-13 K. This is analysis
  round-off; the solver fields are identical.

`scripts/dev/challenge_pools/assemble.py` refuses to assemble two OK records
of one case that disagree beyond 1e-9 relative.

## Assembly

Each pool is the first N cases of its plan, in the plan's draw order, taken
from every run that solved them:

| Pool | Cases | From the owner's host | From the pod | Missing |
| --- | --- | --- | --- | --- |
| Cold plate TRAIN | 400 | 92 | 308 | 0 |
| Cold plate PRACTICE | 100 | 100 | 0 | 0 |
| Motor TRAIN | 150 | 26 | 124 | 0 |
| Motor PRACTICE | 30 | 5 | 25 | 0 |

All 680 cases are OK. The assembled pools are committed with each
Challenge's baselines (cold plate and motor slice 4).

## Accounting

The campaign ledger stays on the owner's host. It records account balance
fields, and this repository is public. Both pods were terminated and their
termination verified, leaving no pod running. Spend stayed within the
owner's cap.
