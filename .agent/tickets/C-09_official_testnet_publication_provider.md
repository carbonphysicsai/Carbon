# C-09 — Official testnet publication and leaderboard provider

**Wave:** C1 real scientific execution foundations
**Status:** `future_reserved`; contract materialized, unselected and unstarted
**Depends on:** A10 boundary, C-06, C-07, C-EA2; real qualified provenance
**Owner:** Codex + publication/protocol engineering
**Accountable reviewer:** Protocol + scientific integration + security
**Authority:** retained C-09 identity from launch v1.0.3 §6.3; current C1/C2
separation in launch v1.0.4 §§4.2–4.3 as amended only on payment routing by
v1.0.6; Build Out/constitutional overlay and evidence-archive contracts

## Goal

Provide the Challenge-local, allow-listed official result/leaderboard projection
that can hand a real signed and archive-acknowledged C1 result toward C-W1
without giving a leaderboard or chain publisher scientific authority.

## Boundary and dependencies

A10 is reusable only as a bounded fixture projection pattern; its current
fixture leaderboard is structurally non-official and cannot be promoted or
mutated into this provider. C-06 owns signed `EvaluationReceipt` provenance,
C-07 owns orchestration and scientific-result association, and C-EA2 must prove
the required eligible real archive acknowledgement before finalization or
publication. C-W1 separately owns `TestnetWeightEligibilityEvent`; C-W2/C-W3
own winner/expiry/sink and chain publication/readback. C-09 emits no chain
intent and treats no on-chain state as scientific truth.

## Admission and projection contract

- Require exact Challenge/version, candidate/method, source submission and
  physical attempt, qualified generator/population/sampling/reference/
  measurement/Score Pack policies, implementation/environment, signed receipt,
  eligible archive acknowledgement, qualification origin and publication
  policy identities.
- Accept only current, real, qualified and uncontested provenance authorized for
  the exact Challenge-local audience. Preserve UNKNOWN and fail closed for
  missing, stale, revoked, superseded, unavailable or disputed evidence.
- Reject fixture, mock, practice, estimate, prior, forecast, scaffold,
  synthetic-archive, partial-build, infrastructure/reference failure and
  unqualified evidence nominally, before projection or downstream handoff.
- Apply an exact positive disclosure allow-list. Do not expose protected cases,
  seeds, reference answers, private transcripts, fine margins, custody details
  or another Challenge's ordering. Public display precision cannot decide rank.
- Append publication/supersession/withdrawal history; exact replay converges and
  conflicting receipt, identity or projection bytes fail closed.

## Definition of Done

- [ ] Real C-06/C-07 receipt and result identities plus an eligible real C-EA2
  acknowledgement are verified before any official projection exists.
- [ ] Challenge-local allow-list, qualification origin, audience/disclosure and
  withdrawal/supersession policies are approved and version-bound.
- [ ] Tests reject every fixture/mock/practice/synthetic/unqualified path,
  cross-Challenge rank, unsigned/stale/revoked receipts, missing archive
  acknowledgement, projection tamper, replay conflict and leakage attempt.
- [ ] Downstream tests prove C-W1 performs its own eligibility admission and
  that neither C-09 nor chain publication creates scientific merit, frontier,
  settlement or qualification authority.

## Authority ceiling

Contract materialization only. No official result exists, no public leaderboard
or testnet transaction is authorized, and no scientific, network, security,
production, settlement or LIVE qualification is earned.
