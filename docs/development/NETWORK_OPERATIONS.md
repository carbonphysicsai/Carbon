# NET-6 — Disposable node and publisher operations

This is a DEVELOPMENT runbook for the pinned C0 synthetic localnet. G2 is
NOT_READY: NET-5 measured all-burn rows, finality, epochs and outage recovery,
but required shielded miner registration failed with SDK Stale/expired. Actual
shared-winner and recycled-UID chain effects remain unobserved. The operator-only
rehearsal deliberately does not attempt that unresolved operation.

## Reproduce and retain a disposable session

Use Carbon's canonical Linux amd64 environment with a functioning Docker daemon:

```sh
CARBON_UV_GROUPS=chain ./scripts/dev/bootstrap.sh
CARBON_UV_GROUPS=chain ./scripts/dev/doctor.sh
CARBON_LOCALNET_MODE=operator CARBON_LOCALNET_KEEP=1 \
  CARBON_LOCALNET_STATE="$PWD/.local/operator-private" \
  ./scripts/dev/localnet.sh .carbon-artifacts/operator
```

The private state destination must not already exist. The harness creates an
internal Docker network, one container with three development authorities, and
process-owned loopback RPC relays. It verifies the exact image, startup command,
container ID, network, observed genesis and runtime before using throwaway keys.
There are no host mounts, privileged mode, public endpoints or valuable tokens.
Default KEEP=0 stops/removes only the named disposable container and network.
KEEP=1 retains them for operator work; record the printed names. It does not
publish a public service. The Windows host used for this delivery has no working
Docker daemon; canonical GitHub Linux runtime evidence is recorded separately.

The single source of pins is `scripts/dev/localnet-runtime.json`: SDK 11.1.0 in
`uv.lock`, independently pinned v445 source and image digest. The checked upstream
script is preserved; each start regenerates `/scripts/carbon-localnet.sh` with
libp2p and `--no-purge`. The runtime binary stays unchanged. Restarting the exact
container retains its writable-layer chain database. Removing/recreating it is
a new disposable session and cannot reuse old journal authority merely because
the deterministic genesis is equal. Configuration binds the exact container ID.

## Start one publisher with an external disposable key

The retained private directory contains `operator.json` and the existing SQLite
journal. It contains no generated key file. Supply the matching throwaway key
through `publisher.key`, owner-only mode 0600, in that private directory. For this
specific disposable fixture publisher only, its known development URI is
`//Alice_hk`. Never use a real account or put key files in artifacts/version control.

```sh
umask 077
printf '%s' '//Alice_hk' > .local/operator-private/publisher.key
.venv/bin/python -m carbon.chain.operations validate --config .local/operator-private/operator.json
.venv/bin/python -m carbon.chain.operations run --config .local/operator-private/operator.json
```

`validate` checks configuration only and does not read a key or assert chain
health. `run` takes the exclusive OS journal lease, reopens the exact configured
loopback ports, reconstructs consumers from the existing registered fixture
contexts, and checks container/genesis/runtime/publisher identity before reading
the external key. No import-time SDK, wallet or network connection occurs.
A name reused by a different container, changed runtime, occupied port, public
endpoint, missing context, wrong key or duplicate publisher fails closed.
The localnet root and fixture keys are public development keys and supply no
production custody or security qualification.

The default heartbeat is five seconds (accepted development range 1–30 seconds).
It reconciles durable pending dispatch before issuing a new projection and checks
the final integer vector at execution. SIGINT/SIGTERM requests graceful shutdown;
SIGKILL/process crash releases the OS lock. Never delete the lock inode to force
a second owner. A stopped process does not clear stored weights. Shutdown output
explicitly retains this exposure. `--max-ticks 2` bounds an operator rehearsal.

Stop the publisher before node maintenance. Use `docker stop --time 35 NAME` and
`docker start NAME` on the exact retained container, then restart the publisher.
Do not rerun the setup harness against the existing journal: it rejects ambiguous
setup replay. A changed internal IP or lost node database requires investigation
and a new explicit disposable session, not edited evidence or forced recovery.

