# G-PR4 — Billing, bounded spending, cancellation, refunds, and contribution

**Wave:** G commercial/private/sponsored plane
**Status:** `future_reserved`; unselected and unstarted
**Goal:** Implement retry-safe monetary authorization and contribution accounting for paid research, separate from official fees/treasury/settlement.

**Prerequisites/owners:** G-PR0 and G-PR1; finance/accounting, payments, commercial terms, job orchestration, security/fraud, support and refund owners. Human inputs: prices, tax/payment policy, limits, refund/cancellation policy, accounting approval.

**Scope and reuse:** Bind quote acceptance to idempotent fund reservation, job authorization, debit, release, cancellation/refund, adjustments and cost attribution for execution/reference/storage/inference/curation/payment/support.

**Interfaces/failure/limits:** No worker dispatch before valid reservation. Retries cannot double reserve/debit/refund. Payment never changes scientific status, queue treatment for official work, release class, score, frontier or settlement. Failure remains typed and auditable.

**Acceptance tests:** duplicate/reordered callbacks, crash at every money/job transition, expired/revoked quotes, partial cancellation, refund retry, reconciliation to commercial ledger, bounded max cost, negative-balance denial, and separation from official fee/treasury code.

**Definition of Done:** [ ] Financial owners approve ledger/reconciliation. [ ] Exactly-once economic effect under the declared model is evidenced. [ ] G-PR3 dispatch is mechanically gated.

**Handoff:** G-PR5 uses ledger facts for conversion/repeat/contribution measures.
