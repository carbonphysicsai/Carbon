# Motor timing calibration, 2026-10-04

These are non-counted timings of public motor TRAIN geometries. They feed two
decisions:
- the per-case timeout of the counted motor decision campaign
  (CHALLENGE-MOTOR-03);
- the priced unit for its equal-cost view (OWNER-GRAPHITE-TEST-WAVE-01 §5).

**Authority:** OWNER-DATA-MOTOR-01, `.agent/decisions/2026-10-04-OWNER-DATA-MOTOR-01.md`.

## Plan

`plans/motor-timing-calibration.json` has 12 cases. `selection.json` records
the rule, fixed before any solve:
- take the 6 OK, default-mesh TRAIN records with the largest recorded wall
  time;
- exclude any geometry equal to one of the 8 study designs;
- run each geometry at the study's boundary-stress conditions:
  - b01: 15 A/mm², 0°
  - b02: 12 A/mm², 30°

The rule is deliberately conservative towards the slow tail.

The same plan runs twice, once on each route:

| Route | Backend | Concurrency | Image or environment |
| --- | --- | --- | --- |
| Operator host (i7-12700H, 20 threads) | Docker, `--cpus 2` | 6 | `ghcr.io/carbonphysicsai/carbon-motor-reference@sha256:599521e7…c1c05` |
| `runpod-cpu5c-16vcpu` | native (motor D10: native equals container) | 6 | pinned Ubuntu base replaying the motor Dockerfile; CPU model in the pod's setup log |

## Boundaries

- Public TRAIN geometry only. No private-pool case, seed or commitment
  reaches rented compute. `pod_phase.py` and `dispatch-cpu` both refuse
  private plans.
- These timings are not decision evidence. They never enter the counted
  comparator, and they are not qualification.
- This repository holds provenance only: plan, code ref, wall times, CPU
  models. The account balance and spend stay in the operator's private
  ledger.

## Results

Not run yet. The operator-host run waits for a host window agreed with the
Graphite Test executor.
