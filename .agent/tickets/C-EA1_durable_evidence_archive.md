# C-EA1 — Durable evidence archive

**Wave:** C1 real scientific execution foundations
**Status:** `done`
**Completion boundary:** exact synthetic development profile only, taking effect after this candidate passes applicable acceptance and normally merges
**Depends on:** C-EA0; OWNER-C-EA1-SYNTHETIC-01 approved development profile
**Owner:** Codex + evidence architecture
**Accountable reviewer:** Operations + data/security + scientific integration
**Selection authority:** `OWNER-C-EA1-SYNTHETIC-01`
**Runtime decision:** `C-EA1-D1`
**Delivery:** PR #136
**Goal:** Implement the catalogue, immutable artifact store, verified manifests, journal, outbox, and availability acknowledgement defined by C-EA0 without creating real-finalization authority.

## Selected profile

C-EA1 was selected as the sole active ticket by the owner after C-EA0 and
NET-5R/G2. Selection authorizes only the closed
`carbon.synthetic-evidence-archive.dev.v1` profile:

- non-secret synthetic C-EA1 fixtures from the existing C-01 fixture scope;
- one tenant, `carbon-synthetic-ci`, and `INTERNAL_AUDIT` as the only eligible
  named use under exact versioned synthetic policy references;
- single-host disposable PostgreSQL plus a loopback-only disposable immutable
  object service, no replicas or public endpoints;
- ephemeral external AES-256-GCM keys; only key identity and authenticated
  encryption metadata persist;
- development quotas of eight active entries, 64 objects, 2 MiB per object and
  3 MiB journal/spool bytes; these have no production meaning; and
- exact recovery after process or individual service restart, with no time
  objective and no host/site/provider/correlated-loss claim.

Every real, customer, protected or official source is rejected. Landscape,
release and commercial named uses are `INELIGIBLE` or `BLOCKED_UNKNOWN`; policy
is never inferred. Production retention, deletion/legal hold, KMS/custody,
replication, durability, availability, RTO/RPO and security qualification remain
human-reserved.

## Implemented scope and reuse

KEEP the C-01 source identities and `archive_acknowledgement_ref` seam; WRAP
them through `DurableExecutionBinding` without altering execution or scientific
meaning. The separately versioned archive runtime provides:

- stable durable admission before dispatch, immutable exact source/attempt
  binding, and `INITIAL`, `RETRY_OF` and `REEXECUTION_OF` history;
- closed capture, archive, artifact, manifest, event, policy, availability, use
  and acknowledgement models preserving all five C-EA0 axes;
- explicit PostgreSQL migrations, constraints, capacity reservation,
  transactions, append-only history, transactional outbox and idempotent
  consumer effects;
- a synchronous restart-safe encrypted stage journal/spool, immutable encrypted
  object adapter, byte/manifest retrieval verification and current availability
  check before acknowledgement;
- exact duplicate convergence, fail-closed conflicts, explicit missing,
  withdrawn and unavailable-key states, append-only reconciliation and safe
  orphan quarantine; and
- bounded non-secret health facts plus the development runbook at
  `docs/development/EVIDENCE_ARCHIVE_SYNTHETIC.md`.

No distributed transaction is assumed. The durable sequence is admission,
journal, encrypted immutable object writes, retrieve/decrypt/verify, catalogue
transaction and outbox, current availability verification, profile-scoped
acknowledgement, then idempotent effects. An upload, pointer, row, digest or
signature is insufficient by itself.

## Acceptance evidence

- Focused C-EA0/C-EA1/C-01 contracts: 61 passed; five actual-service tests skip
  only on the native host where Docker is unavailable and are mandatory in the
  canonical Linux acceptance.
- Package/import/code-authority checks: 103 passed.
- Ruff and Black: clean.
- Canonical RUNTIME_FULL acceptance must exercise actual PostgreSQL and object
  service containers at the exact PR head before merge.

The tests cover the C-EA0 cases and axes, pre-dispatch admission, linked
attempts, duplicate/conflict behavior, every persistence-stage crash boundary,
catalogue/object disagreement, corruption and wrong keys, explicit artifact
states, replay/reordering, orphan handling, service restarts, quota concurrency,
invalid/oversized/cross-tenant inputs, schema drift and key/payload non-retention.

## Definition of Done

- [x] Owner selected the exact synthetic profile and the implementation records
  its reversible operating values and exclusions.
- [x] Selected implementation, migrations and focused fault tests pass.
- [x] No acknowledgement is emitted before every positive C-EA0 predicate and
  current custody verification succeeds.
- [x] Synthetic acknowledgement is structurally ineligible for real C1
  finalization, C-W1, network weights, settlement or qualification.
- [x] Operational runbook covers lifecycle, migrations, restart,
  reconciliation, backup/restore, quotas and isolated namespace cleanup.
- [ ] Applicable canonical acceptance passes and PR #136 normally merges; only
  then does `done` and bounded `SPECIFIED / IMPLEMENTED / TESTED` take effect.

## Handoff

C-EA2 was not selected or implemented. It remains dependency-blocked on the
selected real C1 orchestration/reconstruction/execution path and an eligible real
archive profile/acknowledgement; this synthetic acknowledgement cannot satisfy
that gate. C-EA3 retains recovery/availability qualification.
