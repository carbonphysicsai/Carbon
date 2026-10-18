# DEVELOPMENT construction receiver

This is the operator entrypoint for the existing `DirectRecipeIntake`, not a
second construction service. It serves the registered public
`synthetic-linear-field-2d` kit **1.3** or configured Battery **1.0**, with signed
staging/submit/status on the same
`/carbon/v1/mcp` route, and the existing durable reconstruction/inference tasks.
Every model uses this path. No model family, backbone or matrix-row selector is
part of the operator configuration.

The slice is loopback DEVELOPMENT only: chain signatures and registration are
checked, but chain commitments, official scoring, qualification and rewards are
not provided. HTTPS/Cloudflare exposure and an independent validator-owned
checkout remain separate work; this listener does not claim those properties.

## Installed prerequisites

Use the normal maintained installation and Compute/Review profile. Accepted-main
installation requires the exact clean accepted revision and bound worker
manifest. An explicitly installed DEVELOPMENT candidate retains its own exact
candidate source/build identity; it is not relabelled as accepted main. The
selected worker must pass the existing read-only Docker doctor. Build and
inference parents/accelerators retain their separately checked installed pins.

Per-recipe dependencies use the existing `.direct-development/library-cache`.
After authentic admission, a missing verified dependency overlay can be built
through the bounded offline PREP worker from the exact staged wheel closure.
No package download or participant network access is introduced. A positive
configured `material_cache_bytes` cap is required for that material/overlay
path; it also bounds retained partial uploads. Missing source, insufficient
capacity and unsupported runtime/export operations retain typed refusals. A
graph uses the normal worker parent. Do not edit accepted revisions, manifests,
profile labels or recipe identities to make old inputs appear compatible.

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
  "measure_query": true,
  "material_cache_bytes": 201326592
}
```

The displayed cache cap is an illustrative192MiB DEVELOPMENT storage choice,
not a training-resource or scientific policy. Configure it for the actual owned
capacity and declared material closure. The displayed JSON is a template;
serialize the actual object with the existing
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

## Explicit retry after infrastructure failure

An ordinary submit or status call keeps returning its original task. After a
real `FAILED_INFRA`, the Launchpad construction tools expose **Retry
infrastructure failure**. That explicit action submits the unchanged recipe
with `retry_of_submission_id` naming the failed task. It creates one new normal
attempt and preserves the original terminal task, receipt and worker history.
It is not a way to retry a scientific refusal or revive a cancelled task.

Discovery advertises this prospective extension as `construction_retry` with
schema `carbon.construction.infrastructure-retry.v1`. The existing submit tool
and ordinary fields remain unchanged; older receivers without that capability
are refused by an explicit retry client before signing. The maintained client
API is `submit_and_wait(..., retry_of=failed_task_id)`. It uses the same epoch,
with a separate predecessor-bound attempt journal. Subsequent observation of
that retry supplies the same predecessor and polls only the recorded child.
Ordinary status continues to query the original task.

The signed owner, Challenge kit, full recipe, TRAIN, interface, limits,
measurement mode and selected pack must match. Predecessor workers must be
settled; unknown cleanup or a remaining UV-copy helper refuses fresh work.
Existing resource admission and retained-task bounds apply to the new attempt.
An admitted child can be queried or replayed without starting another attempt.
A later genuine infrastructure failure can be retried explicitly in turn.

Each actual HTTP transmission has a fresh transport request ID. The candidate
and retry keys remain stable at the durable task provider, so reopening after
a lost admission reply creates no duplicate work. A network exception is not
silently retried. Keep the admission journal; never edit recipe/seed fields,
reset the task database or delete the failed record to force another run.

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
./scripts/dev/canonical.sh --focused tests/cpu/test_direct_receiver.py tests/cpu/test_direct_recipe_intake.py tests/cpu/test_direct_intake_source_staging.py tests/cpu/test_lean_recipe_adapter.py tests/cpu/test_direct_construction_retry_provider.py tests/cpu/test_lean_recipe_retry.py tests/cpu/test_direct_signed_retry.py tests/cpu/test_validator_retry_dispatch.py
```

The new loopback test uses authentic routing and durable workspace/task classes
with explicit fake verifier/snapshot/image fixtures, stops before dispatch and
refuses any attempted model run. It validates operator composition only.
Canonical source checks, accepted-source/image installation, a real signed
model build/inference, custody and independent validator evaluation remain
separate evidence states.
