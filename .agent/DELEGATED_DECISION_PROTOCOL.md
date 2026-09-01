# Delegated Development Decision Protocol

**Status:** governance correction for active Carbon development
**Applies to:** coding agents, ticket executors, technical leads, and owner decision routing
**Owner inbox:** GitHub issue #41
**SciML / Technical Lead inbox:** GitHub issue #42

## 1. Purpose

Carbon uses delegated engineering authority with asynchronous lead oversight.

An active ticket authorizes the executor to make reversible engineering and architecture decisions needed to complete that ticket, provided the decision stays inside current repository authority and does not claim a human-reserved maturity or scientific fact.

Lead notification is visibility and an opportunity to intervene. It is not a pre-implementation approval gate.

The normal flow is:

```text
authorized ticket
-> agent evaluates options
-> agent selects and records recommended decision
-> agent notifies the applicable decision inbox
-> agent implements and tests
-> exact-head scope-required checks and Merge gate
-> exact-head Greptile Review
-> repair valid findings and reach zero unresolved threads
-> normal exact-expected-head merge
-> reviewed-tree and exact-main verification
-> completed normalized external receipt posted
-> bounded closeout and next ready ticket
-> lead may KEEP, MODIFY, SUPERSEDE, BLOCK, or DEFER_TO_OWNER
```

Development continues after notification unless an explicit blocking direction exists or the affected behavior requires a reserved human decision that cannot be represented fail-closed.

## 2. Agent-authorized decisions

Within an active ticket, the executor may select, record, implement, test, and recommend decisions including:

- internal architecture and package ownership within the ticket's authorized domain;
- schema shape and typed interfaces consistent with current specifications;
- public interfaces when the active ticket explicitly owns them;
- persistence and canonicalization mechanics;
- dependency direction;
- KEEP / WRAP / REPAIR / REPLACE dispositions;
- deterministic implementation choices;
- test strategy and evidence collection;
- migration mechanics that preserve current authority and historical evidence; and
- other reversible engineering choices required to satisfy the ticket Definition of Done.

These decisions do not require affirmative lead or owner approval before implementation. They require durable recording and notification when material.

## 3. Human-reserved decisions

Agents must not invent or approve:

- physical or scientific truth;
- production thresholds, tolerances, populations, SamplingPlans, evidence weights, or qualification criteria where the value itself is a scientific claim;
- scientific qualification or LIVE activation;
- security acceptance;
- legal, IP, customer-rights, or data-use policy requiring human authority;
- production economics, treasury, settlement, fee, weight, or emission policy;
- launch or deployment authorization;
- commercial acceptance or investor claims; or
- another decision explicitly reserved to a named human owner by current repository authority.

When one of these decisions is needed, the executor must preserve a typed fail-closed seam for the affected behavior, route the decision to the correct human inbox, and continue unrelated authorized work.

A reserved decision blocks the whole ticket only when no correct bounded implementation can continue without selecting the reserved value or authority.

This is the scope rule for `AGENTS.md` conflict, owner-input, and escalation
stops: the affected change or sub-scope stops and is marked blocked; unrelated
authorized work continues only while the unresolved value remains explicit
and fail closed. An agent-authorized engineering choice is no longer
unresolved after the executor selects and records the working decision and
sends any required notification.

## 4. Decision record requirements

Every material development decision must identify:

1. decision ID and ticket;
2. problem being decided;
3. agent-recommended approach;
4. implementation location and current or intended commit/PR;
5. alternatives considered and why they were rejected;
6. affected interfaces, invariants, dependencies, and later tickets;
7. reversibility and migration cost;
8. exact files or decision records to change if a lead disagrees;
9. the smallest superseding change needed; and
10. whether any human-reserved input remains.

The durable repository record lives in `.agent/DECISIONS.md` or the applicable ticket, plan, or specification. Historical decisions are never rewritten to hide that they were once active. Later changes use an explicit superseding decision.

## 5. SciML / Technical Lead inbox: issue #42

Material decisions in `@harshaa765`'s lane must be posted or updated in issue #42 and mention `@harshaa765`.

Each notification must include:

```text
Decision: <ID>
Ticket: <ticket>
Status: IMPLEMENTED_WORKING_DECISION | PROPOSED_WORKING_DECISION

Agent recommendation:
<recommended approach>

Why:
<reasoning and constraints>

Implemented / planned at:
<files, section, commit, PR>

Alternatives rejected:
<short list>

If you want to change it:
- comment `CHANGE <ID>: <direction>`; or
- submit `REQUEST_CHANGES` / `BLOCKED` on the affected PR.

To defer to Carbon owner:
- comment `DEFER_TO_OWNER <ID>: <question or recommendation>`.

Repository change path:
<exact files / decision headings to supersede>

Downstream impact:
<affected tickets / interfaces>

Agent recommendation if unchanged:
KEEP

Development status:
Continuing; no response required unless you want a change.
```

