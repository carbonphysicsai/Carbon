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
| Host and environment | Ryan | **resolved: GW09-D1, stage 1 internal only** | — |
| Storage location and its jurisdiction | Ryan, Nick | unresolved | §3.2; the retention decision depends on it |
| Authenticated staff accounts (who, which roles, which team) | Ryan | unresolved | §3.3 |
| Staff credential issuance and rotation procedure | Ryan | unresolved | §3.3 |
| Sender credential and authorized sender identity | Ryan | unresolved | §3.5; until then no notification is attempted |
| Notice and consent text shown to a client before submission | Ryan, Nick, counsel | unresolved | §3.6 and any public collection |
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

*Precondition: host and environment decided — **resolved by GW09-D1**, stage 1,
internal only.*

Run `tools/team_intake_server.cjs` with `CARBON_TEAM_INTAKE_STORE`,
`CARBON_TEAM_USERS_FILE` and optionally `CARBON_TEAM_NOTIFY_DESTINATION`. It
binds `127.0.0.1` and opens no outbound connection. Reaching it from anywhere
else is the host decision, not a code change.

GW09-D1 adopts stage 1 only: an ordinary long-lived foreground process on the
supported Linux environment, bound to loopback, with no DNS record, route,
reverse proxy, tunnel, container platform or paid resource, exactly one
receiver process per store file, internal and synthetic fixtures only, and
`CARBON_TEAM_NOTIFY_DESTINATION` left unset. **Stage 2 is not adopted**, and a
working internal host is not a deployment, not a security qualification and not
authorization for client-facing collection.

Stage 1 covers check, register-draft, serving the private build and the
receiver. It does **not** cover running studies: the Workbench host is excluded
from stage-1 study execution.

#### The sequence as actually run

Store and credentials live in a private directory outside the checkout and
outside every worktree. The repository is public (§4 of the adopted
decisions), so the directory holds the instances and this document holds only
the shape: `users.json` carries credential **digests**, `tokens.env` carries the
credentials themselves at mode 0600, and neither is ever committed.

**Start.**

```sh
PRIV="$HOME/.carbon/private/stage1"          # outside the checkout
export CARBON_TEAM_INTAKE_STORE="$PRIV/store.json"
export CARBON_TEAM_USERS_FILE="$PRIV/users.json"
export CARBON_TEAM_ARCHIVE_KEYRING="$HOME/.carbon/private/stage1-keys/keyring.json"  # E1: outside the store's directory
export CARBON_TEAM_INTAKE_PORT=8789
unset CARBON_TEAM_NOTIFY_DESTINATION          # deliberately unset
node Business/Carbon_Fit/workbench/tools/team_intake_server.cjs
# Carbon private synthetic intake listening on http://127.0.0.1:8789
```

**Check.** Each of these was run and the result recorded:

| Check | Observed |
|---|---|
| Bound to loopback only | `ss -ltn` shows `127.0.0.1:8789`, not `0.0.0.0` |
| Unreachable off loopback | `curl http://<lan-ip>:8789/…` → connection refused (exit 7) |
| Unauthenticated request | `403` (as run on 2026-09-22; since E9 an unauthenticated request is `401`, and a staff credential alone opens nothing) |
| A second receiver on the same store | refuses, names the holding pid, and **never binds its port** |
| Relay a reviewed export | `201`, `disposition: ACCEPTED` |
| Relay the identical bytes again | `disposition: DEDUPLICATED` |
| Read it back as `TEAM_REVIEWER` | `200`, `ACTIVE`, `owner_team` set, `ARCHIVE_INDEFINITE` |
| Outbox with no destination | `UNCONFIGURED_SYNTHETIC`, `PENDING` |
| Attempt a delivery | `501`, stays `PENDING`, `NOT_ATTEMPTED_NO_TRANSPORT`, attempts `0` |
| Capacity | used, ceiling, and a worst-case inquiry count |

**Stop.** `kill -TERM <pid>`. The listener goes, and the writer lock is
released — verified by the lock file being absent afterwards.

