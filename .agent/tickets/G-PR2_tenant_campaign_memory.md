# G-PR2 — Tenant campaign memory and research context

**Wave:** G commercial/private/sponsored plane
**Status:** `future_reserved`; unselected and unstarted
**Goal:** Implement durable tenant-authorized campaign goals, context, experiment/answer lineage, deliverable dependencies, and correction/update state.

**Prerequisites/owners:** G-PR1 and C-DC2 patterns; customer privacy/rights, data retention, identity/tenant, product and operations owners.

**Scope and reuse:** Reuse private thread/idempotency/source-lineage patterns while keeping commercial campaign identities separate. Store customer-authorized context, goals, decisions, experiments, quotes/jobs, responses, reports and update entitlements; derived summaries never replace history.

**Interfaces/failure/limits:** Purpose permissions remain separate; no cross-tenant memory/resolution, broad training/reuse by default, or private-source existence leak. Deletion/withdrawal covers embeddings, caches, exports and backups according to approved policy.

**Acceptance tests:** tenant isolation, restore, concurrent/idempotent writes, authorization changes, deletion/withdrawal propagation, summary/source consistency, correction impact, and least-context provider calls.

**Definition of Done:** [ ] Campaign history is durable, private, purpose-bound and auditable. [ ] Rights/retention owners approve. [ ] It grants no execution or spending authority.

**Handoff:** G-PR3 consumes authorized context; G-PR5 measures repeat campaigns and usefulness.
