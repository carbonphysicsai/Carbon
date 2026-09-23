"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const F = require("../src/engine.js");
const { ArchiveKeyDestroyed, ArchiveKeyring } = require("./team_archive_keyring.cjs");
const I = require("../src/intake.js");
const { isAuthenticatedPrincipal } = require("./team_staff_directory.cjs");
const { isRecordBasis, stored: storedBasis } = require("./team_record_basis.cjs");

const STORE_VERSION = "carbon.private-team-intake.store.v3";
// On disk only. The file carries the v3 state with every record's client content
// sealed under that record's own archive key (E1); in memory the store is v3.
const SEALED_STORE_VERSION = "carbon.private-team-intake.store.v4-sealed";
const SEALED_FIELDS = ["raw_json", "validated_draft", "reviewed_package", "team_fields", "assessments"];
const KEY_DESTROYED = "ARCHIVE_KEY_DESTROYED";
const STORE_VERSION_V2 = "carbon.private-team-intake.store.v2";
const LEGACY_STORE_VERSION = "carbon.private-team-intake.store.v1";
const RETENTION_VERSION = "carbon.private-team-intake.retention.v1";

// The owner's direction is archival retention with approved exception handling.
// That is a design input, not a legal conclusion, so the fields a lawyer owns
// are present and explicitly unresolved rather than filled in with a guess.
// A null here is the honest state, and code must fail closed on it rather than
// treat it as permission.
const RETENTION_POLICY = Object.freeze({
  schema_version: RETENTION_VERSION,
  policy_id: "local-synthetic-archive-v1",
  default_disposition: "ARCHIVE_INDEFINITE",
  // Owner and legal, routed to Ryan and Nick under OD-25. Unresolved.
  approved_by: null,
  legal_basis: null,
  production_period: null,
  // What an approved deletion can and cannot reach, stated rather than implied.
  deletion_reaches: ["ACTIVE_RECORD", "ACTIVE_INDEX", "PENDING_NOTIFICATIONS"],
  deletion_cannot_reach: ["RETAINED_ARCHIVE", "PRIOR_EXPORTS", "PROVIDER_RECORDS"],
});
// The store ceiling, and why there are two numbers rather than one.
//
// The reader used to parse with a 10 MB limit while persist() enforced nothing.
// A running receiver therefore wrote past the reader's limit and failed only on
// the NEXT open, and the runbook's remedy — restore the backup — could not help,
// because the backup was a copy of the same unopenable file. Archive does not
// shrink the file and deletion needs an approved exception, so that state was
// terminal for the store.
//
// The fix is not a bigger number. It is that a file this class writes is always
// a file this class can read, which needs the write limit to be provably below
// the read limit rather than coincidentally below it. The constructor refuses a
// configuration where that does not hold, so the asymmetry cannot reappear by
// someone changing one of the two.
//
// Basis for the default write ceiling, measured on 2026-09-22 rather than
// guessed. A reviewed package is capped at 120 KB by `accept`; a stored record
// costs about 2.88 times its package, because the raw bytes, the validated
// draft and the reviewed package are all retained. So the worst case is roughly
// 346 KB per inquiry, and 32 MB holds about 92 of those, or about 1,380
// fixture-sized ones. The binding cost is not parsing — a 72 MB store parses in
// ~570 ms — it is that every accepted inquiry rewrites the whole file, so the
// ceiling sits where a write stays comfortably sub-second.
//
// An operator may raise it deliberately; the same symmetry check applies.
const DEFAULT_WRITE_CEILING_BYTES = 32 * 1024 * 1024;

// A sanity bound on what will be parsed at all, far above any permitted write
// ceiling, so that anything written under any accepted configuration opens.
const READ_LIMIT_BYTES = 256 * 1024 * 1024;

const RECEIPT_VERSION = "carbon.private-team-intake.receipt.v1";
const NOTIFICATION_VERSION = "carbon.private-team-intake.notification.v1";
const QUEUE_STATES = [
  "READY_FOR_REVIEW",
  "UNDER_REVIEW",
  "NEEDS_CLIENT_CLARIFICATION",
  "READY_FOR_ROUTE",
  "PARKED",
  "CLOSED",
];
const TEAM_FIELDS = ["assigned_reviewer", "note", "queue_state"];
const clone = (value) => JSON.parse(JSON.stringify(value));
const sha256 = (value) =>
  "sha256:" + crypto.createHash("sha256").update(value).digest("hex");

function emptyStore() {
  return {
    schema_version: STORE_VERSION,
    inquiries: {},
    idempotency: {},
    outbox: {},
    tombstones: {},
    exceptions: {},
    // E5: every release of a record, kept past the record's own deletion.
    releases: {},
    release_log: { since: new Date().toISOString(), origin: "NATIVE" },
  };
}

// E5. A release is anything that leaves the receiver with a record's content:
// an export through it, or a copy sent onward and recorded by the person who
// sent it. Prior exports are one of the things deletion cannot reach, and this
// log is what lets Carbon find every copy it released and ask for its
// destruction. An entry names who released what, to whom, when and why; it
// carries digests, never the content, so it can outlive the record.
// E6. The transport copy: the package as it arrived in the intake mailbox,
// before the receiver relayed it here. Two deletion states, never collapsed.
// In Gmail, deleting moves a message to Trash, where it stays for up to 30 days
// before it is purged; "deleted" while it sits in Trash would be a claim that
// cannot say what it checked. So MOVED_TO_TRASH and PERMANENTLY_REMOVED are
// different states, reached in that order, and each entry says its basis: the
// receiver's own attestation, because the mailbox step is a human one.
const TRANSPORT_CHANNELS = ["MAIL_INTAKE", "DIRECT_HANDOVER"];
const TRANSPORT_ARRIVALS = ["ENCRYPTED", "PLAINTEXT"];
const TRANSPORT_STEPS = { PRESENT_IN_MAILBOX: ["MOVED_TO_TRASH", "PERMANENTLY_REMOVED"], MOVED_TO_TRASH: ["PERMANENTLY_REMOVED"], PERMANENTLY_REMOVED: [] };
const TRASH_PURGE_DAYS = 30;

