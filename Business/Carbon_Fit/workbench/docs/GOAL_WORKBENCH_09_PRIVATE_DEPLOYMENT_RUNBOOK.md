# GOAL-WORKBENCH-09 private receiver deployment runbook

Status: `ENGINEERING_READY_NOT_PROVISIONED_NOT_AUTHORIZED_FOR_CUSTOMER_COLLECTION`

W-C activation is unauthorized. This document is the operational half of
`GOAL_WORKBENCH_09_PRIVATE_DEPLOYMENT_PROPOSAL.md`: it records the procedure an
operator would follow, and it names every input that is still owner or legal
input rather than supplying a plausible value for it. A runbook that fills in
its own unresolved fields reads as ready and is the mechanism by which an
unauthorized deployment happens quietly.

Nothing here has been executed. No host exists, no route or DNS record has been
changed, no notification has been sent, and no paid resource has been
provisioned.

## 1. What is engineering-complete

These behave as specified against synthetic fixtures on a local host, and are
exercised by `tests/test_team_intake_store.cjs`,
`tests/test_team_intake_server.cjs` and `tests/test_team_journeys.cjs`:

- reviewed package v1 intake with an exact idempotency key, raw and canonical
  content identities, and a durable write before any receipt is returned;
- authenticated staff identity: a principal exists only when a presented
  credential matched a directory account, and a structurally correct literal is
  refused because nothing authenticated it;
- role checks on every store endpoint, enumerated from the class rather than
  from a maintained list;
- cross-team denial that refuses a foreign principal exactly as it refuses an
  identifier that was never issued, so the endpoint is not an existence oracle;
- append-only assessment and revision history under optimistic `If-Match`, and
  an append-only retention history: current state is overwritten by a restore,
  so on its own it cannot say who archived a record that was later restored;
- versioned retention with archive, restore, search, index and export effects,
  and deletion gated on a named, reasoned, recorded exception;
- a transactional outbox that retains the inquiry and the pending event when a
  notification fails, and which never claims a delivery it did not make;
- restart and storage-failure recovery: an interrupted write does not commit, a
  damaged store refuses to open rather than starting empty, and interrupted
  write attempts are reported rather than deleted.

TESTED, and nothing further. Not SECURITY_QUALIFIED, not PRODUCTION_QUALIFIED,
and not evidence that a deployment would be lawful or safe.

## 2. Unresolved inputs — owner and legal

Each row is required before the step that names it. None may be inferred by an
engineer, and none is filled in below.

| Field | Owner | Current value | What it blocks |
|---|---|---|---|
| Host and environment | Ryan | unresolved | every step in §3 |
| Storage location and its jurisdiction | Ryan, Nick | unresolved | §3.2; the retention decision depends on it |
| Authenticated staff accounts (who, which roles, which team) | Ryan | unresolved | §3.3 |
| Staff credential issuance and rotation procedure | Ryan | unresolved | §3.3 |
| Sender credential and authorized sender identity | Ryan | unresolved | §3.5; until then no notification is attempted |
| Notice and consent text shown to a client before submission | Ryan, Nick | unresolved | §3.6 and any public collection |
| Retention decision: period, legal basis, approver | Ryan, Nick (OD-25) | unresolved; the code carries `null` | §3.4 |
| Abuse handling: rate limits, refusal and escalation path | Ryan | unresolved | §3.7 |
| Incident ownership and rollback authority | Ryan | unresolved | §3.8 |
| Incremental cost acceptance | Ryan | unresolved | any paid provisioning |

The retention fields are `null` in `RETENTION_POLICY` rather than defaulted.
The code fails closed on them; it does not treat a null as permission, and
"archive indefinitely" is the current synthetic default disposition, not a
legal conclusion that indefinite retention is permitted.

## 3. Procedure

Each step states its precondition. A step whose precondition is unresolved is
not to be performed, worked around, or approximated with a test value.

### 3.1 Host

*Precondition: host and environment decided.*

Run `tools/team_intake_server.cjs` with `CARBON_TEAM_INTAKE_STORE`,
`CARBON_TEAM_USERS_FILE` and optionally `CARBON_TEAM_NOTIFY_DESTINATION`. It
binds `127.0.0.1` and opens no outbound connection. Reaching it from anywhere
else is the host decision, not a code change.

### 3.2 Storage

*Precondition: storage location and jurisdiction decided.*

The store is a single JSON file written through a unique temporary file, an
fsync, a rename and a directory fsync. Its directory is created `0700` and the
file `0600`. Back it up as a whole file; a partial copy will be refused on
open, which is the intended behaviour.

### 3.3 Staff accounts

*Precondition: accounts, roles and the issuance procedure decided.*

