# WEB-QA-03 private-staging evidence

**Evidence date:** 2026-09-17
**Branch:** `agent/web-qa-03-private-staging`
**Base:** `2fd842be8594a51cebde5b3f372bf23987a8cd30`
**Production candidate:** none; both evaluated configurations failed the frozen
final reliability requirement.

This record distinguishes real Cloudflare/OpenAI evidence from local contract
tests. It is not production authorization, scientific/security qualification,
or proof that every possible answer is factually correct.

## Authenticated hosting discovery

The correct Cloudflare account is `Carbon.physics.ai@gmail.com's Account`,
account identifier `7462053c6992b9c9fd889952a7ae0496`. The zone
`carbonphysics.ai` and Worker `carbonwebsite` are present in that account.

`carbonwebsite` is a static-assets-only Cloudflare Worker created through the
manual Dashboard upload workflow. Its domains are
`carbonwebsite.carbon-physics-ai.workers.dev`, `carbonphysics.ai`, and
`www.carbonphysics.ai`; no separate Worker route is configured. The deployment
history retains prior versions, which can be selected in the Dashboard or by
`wrangler rollback`. A code rollback does not roll back Durable Object state.

The account's Workers plan reported **Free / USD 0** and free SQLite Durable
Object quotas sufficient for this bounded evaluation. No plan upgrade, paid
Zero Trust checkout, DNS change, custom-domain change, production deployment,
or new Cloudflare monetary commitment occurred.

## Private staging

Cloudflare Zero Trust onboarding was stopped because its final checkout asked
for billing details and authorization for usage above the included allowance.
Private staging instead uses Worker-enforced HTTP Basic authentication over
TLS, staging-only runtime checks, origin checks, a Cloudflare rate limiter, and
the shared application budget authority. Origin checks remain defense in
depth, not authentication.

Deployed resources:

- `ask-carbon-budget-authority`: route-less Worker with SQLite Durable Object
  `AskCarbonUsageLedger`; `workers_dev=false`.
- `ask-carbon-eval-luna`: private evaluation Worker at
  `https://ask-carbon-eval-luna.carbon-physics-ai.workers.dev`; final staged
  code version `15ec9f6d-88de-4912-bbc9-55f3852bc971`.
- `ask-carbon-eval-terra`: owner-review Worker at
  `https://ask-carbon-eval-terra.carbon-physics-ai.workers.dev`; final staged
  code version `57d86d09-4c43-44f2-83e2-5bfd1bf7bec0`.

Both evaluation Workers bind the same `AskCarbonUsageLedger` namespace and the
same durable `bakeoff` scope. The staged UI uses the existing homepage assets
and integrated dependency-free component; it is not an iframe or replacement
application.

The username and password are Cloudflare secrets. A file-based first upload
retained a trailing line ending, which curl-based automation had stripped but
native browser Basic Auth did not. The browser-compatible staging credential
was rotated and re-uploaded without the line ending. The credential is not in
Git, chat, PR text, logs, or evidence artifacts.

## OpenAI project and data controls

A dedicated OpenAI project named `Ask Carbon` was created with project ID
`proj_Ynh55Gns3IJ23Fn5MygQ5HaX`. It is separate from the existing default,
Workbench, and testnet-agent use. Its final active key is independently
rotatable, expires on 2026-10-17, and is restricted to model requests; it is
stored only as the `ASK_CARBON_OPENAI_API_KEY` Cloudflare secret on the two
evaluation Workers.

Credential-handling correction: the first generated key was displayed by an
accessibility readback during provisioning. It was immediately revoked and was
never used. A second key transferred as an empty browser clipboard value and
was also revoked. The final key was transferred directly to a mode-0600
temporary file, uploaded to Cloudflare secrets, and the local transfer file was
deleted without printing the key.

Account/project controls observed before the first live request:

- project data retention showed `None` (no project override);
- API call logging was enabled per call, while this Worker sends `store:false`;
- feedback, eval, fine-tuning, API input, and API output sharing were disabled;
- the OpenAI Logs view showed no stored evaluation responses.

These facts do **not** establish Zero Data Retention. OpenAI's published API
policy states that API data is not used for training unless the organization
opts in and that abuse-monitoring logs may be retained for up to 30 days by
default. `store:false` disables response storage for the request; it is not a
claim that all provider retention is zero.

## Live provider compatibility corrections

The first compatibility smoke reached OpenAI but both candidates returned HTTP
400 `invalid_json_schema`: the Responses API structured-output subset rejected
`uniqueItems`. The application retained duplicate-ID validation and removed
the unsupported schema keyword. Those possible-dispatch attempts returned no
usage and remain conservatively unresolved in the application ledger.

Subsequent live output showed that a static string schema allowed models to
return card IDs where passage IDs were required. The Worker now constructs
request-specific enums containing only the retrieved passage and source IDs,
then applies the existing application support checks. The pilot source
allowlist was also corrected to derive source IDs from card passages. No
provider retry, hedge, model fallback, tool, or model-selected URL was added.

## Frozen final bakeoff

Both configurations received the same frozen split: 20 single-turn cases and
four conversations containing 12 turns, for 32 backend requests each. Three
requests per model produced deterministic `insufficient_evidence` outcomes
without provider work; 29 requests per model reached OpenAI through the real
Worker and shared ledger.

