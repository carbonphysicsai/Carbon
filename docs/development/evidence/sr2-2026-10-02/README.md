# SR-2 results (2026-10-02): the margin-aware component

**Class.** Public synthetic DEVELOPMENT evidence. It follows its
pre-registration (`docs/development/BATTERY_SCORING_RATIOS_SR2.md`), and the
pre-registration and code were committed before the run. It is offline on
EV2, whose 15 prediction files were verified against their committed
digests. No spend, and no testnet rule changed.

## Outcome: NO_PROMOTION

Chosen on EV2 development conditions: `sr2-a0.1-r0.1-g0.8-m0`. It gives
**no weight to the new leg**.

| Pre-registered check (EV2) | Result |
|---|---|
| Catches the boundary optimist | yes |
| Fewer divergence conditions on verification than the deciding rule | no: 4 against 3 |
| Verification Δτ point estimate at least 0 | no: -0.133 (τ 0.287 against 0.420) |
| Δτ interval's lower end above minus the τ noise band | no: [-0.664, +0.374] against band 0.260 |

## What it shows

1. **The leg measures what it was built to measure.**
   - The boundary optimist overstates safety margins by **1.60 bands** on
     average, against 0.50 to 0.72 for the real MLPs.
   - The oracle scores `m` = 1.0. The conservative control shows the mirror
     image: 0 bands of optimism and 8.9 of pessimism.
   - The kNN members are worst on margins: 3.1 to 3.9 bands of optimism.
2. **Averaged over the whole scoring set, it does not track decision
   quality.**
   - `m` alone has a verification τ of 0.243, against `g` alone's 0.309
     (Δ -0.066, UNRESOLVED).
   - No profile that gives `m` weight is chosen on development conditions.
   - The best such profiles reach a verification τ of 0.22 to 0.27.
3. **Why, as I read it.** A decision turns on a few cases near the designs
   a model selects. The mean over 1,588 cases dilutes exactly those cases,
   and accuracy-style averaging repeats the problem SR-1 found.
4. **Next.** Margin error weighted toward the decision boundary. Defining
   "near the boundary" needs a value the contract does not yet hold, and it
   goes to the science lead before use.

## Limits

- EV2 has 14 eligible real members; its τ noise band is 0.26, so every
  difference here is weak.
- The EV4 replication is `NOT_RUN`: its predictions are not retained.
- This counts toward `STUCK`: 2 of 3. SR-1 was the first.

## File

`results.json` holds every profile's τ, optimist check and divergence
counts, `m` for each member, both paired bootstraps, and the results digest.