**Recover.** Start again with the same command. The accepted record is read
back at the same identity and revision, with its raw bytes retained.

#### One receiver process per store file

Enforced, not merely documented. Every accepted inquiry rewrites the whole
store file, so a second process would not interleave with the first, it would
overwrite its records. The receiver takes a writer lock **before binding its
port**, so a second start fails as a start that did not happen:

```
Error: Another receiver already holds this store: process 1581732 since
2026-09-22T20:01:10.223Z. Exactly one receiver process per store file; stop
that one first, or point this one at a different store.
```

`flock(2)` would be the cleanest mechanism and would need no staleness logic,
but Node exposes no binding for it, and holding it through a `flock(1)` helper
on an inherited descriptor **does not survive the helper exiting** — measured
in this environment, where a second process acquired the lock while it was
supposedly held. So the holder is recorded instead, and staleness is *detected*
rather than assumed: a lock is stale only when its pid is gone, or is alive but
started at a different time, which is what separates a crashed holder from a
reused pid. A crashed receiver therefore does not wedge the next start, and
releasing never removes a lock this process does not hold.

### 3.2 Storage

*Precondition: storage location and jurisdiction decided.*

The store is a single JSON file written through a unique temporary file, an
fsync, a rename and a directory fsync. Its directory is created `0700` and the
file `0600`. Back it up as a whole file; a partial copy will be refused on
open, which is the intended behaviour.

**The ceiling, and why the earlier version of this section was wrong.** The
store used to be readable up to 10 MB while writes were unbounded, so a running
receiver could write a file it could never open again — and the remedy this
section gave, restoring the backup, could not help, because the backup was a
copy of the same unopenable file. Archiving does not shrink the file and
deletion requires an approved retention exception, so that state was terminal.

Writes are now refused above a ceiling that is provably below the read limit,
and the constructor refuses a configuration where it is not, so the two cannot
drift apart again. A refused write happens before any temporary file exists:
the committed store is unchanged, still openable, and its backup is
independently openable. Under GW09-D3 the structural half of retention is
adopted; the period, legal basis and approver remain Ryan's, Nick's and
counsel's under OD-25, and `legal_basis` stays `null`.

Default ceiling 32 MB, from measurement rather than preference: a reviewed
package is capped at 120 KB, a stored record costs about 2.88× its package
because the raw bytes, the validated draft and the reviewed package are all
retained, so the worst case is about 346 KB per inquiry — roughly 92 worst-case
inquiries or about 1,380 fixture-sized ones. The binding cost is not parsing (a
72 MB store parses in about 570 ms) but that every accepted inquiry rewrites the
whole file, so the ceiling sits where a write stays comfortably sub-second.

With sealing (E1, below) a record costs a further 4/3 on disk, because its
sealed content is base64. The worst case is then about 461 KB per inquiry, or
roughly 72 worst-case inquiries under the same ceiling. The ceiling itself is
unchanged. The 92 above is the plaintext figure it was set from.

**Encryption at rest and key destruction (E1).** Every record's client content
(the raw package, the validated draft, the reviewed package, the team fields and
the assessment history) is sealed on disk with AES-256-GCM, under a key that
belongs to that record alone. No key is shared, so no key spans two clients. The
seal is bound to the record's identity, so sealed content moved onto another
record is refused on open. In memory the running receiver holds plaintext. On
disk, and in every backup or archive copy of the file, there is only
ciphertext.

The keys live in a separate keyring file, set by `CARBON_TEAM_ARCHIVE_KEYRING`.
The receiver will not start without one, and a store cannot be opened without
one, so there is no path that writes a plaintext record and encrypts it later.
**The keyring must not be backed up with the store.** A backup holding both the
ciphertext and its keys is a plaintext backup. So the keyring is refused inside
the store's directory, and it has to be excluded from whatever backs the store up.

