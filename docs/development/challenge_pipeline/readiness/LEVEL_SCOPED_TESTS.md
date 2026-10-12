# PLT-09 batch 1: level-scoped readiness assertions

Working contract: automate P3, R7, A2, A3 and S2 at battery development Levels
2, 3 and 4, using existing implementations and public fixtures. Starting main:
`a7dae8b60bb95024c46bebef55e84641d72a3cf0`. No production, hidden, sealed,
scientific qualification, containment qualification or spend authority is earned.

`challenges.json.tests_by_level[item][str(level)]` names `challenge`, `levels`,
`basis` and repository-relative pytest `tests`. Missing level keys return
NOT_BUILT without inheriting legacy or neutral tests. Malformed records, missing
files, collection errors, failing assertions and skipped assertions return FAIL.
The five batch-1 items always require explicit scoped records, including on
other challenges. Existing `tests` wiring continues to work for other items.

P3, R7 and A3 assertions emit `READINESS_LEVEL_EVIDENCE` JSON naming their item,
challenge and level. The runner rejects missing or mismatched summaries and
includes matching summaries, test identities and source file SHA256s in evidence.
P3 exercises the level's brief, compiled delivery identity, rebuild and pod
cleanup. Its Level 4 dry run stages a graph lowered from Carbon's own benign
recipe using in-memory exported bytes; it never executes participant source.
Containment doubles test fixture orchestration only and cannot satisfy R2.

R7 exercises both role loops with a scripted ledger snapshot and checks the
actual turn messages against that independent snapshot. A2 reads each adapter's
families and both control splits, checks actual Attacker tool reachability, and
runs the registered attack/control assertions. Any unreachable family must name
a passing covering assertion; it cannot disappear from the table. A3 reads K
from the provider's recorded stop-rule schema and tests withheld/available finish.

S2 records `[2, 3, 4]` explicitly because admissibility and ranking are
level-independent. Inspection found two existing ranking paths: Graphite's
`delivery.best_improvement` filters eligibility before choosing lowest error;
EV5's `ranked_last` places gate failures below every negative-error score.
Graphite does not call EV5's function. Both paths receive known-answer assertions;
this bounded wiring change preserves their existing semantics rather than
inventing a shared score convention. Reviewer: Graphite Testing Manager.

Plan and validation: implement scoped recording and the five checks, add a
mutation for every protection, run the existing readiness/stop-rule regression
tests and new fixture/mutation tests, then run the five-item gate at each level.
Pinned GitHub CI is canonical acceptance; local Windows/WSL runs are diagnostics.
PLT-10 tracks the unavailable local canonical wrapper for managed worktrees.
The Development Hub was retired by OWNER-WORKFLOW-SPEED01; no map event or
regeneration applies. Later batches depend on this PR merging to main and retain
their current gaps. Queue execution stops at that dependency until merged.
