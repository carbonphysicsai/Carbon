# OPT-11 Phase 4 reconciliation working decision

**Ticket:** OPT-11 PHASE4-RECONCILE-01. **Authority:** owner optimizer queue;
`.agent/DELIVERY_PROTOCOL.md` delegates this bounded engineering choice.
**Status:** development candidate for PR review, not a live spending decision.

Keep the existing research ledger's exclusive provider-call lease, fenced
settlement, idempotent `FAILED_INFRA` booking and the Graphite controller's
claim/settle path. `phase4 reconcile` accepts only the named local session.
Where its retained provider response has a valid charge within the reservation,
book that reported charge; otherwise book the full reservation and report the
basis. A malformed or over-reservation charge refuses the affected call.
Missing evidence never becomes a zero charge.

A crashed still-running session resumes with its original session key after
settlement. An already terminal session retains its immutable export and gets
a separate typed `FAILED_INFRA` closure; no controller or grant re-settlement
occurs. An already finalized weekly settlement may therefore remain
conservatively higher than later provider evidence, and no grant slot is
reclaimed. Changing those economic/accounting rules is outside this ticket.

No model or pod call is sent by reconciliation. Toy crash-point tests and
canonical exact-head checks are the acceptance evidence. This decision adds no
scientific, security, spending or LIVE authority.
