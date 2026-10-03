# CHALLENGE-POOLS-CLOUD-01 — solve public challenge pools on rented CPU pods

**Status:** in progress.
**Primary Hub map_ref:** `SYSTEM/AGENT-EXECUTION`, `HUB_UPDATE_REQUIRED`.
**Authority:**
- OWNER-CHALLENGE-DESIGN-01;
- the owner's grant of 2026-10-02 ("Go": RunPod, public pools only, a
  fixed cap);
- OWNER-CHALLENGE-ROADMAP-01 ROADMAP-D1 (in-flight slices finish and are
  recorded);
- OWNER-DX-03.

**Tracking:** carbonphysicsai/Carbon#342 (cold plate), #344 (motor).

## Outcome

The cold plate's and motor's public TRAIN and PRACTICE cases are solved on
RunPod CPU pods, with no change to what a case is. On the owner's host the
pools would have taken days; on the pods they finished in about 1.5 hours.
- Each batch runner gains a native mode (`--native ENVIRONMENT`). It runs
  the same pinned commands without Docker, in its own process group, killed
  whole on timeout. Each record names its execution environment.
- `pod_control.py dispatch-cpu` launches one CPU pod per public plan. The
  pod has:
  - hash-pinned code at a pushed ref;
  - the campaign's ledger, cap, balance floor and watchdog;
  - a pod image named by tag and digest. For the motor, it replays the
    reference Dockerfile's pinned steps.
- `assemble.py` builds each pool from every run that solved its cases. It
  refuses disagreeing duplicates and reports missing cases.

## Working decisions

- **POOLS-D1. Native on the pod, not Docker-in-pod.**
  - RunPod pods cannot run Docker. The pod therefore is the pinned image:
    the OpenFOAM image itself, or the motor's pinned base with its
    Dockerfile's steps replayed and SHA-256-checked.
  - Agreement with the container was measured before the full runs: motor
    bitwise; cold plate 1.7e-13 K, analysis round-off.
- **POOLS-D2. Private pools never leave the owner's host.** Two refusals
  guard this, and a test covers both:
  - the dispatcher refuses any plan with a root commitment or a private
    batch name;
  - the pod phase refuses the same again.
- **POOLS-D3. The ledger stays local.** It records account balance fields,
  and the repository is public. The evidence README records what ran, the
  code refs, the counts and the agreement, without spend figures.
- **POOLS-D4. Pod wall times are not reference timings.** They are recorded
  as provenance only, and do not enter the challenge pipeline's queue
  (OWNER-CHALLENGE-ROADMAP-01).

## Definition of done

- `tests/cpu/test_challenge_pools_cloud.py` passes. It covers:
  - native exit codes and process-group timeouts;
  - each Challenge's native command path;
  - refusal of private plans;
  - the motor pod replaying exactly what its Dockerfile pins;
  - assembly order and preference, missing cases, and refusal of
    disagreeing duplicates.
- The evidence README records the runs, the agreement and the assembly.
  Both pods were terminated and verified.
- Black, ruff, hygiene and the hub pass.
