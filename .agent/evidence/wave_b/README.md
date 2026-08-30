# Wave B evidence records

Create one Markdown record per Wave B ticket:

```text
.agent/evidence/wave_b/<ticket-id>.md
```

Use the lowercase canonical ticket ID and retain its hyphens. Examples:
`b-01.md`, `b-07d1.md`, and `b-gate.md`. Link the record from the ticket and the
Evidence column in `.agent/WAVE_B.md`.

Each record must contain:

1. ticket ID, branch, base commit/tree, reviewed head/tree, worktree status,
   and merge commit/tree fields marked pending until post-merge closeout;
2. exact authority versions and Master Open Question classifications;
3. Definition-of-Done item to implementation/test/evidence mapping;
4. `KEEP`, `WRAP`, `REPAIR`, `REPLACE`, and owner-decision classifications;
5. exact commands, exit codes, test counts, tool versions, artifact hashes,
   inherited failures, and before/after deltas;
6. invariant and protected-field evidence;
7. independent reviewer identity/role, exact reviewed head/tree, findings,
   repairs, rereview state, Accountable-reviewer routing, and any explicit
   blocking direction plus its resolution;
8. separate maturity claims for specification, implementation, testing,
   scientific qualification, security qualification, network qualification,
   commercial validation, and production qualification;
9. remaining risks and the smallest human decisions required.

A missing, skipped, unavailable, or failed check stays visible. Do not record it
as passing evidence. Any reviewed-tree change invalidates exact-head review.
The implementation merge must preserve the reviewed tree exactly.

After implementation merge and post-merge CI, use a separate documentation
closeout to fill the merge commit/tree and CI fields, link the completed record
from the ticket and board, obtain independent closeout review, route the
candidate to the board's Accountable reviewer, resolve any explicit blocking
direction, pass required CI, normally merge, and propose `done`. Accountable
reviewer routing creates no affirmative-response or silence gate under the
controlling Wave B version 0.4 governance. The implementer cannot serve as the
independent reviewer.

This directory stores engineering and review evidence. It cannot create
scientific truth, security acceptance, LIVE authority, frontier status, network
weights, emissions, settlement, or launch approval.