| Measure | Luna | Terra |
| --- | ---: | ---: |
| Configuration | `gpt-5.6-luna:low:v1` | `gpt-5.6-terra:low:v1` |
| Supported answers delivered | 5/32 (15.6%) | 13/32 (40.6%) |
| Correct typed no-evidence outcomes | 3/32 (9.4%) | 3/32 (9.4%) |
| Service failures after provider work/validation | 24/32 (75.0%) | 16/32 (50.0%) |
| Accepted provider outputs | 5/29 (17.2%) | 13/29 (44.8%) |
| Median end-to-end latency | 3,647 ms | 3,288 ms |
| p95 end-to-end latency | 12,725 ms | 5,564 ms |
| Maximum end-to-end latency | 13,349 ms | 6,253 ms |
| Accepted-output input tokens | 5,751 | 16,222 |
| Accepted-output cached input tokens | 0 | 1,472 |
| Accepted-output output tokens | 711 | 1,548 |
| Accepted-output exact cost | USD 0.002006 | USD 0.048371 |
| Exact ledger increase for the final run | USD 0.012663 | USD 0.115193 |

The exact ledger increase includes billed provider responses later rejected by
application semantic validation; the accepted-output cost does not. Luna's
single-turn failures included 13 `unsupported_claim` and two
`unmapped_answer_claim` outcomes. Terra's included nine and four respectively.
The older conversation artifact did not retain failure codes per failed turn;
the runner now does so for future runs. Failures were retained, not edited into
passes.

Manual source-grounded review applied the frozen rubric in
`eval/QUALITY_RUBRIC.md`. All five Luna supported answers and all 13 Terra
supported answers were direct, relevant to their cited pinned passages,
maturity-accurate, and free of observed critical disclosure, credential,
invented-launch, false-customer, or qualification-inflation defects. This is a
review of delivered supported answers, not a certificate for unanswered cases.

Terra alone completed the full owner-requested four-turn training/reference
conversation, including the topic switch, with supported answers. Luna
completed only the final reference-source turn. Other final conversations had
one or more service failures. Because the frozen rubric requires acceptable
final answers rather than silent server rejection, **neither model clears the
production-candidate threshold**. Terra is the more useful staging diagnostic,
but no model/configuration is selected for production.

Raw retained artifacts:

- `live-luna-final.json`
- `live-terra-final.json`

## Budget and real Durable Object evidence

The real shared Durable Object's final recorded state after compatibility,
development, final evaluation, abort, rollback, and concurrency checks was:

- monthly ceiling: 50,000,000 micro-USD (USD 50.00), UTC calendar month;
- nested `bakeoff` ceiling: 5,000,000 micro-USD (USD 5.00);
- exact settled cost: 135,374 micro-USD (USD 0.135374);
- unresolved possible-dispatch exposure: 78,960 micro-USD (USD 0.078960);
- conservative total exposure: 214,334 micro-USD (USD 0.214334);
- remaining `bakeoff` balance: 4,785,666 micro-USD (USD 4.785666);
- remaining September application balance: 49,785,666 micro-USD
  (USD 49.785666);
- attempts: 79 total: 68 settled, six released pre-dispatch, five unresolved;
- active attempts after expiry/recovery: zero.

Real Cloudflare observations:

- both environments accumulated against one monthly/scope authority;
- a client abort after dispatch authorization first left one active reservation,
  then released the slot at lease expiry while retaining the 5,640 micro-USD
  unresolved exposure;
- a five-request same-client burst admitted two and rejected three with
  `usage_limit`, exercising the per-client concurrency boundary; the global
  limit remained four;
- kill-switch deployment returned inactive health; `wrangler rollback` restored
  the prior Luna code version while Durable Object exposure persisted;
- unauthenticated access returned 401; correct authentication with a wrong
  Origin returned 403; authenticated health returned 200;
- no automatic provider retry or fallback occurred.

Cloudflare cannot safely time-travel a live Durable Object to a future UTC
month or force OpenAI to return malformed usage. Generated state-machine tests
cover exact month rollover, duplicate/late settlement, missing/negative usage,
restart, abandoned attempts, exact boundaries, and cross-environment ceilings;
those cases remain local deterministic evidence rather than claimed live
Cloudflare observations. Source withdrawal, knowledge expiry, continuation
invalidation, and UI request races are likewise covered by contract/browser
tests and were not manufactured against the live knowledge release.

Snapshots:

- `runtime-ledger-after-abort.json`
- `runtime-ledger-final.json`

## Browser and accessibility evidence

The authenticated static root and API were verified over the real workers.dev
hostname, including TLS Basic Auth, security headers, activation health,
correct-Origin enforcement, and the integrated asset paths. Native Safari's
HTTP authentication prompt was exercised. Automated browser control could not
reliably paste a secret into Safari's secure native field, so a complete
post-auth native Safari/VoiceOver session is not claimed.

The real staged static response returned `private, no-store`, a same-origin
connection policy, `frame-ancestors 'none'`, `X-Frame-Options: DENY`,
`nosniff`, no-referrer and a restrictive permissions policy. The legacy static
homepage requires inline script/style allowances; production CSP tightening is
a separate review rather than a claim that those allowances are ideal.

WEB-QA-02's local page checks still cover desktop Chrome, a 390x844 responsive
viewport, keyboard operation, source expansion, maturity rendering, loading
and error states, overlapping requests, topic switching, and horizontal
overflow. They are regression evidence for the same assets, not a substitute
for the owner's hands-on private-staging review. Hands-on VoiceOver remains
unexecuted.

## Production boundary and recommendation

The production Worker `carbonwebsite`, production DNS/domains, homepage assets,
and routing were not changed. A final fetch returned HTTP 200, 5,774,725 bytes,
SHA-256 `5ebb43e859e9837f74bbc93b5748b2db95a6700821afbfcecb407e75702e2020`;
production `/api/ask-carbon` remained 404.

Do not release Ask Carbon to production from this ticket. The next engineering
step is to repair structured-output reliability against the retained failures,
then rerun the same frozen acceptance split through the shared ledger. A later
owner release decision should name the exact passing model/configuration,
knowledge release, production Worker integration, privacy text, and rollback
version. Merge of this evidence is not that authorization.
