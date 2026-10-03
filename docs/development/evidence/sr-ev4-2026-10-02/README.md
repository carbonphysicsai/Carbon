# SR-2 and SR-3 on EV4's 99 members (2026-10-02, OWNER-EV4-REGEN-01)

**Class.** Public synthetic DEVELOPMENT evidence. No testnet rule changed.

## Predictions

- **Regeneration.** EV4's panel predictions were not retained, so they were
  regenerated.
  - Run: EV4's own plan at EV4's code ref `b92e90ef`, on one A40 pod
    (`ev4-regen` campaign, with its own ceiling).
  - 100 of 100 members written, in 24 minutes; spend is in the operator's private ledger.
  - Pod termination verified (`docs/development/evidence/ev4-regen-2026-10-02/accounting/ledger.jsonl`).
- **Verification by content.**
  - Byte digests cannot match, because each file carries wall-clock fields.
  - Instead, each member's exam components (E, E_important, decision score,
    eligibility) were recomputed from the regenerated file and compared with
    EV4's committed results. **All 100 match exactly.**
  - The runners' `--verify content` mode enforces this per member.

## Pre-registered outcomes: NO_PROMOTION for both

| Study | Chosen on EV4 development | Optimist caught | Verification τ (deciding 0.403) | Δτ [95%] | Divergence conditions, verification (deciding: 7) |
|---|---|---|---|---|---|
| SR-1 (already on EV4) | `sr-a0.5-r0.1-g0.4` | yes | 0.412 | +0.009 [-0.053, +0.076] | 7 |
| SR-2 | `sr2-a0-r0.3-g0.6-m0.1` | yes | 0.420 | +0.017 [-0.072, +0.091] | 10 |
| SR-3 | `sr3-a0-r0-g0.8-n0.2` | yes | 0.390 | -0.013 [-0.124, +0.083] | 10 |

The τ noise band on EV4 verification is 0.178. Each study fails one or two of
its four checks. Each fails on the divergence count, and SR-3 also on the
sign of Δτ. They are not promoted.

## What the larger panel shows

1. **EV2 was too small to compare legs; EV4 is not.**
   - On 99 members the margin legs rank models much better than decision
     agreement, the opposite of EV2:
     - `m` alone: τ 0.388;
     - `n` alone: 0.366;
     - `g` alone: 0.262.

     `m` against `g` is Δ +0.126 [-0.188, +0.277], UNRESOLVED.
   - `m` alone does not catch the optimist (26 real members at or below it).
     The chosen profiles do.
2. **Nothing beats the deciding rule at ranking real models beyond noise.**
   - The best is SR-2's chosen profile: τ 0.420 against 0.403.
   - Every Δτ interval contains 0.
3. **The divergence count is the wrong instrument for "real-model
   divergence".** The deciding rule's 7 verification conditions are:
   - 2 constructed controls: the boundary optimist and the localized sign
     error;
   - 3 kNN members scoring at or above other kNN members or the
     conservative control;
   - 2 real non-kNN members (`deeponet_t1500_w512_d3-s0`,
     `mlp_t3000_w256_d3_arr_pca16-s0`), each scoring at or above three
     25%-TRAIN MLPs that decide better by more than the loss band.

   A rule that catches the optimist removes its condition but reorders other
   near-ties, so the count stays at 7-10. The pre-registered criterion
   counts controls and kNN self-ordering together with real-model
   divergence, so it cannot show a real-model improvement.

## Recommendation to the TRACK-B-STUCK-01 review

These are proposals; the reviewers decide.

1. **Separate the two jobs.**
   - **Ranking.** The deciding rule is not beaten beyond noise on 99
     members. Keep it, unchanged.
   - **Admissibility.** Add a separate gate that a predictor overstating
     safety margins near the limits fails: the boundary-optimist failure.
   - This is OWNER-ADMISSION-COMBINED-01's separate-verdict shape. It needs
     its own pre-registered threshold. The threshold is a science value
     (`n`'s optimism in bands), and it goes to the science lead.
2. **Fix the instrument prospectively.** Future studies report divergence
   among real members separately from constructed controls, and within a
   family separately from across families. This applies prospectively only;
   no result here is rescored.
3. **Confirm once in EV5**, on fresh conditions:
   - the deciding rule plus that gate;
   - the SR-2 candidate, as a comparator.
