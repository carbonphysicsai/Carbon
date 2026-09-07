# E-EA7 — Transitive correction propagation

**Wave:** E Landscape and evidence memory
**Status:** `future_reserved`; unselected and unstarted
**Goal:** Propagate source changes through claims, briefs/priors, responses/models, reports, recipients and updates while preserving history.

**Prerequisites/owners:** E-EA6 plus C-DC2/3 minimal correction records; archive, scientific, release, model, customer-deliverable, privacy/rights and operations owners.

**Scope and reuse:** Maintain versioned reverse dependencies and recipient/update-entitlement/delivery state. Distinguish factual correction, withdrawal, permission revocation, and prospective policy change; append events, assess named uses, invalidate where required, and generate authorized linked updates.

**Interfaces/failure/limits:** Never silently rescore historical official results or mutate old responses. Notifications reveal only permitted artifacts. Model invalidation/retraining/re-release is explicit; unavailable recipients or delivery providers remain retryable/auditable within approved retention.

**Acceptance tests:** multi-hop impact closure, cycles rejected, partial/unavailable dependencies, duplicate update delivery, withdrawn permission, backup restoration, model/export/cache invalidation, tenant isolation, and historical replay.

**Definition of Done:** [ ] Every affected dependency class is detected or explicitly unsupported/fail closed. [ ] Update authorization and delivery are idempotent. [ ] Human owners approve required customer/scientific actions.

**Handoff:** E-RI1 excludes invalid candidates; G-PR2/5 incorporate campaign corrections.
