# C-EA1 synthetic evidence archive operator guide

**Scope:** disposable, single-host development and CI only. This guide does not
authorize real, customer, protected, official, production, public-network, or
LIVE evidence.

## Fixed development profile

`carbon.synthetic-evidence-archive.dev.v1` accepts only source bindings derived
from C-01 `FIXTURE_DEVELOPMENT` attempts in tenant `carbon-synthetic-ci`.
Artifacts other than the canonical source binding and capture-profile bytes must
begin with the closed synthetic fixture marker. The only eligible named use is
`INTERNAL_AUDIT` under
`policy:carbon.synthetic-internal-audit.dev.v1`; Landscape, release and
commercial uses are ineligible.

The profile conditionally requires canonical source/profile inputs, a
representative output, public-safe execution log and checkpoint. It separately
records optional debug traces and rebuildable summaries. Requiredness depends on
the execution disposition; `INTENTIONALLY_ABSENT` never satisfies a required
rule.

The development capacity values are eight active entries, 64 objects, 2 MiB of
admitted artifact bytes and 3 MiB of encrypted local spool. They are small CI
values with no production meaning. PostgreSQL and the journal reserve before an
admission returns. Pressure rejects new admission; acknowledged entries release
their active reservation. Stored history and objects are never thinned.

## Components and pins

- PostgreSQL metadata/outbox: Docker Official Image
  `postgres:17.11-bookworm@sha256:051f7b7b3abdd564d5d1bd1e8c4b9c1b6e77087d1dd22020ede611c096a272e0`
  (PostgreSQL License).
- PostgreSQL client: `psycopg[binary]==3.3.5` (LGPL-3.0-only). The adapter is
  isolated behind `PostgresCatalogue`; a later provider can replace it.
- authenticated encryption: `cryptography==50.0.1` (Apache-2.0 OR BSD-3-Clause),
  AES-256-GCM with a fresh 96-bit nonce and source/artifact/digest/key-id
  associated data.
- immutable objects: the loopback-only, one-tenant
  `python -m carbon.evidence_archive.object_service` process. It is a narrow
  disposable local service, not a production object platform.
- stage journal: SQLite with `synchronous=FULL`; encrypted artifact envelopes
  remain available across worker restart. Plain payloads and key bytes do not
  enter PostgreSQL, object metadata, general logs or journal events.

Keys are ephemeral 32-byte test values supplied to the process as
`KeyMaterial`; only key identifiers, algorithms, nonces and authentication
metadata persist. Never put a key value in arguments, configuration files,
manifests, database rows, logs or retained evidence.

## Bootstrap and migration

Install the locked development dependency group in canonical Linux:

```sh
CARBON_UV_GROUPS="archive" ./scripts/dev/bootstrap.sh
```

Start an isolated PostgreSQL container from the exact pin, with a randomly
named container, loopback-only random host port, synthetic database and
ephemeral password supplied outside repository files. Instantiate
`PostgresCatalogue(dsn, limits)` and call `migrate()` before workers start.
Migration `carbon.evidence-archive.postgresql.v1` records its exact checksum and
verifies required relations. A different checksum, missing relation or invalid
version fails closed; do not edit a deployed migration in place.

Start the object service with an isolated directory, random loopback port,
ready-file and the exact tenant:

```sh
python -m carbon.evidence_archive.object_service \
  --root /tmp/isolated-cea1-objects \
  --ready-file /tmp/isolated-cea1-ready \
  --tenant-id carbon-synthetic-ci
```

The integration test creates these services itself. There are no public ports,
replicas, production accounts or persistent credentials.

## Runtime and acknowledgement

Call `EvidenceArchive.admit` before dispatch. It returns a stable content-bound
entry identity after PostgreSQL and the local journal reserve the declaration.
Retries and re-executions use new C-01 attempts and explicit `RETRY_OF` or
`REEXECUTION_OF` links.

The replay-safe sequence is:

```text
capacity reservation and durable admission
-> encrypted bounded stage journal
-> immutable encrypted object writes
-> retrieve/decrypt/byte verification
-> catalogue transaction and transactional outbox
-> current custody-path availability verification
-> profile-scoped acknowledgement
-> idempotent consumer effect
```

`VERIFIED_DURABLE` requires the exact synthetic policy/profile references,
immutable source/attempt binding, every conditionally required artifact in
`VERIFIED`, a recomputed matching manifest identity, verified PostgreSQL rows,
available objects, the matching ephemeral key and successful authenticated
decryption. Its object is structurally `synthetic_only=true`,
`eligible_for_real_finalization=false` and `eligible_for_network_use=false`.
An upload, digest, row, pointer or old acknowledgement never substitutes for
the current checks.

Missing, withdrawn, corrupt and unavailable-key states reject or leave the
entry pending without becoming candidate physics failure. Later unavailability
uses `record_unavailability`, which appends history and does not rewrite the
manifest, acknowledgement or source result.

## Restart, reconciliation and restore

Stop dispatch before shutdown, let active calls return, then stop the object
service and PostgreSQL. Preserve the isolated PostgreSQL volume, object root and
journal together. On process restart, recreate the adapters with the same paths,
re-run `migrate()`/`verify_schema()`, supply the same ephemeral test key from its
external test owner, and replay the admission/archive call. Exact duplicates
converge; conflicts fail closed.

For the bounded backup/restore exercise, stop writers and copy the isolated
PostgreSQL logical dump, object namespace and SQLite journal as one test-owned
set. Restore into fresh disposable services, verify the migration checksum,
recompute entry/manifest/artifact identities, retrieve/decrypt every required
object and replay the outbox. The test requires exact bytes and catalogue state;
there is no time objective.

Unknown objects are quarantined with `quarantine_orphans`; they are never
assigned to a source by filename or content guess. Exact admission/journal
authority may safely replay an object into the catalogue. Reconciliation must
not rerun science or upgrade maturity.

## Health and diagnostics

Safe diagnostics are counts and closed state/reason codes: active reservations,
declared objects/bytes, journal stage, object/catalogue availability, outbox
backlog, quarantine count and acknowledgement reason. Never log payloads,
ciphertext, keys, nonces plus associated data as a reconstructable bundle,
source-private objects or exception echoes.

If PostgreSQL, the object service, the journal or the key is unavailable, stop
new acknowledgement and preserve admitted state. Nonessential consumers stop
before evidence capture. Quota exhaustion applies admission backpressure; it
does not delete or replace existing evidence.

## Cleanup and exclusions

After the test has ended and no worker uses it, stop the uniquely named
PostgreSQL container and object process, then remove the entire isolated test
namespace. C-EA1 exposes no generic entry/object deletion API and cleanup must
never target a shared directory or acknowledged production history.

This profile covers individual worker/process, PostgreSQL and object-service
restart/interruption on one disposable host; crashes at each persistence stage;
duplicate/reordered delivery; catalogue/object disagreement; tampering and
conflicting writes; orphan quarantine; unavailable keys; bounded spool/quota
exhaustion; and admission backpressure. It excludes simultaneous host/volume
loss, site/region/provider loss, correlated failures and disaster recovery. It
makes no universal losslessness, availability, RTO, RPO, production retention,
legal-hold, customer-rights, production KMS/custody, replication, security
qualification or LIVE claim.
