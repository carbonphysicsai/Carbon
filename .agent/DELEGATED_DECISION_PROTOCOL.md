# Delegated engineering decisions

An authorized task delegates the reversible engineering choices needed to finish
it. This document distinguishes those choices from reserved human decisions;
[the delivery protocol](DELIVERY_PROTOCOL.md) alone defines repository delivery
defaults. Current direct human instructions and actual protections still apply.

## Decide within scope

Select and implement interfaces, dependency direction, storage, canonicalization,
tests, migration mechanics and KEEP/WRAP/REPAIR/REPLACE choices that serve the
current contract. Inspect existing callers first. Avoid a new framework where a
repair or deletion completes the same flow.

Record a material decision once: the problem, choice and reason, affected
contract/boundary, and any unresolved reserved input. Include an alternative or
migration cost when it matters to review. Routine implementation detail belongs
in the existing task/PR. A lasting cross-task decision uses
`.agent/decisions/YYYY-MM-DD-<ID>.md`; do not append to frozen
`.agent/DECISIONS.md`. Do not create a decision file for every command or repair.

Notify affected owners through an already authorized channel when the choice
changes their contract, dependency or work. Do not copy one record into multiple
queues, issues, dashboards and receipts. Delivery of a notification is not
approval; no response is required for delegated work unless a dependent action
needs the receiver's artifact or custody. Observe actual changes/blocks promptly.

The historical owner/technical inboxes are issues #41/#42. They are available
when the current task calls for them, not an instruction to post externally for
every decision. Respect the current user's messaging authorization. If a peer
cannot message a destination, do not send it back to retry a rejected route.

## Reserve the actual human decisions

Agents do not select physical truth, production scientific thresholds,
populations or evidence weights, qualification, security acceptance, rights/IP
policy, live economics, production deployment or launch. A new owner-authorized
engineering migration does not by itself settle any of those values.

If such a value is missing, identify the exact behavior and authority source,
keep the value explicit and the behavior fail closed, and state the smallest
needed decision in the existing conversation/record. Reuse an existing pending
question. Continue independent fixture, schema, source or tooling work that does
not choose the missing value. Stop the whole task only if no correct bounded
work can proceed. Owner silence never supplies reserved acceptance.

An engineering choice is no longer unresolved once selected and recorded within
scope; it does not need another approval merely because it changes architecture.
Do not convert a concrete bug, package fact or missing adapter into HUMAN_INPUT.

## Changes and completion

A lead may keep, change, block or defer a decision within its actual authority.
Honor an explicit block on its affected scope, preserve the earlier record, and
make a prospective correction. Do not require a KEEP response before continuing.

A working contract may evolve with implementation. Review the final behavior,
not a ceremony around intermediate documents. Follow the single delivery policy
and actual task-specific conditions; no review/human/GPT/receipt lifecycle is
duplicated here. Engineering work may earn SPECIFIED, IMPLEMENTED and TESTED.
It does not independently earn scientific, security, production, network,
frontier, settlement, weight or emission authority.
