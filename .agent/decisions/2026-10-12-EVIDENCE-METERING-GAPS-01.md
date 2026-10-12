# EVIDENCE-METERING-GAPS-01 — development comparison measurements

- **Ticket:** optimizer queue OPT-10, development evidence only. Base: merged
  `main` at `88dba0221` when work began. Primary historical map ref:
  `WAVE-C/EVIDENCE-CAMPAIGN-RUNNER-01`; the Development Hub is retired, and
  this measurement repair changes neither its placement nor maturity ceiling.
- **Scope:** measure a warm Carbon inference over every candidate and condition
  in each registered decision question, retaining per-question timings in the
  pinned model receipt. Pair those times with the producer's measured serial
  complete-panel reference wall times only where both sides cover the same
  questions. Do not turn one batched inference into per-question latency by
  division.
- **Cost boundary:** stage CPU totals cannot be assigned to physical rows
  without a per-solve meter. Existing battery and motor raw records lack that
  measurement; their cost ledgers keep `core_s: null`, and equal-budget public
  replay remains fail closed where measured CPU is required. A wall-time speed
  receipt cannot unlock the flagship CPU-hour allowance.
- **Motor boundary:** the registered reference export covers the holding
  question. Peak/skew observables for the full question need a registered motor
  kit and cheap comparator, with Data Collection's matching producer evidence.
  This ticket records that gap; it does not invent peak values or run a solver.
- **Invariants:** no hidden or sealed material, no solver runs, no paid compute,
  no scientific threshold/qualification change, no model-choice tuning on the
  held-out panel. All measured claims bind the development export identity;
  absent evidence stays `INSUFFICIENT_EVIDENCE`.
- **Acceptance:** synthetic fixture tests for complete-question timing,
  identity/inventory refusal and cost pairing; Carbon-arm and campaign
  regressions; canonical CI on the exact PR head.

## Exact-source readiness binding

The first PR CI run found that the three committed public readiness source
indexes pin `carbon_arm.py` byte-for-byte. This ticket changes those bytes, so
the battery-v3, motor and f02 item-4 pins were rebound to the new file digest
in this same reviewable PR. Their `finding` and `missing` text did not change;
each still reports `UNKNOWN` until actual panel/TRAIN coverage evidence exists.
The pin refresh is an identity repair, not a readiness or qualification claim.
