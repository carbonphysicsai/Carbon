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

All 24 runs were OK. Per-case figures, raw-record hashes and the timeout
outcome are in `result.json`. Quantiles use linear interpolation over the 12
cases.

| Route | CPU | Batch wall | Per case p50 / p95 / max |
| --- | --- | --- | --- |
| Operator host, Docker | Intel Core i7-12700H, 20 threads | 2,885 s | 1,404 / 1,500 / 1,505 s |
| `runpod-cpu5c-16vcpu`, native | AMD Ryzen Threadripper 7960X, 16 vCPU | 1,821 s | 898 / 921 / 924 s |

- **Timeout.** Two times the host p95 is 3,000 s. That is within the
  registered 3,600 s, so the counted campaign runs study V1 as registered.
  No new study version is needed.
- **Pairing.** The host takes 1.54–1.63 times as long as cpu5c per case.
  Each host case allocates 2 CPUs, so its cost is reported in core-seconds.
- **Agreement.** All 12 torque curves are bitwise identical between the
  container route and the native route.
- **Earlier, slower figures.** The TRAIN pool's 3,000–3,640 s for these same
  geometries were run 16 at a time. The motor pilot's p95 included the
  2,880-node refinement mesh. The study uses the 1,440-node mesh at 6 at a
  time.

## Pod attempts

1. The first pod failed at import, because `CPU_SHIP` lacked
   `carbon.design_search`. This PR fixes that. The pod was terminated within
   minutes.
2. The second pod, at code ref `14a15511`, completed at 18:36Z. A monitoring
   fault left it idle until it was terminated at about 21:07Z, still inside
   the campaign cap. The lessons entry
   `2026-10-04-motor-timing-calibration` records this.
