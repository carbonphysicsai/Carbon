# Public/synthetic DEVELOPMENT testnet runbook

## Finalized DEVELOPMENT chain execution — 2026-09-16

Separate owner-approved one-dispatch scopes completed activation at finalized
block 8017622 and the all-burn commitment at 8017643. Walletless reconciliation
observed reveal at 8017851 and exact row `[[0, 65535]]` at
8017916; the retained state is `ROW_VERIFIED`. Actual fees were
257188 RAO for activation and zero for publication. Both scopes are consumed;
do not replay `run` or infer authority for another transaction.

See [the exact transaction evidence and retained scientific limitations](CW1_BURGERS_AGENT_SESSION.md#finalized-development-chain-execution--2026-09-16).
The earlier proposed and pre-dispatch records below remain historical. The
source stays `COMPLETE_UNRESOLVED`; no comparison, winner, miner payment,
burn amount, epoch effect, protected eligibility or qualification is inferred.

This runbook is for `carbon.public-synthetic-testnet.development.v1`. It is not
the official C-W1/C-09/C-EA2 path and grants no protected, scientific,
production, reward or LIVE status.

## Current operator setup — 2026-09-15

Use the existing Ubuntu-24.04 WSL2 Docker Engine at `/absolute/linux/checkout`.
Subnet 567 and publisher UID 0 now exist. The supervised Burgers session contract,
current identities, exact CLI sequence, observed engineering results and separate
approval scopes are in [CW1_BURGERS_AGENT_SESSION.md](CW1_BURGERS_AGENT_SESSION.md).
The older Darwin/no-subnet observations below describe the pre-setup checkpoint.
Do not switch to Docker Desktop or reuse the earlier unregistered wallet.

## Historical pre-dispatch checkpoint — 2026-09-16

PR #191 is merged. The separately approved real FNO-40 agent session completed
three replicas, 120 updates, 72 measurements, permitted feedback and an ACTIVE
signed source. `CW1_BURGERS_AGENT_SESSION.md` records the results and limits.
Keep the source fixed; no model restart is required. Miner UID 1 is registered;
activation and the one all-burn publication remain separately unapproved.
The prospective zero-fee guard requires the pinned SDK estimate to be exactly
zero before signing. Its acceptance, fresh runtime/activation checks and the
source-bound block-window approval precede public dispatch. The weight method
uses a direct timelocked commitment, without registration's MEV carrier.

## What the implementation composes

An authenticated NET-2/C-08 submission is resolved from its durable receipt
journal and matched to the exact retained C-07 account. C-06 independently
verifies the signed DEVELOPMENT receipt and active ledger state. The controller
records a bounded local evidence/export identity, issues a 60-second all-burn
DEVELOPMENT intent, and uses the existing checked SDK lifecycle for preflight,
signing, durable pre-dispatch journaling, reconciliation, finalization and exact
row readback. One authorization record can bind only one intent effect.

The numerical path is unchanged: the existing C-03 worker executes the frozen
three-replica reconstruction and the C-07 public/synthetic evaluation stages.
Production/protected consumers still reject its signed receipt. The local
retention profile is capped at 2 GiB and must be exported with a content
manifest for review/replay; it does not survive loss of the only host by claim.

## Commands

The shipped example contains public identities only and deliberately leaves the
subnet and transaction authorization empty:

```bash
python -m carbon.development_testnet validate \
  --config "$PWD/docs/development/CW1_DEVELOPMENT_TESTNET_OPERATOR.example.json"

python -m carbon.development_testnet doctor \
  --config "$PWD/docs/development/CW1_DEVELOPMENT_TESTNET_OPERATOR.example.json"
```

After the operator fills an approved netuid and installs the locked chain group
on an eligible Linux host, the read-only public-chain check is:

```bash
uv run --locked --group chain python -m carbon.development_testnet doctor \
  --online \
  --config /absolute/private/operator/development-testnet.json
```

The doctor never reads a wallet/key, signs, submits, reserves funds or mutates
the chain. A complete transaction authorization object must name an ID and
authority-record digest, exact publisher, runtime spec and a finalized-block
window. Fixed fields allow one mechanism-zero
`SubtensorModule.set_mechanism_weights` dispatch with `max_spend_tao=0` and
DEVELOPMENT-only authority. The caller supplies wallet material only to the
existing trusted operator process after this preflight; no key or seed belongs
in the config, logs, repository or chat.

After the trusted controller has completed and exported the exact C-08/C-03/
C-07/C-06 source, it emits
`carbon.development-testnet.source-handoff.v1`. The handoff contains paths and
public verification material only. It does not contain wallet or receipt
signing secrets. The operator then uses the fixed entry point:

```bash
python -m carbon.development_testnet status --config /absolute/private/operator/development-testnet.json --source /absolute/private/operator/source-handoff.json
uv run --locked --group chain python -m carbon.development_testnet run --config /absolute/private/operator/development-testnet.json --source /absolute/private/operator/source-handoff.json
uv run --locked --group chain python -m carbon.development_testnet resume --config /absolute/private/operator/development-testnet.json --source /absolute/private/operator/source-handoff.json
```

`run` verifies the C-08 association, active C-06 ledger receipt, C-07 account,
worker image/resource identities and every bounded export member before wallet
access. `status` is local and read-only. `resume` opens no wallet and can only
reconcile the retained hash through finalization/readback; it cannot rerun
science or resend a transaction. See
[`CW1_DEVELOPMENT_TESTNET_TRANSACTION_PLAN.md`](./CW1_DEVELOPMENT_TESTNET_TRANSACTION_PLAN.md)
for the exact missing target and authorization fields.

## Current read-only observation (2026-09-15)

Using the exact pinned `bittensor==11.1.0` package in an isolated Python 3.11
environment, the public endpoint identified Bittensor testnet genesis
`0x8f9cf856bf558a14440e75569c9e58594757048d7b3a84b5d25f6bd978263105`,
runtime spec 458 and transaction version 1. A finalized-state scan of then
available netuids found no registration for public hotkey
`5E48fhGnyi4C94bsAc64s2bgshyJb7bfP59pRbidghc1pAyQ`; therefore no public UID,
validator permit or publication eligibility was inferred.

At the historical PR #185 preparation checkpoint, the operator machine reported Darwin/arm64, 8 GiB RAM, ample disk, no
available Docker daemon and no installed pinned Bittensor SDK in its project
environment. It is diagnostic-only and cannot supply the required Linux C-03
isolation evidence. Use an already authorized Linux x86-64 host; do not label
an in-process or native-Mac fallback as isolated.

Official Bittensor documentation describes weight-setting as a wallet-hotkey,
netuid, UID/value and version-key operation whose inclusion and finalization
are distinct observations. Carbon additionally requires exact genesis/runtime,
recipient, authorization, durable dispatch and finalized row checks. See
<https://docs.learnbittensor.org/python-api/html/autoapi/bittensor/core/extrinsics/set_weights/index.html>.

## Public execution order and stop conditions

1. Select an existing authorized testnet subnet; record netuid and current
   registration cost without creating a subnet.
2. Re-run the online doctor. Stop on genesis/runtime mismatch, missing
   registration, insufficient stake/permit (unless the publisher is the
   verified subnet owner), rate limit, pending commitment or changed burn sink.
3. If registration is needed, obtain a separate exact testnet-token transaction
   approval. Reconcile ambiguous registration before any resend.
4. Run one public/synthetic C-08 -> C-03 -> C-07 evaluation and retain its
   signed DEVELOPMENT receipt plus local export manifest.
5. Prepare and approve one block-bounded transaction record, load the existing
   wallet through the operator's external mechanism, publish the all-burn
   vector, wait for finalization and verify the stored row.
6. Stop after the single dispatch. Preserve failures and ambiguous state; do
   not infer emissions, payment or epoch behavior from transaction inclusion.

No public write is currently authorized or technically eligible. PR #183's
exact head passed required acceptance run `34927991086` and merged as
`bd7e5a5423d1148d340b3de3993068b66f5973d9`; that evidence is not rerun here.
The precise
missing inputs are an approved existing netuid, registration/UID and publication
capability for the public hotkey, an eligible Linux host/session, any bounded
testnet-token registration amount, and the exact one-dispatch transaction
approval.

## Recovery of a previously missed reveal event

For an already-finalized timelocked commitment whose journal still lacks a
reveal, `resume --rescan-reveal` starts a bounded event backfill at the retained
finalized commitment block plus one. It accepts no caller-provided event, block
or stored-row claim. Each call scans at most 256 finalized blocks; use ordinary
`resume` for subsequent pages. Do not repeatedly rewind a long backfill.

```bash
python -m carbon.development_testnet resume --rescan-reveal --config /absolute/private/operator/development-testnet.json --source /absolute/private/operator/source-handoff.json
python -m carbon.development_testnet resume --config /absolute/private/operator/development-testnet.json --source /absolute/private/operator/source-handoff.json
```

This option is walletless and cannot sign, resend or rerun science. It preserves
transaction facts and prior journal events, does not reopen terminal records,
and still requires a matching finalized reveal, stable exposure and exact row.
It is rejected for other commands and unfinalized dispatches. The completed
subnet 567 example above requires no further rescan or transaction.
