# B-01H bounded protocol

## State machine

```text
PLANNING → DEVELOPING → TESTING
    ↑                       |
    └──── FAILED/regression ┘

any role/evidence → PAUSED_HUMAN | PAUSED_INFRA
all required exact-candidate evidence → FINAL_CANDIDATE_READY
```

`FINAL_CANDIDATE_READY` is terminal inside this controller. Carbon's existing
delivery protocol remains the sole path from that candidate through exact-head
checks, fresh complete-diff Codex/GPT review, non-author approval, GPT review
gate, normal merge, exact-main verification, and external receipt.

## Packet law

All packets use schema version `1.0`, reject unknown fields, and bind the run,
iteration, authority commit/tree, ticket digest, requirements digest, exact
candidate head/tree, and emitting role profile. Validators run after JSON
Schema output and do not trust the executor.

The only requirement states are:

```text
UNTESTED
VERIFIED
FAILED
BLOCKED_HUMAN
BLOCKED_INFRA
OUT_OF_SCOPE
```

Only a Tester packet can create `VERIFIED`, and every verified result must carry
one or more accepted evidence records of a closed kind. Each evidence artifact
must have been disclosed to Tester, must be a regular candidate file, and must
match its recorded SHA-256. The controller requires Tester coverage of every
manifest requirement on each candidate. Required requirements cannot be
`OUT_OF_SCOPE`.

If a later Tester result changes `VERIFIED` to another state, the controller
records an explicit regression with prior evidence and current failure detail.
Every unresolved regression ID must lead the next `ordered_requirement_ids`.

## Identity and scope law

- The authority ref must continue to resolve to the pinned authority commit.
- The pinned authority commit must resolve to the pinned tree.
- Ticket and requirements bytes must match their SHA-256 bindings.
- The requirements manifest must bind the exact ticket path, bytes, and Git
  blob.
- Resume requires the persisted manifest digest and exact clean candidate.
- Developer output must be committed and clean; newly changed paths must match
  both the iteration plan and run-level scope, while cumulative paths must
  remain within the run-level scope.
- Planner and Tester run against projections and cannot repair the candidate.

Any mismatch fails closed without advancement.

## Protected material law

Protected hidden-evaluation paths, official private cases, credentials, private
validator state, and reconstruction-sensitive material cannot be disclosed or
persisted. Both requests and expanded tracked paths are checked. Obvious secret
keys/values in role packets are rejected before persistence.

## Maturity law

The harness can earn bounded development-tooling `SPECIFIED`, `IMPLEMENTED`,
and `TESTED` only after Carbon's complete delivery predicate. It never creates
scientific, security, network, commercial, production, `LIVE`, launch,
frontier, settlement, weight, emission, rights, review, or merge authority.
