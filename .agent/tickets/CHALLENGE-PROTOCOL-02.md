# CHALLENGE-PROTOCOL-02 — Phase 1 step 2: the four stage definitions

**Status:** in progress.
**Primary Hub map_ref:** `SYSTEM/DEVELOPMENT-SEQUENCING`, `HUB_UPDATE_REQUIRED`.
**Authority:** OWNER-CHALLENGE-ROADMAP-01 (2026-10-02), OWNER-DX-03.
**Spec:** `Design_Specs/Challenge_Roadmap.md`, §01 step 2 and §02.
**Depends on:** CHALLENGE-PROTOCOL-01 (battery's status record, which the
worked example cites).

## Outcome

The roadmap's step 2, "Write the four stage definitions, with battery as the
worked example. Entry criteria, work, Graphite's permissions, output artifact
and exit gate for each stage," produces its output, a protocol draft:
- `docs/development/challenge_pipeline/PROTOCOL_DRAFT.md` (v0.1);
- the stage-output templates in `docs/development/challenge_pipeline/templates/`
  (challenge brief, design packet, frozen evidence record);
- Graphite's per-stage permission ledger as data
  (`carbon/challenge_pipeline/graphite_ledger.json`), with a check that names
  only Graphite's real roles.

Phase 1 step 2 is marked done with the draft as its evidence. The draft stays
DRAFT until the process owner locks the protocol (step 8). Steps 3 to 7 will
revise it.

## Working decisions

- **PROTO2-D1. Build on the admission protocol, do not fork it.**
  - The suite's tracks are admission's Tracks A and B.
  - Freeze pins admission's frozen study sheet.
  - The frozen evidence record is admission's evidence package, plus the
    leaderboard fields.
- **PROTO2-D2. Express Graphite's permissions in Graphite's own role
  names.** The ledger lists `RoleName` values from
  `carbon.agent_campaign.graphite.roles`. A test fails if it names a role
  that does not exist. The frozen run admits no role, and ranking admits only
  the writer.
- **PROTO2-D3. Do not wire the controller yet.** The ledger is data plus a
  pure check. Making the controller refuse a role outside its stage is
  harness work for step 3, so that battery's Test/iterate run (step 4) is
  enforced, not advisory. The draft says so (§6).
- **PROTO2-D4. Name gaps; do not fill them.** The battery worked example
  maps existing artifacts to each stage, and states each gap.
  - Gaps: no p50/p95 on reference hardware; no registered anchor set,
    disclosure budget or sealed pool; no direct-solver, interpolation or
    reduced-order baselines; EV3 not run; no graded suite.
  - Every value the roadmap sets during battery stays `HUMAN_INPUT`, with
    its proposer and approver named (§7).
- **PROTO2-D5. Reference timing hardware is a recommendation only.** The
  draft recommends a pinned RunPod CPU pod over the owner's host, because
  anyone can rent the same machine and repeat a measurement. The technical
  owner proposes, and the process owner approves at lock.

## Definition of done

- The draft covers all four stages: entry, work, Graphite, output and exit,
  each with battery's worked example. It also covers the freeze rule, stop
  rules, the ledger and the open values.
- The three templates exist and are marked DRAFT until lock.
- `protocol.json` step 2 is `done` with the draft as evidence.
  `python -m carbon.challenge_pipeline validate` and `render --check` pass.
- `tests/cpu/test_challenge_protocol.py` and the pipeline tests pass. Black,
  ruff and hygiene pass. The hub validates and renders.

## Maturity ceiling

A draft process document and a data ledger. Nothing is enforced at runtime
yet, nothing is measured, and nothing is approved.
