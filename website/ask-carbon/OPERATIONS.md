# Ask Carbon staging, activation and rollback runbook

This runbook defines a fail-closed release seam. It does not authorize a
Cloudflare resource, route, public source release, privacy acceptance or
production deployment.

## Discovered target state (2026-09-17)

The owning Cloudflare account is `Carbon.physics.ai@gmail.com's Account`
(`7462053c6992b9c9fd889952a7ae0496`). Production is the `carbonwebsite`
static-assets Worker created through manual Dashboard upload. It serves the
workers.dev hostname plus `carbonphysics.ai` and `www.carbonphysics.ai`; there
is no separate Worker route. Rollback is a prior Worker deployment selection or
`wrangler rollback`. A Worker rollback does not roll back Durable Object state.

WEB-QA-03 created route-less `ask-carbon-budget-authority` and the separate
`ask-carbon-eval-luna` / `ask-carbon-eval-terra` Workers on the account's Free
plan. Cloudflare Zero Trust checkout was not completed because it required a
new billing/overage authorization; private staging uses Worker-enforced Basic
Auth over TLS instead. Production resources, routes and DNS were not changed.

The concurrent Workbench evaluation also created a private review Worker at
`https://carbon-ask-private-staging.carbon-physics-ai.workers.dev` and a second
route-less ledger script, `carbon-ask-budget-authority`. That second ledger
retains its evaluation history but must not remain a second USD 50 admission
authority. The integrated configuration rebinds continuing callers to
`ask-carbon-budget-authority`; the superseded script remains inactive so its
historical financial exposure is not erased.

The preview and `/api/ask-carbon*` are protected by one rotated Basic access
secret installed in the Worker, while the ledger snapshot has a second rotated
operator secret. These are possession-based staging controls, not named-person
authentication. The Worker has no production homepage route. The responsible
operator for this bounded run is the owner-authorized Engineering session.
Disable by setting activation off or deleting only the private staging Worker;
the public homepage and route-less financial history are separate. No paid-plan
change or incremental Cloudflare charge was observed, but Cloudflare charges
remain outside the provider ledger and are not claimed as zero.

The evaluation Workers additionally accept a rotated
`ASK_CARBON_EVALUATION_ACCESS_SECRET` header only on
`/api/ask-carbon*`, only in staging, and only while evaluation telemetry is
enabled. It leaves the owner's browser Basic credential untouched and cannot
read static assets. Aggregate ledger reads still require the independent
operator secret. Rotate both evaluation secrets after a retained run or
suspected exposure; never copy either into evidence, Git, chat or browser
assets.

The OpenAI project used for the synthetic run showed API-call logging enabled
per call. No approved Zero Data Retention or Modified Abuse Monitoring control
was established. Use public/synthetic inputs only; this is not customer-data
processing authorization. Never place access or provider credentials in chat,
Git, browser bundles, issues or retained evaluation output.

The retained WEB-QA-03 homepage live-evaluation transcripts remain pinned to
knowledge `ask-carbon-staging-2026-09-16.1`. The release candidate advances
to `ask-carbon-release-candidate-2026-09-18.2` under the server-owned
reviewed-card selection contract and refreshes the dated progress explanation
against the same pinned, digest-matched Wave source. The frozen two-candidate
release split, affected-case rerun and exact pilot run are retained in
`evidence/WEB-QA-04.md`; prior evidence keeps its original source basis.

The release candidate remains `STAGING_REVIEWED`, has
`public_activation_allowed:false`, and is not retroactively substituted into
retained evidence. The owner approved the prepared visitor privacy posture and
the bounded private pilot-quality packet. Those approvals do not approve the
new knowledge release, production route, public activation or inquiry
collection. The exact release decision remains in
`PUBLIC_RELEASE_DECISION_PACKET.md`.

## Shared monthly budget authority

All evaluation, staging and production provider calls bind to one central
Durable Object script and the fixed name
`ask-carbon-provider-budget-v2`. Separate per-environment namespaces are
forbidden. Environment and operational scope remain distinct fields and
permissions; the `bakeoff` scope is durably fixed at 5,000,000 micro-USD while
the UTC calendar-month application ceiling is 50,000,000 micro-USD. The scope
caps sum within—not in addition to—the owner ceiling.

Both general Q&A and pilot-design guidance use this authority. Runtime controls
also include approved origins, an exact model/configuration registry, daily
request limits, global and per-client concurrency/rate limits, and bounded
pilot-design requests per session. Attempt states are:

