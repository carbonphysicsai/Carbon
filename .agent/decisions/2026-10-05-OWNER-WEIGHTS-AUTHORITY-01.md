## 2026-10-05 — OWNER-WEIGHTS-AUTHORITY-01: no authorization-only weight blocks on testnet or mainnet; owner-coldkey winners on testnet

**Authority.** The owner, 2026-10-05.

1. **To PR Head, relayed to the Carbon Validator session:**

   > We don't need weight blockers anywhere for testnet or mainnet that is not
   > how you operate a subnet. I approve the merge, remove them!

2. **Confirmed directly in the Carbon Validator session.** The owner was
   asked what the mainnet follow-up should remove and chose "Authority blocks
   only". The option offered was:

   > Remove the refusals that exist only because winner weights weren't
   > authorized: winner_intent, the all-burn-only signing rule, the
   > unavailable winner issuer, and the testnet-only pins on the winner
   > publisher, so the same rule runs on mainnet. Keep the integrity checks:
   > snapshot and recipient drift, the integer-row guard, one publication per
   > epoch, no-resend reconciliation, and the owner-self-pay refusal.

3. **Then, in the same session:**

   > remove that owner coldkey rule for testing. I am not going to mine my
   > own subnet.

**Widens** OWNER-TESTNET-WEIGHTS-01 (testnet 567) to mainnet. It amends
OWNER-BATTERY-TESTNET-01 OD-6 for weight-setting validators.

### What is removed

- **The service key's winner refusals.** `battery.signing.winner_intent` no
  longer raises; it builds a winner-weight intent payload.
  `ServiceKey.sign` no longer refuses a weight intent that is not all-burn.
- **The winner publisher's testnet pins.** The rule and its publisher run on
  any network whose registered weight policy names it:
  - a policy names its network and netuid;
  - the standing authorization must match them;
  - the publisher checks the snapshot against the authorization.

  Mainnet needs:
  - its registered policy (its netuid and launch Challenge set are launch
    values, recorded when they are known);
  - a mainnet operator configuration.

  Neither is an authority block.
- **The owner-coldkey winner refusal, on testnet only.** On testnet, a winner
  whose coldkey is the subnet owner's is paid, so that Carbon's own miners can
  exercise winning.
  - A winner whose *hotkey* is an owner hotkey is still refused: weight sent
    to an owner hotkey burns.
  - On mainnet the coldkey refusal stays, as one of the integrity checks the
    owner chose to keep.

### What stays (integrity, not authority)

- snapshot, recipient and runtime drift refusals;
- the integer-row guard;
- one publication per epoch;
- no-resend reconciliation;
- the publisher-self-winner refusal;
- the mainnet owner-self-pay refusal;
- fixture provenance: localnet fixtures still cannot mint public or treasury
  intents (`rewards.intents`, invariant 9).

### Not decided here

- settlement and treasury routing (VALIDATOR-16; values HUMAN_INPUT);
- the mainnet netuid and launch Challenge set;
- security acceptance. The weight-setting and commitment paths still need
  their security review (AGENTS.md §13). The owner's approval was to merge,
  not a security sign-off.

### Implementation hold (the owner, the same day)

Two parts of this decision were held:
- the edit that makes the winner publisher and policy loader serve mainnet;
- the edit that switches on testnet owner-coldkey payouts in the winner
  publisher.

The session's automated safety check blocked them. The owner's answer:

> The block is fine and can stay

Both parts stay unimplemented until the owner lifts the hold. The decision
itself is unchanged.
