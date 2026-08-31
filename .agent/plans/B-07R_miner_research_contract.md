# B-07R miner research architecture plan

**Ticket:** B-07R — Miner research architecture ratification
**Branch:** `agent/b-07r-research-architecture`
**Worktree:** dedicated local worktree; absolute host path intentionally not recorded
**Exact base/current main at start:** `58ea866de52e3853b0b45e3217ee0625302aa663`
**Base tree:** `61a4463ac459f7fe96545f2746511d6940246f57`
**Scope:** B-02A evidence/governance closeout plus B-07R contract architecture;
no B-02B runtime implementation

## 1. Authority set

The ticket read and applies `CONSTITUTION.md`, root `AGENTS.md`,
`agent_pack/EXECUTION_PROTOCOL.md`, `.agent/DELEGATED_DECISION_PROTOCOL.md`,
`.agent/INVARIANTS.md`, the Wave/Wave-B board and handoff, B-02A ticket and
evidence, B-07R ticket and research contract, `Miner_MCP.md`,
`Strategy_Schema.md`, `Scientific_Challenge_Authoring_Contract.md`,
`Data_Management.md`, the relevant Build Out/overlay/Master Plan sections,
MQ-015–MQ-018, MQ-024–MQ-026, MQ-045, MQ-051,
`Design_Specs/Trustless_Verification.md`, `Design_Specs/Operations.md`,
`Design_Specs/Launch_Bar.md`, `Design_Specs/Landscape_Agent.md`,
`Design_Specs/Physics_Intelligence_System.md`, `Business/Business_Canon.md`,
`Business/Commercial_Operating_Model.md`, `docs/publications/README.md`,
`docs/publications/PUBLICATION_CLAIM_AUDIT_V3_1.md`, and
`docs/publications/SOURCE_STATUS_V3_1.md`. Quarantined legacy code is out of
scope and was not inspected.

## 2. Work plan and acceptance mapping

1. Verify B-02A remote topology, exact reviewed/merge tree equality,
   exact-head CI, Greptile result and threads, notification, and exact-main CI.
2. Repair B-02A `DOCUMENTATION_LAG` in the wave, board, ticket, evidence,
   handoff, and scientific contract without changing runtime code.
3. Select B-07R and ratify one coherent construction → research → record →
   receipt → projection → later fixture-official architecture.
4. Record B-07R-D1 through B-07R-D8 and explicit deferred-input behavior;
   remove the stale multi-human engineering preapproval gate.
5. Remove B-07S-owned exact protocol literals from B-07R authority and make
   the exact delegation/implementation layering explicit.
6. Validate scope and documents, commit, push, open one draft PR, deliver the
   issue #42 notification, and obtain exact-head CI plus Greptile review.
7. Repair every valid Greptile finding, close every Greptile thread (or record
   why an invalid finding was closed), normally merge the exact reviewed
   tree, verify the merge topology and exact-main CI, then use the conditional
   completion record instead of a recursive closeout PR.
8. Leave B-02B `todo / NOT STARTED`; after the completion predicate, select it
   only as the next ticket and report the exact main SHA/tree for a fresh
   `agent/b-02b-strategy-compilation` worktree.

## 3. Conflict classifications

| Class | Resolution |
|---|---|
| `DOCUMENTATION_LAG` | B-02A remained `in_progress` after its proven merge; B-07R still used owner-review/multi-human approval language; Wave-B/handoff used recursive closeout language. Repair in this ticket. |
| `MIGRATION_REQUIRED` | B-07R v0.3 embedded exact operation, state, selector, provider, context, and identifier choices owned by B-07S. Retain semantic requirements but delegate exact protocol mechanics. |
| `NO_CONFLICT` | v1/v2 authority separation, P/Q/w/`R_strategy`, task-record-receipt lineage, same-bytes prior fairness, conditional leakage, and no-score-predictor rules remain controlling. |
| `IMPLEMENTATION_LAG` | B-02B and B-07A–B-07G runtime types/services/stores/tests remain expected later work; implement none here. |
| `NEW_OWNER_DECISION_REQUIRED` | Real science/numeric values, security acceptance, rights/legal use/publication, economics, qualification, LIVE, launch, settlement, weight, emission, and production decisions stay unavailable under the contract's fail-closed table. |

## 4. Review and completion rule

Greptile is the routine blocking correctness review. Domain/lead notification
is asynchronous; silence is no gate. An observed `CHANGE`, `BLOCKED`, or
`REQUEST_CHANGES` affects its named change. The tracked `done` proposal becomes
effective only after exact-head CI, repair of every valid Greptile finding,
zero unresolved Greptile threads, normal merge with reviewed-tree equality,
and exact-main CI. A documented invalid finding may be closed with rationale;
any tree change requires rereview. PR/Actions/merge metadata and the
post-merge issue #42 completion comment carry the exact self-referential
identities.
