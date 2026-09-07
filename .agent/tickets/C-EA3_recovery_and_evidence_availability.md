# C-EA3 — Recovery, reconciliation, and evidence availability

**Wave:** C1 real scientific execution foundations
**Status:** `future_reserved`; unselected and unstarted
**Goal:** Prove C-EA1/2 recover admitted attempts and acknowledged evidence within the approved fault model.

**Prerequisites/owners:** C-EA2; Operations/DR, security/KMS, storage, database, orchestration, and scientific-audit owners. Human inputs: recovery objectives, correlated-failure exclusions, restore acceptance, incident owner, durability/security approval.

**Scope and reuse:** Restore catalogue, objects, keys/versions, manifests, journals, outbox and source bindings; reconcile lost workers, vanished validators, orphan objects, partial writes, and incomplete finalization. Revalidate bytes, manifest completeness, identity and permissions after restore.

**Interfaces/failure/limits:** Orphans quarantine until authorized reconciliation. Unavailable required artifacts/keys remain explicit and block finalization/use. Recovery does not silently rerun science, change historical status, or claim recovery of pre-acknowledgement destroyed values.

**Acceptance tests:** declared node/service/region and backup restore scenarios; integrity corruption; key rotation/unavailability; queue/storage pressure; catalogue/object divergence; safe orphan collection; reconciliation of every admission; evidence-read authorization after restore.

**Definition of Done:** [ ] Fault/restore report maps each declared guarantee and exclusion to evidence. [ ] Operational rollback and incident procedures are approved. [ ] Scientific/security/production qualification remain separately signed.

**Handoff:** Exact launch/Challenge owners decide production use; E-EA4 can later consume qualified views without becoming a launch prerequisite.
