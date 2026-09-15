# C-W1-D1 first public-testnet transaction plan

**Status:** concrete execution handoff; public write not authorized
**Profile:** `carbon.public-synthetic-testnet.development.v1`
**Prepared:** 2026-09-15

This plan binds the one all-burn DEVELOPMENT demonstration. It is not a subnet
selection, token approval, protected admission, scientific result, reward run or
LIVE activation.

## Fixed facts

| Field | Bound value |
|---|---|
| Network | Bittensor public testnet only |
| Endpoint | `wss://test.finney.opentensor.ai:443` |
| Genesis | `0x8f9cf856bf558a14440e75569c9e58594757048d7b3a84b5d25f6bd978263105` |
| Last observed runtime | spec 458, transaction version 1; refresh before approval and dispatch |
| SDK | exact locked `bittensor==11.1.0`; no upgrade in this slice |
| Publisher hotkey | `5HWGPxuumoCdSXmbT62wNEnBN4rgU1WZXdPJfw4zqjLqV1wR` |
| Publisher coldkey | `5D9oP2ZTF1G7pg25EdPjCyy22315c6SvQqwrVzXg2WWF1QMu` |
| Worker | `carbon.c03.linux-x86_64-cpu.development.v1`; exact image digest comes from the retained source receipt and private operator config |
| Worker limits | one worker; 2 logical CPUs; 4 GiB/no swap; 256 tasks; 512 MiB scratch; 600-second productive deadline |
| Evidence | exact C-08 request, C-07 account, active C-06 signature and verified bounded local export; all official/protected/network/reward flags remain false |
| Publication | mechanism 0; one dispatch; all `Q12` units to the observed registered subnet-owner burn sink |
| Value transfer | zero TAO value-transfer authority in Carbon's SDK policy; transaction fees remain an observed non-zero-or-unknown external cost |

The selected subnet is now **567**, with owner/publisher **UID 0**. Creation
finalized at block 8010852, transaction
`0x8efc1856f94403ace7e2706e8e309fbd5bcb8fdd86f1c94215bf7486d9c897c5`,
for 1.003183218 test TAO. These current bindings supersede the earlier unregistered
wallet without rewriting its historical receipts. WSL Ubuntu Docker Engine is
available. Read-only doctor observed owner capability, owner burn UID 0,
mechanism 0 and timelocked commit/reveal; refresh every dynamic value near dispatch.

## Consolidated remaining transaction decision

| Separate scope | Concrete operation | Last read-only cost | Authority |
|---|---|---|---|
| Miner registration | `burned_register(567, 5HmVzauSQMjErYSAzPFiKXi7uN9vM1TMLLVrjdVDJxYdPTxY)` via SDK 11.1/MEV shield | At finalized 8011286: burn 0.433602189 + estimated fee 0.002141781 test TAO | Proposed total cap 0.50 test TAO; six hours; not approved |
| Activation | Owner `start_call(567)` | Estimated fee 0.000257187 test TAO; `FirstEmissionBlockNumber=null` at 8011285 | Proposed total cap 0.001 test TAO; distinct approval still required |
| All-burn publication | One checked mechanism-0 timelocked commitment, all units to observed owner burn UID 0 | Unsigned inner-call fee estimate 0; outer shield/dispatch fee must be refreshed | Exact source, fee cap and one-dispatch block window pending; no approval |

Activation is separate from the already elapsed weights rate limit. It starts
subtoken trading/alpha epoch behavior and does not grant root-controlled TAO
emission. Creation authority does not authorize activation. Miner registration
uses a distinct hotkey under the same owner coldkey, not publisher UID 0 as a
stand-in. Freeze each transaction's individual authority, cap and validity
window, recheck before dispatch, and reconcile any ambiguous result before
another action. The session's USD 0.25 model-run proposal is a separate provider
approval and cannot be charged against a test-TAO allowance.

## Required read-only target observation

The owner/operator supplies one existing Carbon-owned subnet, or written
permission identifying an exact third-party test subnet. With that netuid set,
run:

```bash
uv run --locked --group chain python -m carbon.development_testnet doctor \
  --online \
  --config /absolute/private/operator/development-testnet.json
```

