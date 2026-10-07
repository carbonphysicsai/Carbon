# MOTOR-QUIZ-01: motor quiz and tuning definitions (DRAFT for owner approval)

**Status.** A DRAFT for the owner to approve for testing (the Test Lead's request, 2026-10-07).
- Challenge-neutral: it follows `carbon/battery/value/quiz.py`'s interface (Q2 near-limit, Q3 decision tasks, the same measures and UNRESOLVED treatment).
- Anything not already recorded is marked **HUMAN_INPUT** with a recommended value.
- DEVELOPMENT only.

## Recorded inputs this draft uses

- **Limits** (OWNER-GRAPHITE-TEST-WAVE-01 §6, `MOTOR_SYNTHETIC_DECISION_V2.json` → scenario): mean torque ≥ **4.0 N·m**, ripple fraction (peak-to-peak / |mean|) ≤ **0.30**.
- **Decision rule** (study V2, `carbon/motor/decision_study.py` and `track_b.py`):
  - one fixed geometry is evaluated at six commanded operating conditions: r01–r04 REPRESENTATIVE and b01–b02 BOUNDARY_STRESS;
  - it is feasible when every condition meets both limits;
  - the objective is the worst-condition ripple fraction, with ties to higher mean torque;
  - abstain if nothing is predicted feasible.
- **Stratum:** current density J ≥ 10 A/mm² (the recorded stratum, M3).
- **Solver cost per point (GetDP, pinned image).**
  - Counted campaign (48 cases, 2 CPUs each): wall times of 767 / 1,366 / 1,886 s (min / median / max). That is 33.1 allocated core-hours, or **about 0.7 core-hours per point** at the median.
  - Calibration p95: 1,500 s on the host, 921 s on cpu5c.

## Q2: near-limit cases

- **Measures** (`quiz.q2_measures` shape):
  - false-feasible: of reference-infeasible cases, the share called feasible;
  - torque false acceptance: of reference torque FAILs, the share called PASS (the analogue of battery's plating);
  - false-infeasible.
- **Near-limit band.** **HUMAN_INPUT.** Motor has no committed reference uncertainty band.
  - **Recommended:** within 10 % of either limit on either side, i.e. |mean − 4.0| ≤ 0.4 N·m or |ripple fraction − 0.30| ≤ 0.03.
  - **Recommended in parallel:** a mesh/step-refinement repeatability study, to replace this with a measured band before any rule v3 adoption.
- **UNRESOLVED.** Until a band exists, the reference call is exact, there is no UNRESOLVED state, and the feedback is labelled "no uncertainty band applied". This is the PRACTICE-SAFETY-01 ruling.
- **Selection: HUMAN_INPUT.** Recommended: panel disagreement (as battery Q2) once the motor public panel has at least 10 members. Until then, a random draw from the near-limit pool. Today's motor panel is too small for disagreement to discriminate (analytic, KRR and the four Q1 controls).
- **Sizes: HUMAN_INPUT.** Recommended: a pool of **48** solved cases (the near-limit share is unknown until solved, so the pool is reference-solved first) and a quiz of **24**. Battery's 320/80 would cost about 225 core-hours per batch here. 48 solves is about 34 core-hours.

## Q3: decision tasks

- **Scenario: HUMAN_INPUT.** Recommended: 8 candidate geometries drawn from the private root over `INPUT_BOUNDS` (seeded, hidden), each evaluated at the six recorded conditions under the V2 decision rule above.
  - The geometry space is 6-D, so a lattice like battery's is impractical. The registered finite candidate set plays the lattice's role.
  - Draws must stay off V2's eight public designs (refused within the separation distance below).
- **Cost: 8 × 6 = 48 GetDP solves per scenario, about 34 core-hours.**
- **k: HUMAN_INPUT.** Recommended **k = 2**, about 68 core-hours per batch. Raise k only with a cost decision (k = 8 would be about 270 core-hours).
- **All-infeasible scenarios** are redrawn (battery's v5 rule), and the redraw count is recorded.
- **Separation: HUMAN_INPUT.** Recommended: a candidate geometry is refused if every coordinate lies within 5 % of its range of a V2 design.

## The tuning set

- **Size and strata: HUMAN_INPUT.** Recommended: 60 per-case points, 30 drawn with J ≥ 10 (the recorded stratum) and 30 uniform over `INPUT_BOUNDS`. Plus Q2 (24 from a pool of 48) and Q3 (k = 2). That is about 60 + 48 + 96 = 204 solves, roughly 140 core-hours, solved once at the seal.
- **Decision value** for score tuning: the counted V2 study's decisions (public, already solved). Q3's scenarios stay disjoint from it.

## Known-bad controls (by behaviour, as for battery)

| Control | Behaviour |
|---|---|
| boundary optimist | near either limit: reports mean +0.5 N·m and ripple × 0.8 (optimistic); accurate elsewhere |
| localized sign error | within 0.4 N·m of the torque limit: reflects the mean about the limit |
| near-limit cautious | the optimist's mirror: rejects near-limit feasible designs (over-caution, value control) |
| infeasible edge-seeker | where the truth is infeasible but near a limit: reports just passing |

Known-good: the oracle and the counted study's feasible deciders. The constructed magnitudes above are **HUMAN_INPUT** (recommended as shown).

## Owner decisions needed (all HUMAN_INPUT)

- the near-limit band;
- Q2 selection and sizes;
- the Q3 scenario form, k and separation;
- the tuning-set size and strata;
- the control magnitudes.

The cost driver is GetDP at about 0.7 core-hours per point. Battery's sizes don't transfer.
