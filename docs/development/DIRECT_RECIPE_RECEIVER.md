# DEVELOPMENT construction receiver

This is the operator entrypoint for the existing `DirectRecipeIntake`, not a
second construction service. It serves the registered public
`synthetic-linear-field-2d` kit **1.3**, signed staging/submit/status on the same
`/carbon/v1/mcp` route, and the existing durable reconstruction/inference tasks.
Every model uses this path. No model family, backbone or matrix-row selector is
part of the operator configuration.

The slice is loopback DEVELOPMENT only: chain signatures and registration are
checked, but chain commitments, official scoring, qualification and rewards are
not provided. HTTPS/Cloudflare exposure and an independent validator-owned
checkout remain separate work; this listener does not claim those properties.

## Installed prerequisites

Use the normal maintained installation and Compute/Review profile. The running
source must be the exact clean accepted revision in fetched `origin/main`; its
selected worker manifest must bind that source and pass the existing read-only
Docker doctor. A GPU profile selects its installed `gpu_image`; otherwise the
profile's ordinary worker image is selected. Existing per-recipe library image
resolution reads the installed `.direct-development/library-cache`; it never
builds or downloads from a miner request. A graph uses the same worker parent.
Missing images or unsupported bundle/runtime identities retain their existing
typed refusals. Do not edit accepted revisions, manifests or profile labels to
make an old image appear compatible.

The receiver hotkey is a **public** SS58 address and must equal the actual
configured network publisher. Startup reads an authentic chain snapshot and
requires that receiver to be registered. The entrypoint does not load a signer,
wallet, API key, private key or password. Miner requests still use their own
normal external signer and must authenticate as registered participants.

## Finite Product command

Product runs this only under the current host TEST admission, actual summed
resource reservations, finite process/cleanup deadline and existing SSH guard.
The command is Linux/POSIX because the maintained durable provider and owner
lock use POSIX permissions and locking. Use the same already admitted native
WSL caller as the other normal Launchpad operations.

Create an owner-only directory and canonical JSON config (mode `0600`, parent
`0700`) with exactly these fields. Replace the placeholders with the genuine
installed profile, private receiver state root and public publisher address:

```json
{
  "schema": "carbon.construction.direct-receiver-operator.v1",
  "root": "/absolute/private/operator/direct-receiver-1.3",
  "runner_profile": "/absolute/private/installed/environment/runner-profile.json",
  "receiver_hotkey": "<configured public publisher SS58 address>",
  "host": "127.0.0.1",
  "port": 8767,
  "lifetime_seconds": 1800,
  "measure_query": true
}
```

The displayed JSON is a template; serialize the actual object with the existing
`carbon.development_session.profile.canonical` function before saving it.
`measure_query` is a trusted operator profile choice made **before** task
creation. `true` uses the existing measured query-v2 path and distinct durable
rule/task binding. It is not a miner argument or a way to reinterpret an old
unmeasured task. Historical callers retain the default `false` behavior.

From the accepted installed checkout and its normal Python environment:

```sh
python -B -m carbon.challenge_validator.direct_receiver --config /absolute/private/operator/receiver.json
```

The process prints one `LISTENING` record containing the exact inert
`direct_intake_target` pair after binding the actual listener. The fixed port
must already be available; an occupied port is a failure, not an alternate-port
retry. Discovery is the maintained read-only route:

```sh
curl --fail http://127.0.0.1:8767/carbon/v1/construction/intake
```

Check its actual Challenge, receiver, served contract, chain and snapshot
against the profile. This GET is discovery, not model evidence.

## Normal miner target

In the normal Control Center **Setup → Review → Advanced: DEVELOPMENT
construction receiver**, enter the actual URL and public receiver address
printed above, then write the profile. The existing authenticated
`POST /api/v1/setup/review` operation accepts this same pair:

```json
{
  "direct_intake_target": {
    "intake_url": "http://127.0.0.1:8767",
    "receiver_hotkey": "<same configured public publisher SS58 address>"
  }
}
```

This is input to the existing Review operation alongside any other current
Review choices; the bootstrap never writes a miner profile. Read the resulting
profile to verify the exact pair, including after repeated Review. Open the
existing `direct-development-1.3` session. Its staging and submit tools use this
signed receiver and real served contract; no local workspace is represented as
remotely staged source. Do not select a Battery campaign or relabel its version.

## Stop and custody

Admission ends when the configured lifetime expires or the process receives
SIGINT/SIGTERM. The existing HTTP listener closes first.
An accepted connection has an absolute ten-second request-line/header deadline,
the existing absolute ten-second body deadline, and existing ten-second socket
read/write timeouts. The loopback listener drains its bounded request handlers
before the final task cancellation snapshot; a slow header sender cannot hold
that drain indefinitely. Installed image checks retain their fixed Docker CLI
timeouts (thirty seconds per call).

After that drain, the bootstrap requests
idempotent cancellation of every owned queued/running task through
`cancel_observed_task`; the existing carrier observes its own cancellation and
resource deadlines. The worker is joined before releasing task supervisor
locks. Cleanup is not declared from a callback or elapsed timeout: retained
children still needing reconciliation make shutdown fail. Product retains its
outer deadline/owned-stop monitor and verifies actual owned containers,
processes and reservations before closing the TEST lease. An infrastructure
hang is unresolved cleanup, never a scientific failure or clean shutdown.

State under the private root contains the immutable source/image/chain/kit/
measurement binding, signed receipt journal, attempt ledger and per-hotkey
durable task/workspace ledgers. Restart reopens those exact owners and reconciles
interrupted tasks through the existing provider; it does not make a fresh empty
ledger to bypass old work. Keep this state and original model artifacts for
retention into the existing ScoreLab bank. Receiver startup alone is not bank
ACK, model reconstruction or an official verdict.

## Validation handoff

Product should include these source tests in the next coherent affected
canonical run, using the already arranged SDK/MCP dependencies and cached
canonical route rather than creating another standalone environment:

```sh
./scripts/dev/canonical.sh --focused tests/cpu/test_direct_receiver.py tests/cpu/test_direct_recipe_intake.py tests/cpu/test_direct_intake_source_staging.py tests/cpu/test_lean_recipe_adapter.py
```

The new loopback test uses authentic routing and durable workspace/task classes
with explicit fake verifier/snapshot/image fixtures, stops before dispatch and
refuses any attempted model run. It validates operator composition only.
Canonical source checks, accepted-source/image installation, a real signed
model build/inference, custody and independent validator evaluation remain
separate evidence states.
