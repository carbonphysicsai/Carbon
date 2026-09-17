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
knowledge `ask-carbon-staging-2026-09-16.1`. The reconciled private staging
Workers now serve validated knowledge `ask-carbon-staging-2026-09-18.1` under
the server-owned reviewed-card selection contract. A two-candidate
compatibility smoke was run on that successor; it does not rewrite the prior
bakeoff source basis or constitute the pending frozen final evaluation.

Current main now carries `ask-carbon-staging-2026-09-17.4`. It remains
`STAGING_REVIEWED`, has `public_activation_allowed:false`, and was not silently
substituted into either retained live-evaluation basis. The owner approved the
bounded private pilot-quality packet after PR #203; that disposition does not
approve this newer knowledge release, general-Q&A model selection, privacy or
security, production routing, public activation, or inquiry collection. The
exact next owner decisions are collected in
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

The closed concurrent `carbon-ask-budget-authority` history recorded 80,831
micro-USD of September `bakeoff` exposure: 13,151 settled and 67,680 unresolved.
That script is no longer an admission authority. The canonical ledger policy
durably reserves the full 80,831 micro-USD in period `2026-09` and scope
`bakeoff`, so neither a restart nor a caller migration can recreate the spent
allowance. After the WEB-QA-04 compatibility work and combining the two
historical ledgers, September application exposure is 299,802 micro-USD and
the nested evaluation balance is 4,700,198 micro-USD. Do not remove or reduce
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

Before enabling public `PILOT_DESIGN`, accept the exact public notice and
private inquiry receiver. The private synthetic project observation above does
not settle that release decision. AI consent must precede the first request;
form-only drafting must
remain usable. Do not log abandoned raw conversation text for sales/research
analysis. Inquiry response permission and optional broader reuse permission
must remain separate.

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

## Rollback

1. Set `ASK_CARBON_ACTIVATION=disabled`; verify health is inactive.
2. Remove the API route while retaining ledger/audit records.
3. Remove the stylesheet, custom element and module tag; republish the original
   homepage and purge only affected assets.
4. Verify `/`, `/workbench/`, headers and absence of provider calls.
5. Preserve the released manifest and withdrawal/incident reason. Do not erase
   unresolved financial exposure or rewrite historical evidence.
