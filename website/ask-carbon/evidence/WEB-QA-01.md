# WEB-QA-01 implementation evidence

**Evidence date:** 2026-09-16

**Branch:** `agent/web-qa-01-public-answer-bot`

**Base/main inspected:** `a5a520166e97268ec32e546b12edcd448e46d210`

## Repository and serving inspection

- Fresh `origin/main` exactly matched the package-pinned snapshot. GitHub
  access exposed only `carbonphysicsai/Carbon`; no separate website repository,
  `Carbon_Ask_v1`, `/api/ask-carbon`, WEB-QA ticket, 31-card set or supplied
  live evaluation cases was found.
- During delivery, `origin/main` advanced first to
  `94762b6a8932ac6834c731a416c3a45c4cbf6170` and then to
  `1d7be31dde94d43ae559818894c79c8e99d126b2`. Both revisions were merged
  normally into the WEB-QA-01 branch; their concurrent Workbench, Wave-C,
  prediction-staging and worker changes were preserved.
- `https://carbonphysics.ai/` and `https://www.carbonphysics.ai/` served a
  dependency-free single static HTML document through Cloudflare. The observed
  root document was 5,774,725 bytes and SHA-256
  `5ebb43e859e9837f74bbc93b5748b2db95a6700821afbfcecb407e75702e2020`.
  It matched the saved Workbench input snapshot byte-for-byte. This proves a
  content match, not deployment-repository ownership.
- The production branch, static build source/output directory, Cloudflare
  project and route configuration could not be established. The accessible
  Cloudflare dashboard required sign-in. The observed live response identified
  Cloudflare and did not include a Content-Security-Policy header.
- The live `/api/ask-carbon` route returned 404 during inspection. No existing
  route was changed.

## Implemented and reused

- KEEP: exact existing homepage bytes and `/workbench/` route.
- WRAP: one dependency-free `<ask-carbon>` custom element, one external
  stylesheet and one module script, injected by a SHA-pinned static integration
  tool. No iframe, second framework, CRM or homepage rewrite.
- REPAIR: the supplied visual direction was translated into the existing
  off-white/black/vermilion system with a compact header, four mobile topic
  cards, persistent composer, visible preview state and full “New chat” action.
- NEW bounded server seam: exact `/api/ask-carbon` and
  `/api/ask-carbon/health` Worker routes, fixed OpenAI Responses endpoint,
  server-only credentials, no tools, `store:false`, strict JSON Schema output,
  source-ID allowlist and server-side URL mapping, signed 180-second bounded
  context, publication/expiry gates and a persistent account-global Durable
  Object ledger.
- The ledger serializes request/cost reservation, enforces global daily request
  and micro-USD ceilings, global/client concurrency and a per-client hourly
  ceiling, expires abandoned leases, survives object restart and settles actual
  token usage when trustworthy counts return. A failed or malformed provider
  attempt is charged conservatively at its reserved maximum rather than
  silently undercounted. Prices and every ceiling are explicit required
  configuration; there is no silent model or price default.
- The draft manifest contains 11 preview cards grounded in current already-
  public sources. It explicitly records `expected_count: 31`,
  `received_count: 0` and is not a replacement for the missing package.

## Commands and measured results

```text
cd website/ask-carbon && npm test
23 tests passed, 0 failed
```

Coverage includes activation/rollback, origins, body/context/secret bounds,
signature tamper/expiry, provider schema, unknown-source rejection, fixed URL
mapping, no tool exposure, cost arithmetic, request/cost/concurrency/client
limits, ledger restart/expiry/settlement, integration preservation, CSP hashes,
knowledge release rejection, saved retrieval, prompt injection and thread reset
races.

