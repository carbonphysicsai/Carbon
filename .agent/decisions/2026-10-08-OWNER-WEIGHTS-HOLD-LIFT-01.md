## OWNER-WEIGHTS-HOLD-LIFT-01: the mainnet winner publisher and testnet owner-coldkey payouts are implemented

**Authority.** The owner, 2026-10-08:
- to PR Head, relayed to the Carbon Validator session: "Remove mainnet too";
- **confirmed directly in the Carbon Validator session**, asked whether to lift
  OWNER-WEIGHTS-AUTHORITY-01's implementation hold ("The block is fine and can
  stay"). The owner chose **"Lift both held parts"**, whose description read:

  > Also switch on testnet owner-coldkey payouts in the winner publisher
  > (your earlier "remove that owner coldkey rule for testing"); mainnet keeps
  > the coldkey refusal.

  It was offered beside "Lift mainnet only", which generalizes the winner
  publisher and policy loader to any network a registered weight policy names
  (finney included), keeping the mainnet coldkey refusal and every integrity
  check; mainnet sets nothing until its policy (netuid, launch Challenges) and
  operator configuration are registered.

**Lifts** the implementation hold recorded in OWNER-WEIGHTS-AUTHORITY-01. That
decision is unchanged; this record only lets its two held parts be built.

### What is implemented (VALIDATOR-15, held parts)

1. **The winner publisher and policy loader serve any network a registered
   policy names** (`winner_decay.NETWORK_AUTHORITIES`):
   - testnet 567, under OWNER-TESTNET-WEIGHTS-01 or OWNER-WEIGHTS-AUTHORITY-01;
   - mainnet `finney`, under OWNER-WEIGHTS-AUTHORITY-01 only.

   The rule is the same on both: the decay, the 360-block cadence, burn UID 0,
   and the policy digest pinned in the registry.
2. **Testnet pays a winner whose coldkey is the subnet owner's**
   (`ALLOW_OWNER_COLDKEY_WINNER`, testnet only), so that Carbon's own miners
   exercise winning.

### What stays

- **On mainnet, the owner-coldkey winner refusal.**
- **On both networks:**
  - the owner-hotkey refusal (weight sent there burns);
  - snapshot, recipient and runtime drift refusals;
  - the integer-row guard;
  - one publication per epoch;
  - no-resend reconciliation;
  - the publisher-self-winner refusal;
  - the standing authorization's block window and record digest.
- An authorization never crosses networks: the testnet record never
  authorizes mainnet, and a policy must name the authorization's network,
  netuid and record.

### Not decided here (fail closed)

- **Mainnet's registered weight policy:** its netuid and launch Challenge set
  are launch values; there is no mainnet policy in the registry, so mainnet
  publishes nothing.
- **A mainnet operator configuration:** the publisher's operator loader is the
  development testnet's, which accepts testnet only. A mainnet run is refused
  there until a mainnet operator configuration exists, which is an engineering
  follow-up, not an authority block.
- **The owner's mainnet standing authorization file,** naming this record's
  authority.
- **Security acceptance** of the weight-setting path (AGENTS.md §13).
- **Settlement and treasury routing** (VALIDATOR-16; values HUMAN_INPUT).