function transportAtRelay(headers = {}) {
  const channel = headers["x-carbon-intake-channel"];
  if (!TRANSPORT_CHANNELS.includes(channel))
    throw Error("A relay states its intake channel: " + TRANSPORT_CHANNELS.join(" | "));
  if (channel === "DIRECT_HANDOVER") return { channel, arrival: null, copy_state: "NO_TRANSPORT_COPY", history: [] };
  const arrival = headers["x-carbon-transport-arrival"];
  if (!TRANSPORT_ARRIVALS.includes(arrival))
    throw Error("A mailed package states how it arrived: " + TRANSPORT_ARRIVALS.join(" | "));
  return {
    channel,
    arrival,
    // A package that arrived in plaintext was readable in the mailbox. Its copy
    // is to be removed permanently, not left in Trash; the record says so.
    required_disposition: arrival === "PLAINTEXT" ? "PERMANENTLY_REMOVED_WITHOUT_DELAY" : "PERMANENTLY_REMOVED",
    copy_state: "PRESENT_IN_MAILBOX",
    history: [],
  };
}

const RECIPIENT_KINDS = ["CARBON_STAFF", "CLIENT", "CONTRACTOR", "OTHER"];
const RECIPIENT_REF = /^[A-Za-z0-9][A-Za-z0-9._:\/@-]{2,127}$/;

function releaseTerms({ recipient, purpose } = {}) {
  if (!recipient || typeof recipient !== "object" || !RECIPIENT_KINDS.includes(recipient.kind))
    throw Error("A release names its recipient: kind " + RECIPIENT_KINDS.join(" | ") + ", with a reference");
  if (typeof recipient.ref !== "string" || !RECIPIENT_REF.test(recipient.ref))
    throw Error("A release names its recipient by an opaque reference");
  if (typeof purpose !== "string" || purpose.trim().length < 3 || purpose.length > 200)
    throw Error("A release states its purpose in 3 to 200 characters");
  return { recipient: { kind: recipient.kind, ref: recipient.ref }, purpose: purpose.trim() };
}

function safeKey(value, label) {
  if (
    typeof value !== "string" ||
    !/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(value)
  )
    throw Error("Invalid " + label);
  return value;
}

function validatePrincipal(principal, action) {
  // Not "is this shaped like a principal" but "was this issued by
  // authentication". A literal with the right id, roles and team is refused
  // here, which is the whole point: nothing about such a value is malformed,
  // and a shape check cannot tell it from an authenticated one.
  if (!isAuthenticatedPrincipal(principal))
    throw Error("An authenticated staff principal is required");
  const permitted = {
    accept: ["INTAKE_RECEIVER"],
    read: ["TEAM_REVIEWER", "INTAKE_RECEIVER"],
    update: ["TEAM_REVIEWER"],
    export: ["TEAM_REVIEWER"],
    archive: ["DATA_STEWARD"],
    restore: ["DATA_STEWARD"],
    approve_exception: ["DATA_STEWARD"],
    recover: ["DATA_STEWARD"],
    delete: ["DATA_STEWARD"],
    attach_basis: ["DATA_STEWARD"],
    record_release: ["TEAM_REVIEWER", "DATA_STEWARD"],
    record_transport: ["INTAKE_RECEIVER"],
    releases: ["DATA_STEWARD"],
    search: ["TEAM_REVIEWER", "INTAKE_RECEIVER"],
    outbox: ["NOTIFICATION_OPERATOR"],
  }[action];
  if (!permitted || !principal.roles.some((role) => permitted.includes(role)))
    throw Error("Principal is not authorized for " + action);
  return principal.id;
}

/** Resolve a record for a principal, or refuse as if it did not exist.
 *
 * A foreign team gets the same refusal as a caller naming an identifier that
 * was never issued. Distinguishing the two would turn the endpoint into an
 * oracle for whether another team holds a given inquiry, which is exactly the
 * thing a private receiver is supposed to withhold.
 */
function ownedRecord(store, inquiryId, principal) {
  safeKey(inquiryId, "inquiry ID");
  const record = store.state.inquiries[inquiryId];
  if (!record || record.owner_team !== principal.team) throw Error("Inquiry not found");
  // A record whose archive key was destroyed is present as bytes and readable
  // by nobody. It is refused here, for every action, rather than returned empty.
  if (record.lifecycle === KEY_DESTROYED)
    throw Object.assign(Error("Inquiry content is unreadable: its archive key was destroyed"), { status: 410 });
  // E4: a record held without an agreement reference is not used. One written
  // before E4 carries none, and none is invented for it; a data steward
  // attaches the real one first.
  if (!record.basis)
    throw Object.assign(
      Error("Inquiry has no recorded agreement basis; a data steward must attach one before it can be used"),
      { status: 409 },
    );
  return record;
}

const sealContext = (inquiryId) => "carbon.private-team-intake:" + inquiryId;

/** The on-disk form: every record's client content sealed under its own key. */
function sealStore(state, keyring) {
  const out = clone(state);
  out.schema_version = SEALED_STORE_VERSION;
  for (const [id, record] of Object.entries(out.inquiries)) {
    if (record.lifecycle === KEY_DESTROYED) {
      const { unreadable_sealed: sealed = null, assessments: _a, ...metadata } = record;
      out.inquiries[id] = { ...metadata, sealed };
      continue;
    }
    const content = Object.fromEntries(SEALED_FIELDS.map((field) => [field, record[field]]));
    const metadata = Object.fromEntries(Object.entries(record).filter(([field]) => !SEALED_FIELDS.includes(field)));
    out.inquiries[id] = { ...metadata, sealed: keyring.seal(record.archive_key_id, content, sealContext(id)) };
  }
  return out;
}

/** Back to the v3 state. A record whose key is gone stays, unreadable. */
function unsealStore(value, keyring) {
  // Read the keyring as it is now, so a key destroyed through another handle
  // is seen as destroyed here too.
  keyring.refresh();
  const out = clone(value);
  out.schema_version = STORE_VERSION;
  for (const [id, record] of Object.entries(out.inquiries)) {
    const { sealed, ...metadata } = record;
    if (sealed === undefined) throw Error("Invalid private intake store: an unsealed record in a sealed store");
    try {
      if (sealed === null) throw new ArchiveKeyDestroyed(record.archive_key_id);
      out.inquiries[id] = { ...metadata, ...keyring.open(sealed, sealContext(id)) };
    } catch (error) {
      if (!(error instanceof ArchiveKeyDestroyed)) throw error;
      out.inquiries[id] = {
        ...metadata,
        lifecycle: KEY_DESTROYED,
        history_origin: KEY_DESTROYED,
        assessments: [],
        unreadable_sealed: sealed,
      };
    }
  }
  return out;
}

