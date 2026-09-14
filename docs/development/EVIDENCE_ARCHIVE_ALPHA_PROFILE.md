# C-EA1 private-alpha archive profile preparation

This runbook describes the fail-closed preparation for
`carbon.alpha-evidence-archive.private.v1`. It does not activate a real archive,
issue a real `ArchiveAcknowledgement`, satisfy C-EA2, create cloud resources, or
approve protected, paid, public-network, or LIVE execution.

The accepted synthetic runtime `carbon.synthetic-evidence-archive.dev.v1`
remains unchanged and cannot be relabelled as this profile.

## Fixed prospective policy

- private PostgreSQL catalogue and private immutable/versioned object storage;
- externally supplied, versioned encryption keys, never held by a numerical
  worker;
- named uses limited to internal audit and explicitly approved non-paying
  testnet evidence;
- required attempt, source, plan, runtime, outcome, checkpoint, evidence,
  reconstruction, reference/measurement, receipt, and manifest material;
- retention for at least 90 days after last eligible use and until receipt,
  review, and dispute obligations are all closed;
- one active evaluation and a 20 GiB logical evidence quota, reserved before
  dispatch with backpressure at the boundary; and
- a target of no acknowledged-evidence loss under the declared single-host-loss
  model and restoration within 24 hours. Correlated provider/region loss and
  multi-region availability are excluded.

These are owner-selected operating targets, not demonstrated guarantees. The
profile and policy digest are content-derived from the fixed runtime model.

## Configuration doctor

Copy the checked-in example outside the repository and replace each `null` only
with an authorized, versioned reference. Do not put credentials or key bytes in
the file.

```bash
python -m carbon.evidence_archive.alpha_doctor \
  docs/development/evidence_archive_alpha_deployment.example.json
```

Exit 2 means external inputs are missing. Exit 1 means all references are
present but the deliberately absent real activation/acknowledgement
implementation and acceptance still block C-EA2. This doctor performs no
network connection and makes no daemon, database, object-store, or cloud change.
Its output contains only the profile identity, status, input names, and
fail-closed eligibility facts.

## Isolated service preflight

Canonical service tests reuse the existing PostgreSQL migration
`carbon.evidence-archive.postgresql.v1`, immutable object-store adapter, and
AES-256-GCM envelope with an ephemeral, non-secret test key. They use the exact
test tenant `carbon-alpha-archive-preflight`, verify schema and encrypted object
round trips, and exercise the fixed capacity boundary. They create neither an
`ArchiveEntry` nor an acknowledgement and cannot establish provider durability,
recovery, custody, or security acceptance.

## Exact deployment package still required

Before real acknowledgement can be implemented or C-EA2 selected, the
deployment change must bind all fields in the example configuration and add:

1. private PostgreSQL and immutable/versioned object-service adapters for the
   authorized provider/project/region;
2. least-privilege catalogue, object, journal, supervisor, audit, and recovery
   principals, with no credentials available to numerical workers;
3. an external key-service adapter and exact key-version lifecycle;
4. off-host recoverable catalogue, journal, object, and key-version dependencies
   that satisfy the declared single-host-loss acknowledgement point;
5. atomic capacity reservation and release against the 20 GiB/one-evaluation
   limits;
6. a destructive recovery rehearsal on test-owned data proving integrity and a
   restore time no greater than 24 hours;
7. the scoped security-assessment result, exact deployment authorization, and
   a content-bound deployment identity; and
8. an implementation that can issue a real profile-scoped acknowledgement only
   after all positive predicates pass.

## Cost boundary

This work provisions nothing and spends $0. A defensible estimate requires the
selected provider, project, region, retention growth, versioning/backup policy,
request rates, recovery copies, egress expectations, managed PostgreSQL shape,
logging/monitoring, and key-service pricing. The eventual authorization package
must list those unit rates and quantities separately; it must not infer cost
from the 20 GiB logical quota or claim that quota is a production forecast.

## Maturity ceiling

The code is a `SPECIFIED / IMPLEMENTED / TESTED` preparation and isolated
non-secret service preflight only. Real acknowledgement, single-host-loss
durability, 24-hour restore, protected admission, independent security
acceptance, production qualification, and C-EA2 eligibility remain unavailable.
