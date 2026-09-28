# Battery OD-4a dispatch adapter: scope

**Status.** SECURITY-SENSITIVE (AGENTS.md §13).
- It is **implemented only for review. It is NOT REVIEWED, NOT merged on
  green, and no dispatch may use it** until dedicated review accepts it.
- **Building it authorizes nothing.** A fresh request (0003), a fresh owner
  approval of that exact digest, and review must all come first.
- OD4A-BATTERY-0002 lapsed unused at 2026-09-28T11:50:07Z by owner decision.

## Why it is needed

The only weight publisher (`carbon/development_testnet` over
`carbon/chain/sdk_weights`) takes a CW1 source handoff. It has no input for a
battery service-signed weight intent. Nothing at dispatch reads the approved
OD-4a request (`carbon/battery/od4a.py`).

Several approved bindings are enforced nowhere at dispatch today:

| Approved binding | Where it stands today |
|---|---|
| The approved intent's digest | not checked at dispatch |
| `request_digest` | not tied to the authority record |
| The signing key | `signing.verify` checks the signature against the key embedded in the envelope; it proves no *trusted* key signed it |
| netuid 567 | checked only when the request is built; `load_config` accepts any netuid |
| `expires_utc` | no wall-clock check |
| UID 0 | not literal: the sink is the observed owner UID |
| The probe's surface digest | not rechecked |

## What already exists and is reused, not re-implemented

In the shared publisher (`chain/publisher.py`, `development_testnet/publication.py`,
`chain/sdk_weights.py`):
- one dispatch per authorization (the consumption binding, and one pending
  dispatch);
- the block window, rechecked before signing;
- fee 0 and spend 0 (the SDK policy);
- the testnet genesis check;
- the runtime spec;
- mechanism 0;
- the publisher hotkey and wallet identity, with only the hotkey signing;
- no automatic resend (reconcile to finalized state).

## What the adapter adds

1. **An approved-publication value that can only be constructed by
   verification.** This follows enforce-by-construction. Its constructor
   loads the request, the owner approval record, the signed intent and the
   trusted service key id, and **refuses unless every check passes**:
   - the request digest recomputes;
   - the approval record names that exact `request_digest`, and its own file
     digest is the `authority_record_digest`;
   - the intent envelope's digest equals the request's `source_intent.digest`;
   - the intent verifies **and** its `key_id` equals the pinned trusted key id,
     so it is not self-certified;
   - the payload is exactly the Phase A all-burn intent, as accepted by
     `signing._is_all_burn`;
   - netuid 567 and the testnet genesis;
   - the weights row is exactly `[[0, 65535]]`;
   - `max_dispatches` 1 and fee and spend 0;
   - the block window;
   - `expires_utc` is in the future.

   A raw dict, or an intent that is valid but not approved, cannot stand in
   for it.
2. **A battery issuer and intent type** beside the CW1 pair. The issuer stores
   the verified envelope in the publication journal and resolves an all-burn
   projection (burn at Q12, no challenges, no winners).
3. **A battery publisher** (a `DevelopmentTestnetPublisher` subclass). Its
   `validate_stage` adds, at every stage and again before signing:
   - that the resolved envelope's digest equals the approved digest;
   - netuid 567;
   - the sink UID is 0;
   - wall-clock expiry.
4. **An operator command**, `python -m carbon.battery.od4a_dispatch
   status|run|resume`. `status` and `resume` open no wallet. `run` opens the
   publisher hotkey only, through the existing external-wallet path.

## Boundaries (the point of the ticket)

- **All-burn only.** `signing.sign()` and `winner_intent()` are left exactly as
  they are. The adapter routes what they permit and never widens it.
- **OD-4b stays unauthorized.** No winner path and no parameter that could
  carry one.
- **The adapter is not authority to dispatch.** It refuses without an approval
  record matching the exact request.
- **It cannot dispatch an unapproved intent.** Enforced by construction and
  tested with an intent that is valid but not approved, and with an altered
  one.
- **Signing stays external.** Carbon holds no private key, seed or mnemonic.
  The coldkey is not read, copied, moved or decrypted; only the public coldkey
  address is compared, as today.
- **Testnet 567 only.** No mainnet path, now or anticipated.
- **The C-W1 path changes only additively.** `DevelopmentTestnetPublisher`
  names its issuer and intent types as class attributes, so the battery
  publisher can subclass it and inherit every check. It gains one refusal: an
  authorization bound to a source intent is refused on the C-W1 path, and an
  unbound one is refused on the battery path. So neither authorization can
  publish through the other. `DevelopmentTransactionAuthorization` gains
  `source_intent_digest`, which defaults to None, so existing configurations
  load unchanged.

## As implemented (NOT REVIEWED)

- `carbon/battery/od4a_dispatch.py`: `ApprovedPublication`,
  `BatteryAllBurnIntentIssuer`, `BatteryAllBurnPublisher`, and the CLI
  `verify|run|resume`.
  - `verify` reads no wallet and makes no chain call.
  - `run` verifies every offline binding before it reads the chain or opens
    the publisher hotkey.
  - `resume` only reconciles a dispatch already made. It opens no wallet and
    never signs, so it may run after the expiry. `resume` needs no probe.
- **The trusted service key is pinned by its full public key in the source.**
  Rotating the key is therefore a reviewed code change.
- **Tests:** `tests/cpu/test_battery_od4a_dispatch.py`. The structural
  refusals, each run beside the approved case as a positive control:
  - a validly signed but unapproved all-burn intent is refused;
  - a tampered intent is refused;
  - a self-consistent intent from an untrusted key is refused;
  - there is no constructor except verification;
  - an altered or forged journal row is refused.

  Other tests cover each binding, testnet 567 only, cross-path authorization
  refusal, expiry rechecked just before signing, a row other than UID 0, the
  inherited block window, and one dispatch.
- **What is not tested here:** a real chain. The adapter reuses the checked
  SDK backend unchanged, and no transaction was sent while building it.

## Sequencing against M4

PROGRAMME_STATE row 4 (the OD-4a approval just before dispatch) depends on M4
(the GPU backend and the two-host run), which has not started. **That does not
change the adapter's sequencing.** The adapter is dispatch mechanics,
independent of M4. What M4 gates is **whether a publication should happen at
all**: the owner's approval of a fresh request. So the order stays:

1. adapter;
2. review;
3. M4 and the owner's go;
4. request 0003;
5. owner approval;
6. a single dispatch.
