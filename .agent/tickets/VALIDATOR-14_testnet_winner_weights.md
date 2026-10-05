# VALIDATOR-14: testnet winner weights from validator outcomes, and the commitment reader

**Status:** design.

**Authority:**
- OWNER-VALIDATOR-MAINNET-PARITY-01 (2026-10-05):
  - item 1: real testnet weights from hidden-batch scores;
  - item 2: battery rule v2 in testing, with the on-chain commitment check.
- OWNER-TESTNET-WEIGHTS-01 (2026-10-05): the winner-weight blockers lifted on
  testnet 567 under one standing approval, and the owner's weight rule.

**Scope.** Testnet 567 only; mainnet stays unauthorized. Nothing transfers
funds.

**Executor:** the Carbon Validator session. Branch
`claude/validator-14-testnet-weights`, from main `e5491d2ca`.

## Where the code is today

- **The weight pipeline works on localnet only.** `rewards.core.targets`
  (bounded-linear, Q12) feeds `chain.publication.compile_targets`, then
  `chain.publisher.VerifiedWeightPublisher`, then `sdk_weights.guarded_weights`
  (`set_mechanism_weights` or commit-reveal).
- **Testnet 567 publishes all-burn only:**
  - `development_testnet.publication.DevelopmentTestnetPublisher`;
  - `battery.od4a_dispatch.BatteryAllBurnPublisher` (UID 0 burn).
- **OD-4b is refused in code:**
  - `battery.signing.winner_intent` raises;
  - `ServiceKey.sign` refuses a weight intent that is not all-burn;
  - `rewards.intents.TestnetWinnerWeightIntent` raises.
- **Battery results never reach rewards.** `daemon.py` says so ("Scientific
  results never become chain actions here").
- **OD-7 has no chain reader.** `BatteryValidator(commitments=...)` is a
  duck-typed seam, and `deployment.build` always passes None, so a deployment
  that requires a commitment refuses every submission
  (`commitment_reader_unavailable`).

## Design

**1. The commitment reader (OD-7):** `carbon/chain/commitments.py`.
- `ChainCommitmentReader.read(hotkey)` returns
  `{"digest", "block"}` for netuid 567 at a finalized block, using the
  existing read-only `sdk.BittensorReader`. It never signs.
- A missing or unreadable commitment keeps today's typed outcome:
  `commitment_required`, or `commitment_reader_unavailable` for
  infrastructure, never a candidate failure.
- The deployment configuration gains an optional `commitment_reader` block
  (network, netuid, endpoint). With it, `require_commitment: true` becomes
  servable.
- Miners post their commitment through their own signer, which is link-only;
  Carbon never holds a miner key.

**2. The eligibility event:** `TestnetWeightEligibilityEvent` (SPEC C2).
- It is derived only from the validator's own promotion: the incumbent set by
  a decided final on a fresh, consumed finalist set, or the first-incumbent
  rule. A screening score alone never makes anyone eligible (invariant 7.7).
- **Not eligible**, failing closed:
  - a promotion whose nomination score was taken on an overdue pool version
    (the Test Lead's ruling: overdue scores never enter a promotion claim);
  - Graphite development identities;
  - any `DEVELOPMENT_PUBLIC_ADAPTIVE` outcome;
  - a hotkey not in the metagraph snapshot (`MISSING`).
- Each event binds the final's id, the fresh set's fingerprint, the rule
  digest, the contract digest and the rebuilt artifact digest. The artifact
  digest is also the key settlement uses (VALIDATOR-16).

**3. The weight policy** (OWNER-TESTNET-WEIGHTS-01 §2): a registered,
digest-pinned document, `carbon/chain/weight_policies/testnet-winner-v1.json`.
The pure arithmetic lives in `carbon/rewards/winner_decay.py`.

- **Challenge shares.** `challenges` lists the N Challenges, and each gets
  `Q12 // N`. The integer remainder burns.
- **The winner's fraction of its Challenge's share:**
  - 1 for the first 24 hours after its promotion (finalized-chain time);
  - then `2^-k` from day k + 1, so 1/2 on the second day, 1/4 on the third,
    and so on (a step every 24 hours);
  - whatever is not paid burns to UID 0.
- **Being beaten** is the Challenge's own promotion rule (battery: an
  IMPROVEMENT final). The new winner's clock starts at its promotion.
- **`self_improvement_factor`: null (to be measured, §7).** While it is null, a
  promotion whose challenger shares a hotkey or coldkey with the incumbent it
  beat is not weight-eligible. The incumbent keeps its own decaying share.
- **No winner,** or a Challenge without a serving validator: its whole share
  burns.
- **`cadence_blocks`:** one tempo (360), the chain's own value.

**7. Measuring the self-improvement factor** (an engineering measurement; the
owner adopts the value).
- For a winning construction, generate every one-registered-step perturbation
  of one parameter (the contract's own vocabulary).
- Score each against the original on the same fresh cases with the
  Challenge's final comparison.
- Report the distribution of the apparent relative improvement, and propose a
  factor above its upper tail.
- Development data only, never a sealed set.

**4. Signing.**
- `signing.winner_intent` is implemented. `ServiceKey.sign` accepts a winner
  weight intent only when it binds:
  - the registered policy digest;
  - the eligibility event digest;
  - the owner record id (OWNER-TESTNET-WEIGHTS-01);
  - netuid 567.
- Anything else is refused as before. The all-burn path is unchanged.

**5. Publication.** `TestnetWinnerPublisher` wraps the network-parametric
`VerifiedWeightPublisher` and `BittensorPublicationBackend`.
- It is pinned to network `testnet` and netuid 567, with UID 0 as burn.
- It recompiles against a fresh snapshot, journals through `DispatchJournal`
  and reconciles on finalized blocks, as it does today.
- The operator's validator wallet is opened by file path
  (`open_operator_wallet`). Starting the signer stays a human step.

**6. The attack side (Test Engineer).** A `weight_channel` family: an
adversary that sees only on-chain weights and its own outcomes, measured for
how much hidden-pool information it recovers across tempos.

## Tests (DEVELOPMENT; synthetic snapshots and a scripted chain backend, no
network)

- Commitment reader:
  - a match admits;
  - a mismatch or a missing commitment is refused with today's codes;
  - reader failure is infrastructure.
- Eligibility:
  - only a decided-final or first-incumbent promotion is eligible;
  - an overdue-nominated, development or missing holder is refused.
- Policy arithmetic:
  - each Challenge gets 1/N;
  - the fraction is 1 until 24 h, then 1/2, 1/4, …;
  - a new winner resets the clock;
  - no winner burns;
  - the remainders burn;
  - same miner: not eligible while the factor is null.

  The registry pins the digest.
- Signing: a winner intent signs only with all its bindings, and an all-burn
  intent is byte-unchanged.
- Publisher: refuses mainnet, a netuid other than 567, and a drifted snapshot.
  The scripted backend receives exactly the compiled u16 row.

## Open values (null, fail closed, until adopted)

1. **The self-improvement factor** (§7). It is measured first, then adopted by
   the owner.
2. **N's membership.** The candidate is the 8 launch Challenges
   (OWNER-LAUNCH-PORTFOLIO-02). With only battery serving, battery's
   1/N share is paid and the other 7/8 burns.

## Maturity ceiling

IMPLEMENTED and TESTED (DEVELOPMENT) on scripted chains. A live testnet
publication is an operator step under the owner's record. This is not a
security audit.
