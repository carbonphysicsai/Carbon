"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const F = require("../src/engine.js");
const I = require("../src/intake.js");
const { isAuthenticatedPrincipal } = require("./team_staff_directory.cjs");

const STORE_VERSION = "carbon.private-team-intake.store.v3";
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
  };
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
  return record;
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
  if ([LEGACY_STORE_VERSION, STORE_VERSION_V2].includes(value.schema_version))
    return migrate(value);
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

class DurableIntakeStore {
  constructor(filePath, options = {}) {
    // A destination is configuration, not consent to send. With none set the
    // outbox stays observable and every attempt fails closed and says why.
    const destination = options.destination;
    if (destination !== undefined && (typeof destination !== "string" || !destination))
      throw Error("Notification destination must be a non-empty string");
    this.destination = destination || "UNCONFIGURED_SYNTHETIC";
    this.filePath = path.resolve(filePath);
    this.state = fs.existsSync(this.filePath)
      ? validateStore(
          F.strictJsonParse(fs.readFileSync(this.filePath, "utf8"), {
            maxBytes: 10_000_000,
            maxDepth: 18,
          }),
        )
      : emptyStore();
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
    const temporary =
      this.filePath + ".tmp-" + process.pid + "-" + crypto.randomUUID();
    try {
      const handle = fs.openSync(temporary, "wx", 0o600);
      try {
        fs.writeFileSync(handle, JSON.stringify(next, null, 2) + "\n", {
          encoding: "utf8",
        });
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

  async accept(raw, idempotencyKey, principal) {
    const actor = validatePrincipal(principal, "accept");
    safeKey(idempotencyKey, "idempotency key");
    if (typeof raw !== "string" || Buffer.byteLength(raw) > 120_000)
      throw Error("Reviewed intake exceeds 120 KB");
    const rawDigest = sha256(raw);
    const priorId = this.state.idempotency[idempotencyKey];
    if (priorId) {
      const prior = this.state.inquiries[priorId];
      if (!prior || prior.raw_sha256 !== rawDigest)
        throw Error("Idempotency key conflict");
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

  export(inquiryId, principal, { includeArchived = false } = {}) {
    // Checked as its own action. Never widen the caller's roles to satisfy the
    // read check: a later export role must not become a read grant by accident.
    validatePrincipal(principal, "export");
    const record = ownedRecord(this, inquiryId, principal);
    // An archived record has been taken out of the working set deliberately.
    // Exporting one is a separate decision, so it has to be asked for.
    if (record.lifecycle === "ARCHIVED" && !includeArchived)
      throw Error("Archived inquiry export requires an explicit archive request");
    return clone(record);
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
    if (typeof handler !== "function")
      handler = async () => {
        throw Error(
          "No notification transport is configured; delivery is not attempted",
        );
      };
    const attempted = clone(event);
    attempted.attempts += 1;
    let status, failure;
    try {
      await handler(clone(attempted));
      status = "DELIVERED";
      failure = "";
    } catch (error) {
      status = "PENDING";
      failure = String(error.message || error).slice(0, 500);
    }
    // Merge into the state as it is now. A snapshot taken before the await
    // would erase any assessment, deletion or attempt written while the
    // delivery was in flight.
    const next = clone(this.state);
    const current = next.outbox[eventId];
    if (!current)
      throw Error("Outbox event was removed while its delivery was in flight");
    current.attempts += 1;
    current.status = status;
    current.last_error = failure;
    this.persist(next);
    return clone(current);
  }
}

module.exports = {
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
