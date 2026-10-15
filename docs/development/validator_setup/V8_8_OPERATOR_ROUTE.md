# Proposed v8.8 validator operator route

This is DEVELOPMENT software and packaging. Root/owner retains the literal
release/tag word and final SHA, image publication, privileged execution,
exposure, mainnet policy/custody and qualification decisions. A source-byte
verification or fixture pass is not installation, HTTPS or payment acceptance.

## What is distributed

`carbon.validator_setup` wraps the existing service/supervisor, intake/daemon,
answer-key sync and registered winner publisher. The operator source bundle
contains exact public Git blobs, per-file SHA256/mode/size, source revision/tree,
UV lock and SDK11.1.0. No working-tree files, state, wallet, private material,
commercial documents or legacy executable checkout is packaged.

`.devcontainer/Dockerfile.validator-service` is a separate trusted-operator
runtime recipe. Reconstruction-worker images remain distinct. Build context
preparation verifies the payload; an explicit build inspects the actual local
image's labels and linux/amd64 identity. Its **local image ID** is not a registry
manifest digest. Publication and an exact accepted `registry@sha256:...` receipt
remain Root-owned. An image recipe/context is not a built/pulled image.

The operator image ships intake/daemon/sync/weights entry points. Configuration,
certificate/signer access, worker image manifests, state and history stay in
operator-owned external paths. Only trusted operator tooling gets that access;
the miner HTTP/MCP surfaces gain no setup, wallet, Docker or operator action.
Existing worker isolation/permits/device and scientific gates remain controlling.

### Registered-score runtime metadata

The public runtime payload includes the existing owner-adopted
`docs/development/evidence/battery-score-tuning/registry-v5.json`, with its
bytes frozen in the same manifest as the owner decision and EV4 contract.
It does not export the surrounding evidence directory. A different registry
must be deliberately included in a later bound artifact; an unavailable
registry is a refusal, not a fallback to another score.

Materialized releases have no Git history. The operator entrypoint propagates
its externally verified manifest pin as `CARBON_VALIDATOR_BUNDLE_DIGEST` to
its supervised children. Registered-score initialization verifies the actual
immutable bundle against that pin, checks that the requested registry is a
manifest member, and retains the configured registry SHA, candidate and
owner-decision checks. The manifest's source revision establishes committed
source provenance; a manifest cannot supply its own expected digest. Ordinary
research/checkouts still require the existing clean, committed Git registry.
No score values, candidate selection or historical scores change.

Service preflight includes a `registered_score` metadata check before building
the deployment. An active scorer must initialize successfully; no score term
is explicitly `not_applicable`. This reads public registry/contract/decision
metadata only and never computes a score, reconstructs a model or reads exam
cases. Passing these checks is not actual daemon or host acceptance. R5's
failed startup and rollback receipts remain historical; a repaired source PR
does not change the failed artifact or authorize a manual payload patch.

## Build and prepare (public source only)

The following are executable interfaces; use the exact completed candidate,
not a mutable branch/tag. Builder validation never calls a real wallet/chain.

```bash
python -m carbon.validator_setup materialize \
  --repository "$PUBLIC_REPOSITORY" --revision "$EXACT_REVISION" \
  --target "$NEW_RELEASE_DIRECTORY"
python -m carbon.validator_setup verify \
  --bundle "$NEW_RELEASE_DIRECTORY" --digest "$RECORDED_BUNDLE_DIGEST"
python -m carbon.validator_setup image-context \
  --repository "$PUBLIC_REPOSITORY" --revision "$EXACT_REVISION" \
  --target "$NEW_IMAGE_CONTEXT"
```

`image-context --build` explicitly invokes local Docker build/inspect, never
push/pull/run/deploy. Root/authorized CI selects when to build. The operator
record binds source/bundle/lock/recipe, actual local image ID, published manifest
digest when one exists, installed SDK and Docker/OS/dependency facts. Pinned base
and Python/UV/SDK inputs do not establish independently reproducible OCI bytes;
OS package resolution and actual built identity must be recorded honestly.

## Fresh machine and host source mirror

A fresh operator obtains the exact accepted published operator image through
the owner route. No reconstruction-image digest substitutes for it. The
`extract` command checks that the actual pulled image has the exact RepoDigest,
source/bundle/SDK/scope labels, copies only its public `/opt/carbon` payload from
an **unstarted** uniquely owned container, verifies actual bytes and removes
that extraction container. It neither creates a wallet nor starts services.

```bash
python -m carbon.validator_setup extract \
  --image "$EXACT_OPERATOR_IMAGE_REFERENCE" --revision "$EXACT_REVISION" \
  --digest "$RECORDED_BUNDLE_DIGEST" --target "$NEW_RELEASE_DIRECTORY"
```

On a machine without Carbon/Python installed, the same operator image runs this
command, with its Docker client reaching the operator's daemon and a new target
under an explicitly mounted operator-owned release parent. Platform2's packet
provides the literal Docker invocation/user/socket/directory bindings. Root
executes it. No existing Ryan checkout/venv/history is an implicit prerequisite.

