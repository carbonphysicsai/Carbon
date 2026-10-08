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
