# Carbon Operations vNext Reconciliation

**Status:** OWNER-RECOMMENDED operations overlay; current `Operations.md` remains the runtime operations manual until implementation migration.  
**Purpose:** Extend operations from direct lean-eval scoring to qualified Challenge, promotion, and treasury settlement without conflating scientific and economic failure states.

## 1. Operational job classes

Future operations should distinguish at least:

```text
challenge_authoring / qualification
lean_eval
frontier_promotion
reconstruction_repeat / audit
reference_backend
landscape_batch
bank_retrain
product_battery
treasury_governance
treasury_settlement
```

A `lean_eval` produces scientific evidence. It does **not** automatically create a payout.

## 2. Scientific state and payout state are separate

Scientific state examples:

```text
REJECTED_INVALID
FAILED_INFRA
SCIENTIFIC_INADMISSIBLE
INDETERMINATE_EVIDENCE
VALID_RANKED
SUPERIOR
NOT_SUPERIOR
FRONTIER_ADVANCE_CONFIRMED
```

Settlement state examples:

```text
NO_EVENT
PAYOUT_PROPOSABLE
PAYOUT_PENDING_GOVERNANCE
PAYOUT_QUEUED
PAYOUT_TIMELOCKED
PAYOUT_EXECUTABLE
PAYOUT_PENDING_INFRA
PAID
CANCELED_WITH_REASON
EXPIRED
```

An operations incident may move settlement state without mutating scientific state.

## 3. Challenge health

Operators should monitor exact qualified Challenge identities:

- distribution / SamplingPlan version;
- generator digest;
- ReferencePolicy/backend digest;
- MeasurementContract versions;
- Validation Dossier digest/status;
- Score Pack digest;
- backend profile;
- FrontierBaseline / incumbent identity;
- LeaderReplacementPolicy;
- ChallengeSetEpoch membership.

Any material mismatch blocks authoritative execution or settlement.

## 4. Reference backend health

Do not assume one universal SciML service is required by every Challenge.

Each Challenge declares its reference dependencies. A reference outage produces explicit reference/infra state and retry/quarantine behavior. It must not be converted into candidate physics failure.

## 5. Promotion-exam operations

Frontier promotion is its own scheduled scientific job class when required by the Challenge.

Operational requirements:

- opening incumbent identity frozen;
- eligible contender set frozen at settlement boundary;
- same promotion exam identity used across incumbent/contenders as registered;
- reconstruction-repeat policy enforced consistently;
- no arrival-order reward race;
- promotion receipts/events append-only;
- `INDETERMINATE` follows retry/hold policy, not arbitrary tie-break payout.

## 6. ChallengeSetEpoch operations

For every settlement epoch, record:

```text
epoch_id
active reward-enabled Challenge IDs/versions
N
slot_fraction = 1/N
open/close block/time
frontier policy refs
treasury accounting version
```

Adding/freezing/retiring/versioning a Challenge affects the next epoch unless emergency freeze semantics explicitly require otherwise.

## 7. Treasury services

Expected components under the current research architecture:

- registered treasury neuron/hotkey;
- TreasuryVault / asset custody;
- TreasuryController / governance;
- event/entitlement index;
- proposal/timelock/execution monitor;
- Bittensor EVM/precompile integration;
- reconciliation service from subnet inflow → notional Challenge accounting → paid events.

## 8. Treasury monitoring

Monitor:

- treasury-neuron registration / UID / hotkey association;
- observed miner-side emission into treasury;
- Alpha/TAO balances and stake locations;
- governance voter eligibility and active-validator status;
- proposal state / quorum / timelock / expiry;
- spend-limit windows;
- event-to-proposal correspondence;
- duplicate-payment attempts;
- failed precompile / gas-estimation calls;
- chain/RPC divergence;
- exact paid amount and recipient;
- untriggered Challenge opportunity retained as treasury capital.

## 9. Treasury incident semantics

Examples:

- **RPC down:** `PAYOUT_PENDING_INFRA`; frontier event remains confirmed.
- **Gas estimation/precompile regression:** freeze execution, preserve proposals/events, open chain compatibility incident.
- **Challenge scientific defect discovered before payment:** freeze Challenge settlement under explicit policy; do not erase historical evidence.
- **Duplicate proposal:** reject mechanically by frontier-event identity.
- **Proposer censorship:** alert and invoke documented governance/recovery path; do not silently expire valid science without record.
- **Treasury key/controller compromise:** freeze spending, preserve event ledger, activate incident/governance procedure.

## 10. Reconciliation accounting

For each settlement period, Carbon should be able to reconcile:

```text
observed treasury inflow
= paid frontier entitlements
+ retained general treasury capital
+ explicitly governed non-performance transfers
+ fees/gas/accounting deltas where applicable
```

Every performance transfer maps to one finalized FrontierAdvanceEvent.

## 11. SLO separation

Scientific evaluation, promotion, treasury governance, and product qualification should have different SLOs. Treasury delay must not block ordinary scientific experimentation unless the protocol explicitly pauses new payout-enabled windows for solvency/security reasons.

## 12. Launch progression

```text
offline scientific PoC
→ qualified one-Challenge testnet
→ promotion dry-run
→ treasury localnet
→ treasury testnet with synthetic events
→ one-Challenge event-bound payout
→ 4–7 Challenge portfolio dry-run
→ payout-enabled portfolio
```

Do not jump from “score computed” to “mainnet reward path proven.”

## 13. Final rule

> **Operations preserves the boundaries: evidence jobs determine science, promotion jobs determine frontier state, and treasury jobs settle already-authorized economic entitlements.**
