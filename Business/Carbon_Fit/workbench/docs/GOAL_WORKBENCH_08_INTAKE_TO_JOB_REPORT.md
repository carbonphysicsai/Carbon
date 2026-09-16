# GOAL-WORKBENCH-08 — local intake-to-job report

Status: implementation candidate; final PR, CI, merge, and artifact identities are recorded at delivery closeout.

## Outcome

The Workbench now has one local, website-ready intake seam and one ordinary
internal import path:

`plain-language need -> deterministic local brief -> explicit download -> import preview -> UNASSESSED direct job -> operator route -> prepared handoff`

`Carbon_Client_Intake_Preview.html` is a dedicated public/synthetic surface.
It works from `file://`, keeps draft state in memory, and exposes no submit,
contact, arbitrary-file, analytics, model, URL-fetch, or network path.
`Carbon_Opportunity_Workbench.html` remains the system of record and performs
the preview, atomic commit, lineage, route, and handoff work.

## Reuse map

| Existing function / record | New use | Necessary extension |
|---|---|---|
| `newJob`, job assignment, requirement records | create one direct intake-backed job without Atlas | additive `intake_records` lineage and source references |
| route plan and `selectRoute` | operator chooses the smallest defensible route after review | none; imported drafts always start `UNASSESSED` |
| handoff request | reuse intake decision and unresolved question | no new envelope or dispatcher |
| Owner Console action/status resolver | display the imported job and its real blocker | intake source lineage only |
| cumulative review and revision rules | retain scientific/rights debt across later interpretation | intake successor never edits a sealed design |
| source-assessment reader | reject same-PDE reuse on a different request/subject | none; admitted index and 07A bytes stay unchanged |
| workspace parser/migration/export | preserve dedupe identity after save/reload | additive v0.8 job collection and migration receipt |
| standalone build/package tools | ship internal and public-local artifacts together | second shell using shared `src/intake.js`, without internal embeds |

## Transport and mapping

`carbon.client-intake.draft.v1` is a closed, bounded local transport. It records
draft/revision/predecessor identities, explicit unknown/value states, field
origins, units, a deterministic summary, mapping version, and local-only scope.
It has no authority, receipt, trust-root, approval, native-state, consent, or
workspace-object slots. IDs and digests establish association and bytes, not a
real person, consent, truth, or customer identity.

The Workbench recomputes and validates the summary, retains raw imported bytes
and digest, and maps only safe one-to-one fields. Consequential-error and
requested-accuracy answers become source-linked client requirement candidates;
they are not accepted tolerances or mandatory scientific gates. Missing values
stay unknown and unlike timing boundaries remain separate.

## Frozen journeys and observed friction

The fixtures cover an existing-method inquiry, a fresh Burgers-like inquiry,
and an unsupported non-Burgers inquiry plus a declared successor. Negative
vectors cover replay, changed bytes under one identity, missing predecessor,
cross-format payloads, forged authority fields, malformed JSON, and hostile
display text.

The primary local form exposes nine high-level text prompts and five optional
quantity records; the latter default to unknown. The browser journey required
one explicit intake export, one Workbench import preview, one create action,
one route save, and one handoff preparation. The mapped brief and requirement
candidates required no re-entry. Owner, lead, route rationale, next decision,
and the consequential handoff question correctly remained operator choices.
Exact replay required one import and confirmation and created no duplicate.
No human operator timing or permitted customer session occurred, so human
effort, waiting time, usability, demand, and business value remain unknown.

Each synthetic route reaches one useful next question in pure acceptance:
baseline applicability for existing capability, exact delta review for supported
adaptation, and one restartable feasibility question for unsupported physics.
These are product-flow observations, not qualified client outcomes.

## Validation evidence

- JavaScript pure/schema/integration: 245 passed, 0 failed.
- Python source/schema/bridge: 27 passed, 0 failed.
- Google Chrome generated artifacts: inherited Workbench 40, goal flow 29,
  routing/state 19, source assessment 13, and intake bridge 18 checks passed.
- Intake browser journey used actual downloaded draft bytes, fresh browser
  pages, desktop and 390px views, save/reload, and zero off-device requests.
- Repository snapshot admission check remained `ADMISSION_CONSISTENT` for the
  unchanged one-entry 07A snapshot.

These suite results overlap and are not a scientific, privacy, security, or
readiness percentage. Safari/WebKit and assistive-technology hardware testing
were unavailable and are not called passed. Required repository exact-head CI
and merge are delivery records, not inferred from these local results.

## Live website handoff — not implemented

A later approved website should mount the shared intake component, transmit the
versioned draft only to its owning backend, and have that backend repeat closed
validation and summary computation before private persistence, a real receipt,
and retryable staff notification. Nothing in this delivery supplies that path.

Issue #139 still needs exact decisions for:

- the actual website repository, host, route, and receiving endpoint;
- private store and staff notification destination;
- authentication and staff access roles;
- retention, deletion, and incident ownership;
- approved public notice and separate inquiry versus optional-learning choices;
- server-side abuse, rate, availability, and recovery controls.

The preview is not published, issue #139 remains open, and no vendor,
credential, destination, consent, or production security decision is inferred.

## Conclusions and authority ceiling

- **Local engineering workflow:** implemented and locally tested; final
  acceptance/merge identity remains the delivery closeout record.
- **Actual customer usability/value:** unmeasured; only public/synthetic product
  journeys were run.
- **Live collection/hosting:** not implemented or authorized.

The active C-W1 DEVELOPMENT lane was not changed. CPES A remains the baseline,
B conditional/non-activating, C sensitivity-only, and AT-09/16/19/22/30 remain
unresolved. No source statement, scientific qualification, rights grant,
protected reuse, numerical campaign, ScoreInput, official grade, reward,
network action, or launch was created.
