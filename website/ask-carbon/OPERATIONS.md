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

Before enabling `PILOT_DESIGN`, verify the exact public notice against the
actual Carbon OpenAI account retention configuration and the private inquiry
receiver. AI consent must precede the first request; form-only drafting must
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
   `wrangler.budget-authority.example.toml`, after cost authorization.
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
7. Run development cases on Luna and Terra through the Worker within the shared
   USD 5 bakeoff cap. Freeze configuration, then run the final split and score
   with `eval/QUALITY_RUBRIC.md`. If neither meets the rubric, keep disabled.

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

`npm run eval:pilot:live` is intentionally fail-closed while this runbook has
no exact private target or accepted access mechanism. After the inputs in the
private staging sequence are actually recorded, the live path must be bound to
that exact authenticated Worker and central ledger before it is enabled. Do not
substitute a direct provider call or Origin header for private access.

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
