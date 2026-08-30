# Ticket B-01 - Wave B orientation and authority pin

**Wave:** B active in bounded development scope
**Status:** closeout candidate proposes `done`; authoritative `in_progress` on
current `main` until the exact closeout head is independently reviewed and
normally merged
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
exact-main push CI `33305214501` succeeded. This separate documentation
closeout therefore proposes `done`; B-01 remains authoritatively `in_progress`
until the closeout itself is independently reviewed and normally merged. The
closeout changes documentation/evidence only and starts neither B-01E nor
B-02A nor any later Wave B implementation.
