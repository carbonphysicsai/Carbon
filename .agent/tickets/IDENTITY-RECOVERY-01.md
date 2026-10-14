# IDENTITY-RECOVERY-01 — Preserve winner identity across predecessor deregistration

**Status:** implementation in progress, testnet 567 DEVELOPMENT only.
**Starting base:** `408552f39bbcb90ed553d6575e267abc2800eb64` (current `origin/main` at ticket start).
**Authority:** `OWNER-TESTNET-WEIGHTS-01` §3 defines the same miner by hotkey or coldkey; `OWNER-VALV2-WEIGHTS-01` §5 says a same-hotkey or same-coldkey promotion never resets the clock. `VALIDATOR-14` records that current behavior. This ticket repairs an implementation lag; it does not select a new weight policy.

## Working contract

- KEEP the validator's promotion and existing append-only winner ledger. REPAIR the coldkey comparison where the previous hotkey has disappeared from the current finalized snapshot.
- New ledger records freeze the winner's coldkey when present in the finalized snapshot. A later promotion may use that recorded identity only for its matching predecessor model. The challenger identity comes from the current finalized snapshot.
- Existing v1 records remain byte-for-byte historical evidence. A v1 predecessor may use its old hotkey's current snapshot association while that hotkey remains present. A v2 predecessor uses only its frozen coldkey; a v2 record without one cannot later acquire historical identity from a new snapshot. When the applicable predecessor coldkey cannot be established, refuse with a typed identity-unavailable error before appending a record or creating an intent. Do not infer a reset, payment, or burn disposition for that unknown historical identity.
- Preserve the current same-miner clock, distinct-miner reset, overdue-pool refusal, absent-winner withholding, preview, and once-only observation semantics. With no registered public baseline, a new deployment's `FIRST_INCUMBENT` must also compare against an existing Challenge ledger winner: the same hotkey or frozen coldkey keeps its earlier clock; a distinct miner follows the existing first-incumbent rule; unknown historical identity refuses.
- A registered public baseline makes a new deployment's `FIRST_INCUMBENT` unchecked. With an existing Challenge ledger winner, the current authority supplies no safe cutover disposition. Refuse this path before ledger append or intent creation. With no prior ledger winner, retain the existing ineligible first-incumbent result. Do not inherit eligibility for an unchecked new model.

## Bounded file scope and evidence

- `carbon/rewards/winner_eligibility.py`: prospective identity field and fail-closed comparison.
- `tests/cpu/test_reward_winner_eligibility.py`: predecessor-disappears same/different coldkey, cutover first-incumbent same/different miner, legacy missing-identity refusal, and append-only checks.
- `carbon/rewards/testnet_winner_publication.py` and `tests/cpu/test_reward_testnet_winner_publication.py`: carry the bounded identity refusal through preview/issue and prove it stores no intent or signs anything.
- `.agent/decisions/2026-10-14-IDENTITY-RECOVERY-01.md`: durable prospective schema and legacy refusal decision.

Validation is held under the current OPERATOR gate. Before engineering delivery, run the focused reward tests and applicable canonical scope checks on the unchanged candidate head. No chain execution, signing, payout, clock-policy change, historical record mutation, LIVE claim, or qualification is in scope.

**Maturity ceiling:** IMPLEMENTED, then TESTED only after authorized canonical checks pass. Scientific, security, network, economic, and production qualification are not claimed.

**Historical limit:** A v1 predecessor that has disappeared has no frozen coldkey in the ledger. An actual affected record requires authoritative historical identity evidence or an owner disposition before its promotion can be classified. This ticket leaves that promotion unrecorded and refuses publication; it does not repair old decisions or backfill the ledger.

**Owner decision reserved:** For a Challenge with a registered public baseline and a retained ledger winner, define how a new deployment's unchecked first incumbent is handled and what evidence preserves or replaces the old winner. The affected cutover remains typed `BASELINE_CUTOVER_UNRESOLVED`; null-baseline identity recovery is independent and remains in scope.