```text
npm run validate
valid=true; 11 cards; 3 sources; warning=31 candidate cards missing

node tools/validate-knowledge.mjs --production
expected failure: knowledge not approved; release date missing; release missing
or expired; 31-card review incomplete

npm run eval:mock
5/5 placeholder cases passed support, citation relevance, maturity accuracy and
usefulness; measured handler latency 0.032–8.376 ms; cost USD 0

find website/ask-carbon ... | xargs node --check
all JavaScript modules parsed successfully

Development Hub source/render validation
91 generated files current; 134 events after the required repin;
0 validation errors; 84 validator tests passed; 14 static, 13 interactive and
5 living-state route checks passed; desktop/mobile JavaScript-on/off browser
smoke and mobile navigation accessibility passed in Chrome
```

The five evaluation cases are author-created local contract cases, not the
missing supplied live suite. The provider is saved deterministic explanations;
this is not live-model quality evidence.

The integration tool accepted only the inspected homepage SHA and produced:

```text
integrated index SHA-256:
781c236382aa9ee88f194c19705d410a3ff1f09d6d24a3b98e31cb9b66e9c2f3
```

The CSP tool found one existing inline script and one existing inline style,
generated exact SHA-256 directives, used no `unsafe-inline`, and refused inline
event handlers. The policy is candidate configuration only because the actual
deployment repository is unknown.

## Browser and accessibility evidence

- Local integrated page opened at desktop 1280×720 and responsive 390×844.
  The 390×844 view showed the full two-column starter grid, persistent composer,
  source status and privacy note without horizontal overflow.
- Accessibility-tree interaction verified labelled dialog/launcher/textarea,
  topic activation, answer rendering, expandable source links, follow-up
  controls, New chat reset, Escape close and focus restoration to the launcher.
- A missing-knowledge staging route produced the visible, announced
  “Public explanations are temporarily unavailable” error and disabled input.
- Native Safari automation timed out. iOS Mobile Safari and hands-on screen
  reader testing were not executed and remain required before activation.

## Acceptance limitations

- `./scripts/dev/canonical.sh --full` was attempted once and exited before
  tests because Docker was unavailable. Per repository policy it was not
  repeated.
- `./scripts/dev/bootstrap.sh` also exited before environment creation because
  the host is Darwin and the canonical environment requires Linux. Repository
  canonical/invariant acceptance therefore remains for GitHub CI.
- Real Cloudflare Durable Object/Worker behavior was not exercised because the
  actual project, route and authenticated account were unavailable. Unit tests
  cover the intended transaction/restart/expiry behavior but are not a real
  runtime acceptance.
- The canonical GitHub job now runs this package's dependency-free test suite
  and draft-knowledge validator before repository acceptance. Results for the
  exact PR revision remain pending until the branch is pushed.

## Live calls, release and activation

- Live provider/model calls: **0**.
- Provider spend: **USD 0**.
- Owner-approved model candidates evaluated live: **0**.
- Public source release date: **not assigned (`null`)**.
- Knowledge release: **`DRAFT_NOT_APPROVED`**.
- Activation: **disabled/fail closed**.
- Deployment: **not attempted**.
- Production homepage changed: **no**.

Remaining production inputs are the actual deploy repository/project/branch and
route owner; the missing candidate implementation, 31 cards and live cases;
public-source approval/date/expiry; privacy and security acceptance; approved
model and prices; global ceilings; externally provisioned secrets; real
Cloudflare runtime evidence; Mobile Safari/assistive-technology acceptance; and
deployment authorization.

## Maturity and Hub impact

The component and fail-closed adapter earn only **IMPLEMENTED** and locally
**TESTED** for the evidence above. They are not scientifically, security,
network, commercially or production qualified. No LIVE/launch authority exists.

Primary Hub map reference is `SYSTEM/PUBLICATION-AUTHORITY`. The Hub impact
policy now explicitly owns the WEB-QA-01 ticket, event `WEB-QA-01-D1` records
the inactive implementation and activation blockers, and the Hub is repinned
and regenerated from its exact authority snapshot. The current Wave-C
selection, scientific runtime, dependencies, qualification status and public
deployment state remain unchanged.
