# Ask Carbon pilot-design review

Status: implementation and local preview complete; live activation and public
collection remain disabled.

## Exact visitor notice in the preview

Before the first AI request, the pilot designer states:

> Sent to provider: the current high-level brief, pilot outline, unresolved
> assumptions, and up to ten conversation turns. Contact details and the
> optional submission-history choice are not sent.
>
> Provider: OpenAI API, Responses API, `store:false`. OpenAI states that API
> data is not used to train models unless the customer opts in. For the private
> synthetic staging project, Carbon observed API call logging enabled per call
> and did not establish an approved Zero Data Retention or Modified Abuse
> Monitoring control. Treat prompts and responses as potentially retained for
> up to 30 days under default abuse monitoring. This staging observation does
> not authorize customer-data processing.
>
> Carbon preview: this file stores no abandoned conversation. Conversation
> stays in memory unless explicitly included in an exported review package.
> Clearing it here does not delete provider records.

Official provider basis: <https://developers.openai.com/api/docs/guides/your-data>.
The final public notice must be re-reviewed against the actual Carbon account,
provider settings, host, receiver, store, and deletion process before serving.

## Data choices

| Client action | Carbon receives in this implementation |
|---|---|
| Uses the form without AI | Nothing leaves the browser. An explicit local export creates a review package. |
| Enables guided AI | The disclosed high-level draft/context and bounded conversation are sent to the configured provider route. The route is inactive in the shipped preview. |
| Exports the reviewed inquiry | Contact fields, the structured brief, accepted suggestions, unresolved assumptions, versions, and consent record are included locally. Conversation is included only when the client selects the unchecked option. Nothing is submitted. |

The format has no marketing, model-training, cross-customer reuse, scientific
approval, source-owner authority, execution, scoring, or launch field. Any
future optional reuse permission must be separate from inquiry-response
permission.

## Combined cost and degraded operation

General website Q&A and `PILOT_DESIGN` use the same Durable Object ledger and
one owner ceiling of 50,000,000 micro-USD ($50) per UTC month. The worker
requires that exact ceiling. Both modes also share daily-request, client-rate,
global-concurrency and operational-scope controls; pilot design adds a durable
per-session request count. The Worker prepares a worst-case reservation before
dispatch, records dispatch intent, and retains conservative exposure when
dispatch or usage is ambiguous.

If health is inactive, the provider fails, or a limit is reached, the local
draft is preserved and the visitor can continue through the form and export
it. This implementation creates no second allowance.

## Evaluation state

- Authored contract cases: nine public/synthetic scenarios in
  `eval/pilot-design.cases.public.json`.
- Frozen executable scripts: the same nine IDs in
  `eval/pilot-design.executable.public.json`; 11 literal turns with explicit
  accept, reject, undo, correction, skip and form-switch actions.
- Plan observation: no network calls; maximum conservative reservation for the
  finite 11-turn Luna plan is 62,040 micro-USD inside the existing $5 nested
  bakeoff scope and $50 shared monthly ceiling.
- Contract/mock observation: all nine scripts traversed the actual
  `PILOT_DESIGN` request validator, Worker dispatch boundary, shared ledger,
  reviewed-package validator and ordinary Workbench import. Eleven test-owned
  attempts settled 880 simulated micro-USD; paid spend remained zero. Each job
  started `UNASSESSED`, received an explicit operator route and one prepared
  manual handoff, survived save/reload, deduplicated exact replay and rejected
  changed bytes under the same identity.
- Mock browser conversation: executed through the generated artifact; client
  accepted one suggestion, rejected another, switched modes, undid a change,
  cleared local history, exported, and imported the package into Workbench.
- Live model/provider calls: **0**.
- Human quality review: **not performed**; complete public/synthetic output is
  retained in `evidence/pilot-design-v1/human-review-packet.md` for a named
  reviewer rather than converted to an automated quality claim.
- Actual customer usability observations: **none**.

Live comparison remains unavailable because the knowledge release is staging-
reviewed rather than public-approved, no provider secret or verified project
policy is available, the actual provider retention posture for Carbon is
unverified, and the private staging/receiving/deployment path is not
established. Luna and Terra configurations and prices are pinned for testing,
not selected by live evidence. Mock and authored tests are not model-quality
evidence.

## Remaining production decisions

Activation requires the actual homepage repository/static output and
Cloudflare route, approved public knowledge release and expiry, owner-approved
model and prices, account retention posture, privacy/security notice,
combined cost controls, private inquiry receiver/store, staff access,
retention/deletion and incident ownership, abuse controls, rollback, and
deployment authorization. The current preview does not transmit submissions,
persist abandoned conversations, publish the component, or change the live
homepage.
