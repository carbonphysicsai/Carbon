# WEB-QA-04 — Ask Carbon reviewed-answer selection reliability

**Status:** ACTIVE — concrete public-release candidate implementation and private acceptance
**Owner authorization:** continue the Ask Carbon staging workstream; no production activation
**Depends on:** merged WEB-QA-03 / PR #204 evidence
**Coordination:** issue #209 comment `5720642402`
**Evidence:** `website/ask-carbon/evidence/WEB-QA-04.md`

## Goal

Repair the retained structured-output failures without weakening source,
publication, privacy, budget, or production boundaries. Re-run the frozen Ask
Carbon acceptance split through the private Cloudflare Workers and shared
provider-budget authority, select the least-cost passing registered model or
select none, and prepare one concrete owner-review release candidate.

The first-release candidate includes public Carbon Q&A, guided pilot drafting,
form-only drafting without AI, and explicit local download of a reviewed draft.
Inquiry collection, receipt, persistence and staff notification remain a
separate issue #139 workstream. Their receiver is not a prerequisite for local
or AI-guided drafting because this release contains no submission action.

## Bounded implementation

- Replace the provider-authored answer plus duplicate claim-paraphrase map with
  a strict selection of server-owned reviewed answer cards.
- Assemble displayed text from exact reviewed passage text, and assemble passage
  IDs, source destinations, maturity notes and follow-up wording only from the
  eligible release on the server.
- Keep request-specific enums, application validation, no tools, no
  model-selected URLs, one provider call, no retry/fallback, and the existing
  shared USD 50 / nested USD 5 Durable Object authority.
- Preserve the current private staging and production-disabled release gates.
- Retain old evidence and run the successor as a separate release/evaluation
  identity.
- Preserve the existing homepage and Workbench; integrate the dependency-free
  component and the maintained pilot designer without an iframe or second
  framework.
- Keep AI off until affirmative disclosure acceptance; expose accept, reject,
  undo, direct edit, reset, unresolved-field and local-download behavior.
- Prepare an exact inactive production configuration for only
  `/api/ask-carbon*` on both approved hostnames. Do not deploy it or mutate the
  production homepage before the owner approves the exact release package.

## Core-programme boundary

Issue #209 and PR #211 were inspected before implementation. This ticket does
not change `carbon/reconstruction`, shared scientific-task APIs, capability
discovery, execution profiles, checkpoints, grants, shared artifacts/evidence,
campaign accounting, or job lifecycle. Ask Carbon's existing provider ledger
remains an application-specific public-Q&A cost authority; it is not a
scientific scheduler, runner, artifact format, or campaign ledger. Any future
dependency on those interfaces stays blocked and is coordinated with issue
#209's owner before shared code changes.

## Acceptance

1. Tests reject unknown, duplicate, withdrawn, stale, or non-retrieved answer
   selections and prove that displayed factual text cannot be supplied by the
   model.
2. Knowledge validation proves every eligible answer card has a reviewed
   passage/source basis.
3. Existing request, retrieval, privacy, accounting, continuation, withdrawal,
   body-size, provider-usage, and UI-race tests remain green.
4. The same frozen final split is run for Luna and Terra through the real
   private Worker and shared ledger within the remaining evaluation ceiling.
5. Retained failures and independent source-grounded review determine model
   selection; production remains unchanged.
6. Local and private-staging browser checks cover the two visitor paths,
   form-only operation, disclosed outbound context, local download, accessible
   status/errors, keyboard navigation, mobile overflow and rollback.
7. The release packet records the exact static input/output hashes, knowledge,
   model/configuration, budget state, Cloudflare versions and remaining owner
   inputs without treating merge as public approval.

## Required automated acceptance

Run the applicable Ask Carbon suite and the repository's delivery-protocol
acceptance on the final candidate. Merge only with the expected-head guard and
no production route, DNS, homepage, or activation change.
