## 2026-10-05 — OWNER-VALIDATOR-MAINNET-PARITY-01: real testnet weights, the v2 rule in testing, fair shared conditions, settlement now

**Authority.** The owner, 2026-10-05, in the Carbon Validator session,
answering its four chain and economic questions. The Test Lead declined these
as reserved for the owner (AGENTS.md §14).

> yes on 1 and 2. for 3 the competition has to be fair, everyone has to be
> scored on the same conditions with the same solver results... 4. now

**Supplements** the owner's testnet = mainnet parity direction of 2026-10-04,
and the same day's instruction that testing must operate like mainnet ("There
is no point in this testing if it's not operationally relevant!").

1. **Real testnet weights from hidden-batch scores.** Yes.
   - Testnet weights are set from validator outcomes on hidden batches, using
     the testnet 567 identities.
   - Weights are public, so they are a feedback channel. An attack family
     measures what a miner can learn from weights alone.
   - Signing stays where the miner-setup rules put it: keys by file path
     only, and the wallet password file is owner-read only.
2. **Mainnet's scoring rule (battery rule v2) in testing.** Yes.
   - One scored submission per hotkey per tempo.
   - Rotation by finalized block.
   - The on-chain commitment check.
   - Hidden-batch results sealed from miners (OWNER-BATTERY-3B-AND-EXPOSURE-01).
3. **Fairness across validators.** Every participant is scored on the same
   conditions, with the same solver results. Every validator therefore uses
   the identical hidden cases and the identical reference (solver) results;
   no validator draws or solves its own.
   - How those cases and results are distributed while staying hidden is the
     engineering design that follows. It must keep every validator's
     conditions identical, and the leak of a single validator is an attack the
     design has to measure.
4. **Settlement.** Build it now.
   - Its policy values are not set by this record and stay HUMAN_INPUT, fail
     closed: amounts, shares, emission split, treasury addresses and any
     transfer.
   - Settlement refuses development public-adaptive evidence, and keys each
     entitlement on the rebuilt construction's artifact digest.
   - Nothing moves funds without a further owner record.

5. **Rotation cadence, release and batch composition.** The owner added, the
   same day:

   > only caveat on rotation is that it will vary based on how expensive the
   > data generation is. Some will be way less often that 3 submissions. They
   > goal is to find an optimal cadence, publish the retired data, and fill
   > the new batch with spots in the envelope that are showing to be most
   > important

   - **Cadence is per Challenge,** set by what its data generation costs. It
     can be far rarer than every 3 submissions. The goal is a measured optimal
     cadence, not a fixed count.
   - **Retired batches are published** into the training data, which is the
     release path OWNER-BATTERY-3B-AND-EXPOSURE-01 names
     (`CARBON_COMMIT_TO_TRAINING_POOL`) and which does not exist yet.
   - **New batches are filled toward the regions of the envelope** shown to
     matter most.
   - **Constraint carried forward** (scientific invariant 7.2): steering where
     new cases are drawn (the proposal `Q(x)`) must not silently change the
     population the score claims (`P(x)`). Either the score weights cases back
     to `P(x)`, or the Challenge's registered population names the
     stratification. Which one, and each Challenge's importance signal, are
     scientific values for the Challenge's owner. They stay HUMAN_INPUT until
     recorded.

**Not decided here:** any numeric economic value, mainnet deployment, or
security acceptance.