The Docker host must have the public source at the **same absolute path** the
operator controller passes to reconstruction workers. Bind it read-only into
the controller at that same path and set its working directory there; bind
needed operator state/config/work directories at identical host/container paths.
Do not use `-v` to manufacture a missing source directory. Use explicit bind
`--mount`; a missing host path refuses. The image's expected bundle digest must
match the loaded mounted source, checked by the entry point. No image-only code
parity claim is valid when a source mount changes the code actually executed.

```bash
python -m carbon.validator_setup mirror-check \
  --bundle "$NEW_RELEASE_DIRECTORY" --digest "$RECORDED_BUNDLE_DIGEST" \
  --image "$EXACT_OPERATOR_IMAGE_REFERENCE"
```

This trusted read-only probe verifies the Docker host bind through the operator
image with network none/read-only/capabilities dropped/no new privileges. It gets
only public source, no socket/keys/state. This is not worker containment acceptance.

## Owned configuration and fresh initialization

New bundles require the exact pinned public OCV table, TRAIN v1, frozen
calibration, truth-overlay lock, already-published input index and public
refs-b battery records consumed by the battery runtime. The records preserve
the refusal of published cases outside that index. Bundles include these six
data files individually; broader
evidence and exam-design script directories stay excluded. Missing material
refuses before the release directory is written. Existing runtime loaders keep
their digest checks and scientific values. Historical bundle verification still
checks its original bytes and file set; it does not establish installation
readiness. Actual fresh-process initialization is a separate acceptance check.

Reuse the current owner-only service/intake/deployment/answer-key schemas and
their exposure/identity/image checks. Ordinary remote validators use
`batch_source: answer_key`: no producer/solver/root-sharing/tuning commands.
The trusted operator supplies its own receiver/hotkey/signer/permit context and
pins the producer public key. No key or password is put in the image.

```bash
python -m carbon.validator_setup initialize \
  --bundle "$NEW_RELEASE_DIRECTORY" --digest "$RECORDED_BUNDLE_DIGEST" \
  --config "$DEPLOYMENT_CONFIG" --service-config "$SERVICE_CONFIG"
python -m carbon.validator_setup sync \
  --bundle "$NEW_RELEASE_DIRECTORY" --digest "$RECORDED_BUNDLE_DIGEST" \
  --config "$FETCH_CONFIG" --service-config "$SERVICE_CONFIG"
python -m carbon.validator_setup service preflight \
  --bundle "$NEW_RELEASE_DIRECTORY" --digest "$RECORDED_BUNDLE_DIGEST" \
  --config "$SERVICE_CONFIG"
```

Initialization reuses `operate.init` and explicitly opens the import-only pool;
an empty windowed pool can be ROTATION_PENDING and is **not evaluation ready**.
Sync imports the shared verified references and observes finalized windows.
HELD requires persisted reconstruction salt and any complete design selection;
interrupted imports retry without replacing their reference/window identities.
No publisher ledger/epoch intent/clock is deleted or reset.

Service actions `preflight/status/supervise/units` reuse existing refusal,
unhealthy exit codes, writer locks and restart behavior. Managed operations hold
a shared operator runtime lease; release selection takes it and all existing
child locks exclusively. The HTTP routes remain the registered intake routes.

`service units` retains the existing host-style intake/daemon units for
compatibility. For the intended image-backed route use `runtime-units` and the
adjacent closed template: all three operator roles use the same digest-pinned
image/bundle, explicit UID/GID/socket and identical source/state path bindings.
Its own intake receiver, answer-key hotkey and weights publisher must agree;
fetch/intake/weights must name the same deployment. Sync/weights periods are
explicit operator inputs, never silently invented. Generation writes five
owner-only support files to a new directory, installs/starts nothing.

The profile also binds `service_network` to `mode: host`, the intake's exact
`listener_host`/`listener_port`, and its explicit local `proxy_peer` (127.0.0.1
or ::1 for trusted-proxy mode, null for direct mode). Only the trusted operator
service container joins the host network namespace. A host TLS proxy can then
reach the configured loopback listener and retain its registered loopback peer;
Docker bridge publication would change that peer and is refused by this route.
This does not publish a listener, start a proxy, authorize exposure or alter the
network isolation of reconstruction/miner workers. Existing intake exposure,
TLS, carrier and commitment checks remain controlling. No blanket forwarded
header trust is introduced; nonregistered proxy peers still refuse.

The image route requires an explicit `signer_socket` in the existing fetch
configuration. It refuses the implicit container-home signer fallback. That
socket, any fetch `ca`, and any intake `tls_cert`/`tls_key` must already exist
as the expected socket/regular file under declared identical state mounts,
without symlink traversal. Keep the signer running under its existing authority;
unit rendering only checks its path/type and does not connect or sign. Prepare
these files/socket before rendering units; no credentials are copied into the
public source bundle or image. Existing runtime TLS/key permission checks apply.

```bash
python -m carbon.validator_setup runtime-units \
  --profile "$OWNED_RUNTIME_UNITS_PROFILE" --out "$NEW_UNIT_OUTPUT_DIRECTORY"
```