The directory file is a JSON array of accounts:

```json
[{ "principal": "<account-id>", "team": "<team>", "roles": ["TEAM_REVIEWER"],
   "token_sha256": "<sha256 of the credential>", "status": "ACTIVE" }]
```

It holds credential **digests** and never a credential. A credential is issued
out of band, is never written to this file, a commit, an export, an issue, a
log or a chat message, and two accounts may not share one digest — the
directory refuses that, because a shared credential would make every later
provenance entry name whichever account was listed first.

Roles are `INTAKE_RECEIVER`, `TEAM_REVIEWER`, `DATA_STEWARD` and
`NOTIFICATION_OPERATOR`. `DATA_STEWARD` carries archive, restore, exception
approval, deletion and recovery. Grant least privilege; the cross-team denial
in §1 is enforced from the account's `team`, so an account's team is a
deliberate choice and not a formality.

Migrated records carry `MIGRATED_TEAM_UNASSIGNED`, which no account can hold,
so they are readable by nobody until an owner assigns them. That is intentional
and must not be "fixed" by assigning them to whichever team asks.

Routes, all authenticated and role-checked in the store rather than in the
route, which is what keeps "every endpoint is checked" true as routes are added:

| Route | Method | Role |
|---|---|---|
| `/private/intake` | POST | `INTAKE_RECEIVER` |
| `/private/intake?archived=include` | GET | `TEAM_REVIEWER` or `INTAKE_RECEIVER` |
| `/private/intake/<id>` | GET / PATCH / DELETE | reviewer / reviewer / steward |
| `/private/intake/<id>/export?archived=include` | GET | `TEAM_REVIEWER` |
| `/private/intake/<id>/archive` and `/restore` | POST | `DATA_STEWARD` |
| `/private/intake/<id>/deletion-exception` | POST | `DATA_STEWARD` |
| `/private/outbox` and `/private/outbox/<event>/attempt` | GET / POST | `NOTIFICATION_OPERATOR` |

A deletion exception names its approver in the request body. It is not taken
from the authenticated caller: who approved a deletion and who carried it out
are different facts, and conflating them is how an approval disappears.

### 3.4 Retention

*Precondition: the retention decision — period, legal basis, approver.*

Until it is made: the default disposition is archive, archived records leave the
active index and search, exporting one requires an explicit request, a revision
cannot land on one until it is restored, and deletion requires an approved
exception naming an approver and a reason.

A deletion reaches the active record, the active index and pending
notifications. It does not reach retained archives, prior exports or any
provider's own records, and the tombstone says so. Do not describe deletion to
a client as complete erasure; the system cannot enforce that, and the tombstone
is deliberately written so that nobody has to take an engineer's word for what
it reached.

### 3.5 Notification

*Precondition: sender credential and authorized sender identity.*

With no transport configured, every attempt fails observably and the event stays
`PENDING`. Configuring `CARBON_TEAM_NOTIFY_DESTINATION` records where a
notification would go; it is not a mailbox credential and not permission to
contact anyone. The queued payload carries an inquiry identifier, a digest, a
queue state and counts — no client words, contact details or scientific content.

### 3.6 Notice and consent

*Precondition: reviewed notice and consent text.*

Public submission stays disabled until this exists. The client-side notice and
the consent record are separate from anything in this receiver; do not write
placeholder text into a live surface.

### 3.7 Abuse handling

*Precondition: rate limits, refusal and escalation path.*

Present today: a 130 KB body limit that answers before closing the connection,
a closed input schema, no file, geometry, executable content or URL fetching,
and an identical refusal for a missing and a wrong credential. Absent: rate
limiting, lockout and an escalation path. Absent is absent — do not read the
list of present controls as an abuse posture.

### 3.8 Incident and rollback

*Precondition: named incident owner and rollback authority.*

Rollback is: stop the process and leave the store file in place. The store is
the evidence; nothing in an incident justifies deleting it, and a deletion still
requires an approved exception.

Recovery from an interrupted write:

1. Open the store. If it refuses, the file is damaged — restore the backup.
   Do not start a fresh store to get the service back; that silently discards
   every accepted inquiry and its idempotency index, after which a client's
   retry is accepted a second time as a new record.
2. List interrupted write attempts with `pendingWriteDebris(principal)`
   (`DATA_STEWARD`). These are replacement files whose rename never happened,
   so no data is missing from the committed state.
3. Do not delete them reflexively. Another process writing the same store may
   be producing that exact file right now. Confirm no writer is running, then
   remove them.

## 4. What would make this deployable

Every row in §2 resolved, then a security review of the deployed surface rather
than of this repository's tests. Passing tests are not a security
qualification, and this runbook is not an authorization to provision anything.
