# WEB-QA-02 repair and staging-candidate evidence

**Evidence date:** 2026-09-16  
**Branch:** `agent/web-qa-02-repair-staging`  
**Base:** `405a820bfdd5a38aa2d498e3dbde3fa15449379f`

## Recovered input and reconciliation

`Carbon_Ask_v1.zip` was mounted and matched the owner-supplied SHA-256
`ca1e23c3a77ec813c384d893358fe1fe1959edd5989068a5711b04e2821120cb`.
Archive entries were regular bounded paths; no archived code was executed as an
install step. The package contained 31 draft cards and the stated 40
single-turn/five-conversation suite. The cards were compared with current
governing sources at the base revision and used as draft prompts, not authority
or a count target.

The reconciled staging release has 26 cards and nine source records. Each card
has a stable ID, public disclosure class, scope/maturity note, direct passage,
review/expiry state and current revision-pinned URL. Source-byte validation
matched all nine declared SHA-256 values. Training content now distinguishes
Challenge-owned support, registered miner curricula/sampling choices,
validator-supplied randomness, and protected official evaluation. Current
status has a seven-day freshness window; stable concepts and network/product
topics use separately bounded windows. The source release date is 2026-09-16.

## Concrete repairs

- Replaced day-bucket accounting with one UTC-month, 50,000,000-micro-USD
  authority and a durable attempt state machine. The USD 5 bakeoff is a
  persistent sub-cap inside the same allowance.
- Reserved all possible provider work before dispatch; removed retry/fallback;
  retained conservative exposure after crash, abort, invalid/missing usage,
  model mismatch or settlement failure; settled late usage idempotently.
- Added exact Luna/Terra configuration and integer-safe input/cached/output
  pricing. Reasoning tokens remain part of output tokens and are required in
  usage details. Unexpected model or price identity stops service.
- Added deterministic conversation-aware retrieval using only server-issued,
  release/version/withdrawal/expiry-bound topic state. Visitor-authored answer
  history is rejected and every turn retrieves evidence again.
- Added a relevance floor and distinct supported, insufficient-evidence,
  out-of-scope and service-failure responses.
- Added claim-to-passage mappings and deterministic support checks. The server
  alone resolves source URLs. There is no claim that a second model verifies
  every answer.
- Unified build, Worker and saved-answer publication logic. Individual stale or
  withdrawn topics stop independently; global withdrawal invalidates all
  content and continuation state. Production rejects the staging release.
- Fixed overlapping request identity, reset/late completion races, maturity
  rendering, request/response stream limits and mobile long-token overflow.
- Added one non-public central Durable Object entrypoint so separately
  permissioned app environments can share one financial authority instead of
  receiving separate USD 50 namespaces.

## Test and local staging evidence

Focused package tests currently cover 37 cases (all passing at the recorded
candidate): release/withdrawal/freshness, activation/privacy/edge gates,
continuation forgery and expiry, topic switch, no evidence, claim support,
pricing, crash/restart, concurrent exact-boundary admission, rollover, scope
cap immutability, unresolved/late/double settlement, generated event sequences,
provider errors/usage, settlement failure, stream limits, static integration,
CSP, source hashes, UI retrieval and request identity.

The contract evaluation retained all 40 supplied single-turn cases and all five
conversations: 38 single-turn questions matched a reviewed saved explanation
and two correctly had no relevant saved explanation. This is retrieval contract
evidence, not factuality or live-model quality.

The current public homepage was downloaded again and retained the reviewed
5,774,725-byte SHA-256
`5ebb43e859e9837f74bbc93b5748b2db95a6700821afbfcecb407e75702e2020`.
The static integration preserved that page and `/workbench/`, added four
external assets, and generated a CSP with one exact script hash and one exact
style hash, no `unsafe-inline`, no inline event handlers, and `connect-src
'self'`. Local Chrome checks covered desktop and 390×844 responsive layout,
topic answer, visible maturity, source expansion, labelled controls, Escape,
focus restoration and measured zero horizontal overflow at body, dialog, main
and message levels. Native iOS Mobile Safari and VoiceOver were not available
and are not reported as passed.

## Hosting and runtime discovery

Authenticated GitHub evidence shows `carbonphysicsai/Carbon` is the only
accessible organization repository. Its GitHub Pages source is the Development
Hub workflow from `main:/docs`, not the public homepage.

The authenticated `hello@carbonphysics.ai` Cloudflare account has no domains,
Workers, Pages projects, Durable Objects or Zero Trust application. Public DNS
and response headers show Cloudflare serving the hostname but do not prove the
owning account or source. No Cloudflare resource, route, DNS record, key,
subscription or charge was created. Real Worker/Durable Object restart,
concurrency, cache withdrawal and rollback therefore remain unexecuted.

## Live evaluation, spend and activation

- Candidate configurations prepared: `gpt-5.6-luna:low:v1` and
  `gpt-5.6-terra:low:v1`.
- Live provider calls: **0**.
- Exact/uncertain provider spend: **USD 0 / USD 0**.
- Bakeoff share consumed: **USD 0 of USD 5**.
- Monthly application exposure consumed: **USD 0 of USD 50**.
- Chosen model: **none; no live compatibility or quality evidence exists**.
- Staging deployment: **blocked before resource creation**.
- Public activation: **disabled**.
- Production homepage changed: **no**; the public API path still returned 404.

The available environment had no OpenAI credential and the actual OpenAI
project data-control settings were not accessible. Official documentation was
used for candidate compatibility/prices and for the fact that `store:false`
does not itself create Zero Data Retention. The proposed exact privacy notice
and retention map are in `PRIVACY_AND_RETENTION.md`; owner acceptance remains a
production gate.

## Actionable external blockers

1. **Hosting owner:** identify the exact account/upload workflow that owns
   `carbonphysics.ai`, and grant minimum access to an existing private staging
   target or name its operator/rollback owner.
2. **Cloudflare cost/security owner:** authorize only if needed the central
   Durable Object plus private access and edge-rate-limit policies, including
   any non-zero charge. The currently accessible account contains none.
3. **Provider project owner:** provision a dedicated staging secret outside
   chat and confirm the actual project data-control/retention setting. This is
   required before the bounded Luna/Terra bakeoff.
4. **Privacy owner:** accept or replace the exact public notice and retention
   map before production live answers.
5. **Release owner:** after staging quality/runtime evidence exists, approve the
   exact deployment target, knowledge/model/configuration and production route.

No resolved owner decision is re-opened: source discovery was attempted, the
USD 50/5 caps are implemented, the two candidates are selected for testing,
and routine publicly eligible content was reconciled without per-card approval.