## Health, recovery and bounded capacity

```sh
.venv/bin/python -m carbon.chain.operations health --journal .local/operator-private/receipts.sqlite
```

Use the actual journal path in `operator.json` if it differs. Health is a read-only
allow-list of final observed block/time, dispatch state, pending identity, capacity
and stale exposure. RECENT is a journal observation, not proof that a process or
provider is currently alive. UNKNOWN, CLOCK_DISAGREEMENT and age over 30 seconds
require inspection. The wall clock only diagnoses health; finalized-chain time
continues to govern credit age. Transaction identity, inclusion/finalization,
reveal, stored row and observed settlement remain distinct.

Provider failure closes the connection and retries observation on the next tick.
Ambiguous dispatch is reconciled through the existing bounded owner; it is never
blindly resent. Missing transaction identity or a history gap that exceeds the
reconciliation bound requires read-only chain evidence before any intervention.
Do not reset a journal, erase pending liabilities or infer zero payout from local
expiry. The development dispatch journal has a 10,000-row bound, with NEAR at
9,000 (about 13.9 hours at five-second issuance for the hard bound). Stop and
retain evidence before exhaustion; automatic pruning and production archival
rotation are not implemented. Backups are not a license to reset replay history.

## Consistent private backup and no-overwrite restore

```sh
.venv/bin/python -m carbon.chain.operations backup \
  --journal .local/operator-private/receipts.sqlite \
  --destination .local/operator-backup-001
.venv/bin/python -m carbon.chain.operations restore \
  --backup .local/operator-backup-001 \
  --destination .local/operator-private/restored.sqlite \
  --config .local/operator-private/operator.json
```

SQLite backup captures all committed logical state, including WAL, receipt order,
nonces, accepted provenance, score bytes, credit age and pending dispatch. The
snapshot is bounded to one GiB and a 60-second backup deadline. The private bundle
contains an integrity/schema/context manifest, not keys. Its checksum detects
corruption, not malicious replacement by an authorized filesystem writer.
Store it with the same private access and retention as the original journal.

Restore checks schema, context, checksum and database integrity, fsyncs data, and
atomically links to a new destination without overwriting an existing database.
A partial backup without a complete manifest is unusable. Stop the old publisher,
retain its journal, and change only the private configuration's journal path to
the restored destination. Reconcile pending transactions against the same chain
before any new issuance. Never run both copies: the OS lease protects one path,
not cloned databases. Cross-machine custody, encrypted durable archives, retention
policy and adversarial filesystem protection require the C-EA owners.

## Upgrades and remaining integration

Follow `docs/development/CHAIN_ADAPTER.md`'s exact dependency upgrade workflow and
installed-SDK compatibility tests. Change image/source/startup pins in a reviewable
PR, rerun isolated genesis/runtime capability checks and the full relevant localnet
scenario, and retain capability differences. SDK version alone does not establish
runtime compatibility. No floating image, automatic production upgrade or policy
bypass is supported.

The remaining full integration command is:

```sh
CARBON_LOCALNET_MODE=full ./scripts/dev/localnet.sh .carbon-artifacts/localnet
```

Its prerequisite is a tested resolution of required shielded miner registration
for the pinned SDK/runtime path. Preserve both inner and carrier transaction IDs,
finalized-block/era observations and exact errors; do not use an unchecked raw
extrinsic, downgrade shielding policy, or retry unchanged inputs. The current
operator mode is not a substitute for this full scenario or G2 readiness.

`scripts/dev/public-network-config.schema.json` is an inert handoff schema:
enabled=false, all privileged identities/policies null. The executable operator
accepts only its separate disposable-localnet configuration. C1 real construction,
scientific qualification, C-EA evidence custody, C2 public integration and live
security/economic approvals remain with their existing owners. Treasury is absent
from this persistent direct-winner-plus-burn path; optional treasury work has its
own future admission/custody contract. B-E4 and unfinished B-01G remain non-blocking.