Financial exposure and global concurrency are shared across environments.
Schema v3 stores immutable daily, per-client and pilot-session policies by
environment so private staging and production can use stricter abuse limits
without creating a second budget or changing the shared ceiling. The v2-to-v3
migration reconstructs counters from retained attempts and preserves every
settled and unresolved financial entry.

The closed concurrent `carbon-ask-budget-authority` history recorded 80,831
micro-USD of September `bakeoff` exposure: 13,151 settled and 67,680 unresolved.
That script is no longer an admission authority. The canonical ledger policy
durably reserves the full 80,831 micro-USD in period `2026-09` and scope
`bakeoff`, so neither a restart nor a caller migration can recreate the spent
allowance. After the complete WEB-QA-04 evaluation and combining the two
historical ledgers, September application exposure is 453,479 micro-USD and
the nested evaluation balance is 4,546,521 micro-USD. Do not remove or reduce
this offset; later exact reconciliation may
replace uncertain exposure only through a separately reviewed, idempotent
accounting migration.

```text
prepared -> dispatch_authorized -> settled
    |                |             settled_overrun (recorded, fail closed)
    |                +-----------> unresolved (conservative reservation retained)
    +---------------------------> released_pre_dispatch
```

The Worker reserves the worst-case configured input and output work before
dispatch, persists dispatch intent, performs one call only, and never retries,
hedges or falls back automatically. Confirmed pre-dispatch rejection releases
cost but retains request/abuse accounting. Timeout, crash, abort, invalid or
missing usage, model mismatch and possible-dispatch settlement failure retain
the reservation. Lease expiry releases scheduling concurrency, not financial
exposure. Late usage settles idempotently against the admission month; duplicate
attempt IDs and conflicting settlements reject.

Public `PILOT_DESIGN` drafting requires the approved visitor notice, explicit
AI enablement and the shared provider/abuse controls. It does **not** require an
inquiry receiver because this release offers only local editing and download.
Any future submit/receive control remains disabled until issue #139 supplies
and accepts the private receiver, persistence, staff access, retention,
notification and incident contracts. Form-only drafting must remain usable.
Do not log abandoned raw conversation text for sales/research analysis.
Inquiry response permission and optional broader reuse permission remain
separate.

## Routing and activation order

With current bounds (24,000 input and 700 output tokens), maximum reservations
are 5,640 micro-USD for Luna and 56,400 micro-USD for Terra. UTF-8 request bytes
plus an explicit framing allowance are used only as a conservative input-token
upper bound, never as an exact token count. Unsupported framing, usage or price
identity stops service. The application ledger does not cap unrelated account
invoices, Cloudflare charges or out-of-path API use; a dedicated project/key is
still recommended.

## Release and source updates

1. Recompute every local source SHA and inspect changed sections.
2. Invalidate or queue only affected cards. Do not silently republish changed
   source content or disable unrelated healthy topics.
3. Review disclosure, support, maturity, direct URLs, expiry and withdrawal.
4. Set `APPROVED_PUBLIC` and `public_activation_allowed:true` only through the
   authorized publication path. A merge to `main` is not approval.
5. Run `node tools/validate-knowledge.mjs --production` and preserve the exact
   reviewed manifest with its static bundle and continuation epoch.

Current-status material has a seven-day review window; network/product status
has a shorter window than stable conceptual explanations. Global withdrawal or
withdrawal-epoch change invalidates live activation, static fallback and old
continuations together.

## Private staging sequence

1. WEB-QA-03 uses Worker-enforced TLS Basic authentication because
   Cloudflare Zero Trust Free checkout requires a new overage-charge
   authorization. Provision the username/password only as Worker secrets;
   origin filtering is defense in depth, not authentication. Production mode
   rejects this staging-only access mode.
2. Deploy exactly one route-less shared budget authority from
   `wrangler.budget-authority.staging.toml`.
3. Bind evaluation and staging app Workers to that exact authority using
   `script_name`. Deploy with no production route and activation disabled.
4. Configure Cloudflare edge rate limiting/WAF for all request shapes, including
   malformed bodies. The Durable Object additionally enforces global monthly,
   daily, concurrency, per-client and operational-scope limits for valid
   requests. A hashed IP remains pseudonymous, not anonymous.
