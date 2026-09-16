# GOAL-WORKBENCH-08A — guided pilot-design report

Status: implementation candidate; exact PR, tested head, required acceptance,
merge, and final artifact identities are filled by delivery closeout.

## Outcome

The maintained client preview now provides two views over one versioned brief:
guided Ask Carbon conversation and direct form editing. The client can switch
without losing work, skip questions, preserve unknowns, accept or reject each
proposed structured change, undo an accepted change, inspect the draft pilot,
and export a reviewed local package. No submission path is enabled.

The Workbench accepts the reviewed package through its ordinary intake file
control, previews before mutation, and creates one `UNASSESSED` direct job with
the original v1 brief, pilot outline, AI/client provenance, assumptions, and
existing exact lineage. It neither inherits the 07A assessment nor selects a
route or starts numerical work.

## Reuse map

| Existing implementation | Reuse | Extension |
|---|---|---|
| `carbon.client-intake.draft.v1` and `src/intake.js` | canonical client brief and deterministic summary | closed `carbon.client-intake.reviewed.v1` wrapper for pilot/provenance/consent/sharing |
| GOAL-WORKBENCH-08 preview/import | local editing, explicit download, atomic Workbench preview/commit | conversation/form shell, reviewed-package display and mapping |
| Ask Carbon PR #193 worker | server credentials, bounded source context, structured outputs, origin and cost controls | `PILOT_DESIGN` instructions/context/output schema |
| Ask Carbon Durable Object ledger | daily cost/request, global concurrency, client limits, conservative settlement | shared monthly owner ceiling and pilot session count |
| Workbench route/handoff/Owner Console | operator disposition after intake | no new workflow or dispatcher |

## Data and consent behavior

Form-only drafting sends nothing. Before AI guidance, the preview discloses
the draft/context sent, OpenAI API provider, current provider retention caveat,
and non-confidential-data boundary; consent is affirmative. Contact details
and the optional conversation-inclusion choice are not sent in guidance
context. Clearing conversation removes local turns but explicitly does not
claim provider deletion.

An export includes the client-reviewed structured brief, field provenance,
accepted suggestions, assumptions, schema/guidance/notice versions, consent
time when applicable, and contact fields. Conversation history is off by
default and included only on explicit selection. Submission permission does
not imply marketing, training, or cross-client reuse.

The exact notice and production data decisions are in
`website/ask-carbon/PILOT_DESIGN_REVIEW.md`. The provider basis is OpenAI's
official API data-controls guidance. The actual Carbon account retention
configuration remains unverified and must be reviewed before activation.

## Budget and evaluation

General Q&A and pilot guidance use one monthly owner ceiling of $50, enforced
as 50,000,000 micro-USD in the shared ledger. Daily request/cost, concurrency,
per-client, token, timeout, and conservative uncertain-dispatch controls also
remain; pilot guidance adds a bounded per-session request count. No second
allowance was created.

Nine authored public/synthetic evaluation cases cover an existing model,
thermal/fluid cold plate, unfamiliar coupled physics, sparse information,
contradictions/corrections, unrealistic performance, absent references,
unsupported guarantees, and prompt injection/cross-client requests. The
generated-browser flow uses a mock provider to exercise consent, proposed
changes, rejection, switching, undo, clearing, export, Workbench import,
deduplication, handoff, and save/reload. These are authored/mock engineering
tests. Live provider/model calls: **0**. Permitted customer sessions: **0**.

Local acceptance on the implementation candidate recorded:

- 233 Workbench pure/schema/integration JavaScript checks passed;
- 29 Ask Carbon adapter, ledger, static-integration, UI-state, and pilot-eval
  contract checks passed;
- 24 dependency-light authoring/bridge Python checks passed in an isolated
  pinned pytest tool;
- 19 source/schema/build/package Python checks passed;
- generated Google Chrome suites passed separately: 40 inherited Workbench,
  29 goal-flow, 19 routing/state, 13 source-assessment, and 28 guided-intake
  checks; the guided journey made zero off-device requests;
- Development Hub validation passed with 114 unique decisions, 84 validator
  tests, and static/interactive route checks.

These suites overlap in purpose and are not a scientific, privacy, security,
model-quality, or readiness percentage. The repository lock declares a Linux
x86_64 environment, so a direct macOS `uv run --frozen` was unavailable; the
dependency-light authoring tests were rerun with isolated pytest instead.

Live comparison is not run because the public knowledge release is still
draft, owner-approved model/prices and a provider secret are not installed in
this repository, the actual retention posture is unknown, and production
routing/deployment remain unauthorized. Those missing inputs block activation,
not local form use or implementation evidence.

## Delivery and limitations

The deterministic build emits `Carbon_Client_Pilot_Designer_Preview.html`, the
historical intake filename with identical bytes, and the internal Workbench.
The client artifact contains no source-assessment root, evidence collection,
operator notes, private path, or credential. Static submit remains disabled;
the production homepage is unchanged.

Final exact local suite counts, Chrome results, hashes, PR/head/run/merge, and
failed-attempt history are delivery-closeout fields. Safari/WebKit, hardware
assistive technology, actual Cloudflare runtime behavior, live model quality,
privacy/security acceptance, customer usability, hosted collection, private
persistence, staff notification, and rollback in production remain unexecuted.

## Authority ceiling

This is a draft-pilot and intake implementation. It creates no scientific
qualification, rights grant, reference adequacy, tolerance, speedup, savings,
execution authority, ScoreInput, protected use, official grade, reward,
network action, hosting approval, or launch. C-W1 and active Wave selection,
CPES variants/blockers, source-assessment snapshot, and numerical runtimes are
unchanged.
