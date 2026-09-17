# GOAL-WORKBENCH-08B private pilot-evaluation report

Status at candidate preparation:

- Engineering: private-staging and live-evidence implementation complete;
  repository delivery pending exact-head acceptance.
- Private preview: deployed and access-gated.
- Live evaluation: completed for the frozen nine-scenario / 11-turn synthetic
  suite using the selected evidence from runs `v3` and `v4`.
- Human quality review: `NOT_PERFORMED`; Ryan and Nick are named but their
  reviewer assignments and dispositions remain unconfirmed.
- Public activation: disabled and unchanged.
- Customer sessions: zero.

## Reuse and implementation

| Existing record/function | Reuse | Bounded extension |
|---|---|---|
| `pilot-design.cases.public.json` and executable suite | retained nine scenario IDs, turns and required/forbidden behavior | live runner applies real proposals only by exact ID or one unambiguous frozen expected field |
| Ask Carbon `PILOT_DESIGN` Worker | closed context, retrieval, response validation and provider seam | provider HTTP errors, supported strict schema and source passage identities repaired from retained failures |
| `ask-carbon-provider-budget-v2` | one shared Durable Object ledger | route-less authority deployed once; no second allowance or namespace |
| reviewed intake and Workbench APIs | ordinary `UNASSESSED` import, route and request-only handoff | live-model reviewed packages traverse the same round trip |
| maintained pilot preview | same brief in form and conversation modes | authenticated private Worker serves the generated artifact; no homepage route |

The private app Worker is `carbon-ask-private-staging` at
`https://carbon-ask-private-staging.carbon-physics-ai.workers.dev`; the
route-less authority is `carbon-ask-budget-authority`. Deployed app version
`47310060-740c-45c4-8575-5d0fee1caf9f` uses knowledge
`ask-carbon-staging-2026-09-16.1` and model configuration
`gpt-5.6-luna:low:v1`. Access uses a rotated Basic secret plus a separate
operator secret for the ledger snapshot. This is possession-based staging
access, not named-person authentication. No public homepage route changed.

## Live execution and retained failures

The first full run (`v1`) failed all nine first turns. OpenAI rejected an
unsupported `uniqueItems` keyword in the strict response schema, but the Worker
incorrectly classified the HTTP 400 response as a model mismatch. The failed
run remains retained with 50,760 micro-USD of conservative unresolved exposure.
Repairs now classify provider rejection before model identity, omit the
unsupported provider-schema keyword while preserving Carbon duplicate checks,
and log only safe provider error metadata.

Focused diagnostics then exposed and repaired two more concrete defects:

1. pilot sources were read from a nonexistent card-level field instead of the
   retained passage source IDs, causing `unknown_source` after a valid model
   response;
2. the 15-second staging timeout was shorter than an observed valid response,
   so private staging now uses a 60-second engineering limit. This is not a
   public latency promise.

Run `v2` produced six settled responses before the durable 20-request client
hour limit correctly rejected five remaining turns. It also showed that live
suggestion IDs differ from mock IDs. The client-action harness was repaired to
accept an exact suggestion ID or one unambiguous proposal for the frozen
expected field; absent or ambiguous proposals remain unapplied. Undo now binds
the actual accepted proposal while retaining scripted lineage. The old `v2`
packet remains unchanged development history, including its partial briefs.

After the hourly boundary reset naturally, `v3` ran the five previously
rate-limited scenarios (six turns). Run `v4` ran the four earlier affected
scenarios (five turns) through the repaired client-action mapping. There were
no retries. The final selected evidence is `v4` for the first four scenarios
and `v3` for the remaining five. All selected 11 turns returned supported,
schema-valid responses and completed the ordinary Workbench return.

Two staging credentials appeared in local diagnostic output during setup. Each
was rotated immediately, the affected old value was replaced in Cloudflare,
and no value is retained in repository artifacts. No provider key was exposed
by those events. Tail-based request inspection is not used for the protected
operator snapshot route.

## Observed live results

| Observation | Selected-suite result |
|---|---|
| Scenarios / turns | 9 / 11 |
| Supported live responses | 11 |
| Selected settled provider cost | 7,153 micro-USD (USD 0.007153) |
| Median / p95 / maximum latency | 9,197.907 / 17,355.953 / 17,355.953 ms |
| Workbench initial state | all `UNASSESSED` |
| Handoff | all `PREPARED`, request-only |
| Scientific / rights / launch | `NOT_QUALIFIED` / `UNRESOLVED` / `NOT_AUTHORIZED` |
| Source-assessment responses admitted | 0 |
| Customer sessions | 0 |