function validateStore(value) {
  if (
    !value ||
    ![STORE_VERSION, STORE_VERSION_V2, LEGACY_STORE_VERSION].includes(
      value.schema_version,
    ) ||
    !value.inquiries ||
    !value.idempotency ||
    !value.outbox ||
    !value.tombstones
  )
    throw Error("Invalid private intake store");
  if (value.schema_version === STORE_VERSION && !value.exceptions)
    throw Error("Invalid private intake store");
  // Written before E5: nothing was logged, and the log says so rather than
  // implying that an empty list means nothing was ever released.
  if (!value.releases) {
    value.releases = {};
    value.release_log = { since: new Date().toISOString(), origin: "PRE_E5_RELEASES_NOT_LOGGED" };
  }
  if ([LEGACY_STORE_VERSION, STORE_VERSION_V2].includes(value.schema_version))
    return migrate(value);
  for (const event of Object.values(value.outbox)) {
    // Written before the outcome was recorded separately from the queue state.
    // Defaulted rather than guessed: an existing attempt count is real, and
    // what its last call did is simply not known for those events.
    if (typeof event.last_outcome !== "string") event.last_outcome = "UNRECORDED";
  }
  for (const record of Object.values(value.inquiries)) {
    if (!Array.isArray(record.assessments))
      throw Error("Invalid retained assessment history");
    // The history is append-only: one entry per recorded team revision. A store
    // whose history does not account for its own version has been edited.
    const accounted = record.assessments.length + 1;
    if (record.history_origin === "NATIVE" && accounted !== record.version)
      throw Error("Retained assessment history does not match the record version");
    // An append-only list that is missing an entry from its middle looks
    // perfectly ordinary. The sequence numbers are what make a removal visible.
    const events = record.retention_events || [];
    if (events.some((event, index) => event.seq !== index + 1))
      throw Error("Retention history is not a contiguous append-only sequence");
    // Written before E4: no agreement reference was recorded, and none is
    // invented. The record stays unreachable until a steward attaches one.
    if (record.basis === undefined) {
      record.basis = null;
      record.basis_history = [];
      record.basis_origin = "PRE_E4_NONE_RECORDED";
    }
  }
  return value;
}

function migrate(value) {
  const from = value.schema_version;
  const next = clone(value);
  next.schema_version = STORE_VERSION;
  if (from === LEGACY_STORE_VERSION) {
    // A v1 store retained no per-revision history. Record that honestly rather
    // than inventing a reviewer, a time or an assessment that was never written.
    for (const record of Object.values(next.inquiries)) {
      record.assessments = [];
      record.history_origin = "MIGRATED_V1_NO_RETAINED_HISTORY";
    }
  }
  // v1 and v2 both predate the versioned retention record. Adopt the current
  // default disposition, and record that no archive action was ever taken
  // rather than back-dating one.
  next.exceptions = next.exceptions || {};
  for (const record of Object.values(next.inquiries)) {
    // Pre-v3 records carry no owning team. This value cannot equal any team a
    // directory account may hold, because account teams are lower-case by
    // construction, so a migrated record is unreachable until an owner assigns
    // it rather than quietly readable by whoever asks first.
    if (!record.owner_team) record.owner_team = "MIGRATED_TEAM_UNASSIGNED";
    // Empty rather than a reconstructed history. Nothing was retained, and an
    // invented entry would be indistinguishable from one that was recorded.
    if (!Array.isArray(record.retention_events)) record.retention_events = [];
    record.retention = {
      schema_version: RETENTION_VERSION,
      policy_id: RETENTION_POLICY.policy_id,
      disposition: RETENTION_POLICY.default_disposition,
      archived_at: null,
      archived_by: null,
      exception_id: null,
      production_period: RETENTION_POLICY.production_period,
    };
  }
  return next;
}

function appendRetentionEvent(record, action, actor, detail = {}) {
  record.retention_events = record.retention_events || [];
  record.retention_events.push({
    seq: record.retention_events.length + 1,
    action,
    actor,
    at: new Date().toISOString(),
    ...detail,
  });
  return record.retention_events[record.retention_events.length - 1];
}

function processStartTime(pid) {
  // Field 22 of /proc/<pid>/stat, after the comm field, which can itself
  // contain spaces and parentheses.
  const stat = fs.readFileSync("/proc/" + pid + "/stat", "utf8");
  return stat.slice(stat.lastIndexOf(")") + 2).split(" ")[19];
}

function processIsAlive(pid, startTime) {
  if (!Number.isSafeInteger(pid) || pid <= 0) return false;
  try {
    process.kill(pid, 0);
  } catch (error) {
    // EPERM means it exists and is not ours, which still counts as alive.
    if (error.code !== "EPERM") return false;
  }
  try {
    // A pid can be reused. Same pid at a different start time is a different
    // process, and the lock it left behind is stale.
    return processStartTime(pid) === startTime;
  } catch {
    return false;
  }
}

function readLockHolder(lockPath) {
  try {
    const value = JSON.parse(fs.readFileSync(lockPath, "utf8"));
    if (typeof value.pid !== "number") return null;
    return value;
  } catch {
    // An unreadable lock records no live holder, so it does not block a start.
    return null;
  }
}

function notification(inquiryId, record) {
  // The permitted minimal summary and an authenticated record path. No client
  // words, contact details, scientific content or reviewed package travel here;
  // a recipient must authenticate to the private receiver to read the record.
  const brief = record.validated_draft || {};
  return {
    schema_version: NOTIFICATION_VERSION,
    inquiry_id: inquiryId,
    canonical_digest: record.canonical_digest,
    record_path: "/private/intake/" + inquiryId,
    queue_state: record.team_fields.queue_state,
    summary: {
      has_contact_details: Boolean(
        record.reviewed_package &&
          record.reviewed_package.contact &&
          Object.values(record.reviewed_package.contact).some((v) => v),
      ),
      unresolved_assumption_count: Array.isArray(
        record.reviewed_package && record.reviewed_package.unresolved_assumptions,
      )
        ? record.reviewed_package.unresolved_assumptions.length
        : 0,
      unknown_field_count: Object.values(brief).filter((v) => v === "" || v === null)
        .length,
    },
    authority: "NOTIFICATION_ONLY_NOT_A_COMMITMENT_OR_SCIENTIFIC_RESULT",
  };
}

