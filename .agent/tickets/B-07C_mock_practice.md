# Ticket B-07C - Nominal mock and practice execution

**Wave:** B candidate
**Status:** `done` in bounded merged in-process synthetic-fixture scope
**Completed delivery:** PR #94 accepted head
`5c1f2551aaf3f3d23ed838050db19cd98bf95dd3` and normally merged it as
`3d48b3569a8ecc68e15f8b4a151a10c804896f52`; acceptance run `34069874204`
passed all applicable jobs and Merge gate
**Depends on:** B-02C, B-03, B-05, B-07A, B-07B, B-07S, A4, A8, A9
**Build Out:** C9/C11 mock/practice lane
**Master questions:** MQ-002, MQ-003, MQ-004, MQ-005, MQ-015, MQ-016
**Authority:** `Miner_MCP_Wave_B_Research_Contract.md` §6; A8-R15; current `Miner_MCP.md` §12

## Goal

Provide honest fixture-only reconstruction rehearsal, practice runs, and paired comparison over fresh mock-only cases while remaining mechanically outside official authority.

## Definition of Done

- [x] Consume B-07A's B-07S-ratified shared wire-visible practice types without
      redefining them; implement the domain-owned nominal
      `MockTrainEvalService`, `PracticeScopeStatement`,
      `PracticeMeasurementPack`, and mock-pack registry without schema drift.
- [x] Implement task kinds for reconstruction rehearsal, single practice run, paired common-case comparison, and resource calibration.
- [x] Require exact manifest, Strategy, resolved plan, mock pack, resource, compiler, and environment pins.
- [x] Use only mock context and role-separated fresh mock draws beneath the
      plan's abstract registered training-randomness purposes; reject every
      fixture-official or official entropy context, pack, seed, and reference
      right. Semantic parity never grants entropy parity.
- [x] Return bounded aggregate practice evidence and uncertainty allowed by policy, with no official prediction.
- [x] Allow a public qualified measurement implementation only through a nominal PracticeMeasurementPack with non-authoritative configuration; reject official thresholds, Score Packs, and A5 calls.
- [x] Implement a versioned non-champion scaffold that compiles and runs under the fixture catalog.
- [x] Keep all results mechanically unable to enter A5-A7, official leaderboard, frontier, network, or settlement.
- [x] Add mock/official type-confusion, seed, pack, context, common-case pairing, reference failure, infra failure, resource kill, no-score, no-publication, and installed-wheel tests.

These engineering criteria are implemented, focused-tested, accepted, and
normally merged in PR #94. See
`Design_Specs/Mock_Practice_Execution_Contract.md` and
`.agent/evidence/wave_b/b-07c.md`.

## Human input

SciML/statistics/security owners approve the real practice population
relationship, reference, omissions, scope statement, uncertainty treatment,
and disclosure limits. Until then the service remains in-process fixture-only.

## Must not

Use a caller mode string, fall back to official or mock truth, expose official correlation targets, or imply practice result equals official evidence.
