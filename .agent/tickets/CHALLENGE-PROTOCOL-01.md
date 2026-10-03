# CHALLENGE-PROTOCOL-01 — Phase 1 step 1: reconcile battery's current state

**Status:** in progress.
**Primary Hub map_ref:** `SYSTEM/DEVELOPMENT-SEQUENCING`, `HUB_UPDATE_REQUIRED`.
**Authority:** OWNER-CHALLENGE-ROADMAP-01 (2026-10-02), OWNER-DX-03.
**Spec:** `Design_Specs/Challenge_Roadmap.md`, §01 step 1.
**Depends on:** CHALLENGE-PIPELINE-01 (the pipeline state it updates).

## Outcome

The roadmap's step 1, "Reconcile battery's current state. Contract, EV1–EV3
results, PR 458 status, current exam batch," produces its output, "battery
status record with commit IDs":
`docs/development/challenge_pipeline/BATTERY_STATUS_2026-10-02.md`.

Phase 1 step 1 is marked done in `carbon/challenge_pipeline/protocol.json`,
with the record as its evidence. Battery's pipeline record (`records/f05.json`)
links the record as its status evidence.

## Working decisions

- **PROTO1-D1. Reconcile; do not re-measure.** Every statement in the record
  cites a file, PR head and merge commit, or a decision. No study is re-run,
  and no figure is recomputed. Where the repository cannot show something
  (the live deployment's batch identities and root commitments, which are
  private by design), the record says so.
- **PROTO1-D2. State a stale roadmap statement, do not edit the roadmap.**
  The roadmap's "EV2 running" is stale, and EV4 is missing from it. The
  record says this. The roadmap's text stays as approved, and a correction is
  a revision for its owners.
- **PROTO1-D3. Leave other lanes' stale surfaces to them.** The battery
  programme state, the readiness record's `next_experiment` and
  `PROJECT_STATUS.md` are listed as follow-ups, not edited here:
  - the programme state is the battery lane's, and #497 also edits it;
  - a readiness record bump relays to the Workbench.
- **PROTO1-D4. Inputs, not verdicts.** §6 of the record maps existing
  battery work to the suite's items as starting material for steps 2 and 3.
  It does not say any suite item is satisfied.

## Definition of done

- The record exists, and every PR state and commit ID in it matches GitHub
  on 2026-10-02.
- `protocol.json` step 1 is `done` with the record as evidence, and battery's
  record links it. `python -m carbon.challenge_pipeline validate` and
  `render --check` pass.
- The pipeline tests pass. The hub validates and renders.

## Maturity ceiling

Documentation of repository state. Nothing is measured, qualified or
accepted.
