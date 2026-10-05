## 2026-10-05 — OWNER-TESTNET-WEIGHTS-01: lift the testnet winner-weight blockers; the winner-weight rule

**Authority.** The owner, 2026-10-05, in the Carbon Validator session. First:

> override any of the weight setting blockers. My approval. The is testing
> time now

Then, approving that this record be written and giving the rule:

> approve, the rule is new challenge winner gets all emissions for that
> challenge for 24 hours or until beat, after 24 hours it gets cut in half
> every 24 hours. That same miner resubmitting has to beat his old score by a
> factor that makes copying and changing 1 thing not work. The challenges all
> get 1/N with N being total challenges of the emissions.

**Amends** OWNER-BATTERY-TESTNET-01:
- OD-4b ("Not authorized yet; the winner issuer stays unavailable");
- OD-6 ("validators … never register or set weights").

The amendment covers testnet 567. It follows from
OWNER-VALIDATOR-MAINNET-PARITY-01 item 1.

### 1. Blockers lifted on testnet 567

- **Code refusals.** These winner-weight refusals become authority checks
  instead of refusals:
  - `battery.signing.winner_intent`;
  - `ServiceKey.sign`'s all-burn-only rule;
  - `rewards.intents.TestnetWinnerWeightIntent`'s unavailable issuer.
- **Per-publication approval** of each request digest (the OD-4a pattern).
  - One standing approval, this record together with the registered weight
    policy's digest, lets the publisher run every tempo.
  - Every publication is still journalled, recompiled against a fresh
    snapshot and reconciled on finalized blocks.

### 2. The weight rule

This supersedes OWNER-C0-REWARD-01's bounded-linear credit for these weights.

- **Per-Challenge share.** Each Challenge receives 1/N of the emissions, where
  N is the total number of Challenges.
- **Winner takes the Challenge's share.** A new Challenge winner receives all
  of that Challenge's share for 24 hours, or until beaten.
- **Halving.** After 24 hours, the share is cut in half every 24 hours: 1/2
  for the second day, 1/4 for the third, and so on. The rest of the
  Challenge's share burns to UID 0.
- **Beaten.** The new winner takes the full share, and its 24 hours start.
  "Beat" is the Challenge's own scientific promotion rule (battery: an
  IMPROVEMENT final on a fresh set, OD-2). A screening score alone never
  wins.
- **The same miner resubmitting** must beat its own previous score by a
  factor large enough that copying it and changing one thing does not
  succeed.
- **No winner.** A Challenge with no eligible winner burns its whole share.

### 2a. Two further owner directions, the same day

> any emissions not used in an epoch are burned, and I want the scores
> closest to 1 to be the best.

- **Unused emissions burn.** In every epoch, any emission not paid to an
  eligible winner burns to UID 0:
  - the decayed remainder;
  - Challenges without a winner;
  - the integer remainders.

  Nothing carries over to a later epoch, and nothing accumulates.
- **Scores run toward 1.** Every Challenge's published score is on [0, 1],
  where closer to 1 is better. This is the repository's ScorePack convention
  (`Design_Specs/Scoring.md` §6: legs on [0, 1], logistic tail transforms,
  geometric combination).
  - Battery, cooling and motor today publish raw mean errors, where lower is
    better. Each moves onto a [0, 1] score through its own registered score
    variant (VALIDATOR-09's registry).
  - That move is prospective. Evidence already scored keeps its rule
    (invariant 10).
  - The transform's parameters (thresholds, sharpness, weights) are pack-bound
    scientific values. They are proposed per Challenge, with measured
    behaviour, for the owner to adopt.
  - Promotion is unchanged: it stays each Challenge's own comparison.
  - The self-improvement factor (§3) is expressed on this score.

### 3. Values this record leaves for the build to measure and the owner to adopt

- **The self-improvement factor.** It is to be measured, never guessed:
  - perturb a winning construction by one registered step of each parameter;
  - measure the distribution of the resulting apparent improvement on fresh
    cases;
  - propose a factor above it.

  Until it is adopted, a same-miner promotion is not weight-eligible (fail
  closed).
- **"Same miner"** is measured on both the hotkey and its coldkey, so that a
  second hotkey cannot reset the factor.
- **N.** The Challenges registered in the weight policy. The current
  candidate set is the 8 launch Challenges (OWNER-LAUNCH-PORTFOLIO-02). A
  Challenge without a serving validator, or without a winner, burns its 1/N.
  Changing N is a new policy version.

### Unchanged

- mainnet;
- settlement and transfers;
- each Challenge's scientific promotion rule;
- miner keys, which Carbon never holds;
- the wallet password file, which is owner-read only.