The report must bind endpoint/genesis/runtime, registration and UID, observed
coldkey association, owner identity and burn UID, permit/stake or owner
exception, burn mode, mechanism count, commit/reveal method, rate limit, last
update, next eligible block and pending commitments. RPC failure leaves the
affected fields unknown. Registration must not be attempted until this report
shows how this hotkey can become publication-eligible.

Official Bittensor documentation treats weight setting as a wallet-hotkey,
netuid, UID/value and version-key operation, and distinguishes inclusion from
finalization:
<https://docs.learnbittensor.org/python-api/html/autoapi/bittensor/core/extrinsics/set_weights/index.html>.
Its Dynamic TAO documentation also makes subnet stake and price state dynamic,
so Carbon obtains the target-specific values from the same finalized chain
view, not a copied estimate:
<https://docs.learnbittensor.org/dynamic-tao/dtao-guide>.

## Separate authorization records

If the hotkey is not registered, first prepare a registration-only request with
the exact runtime call selected by the pinned SDK, observed burn/registration
price, bounded fee allowance, total test-TAO cap, validity window and ambiguous
submission reconciliation. The earlier 1.0 test-TAO idea is not approved. A
stake, subnet creation or ownership change is a separate operation and requires
its own exact authorization; none is implied here.

Only after registration and publication eligibility are finalized may the
owner approve the one weight transaction. The checked-in configuration schema
requires:

```json
{
  "authorization_id": "OWNER_SUPPLIED_TOKEN",
  "authority_record_digest": "sha256:OWNER_RECORDED_64_HEX_DIGEST",
  "publisher_hotkey": "5HWGPxuumoCdSXmbT62wNEnBN4rgU1WZXdPJfw4zqjLqV1wR",
  "expected_runtime_spec": 458,
  "valid_from_block": 0,
  "valid_through_block": 0
}
```

The two block values must be prospectively chosen around the intended dispatch,
not copied from this example. Fixed code adds mechanism 0, exactly one dispatch,
`SubtensorModule.set_mechanism_weights`, zero TAO value-transfer authority and
DEVELOPMENT-only scope. If the observed runtime requires the pinned SDK's
timelocked commit/reveal path, the doctor reports that method and the existing
checked builder retains it; an unrevealed pre-existing commitment blocks the
run.

## Execution and recovery

The trusted controller emits a closed source handoff after the authenticated
C-08 request, isolated reconstruction, C-07 stages, C-06 signature and local
export have completed. The handoff contains public verification material and
paths under the private retention root, never a signing or wallet secret.

```bash
python -m carbon.development_testnet status \
  --config /absolute/private/operator/development-testnet.json \
  --source /absolute/private/operator/source-handoff.json

uv run --locked --group chain python -m carbon.development_testnet run \
  --config /absolute/private/operator/development-testnet.json \
  --source /absolute/private/operator/source-handoff.json

uv run --locked --group chain python -m carbon.development_testnet resume \
  --config /absolute/private/operator/development-testnet.json \
  --source /absolute/private/operator/source-handoff.json
```

`run` checks the Linux worker host, fresh chain capabilities, authorization,
source receipt/profile and every export member before opening the named
external wallet. It creates the short-lived intent immediately before the
checked publication. `status` is local/read-only. `resume` opens no wallet and
only scans finalized blocks/readback for the exact retained transaction hash;
it never reconstructs, signs or resubmits.

Stop on target/permission uncertainty, SDK/runtime/genesis drift, missing or
changed source bytes, wallet identity mismatch, registration/coldkey mismatch,
insufficient capability, changed burn sink, rate limit, pending commitment,
expired authorization, ambiguous registration, failed local export or an
ineligible Linux host. After `ROW_VERIFIED`, stop. A stored all-burn row may
remain after the process exits and is not evidence of burn execution, epoch
effects, miner payment or scientific validity.

## Missing external decision

The subnet and Linux host are supplied and observed. The pending operator
response is the concrete bounded model-run approval/private provider credential
and distinct miner-registration approval in the supervised session plan. Keep
activation and the final source-bound all-burn authorization separate. No secret
value belongs in chat or repository; no transaction is dispatched by this plan.