Harsh may respond with:

- `KEEP <ID>`;
- `CHANGE <ID>: <direction>`;
- `BLOCKED <ID>: <reason>`;
- a GitHub `REQUEST_CHANGES` review; or
- `DEFER_TO_OWNER <ID>: <question or recommendation>`.

`KEEP` is useful evidence but is not required for development to continue.

`CHANGE`, `BLOCKED`, or `REQUEST_CHANGES` pauses the affected change once observed. Unrelated authorized work continues.

`DEFER_TO_OWNER` routes the decision to issue #41. It does not erase Harsh's recommendation or prior analysis. The owner receives the full decision package and may keep, change, or supersede the working decision.

## 6. Carbon owner inbox: issue #41

Issue #41 is the live decision inbox for `@jbequ5`.

Items reach #41 when:

- repository authority reserves the decision to the Carbon owner;
- another named lead explicitly uses `DEFER_TO_OWNER`;
- a cross-domain conflict cannot be resolved within delegated development authority; or
- the owner elects to review or supersede a working decision.

An owner notification must include:

- exact decision ID and originating ticket;
- the current working decision;
- the agent recommendation;
- any lead recommendation, including Harsh's recommendation when deferred;
- implementation state and exact files/PR/commit;
- alternatives and consequences;
- whether development can continue fail-closed while the owner considers it;
- the exact repository record to modify or supersede; and
- a recommended owner action: `KEEP`, `CHANGE`, `SUPERSEDE`, or `BLOCK`.

Owner silence is not approval, but it also does not block agent-authorized engineering work. A genuinely owner-reserved value remains unavailable until the owner decides it.

## 7. Review and merge

Greptile is Carbon's routine independent correctness review before merge.
Human and domain-lead review remains asynchronous oversight unless current
authority explicitly reserves the affected value or acceptance decision to a
human. Human silence is not a gate. Review is primarily a pre-merge
correctness gate, not a universal pre-implementation gate.

A reviewer may identify defects while development is in progress. The executor repairs valid findings on the same ticket branch and requests rereview where needed.

A reviewed tree must satisfy the exact-head predicate in
`.agent/DELIVERY_PROTOCOL.md`: every scope-required check and `Merge gate`
succeeds on the unchanged exact head; Greptile succeeds on that same head;
every valid finding is repaired; unresolved Greptile thread count is zero; no
applicable `CHANGE`, `BLOCKED`, or `REQUEST_CHANGES` remains; and the base is
reconciled. Use a normal merge commit with an exact expected-head guard. Do not
squash, rebase-merge, or enable auto-merge.

Unless owner direction explicitly says to stop before merge, the authorized
end-to-end ticket session continues through that normal merge, ordered-parent
and reviewed-tree verification, fetched exact-main `Merge gate`, posting of the
completed normalized external receipt, bounded closeout, and selection of the
next ready ticket. Another owner prompt is not required solely to merge a clean
reviewed ticket.

This protocol does not weaken merge evidence or maturity accounting. Dynamic
review/check/merge identities belong in the external completion receipt, not
an evidence-only commit.

## 8. Contract-first tickets

When a ticket asks for a contract or design before implementation, the executor
should write the working contract first, record the material decisions, notify
the applicable leads, then implement against that working contract in the same
ticket branch and pull request unless a separate-contract exception in
`.agent/DELIVERY_PROTOCOL.md` is recorded. Ticket size alone is not an
exception.

The contract may evolve during implementation. Material changes receive new
decision records or supersession notes and renewed notification. Greptile and
all ticket-required review must cover the final contract, implementation,
tests, and stable evidence together.

A working contract is not the same as scientific qualification, security acceptance, LIVE authority, launch approval, or production qualification.

## 9. Maturity discipline

Delegated authority may earn:

```text
SPECIFIED
IMPLEMENTED
TESTED
```

when the applicable evidence gates are satisfied.

It cannot by itself earn:

```text
SCIENTIFICALLY_QUALIFIED
SECURITY_QUALIFIED
NETWORK_QUALIFIED
COMMERCIALLY_VALIDATED
PRODUCTION_QUALIFIED
LIVE / LAUNCH / FRONTIER / SETTLEMENT / WEIGHT / EMISSION AUTHORITY
```

unless the current human-owned qualification process explicitly grants that state.