5. Provision the OpenAI key and continuation HMAC only as Worker secrets. Check
   the actual OpenAI project data controls; `store:false` is not zero retention.
   Provision evaluation-only access and operator-read credentials through the
   same secret mechanism; the live runner must not receive the browser Basic
   credential.
6. Run real Worker/DO tests: concurrent admission, restart, prepared and
   dispatched expiry, failed/late settlement, month rollover, source withdrawal,
   config/price mismatch and rollback. Preserve the ledger snapshot.
7. Run the frozen development cases on the selected configuration through the
   Worker within the shared USD 5 bakeoff cap. Preserve exact outputs for human
   review with `eval/QUALITY_RUBRIC.md`; do not infer a winner or readiness from
   unreviewed responses.

## Guided-pilot evaluation commands

The nine public/synthetic guided-pilot scenarios use the existing runner and
Worker contract:

```sh
npm run eval:pilot:plan
npm run eval:pilot:mock
npm run eval:pilot:evidence
```

These commands are local-only. Plan enumerates the exact finite request and
worst-case reservation; mock exercises the real Worker validator and shared
ledger with test-owned provider output; evidence writes the deterministic
transcript/review packet and digest manifest. None calls a provider or private
staging service.

The live writer is explicit and fail closed. Load secrets only from the
approved operator environment, then run:

```sh
node eval/write-pilot-live-evidence.mjs \
  --output-dir evidence/pilot-design-live-YYYY-MM-DD-vN \
  --run-id bounded-private-run-id
```

`ASK_CARBON_EVAL_ENDPOINT` must be the recorded private Worker,
`ASK_CARBON_EVAL_ORIGIN` its approved origin, and the Basic and operator
credentials must be present. `--case-ids` can select named affected cases for a
bounded follow-up. There are no retries or direct-provider calls. Preserve the
shared hourly/session/monthly controls rather than resetting them to complete a
run.

## Production release sequence

Production needs a separate exact owner authorization after the staging report:

1. approve the final privacy notice/provider processing and security review;
2. approve the exact knowledge/model/config and production target;
3. publish reviewed static assets and CSP without replacing homepage routing;
4. bind only `/api/ask-carbon*`, preserving `/` and `/workbench/`;
5. verify inactive health, route behavior, cache withdrawal and all ceilings;
6. explicitly enable activation and observe the first bounded requests.

> **Rebaseline, 2026-09-22.** The owner replaced the live site with the
> multi-page redesign on 2026-09-22 (Dashboard upload, 97 paths verified). The
> 18 September candidate's homepage pin (`5ebb43e8…`) and
> `--reconcile-owner-upload` no longer apply. Candidate
> `ask-carbon-public-release-2026-09-22.1` pins the redesigned homepage
> (`99be1318…`) and ships a **complete** baseline manifest generated from the
> site build directory `carbon-site-upload-v2.zip`. Build with:
>
> ```sh
> OUT=/tmp/ask-carbon-production-$(date -u +%Y%m%dT%H%M%SZ)
> node website/ask-carbon/tools/integrate-static.mjs \
>   --input /path/to/carbon-site-v2/index.html \
>   --output "$OUT/index.html" \
>   --asset-prefix ./ask-carbon \
>   --existing-site /path/to/carbon-site-v2 \
>   --require-complete-bundle
> ```
>
> The tool now also refuses `--require-complete-bundle` until
> `deployment_target_observed.live_version_id` in the manifest is the version
> id captured from `wrangler deployments list --name carbonwebsite`. The
> sections below describe the superseded 18 September procedure and are kept
> for the record.

For the approved 18 September inactive-publication candidate, extract the
owner-supplied ZIP into a temporary directory, verify its recorded archive and
`index.html` hashes, and build the static artifact with the repository tool:

```sh
node website/ask-carbon/tools/integrate-static.mjs \
  --input /path/to/extracted/index.html \
  --output /tmp/ask-carbon-production/index.html \
  --asset-prefix ./ask-carbon \
  --reconcile-owner-upload
```

The output `index.html` must hash to
`d897118ebd16a602994f3498ae8084f4a9ba908cee4aa6a7b8ef1650cc25da55`.

### The upload directory must be the complete site, not just the homepage

`carbonwebsite` is a Cloudflare **static-assets** Worker. A deployment replaces
the entire asset set: any path absent from the uploaded directory is withdrawn
from production. `integrate-static.mjs` writes only `index.html` and the
`ask-carbon/` assets, so deploying its output directory on its own would
delete the live Workbench route and the shared homepage images.

