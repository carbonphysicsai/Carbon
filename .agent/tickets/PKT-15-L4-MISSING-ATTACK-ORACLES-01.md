# PKT-15: missing Level 4 attack oracles

Status: active bounded engineering; full six-family DoD remains conditional.
Authority: the Packets2 queue assignment and Test Lead's explicit next-item
direction, 2026-10-13. Starting main: 1b793aba1877c1cc233a109287b1cfa21cc7c0e1.
One fresh-main PR; PR Head owns merge. No Hub maintenance or receipt ceremony.

## Working scope and checkpoint

KEEP the seven existing graph oracles and their controls. WRAP Carbon's
existing G5 dispatch, frozen R6/R7 analysis, and G7 nonfinite-case detector
in three executable **declared software probes**, with known-bad inputs,
deliberately weakened specimens, valid contrasts, and mutation checks.
The six missing family identities remain unchanged; the added probes earn
software evidence only, not actual compiler containment or runtime coverage.

The adapter must not execute a session's untrusted graph or accept a
session's claimed timing/GPU evidence as a probe. Only exact engine
`AttackInput` declarations run these fixed probes. Session views return
typed NOT_RUN with an explicit unavailable reading, never HELD or invented
NOT_APPLICABLE. No real host worker, GPU, provider, or attack session runs.

Implementation order, based on reachable code:
1. G5's registered scope/deadline and fixed Carbon-program dispatch checks.
   `compile_in_isolation` dispatches through the carrier, but the battery
   graph adapter does not invoke G5; this checks dispatch guards, not a live
   compiler exploit. A nonexecuting fixture runner captures the real call.
2. R6/R7's already-frozen rule functions (1.5 underprediction ratio and
   three-times prediction safety limit). Fixture observations test rule
   discrimination; they do not establish an actual runtime prediction.
3. G7's case-level finite-output detection on Carbon-generated, validated
   CPU graph fixtures. No scientific tolerance is needed for NaN/infinity.

Remaining affected scope stays fail closed:
- fresh_cases_rerun: an authorized fresh Phase 3/Launchpad run is required;
- procedural_tables: D4's priors/hybrids rule and independent criterion are
  unresolved; graph inspection cannot declare a compact procedure invalid;
- gpu_nondeterminism: actual registered GPU reconstruction/R1 evidence is
  required; CPU fixtures or claimed backend labels cannot establish it.

The queue's two historical L4 INCONCLUSIVE results must be reported from
released aggregate evidence. Main has no such L4 result record; the pinned
public #1293 snapshot has L4 NOT_ATTACKED, so names/reasons will not be
invented or recovered by reading private attacker stores.

## Plan and acceptance

Write the contract/decision first, implement the three probes and adapter
registration, retain every existing graph assertion, add independent
known-bad/valid/mutation and session-unavailable controls, document limits,
and run relevant tests plus canonical acceptance. Full PKT-15 is not DONE
until all six requested families have the required decidable oracle and
controls and the outstanding actual-evidence/owner conditions are met.

Expected paths: this ticket; its decision; battery_level4.py;
battery_level4_checks.py; both named L4 adapter/check test files; and
docs/development/graphite/LEVEL4_ATTACK_ORACLES.md.

Native diagnostics are noncanonical. Baseline broad checks encountered
Windows fcntl absence and Python 3.12 Protocol proxy behavior; those do not
authorize repairs outside this ticket. Canonical CI supplies that baseline.
Maturity ceiling: implemented/tested development software only. No LIVE,
scientific/security qualification, accepted attack coverage, spend or host
authority is earned. Protected data and finding records are never read.
