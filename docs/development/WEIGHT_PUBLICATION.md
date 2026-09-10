# NET-4B localnet publication and recovery

Use `LocalnetPublisher(LocalnetIntentIssuer(ledger), backend)` with an explicitly
constructed `BittensorPublicationBackend(context, publisher_hotkey, wallet)`.
Construction/import opens no connection or keyfile. The operator supplies a
throwaway wallet externally. Only localnet contexts with explicit loopback endpoint,
observed expected genesis and non-root netuid are supported. SDK fallback/archive
pools are empty; no public default or indefinite reconnect is permitted.

The SDK is exactly 11.1.0; runtime source is v445,
d3f40e44bda9019c606aeb0c907bb52ba7fe386c, independently pinned from the SDK. Fresh
finalized capture binds metagraph, registration identities, runtime version,
mechanism count, owner identities, Burn mode, weight min/max/version/rate and
publisher permit/stake. The reference development configuration is mechanism 0,
minimum one weight and maximum 65535. The runtime's owner-hotkey stake exemption
is explicit; this does not imply useful Yuma stake or guaranteed epoch rewards.
The runtime defaults to one mechanism and permits at most two. Independent
challenge ledgers feed one complete vector; mechanisms are not challenge purses.

Burn verification uses registered SubnetOwnerHotkey and the owner's registered
OwnedHotkeys, with RecycleOrBurn exactly Burn. Runtime source sends their miner
incentives to burn_subnet_alpha. Recycle mode fails; MinerBurned includes recycled
allocation too and cannot prove burn alone. Owner cut and validator dividends
remain separate flows. Owner-associated payable winners and a publisher's own
winner row are rejected: owner miner rewards would burn, and the epoch algorithm
removes non-owner diagonal self weights. An arbitrary recipient, all-zero vector
or stopped publisher cannot stand in for burn.

Sources at the immutable runtime revision:

- [Owner miner incentive routing](https://github.com/RaoFoundation/subtensor/blob/d3f40e44bda9019c606aeb0c907bb52ba7fe386c/pallets/subtensor/src/coinbase/run_coinbase.rs).
- [Weight checks and storage](https://github.com/RaoFoundation/subtensor/blob/d3f40e44bda9019c606aeb0c907bb52ba7fe386c/pallets/subtensor/src/subnets/weights.rs).
- [Auto-reveal event and application](https://github.com/RaoFoundation/subtensor/blob/d3f40e44bda9019c606aeb0c907bb52ba7fe386c/pallets/subtensor/src/coinbase/reveal_commits.rs).
- [Epoch/Yuma behavior](https://github.com/RaoFoundation/subtensor/blob/d3f40e44bda9019c606aeb0c907bb52ba7fe386c/pallets/subtensor/src/epoch/run_epoch.rs).
- [Emission scaling by MinerBurned](https://github.com/RaoFoundation/subtensor/blob/d3f40e44bda9019c606aeb0c907bb52ba7fe386c/pallets/subtensor/src/coinbase/subnet_emissions.rs).

The compiler rechecks every challenge's allocated = earned + unearned and the
shared-holder aggregate. It preserves unused capacity and all unearned allocation
in the sink. It resolves hotkey/coldkey/registration to current UID; an identity
change requires a fresh projection, which burns a missing/recycled holder. No
loser floors, earned-only normalization or cross-challenge redistribution exist.

Q12 targets max-upscale to u16 using half-even rounding. The final representation
may drop dust. For N positive intended recipients, the complete vector's L1
quantization tolerance is ceil(N * 10^12 / 65535) Q12 units (about 30.52 ppm for
two recipients). Every final UID must belong to the intended vector; tolerance
cannot authorize a loser. Actual min-count/max-limit checks still apply, including
the runtime's self-only exemption. A clipping or configuration distortion beyond
that bound fails publication with a concrete reason. Application challenge targets,
SDK-conformed integers, stored weights, Yuma consensus and observed settlement
remain distinct; native weights do not promise target-equivalent payouts.

`sdk_weights.py` isolates the narrow version-specific shim. A public SetWeights
subclass mirrors installed 11.1.0 build and inserts the final integer check after
SDK preflight/conformance and before encryption or composition. Client.execute
rebuilds the plan; the check runs again there. A pre-sign hook rechecks fresh
identity/runtime/intent validity and the exact checked call bytes. SDK Policy
still restricts netuid and spend, and execute uses retries=0. No global patch,
broad fork, arbitrary raw extrinsic or policy bypass is used. Installed-source
AST hashes and actual SDK build/execute/policy/encryptor tests guard upgrades.

The journal records immutable intent, compiled targets, snapshot and capabilities
before effects. It records checked integers and call hash before signing, and
the signed transaction hash before wire submission through a narrow RpcSubstrate
reporting hook. Signed bytes and keys are not journaled. One active dispatch per
chain journal is enforced; a hash cannot bind two intents. Exact intent replay
returns its existing receipt and never resends it.

Inclusion, finality, timelock reveal, stored row and settlement have separate fields.
Reconciliation searches at most 256 finalized blocks per call with a durable
cursor. Unknown outcomes block new dispatch. An interrupted operation without
transaction identity remains explicitly ambiguous for operator reconciliation;
do not reset it or guess success. Known finalized rejection is a separate terminal
receipt. Changed recipient/runtime exposure after finalization is recorded as
EXPOSURE_CHANGED, never ROW_VERIFIED, so a fresh corrective intent may follow.
An unexplained differing stored row remains unresolved for operator investigation.

Plain publication needs no reveal. Timelock publication requires no pre-existing
publisher commitments, preserves the SDK reveal round, and awaits a finalized
TimelockedWeightsRevealed event plus the checked stored vector. LastUpdate advances
at commit time and is insufficient proof. v445's reveal event binds subnet and
hotkey, not the commitment hash; exclusive publisher credentials and an empty
pending queue are development assumptions. Compromised/shared credentials cannot
be security-qualified by these tests. NET-5 must identify which mode actually ran;
an offline encryption test is not an observed on-chain reveal.

`await publisher.run(stop_event)` supplies the explicit DEVELOPMENT five-second
heartbeat (configurable 1–30 seconds), issuing new decay/all-burn intents or
reconciling pending effects first. Operator status retains closed failure reasons.
Stopping or expiring this process never reports cleared chain weights. Keep the
heartbeat/readback running; after an outage, reconcile known transactions and
publish a fresh complete projection. Real throughput and heartbeat timing are
observations, not production SLOs. NET-6 owns exclusive process operation and
backup/restore. Journal development capacity is 10,000 dispatches; rotate/archive
only after preserving unresolved transaction and scientific history.

Settlement observations have separate immutable identities and block references,
with explicit OBSERVATION_NOT_TARGET_EQUALITY meaning. A row receipt alone leaves
settlement UNOBSERVED. NET-5 supplies actual pinned-runtime inclusion/finality,
applicable reveal, burn and epoch evidence. No G2, science/security qualification,
public-network deployment, treasury or LIVE authority is claimed by NET-4B.