#### The asset inventory is not yet established

`production-baseline.manifest.json` records the SHA-256 digest and byte size of
every asset currently known to be deployed. It is marked
`"inventory_status": "incomplete"`, and `--require-complete-bundle` therefore
**refuses to certify any production bundle** until that changes.

That refusal is correct and must not be worked around. Downloading a list of
known public URLs retrieves verified bytes for the paths you already know; it
is a transport, **not an enumeration**. It cannot show that no other asset
exists. Two concrete demonstrations of why the previous wording was unsafe:

- `https://carbonphysics.ai/index.html` returns **307 → `/`** with an empty
  body, and `workbench/index.html` returns **307 → `/workbench/`**. A recipe
  that downloads the literal listed paths writes a **zero-byte `index.html`**,
  which the previous presence-only `fs.access` check accepted as "present".
- `workbench/atlas-source.json` (156,568 bytes, HTTP 200) is a live production
  asset that the old hard-coded path list omitted entirely. A bundle built
  against that list would have withdrawn it from production while reporting
  `"deployable_to_carbonwebsite": true`.

To complete the inventory, obtain the deployed asset set from the authoritative
source — the owner's current website source, or an authenticated
`carbonwebsite` asset enumeration after Cloudflare login. Capture the deployed
headers, redirects and asset-routing configuration as configuration, not as
inferred observations. Then set `inventory_status` to `"verified-complete"`
and record how it was established. Do not mark it complete by assumption, and
do not create placeholder files to satisfy the check.

Homepage source authority stays separate from these read-only production
observations: the homepage published by this bundle is the owner-supplied
upload reconciled by `--reconcile-owner-upload`, not the copy downloaded from
production.

#### Building the bundle

Place the verified current asset set in `/tmp/ask-carbon-current`. The
`--output` directory must be **fresh** — the tool refuses to build into a
directory that already contains anything, because stale files there can
survive assembly and be published. Use a new timestamped directory each time:

```sh
OUT=/tmp/ask-carbon-production-$(date -u +%Y%m%dT%H%M%SZ)
node website/ask-carbon/tools/integrate-static.mjs \
  --input /path/to/extracted/index.html \
  --output "$OUT/index.html" \
  --asset-prefix ./ask-carbon \
  --reconcile-owner-upload \
  --existing-site /tmp/ask-carbon-current \
  --require-complete-bundle
```

The tool verifies `--existing-site` against the manifest by exact content
digest and file metadata, rejecting missing files, empty files, content
mismatches, directories standing in for files and symlinks. It assembles into
an isolated staging directory, re-verifies the bytes actually staged, and only
then moves the result into `$OUT`. A failed build leaves no partial bundle.

Deployment requires the emitted JSON to show all of:

```text
"baseline_inventory_complete": true
"baseline_assets_preserved":   true
"deployable_to_carbonwebsite": true
```

`bundle_identity_sha256` is the identity of the staged bytes; record it and
re-derive it from disk before deploying. `--staging-preview` and
`--allow-changed-source` produce inspection artifacts only: they always report
`"deployable_to_carbonwebsite": false` and are never deployable.

#### Deploy the inactive API Worker first

**Order matters.** Deploy the inactive `ask-carbon-public` Worker *before*
publishing the `carbonwebsite` assets, not after.

The integrated homepage fetches `${api-url}/health` on load (see
`public/ask-carbon.js`). Publishing the static assets first means every
homepage visitor requests a route that does not exist yet, so the whole gap
between the two deployments produces 404s — and during exactly the window the
inactive verification is meant to check, "not deployed" is indistinguishable
from "deployed and inactive". Deploying the Worker first means the health
endpoint answers correctly from the moment the homepage ships.

The Worker binds only `/api/ask-carbon*`, which returns 404 today, so adding
it ahead of the homepage is low-risk and reversible. This supersedes any
earlier sequence that listed `carbonwebsite` first.

```sh
npx wrangler deploy --config wrangler.public-release-candidate.toml
```

Then publish the assets. The current `carbonwebsite` Worker uses compatibility
date `2026-09-12`; retain it for this asset-only update:

```sh
npx wrangler deploy \
  --name carbonwebsite \
  --assets "$OUT" \
  --compatibility-date 2026-09-12
```

After deploying, re-verify `/`, `/workbench/`, both `/assets/*.png` and
`/workbench/atlas-source.json` on both hostnames before treating the
publication as complete. A 404 on any of them means the upload was incomplete;
roll back immediately.