// Not a store method, so it is not an endpoint: every caller is a method that
// has already authenticated its principal.
function logRelease(store, record, actor, entry) {
  const next = clone(store.state);
  const seq = Object.keys(next.releases).length + 1;
  const releaseId = "release-" + String(seq).padStart(6, "0") + "-" + crypto.randomBytes(4).toString("hex");
  next.releases[releaseId] = {
    release_id: releaseId,
    seq,
    inquiry_id: record.inquiry_id,
    owner_team: record.owner_team,
    record_version: record.version,
    raw_sha256: record.raw_sha256,
    released_at: new Date().toISOString(),
    released_by: actor,
    ...entry,
  };
  store.persist(next);
  return clone(next.releases[releaseId]);
}


class DurableIntakeStore {
  constructor(filePath, options = {}) {
    // A destination is configuration, not consent to send. With none set the
    // outbox stays observable and every attempt fails closed and says why.
    const destination = options.destination;
    if (destination !== undefined && (typeof destination !== "string" || !destination))
      throw Error("Notification destination must be a non-empty string");
    this.destination = destination || "UNCONFIGURED_SYNTHETIC";
    const ceiling =
      options.writeCeilingBytes === undefined
        ? DEFAULT_WRITE_CEILING_BYTES
        : options.writeCeilingBytes;
    if (!Number.isSafeInteger(ceiling) || ceiling <= 0)
      throw Error("Store write ceiling must be a positive byte count");
    // The invariant, checked where it can still be acted on: a file this class
    // is willing to write must be a file it is willing to read. Configuring a
    // ceiling above the read limit is the old defect, so it is refused here
    // rather than discovered on a later open.
    if (ceiling > READ_LIMIT_BYTES)
      throw Error(
        "Store write ceiling exceeds the read limit; a store written under it " +
          "could not be opened again",
      );
    this.writeCeilingBytes = ceiling;
    this.filePath = path.resolve(filePath);
    // E1: client records are encrypted from the first one. A store without a
    // keyring cannot be opened at all, so there is no path that writes a
    // plaintext record and encrypts it later.
    if (!(options.keyring instanceof ArchiveKeyring))
      throw Error("A private intake store requires an archive keyring: client records are encrypted from the first one");
    this.keyring = options.keyring;
    const onDisk = fs.existsSync(this.filePath)
      ? F.strictJsonParse(fs.readFileSync(this.filePath, "utf8"), {
          maxBytes: READ_LIMIT_BYTES,
          maxDepth: 18,
        })
      : null;
    // A store written before E1 holds plaintext. It is opened as it is and
    // sealed by the next write, which `sealAtRest` makes happen immediately.
    this.plaintextAtRest = Boolean(onDisk && onDisk.schema_version !== SEALED_STORE_VERSION && Object.keys(onDisk.inquiries || {}).length);
    this.state = onDisk
      ? validateStore(onDisk.schema_version === SEALED_STORE_VERSION ? unsealStore(onDisk, this.keyring) : onDisk)
      : emptyStore();
  }

  /** Rewrite a pre-E1 plaintext store sealed. Earlier plaintext copies remain. */
  sealAtRest() {
    if (!this.plaintextAtRest) return false;
    this.persist(clone(this.state));
    this.plaintextAtRest = false;
    return true;
  }

  /** Take the single-writer lock for this store file, or refuse to start.
   *
   * The adopted stage-1 decision says exactly one receiver process per store
   * file. Every write rewrites the whole file, so two processes would not
   * interleave badly, they would lose each other's records wholesale. Left as
   * an operational rule that is a thing a reader must remember; held as a lock
   * it is a thing the second process cannot do.
   *
   * Real `flock(2)` would be the cleanest mechanism and needs no staleness
   * logic, but Node exposes no binding for it, and holding it through a
   * `flock(1)` helper on an inherited descriptor does not survive the helper
   * exiting — measured on 2026-09-22 in this environment, where a second
   * process acquired the lock while it was supposedly held. So the holder is
   * recorded instead, and staleness is *detected* rather than assumed: a lock
   * is stale only when its pid is gone, or is alive but started at a different
   * time, which is what distinguishes a crashed holder from a reused pid.
   *
   * Linux, which is what the adopted stage-1 environment is.
   */
  acquireWriterLock() {
    const lockPath = this.filePath + ".writer.lock";
    const mine = JSON.stringify(
      {
        pid: process.pid,
        start_time: processStartTime(process.pid),
        acquired_at: new Date().toISOString(),
      },
      null,
      2,
    );
    fs.mkdirSync(path.dirname(lockPath), { recursive: true, mode: 0o700 });
    try {
      const handle = fs.openSync(lockPath, "wx", 0o600);
      fs.writeFileSync(handle, mine + "\n");
      fs.closeSync(handle);
    } catch (error) {
      if (error.code !== "EEXIST") throw error;
      const holder = readLockHolder(lockPath);
      if (holder && processIsAlive(holder.pid, holder.start_time))
        throw Error(
          "Another receiver already holds this store: process " +
            holder.pid +
            " since " +
            holder.acquired_at +
            ". Exactly one receiver process per store file; stop that one " +
            "first, or point this one at a different store.",
        );
      // The recorded holder is gone, or its pid has been reused by a process
      // that started at a different time. Either way nothing is writing here.
      const replacement = lockPath + ".tmp-" + process.pid;
      fs.writeFileSync(replacement, mine + "\n", { mode: 0o600 });
      fs.renameSync(replacement, lockPath);
    }
    this.writerLockPath = lockPath;
    return lockPath;
  }

  /** Release the lock, but only while it still records this process. */
  releaseWriterLock() {
    if (!this.writerLockPath) return false;
    const holder = readLockHolder(this.writerLockPath);
    const path_ = this.writerLockPath;
    this.writerLockPath = null;
    if (!holder || holder.pid !== process.pid) return false;
    fs.rmSync(path_, { force: true });
    return true;
  }

  /** Bytes used, the ceiling, and what is left.
   *
   * The ceiling exists so a store cannot wedge itself, but a refusal on the
   * next accepted inquiry is a poor way to learn how close it was. This is what
   * the runbook's capacity step reads.
   */
  capacity(principal) {
    validatePrincipal(principal, "recover");
    const used = fs.existsSync(this.filePath) ? fs.statSync(this.filePath).size : 0;
    const remaining = Math.max(0, this.writeCeilingBytes - used);
    return {
      used_bytes: used,
      ceiling_bytes: this.writeCeilingBytes,
      read_limit_bytes: READ_LIMIT_BYTES,
      remaining_bytes: remaining,
      // At the worst case this class can actually be handed: a 120 KB package
      // retained three ways (measured at 2.88 times its size), then sealed,
      // which base64 expands by a further 4/3. Deliberately pessimistic,
      // because the number an operator needs is the one that cannot surprise
      // them.
      worst_case_inquiries_remaining: Math.floor(remaining / ((120_000 * 2.88 * 4) / 3)),
      inquiries: Object.keys(this.state.inquiries).length,
    };
  }

