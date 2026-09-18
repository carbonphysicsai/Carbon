# GOAL-WORKBENCH-09 — private team intake and review report

Status: implementation candidate; repository acceptance and merge identities
are recorded at delivery, not inferred by this report.

## Outcome

The maintained Workbench now supports the bounded private-team journey:

```text
reviewed client brief
→ durable synthetic/private receipt
→ intake queue
→ assigned team assessment
→ immutable design alternatives/revisions
→ evidence and feasibility gaps
→ client pilot brief + internal execution brief
→ request-only source-bound handoff
```

This is an additive v0.9 application, not another Workbench. Existing v0.1–v0.8
sessions migrate with empty team-review/assessment state and no fabricated
reviewer, evidence, route, result or approval.

## Reuse map

| Existing record/function | New use | Necessary extension |
|---|---|---|
| reviewed intake v1 and `previewIntakeImport` / `commitIntakeImport` | queue source and exact lineage | queue moves to `READY_FOR_REVIEW`; receipt remains separate |
| job assignment and immutable design revisions | team corrections, assessment and alternatives | job `team_review`; design `assessment` |
| three planning routes and deterministic next action | operator disposition after review | no new route or fit score |
| requirement → trace → case → reference model | assessment source binding | client/internal briefs reference the same design |
| existing handoff v1 | scoped Engineering/science request | no dispatch or execution |
| Owner Console | all-inquiry review queue | objective/baseline/conditions/output/reference/missing/reviewer/action columns |
| issue #209 shared task contract | three future task dependencies | `CORE_INTERFACE_PENDING`; no runner or scheduler |
| Ask Carbon reviewed package | local/private receiver input | no model/provider or public-submit change |

## Application behavior

Team reviewers can assign a reviewer and queue state, record a transcription
correction without overwriting the original words, add internal notes and open
questions, edit a traceable assessment, create alternatives/revisions, select
an existing route and prepare one manual handoff. The assessment covers the
physical definition, units/envelope, observables, requested performance,
physics/diagnostics, data rights/provenance, generator/sampling, reference and
measurement/uncertainty gaps, implementation dependencies, assumption-labeled
resources, smallest pilot and stop conditions.

Two outputs are derived at export time from the exact same job/design:

- `carbon.goal-workbench.client-pilot-brief.v1` uses client-readable scope,
  evidence/input needs, exclusions, open questions and next discussion. It
  excludes private team notes.
- `carbon.goal-workbench.internal-execution-brief.v1` retains the exact design,
  route, full assessment, requirement/case/evidence IDs, work packages,
  dependencies, handoff bindings and unresolved decisions.

Neither output turns a request into measured evidence, a target into a
guarantee, or an exported handoff into send/execution.

## Persistence and authorization scope

`tools/team_intake_store.cjs` is a deterministic file-backed private/synthetic
store using atomic temp-file replacement. `tools/team_intake_server.cjs`
provides a loopback HTTP boundary with externally supplied named principals and
token hashes. The service:

- validates the closed reviewed-intake schema and 120 KB body limit;
- recomputes raw/canonical identities;
- persists the inquiry and outbox before issuing a receipt;
- deduplicates exact response-loss retries and rejects changed bytes under the
  same idempotency key;
- rejects stale optimistic updates;
- authorizes read/update/export/delete/outbox operations by named role;
- retains a pending outbox after delivery failure; and
- deletes client content under the explicit local synthetic lifecycle while
  retaining a content-free tombstone with the prior digest.

No production store/auth target, notification destination, live staff identity
set, visitor notice, retention period or paid service was invented. A hidden
page or shared password is not treated as customer-record authorization.

## Frozen scenarios and observed results

`data/goal_workbench_09_team_scenarios_v1.json` freezes four public/synthetic
cases. `tests/test_team_journeys.cjs` executes each from reviewed package
through persistence, ordinary Workbench import, assignment, assessment, route,
handoff, client/internal exports, save/reload and exact replay:

| Scenario | Route | Result |
|---|---|---|
| existing model and reference | `USE_EXISTING_CAPABILITY` | bounded intended-use/reference clarification prepared |
| objective without usable reference | `ADAPT_SUPPORTED_CHALLENGE` | reference-feasibility gap retained; no execution |
| unsupported coupled physics | `DEVELOP_NEW_CAPABILITY` | one compatibility question and stop/restart event |
| incomplete brief | `DEVELOP_NEW_CAPABILITY` | unknowns preserved; one consequential clarification |

All four correctly executed despite unresolved feasibility. None is customer
demand or scientific evidence.

## Verification performed before repository acceptance

- 265 JavaScript tests passed: the inherited 260-test application suite, one
  private-export authorization regression and four end-to-end team journeys.
  The focused additions also cover durable
  response-loss recovery, idempotency conflict, access control, optimistic
  concurrency, authorized export, outbox recovery, deletion, correction lineage, output privacy,
  revision behavior and task-boundary rejection.
- Existing generated-HTML browser journey: 29 checks passed in local Google
  Chrome.
- New team-review generated-HTML journey: 13 checks passed at desktop and
  narrow width with keyboard-addressable native controls, safe text output and
  zero HTTP/WebSocket requests.
- Safari/WebKit, VoiceOver and a real permitted customer session were not run
  and are not counted as passes.

Exact final suite counts, source/tested head, CI attempt, merge and artifact
digests are appended to the delivery record after exact-head acceptance.

## Core and Ask Carbon boundaries

The implementation inspected issue #209 and the open C-CORE-04 Workbench
science PR. It does not edit `carbon/scientific_tasks`, Julia, accelerator
selection, scheduling, checkpoints, grants, accounting or job lifecycle. The
three scientific study actions remain dependency projections until the shared
accepted service is available; later integration must use a successor
experiment identity and exact design/numerical bindings.

Ask Carbon keeps its reviewed brief format, suggestion lifecycle and public
activation state. No model gateway, ledger, prompt, public Submit control or
provider grant changed. Public Q&A and local guided drafting remain independent
of this receiver.

## Deployment proposal and exact remaining inputs

Recommended future deployment, subject to owner decisions, is the existing
Cloudflare account with named-user Cloudflare Access for the team surface and a
single private Worker using a D1 or Durable Object persistence implementation
of the tested contract. The browser receiver and store must remain private;
the public Submit control stays disabled until the following are supplied once:

1. Store/route: approved private Cloudflare target and permission to incur any
   incremental hosting/storage charge.
2. Named access: staff principals and roles for receiver, reviewer, data
   steward, notification operator and rollback operator.
3. Notification: destination and explicit sending authority.
4. Data lifecycle: retention/deletion period, approved visitor notice, and
   separate inquiry versus optional-learning permissions.
5. Operations: incident owner, rollback/disable operator and recovery target.

Their absence blocks live customer collection, not this synthetic/local
implementation.

## Authority ceiling and next step

The Workbench remains planning and evidence coordination. It does not qualify
physics, references, measurements, uncertainty, rights, protected reuse,
scores, rewards or launch. CPES A/B/C and AT-09/16/19/22/30 remain unchanged.

Next dependency-ready step: after the shared issue #209 task/capability service
and C-CORE-04 Workbench adapter are accepted, wrap one exact
`PHYSICAL_DEFINITION_CHECK` action behind the existing dependency row using a
new task/experiment identity. Until then, keep the unavailable state visible
and continue no local execution substitute.
