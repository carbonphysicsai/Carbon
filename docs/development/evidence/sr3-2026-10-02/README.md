# SR-3 results (2026-10-02): margin error near the decision boundary

**Class.** Public synthetic DEVELOPMENT evidence. It follows its
pre-registration (`docs/development/BATTERY_SCORING_RATIOS_SR3.md`, commit
`a05947a9`, before any `n` was computed). It is offline on EV2's 15 verified
prediction files, with no spend and no testnet rule changed. "Near" is the
published important region (OWNER-SR3-NEAR-01): 311 of 1,588 scoring cases.

## Outcome: NO_PROMOTION, and `STUCK` fires

Chosen on EV2 development conditions: `sr3-a0.1-r0.1-g0.8-n0`, the same
profile SR-2 chose. It gives no weight to `n`.

| Pre-registered check (EV2) | Result |
|---|---|
| Catches the boundary optimist | yes |
| Fewer divergence conditions on verification | no: 4 against 3 |
| Verification Δτ at least 0 | no: -0.133 |
| Δτ interval's lower end above minus the band (0.260) | no: -0.668 |

SR-1, SR-2 and SR-3 are three consecutive studies without progress. The
amended §4.2 trigger **`STUCK`** fires: a full Track B review
(`.agent/DECISIONS.md`, TRACK-B-STUCK-01).

## What it shows

1. **`n` sharpens the safety signal.**
   - The boundary optimist overstates near-limit margins by **2.41 bands**,
     against 1.60 over all cases in SR-2.
   - The real MLPs overstate them by 0.58-0.97, kNN by 3.1-4.2, and the
     oracle by 0.
2. **It tracks decisions worse, not better.**
   - `n` alone has a verification τ of 0.177, against `m`'s 0.243 and `g`'s
     0.309. Every difference is UNRESOLVED.
   - The best profiles that give `n` weight reach a verification τ of 0.199.
3. **The pattern across SR-1, SR-2 and SR-3 is the finding.**
   - On EV2, development and verification disagree about which rule is best.
   - The deciding rule is worst on development (τ 0.114) and best on
     verification (0.420).
   - Decision agreement is the reverse (0.366 against 0.309).
   - With 14 eligible members and a τ noise band of 0.26, selection on
     development does not transfer to verification.
   - **The limit is the evidence, not the formula.** Further formula search
     on EV2 cannot settle anything.

## Recommendation to the review

1. **Rerun SR-1, SR-2 and SR-3 on EV4's 99 members** before any new formula.
   - Regenerate EV4's 100 prediction files on the EV4 pod path and verify
     them against `docs/development/evidence/ev4-2026-10-01/predictions.sha256`.
   - Estimated cost: about USD 1-3 of pod time, inside OWNER-TRACK-A-L0-02's
     USD 25 cap.
   - The selection rules are already frozen in the three pre-registrations.
2. **Then freeze the best candidate** and confirm it once, on fresh
   conditions, in EV5: the first combined admission run.
3. **Meanwhile, keep the safety half separate.** Any of the 27 SR-1 ratios
   that catch the boundary optimist can serve as an admissibility check.
   This follows OWNER-ADMISSION-COMBINED-01's separate verdicts. It is not a
   ranking rule and needs no new formula.

## Limits

- EV2's panel is small, and its verification conditions are published.
- This is development evidence only. The EV4 replication is `NOT_RUN`.