  /** Interrupted write attempts left beside the store file.
   *
   * A process killed between writing its replacement and renaming it leaves a
   * temporary file behind. The rename never happened, so no data was lost and
   * the file is debris — but this class does not delete it, because another
   * process on the same store may be writing that exact file right now, and a
   * store that tidies up a live write is worse than one that accumulates
   * debris. Recovery reports; an operator decides. The runbook names this.
   *
   * Authenticated like everything else here. It discloses no inquiry content,
   * but "which endpoints may skip the identity check" is not a judgement worth
   * making once per method, and an exemption list is a thing that grows.
   */
  pendingWriteDebris(principal) {
    validatePrincipal(principal, "recover");
    const directory = path.dirname(this.filePath);
    const prefix = path.basename(this.filePath) + ".tmp-";
    if (!fs.existsSync(directory)) return [];
    return fs
      .readdirSync(directory)
      .filter((name) => name.startsWith(prefix))
      .map((name) => path.join(directory, name))
      .sort();
  }

  persist(next) {
    // A receipt the team can act on must survive power loss, so the replacement
    // file and its directory entry both reach the disk before this returns. An
    // in-memory write followed by an acknowledgement is not a durable save.
    const directory = path.dirname(this.filePath);
    fs.mkdirSync(directory, { recursive: true, mode: 0o700 });
    // The name is unique per attempt and the file is removed on every failure
    // path. A fixed name plus an exclusive create meant that one failed write
    // left a file behind that blocked every later write with EEXIST.
    // Every record gets its own key the first time it is written, and the key
    // is durable before the store that depends on it.
    for (const record of Object.values(next.inquiries))
      if (!record.archive_key_id && record.lifecycle !== KEY_DESTROYED) record.archive_key_id = this.keyring.create();
    const serialised = JSON.stringify(sealStore(next, this.keyring), null, 2) + "\n";
    // Refused before a temporary file exists, so a refusal writes nothing at
    // all and the committed store stays exactly as it was — and stays openable,
    // which is the whole point of having a ceiling.
    const size = Buffer.byteLength(serialised, "utf8");
    if (size > this.writeCeilingBytes)
      throw Error(
        "Store write refused: " +
          size +
          " bytes exceeds the " +
          this.writeCeilingBytes +
          " byte ceiling. The store on disk is unchanged and still openable. " +
          "Export and rotate to a new store file, or raise the ceiling " +
          "deliberately; archiving does not shrink the file and deletion needs " +
          "an approved retention exception.",
      );
    const temporary =
      this.filePath + ".tmp-" + process.pid + "-" + crypto.randomUUID();
    try {
      const handle = fs.openSync(temporary, "wx", 0o600);
      try {
        fs.writeFileSync(handle, serialised, { encoding: "utf8" });
        fs.fsyncSync(handle);
      } finally {
        fs.closeSync(handle);
      }
      fs.renameSync(temporary, this.filePath);
    } catch (error) {
      fs.rmSync(temporary, { force: true });
      throw error;
    }
    const directoryHandle = fs.openSync(directory, "r");
    try {
      fs.fsyncSync(directoryHandle);
    } finally {
      fs.closeSync(directoryHandle);
    }
    this.state = next;
  }

