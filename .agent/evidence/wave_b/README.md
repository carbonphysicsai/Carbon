# Wave B evidence records

Create one Markdown record per Wave B ticket:

```text
.agent/evidence/wave_b/<ticket-id>.md
```

Use the lowercase canonical ticket ID and retain its hyphens. Examples:
`b-01.md`, `b-07d1.md`, and `b-gate.md`. Link the record from the ticket and the
Evidence column in `.agent/WAVE_B.md`.

## Stable tracked evidence

Each tracked record contains facts that can exist before the final candidate
identifies itself:

1. ticket ID, branch, starting base commit/tree, worktree status, and a
   conditional-completion pointer to external metadata;
2. exact authority versions and Master Open Question classifications;
3. Definition-of-Done item to implementation/test/evidence mapping;
4. `KEEP`, `WRAP`, `REPAIR`, `REPLACE`, and owner-decision classifications;
5. expected manifest, validation commands, invariants, and protected-field
   acceptance;
6. inherited failures and required before/after deltas;
7. applicable automated-acceptance predicate, Accountable lead-notification
   routing, and handling for an explicit blocking direction;
8. separate maturity ceilings for specification, implementation, testing,
   scientific qualification, security qualification, network qualification,
   commercial validation, and production qualification; and
9. remaining risks, smallest human decisions, and conditional closeout.

A missing, skipped, unavailable, or failed check stays visible. Do not record it
as passing evidence. Any reviewed-tree change invalidates exact-head review.
The implementation merge must preserve the reviewed tree exactly.

## External dynamic completion receipt

Final accepted head/tree, CI/check/job identities, merge commit/ordered
parents/tree, notification identity, final maturity, and next-ticket selection
are dynamic completion facts. Record them outside the accepted tree
using `.agent/templates/EXTERNAL_COMPLETION_RECEIPT.md`, in the PR body, one
normalized PR completion comment, issue #42, or a retained GitHub Actions
artifact.

A ticket candidate may coordinate its bounded `done` state and the next-ticket
selection. Under OWNER-DX-03 the transition becomes authoritative only after
the final ready revision passes its applicable automated acceptance and
`Merge gate` and normally merges with the expected-head guard. No mandatory
review receipt, human approval, `GPT review gate`, post-merge full-CI run,
recursive closeout pull request, or evidence-only commit applies.

PR-body and issue-comment edits do not change the reviewed Git tree. Correct a
stale declaration and validate the current live body/head without an empty
commit. A declaration edit cannot substitute for required repository content.

Resolve every explicit blocking direction and route applicable Accountable
lead notifications. Notification and silence remain separate from reserved
acceptance. Human-reserved authority stays fail closed.

This directory stores engineering and review evidence. It cannot create
scientific truth, security acceptance, `LIVE` authority, frontier status,
network weights, emissions, settlement, deployment, or launch approval.