Before human judgment, the retained outputs show useful bounded behavior: the
assistant preserved unknowns in the sparse case, converted the 100x request
into an aspirational/testable question, kept missing reference evidence
explicit, declined to confirm arbitrary coupled-physics support, refused
qualification/launch guarantees, and refused another-client and arbitrary-URL
requests.

The outputs also retain quality/friction findings rather than tuning them away.
The model did not propose `pilot.bounded_first_pilot` in the existing-model or
absent-reference scenarios, and did not propose `pilot.next_discussion` in the
unsupported-guarantee scenario. Those client actions are recorded as
`EXPECTED_PROPOSAL_ABSENT`; their corresponding final checks remain incomplete.
The cold-plate and coupled-physics cases did produce useful scoped evaluation
or evidence-audit fields while retaining reference, tolerance, rights and
execution unknowns. These are observations, not a human quality verdict.

## Cost and data boundary

The shared September ledger after `v4` records:

- settled provider cost: 13,151 micro-USD (USD 0.013151), including diagnostics
  and superseded development runs;
- unresolved conservative exposure: 67,680 micro-USD (USD 0.067680);
- total ledger exposure: 80,831 micro-USD (USD 0.080831);
- nested evaluation ceiling: 5,000,000 micro-USD inside the 50,000,000
  micro-USD application monthly ceiling.

Missing or uncertain usage was not converted to zero. Cloudflare cost is
separate and unmeasured; no paid-plan change was observed. The OpenAI project
showed API-call logging enabled per call. No approved Zero Data Retention or
Modified Abuse Monitoring control was established, so the preview discloses
potential default abuse-monitoring retention up to 30 days and remains
synthetic-only. This does not authorize customer-data processing.

## Verification executed

- Ask Carbon: 53 Node tests; knowledge validation of 26 cards / nine sources;
  40 single-turn and five conversation deterministic retrieval checks; pilot
  plan and mock paths.
- Workbench: 233 focused/inherited JavaScript checks; 19
  source/schema/build/package checks.
- Generated browser artifacts: 28 intake checks and 29 inherited Workbench
  checks in Chrome, including desktop/narrow layout, keyboard/file controls,
  zero external requests for the local path, reviewed-package import,
  save/reload and 07A non-inheritance.
- Private deployment: unauthenticated preview returned 401; authenticated
  preview and health returned 200; current retention disclosure was inspected
  in Chrome.

The first Playwright attempts failed because the optional module was not on the
default Node path and then because sandboxed Chrome could not launch. The same
unchanged suites passed using the bundled dependency runtime with approved GUI
execution. Safari/WebKit, VoiceOver and an actual customer usability session
were not run and are not passes.

## Human packet and next decision

`website/ask-carbon/evidence/PILOT_DESIGN_PRIVATE_REVIEW_PACKET_2026-09-17.md`
links the selected `v3`/`v4` transcripts, resulting briefs and a compact
ACCEPT/CHANGE/REJECT form. Ryan is named for engineering relevance and
pilot-design quality; Nick is named for clarity and prospective-client
usefulness. Their review has not occurred and no acceptance is inferred.

The next decision is a permitted human review of that packet and private
preview. Fix only a named answer/interaction defect that review identifies.
Public release still requires explicit publication, privacy/security, customer
receiver/storage, cost and deployment authorization; this work does not close
issue #139.

## Authority ceiling and delivery identities

Public activation remains disabled. This work creates no scientific evidence,
qualification, reference adequacy, rights grant, customer-use approval,
execution authority, score, protected use, Wave change or launch. C-W1 and the
accepted 07A assessment bytes/snapshot are untouched.

PR #200 remains the accepted local/mock baseline (head
`275a6c94c801a3e688bbaaeac83c60ec32f3025d`, merge
`fab8acd59f65c67a1560a242002bc0a1de123da5`, run `35111712129`). The exact
feature PR, tested head, classifier-selected acceptance run, merge revision and
final package hashes for this continuation are recorded at delivery; they are
not inferred in this pre-acceptance report.