  async accept(raw, idempotencyKey, principal, basis, transport) {
    const actor = validatePrincipal(principal, "accept");
    // E4: the agreement basis is checked before anything else is read. Only a
    // basis the record-basis module issued is accepted, so a record without a
    // complete agreement reference cannot be constructed at all.
    if (!isRecordBasis(basis)) throw Error("A record cannot be created without an agreement reference");
    const recordBasis = storedBasis(basis);
    // E6: how the package arrived is required too; there is no default.
    if (
      !transport ||
      !TRANSPORT_CHANNELS.includes(transport.channel) ||
      (transport.channel === "MAIL_INTAKE" && !TRANSPORT_ARRIVALS.includes(transport.arrival)) ||
      !["PRESENT_IN_MAILBOX", "NO_TRANSPORT_COPY"].includes(transport.copy_state) ||
      !Array.isArray(transport.history) ||
      transport.history.length
    )
      throw Error("A record states how its package arrived: use transportAtRelay");
    safeKey(idempotencyKey, "idempotency key");
    if (typeof raw !== "string" || Buffer.byteLength(raw) > 120_000)
      throw Error("Reviewed intake exceeds 120 KB");
    const rawDigest = sha256(raw);
    const priorId = this.state.idempotency[idempotencyKey];
    if (priorId) {
      const prior = this.state.inquiries[priorId];
      if (!prior || prior.raw_sha256 !== rawDigest)
        throw Error("Idempotency key conflict");
      // The same bytes relayed under a different agreement are not a retry.
      if (!prior.basis || prior.basis.legal_basis !== recordBasis.legal_basis)
        throw Error("Idempotency key conflict: the same package under a different agreement basis");
      return { ...clone(prior.receipt), disposition: "DEDUPLICATED" };
    }
    const inspected = await I.inspect(raw, F.strictJsonParse);
    if (!inspected.review_package)
      throw Error("Private receiver accepts only reviewed client brief packages");
    const inquiryId = "inquiry-" + inspected.canonical_digest.slice(7, 23);
    if (this.state.inquiries[inquiryId])
      throw Error("Canonical inquiry collision requires reconciliation");
    const receipt = {
      schema_version: RECEIPT_VERSION,
      receipt_id: "receipt-" + inspected.canonical_digest.slice(7, 23),
      inquiry_id: inquiryId,
      revision: 1,
      raw_sha256: rawDigest,
      canonical_digest: inspected.canonical_digest,
      status: "PERSISTED_PRIVATE_SYNTHETIC",
      authority: "RECEIPT_ONLY_NOT_SCIENTIFIC_COMMERCIAL_OR_EXECUTION_APPROVAL",
    };
    const record = {
      inquiry_id: inquiryId,
      version: 1,
      lifecycle: "ACTIVE",
      raw_sha256: rawDigest,
      canonical_digest: inspected.canonical_digest,
      raw_json: raw,
      validated_draft: inspected.draft,
      reviewed_package: inspected.review_package,
      receipt,
      created_by: actor,
      last_updated_by: actor,
      // The owning team is taken from the authenticated identity, never from
      // the submission or the caller's argument list.
      owner_team: principal.team,
      // E4: the agreement this record is held under. Plain metadata: opaque
      // references, never agreement text.
      basis: recordBasis,
      // E6: how the package arrived, and what became of its transport copy.
      transport: clone(transport),
      basis_history: [{ seq: 1, event: "RECEIVED", ...recordBasis, by: actor, at: new Date().toISOString() }],
      team_fields: {
        assigned_reviewer: "",
        queue_state: "READY_FOR_REVIEW",
        note: "",
      },
      // Append-only: every later team assessment is added here and no entry is
      // ever rewritten, so an engineer's revision history survives a correction.
      assessments: [],
      history_origin: "NATIVE",
      retention: {
        schema_version: RETENTION_VERSION,
        policy_id: RETENTION_POLICY.policy_id,
        disposition: RETENTION_POLICY.default_disposition,
        archived_at: null,
        archived_by: null,
        // Set only by an approved exception; never inferred.
        exception_id: null,
        // The lawful basis the record is held on, enforced rather than filled
        // in: it is the agreement reference, and a record cannot exist without it.
        legal_basis: recordBasis.legal_basis,
        production_period: RETENTION_POLICY.production_period,
      },
      // Append-only, like the assessment history. The retention block above is
      // current state and is overwritten — a restore clears the archive fields
      // — so on its own it loses who archived a record that was later restored
      // and archived again. "Who did what to this inquiry" is the question
      // asked afterwards, and current state cannot answer it.
      retention_events: [],
    };
    const next = clone(this.state);
    next.inquiries[inquiryId] = record;
    next.idempotency[idempotencyKey] = inquiryId;
    next.outbox["notify-" + inquiryId] = {
      event_id: "notify-" + inquiryId,
      inquiry_id: inquiryId,
      // A notification carries a summary of a private inquiry, so it is scoped
      // to the same team as the record it describes.
      owner_team: principal.team,
      status: "PENDING",
      attempts: 0,
      last_error: "",
      // What happened on the last call, as distinct from what the queue state
      // is. A pending event that was never attempted and one whose delivery
      // was refused are both PENDING and need different things done about them.
      last_outcome: "NOT_ATTEMPTED",
      destination: this.destination,
      notification: notification(inquiryId, record),
    };
    this.persist(next);
    return { ...clone(receipt), disposition: "ACCEPTED" };
  }

  read(inquiryId, principal) {
    validatePrincipal(principal, "read");
    const record = ownedRecord(this, inquiryId, principal);
    return clone(record);
  }

  update(inquiryId, expectedVersion, patch, principal) {
    const actor = validatePrincipal(principal, "update");
    const record = ownedRecord(this, inquiryId, principal);
    // An archived record was deliberately taken out of the working set. Letting
    // a revision land on it anyway would make the archive a label rather than a
    // state, and would append assessment history to a record nobody is
    // reviewing. Restore it first, which is recorded.
    if (record.lifecycle === "ARCHIVED")
      throw Error("Archived inquiry cannot be revised until it is restored");
    if (!Number.isSafeInteger(expectedVersion) || expectedVersion !== record.version)
      throw Error("Concurrent inquiry update conflict");
    const keys = Object.keys(patch || {}).sort();
    if (JSON.stringify(keys) !== JSON.stringify([...TEAM_FIELDS].sort()))
      throw Error("Unsupported team update fields");
    if (typeof patch.assigned_reviewer !== "string" || patch.assigned_reviewer.length > 300)
      throw Error("Invalid assigned reviewer");
    if (typeof patch.note !== "string" || patch.note.length > 8000)
      throw Error("Invalid team note");
    if (!QUEUE_STATES.includes(patch.queue_state))
      throw Error("Invalid private queue state");
    const next = clone(this.state);
    const updated = next.inquiries[inquiryId];
    // Retain the superseded assessment beside the new one. A correction adds a
    // revision; it never rewrites what an engineer previously recorded.
    updated.assessments.push({
      revision: updated.version,
      superseded_team_fields: clone(updated.team_fields),
      recorded_by: updated.last_updated_by,
      superseded_by: actor,
    });
    updated.version += 1;
    updated.last_updated_by = actor;
    updated.team_fields = clone(patch);
    this.persist(next);
    return clone(updated);
  }

  export(inquiryId, principal, { includeArchived = false, recipient, purpose } = {}) {
    // Checked as its own action. Never widen the caller's roles to satisfy the
    // read check: a later export role must not become a read grant by accident.
    const actor = validatePrincipal(principal, "export");
    const record = ownedRecord(this, inquiryId, principal);
    // An archived record has been taken out of the working set deliberately.
    // Exporting one is a separate decision, so it has to be asked for.
    if (record.lifecycle === "ARCHIVED" && !includeArchived)
      throw Error("Archived inquiry export requires an explicit archive request");
    // E5: the release is logged, durably, before the content is handed over.
    // An export that returned first and logged afterwards could leave a copy
    // nobody knows to ask about.
    const terms = releaseTerms({ recipient, purpose });
    const exported = clone(record);
    logRelease(this, record, actor, {
      ...terms,
      channel: "RECEIVER_EXPORT",
      artifact_sha256: sha256(JSON.stringify(exported)),
    });
    return exported;
  }

  /** Record a release made outside the receiver: a copy sent onward by hand. */
  recordRelease(inquiryId, { recipient, purpose, artifact_sha256: artifact } = {}, principal) {
    const actor = validatePrincipal(principal, "record_release");
    const record = ownedRecord(this, inquiryId, principal);
    const terms = releaseTerms({ recipient, purpose });
    if (typeof artifact !== "string" || !/^sha256:[0-9a-f]{64}$/.test(artifact))
      throw Error("A recorded release names the artifact it released by its sha256 digest");
    return logRelease(this, record, actor, { ...terms, channel: "RECORDED_EXTERNAL", artifact_sha256: artifact });
  }

