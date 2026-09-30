# GOAL-WORKBENCH-16: one client route, from guided intake to a proposed Challenge

Owner authority: the repository owner, in the Workbench session on 2026-09-30,
approved this programme ("Approved.") after asking for it:

> integrate all capabilities here into the Pilot Designer, retire external
> workbench parts we don't need, and also leverage some of the testnet test
> designs we've created where it makes sense to. This needs to be a seamless
> route from guided intake to proposed challenge with data on why we chose to
> build it that way using an intelligent system we designed to optimize
> score/batch size/rate, Conditions (If customer doesn't supply which they
> should), etc.

Recorded as `OWNER-PILOT-DESIGNER-ROUTE-01` in `.agent/DECISIONS.md`.

Primary Development Hub map_ref: `SYSTEM/BUSINESS-AUTHORITY`; impact
`mapped_detail`.

Status: slice 1 merged (#448, e27a7adb3). Slice 2 in progress. One pull request per slice, each based on main.

## Why

Three client-facing drafting surfaces exist, and only one of them hands Carbon
something Carbon can import:

| Surface | Where it lives | Export imported by the internal Workbench? |
|---|---|---|
| Live `carbonphysics.ai/workbench/` (planning preview 0.3) | the owner's site upload, not this repository | **No** (`carbon.client-intake/1`) |
| Public onboarding edition (GOAL-WORKBENCH-14) | this repository, never deployed | Yes |
| Pilot Designer (`/ask-carbon/pilot-designer`) | this repository, live | Yes (`carbon.client-intake.reviewed.v1`) |

The Pilot Designer becomes the one client entry point. It already has the
guided AI conversation and the encrypted handover.

## Slices

1. **Consolidate.** Bring the live Workbench's problem builder into the Pilot
   Designer: physical components and couplings, structured inputs and outputs,
   evidence sources, success criteria, practical constraints, the cost
   calculator, the 64 research leads and the derived evidence plan. A saved
   `/workbench/` draft opens in the Pilot Designer. The brief format gains an
   additive version; every earlier version still validates as written.
2. **Propose a Challenge.** Deterministic family matching against the launch
   portfolio (`carbon/challenge_readiness/records/`). For a family with
   exam-design evidence (battery today), a proposed Challenge whose every
   setting carries the evidence that chose it (exam-design campaign 1:
   screening-batch size, active batches, rotation, equivalence margin, gates,
   score components). Conditions the client did not give are proposed from the
   family's tested design and labelled as proposals.
3. **Outside the evidence.** Conditions outside the tested envelope are flagged
   as no longer covered, with what a new campaign would need. A family without
   evidence gets a costed exam-design campaign plan, not a Challenge.
4. **Release.** An Ask Carbon release candidate for owner approval (the Ask
   Carbon lane owns `website/ask-carbon/`), and a redirect retiring the live
   `/workbench/` in the owner's site upload. Publication is the owner's act.

## Boundaries

- A proposal is not a Challenge. It registers, qualifies, activates and pays
  nothing. The owner and the science owners approve a real Challenge, and no
  Challenge pays rewards before its training budget study is complete
  (`OWNER-TRAINING-BUDGET-STUDY-01`).
- Proposed conditions are copied from a design Carbon already tested, never
  invented per client, and always labelled as proposals (AGENTS.md §5).
- The proposal is computed in the client's browser from public records. No new
  data leaves the browser; the optional AI guidance keeps its existing,
  consented context and gains no new field in this programme without a
  separate decision.
- E1–E9 and E8 are unchanged: no code path from client material to the subnet
  or the public assistant.
- The client security review (`OWNER-CLIENT-SECURITY-REVIEW-01`) still arms on
  the first real client engagement. Building this does not arm it.
- No deployment from this host, no Cloudflare access, no spend.

## Slice 1 decisions

- **D1. The live Workbench's problem model is reused, not rewritten.** Its
  engine (`carbon.workbench.problem.v0.3`, rules `problem.rules.2026-09-12.2`)
  is brought in byte-for-byte from the owner's site build input
  `carbon-site-v3-BUILD-INPUT.zip`, whose `workbench/` scripts match the live
  site by SHA-256 (read 2026-09-30).
- **D2. The words stay in the brief; the structure goes in `system`.**
  `carbon.client-intake.draft.v2` is `draft.v1` plus one `system` member, a
  validated problem. The decision, requested result and baseline stay in the
  brief's own fields, which is what the AI guidance edits. The canonical digest
  covers the system, so a change to it is a new revision, not a collision.
- **D3. Prospective only.** `draft.v1` and `reviewed.v1` packages keep their
  meaning and still import. Nothing already written is rewritten.
- **D4. The AI context is unchanged.** The system builder's values are not sent
  to the provider in this slice.

## Slice 2 decisions

- **D5. The proposal is computed, not authored per client.** `src/challenge_proposal.js`
  is pure and deterministic over the brief and one public record,
  `data/challenge_families_v1.json`. The same brief always gives the same
  proposal, in the browser and in a test.
- **D6. The record relays, it does not restate.** `tools/build_challenge_families.py`
  copies each launch-portfolio readiness record's status, limits, costs,
  reviews, training budget study, reference applicability and open items as
  recorded, reads the battery bounds from `carbon/battery/domain.py`, and takes
  each setting's evidence as verbatim quotes from
  `docs/development/EXAM_DESIGN_CAMPAIGN_RESULT.md`. A quote that no longer
  appears stops the build. The only authored content is each setting's
  one-sentence reason and the matching vocabulary, in
  `data/challenge_evidence_source_v1.json`.
- **D7. Matching is a suggestion.** A family is suggested by whole-word matches
  of its vocabulary in the client's own words and by physics overlap. The client
  can always choose another family. Matching is a starting point for Carbon
  review, not an assessment of fit.
- **D8. Conditions are relayed or flagged, never invented.** A condition the
  client did not give is proposed from the tested design's range and labelled
  so. A client range is compared with the tested range only when the units are
  spelled the same; a different or ambiguous unit asks for confirmation and is
  never converted. A range outside the tested one is reported as outside the
  evidence, and every setting is then marked as not covering it.
- **D9. No evidence, no setting.** A family without an exam-design campaign
  proposes no exam setting and shows no cost figure it does not have; it shows
  its recorded next experiment and names the unmeasured cost items.
- **D10. The proposal stays out of the brief format.** It is recomputable from
  the brief, so the reviewed package is unchanged; the client can download it
  as Markdown. It is not sent to the guidance provider.
