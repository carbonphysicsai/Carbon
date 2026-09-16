# GOAL-WORKBENCH-08B pilot-evaluation report

Status: local evaluation tooling and Workbench return implemented; live model
evaluation and public activation not run.

## Reuse and implementation

| Existing record/function | New use | Extension |
|---|---|---|
| `pilot-design.cases.public.json` | retained nine source scenario IDs and required/forbidden behavior | adjacent frozen executable turns/actions; original descriptions unchanged |
| Ask Carbon `PILOT_DESIGN` Worker | closed context, retrieval, response validation and bounded provider seam | runner supplies test-owned outputs in mock mode; no second adapter |
| `ask-carbon-provider-budget-v2` ledger | shared per-request admission and settlement | no new budget or namespace |
| `carbon.client-intake.reviewed.v1` | final client-reviewed brief | no schema change |
| Workbench `previewIntakeImport` / `commitIntakeImport` | ordinary `UNASSESSED` inquiry creation | deterministic test driver only |
| existing routes and `handoff` | one explicit operator route and next action | no new workflow engine |

The existing general-Q&A runner remains unchanged by default. Selecting
`--suite pilot-design` adds `plan`, `mock`, and fail-closed `live` behavior.
Plan and mock make no external network request. Live never calls a provider
directly and currently stops before dispatch because no accepted private
staging access mechanism/target exists.

## What ran

The frozen suite contains the accepted nine scenario IDs and 11 public/synthetic
turns. Each turn retained the exact disclosed brief context, test-owned Worker
response, proposed edits, explicit client action and resulting brief. The
scripts include accept, reject, undo, correction, skip and form-switch actions.
If a named proposal is absent, the action records
`EXPECTED_PROPOSAL_ABSENT`; it does not fabricate an edit.

All nine reviewed packages:

1. previewed as `CREATE_NEW_JOB`;
2. created an `UNASSESSED` inquiry;
3. received an explicit operator route and one `PREPARED` request-only handoff;
4. reopened with the same intake record and unresolved authority;
5. deduplicated exact replay; and
6. rejected changed bytes under the same draft/revision identity.

The contradiction case also attached a valid `rev-002` successor for review
without overwriting its predecessor. No case contained a source-assessment
response. Scientific qualification remained `NOT_QUALIFIED`, rights
`UNRESOLVED`, and launch `NOT_AUTHORIZED`.

Deterministic evidence is under
`website/ask-carbon/evidence/pilot-design-v1/`. Rebuilding twice produced the
same bytes. The manifest distinguishes authored expectations, deterministic
contract observations and mock-provider workflow observations.

## Measurements and missingness

| Observation | Result |
|---|---|
| Frozen scenarios / turns | 9 / 11 |
| External provider calls / paid spend | 0 / USD 0 |
| Mock Worker attempts | 11 settled |
| Mock settled cost | 880 micro-USD, simulated only |
| Conservative plan reservation | 62,040 micro-USD, not spent |
| Shared ceilings | 5,000,000 micro-USD bakeoff inside 50,000,000 micro-USD monthly |
| Customer sessions | 0 |
| Human quality review | `NOT_PERFORMED` |
| Live-model latency/cost/usefulness | `NOT_MEASURED` |

The inherited generated-artifact Chrome journey passed 28 checks at desktop
and narrow width with zero outbound requests and zero live-model calls. It
covered consent before guidance, disclosed context, accept/reject/undo,
form/conversation continuity, local clearing, reviewed-package download,
ordinary Workbench import, route/handoff, save/reload, deduplication, 07A
non-inheritance and escaped hostile text. Safari/WebKit and assistive-technology
sessions were not run and are not reported as passes.

Local acceptance also ran the 47 Ask Carbon tests, 233 focused/inherited
Workbench JavaScript tests, 19 source/schema/build/package tests and current
knowledge validation. The first source-test invocation under system Python
failed before collection because `python-docx` was absent; the same unchanged
suite passed in the repository/app bundled Python environment. This environment
failure is retained as diagnostic history, not relabeled as a passing run.

No customer-time or value claim follows from test duration. Synthetic cold
plate and coupled-physics cases remain scoping examples, not capability or
scientific-support claims. The complete retained packet is ready for a named
reviewer using the existing rubric; no automated average hides authority or
sensitive-data defects.

## Live gate and next action

Private synthetic live evaluation is `NOT_RUN_NAMED_INPUTS_MISSING`. The exact
restart inputs are:

1. exact permitted private staging account/project and Worker route;
2. its accepted access-authentication mechanism and responsible operator;
3. provider secret installed through the approved secret process;
4. provider-project retention/data-control evidence;
5. current knowledge/model/config release checks and a shared-ledger snapshot
   showing remaining authorized bakeoff exposure; and
6. explicit authority for any incremental non-provider infrastructure cost.

Owner: Ryan for product/interface disposition, with the existing security,
privacy, infrastructure-cost and publication owners for their scoped inputs.
Restart event: those inputs are recorded for one exact private Worker target.
Then run the finite suite once through that Worker, retain the ledger snapshot
and outputs, and assign a named human reviewer. Do not provision a parallel
Worker, call the provider directly, or activate the public service.

## Authority ceiling

Public activation remains disabled. This work creates no scientific evidence,
qualification, rights grant, customer-use approval, reference reuse, provider
account acceptance, execution authority, score, protected use, Wave change or
launch. C-W1 and the accepted 07A assessment bytes/snapshot are untouched.

## Delivery identities

The exact PR, tested head, required acceptance run/attempt, merge revision and
final artifact hashes are recorded in the delivery PR and completion comment.
They are not inferred in this pre-merge report.