  /** Every release of an inquiry, including one that has since been deleted. */
  releases(principal, { inquiryId } = {}) {
    validatePrincipal(principal, "releases");
    return Object.values(this.state.releases)
      .filter((entry) => entry.owner_team === principal.team)
      .filter((entry) => inquiryId === undefined || entry.inquiry_id === inquiryId)
      .sort((a, b) => a.seq - b.seq)
      .map(clone);
  }

  /** Search the active index. Archived records are out of it by design. */
  search(principal, { includeArchived = false } = {}) {
    validatePrincipal(principal, "search");
    return Object.values(this.state.inquiries)
      .filter((record) => record.owner_team === principal.team)
      .filter((record) => includeArchived || record.lifecycle === "ACTIVE")
      .map((record) => ({
        inquiry_id: record.inquiry_id,
        lifecycle: record.lifecycle,
        queue_state: record.team_fields.queue_state,
        disposition: record.retention.disposition,
      }))
      .sort((a, b) => (a.inquiry_id < b.inquiry_id ? -1 : 1));
  }

  /** Retain the record and take it out of the active index. Nothing is erased. */
  /**
   * Attach or change a record's agreement basis. A data steward attaches the
   * real basis to a record written before E4, or moves a SCOPING record to
   * STUDY once its MSA and Order Form exist. Nothing else: a STUDY record does
   * not go back, and a basis is never removed. The history is append-only.
   */
  attachBasis(inquiryId, basis, principal) {
    const actor = validatePrincipal(principal, "attach_basis");
    if (!isRecordBasis(basis)) throw Error("A record cannot be held without an agreement reference");
    const incoming = storedBasis(basis);
    safeKey(inquiryId, "inquiry ID");
    const current = this.state.inquiries[inquiryId];
    if (!current || current.owner_team !== principal.team) throw Error("Inquiry not found");
    if (current.lifecycle === KEY_DESTROYED)
      throw Object.assign(Error("Inquiry content is unreadable: its archive key was destroyed"), { status: 410 });
    let event;
    if (!current.basis) event = "ATTACHED_PRE_E4";
    else if (current.basis.record_class === "SCOPING" && incoming.record_class === "STUDY") event = "PROMOTED_TO_STUDY";
    else throw Error("Agreement basis conflict: only a missing basis may be attached, or SCOPING promoted to STUDY");
    const next = clone(this.state);
    const record = next.inquiries[inquiryId];
    record.basis = incoming;
    record.retention.legal_basis = incoming.legal_basis;
    record.basis_history = [
      ...(record.basis_history || []),
      { seq: (record.basis_history || []).length + 1, event, ...incoming, by: actor, at: new Date().toISOString() },
    ];
    this.persist(next);
    return clone(record.basis);
  }

  /**
   * Record what the receiver did with the transport copy in the mailbox. The
   * states move forward only, and each entry is the receiver's attestation:
   * this store cannot see the mailbox, and says so rather than implying it can.
   */
  recordTransportCopy(inquiryId, state, principal) {
    const actor = validatePrincipal(principal, "record_transport");
    const current = ownedRecord(this, inquiryId, principal);
    const transport = current.transport || {};
    const allowed = TRANSPORT_STEPS[transport.copy_state] || [];
    if (!allowed.includes(state))
      throw Error(`The transport copy cannot move from ${transport.copy_state || "unrecorded"} to ${state}`);
    const next = clone(this.state);
    const record = next.inquiries[inquiryId];
    const now = new Date();
    const entry = {
      seq: record.transport.history.length + 1,
      state,
      at: now.toISOString(),
      by: actor,
      basis: "RECEIVER_ATTESTATION",
      purge_expected_by:
        state === "MOVED_TO_TRASH" ? new Date(now.getTime() + TRASH_PURGE_DAYS * 86_400_000).toISOString() : null,
    };
    record.transport.copy_state = state;
    record.transport.history.push(entry);
    this.persist(next);
    return clone(record.transport);
  }

  archive(inquiryId, principal) {
    const actor = validatePrincipal(principal, "archive");
    const record = ownedRecord(this, inquiryId, principal);
    if (record.lifecycle === "ARCHIVED") return clone(record);
    const next = clone(this.state);
    const archived = next.inquiries[inquiryId];
    archived.lifecycle = "ARCHIVED";
    archived.retention = {
      ...archived.retention,
      disposition: "ARCHIVE_INDEFINITE",
      archived_at: new Date().toISOString(),
      archived_by: actor,
    };
    appendRetentionEvent(archived, "ARCHIVED", actor);
    this.persist(next);
    return clone(archived);
  }

  restore(inquiryId, principal) {
    const actor = validatePrincipal(principal, "restore");
    const record = ownedRecord(this, inquiryId, principal);
    const next = clone(this.state);
    const restored = next.inquiries[inquiryId];
    restored.lifecycle = "ACTIVE";
    // The archive action is cleared, but who restored it is retained: the
    // record of what happened to an inquiry is append-only in spirit even when
    // the lifecycle moves back.
    restored.retention = {
      ...restored.retention,
      archived_at: null,
      archived_by: null,
      restored_by: actor,
      restored_at: new Date().toISOString(),
    };
    appendRetentionEvent(restored, "RESTORED", actor);
    this.persist(next);
    return clone(restored);
  }

  /** Record an approved exception to archival retention.
   *
   * Deletion is gated on one of these existing. The approver is recorded
   * because "who approved this" is the question asked after the fact, and the
   * scope is recorded because an exception that does not say what it covers
   * cannot be audited against what was actually removed.
   */
  approveDeletionException(inquiryId, { approver, reason }, principal) {
    const actor = validatePrincipal(principal, "approve_exception");
    ownedRecord(this, inquiryId, principal);
    if (typeof approver !== "string" || !approver.trim())
      throw Error("An approved deletion exception requires a named approver");
    if (typeof reason !== "string" || reason.trim().length < 8)
      throw Error("An approved deletion exception requires a stated reason");
    const exceptionId = "exception-" + inquiryId;
    const next = clone(this.state);
    next.exceptions[exceptionId] = {
      exception_id: exceptionId,
      inquiry_id: inquiryId,
      approver: approver.trim(),
      reason: reason.trim(),
      recorded_by: actor,
      recorded_at: new Date().toISOString(),
      reaches: [...RETENTION_POLICY.deletion_reaches],
      cannot_reach: [...RETENTION_POLICY.deletion_cannot_reach],
      status: "APPROVED_LOCAL_SYNTHETIC",
    };
    next.inquiries[inquiryId].retention = {
      ...next.inquiries[inquiryId].retention,
      exception_id: exceptionId,
    };
    appendRetentionEvent(next.inquiries[inquiryId], "DELETION_EXCEPTION_APPROVED", actor, {
      exception_id: exceptionId,
      approver: next.exceptions[exceptionId].approver,
    });
    this.persist(next);
    return clone(next.exceptions[exceptionId]);
  }

