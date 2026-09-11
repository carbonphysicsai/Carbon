# C-EA1 durable evidence archive evidence

**Ticket:** C-EA1
**Decision:** `OWNER-C-EA1-SYNTHETIC-01`, `C-EA1-D1`
**Delivery:** PR #136
**Disposition:** bounded completion is conditional on applicable acceptance and
normal merge of the exact candidate
**Maturity ceiling:** `SPECIFIED / IMPLEMENTED / TESTED` only for
`carbon.synthetic-evidence-archive.dev.v1`

## Exact scope

The runtime accepts only marked, non-secret synthetic C-EA1 fixtures derived
from source-owned C-01 fixture bindings in tenant `carbon-synthetic-ci`.
`INTERNAL_AUDIT` under the exact synthetic policy references is the sole eligible
named use. It rejects real, customer, protected and official evidence. The
acknowledgement carries explicit facts making it ineligible for real C1
finalization, C-W1, weights, settlement and every qualification claim.

The implementation keeps C-01's execution and result owners intact. It adds a
separately versioned archive model, PostgreSQL catalogue/migration, encrypted
restart-safe stage journal, loopback-only immutable object adapter,
retrieve/decrypt/byte/manifest verification, transactional outbox, idempotent
consumer effects, append-only reconciliation, safe orphan quarantine and
profile-scoped acknowledgement evaluation.

## Pinned development services and libraries

| Component | Pin | Role and implication |
|---|---|---|
| PostgreSQL | `postgres:17.11-bookworm@sha256:051f7b7b3abdd564d5d1bd1e8c4b9c1b6e77087d1dd22020ede611c096a272e0` | disposable canonical metadata service; no production account, replica or public endpoint |
| cryptography | `50.0.1`; Apache-2.0 OR BSD-3-Clause | maintained AES-256-GCM implementation; key bytes remain external and ephemeral |
| psycopg binary | `3.3.5`; LGPL-3.0-only | narrow PostgreSQL adapter; binary extra is pinned for reproducible CI and is replaceable behind the catalogue interface |

The local object service uses Python's existing standard-library HTTP/runtime
surface and loopback endpoints only. Object paths are system-derived from
validated tenant and content identities. Payload bytes never enter PostgreSQL or
general logs; persisted journal/object bytes are authenticated ciphertext.

## Development quotas and fault boundary

Limits are eight active entries, 64 objects, 2 MiB per object and 3 MiB local
spool. Capacity is reserved transactionally before dispatch. Exact-boundary,
one-over, concurrent and released-reservation tests preserve admitted evidence
and reject/backpressure new admission without thinning or replacement.

The covered single-host fault model includes worker/process restart, individual
PostgreSQL or object-service interruption, every persistence-stage crash,
duplicate/reordered delivery, object/catalogue disagreement, corrupt/conflicting
writes, orphan objects, unavailable/wrong keys, bounded spool exhaustion and
schema drift. It requires exact byte, manifest, source-binding and catalogue
restoration after individual service restart. It excludes simultaneous
host/volume, site/region/provider and correlated loss and disaster recovery, and
sets no availability, RTO or RPO objective.

## Predicate evidence

| Required result | Evidence |
|---|---|
| C-EA0 vocabulary remains independent | all contract cases retain execution, scientific-result, completeness, qualification-origin and named-use axes |
| durable admission and attempt history | archive identity is created/reserved before dispatch; retries and re-executions are immutable linked entries |
| duplicate/conflict behavior | exact admission/object/catalogue duplicates converge; conflicting bytes or metadata fail closed |
| staged crash safety | injected faults before/after each stage replay from durable admission/journal without false acknowledgement or duplicate effects |
| positive acknowledgement | every conditionally required artifact is verified; exact policies, source binding, manifest, catalogue commit, key and current object availability are checked |
| negative acknowledgement | missing/withdrawn/unavailable-key required artifacts, corrupt/missing objects, tampered manifest/ciphertext, wrong keys or schema mismatch stay pending/rejected with stable reasons |
| outbox and orphans | duplicate/reordered replay creates one logical effect; unknown objects quarantine and reconcile only under exact authority |
| isolation and secrecy | invalid/traversal/oversized/cross-tenant inputs fail before storage access; keys/plaintext are absent from catalogue, logs and fixtures |
| profile ceiling | only synthetic INTERNAL_AUDIT is eligible; synthetic acknowledgement cannot enter C-EA2/C-W1/network paths |

## Verification

Native focused verification:

```text
pytest C-EA0/C-EA1/C-01 focused
61 passed, 5 skipped
```

The five skips are explicitly guarded actual-service tests because local Docker
was unavailable. The canonical Linux job sets `CARBON_REQUIRE_DOCKER_TESTS=1`
and must run those tests against the pinned PostgreSQL image plus a separate
loopback object-service process before merge.

Pre-acceptance run `34550288416` at `03f2a6880d0b56cf394c1a3cc58b49b1d7d84b04`
passed delivery preflight, all 204 invariants and 5,195 CPU cases. Its service
path completed initial migration, encrypted archival and positive durable
acknowledgement, then failed after PostgreSQL restart because the test harness
allowed only ten seconds for service readiness. The clean-image lane separately
passed 5,149 CPU cases but omitted the `archive` dependency group, so 16 archive
tests failed closed at the unavailable cryptography boundary. The successor
candidate propagates the pinned `chain archive` groups through clean-image
bootstrap/doctor/acceptance and waits for verified catalogue readiness within
the existing CI job ceiling. That harness bound is not an availability, RTO or
RPO objective.

```text
pytest package/import/code-authority
103 passed

ruff check ...
All checks passed

black --check ...
8 files would be left unchanged
```

The applicable classifier is `RUNTIME_FULL` because the candidate adds a runtime
package, dependencies, CI group and migrations. OWNER-DX-03 requires one ready-
candidate automated acceptance; its immutable run/head identity belongs to the
PR and completion record rather than a CI-only repository commit.

## Exclusions and handoff

No real/customer/protected/official evidence, public network, production
credential, settlement, treasury, paid inference or LIVE action occurred.
Production retention/deletion/legal hold, real artifact profiles and rights,
custody/KMS, principals/zones, provider/region/replication, correlated-loss
durability, availability, RTO/RPO and security qualification remain unapproved.

C-EA2 was not selected. It remains dependency-blocked on a selected real C1
orchestration/reconstruction/execution path and a real eligible archive profile/
acknowledgement. C-02 separately still lacks the authorized JAX repository,
immutable revision/build identity and actual training/inference interface.