Platform2 packages the exact generated files into the owner packet. Root owns
systemd installation/enable/start, role credentials/socket access, exposure and
first actual host receipt. Existing host-style units do not establish image-route
parity. The adjacent templates deliberately fail closed until all required
identity/path/image/runtime/cadence fields are supplied.

## Checked weights and actual runtime observation

`weights` accepts additive `carbon.validator-weights-operator.v1`: exactly
`schema`, `context`, `expected_runtime_spec`, `publisher`, `wallet`. Context has
`network`, `endpoint`, `chain_id` (provider label), `genesis_hash`, `netuid`;
publisher has `hotkey/coldkey` public identities and wallet has `name/hotkey_name/path`.
All identity/context fields are explicit. The file is regular, absolute and
owner-only. This is not a miner setup profile or an economic authorization.
Wallet path is explicit, absolute and external: it never silently uses the
image user's or Ryan's default home. Existing helper callers retain their
default behavior; the new route supplies this path explicitly.

```bash
python -m carbon.validator_setup weights preview \
  --bundle "$NEW_RELEASE_DIRECTORY" --digest "$RECORDED_BUNDLE_DIGEST" \
  --service-config "$SERVICE_CONFIG" --config "$WEIGHTS_CONFIG" \
  --standing "$STANDING" --journal "$PUBLICATION_JOURNAL" \
  --ledger "$WINNER_LEDGER" --battery-deployment "$DEPLOYMENT_CONFIG"
python -m carbon.validator_setup runtime \
  --bundle "$NEW_RELEASE_DIRECTORY" --digest "$RECORDED_BUNDLE_DIGEST" \
  --network "$NETWORK" --endpoint "$ENDPOINT" --genesis "$GENESIS" \
  --expected-spec "$OBSERVED_ADOPTED_RUNTIME_SPEC"
```

`weights run` uses the same existing issuer/shared publisher/standing/registry/
context/holder/integer/epoch/reconcile/no-resend gates. Mainnet policy registration,
netuid/custody/activation remain HUMAN_INPUT; no testnet policy is adopted for
finney, and a missing policy refuses before wallet/private-source access.
Testnet's owner-coldkey exception and mainnet's exclusion remain unchanged.

`runtime` reuses the SDK used-surface finalized-metadata probe and compares the
actual spec with the operator's explicit pin. It grants no transaction authority.
Actual finney/testnet feature/hyperparameter differences and current official
compatibility require Data Collector's dated public receipt. Do not equate chains
by SDK version or infer deployed rules from upcoming release notes.

## Docker socket supplementary group

At unit generation, the configured Docker endpoint must be a real socket with
readable metadata and write permission for the configured identity class.
The renderer adds the observed socket GID as Docker `--group-add` to service,
sync and weights. The profile's UID and primary GID stay unchanged; no group
number is a default or copied from another machine. A missing, symlinked,
non-socket, unreadable or non-writable endpoint refuses before unit output.
The socket is not connected or changed by rendering. Normal parent aliases
such as `/var/run` remain usable; the endpoint itself must not be a symlink.

Root's installation comparison must check each ExecStart's unchanged `--user`
and supplementary group against the actual mounted socket. If its path/GID
changes, regenerate units before starting; a prior rendering is not runtime
availability or security acceptance. Do not change socket modes, primary GID,
UID, privilege flags or state ownership to work around a refused endpoint.

This renderer is baked controller content. A renderer repair requires a new
matched source bundle and image before cutover. Existing source/image receipts
remain historical and immutable; do not relabel an older published digest or
execute repaired host source against that older image's bundle identity.

## Update and rollback

Prepare and verify a new immutable source/image pair first. Stop the managed
service, sync and publisher route through the owner packet. `select` acquires
the managed-runtime and existing supervisor/intake/daemon locks and compares the
expected pointer before an atomic code selection. Active/stale selection refuses.
It does not restart processes or restore/downgrade/delete private state.

```bash
python -m carbon.validator_setup select \
  --bundle "$NEW_RELEASE_DIRECTORY" --digest "$RECORDED_BUNDLE_DIGEST" \
  --service-config "$SERVICE_CONFIG" --pointer "$CODE_SELECTION_POINTER" \
  --expected-current-file "$SAVED_CURRENT_SELECTION"
```

For first install omit the expected-current file; any existing pointer refuses.
Rollback selects the prior verified source **and its matching image**; the
operator retains state/journals and runs compatibility/preflight before restart.
Any unsupported historical schema/policy refuses rather than inventing recovery.

## Separate acceptance cells

All real cells start NOT_RUN: fresh-machine same-artifact install/update/rollback,
own independent identity/state/reference/pool/restart; external registered
miners using receiver-bound HTTPS signatures and on-chain endpoint discovery;
certificate/TLS/proxy boundaries and durable202/admit/score/own-status; replay,
wrong receiver, unregistered, tamper, limits, restart, forged proxy negatives with
legitimate contrasts; multi-miner actual commit/reveal/inclusion/finalized row.
Loopback, scripted Docker or in-process fixtures do not close those cells.
Current testnet exposure record is reused only within its exact scope; additional
mainnet/external-validator exposure/custody decisions remain owner-reserved.
