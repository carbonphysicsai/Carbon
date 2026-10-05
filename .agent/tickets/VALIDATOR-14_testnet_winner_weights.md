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

## Build record

1. **The rule.** `rewards/winner_decay.py` plus `weight_policies/` (pinned by
   digest).
   - testnet-winner-v1: 3 Challenges, per-Challenge `baselines` null, the
     factor null.
2. **The commitment reader.** `chain/commitments.py`, with a deployment
   `commitment_reader` block.
   - A chain failure is `commitment_reader_unavailable`.
3. **Eligibility.** `rewards/winner_eligibility.py`: `battery_promotion`,
   `decide` and an append-only owner-only `WinnerLedger`.
   - Promotions are recorded once, at the first finalized time observed.
   - An overdue-nominated promotion pays nobody.
   - The same miner (hotkey or coldkey) never resets its clock.
4. **Publication.** `rewards/testnet_winner_publication.py`, made up of
   `StandingAuthorization`, `TestnetWinnerIntentIssuer`,
   `TestnetWinnerPublisher`, and the operator `run` command (one epoch per
   call).
   - It inherits the shared checked publisher.
   - It adds the block window, netuid 567, burn UID 0, the policy digest, one
     publication per epoch, and a refusal when the targets change.
5. **The factor study.** `rewards/self_improvement_study.py`: one-step
   neighbours and the measured distribution.
   - It produces a proposal (`PROPOSED_NOT_ADOPTED`). Running it on battery is
     the next step.

**Design changes from the draft**
- **No service-key signing.** The publisher reads the validator state
  read-only on the operator host, so `signing.winner_intent` stays refused and
  unused.
- **Same-miner promotions never reset the clock** until checking the factor
  against a measured gain is built.

**Kept on purpose: the shared compiler's owner-associated-winner refusal.**
- A winner whose hotkey or coldkey is the subnet owner's
  (`OWNER_ASSOCIATED_WINNER_WOULD_BURN`) still refuses the publication.
- Carbon's own testnet miners need a coldkey that is not the owner's to win
  weights.

**Validation (canonical)**
- The new tests (decay, eligibility, commitments, publication, study) pass.
- The battery deployment, daemon, service, intake, adapter, OD-4a dispatch,
  C-W1 testnet and reward core and ledger suites pass unchanged.
- `scripts/check_quality.py --base origin/main`: passed.

**Maturity.** IMPLEMENTED and TESTED (DEVELOPMENT) on scripted chains. It is
not security-reviewed (AGENTS.md §13). A live publication is an operator step
under the standing authorization.
