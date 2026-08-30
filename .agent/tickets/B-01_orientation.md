# Ticket B-01 - Wave B orientation and authority pin

**Wave:** B active in bounded development scope
**Status:** `done`
**Correction authority gate:** this status is non-authoritative on the
correction branch until the exact
`agent/b-01-closeout-correction` head is independently reviewed with all
review threads resolved, passes required PR CI, normally merges with the exact
reviewed tree preserved, and exact-main push CI on that merge succeeds; until
then the prior merged `main` state remains `in_progress`. The Wave B handoff
derives ticket selection from exact fetched `origin/main`, never from a
pull-request branch's prospective status token
**Depends on:** merged A11, merged A12, `.agent/WAVE_A_REPORT.md`, explicit Wave B activation
**Build Out:** Wave B orientation; launch `B-01`
**Master questions:** MQ-018

## Goal

Establish the exact repository, authority, dependency, and baseline state from which Wave B implementation may begin.

## Definition of Done

- [x] Record the exact commit, tree, branch, clean status, active authority files, and current CI evidence.
- [x] Confirm Wave A is closed with no conditional or unmerged ticket state.
- [x] Map current code, historical PoC/Julia/miner/Landscape code, tests, and public interfaces relevant to Wave B.
- [x] Classify each candidate component `KEEP`, `WRAP`, `REPAIR`, `REPLACE`, or `NEW_OWNER_DECISION_REQUIRED`.
- [x] Record the Wave B conflict ledger, including prior publication, inert Strategy parameters, mock/official separation, and legacy simulated-score paths.
- [x] Confirm every later ticket has an exact dependency and domain authority.
- [x] Run and record the full baseline CPU, invariant, quality, package, and applicable PoC/Julia checks without repairing failures in this ticket.
- [x] Update `.agent/ORIENTATION.md` prospectively while preserving its historical A-1 record.

## Must not

Implement B-02 or later work, invent scientific/security/economic values, normalize legacy behavior into authority, or claim Wave B readiness from orientation alone.

## Evidence

[`.agent/ORIENTATION.md`](../ORIENTATION.md) and
[`.agent/evidence/wave_b/b-01.md`](../evidence/wave_b/b-01.md) contain the
prospective orientation, canonical conflict ledger, exact commands/results,
and reviewed ticket crosswalk. Final orientation head
`82d17a1f2b1f03e27880965d5345bd3fad8811e6`, tree
`138494feaedce3f6e4a338940038d11fb73d383a`, received independent exact-head
review with no blocking finding left and all three review threads resolved.
PR #55 normally merged it as
`1fe980297897faf196e1d1d4fb845846ee08a0b7`, preserving that exact tree, and
exact-main push CI `33305214501` succeeded. GitHub then merged the PR #56
documentation closeout before independent review completed, as two-parent
commit
`d03e1e0e23005d2d61381bea3847b248d73d4fd4`, and exact-main push CI
`33306558958` succeeded. Its independent review completed after merge and left
one valid unresolved P1: the board said `done` while the wave, this ticket, and
the evidence still said authoritative `in_progress`. This bounded correction
uniformly proposes `done` across all four status-bearing records. The proposal
is non-authoritative until the correction's exact head is independently
reviewed with zero unresolved review threads, required PR CI passes, the
correction normally merges with the exact reviewed tree preserved, and
exact-main push CI on that merge succeeds. The correction changes
documentation/evidence only. The handoff derives selection from exact fetched
`origin/main`, so these prospective branch tokens start neither B-01E nor
B-02A nor any later Wave B implementation.