On an approved deletion exception, the record's key is destroyed **first**.
Only its tombstone remains, and it is written durably before the record is
removed. Every copy of that record, in the store and in any backup or archive,
is then unreadable, although the bytes remain. Opening such a copy shows the
record as `ARCHIVE_KEY_DESTROYED`, and every action on it answers `410`. The
tombstone keeps `RETAINED_ARCHIVE` in `did_not_reach`, because the bytes are not
reached, and records `archive_key: DESTROYED`: both statements are true.

A store written before E1 is sealed when the receiver starts. Copies of it made
before that are plaintext and stay plaintext.

**For the security review, not settled here:**

- The keyring holds key material in the clear, in a `0600` file. There is no key
  wrapping, HSM or KMS.
- A destroyed key is removed by rewriting the file. Blocks the filesystem once
  held are not scrubbed.
- A keyring that was backed up carries its keys into that backup. Destroying a
  key does not reach a backup of the keyring.
- The running process holds plaintext in memory.

**Check headroom before it matters**, rather than discovering it on a refusal:

```sh
curl -s -H "authorization: Bearer $STEWARD_TOKEN" \
  http://127.0.0.1:8789/private/capacity
```

It reports bytes used, the ceiling, the read limit, bytes remaining and a
deliberately pessimistic worst-case inquiry count. A `DATA_STEWARD` credential
reads it; a reviewer is refused.

**When the ceiling is reached**, the receiver answers `507` and writes nothing.
Two options, both deliberate: export the records and rotate to a new store file,
or raise `writeCeilingBytes` with a documented basis, which keeps the same
symmetry check. Do not expect archiving or deletion to recover space.

### 3.3 Staff accounts

*Precondition: accounts, roles and the issuance procedure decided.*

The directory file is a JSON array of accounts:

```json
[{ "principal": "<account-id>", "team": "<team>", "roles": ["TEAM_REVIEWER"],
   "token_sha256": "<sha256 of the credential>",
   "totp_secret": "<base32 TOTP secret, at least 160 bits>", "status": "ACTIVE" }]
```

**Every active account is enrolled in a second factor (E9).** The directory
refuses to load an `ACTIVE` account without a `totp_secret`. The secret is the
one thing in this file that is not a digest, because checking a TOTP code needs
it, so the file stays mode 0600 in the private directory and is never
committed. The person enrols the same secret in their own authenticator app
(RFC 6238: SHA-1, 30-second steps, six digits).

**A credential alone opens nothing.** Staff open a session with the credential
and a current code, then present the session on every other route:

