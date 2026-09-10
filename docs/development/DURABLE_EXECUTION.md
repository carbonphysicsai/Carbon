# Durable execution state

`carbon.execution` is the private C1 queue boundary between an A7-issued attempt
and later reconstruction/orchestration work. It persists exact source submission
and attempt identity, requester, Strategy hash, seed/generator/scoring pins,
environment, resolved-plan, reconstruction, resource and protected-evaluation
policy digests before work can be dispatched.

## State and restart contract

Admission is idempotent for identical bytes and rejects conflicts. A claim changes
`QUEUED` to `DISPATCHING` atomically and records its intent in the same transaction.
The worker marks `RUNNING` only after dispatch is known. Opening the owner after a
process restart moves `DISPATCHING` or `RUNNING` to `RECONCILIATION_REQUIRED`; it
never automatically retries. Reconciliation either proves no dispatch and requeues
the same attempt, or resumes the existing work under the same claim. Verified
partial artifact references remain available to the claim holder.

A successor attempt is accepted only when the immediately preceding attempt is
`RETRYABLE_INFRA`, its number increments by exactly one, and every requester,
Strategy, scientific, environment and policy binding remains unchanged.
Infrastructure and Strategy failures are separate terminal states. Duplicate
writes converge; mismatched replays fail closed.

## Privacy and downstream ownership

The requester status view exposes only submission ID, attempt number, state,
partial-stage count, whether a result reference was recorded, and the constant
fact that archive acknowledgement is absent. It never returns protected seed
bindings, Strategy hashes, private results, transcript references or artifacts.
Workers receive exact bindings and partial references only through a held claim.

The queue stores opaque private-result, card-record and transcript references. It
does not score, publish a card, sign an EvaluationReceipt, archive evidence, set
weights, or perform network I/O. Every recorded result remains explicitly marked
`C_EA2_ACKNOWLEDGEMENT_REQUIRED`; C-EA2 must provide verified archive durability
before any required real result can be finalized or published.
