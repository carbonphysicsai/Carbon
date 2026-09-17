# Launchpad DEVELOPMENT research bridge

Ticket: `.agent/tickets/C-MLP-02_development_research_bridge.md`.
Status: admission-disabled engineering integration; real campaign validation pending.

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

The accepted PR #206 C-W1-D4 `research_campaign` is the reused runner.
It owns public practice, the adaptive research loop, retained hypotheses and
capability requests, exact recipe freeze, independent final reconstruction and
existing report artifacts. Its accepted implementation is now integrated.
Its CLI currently exposes run/resume/status/report; that is not evidence of a
Launchpad-safe pause/stop contract. Its D4 resource grant cannot authorize a new
Launchpad campaign. No unrelated checkout or in-flight campaign is modified.

The bridge validates an accepted runtime, a campaign-specific
resource envelope, exact identity and worker ownership, durable dispatch and
cleanup/reconciliation before enabling launch. Only allow-listed existing report
projections may cross into the browser. A stopped process alone cannot establish
that owned compute stopped. Unknown cleanup must remain visible.

The real acceptance predicate remains at least two genuine research iterations,
retained unsuccessful attempts and measured usage, exact candidate freeze,
Carbon submission and independent reconstruction, actual receipt/disposition,
browser reconnect and verified stop of owned work. Engineering source fixtures
and browser readback fixtures do not satisfy that predicate.

## Trusted runner adapter

`--research-profile /absolute/private/profile.json` installs an operator-only
`carbon.launchpad.runner-profile.v1` record. Without it, research admission is
disabled. The record has exactly `schema`, `profile_id`, `principal`, `grant_file`,
`account_ref`, `enabled`, `paths` and `accepted_revision`. `paths` contains the
existing runner's seven file inputs: image_manifest, analysis_image_manifest,
operator_config, api_key_file, miner_public, miner_password_file and
quarantine_journal. Files must be absolute private operator inputs; browser
requests cannot install or replace them. The existing registered subnet-567 miner
is verified through the original trusted signing boundary before research.

New Launchpad campaigns select the accepted C-W1-D5 v2 continuation policy. The
runner freezes its prompt/tool identity; this does not transfer D5's separate
program grant. Legacy command defaults and existing campaign manifests remain
unchanged. Own-research records expose concise hypothesis history, decisions and
epoch stop reasons separately from verified independent DEVELOPMENT results.
Raw transcripts and internal accounting payloads are not browser projections.

The separate `carbon.launchpad.research-grant.v1` must explicitly be APPROVED,
with exact principal, miner, campaign/root, runtime/image identities, provider and
account reference, all resource dimensions, original lifetime and absolute expiry.
Only one campaign per grant is supported. The grant-derived run identity and
canonical root survive different browser retry keys and controller databases.
All operations remain charged by CampaignLedger; no Launchpad consumption ledger
exists. D4 v1 manifests are neither migrated nor assigned another allowance.
The approved limits may narrow the existing envelope but cannot exceed it or
remove its final reconstruction/cleanup reserve. Unknown usage stops new paid
dispatch. The runtime remains exact-clean-accepted and images source-matched.

The HTTP namespace `/api/v1/research` lists preflight and safe records; POST
accepts only `{ "profile": "operator-configured-opaque-id" }` plus an idempotency
key. `/api/v1/research/ID` re-resolves export; the pause, resume, stop and reconcile
subroutes accept only empty objects. The loopback session authorizes this local
operator's configured records. This is not a multi-user hosted authorization model.

Pause is a durable request and blocks new ledger admission, tool selection and
final submissions at cooperative boundaries. An in-flight bounded operation may
finish; PAUSED is not a training checkpoint. Stop persists first, requests
supported research-worker cancellation and resolves original cleanup journals.
Fixed final/reference calls can settle to their existing deadline. Unknown
provider, final or worker outcomes keep reservations and remain actionable as
RECONCILIATION_REQUIRED; operator reconciliation never retries them. A campaign
OS lock and durable generation prevent a second/stale controller dispatch.

The browser projects actual attempted operations, completed practice, own concise
hypotheses/capability requests, usage and frozen candidates. It never serves the
private owner HTML/JSON report. Final comparisons are resolved through existing
C-10/C-06/C-08 authority on every view/export, preserving every real disposition.
Current execution is labelled LIVE PRACTICE/RESEARCH, explicitly not qualified
LIVE. Historical attached evidence retains its separate label.

## Outstanding empirical acceptance

`MINER_LAUNCHPAD_VALIDATION_REQUEST.json` is the single REQUESTED_NOT_GRANTED
validation record. It is not an executable approval. Its requested USD0.50 / four
trial envelope includes the existing minimum final reserve of twelve replicas,
8,640,000 numerical milliseconds and eight selection/report calls. That headroom
does not guarantee successful reconstruction or sufficient total work. Actual
provider invoice limits are not inferred from token-cost estimates.

Merge the accepted admission-disabled engineering slice first, then build exact
source-matched images and install only a separately approved private grant. The
first browser-launched adaptive campaign remains C-MLP-02's selected acceptance;
controller tests, fixed jobs and D4's separately owned campaigns do not close it.

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
