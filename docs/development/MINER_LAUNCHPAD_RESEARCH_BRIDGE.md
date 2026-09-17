# Launchpad DEVELOPMENT research bridge

Ticket: `.agent/tickets/C-MLP-02_development_research_bridge.md`.
Status: partial implementation; real campaign launch is not enabled.

## Existing receipt attachment

The local operator can attach a source handoff created by Carbon's existing
DEVELOPMENT pipeline. Use the Linux environment with the locked `chain`, `archive`
and `science-jax` groups installed. Carbon's secure registry/source fixtures do
not run on native Windows; the rehearsal controls remain host-portable.

```sh
uv run --locked --group chain --group archive --group science-jax python \
  scripts/dev/miner_launchpad/controller.py \
  --state-dir /absolute/private/launchpad \
  --development-source /absolute/private/session/source-SUBMISSION.json
```

Supply the actual existing handoff filename. No wallet is opened, transaction
issued, inference requested or numerical work launched by attachment. Keep the
listener on loopback. The source handoff and all its source-owner journals and
exports must remain available in their existing layout.

Attachments persist in the controller database across browser and controller
restarts. Repeating the same attachment returns its original opaque identity.
A changed source cannot silently replace an existing attachment. The HTTP API
does not accept source paths or attachment requests. The local session token
authorizes access to the operator's attached public projections only.

Each read resolves the existing handoff, bounded export, C-06 signature and
current receipt lifecycle, and C-08 authenticated submission association. The
display and JSON export contain exactly C-07's existing public projection plus
Launchpad attachment metadata. No private source directory, seed, case manifest,
measurement array, transport context, verification key or signing material is
served. Export rechecks the source rather than downloading stale browser state.
Invalid, revoked, missing or changed sources become `READBACK_UNAVAILABLE`; the
UI hides their receipt. This is a readback failure, not a new scientific result.

An attached receipt is explicitly labelled `OPERATOR_ATTACHED_EXISTING_SOURCE`.
It does not count as a Launchpad campaign, practice iteration or improvement.
`COMPLETE_UNRESOLVED` remains Carbon's unresolved DEVELOPMENT disposition.
This slice does not derive a comparison, rank candidates or create a receipt.

## Real campaign integration dependency

The concurrently implemented C-W1-D4 `research_campaign` is the intended runner.
It owns public practice, the adaptive research loop, retained hypotheses and
capability requests, exact recipe freeze, independent final reconstruction and
existing report artifacts. It is not yet an accepted dependency at this slice.
Its CLI currently exposes run/resume/status/report; that is not evidence of a
Launchpad-safe pause/stop contract. Its D4 resource grant cannot authorize a new
Launchpad campaign. No unrelated checkout or in-flight campaign is modified.

The remaining bridge must validate an accepted runtime, a campaign-specific
resource envelope, exact identity and worker ownership, durable dispatch and
cleanup/reconciliation before enabling launch. Only allow-listed existing report
projections may cross into the browser. A stopped process alone cannot establish
that owned compute stopped. Unknown cleanup must remain visible.

The real acceptance predicate remains at least two genuine research iterations,
retained unsuccessful attempts and measured usage, exact candidate freeze,
Carbon submission and independent reconstruction, actual receipt/disposition,
browser reconnect and verified stop of owned work. Engineering source fixtures
and browser readback fixtures do not satisfy that predicate.

## Focused verification

```sh
CARBON_UV_GROUPS="chain archive science-jax" ./scripts/dev/canonical.sh --focused \
  tests/cpu/test_miner_launchpad_development.py tests/cpu/test_miner_launchpad.py -q
python scripts/dev/miner_launchpad/browser_smoke.py
node --check scripts/dev/miner_launchpad/app.js
```

The browser test uses a real local HTTP server and Chromium. Its deliberately
injected readback records exercise rendering/export/invalidation only. Canonical
Python tests separately resolve signed authenticated engineering sources through
the actual Carbon owners, including revocation and corruption failures.
