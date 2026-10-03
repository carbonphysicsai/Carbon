# SR-1 results (2026-10-02): battery scoring ratios on retained EV results

**Class.** Public synthetic DEVELOPMENT evidence. It follows its
pre-registration (`docs/development/BATTERY_SCORING_RATIOS_SR1.md`, committed
before the run). It is offline, with no spend, and it changes no testnet
rule.

## Outcome: NO_PROMOTION (pre-registered rule, §6)

Chosen on EV4 development conditions: **`sr-a0.5-r0.1-g0.4`**. That is 0.5 on
accuracy, 0.1 on important-region robustness and 0.4 on decision agreement,
combined by Carbon's weighted geometric mean.

| Pre-registered check | Result |
|---|---|
| Catches the boundary optimist on EV4 and EV2 | **yes**: 0 of 99 (EV4) and 0 of 14 (EV2) real members at or below it |
| Fewer score-value divergence conditions than the deciding rule, EV4 verification | **no**: 7 against 7 |
| EV4 verification Δτ point estimate at least 0 | yes: +0.009 (τ 0.412 against 0.403) |
| Δτ interval's lower end above minus the τ noise band | yes: [-0.053, +0.076] against band 0.178 |

The paired Δτ uses B = 10000, seed 20261002, 99 members and 12 conditions,
and is UNRESOLVED. One check fails, so the profile is not promoted.

## What it shows

1. **Catching the optimist costs nothing in ranking.**
   - 27 of 66 profiles score the boundary-optimist control below every real
     model on EV4.
   - The chosen one ranks real models no worse than the deciding rule on
     EV4 verification: τ 0.412 against 0.403.
   - Decision agreement alone (`sr-a0-r0-g1`, the earlier proposal) is far
     worse: τ 0.262.
   - The failure EV2 and EV4 reported can be fixed by re-weighting.
2. **The divergence among real models is not fixed by re-weighting these
   three legs.**
   - On EV4 the deciding rule fires 34 conditions on development and 7 on
     verification. The best admissible profile fires 33 and 7, and no
     admissible profile fires fewer than 7 on verification.
   - So real models still score at or above models that decide better, by
     more than the seed-noise band, under every ratio of accuracy, important
     region and decision agreement.
   - Re-weighting these legs cannot remove that. A rule that fixes it needs
     information they do not carry: margin-aware or worst-case decision
     error, or calibrated uncertainty near the limits.
3. **Replication is mixed.**
   - On EV2's smaller panel the chosen profile also catches the optimist and
     fires fewer development conditions (6 against 8).
   - Its EV2 verification τ is lower (0.376 against 0.420), within EV2's own
     wide band.

## Limits

- EV2's and EV4's verification conditions are published, and 66 profiles
  were tried. This is development evidence, not confirmation.
- The boundary optimist is a constructed control, not evidence about real
  models' generalization.
- The study counts toward the §4.2 `STUCK` trigger: 1 of 3.

## File

`results.json` holds every profile on EV4 and EV2:
- τ on development and verification;
- the optimist check;
- divergence counts by split;
- the chosen profile's paired bootstrap;
- the τ noise band;
- the results digests.