  delete(inquiryId, principal) {
    const actor = validatePrincipal(principal, "delete");
    const existing = ownedRecord(this, inquiryId, principal);
    // Archival retention is the default disposition, so removal is the
    // exception and needs an approved one on record.
    const exception = this.state.exceptions[existing.retention.exception_id];
    if (!exception)
      throw Error(
        "Deletion requires an approved retention exception for this inquiry",
      );
    // The key goes first. Once it is destroyed every copy of this record, the
    // store file and any backup or archive copy of it, is unreadable, even
    // though those bytes remain. If the write below then failed, the record
    // would still be present and still unreadable, which is the safe side.
    const keyDestroyed = existing.archive_key_id
      ? this.keyring.destroy(existing.archive_key_id, { reason: exception.exception_id })
      : null;
    if (keyDestroyed)
      this.state.inquiries[inquiryId] = {
        inquiry_id: inquiryId,
        owner_team: existing.owner_team,
        archive_key_id: existing.archive_key_id,
        lifecycle: KEY_DESTROYED,
        history_origin: KEY_DESTROYED,
        assessments: [],
        version: existing.version,
        unreadable_sealed: null,
      };
    const next = clone(this.state);
    delete next.inquiries[inquiryId];
    for (const [key, value] of Object.entries(next.idempotency))
      if (value === inquiryId) delete next.idempotency[key];
    for (const [key, value] of Object.entries(next.outbox))
      if (value.inquiry_id === inquiryId) delete next.outbox[key];
    next.tombstones[inquiryId] = {
      inquiry_id: inquiryId,
      deleted_by: actor,
      prior_raw_sha256: existing.raw_sha256,
      status: "DELETED_LOCAL_SYNTHETIC",
      exception_id: exception.exception_id,
      approved_by: exception.approver,
      // State the reach rather than implying removal everywhere. Promising a
      // deletion that retained archives and prior exports do not honour would
      // be a promise this store cannot keep.
      reached: [...exception.reaches],
      did_not_reach: [...exception.cannot_reach],
      // The retained archive's bytes are not reached. Its key is, which is what
      // makes those bytes unreadable; the two statements are both true.
      // Deletion cannot reach prior releases. It can name them, so each one
      // can be followed up with a request to destroy that copy.
      prior_releases: Object.values(next.releases)
        .filter((entry) => entry.inquiry_id === inquiryId)
        .map((entry) => entry.release_id),
      archive_key: keyDestroyed ? "DESTROYED" : "NONE_HELD",
      archive_key_destroyed_at: keyDestroyed ? keyDestroyed.destroyed_at : null,
    };
    this.persist(next);
    return clone(next.tombstones[inquiryId]);
  }

  listOutbox(principal) {
    validatePrincipal(principal, "outbox");
    return Object.values(clone(this.state.outbox))
      .filter((event) => event.owner_team === principal.team)
      .sort((a, b) =>
      a.event_id < b.event_id ? -1 : a.event_id > b.event_id ? 1 : 0,
    );
  }

  async processOutbox(eventId, handler, principal) {
    validatePrincipal(principal, "outbox");
    safeKey(eventId, "outbox event ID");
    const event = this.state.outbox[eventId];
    if (!event || event.owner_team !== principal.team)
      throw Error("Outbox event not found");
    if (event.status === "DELIVERED") return clone(event);
    // Nothing configured is not a delivery that failed.
    //
    // This used to run a default handler that threw, so an unconfigured
    // receiver recorded an attempt and a failure for a delivery nobody tried.
    // An operator polling it saw a rising attempt count and an error string,
    // and could not tell "tried seven times and the remote refused" from
    // "asked seven times with nothing to ask". The two need different actions,
    // so they are now different outcomes: `attempts` counts attempts that
    // actually happened, and the one that did not is typed rather than
    // inferred from an error message.
    const configured = typeof handler === "function";
    let status, failure, outcome;
    let attemptedHere = configured;
    if (!configured) {
      status = "PENDING";
      failure = "";
      outcome = "NOT_ATTEMPTED_NO_TRANSPORT";
    } else {
      const attempted = clone(event);
      attempted.attempts += 1;
      try {
        await handler(clone(attempted));
        status = "DELIVERED";
        failure = "";
        outcome = "DELIVERED";
      } catch (error) {
        status = "PENDING";
        // Only a typed outcome's own fixed message is kept. An error nobody
        // anticipated is recorded as such and its text is not: the catch-all
        // is where a credential or a server's echo would otherwise be written
        // into the record, because it is the branch nobody designed.
        if (error && typeof error.outcome === "string" && /^[A-Z_]+$/.test(error.outcome)) {
          outcome = error.outcome;
          failure = String(error.message).slice(0, 300);
          // A transport that refused before trying (no credential, an unsafe
          // one) did not attempt a delivery, and the count says so.
          if (error.attempted === false) attemptedHere = false;
        } else {
          outcome = "ATTEMPT_FAILED";
          failure = "The transport failed in an unexpected way; its error is not recorded";
        }
      }
    }
    // Merge into the state as it is now. A snapshot taken before the await
    // would erase any assessment, deletion or attempt written while the
    // delivery was in flight.
    const next = clone(this.state);
    const current = next.outbox[eventId];
    if (!current)
      throw Error("Outbox event was removed while its delivery was in flight");
    if (attemptedHere) current.attempts += 1;
    current.status = status;
    current.last_error = failure;
    current.last_outcome = outcome;
    this.persist(next);
    return clone(current);
  }
}

module.exports = {
  transportAtRelay,
  TRASH_PURGE_DAYS,
  SEALED_STORE_VERSION,
  DEFAULT_WRITE_CEILING_BYTES,
  READ_LIMIT_BYTES,
  STORE_VERSION,
  RETENTION_VERSION,
  RETENTION_POLICY,
  LEGACY_STORE_VERSION,
  RECEIPT_VERSION,
  NOTIFICATION_VERSION,
  QUEUE_STATES,
  notification,
  DurableIntakeStore,
  emptyStore,
  validatePrincipal,
};