### Deployment prerequisites are separate gates

The named-owner gate below is satisfied. That gate alone does **not** make this
deployment ready. Each of the following is a distinct prerequisite with its own
evidence:

| Prerequisite | Status as of 2026-09-20 |
| --- | --- |
| Named incident/rollback owner recorded | Satisfied (`WEB-QA-05-D2`) |
| Cloudflare deployment credentials for the Carbon account | Satisfied — OAuth session for `carbon.physics.ai@gmail.com`, account `7462053c6992b9c9fd889952a7ae0496`, with `workers`/`workers_scripts`/`workers_routes` write |
| Pinned deployment tool | Satisfied — Wrangler `4.134.0` (see below) |
| Complete verified production asset inventory | **Not established** — `inventory_status: "incomplete"`; needs the owner's website archive |
| Required Worker secrets present and bound | **Not verified** |
| CI / release verification for the repaired revision | Per `.agent/DELIVERY_PROTOCOL.md` |
| Recorded pre-deployment rollback target | **Must be re-captured immediately before deploying** |

Satisfying the owner gate does not satisfy any of the others, and asset
completeness is not release authorization: publication and public activation
remain governed by `PUBLIC_RELEASE_CANDIDATE.json` and the recorded owner
decisions.

### Deployment tooling

The deployment CLI is pinned and installed outside the repository, so it never
enters the public asset tree and never alters the repository's own dependency
pins:

```sh
# ~/.local/lib/carbon-wrangler/package.json pins "wrangler": "4.134.0"
WRANGLER="$HOME/.local/lib/carbon-wrangler/node_modules/.bin/wrangler"
"$WRANGLER" --version   # 4.134.0
"$WRANGLER" whoami      # verify the account before any mutation
```

`4.134.0` matches the version already used against this account. Do not
substitute an implicit `latest`, and do not change the Worker's accepted
compatibility date merely to satisfy a newer CLI.

Wrangler stores its OAuth credentials in the user configuration directory
(`~/Library/Preferences/.wrangler/config/` on macOS). Never copy that file, a
token, or a device code into the repository, a PR, or any evidence record.

### The remaining owner action

One thing is outstanding before a production deployment can be certified:

> **Supply the website archive most recently uploaded to the `carbonwebsite`
> Cloudflare Dashboard.**

The live version (`5a44ab03-ce7c-4100-ae42-71843b07246a`, version 17) has
`source: "dash"`, so it was uploaded through the Dashboard rather than built
from repository state. That archive is therefore the authoritative asset set.
Cloudflare login does not substitute for it: Wrangler 4.134.0 provides no
command that lists a static-assets Worker's deployed files, so the deployed set
cannot be enumerated from the platform side. This is a capability gap, not a
credentials gap.

Once the archive is supplied, reconcile it against the verified digests in
`production-baseline.manifest.json`, add every additional path it contains,
and only then set `inventory_complete` to `true`.

The incident owner and authorized disable/rollback operator are recorded under
"Named production operators" below, so this deployment is unblocked. Static
publication still does not authorize the separate activation step.

## Activation: three gates, two files

Activation is not one flag. A visitor receives an answer only when all three
of these hold, and the inactive publication deliberately fails all three:

| Gate | Where | Inactive value |
| --- | --- | --- |
| `ASK_CARBON_ACTIVATION` | Worker config `[vars]` | `disabled` |
| `release.status` | `knowledge/public-knowledge.v1.json` | `STAGING_REVIEWED` |
| `release.public_activation_allowed` | same file | `false` |

The two knowledge gates are enforced by `public/release-contract.js`. They
exist so that authorizing a *release* cannot by itself publish *answers*: the
content needs its own recorded approval. Check them by reading the health
body, which lists every unmet gate by name:

```sh
curl -s https://carbonphysics.ai/api/ask-carbon/health
```

`"reasons": ["activation_disabled"]` alone means the content is approved and
only the Worker flag is holding it back. Additional `release_not_approved_public`
or `public_activation_not_allowed` entries mean the knowledge record has not
been approved for public display.

### Do not enable activation in the candidate config

`wrangler.public-release-candidate.toml` must keep `ASK_CARBON_ACTIVATION =
"disabled"`, because redeploying it is the fail-closed incident response in the
next section. Editing it to enable activation would silently turn the emergency
disable command into a no-op.

