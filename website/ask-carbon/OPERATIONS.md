# Ask Carbon staging, activation and rollback runbook

This runbook defines a fail-closed release seam. It does not authorize a
Cloudflare resource, route, public source release, privacy acceptance or
production deployment.

## Private target observed on 2026-09-17

The owner identified the existing website Cloudflare account as
`carbon.physics.ai@gmail.com`. The bounded evaluation created two resources in
that account:

- route-less shared budget authority: `carbon-ask-budget-authority`;
- private review Worker: `carbon-ask-private-staging` at
  `https://carbon-ask-private-staging.carbon-physics-ai.workers.dev`.

The preview and `/api/ask-carbon*` are protected by one rotated Basic access
secret installed in the Worker, while the ledger snapshot has a second rotated
operator secret. These are possession-based staging controls, not named-person
authentication. The Worker has no production homepage route. The responsible
operator for this bounded run is the owner-authorized Engineering session.
Disable by setting activation off or deleting only the private staging Worker;
the public homepage and route-less financial history are separate. No paid-plan
change or incremental Cloudflare charge was observed, but Cloudflare charges
remain outside the provider ledger and are not claimed as zero.

The OpenAI project used for the synthetic run showed API-call logging enabled
per call. No approved Zero Data Retention or Modified Abuse Monitoring control
was established. Use public/synthetic inputs only; this is not customer-data
processing authorization. Never place access or provider credentials in chat,
Git, browser bundles, issues or retained evaluation output.

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

1. Confirm the recorded private target, credentials, costs and rollback owner.
   Basic access is the current bounded staging gate; origin filtering remains
   defense in depth, not authentication.
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
