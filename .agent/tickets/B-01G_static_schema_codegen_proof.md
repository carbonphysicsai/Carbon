# Ticket B-01G — Static Schema Codegen Proof

**Wave:** B future tooling
**Status:** `todo`
**Depends on:** B-01F for delivery tooling only
**Blocks B-04:** no
**Authority:** future bounded tooling proof; no runtime or domain migration
authority

## Goal

Prove a small deterministic, checked-in static code-generation path for
repeated nominal reference and canonical-registry patterns without changing
their current bytes or runtime authority.

## Definition of Done

- [ ] Select one small shadow-generation fixture rather than a production
      domain migration.
- [ ] Generate deterministic checked-in output and prove regeneration/drift.
- [ ] Use no runtime reflection and create no generic untrusted deserializer.
- [ ] Prove current canonical bytes remain unchanged.
- [ ] Document hostile-input and authority boundaries.
- [ ] Keep any later migration prospective, domain-owned, and separately
      reviewed.

## Must not

Do not mass-migrate B-02, B-03, B-04, or another domain. Do not modify runtime
wire/canonical semantics, introduce dynamic schema discovery, or make B-01G a
dependency for B-04 implementation.

## Readiness

B-01G is intentionally queued and unstarted. B-04 resumes after B-01F's exact
completion predicate without waiting for B-01G.