```sh
curl -s -X POST http://127.0.0.1:8789/private/session \
  -H "authorization: Bearer $CREDENTIAL" -H 'content-type: application/json' \
  -d '{"code":"123456"}'            # -> {"session_token": "...", "expires_at": "..."}
curl -s http://127.0.0.1:8789/private/intake -H "authorization: Bearer $SESSION"
curl -s -X DELETE http://127.0.0.1:8789/private/session -H "authorization: Bearer $SESSION"
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
| `/private/session` | POST / DELETE | credential + second factor / the session itself |
| `/private/capacity` | GET | `DATA_STEWARD` |
| `/private/intake` | POST, with the agreement basis in headers | `INTAKE_RECEIVER` |
| `/private/intake/<id>/basis` | POST, with the basis in headers | `DATA_STEWARD` |
| `/private/intake?archived=include` | GET | `TEAM_REVIEWER` or `INTAKE_RECEIVER` |
| `/private/intake/<id>` | GET / PATCH / DELETE | reviewer / reviewer / steward |
| `/private/intake/<id>/export?archived=include` | GET | `TEAM_REVIEWER` |
| `/private/intake/<id>/archive` and `/restore` | POST | `DATA_STEWARD` |
| `/private/intake/<id>/deletion-exception` | POST | `DATA_STEWARD` |
| `/private/outbox` and `/private/outbox/<event>/attempt` | GET / POST | `NOTIFICATION_OPERATOR` |

**Every record is received under an agreement (E4).** No record can be created
without an agreement reference: the store accepts only a basis issued for a
complete set of references, so a record without one cannot be built, not merely
rejected later. The relay sends the basis in headers beside the package, because
the package bytes are the client's and are stored exactly:

| Class | When | Headers |
|---|---|---|
| `SCOPING` | Received under a mutual NDA, before any contract, so a client can get a quote | `x-carbon-record-class: SCOPING`, `x-carbon-nda-ref` |
| `STUDY` | Only after a countersigned MSA and an Order Form | `x-carbon-record-class: STUDY`, `x-carbon-msa-ref`, `x-carbon-order-form-ref` |

References are opaque identifiers for agreements held elsewhere. No agreement
text, party or term is stored with the record, and no reference is ever written
into the repository. The record's `retention.legal_basis` is
`contract:<reference>`, so it is enforced rather than filled in by hand. When the
Order Form is signed, a data steward moves a record from SCOPING to STUDY
through `/basis`. A STUDY record never goes back, and the history is
append-only. Records written before E4 carry no basis, and none is invented for
them. They answer `409` until a steward attaches the real one.

The 60-day SCOPING expiry is a retention value and belongs to E3. It stays null
until counsel confirms it, and a null does not delete anything.

**Only screened people reach client records (E7).** A record's content is
reachable only by an account screened under the configured standard, and only
once the record carries its export-control reference. This covers reading,
exporting, updating, archiving and restoring, because each of those returns the
content.

- The standard is counsel's. It is set by `CARBON_TEAM_SCREENING_STANDARD`, as an
  opaque reference. **While it is unset, no record's content is reachable by
  anyone.** Nobody can have been screened under a standard that does not exist.
  That is fail closed as intended, and until counsel decides, the receiver
  serves no content.
- Each account that may reach records carries
  `"screening": {"standard": "<the standard>", "ref": "<the screening record>"}`
  in the staff directory. A screening under a different standard does not count,
  so changing the standard invalidates every earlier screening.
- A record's export-control reference arrives with the relay as
  `x-carbon-export-control-ref`, or a data steward records it once at
  `POST /private/intake/<id>/export-control`. It is never replaced. A record
  without one, including every record written before E7, is unreachable until
  it has one.
- Actions that disclose no content stay available: the queue, retention
  planning, closure recording and the release log.

The screening records and determinations themselves live outside this store;
only their references are kept here.

**Every release is logged (E5).** An export names who it is for and why, or it
releases nothing:

```sh
curl -s http://127.0.0.1:8789/private/intake/$ID/export -H "authorization: Bearer $SESSION" \
  -H 'x-carbon-release-recipient-kind: CARBON_STAFF' -H 'x-carbon-release-recipient-ref: <opaque ref>' \
  -H 'x-carbon-release-purpose: Team review'
