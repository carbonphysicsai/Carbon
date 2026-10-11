# VALIDATOR-15: lift the authorization-only weight blocks

**Status:** implemented. The held parts were lifted by
OWNER-WEIGHTS-HOLD-LIFT-01 (2026-10-08) and built on
`agent/weights-mainnet`.

**Authority:** OWNER-WEIGHTS-AUTHORITY-01 (2026-10-05).

**Executor:** the Carbon Validator session. Branch
`claude/validator-15-weights-authority`, stacked on #646 (VALIDATOR-14).

## Implemented

- **`battery.signing`.**
  - `winner_intent` builds a registered winner-weight intent payload instead
    of raising.
  - `ServiceKey.sign` signs the all-burn intent and the registered winner
    intent, and refuses any other weight-intent shape (`ValueError`).
- **`chain.publication.compile_targets`** gains `allow_owner_coldkey_winner`,
  default False, behind `VerifiedWeightPublisher.ALLOW_OWNER_COLDKEY_WINNER`.
  - An owner *hotkey* winner is refused regardless.
  - Every existing publisher keeps today's behaviour.
- **Docstrings and tests** that asserted OD-4b's refusal now assert the new
  registered shapes:
  - `daemon.py` and `od4a_dispatch.py` docstrings;
  - `test_battery_validator_daemon.py` and `test_battery_od4a_dispatch.py`.
- **Kept, as integrity:** `rewards.intents`'s reserved families. Localnet
  fixtures still cannot mint public or treasury intents (invariant 9).

## Formerly held, now implemented (OWNER-WEIGHTS-HOLD-LIFT-01)

The owner had said "The block is fine and can stay". The owner lifted the
hold on 2026-10-08 ("Lift both held parts", confirmed directly).

- **`winner_decay.load_policy` and `testnet_winner_publication` serve any
  network a registered policy names** (`NETWORK_AUTHORITIES`):
  - testnet 567;
  - mainnet `finney`, under OWNER-WEIGHTS-AUTHORITY-01 only.

  The authorization, the policy and the snapshot must name the same network,
  netuid and record (`POLICY_NOT_FOR_THIS_NETWORK`, `NETWORK_NOT_AUTHORIZED`).
  A mainnet intent is `mainnet-winner-…`, `PUBLIC_MAINNET`,
  `MAINNET_OWNER_AUTHORIZED`; testnet intents are unchanged.
- **`ALLOW_OWNER_COLDKEY_WINNER` is on for the testnet winner publisher** and
  off on mainnet.
- **Still needed for a mainnet run (fail closed):**
  - mainnet's registered policy (netuid, launch Challenges);
  - a mainnet operator configuration (the operator loader is the
    development testnet's);
  - the owner's standing authorization file.

## Validation (canonical)

These suites pass:
- `test_battery_validator_daemon.py`
- `test_battery_od4a_dispatch.py`
- `test_reward_testnet_winner_publication.py`
- `test_cw1_development_testnet.py`
- `test_net4a_intents.py`
- `tests/invariants/test_net4a_intent_boundary.py`

`scripts/check_quality.py --base origin/main`: passed (recorded in the PR).

## Maturity

IMPLEMENTED and TESTED (DEVELOPMENT). Not security-reviewed (AGENTS.md §13).
