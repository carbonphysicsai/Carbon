"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const F = require("../src/engine.js");
const I = require("../src/intake.js");

const STORE_VERSION = "carbon.private-team-intake.store.v2";
const LEGACY_STORE_VERSION = "carbon.private-team-intake.store.v1";
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
  if (
    !principal ||
    typeof principal.id !== "string" ||
    !Array.isArray(principal.roles)
  )
    throw Error("Named principal required");
  const permitted = {
    accept: ["INTAKE_RECEIVER"],
    read: ["TEAM_REVIEWER", "INTAKE_RECEIVER"],
    update: ["TEAM_REVIEWER"],
    export: ["TEAM_REVIEWER"],
    delete: ["DATA_STEWARD"],
    outbox: ["NOTIFICATION_OPERATOR"],
  }[action];
  if (!permitted || !principal.roles.some((role) => permitted.includes(role)))
    throw Error("Principal is not authorized for " + action);
  return principal.id;
}

function validateStore(value) {
  if (
    !value ||
    ![STORE_VERSION, LEGACY_STORE_VERSION].includes(value.schema_version) ||
    !value.inquiries ||
    !value.idempotency ||
    !value.outbox ||
    !value.tombstones
  )
    throw Error("Invalid private intake store");
  if (value.schema_version === LEGACY_STORE_VERSION) return migrate(value);
  for (const record of Object.values(value.inquiries)) {
    if (!Array.isArray(record.assessments))
      throw Error("Invalid retained assessment history");
    // The history is append-only: one entry per recorded team revision. A store
    // whose history does not account for its own version has been edited.
    const accounted = record.assessments.length + 1;
    if (record.history_origin === "NATIVE" && accounted !== record.version)
      throw Error("Retained assessment history does not match the record version");
  }
  return value;
}

function migrate(value) {
  // A v1 store retained no per-revision history. Record that honestly rather
  // than inventing a reviewer, a time or an assessment that was never written.
  const next = clone(value);
  next.schema_version = STORE_VERSION;
  for (const record of Object.values(next.inquiries)) {
    record.assessments = [];
    record.history_origin = "MIGRATED_V1_NO_RETAINED_HISTORY";
  }
  return next;
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
        policy: "LOCAL_SYNTHETIC_DELETE_ON_REQUEST",
        production_period: null,
      },
    };
    const next = clone(this.state);
    next.inquiries[inquiryId] = record;
    next.idempotency[idempotencyKey] = inquiryId;
    next.outbox["notify-" + inquiryId] = {
      event_id: "notify-" + inquiryId,
      inquiry_id: inquiryId,
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
    safeKey(inquiryId, "inquiry ID");
    const record = this.state.inquiries[inquiryId];
    if (!record) throw Error("Inquiry not found");
    return clone(record);
  }

  update(inquiryId, expectedVersion, patch, principal) {
    const actor = validatePrincipal(principal, "update");
    safeKey(inquiryId, "inquiry ID");
    const record = this.state.inquiries[inquiryId];
    if (!record) throw Error("Inquiry not found");
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

  export(inquiryId, principal) {
    // Checked as its own action. Never widen the caller's roles to satisfy the
    // read check: a later export role must not become a read grant by accident.
    validatePrincipal(principal, "export");
    safeKey(inquiryId, "inquiry ID");
    const record = this.state.inquiries[inquiryId];
    if (!record) throw Error("Inquiry not found");
    return clone(record);
  }

  delete(inquiryId, principal) {
    const actor = validatePrincipal(principal, "delete");
    safeKey(inquiryId, "inquiry ID");
    const existing = this.state.inquiries[inquiryId];
    if (!existing) throw Error("Inquiry not found");
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
    };
    this.persist(next);
    return clone(next.tombstones[inquiryId]);
  }

  listOutbox(principal) {
    validatePrincipal(principal, "outbox");
    return Object.values(clone(this.state.outbox)).sort((a, b) =>
      a.event_id < b.event_id ? -1 : a.event_id > b.event_id ? 1 : 0,
    );
  }

  async processOutbox(eventId, handler, principal) {
    validatePrincipal(principal, "outbox");
    safeKey(eventId, "outbox event ID");
    const event = this.state.outbox[eventId];
    if (!event) throw Error("Outbox event not found");
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
  LEGACY_STORE_VERSION,
  RECEIPT_VERSION,
  NOTIFICATION_VERSION,
  QUEUE_STATES,
  notification,
  DurableIntakeStore,
  emptyStore,
  validatePrincipal,
};
