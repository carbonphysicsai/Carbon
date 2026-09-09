# Candidate commitment and fixture acceptance

NET-3-D1 composes existing Carbon owners. `CandidateJournal` extends the NET-2
SQLite receipt database; `FixtureCandidateService` calls A7 SubmissionService,
A8 FixtureTrainEvalService and A7's A6 publication seam. Construct them explicitly
with one immutable `FixtureEvaluationContext` (exact ScorePack/environment),
existing resource limits and the authenticated receipt journal. No listener,
SDK object, key loading, arbitrary code or second scientific evaluator is added.

## Ingress and artifact identity

Authenticate the normal NET-2 `submit` envelope with challenge_id,
challenge_version and Strategy fields. Pass its journal-resolved ReceiptRef and
exact signed body to `CandidateJournal.commit`. It verifies body hash, challenge,
A2 validation and A7 canonical Strategy identity. Artifact bytes are canonical
JSON, separately SHA-256 checked and retained in the same transaction. Signed
receipts never carry private evaluator data. These records are private operator
state; this module adds no public result serialization or disclosure bypass.

A candidate key binds immutable registered evaluation context and A7 Strategy
hash. Copying the artifact, changing wallet, changing request ID or reordering
JSON keys cannot create a fresh evaluation/reward identity. Original authenticated
receipt sequence determines attribution; if commits are processed out of order,
the earlier receipt replaces the provisional one before admission. Late earlier
receipts after admission conflict rather than rewrite issued provenance. Operators
must drain the closed intake before starting a batch. Receipt order remains
independent of completion order. The reward owner selects accepted winners.

## Lifecycle and recovery

COMMITTED -> DISPATCHING -> ADMITTED -> RUNNING -> ACCEPTED_FIXTURE.
A7 alone decides admission and checks exact execution handles/pins. Only successful
A7 publication of an A5 SCORED outcome creates an accepted fixture projection.
Mandatory failure is REJECTED_SCIENCE; infrastructure failure is FAILED_INFRA and
uses A7 terminal refund. Unexpected/interrupted work remains indeterminate, never
scientific failure or acceptance. Exact completed replay returns the retained
record without another A7 call. A6 still owns public cards and disclosure budgets.

AcceptedFixtureRecord preserves the canonical binary64 score as float.hex(),
aggregate physics/robustness/accuracy legs, registered context, artifact digest,
A7 Strategy hash, submission and original authenticated identity/order. Public
rounded scores never determine acceptance or later comparison. No seeds, cases,
private margins, per-case outputs, reconstruction binding or credentials are
persisted in this projection. It is structurally fixture-only, not real accepted
science, frontier entitlement or LIVE settlement authority.

The receipt database transaction records intent before any A7 side effect.
Completed rows survive restart. A7's queue remains process-local; a crash during
DISPATCHING/ADMITTED/RUNNING or between A6 publication and projection requires
operator reconciliation. Never blindly retry these states. Preserve the database
and source evidence; restore the original process if available, otherwise retain
an indeterminate record. C1 durable real queues and evidence archive ownership
remain required. This module does not fabricate recovery of unavailable private
state or guarantee exactly-once execution across that external seam.

DEVELOPMENT bounds: at most 10,000 candidate rows globally, each artifact bounded
by the existing 65,536-byte wire limit, plus existing NET-2 receipt capacity/rate
limits. Capacity fails closed. SQLite synchronous FULL and indexed lookup bound
normal restart/replay cost. File access control, database backup and physical
storage health are operator responsibilities; hashes detect accidental changes,
not a compromised validator rewriting its entire database.

## Validation and maturity

Focused NET-1/2/3, A7 submission and A8 fixture tests plus all invariants and
quality/package/Hub acceptance. Real A3 filesystem integration runs on canonical
Linux; native Windows diagnostics skip those tests explicitly. This implements
and tests C0 fixture orchestration only. It is not localnet execution, real
scientific evaluation, security qualification, production deployment or G2.
