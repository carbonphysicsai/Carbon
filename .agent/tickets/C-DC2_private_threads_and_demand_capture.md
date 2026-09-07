# C-DC2 — Durable private threads, preferences, demand, and lineage

**Wave:** C authenticated launch communication
**Status:** `future_reserved`; unselected and unstarted
**Goal:** Implement durable idempotent intake and requester-private thread history with minimal launch demand and correction dependencies.

**Prerequisites/owners:** C-DC1; identity/tenant, data/privacy, persistence, disclosure, Operations, and correction owners.

**Scope and reuse:** Store immutable/versioned requests, messages, responses, preferences, feedback, subscriptions, update entitlements/delivery, source versions, response dependencies, and coarse purpose-permitted `DemandObservation`s. Acknowledgement follows durable acceptance; summaries never replace history.

**Interfaces/failure/limits:** Separate service delivery, demand aggregation, internal research, training, and cross-customer reuse permissions. Preserve unknown/original terms. Duplicate delivery cannot duplicate records, demand counts, updates, or later charges. Launch inbox/polling only unless transport owner approves more.

**Acceptance tests:** restart/restore, concurrency/idempotency, tenant/requester denial, deletion/withdrawal through summaries/caches/embeddings/backups, subscription/update authorization, source withdrawal state, and private-source non-disclosure.

**Definition of Done:** [ ] Durable private history and minimal launch correction/demand records pass security and recovery tests. [ ] Access does not require broad reuse/training consent. [ ] No E-D12 aggregation is smuggled into C.

**Handoff:** C-DC3 consumes authorized context; E-D12 aggregates only eligible projections; E-EA7 extends transitive correction.