Activation deploys a separate file instead:

```sh
cd website/ask-carbon
npx wrangler deploy --config wrangler.public-release-active.toml
```

The two configs differ in exactly one line, which a test asserts. Changing the
knowledge record additionally changes the bundle, so the static assets must be
rebuilt and redeployed as well; the resulting bundle identity will not match a
bundle approved before the knowledge changed, and needs its own decision.

### To disable again

Redeploying the candidate config is the fastest disable and does not touch the
static assets:

```sh
npx wrangler deploy --config wrangler.public-release-candidate.toml
```

Rolling the static bundle back is a separate action with a different effect:
it restores the previous asset set, including whichever knowledge record that
bundle carried.

## Incident disable and rollback procedure

### Named production operators

The repository owner recorded these identities on 2026-09-19 in
`.agent/DECISIONS.md` as `WEB-QA-05-D2`. They are owner-supplied, not inferred
from repository or Cloudflare account access.

| Role | Named people |
| --- | --- |
| Production incident owner | Ryan Bequette, Nick Fitzpatrick |
| Authorized disable and rollback operator | Ryan Bequette, Nick Fitzpatrick |

**Either named operator may act independently.** Disabling or rolling back Ask
Carbon does not require both people, a quorum, or a second approval. Neither
identity may be substituted or extended by an unnamed holder of account
access, and these roles authorize only this Ask Carbon release.

This satisfies the `required_before_production_mutation` gate in
`PUBLIC_RELEASE_CANDIDATE.json`. Publication of the inactive bundle is
therefore unblocked; the separate public enable step remains its own recorded
decision.

The first response to a suspected disclosure, spend, provider, source or
answer-integrity incident is a fail-closed Worker deployment from the reviewed
release checkout:

```sh
cd website/ask-carbon
npx wrangler deploy --config wrangler.public-release-candidate.toml
curl --fail-with-body --silent --show-error \
  -H 'Origin: https://carbonphysics.ai' \
  https://carbonphysics.ai/api/ask-carbon/health
```

The committed candidate sets `ASK_CARBON_ACTIVATION=disabled`; the health body
must report inactive before any further investigation. Do not put a secret in
the command line or shell history. If the API route itself must be withdrawn,
the named Cloudflare operator removes only the two `/api/ask-carbon*` route
bindings in the Dashboard or rolls back `ask-carbon-public` to its recorded
inactive version. This must not delete or replace the shared
`ask-carbon-budget-authority` Durable Object.

If the homepage bundle must be withdrawn, roll back to the version that was
actually live immediately before this deployment. **Capture that version ID as
a pre-deployment step** — do not reuse an ID written in an older revision of
this runbook, which may no longer be the current predecessor:

```sh
# BEFORE deploying: record the current live version as the rollback target.
npx wrangler deployments list --name carbonwebsite
```

Record the resulting version ID and the configuration in force with it
(compatibility date, routes, asset set) alongside the build's
`bundle_identity_sha256`. Roll back to that captured ID:

```sh
npx wrangler rollback <captured-pre-deployment-version-id> \
  --name carbonwebsite
```

Authenticated inspection on 2026-09-20 showed the version actually serving
100% of traffic is **`5a44ab03-ce7c-4100-ae42-71843b07246a`** (version 17,
created 2026-09-12, compatibility date `2026-09-12`, no bindings).

`b99c37f0-c2d2-432b-842a-00b9fb518d96` was recorded in an earlier revision of
this runbook as the rollback target. It is **two deployments older** than the
live version and is **not** the current predecessor. It is retained as
historical evidence only. This is exactly why the target must be re-captured at
deploy time rather than read from a document — including from this paragraph. The owner must still
provide the latest uploaded website ZIP/source so its relationship to the
Dashboard deployment and asset set can be reconciled before production
mutation. After rollback, verify both approved hostnames,
`/workbench/`, CSP/assets, API inactivity and the preserved ledger snapshot.
Worker/static rollback never means Durable Object rollback.

## Rollback

1. Set `ASK_CARBON_ACTIVATION=disabled`; verify health is inactive.
2. Remove the API route while retaining ledger/audit records.
3. Remove the stylesheet, custom element and module tag; republish the original
   homepage and purge only affected assets.
4. Verify `/`, `/workbench/`, headers and absence of provider calls.
5. Preserve the released manifest and withdrawal/incident reason. Do not erase
   unresolved financial exposure or rewrite historical evidence.
