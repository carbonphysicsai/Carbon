# Training budget study grants

Each grant binds one Challenge's study pod spend (TRAINING-BUDGET-01). The
grant file uses the standard spending-grant schema
(`carbon.agent-campaign.spending-grant.v1`). The study's own limits sit beside
it in `<grant>.limits.json`, because the standard schema has no fields for
them:
- a rate cap per pod-hour;
- the 80% pause;
- the re-estimate after Phase A.

The study's pod runner (slice 2c) binds both files. It refuses a run the
grant does not cover, and it pauses, or stops, at the limits.

## TRAINING-BUDGET-GRANT-BATTERY-STUDY-01

**Superseded by -02 (2026-10-08). It is not spendable:** the sheet's spend
ceiling is -02's, so a runner that binds the sheet and a grant refuses -01.
Its figures below are kept as recorded.

**Authority:**
- The owner approved the grant on 2026-10-07: "approve study grant USD 31.54".
  The Test Lead relayed it, and the owner confirmed it directly in the Test
  Engineer's session.
- The sheet's values come under the owner's "team proposes all rows, I approve
  it for testing" (OWNER-BATTERY-STUDY-SHEET-01).

**Arithmetic** (an estimate, not a measurement; no battery rebuild has been
timed on an A40):

| Item | Count | Seconds each | Hours |
|---|---|---|---|
| Phases A-G, including a B repeat if R9 moves D | 682 rebuilds | 120 | 22.7 |
| Phase H, about 100 configurations × 6 fractions × 3 seeds | 1,800 rebuilds | 60 | 30.0 |
| Overhead (pod start-up, infra retries under 10%, R6 re-runs): +15% | | | 7.9 |
| Total, rounded up | | | **64** |

    64 h × USD 0.492739726 per hour = USD 31.54 (the ceiling)
    80% of 31.54 = USD 25.23 (the pause)

Generation (TRAIN up to 3,200 cases, eval 200, confirmation 120) runs on the
producer host at no pod cost.

**Limits:**
- **Rate cap:** one A40 pod at no more than USD 0.492739726 an hour. The rate
  covers the EV4 tooling's USD 0.49 plus 20 GB of container disk. A pod
  offered above the cap is refused.
- **One pod at a time.** Nine runs (A, B, C, F, G, the possible B repeat, D, E
  and H), each at most 34.5 h. The largest run, H, has a worst case of USD
  17.00; cleanup is USD 0.25.
- **Pause at USD 25.23.** Report to the Test Lead before continuing (the
  spec's stop rule).
- **Re-estimate after Phase A.** Runbook step 6 replaces the 120 s and 60 s
  estimates with Phase A's measured times. If the new estimate exceeds the
  ceiling, the study stops before Phase B.
- **Not production.** The grant funds only the testing study under a
  testing-only sheet.

## TRAINING-BUDGET-GRANT-BATTERY-STUDY-02

**Authority:** the owner approved it directly in the Test Engineer's session
on 2026-10-08: "I approve the TRAINING-BUDGET-01 study on RTX 4090: cap USD
34.80, pause at USD 27.84, re-issued as grant -02". The move from the A40 came
first (the owner, relayed by the Test Lead): RunPod could not allocate an A40,
and Vast listed none. Decision OWNER-BATTERY-STUDY-4090-01.

**Rates:** Vast's public offers on 2026-10-08, verified hosts, on demand, one
GPU:
- **RTX 4090 (24 GB):** 31 offers, median USD 0.456 an hour.
- **A100 (80 GB):** 7 offers, about USD 0.87-1.19 an hour.

**Arithmetic** (an estimate, not a measurement; no battery rebuild has been
timed on a 4090):

| Item | Count | Seconds each | Hours |
|---|---|---|---|
| Phases A-G, including a B repeat if R9 moves D | 682 rebuilds | 120 | 22.7 |
| Phase H, Level 0 | 1,800 rebuilds | 60 | 30.0 |
| Phase H, Level 1-4 recipes (about 10 configurations × 6 fractions × 3 seeds) | 180 rebuilds | 60 | 3.0 |
| Overhead: +15% (55.7 h becomes 64.1 h), rounded up | | | **65 (4090)** |
| Run S: the A100-80 memory leg (8 FNO cells over 20 GiB × 3 seeds, at full TRAIN), +15%, rounded up | 24 rebuilds | 300 | **3 (A100-80)** |

    65 h × USD 0.48 = USD 31.20
     3 h × USD 1.20 = USD  3.60
    ceiling          USD 34.80
    80% of 34.80   = USD 27.84 (the pause)

**Limits:**
- **Rate caps, verified hosts only:**
  - one RTX 4090 at no more than USD 0.48 an hour, disk and bandwidth
    included;
  - for run S only, one A100 80 GB at no more than USD 1.20 an hour.
  - An offer above its cap is refused.
- **Each leg is bound by its own pod-hours.** One pod at a time.
- **Ten runs:** A, B, C, F, G, the possible B repeat, D, E, H and S.
  - The largest, H, runs at most 38 h, with a worst case of USD 18.24.
  - Cleanup is USD 0.25.
- **Pause at USD 27.84.** Report to the Test Lead before continuing.
- **Re-estimate after Phase A,** as for -01. The 4090's fp32 rate is about
  twice the A40's, so the estimate is expected to fall.

**Blocked until set:**
- **The image.** The sheet's `image_digest` is HUMAN_INPUT until
  worker-images-v3 is released, because v2's PyTorch GPU image fails every
  FNO rebuild (#826).
- **The study seed root** (#738).
- **The pod runner.** Slice 2c must bind provider `vast`.
- **Level 1-4 recipes** enter Phase H only once TRAINING-BUDGET-02 (#806)
  prices them.

**Not production.** The grant funds only the testing study under a
testing-only sheet.
