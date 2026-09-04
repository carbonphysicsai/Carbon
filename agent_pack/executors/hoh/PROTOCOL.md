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
match its recorded SHA-256. Its argv must exactly match a command bound to that
requirement by the requirements manifest and name the verifier artifact. The
controller independently reruns it in the isolated candidate projection and
matches the claimed exit status and combined stdout/stderr digest; `VERIFIED`
requires exit zero. An empty authoritative command list cannot verify. The
controller requires Tester coverage of every manifest requirement on each
candidate. Required requirements cannot be `OUT_OF_SCOPE`.

If a later Tester result changes `VERIFIED` to another state, the controller
records an explicit regression with prior evidence and current failure detail.
Every unresolved regression ID must lead the next `ordered_requirement_ids`,
the action sequence must exactly follow that order, and no open regression can
reach `FINAL_CANDIDATE_READY`. Sanitized failure reason/evidence and complete
open-regression records remain structured inputs to later roles.

## Identity and scope law

- The authority ref must continue to resolve to the pinned authority commit.
- The pinned authority commit must resolve to the pinned tree.
- Ticket and requirements bytes must match their SHA-256 bindings.
- The requirements manifest must bind the exact ticket path, bytes, and Git
  blob.
- Initialization, resume, retry, and final handoff require authority ancestry,
  the exact clean candidate, recomputed and authorized cumulative Git scope,
  regular-file Git modes, and the protected-path boundary. Resume additionally
  requires the persisted manifest digest, lifecycle-coherent phase/plan/state,
  reauthorized disclosures, and replayed final evidence before acceptance.
- A paused run can retry only from its recorded coherent active phase after the
  same identity checks; Tester-originated pauses retain their active plan. A
  manual adapter may consume one externally supplied packet.
- Developer output must be committed and clean; newly changed paths must match
  both the iteration plan and run-level scope. Developer operates only in a
  sanitized writable projection; the controller imports its validated patch
  and creates the candidate commit, while cumulative paths remain within the
  run-level scope. Only regular-file Git modes are accepted and a failed import
  restores the exact prior candidate.
- Planner and Tester run against read-only projections and cannot repair the
  candidate.
- Codex role subprocesses receive only an allow-listed environment; ambient
  API-key and credential variables are not inherited.

Any mismatch fails closed without advancement.

## Protected material law

Protected hidden-evaluation paths, official private cases, credentials, private
validator state, and reconstruction-sensitive material cannot be disclosed or
persisted. Both requests and expanded tracked paths are checked. Obvious secret
keys/values in role packets are rejected before persistence. The mandatory
default protected-pattern set cannot be removed or weakened by a run manifest.

## Maturity law

The harness can earn bounded development-tooling `SPECIFIED`, `IMPLEMENTED`,
and `TESTED` only after Carbon's complete delivery predicate. It never creates
scientific, security, network, commercial, production, `LIVE`, launch,
frontier, settlement, weight, emission, rights, review, or merge authority.
