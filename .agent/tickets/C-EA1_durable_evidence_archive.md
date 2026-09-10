# C-EA1 — Durable evidence archive

**Wave:** C1 real scientific execution foundations
**Status:** `todo`; unselected, unstarted and input-blocked after C-EA0 delivery
**Goal:** Implement the catalogue, immutable artifact store, verified manifests, journal, outbox, and availability acknowledgement defined by C-EA0.

**Prerequisites/owners:** C-EA0; current persistence, Operations, security/KMS, privacy/data, and execution owners. Human inputs: approved PostgreSQL/object-store deployment, key custody, backup/restore, retention, capacity, and fault profile.

**Scope and reuse:** Begin with PostgreSQL metadata plus encrypted/versioned object storage, without assuming a distributed transaction. Reuse source-owned identities and lifecycle. Implement durable admission, bounded stage journaling, immutable writes, byte/manifest verification, catalogue transaction plus transactional outbox, archive acknowledgement, and idempotent consumer effects.

**Interfaces/failure/limits:** Conflicting content fails closed; identical duplicates converge. Represent missingness and object/key availability explicitly. A row, pointer, signature, or upload response is not durability or truth. Backpressure cannot silently delete evidence. No Landscape, release, runtime science, or retention-policy invention.

**Acceptance tests:** crash injection around every stage; duplicate/reordered messages; conflicting writes; object/catalogue disagreement; unavailable key/artifact; outbox replay; capacity/backpressure; immutable-history and tenant/custody authorization tests.

**Definition of Done:** [ ] Selected implementation and migration pass tests under the approved fault model. [ ] No acknowledgement is emitted before verified durability. [ ] Operational runbook and rollback preserve admitted records.

**Handoff:** C-EA2 integrates acknowledgement; C-EA3 qualifies recovery/availability.
