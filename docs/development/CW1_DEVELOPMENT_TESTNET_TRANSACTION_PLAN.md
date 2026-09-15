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
| Publisher hotkey | `5E48fhGnyi4C94bsAc64s2bgshyJb7bfP59pRbidghc1pAyQ` |
| Publisher coldkey | `5CmGx8PFzfL7EvrvqFgV2Sv2HGok53YkGUsBw1atTD5hw7N8` |
| Worker | `carbon.c03.linux-x86_64-cpu.development.v1`; exact image digest comes from the retained source receipt and private operator config |
| Worker limits | one worker; 2 logical CPUs; 4 GiB/no swap; 256 tasks; 512 MiB scratch; 600-second productive deadline |
| Evidence | exact C-08 request, C-07 account, active C-06 signature and verified bounded local export; all official/protected/network/reward flags remain false |
| Publication | mechanism 0; one dispatch; all `Q12` units to the observed registered subnet-owner burn sink |
| Value transfer | zero TAO value-transfer authority in Carbon's SDK policy; transaction fees remain an observed non-zero-or-unknown external cost |

The current repository/operator context supplies no approved netuid. The named
hotkey was unregistered across the previously scanned netuids. Therefore UID,
subnet ownership/permission, burn recipient, current registration price,
validator permit/stake exception, rate window, pending commitments, exact
weight method and transaction fee are `UNKNOWN`, not false or zero.

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
  "publisher_hotkey": "5E48fhGnyi4C94bsAc64s2bgshyJb7bfP59pRbidghc1pAyQ",
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

One concrete operator response is still required: approved netuid and evidence
of permission to use it, an eligible Linux x86-64 Docker host/session, and—only
after refreshed read-only observations—the exact test-TAO cap for any required
registration plus the distinct one-dispatch block-window authorization. No
secret value belongs in chat or repository.