```

The entry is written durably **before** the content is returned: when, by whom,
to whom (`CARBON_STAFF`, `CLIENT`, `CONTRACTOR` or `OTHER`, with an opaque
reference), why, which record version, and the exported artifact's digest. A
copy sent onward by hand, such as a brief downloaded from the Workbench and
emailed, is recorded with `POST /private/intake/<id>/releases` and its artifact
digest. A data steward reads the log at `GET /private/releases?inquiry=<id>`.

Entries carry digests and references, never the client's content, so they
outlive the record. On deletion the tombstone lists every prior release by id.
`PRIOR_EXPORTS` stays in `did_not_reach`, because deletion cannot reach those
copies. The log is what lets Carbon ask for each one to be destroyed. A store
written before E5 records `PRE_E5_RELEASES_NOT_LOGGED`, rather than letting an
empty list claim that nothing was ever released. The log's limit is what it
cannot see: a copy that leaves the local Workbench and is never recorded does
not appear in it.

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

**The retention schema (E3, `retention.v2`).** One `production_period` could
not hold a closure event and two periods, so it was replaced rather than
reinterpreted:

| Field | Meaning | Value |
|---|---|---|
| `closure_event` (policy) | which events close a study | null: counsel's |
| `closure` (record) | when this record's study actually closed, and who recorded it | null until recorded |
| `active_period` | how long after closure the record stays active | null: counsel's |
| `archive_period` | how long after closure the archive is kept | null: counsel's, to be matched to the limitation period under the MSA's governing law |
| `scoping_expiry` | how long after receipt a SCOPING record is kept without an Order Form | null: counsel's. A STUDY record reads `NOT_APPLICABLE_STUDY_RECORD`, which is a different fact from unset |

No intended value is written anywhere in the code, and a null never defaults to
keeping or to deleting. Records written under `retention.v1` migrate when the
store opens, keeping their archive facts, recording `migrated_from`, and
inventing no closure or period. A v1 record that ever carried a non-null
`production_period` stops the store from opening, because splitting it would be
a guess.

**The scheduled destruction job (E2).** Deletion stops being exception-only. The
values are counsel's, and they are **operator configuration**, never
literals: `CARBON_TEAM_RETENTION_VALUES_FILE` names a JSON file with exactly
`closure_events` (a list of event names), `active_period`, `archive_period` and
`scoping_expiry` (ISO-8601 durations such as `P…Y…M…D`), each allowed to be
`null`.

- **With any value null, or no file at all, the job does not run.** It records
  a `REFUSED` run naming every missing value and applies nothing. It does not
  skip a record silently and does not delete on a guess. Neither keeping nor
  deleting is treated as a safe default.
- **A record whose receipt time is unknown** (written before E2 and E4) also
  stops the run and is named as the blocker.
- **When everything is set:** a SCOPING record is destroyed once its expiry
  after receipt has passed. A STUDY record's clocks start at its recorded
  closure. After the active period it is archived, and after the archive period
  it is destroyed, key first, as in E1, with a tombstone of
  `DESTROYED_BY_SCHEDULE` that names the values that applied. A study with no
  recorded closure is kept.
- A data steward records a closure at `POST` through the store's
  `recordClosure`, against one of the configured closure events. With none
  configured, a closure cannot be recorded.
- `GET /private/retention/plan` shows what the job would do and why, including
  what configured values would do even while it refuses.
  `POST /private/retention/run` runs it now. Both are for data stewards only.
- The receiver runs the job once a day in-process, because it holds the store's
  writer lock, as the named system actor `scheduled-retention-job`. Every run
  is recorded in `retention_runs`, refused or not.

**Proposed, not built: a record-level hold.** The workspace edition has no
legal hold on mail, and that stays a recorded limitation. But the store has its
own destruction paths: this job, and the key destruction on an approved
deletion. Neither can currently be paused for a record under hold. Until
retention values are configured the job destroys nothing, so the risk is latent.
**A hold flag that both paths refuse should be decided before any period is
set.** Whether a hold is required at all is counsel's question.

### 3.5 Notification and the intake mailbox (E6)

*The sender identity and mailbox now exist as operator configuration. The
credential lives in the owner's password manager and is supplied at runtime.*

**Configuration.** Everything is operator configuration, read at start. None of
it is in this repository, and none of it has a default:

| Variable | Holds |
|---|---|
| `CARBON_TEAM_SMTP_HOST`, `CARBON_TEAM_SMTP_PORT` | the submission server; port 587 with STARTTLS |
| `CARBON_TEAM_SMTP_USER` | the intake account |
| `CARBON_TEAM_SMTP_FROM` | the sending identity |
| `CARBON_TEAM_NOTIFY_DESTINATION` | where notifications go; **must be on the sender's own domain** or the receiver will not start |
| `CARBON_TEAM_SMTP_CREDENTIAL_FILE` | the path to a file holding the app password, mode `0600`, outside the checkout |

With none of the SMTP variables set, no transport exists. Each attempt then
answers **501** with `NOT_ATTEMPTED_NO_TRANSPORT`, zero attempts counted, as
before. A partial configuration is refused at start, and the error names what
is missing.

**The credential.** It is read from its file at send time and at no other
point. It is never taken from the repository, from a default or from the
environment's value. It is sent only after the connection has upgraded to TLS.
If the server offers no STARTTLS, or its certificate does not verify, the result
is `TRANSPORT_REFUSED_NO_TLS` and the credential is not sent. Every failure is a
typed outcome with a fixed message, and only a server reply's code is ever
kept, never its text. A server that echoes the credential in its refusal, as
the test server deliberately does, still cannot get it into a record. An error
nobody anticipated is recorded as such, and its text is not.

| Situation | Outcome | Attempts | Route answers |
|---|---|---|---|
| no transport configured | `NOT_ATTEMPTED_NO_TRANSPORT` | 0 | 501 |
| transport configured, credential file unset, missing or empty | `NOT_ATTEMPTED_NO_CREDENTIAL` | 0 | 501 |
| credential file readable by anyone but its owner | `NOT_ATTEMPTED_CREDENTIAL_UNSAFE` | 0 | 501 |
| server offers no STARTTLS or its TLS fails to verify | `TRANSPORT_REFUSED_NO_TLS` | 1 | 502 |
| credential rejected (535) | `CREDENTIAL_REJECTED` | 1 | 502 |
| server unreachable or refused a step | `TRANSPORT_FAILED` | 1 | 502 |
| delivered | `DELIVERED` | 1 | 200 |

A missing credential and a rejected one are different outcomes. The first means
restoring a configuration; the second means checking the credential itself.

A notification carries the inquiry identifier, a digest, the queue state and
counts. It never carries the client's words, contact details or scientific
content, and it goes only to the sender's own domain. **A configured sender is
not permission to contact anyone.** Nothing here sends mail outside Carbon.

**The sequence as run.** The real receiver process, driven against a local
synthetic SMTP server with a throwaway certificate and a synthetic credential
on 2026-09-23. No real mail server, account or credential was used. The first
run with the real credential is the owner's.

| Step | Observed |
|---|---|
| Start with the transport configured and no credential file | listening |
| Relay a package (`MAIL_INTAKE`, `ENCRYPTED`) | `201` |
| Attempt the notification | `501`, `NOT_ATTEMPTED_NO_CREDENTIAL`, attempts `0`, the message names the missing variable |
| Record the mailbox steps | `MOVED_TO_TRASH` with `purge_expected_by` 30 days later, then `PERMANENTLY_REMOVED`; both `RECEIVER_ATTESTATION` |
| Stop (`SIGTERM`) | exit `0` |
| Recover: start again with the credential file set | the event is still `PENDING`, `NOT_ATTEMPTED_NO_CREDENTIAL`, attempts `0` |
| Attempt again | `200`, `DELIVERED`, attempts `1`; the server saw authentication over TLS and one message |
| Start with a wrong credential; relay a `PLAINTEXT` arrival; attempt | `502`, `CREDENTIAL_REJECTED`, attempts `1` |
| Search the store and keyring files for the credential | absent; the store on disk is sealed |

**The mailbox step, by hand.** The deletion claim starts here, with a person, so
the record says exactly what that person did and on whose word:

1. Open the package from the intake mailbox. Decrypt it on the internal machine,
   **not** in the mailbox.
2. Relay it with the record class and agreement headers, plus
   `x-carbon-intake-channel: MAIL_INTAKE` and `x-carbon-transport-arrival:
   ENCRYPTED` or `PLAINTEXT`, stating how it actually arrived.
3. Delete the message. In Gmail this **moves it to Trash**, and it is purged up
   to 30 days later. Record `MOVED_TO_TRASH` at
   `POST /private/intake/<id>/transport-copy`.
4. Empty it from Trash: open Trash, select the message, *Delete forever*. Only
   then record `PERMANENTLY_REMOVED`. A plaintext arrival is recorded as
   `required_disposition: PERMANENTLY_REMOVED_WITHOUT_DELAY`, so do step 4 at
   once.

The record moves forward only, with no `DELETED` state that would blur the two.
Each entry is `RECEIVER_ATTESTATION`, because this store cannot see the mailbox
and does not claim to.

**Known limits, recorded rather than built around:**

- The workspace edition has no Vault, so there is **no retention rule** that
  keeps a message after deletion. That is what makes the record above honest.
  It also means there is **no legal hold on mail**. If counsel requires one, it
  is an edition upgrade and an owner decision, not an engineering change.
- An administrator may be able to restore purged mail for a further window.
  This has not been verified against the account, and until it is, "permanently
  removed" means "permanently removed from the mailbox as its user sees it".
- The intake mailbox shares a pooled storage allowance. When it fills, mail
  **bounces and nobody is told**. Check the mailbox's storage when relaying.
  Nothing in the receiver watches it.

### 3.6 Notice and consent

*Precondition: reviewed notice and consent text.*

**The intake path is settled: GW09-D-INGRESS, Path A, relayed export.** A client
downloads the reviewed package and sends it to Carbon; a named `INTAKE_RECEIVER`
relays it into the receiver with an idempotency key. No public submission
endpoint is built, which is why this section is still waiting on notice text
rather than on a consent block, a notice registry, an allowlist or rate limiting
on a public POST. Building a public endpoint is a separate decision that reopens
those at full size.

Public submission stays disabled until this exists. The client-side notice and
the consent record are separate from anything in this receiver; do not write
placeholder text into a live surface.

### 3.7 Abuse handling

*Precondition: rate limits, refusal and escalation path.*

Present today: a 130 KB body limit that answers before closing the connection,
a closed input schema, no file, geometry, executable content or URL fetching,
and an identical refusal for a missing and a wrong credential.

**Mechanical controls, E9, built before the security review so the reviewer has
something to test.** Their numbers are engineering defaults in
`tools/team_staff_directory.cjs` (`DEFAULT_LIMITS`). They are not reviewed
values, and the review may change them:

| Control | Default | Refusal |
|---|---|---|
| Second factor on every active account | TOTP, ±1 step | `401` |
| A used code cannot open a second session | per account | `401` |
| Session-opening attempts per source address | 10 per 5 minutes | `429` + `Retry-After` |
| Consecutive second-factor failures before lockout | 5 | `423` + `Retry-After` |
| Lockout period | 15 minutes; a correct code is refused while locked, and live sessions end | `423` |
| Requests per session | 120 per minute | `429` + `Retry-After` |
| Session lifetime | 8 hours | `401` |

Limits: sessions, lockouts and counters live in the receiver process, so a
restart clears them, which is a reason not to restart a receiver under attack. A
wrong credential names no account and is limited per source only.

**Still absent: the escalation and abuse-response path** (who is told, what
happens after repeated lockouts, how an account is investigated). That is
policy, and it stays behind the security review. Absent is absent: do not read
the controls above as an abuse posture.

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

## 4. What the adopted decisions did and did not resolve

Adopted on owner delegation, 22 September, pending owner review. Every one is
reversible and none commits money, activates anything public, or writes a legal
conclusion.

| Adopted | Resolves |
|---|---|
| GW09-D1 — stage 1, internal only | §3.1, and nothing else |
| GW09-D-INGRESS — Path A, relayed export | the intake path §3.6 was gated on |
| GW09-D3 — the ceiling, structural half | the store wedge, not retention policy |

Still blocked, and by which row: **§3.2** storage location and jurisdiction
(Nick, plus a jurisdiction and entity only Ryan can supply); **§3.3** staff
accounts and credential issuance; **§3.4** retention period, legal basis and
approver (Ryan, Nick, counsel under OD-25 — `legal_basis` stays `null`);
**§3.5** sender credential, which stays unset; **§3.6** notice and consent text;
**§3.7** rate limiting, lockout and escalation, which remain absent; **§3.8**
incident ownership and rollback authority. Money for counsel and for the §5
security review is unanswered, and nothing legal can start until it is.

**§3.1 being resolved is not W-C progressing.** A working internal host on
loopback with synthetic fixtures is one precondition of nine, and the eight that
remain are the ones that involve a client.

## 5. What would make this deployable

Every row in §2 resolved, then a security review of the deployed surface rather
than of this repository's tests. Passing tests are not a security
qualification, and this runbook is not an authorization to provision anything.
