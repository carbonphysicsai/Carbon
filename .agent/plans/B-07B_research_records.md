# B-07B research task and private record delivery plan

**Ticket:** B-07B — Research tasks, ExperimentRecords, and receipts
**Branch:** `agent/b-07b-research-records`
**Starting base:** `30c87a83e821d5fbd27bc87c4620173d712496eb`
**Starting tree:** `f6120747cc433c8eade4e0c02b28b1c61fa99fb4`
**Primary Hub map:** `WAVE-B/B-07B`

## Eligibility and authority

Fetched `origin/main` is still the verified B-07A merge checkpoint. GitHub and
the Wave registers record B-07A done in its bounded scope and B-07B as the next
eligible, todo, unstarted ticket. Existing worktrees are clean and unrelated
work is preserved.

Authority is the root `AGENTS.md`, Constitution, invariants, Wave registers,
B-07B ticket, OWNER-DX-03 delivery and delegated-decision protocols, the exact
B-07S service protocol, B-07R research contract, Build Out and its overlay,
the owner-approved science integration sources, current maturity ledger, and
the Development Hub maintenance contract. Existing B-07A v2 types and B-02B
compiler results are implementation authority; B-07G retains composition and
dispatch ownership.

## Working contract

The implementation is one in-memory, constructor-bound requester session. A
single lock linearizes task identity, idempotency insertion, state revisions,
cancellation, polling snapshots, and terminal commits. Exact challenge,
manifest, compiler, prior, resource-policy, and resolved-plan identities are
resolved before insertion. An injected execution seam may run a queued task,
but polling is read-only and never schedules or advances work.

Private `ExperimentRecord` values are immutable and are not wire records.
Paired intervention identity is derived by comparing exact resolved-plan
surfaces, excluding downstream identity/provenance changes. Receipt findings
can only be selected from a constructor-owned disclosure catalog; execution
cannot supply public strings. Missing rights defaults to local/private-only and
an absent epistemic status remains absent.

## Delivery slices

1. Add private record, evidence, failure, retention, execution, and resolution
   types without changing the frozen v2 wire registry.
2. Implement start identity, transactional resolution/insertion, duplicate and
   conflict behavior, exact bindings, lifecycle transitions, retry, cancel
   cutoff, polling replay, terminal receipt hashing, and requester isolation.
3. Add adversarial CPU and invariant tests for every B-07B boundary, including
   installed-wheel and v1/import separation checks.
4. Run focused and affected native diagnostics, build/install a wheel, inspect
   the candidate, and record the unavailable local canonical environment once.
5. Record decisions/evidence, reconcile ticket/Wave/maturity/Hub sources,
   regenerate and validate the Hub, then use one ready PR for applicable
   acceptance and an expected-head normal merge.

## Human-reserved boundaries

No scientific interpretation, evidence promotion, security acceptance,
rights/reuse approval, retention duration, external identity, remote transport,
official submission/scoring, production qualification, or launch authority is
created. Missing permission excludes learned aggregation. The bounded local
implementation may earn only IMPLEMENTED/TESTED claims supported by tests and
ready-PR acceptance.
