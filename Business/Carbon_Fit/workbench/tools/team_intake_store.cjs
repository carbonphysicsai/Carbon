"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const F = require("../src/engine.js");
const I = require("../src/intake.js");

const STORE_VERSION = "carbon.private-team-intake.store.v1";
const RECEIPT_VERSION = "carbon.private-team-intake.receipt.v1";
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
    value.schema_version !== STORE_VERSION ||
    !value.inquiries ||
    !value.idempotency ||
    !value.outbox ||
    !value.tombstones
  )
    throw Error("Invalid private intake store");
  return value;
}

class DurableIntakeStore {
  constructor(filePath) {
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
    const directory = path.dirname(this.filePath);
    fs.mkdirSync(directory, { recursive: true, mode: 0o700 });
    const temporary = this.filePath + ".tmp-" + process.pid;
    fs.writeFileSync(temporary, JSON.stringify(next, null, 2) + "\n", {
      encoding: "utf8",
      mode: 0o600,
      flag: "w",
    });
    fs.renameSync(temporary, this.filePath);
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
      destination: "UNCONFIGURED_SYNTHETIC",
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
    if (JSON.stringify(keys) !== JSON.stringify(["assigned_reviewer", "note", "queue_state"].sort()))
      throw Error("Unsupported team update fields");
    if (typeof patch.assigned_reviewer !== "string" || patch.assigned_reviewer.length > 300)
      throw Error("Invalid assigned reviewer");
    if (typeof patch.note !== "string" || patch.note.length > 8000)
      throw Error("Invalid team note");
    if (!["READY_FOR_REVIEW", "UNDER_REVIEW", "NEEDS_CLIENT_CLARIFICATION", "READY_FOR_ROUTE", "PARKED", "CLOSED"].includes(patch.queue_state))
      throw Error("Invalid private queue state");
    const next = clone(this.state);
    next.inquiries[inquiryId].version += 1;
    next.inquiries[inquiryId].last_updated_by = actor;
    next.inquiries[inquiryId].team_fields = clone(patch);
    this.persist(next);
    return clone(next.inquiries[inquiryId]);
  }

  export(inquiryId, principal) {
    validatePrincipal(principal, "export");
    return this.read(inquiryId, { ...principal, roles: [...new Set([...principal.roles, "TEAM_REVIEWER"])] });
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

  async processOutbox(eventId, handler, principal) {
    validatePrincipal(principal, "outbox");
    safeKey(eventId, "outbox event ID");
    const event = this.state.outbox[eventId];
    if (!event) throw Error("Outbox event not found");
    if (event.status === "DELIVERED") return clone(event);
    const next = clone(this.state);
    next.outbox[eventId].attempts += 1;
    try {
      await handler(clone(next.outbox[eventId]));
      next.outbox[eventId].status = "DELIVERED";
      next.outbox[eventId].last_error = "";
    } catch (error) {
      next.outbox[eventId].status = "PENDING";
      next.outbox[eventId].last_error = String(error.message || error).slice(0, 500);
    }
    this.persist(next);
    return clone(next.outbox[eventId]);
  }
}

module.exports = {
  STORE_VERSION,
  RECEIPT_VERSION,
  DurableIntakeStore,
  emptyStore,
  validatePrincipal,
};
