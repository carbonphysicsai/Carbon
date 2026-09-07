# B-07G implementation plan — research-service integration

**Starting main:** `46874bf682ac6e465324631f982e1120652b21b1`
**Ticket:** `.agent/tickets/B-07G_research_service_integration.md`
**Delivery:** one branch and pull request under OWNER-DX-03
**Implementation state:** implementation complete; acceptance and normal merge pending

## Ordered implementation

1. Preserve B-07S as the exact wire authority and keep the Wave-A v1 service
   and B-07F fixture-official adapter outside the v2 dispatcher.
2. Add the exact external-public and fixture constructor graphs, with no caller
   mode, provider registry, or dynamic context selection.
3. Compose all twelve ratified operations through their existing domain owners;
   keep B-07B as the only task lifecycle and state owner.
4. Enforce canonical request/reply, staged protocol errors, bounds, Challenge
   and ref consistency, disclosure projection, and TEST_ONLY isolation.
5. Check a complete deterministic operation matrix against the B-07S manifest
   and prove domain-provider substitutability at the service boundary.
6. Run focused, owner, installed-package, invariant, Hub, and canonical CI
   acceptance; merge the unchanged accepted head with the expected-head guard.

## Reuse classification

- **KEEP:** B-07A discovery/canonical core, B-07B lifecycle and records, B-07C
  scaffold/practice semantics, B-07D3 retrieval/alignment, B-07E resources,
  A2 validation, B-02B compilation, A9 v1, and B-07F isolation.
- **WRAP:** A2 validation and B-02B compilation behind their ratified provider
  protocols; all other owners are injected directly.
- **REPAIR:** typed service-boundary classification for bounds, context
  selection, and reference mismatch already required by B-07S; stale B-07F
  conditional status after merged PR #97.
- **REPLACE:** none.

## Explicit boundary

This is an in-process, fixture-contract service only. It supplies no listener,
remote identity, authentication, credentials, signing, quote, admission,
observed resource accounting, official submission/result path, real training
or reconstruction, scientific/security/rights qualification, production, or
LIVE authority.
