# Execution plan template

Use for any multi-module, protocol, persistence, concurrency, scientific, or
security-sensitive ticket. Save it as `.agent/plans/<ticket-id>.md` before
implementation. The plan is working contract support, not a human-silence
gate.

## Authority and start

**Ticket / delivery mode:** (`SINGLE_TICKET_PR` by default)
**Starting base commit/tree:**
**Relevant authority/specifications:**
**Human-reserved inputs and fail-closed seams:**

## Disposition and decisions

**Existing implementation:** (paths + `KEEP` / `WRAP` / `REPAIR` / `REPLACE`)
**Durable decisions / notification route:**
**Separate-contract exception:** (`NOT_APPLICABLE` or exact authorized reason)

## Vertical slices

1. Working contract, decisions, plan, and ticket-start state.
2. Coherent implementation/test slices.
3. Final integration, stable tracked evidence, and exact candidate audit.

**Expected manifest / explicit exclusions:**
**Tests to add:**
**Canonical commands:** (use `./scripts/dev/canonical.sh` off canonical Linux)
**Risks / stop conditions:**

## Completion predicate

State the exact-head required checks and `Merge gate`, exact-head Greptile,
valid-finding repair, zero unresolved threads, normal expected-head merge,
ordered-parent/reviewed-tree verification, exact-main `Merge gate`, bounded
maturity, and next-ticket transition. Dynamic identities belong in the
external completion receipt, not a closeout-only commit.

## Implementation result

**What shipped:**
**Focused/canonical validation outcome:**
**Deviations from plan:**
**Remaining human input / follow-up:**
