"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
if (!globalThis.crypto) globalThis.crypto = crypto.webcrypto;
const I = require("../src/intake.js");
const F = require("../src/engine.js");
const {
  DurableIntakeStore,
  STORE_VERSION,
  SEALED_STORE_VERSION,
} = require("../tools/team_intake_store.cjs");
const ROOT = path.resolve(__dirname, "..");

const { StaffDirectory, StaffPrincipal } = require("../tools/team_staff_directory.cjs");
const { RELEASE, enrolled, keyringFor, openStore, principalFor, scoping } = require("./staff_fixture.cjs");

// Principals are authenticated rather than declared. The literals these
// replaced asserted their own roles, which meant the store was trusting its
// caller to tell the truth about who was calling.
const TEAM = "carbon-fit", OTHER_TEAM = "other-tenant";
const TOKENS = {
  receiver: "synthetic-receiver-token-0001",
  reviewer: "synthetic-reviewer-token-0001",
  steward: "synthetic-steward-token-0001",
  notifier: "synthetic-notifier-token-0001",
  second_reviewer: "synthetic-second-reviewer-token-0001",
  foreign: "synthetic-foreign-token-0001",
};
const digest = (value) => crypto.createHash("sha256").update(value).digest("hex");
const DIRECTORY = new StaffDirectory([
  enrolled("synthetic-receiver", TEAM, ["INTAKE_RECEIVER"], TOKENS.receiver),
  enrolled("synthetic-reviewer", TEAM, ["TEAM_REVIEWER"], TOKENS.reviewer),
  enrolled("synthetic-second-reviewer", TEAM, ["TEAM_REVIEWER"], TOKENS.second_reviewer),
  enrolled("synthetic-steward", TEAM, ["DATA_STEWARD"], TOKENS.steward),
  enrolled("synthetic-notifier", TEAM, ["NOTIFICATION_OPERATOR"], TOKENS.notifier),
  enrolled(
    "synthetic-foreign",
    OTHER_TEAM,
    ["INTAKE_RECEIVER", "TEAM_REVIEWER", "DATA_STEWARD", "NOTIFICATION_OPERATOR"],
    TOKENS.foreign,
  ),
]);
const as = (name) => principalFor(DIRECTORY, TOKENS[name]);
const roles = {
  receiver: as("receiver"),
  reviewer: as("reviewer"),
  steward: as("steward"),
  notifier: as("notifier"),
  second_reviewer: as("second_reviewer"),
  foreign: as("foreign"),
};

function reviewedRaw(distinct = false) {
  const brief = JSON.parse(
    fs.readFileSync(path.join(ROOT, "intake/fixtures/existing_method_v1.json"), "utf8"),
  );
  if (distinct) brief.draft_id = "synthetic-second-draft";
  return JSON.stringify({
    schema_version: I.REVIEW_VERSION,
    brief,
    pilot: {
      label: "Draft pilot for Carbon review",
      ...Object.fromEntries(I.PILOT_FIELDS.map((field) => [field, ""])),
      bounded_first_pilot: "Compare the reported baseline over an agreed synthetic range.",
    },
    field_provenance: [
      ...I.TEXT_FIELDS,
      ...I.QUANTITY_FIELDS,
      ...I.PILOT_FIELDS.map((field) => "pilot." + field),
    ].map((field) => ({
      field,
      origin: field === "pilot.bounded_first_pilot" ? "CLIENT_TYPED" : "UNKNOWN",
      suggestion_id: null,
    })),
    accepted_suggestions: [],
    unresolved_assumptions: ["Reference adequacy is unknown."],
    ai_guidance: {
      enabled: false,
      provider: null,
      guidance_version: I.GUIDANCE_VERSION,
      notice_version: null,
      consented_at: null,
      cleared_locally: false,
    },
    sharing: { include_conversation: false, conversation: [] },
    contact: { name: "", email: "", organization: "" },
    local_scope: I.REVIEW_SCOPE,
  });
}

// Deletion is now the exception to archival retention, so a test that deletes
// has to approve one first. Kept explicit rather than hidden in a helper that
// silently grants it.
function approveDeletion(store, inquiryId) {
  return store.approveDeletionException(
    inquiryId,
    { approver: "Ryan Bequette", reason: "Synthetic fixture cleanup only." },
    roles.steward,
  );
}

function temporaryStore() {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "carbon-team-intake-"));
  return {
    directory,
    file: path.join(directory, "store.json"),
    store: openStore(path.join(directory, "store.json")),
  };
}

test("accepted inquiry is durable before receipt and exact response-loss retry deduplicates", async () => {
  const fixture = temporaryStore(), raw = reviewedRaw();
  const first = await fixture.store.accept(raw, "retry-key-001", roles.receiver, scoping());
  assert.equal(first.disposition, "ACCEPTED");
  assert.equal(fs.existsSync(fixture.file), true);
  const restarted = openStore(fixture.file);
  const second = await restarted.accept(raw, "retry-key-001", roles.receiver, scoping());
  assert.equal(second.disposition, "DEDUPLICATED");
  assert.equal(Object.keys(restarted.state.inquiries).length, 1);
  assert.equal(Object.keys(restarted.state.outbox).length, 1);
});

test("idempotency conflict and unauthorized access reject without mutation", async () => {
  const fixture = temporaryStore(), raw = reviewedRaw();
  await fixture.store.accept(raw, "retry-key-002", roles.receiver, scoping());
  const before = JSON.stringify(fixture.store.state);
  await assert.rejects(
    () => fixture.store.accept(raw + " ", "retry-key-002", roles.receiver, scoping()),
    /conflict/,
  );
  assert.throws(
    () => fixture.store.read(Object.keys(fixture.store.state.inquiries)[0], { id: "intruder", roles: [] }),
  );
  assert.throws(
    // A structurally perfect literal naming a real account and its real roles.
    // Nothing about this value is malformed; it is refused because nothing
    // authenticated it, which no shape check could have established.
    () => fixture.store.read(Object.keys(fixture.store.state.inquiries)[0],
      { id: "synthetic-reviewer", team: "carbon-fit", roles: ["TEAM_REVIEWER"], has: () => true }),
    /authenticated staff principal/,
    /not authorized/,
  );
  assert.equal(JSON.stringify(fixture.store.state), before);
});

test("optimistic updates preserve revisions and reject concurrent overwrite", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "retry-key-003", roles.receiver, scoping());
  const updated = fixture.store.update(
    receipt.inquiry_id,
    1,
    { assigned_reviewer: "Ryan", queue_state: "UNDER_REVIEW", note: "Synthetic review only." },
    roles.reviewer,
  );
  assert.equal(updated.version, 2);
  assert.throws(
    () => fixture.store.update(
      receipt.inquiry_id,
      1,
      { assigned_reviewer: "Nick", queue_state: "READY_FOR_ROUTE", note: "stale" },
      roles.reviewer,
    ),
    /Concurrent/,
  );
  assert.equal(fixture.store.read(receipt.inquiry_id, roles.reviewer).team_fields.assigned_reviewer, "Ryan");
});

test("notification failure preserves inquiry and pending outbox for recovery", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "retry-key-004", roles.receiver, scoping());
  const eventId = "notify-" + receipt.inquiry_id;
  const failed = await fixture.store.processOutbox(
    eventId,
    async () => { throw Error("synthetic destination unavailable"); },
    roles.notifier,
  );
  assert.equal(failed.status, "PENDING");
  assert.equal(fixture.store.read(receipt.inquiry_id, roles.reviewer).lifecycle, "ACTIVE");
  const delivered = await fixture.store.processOutbox(eventId, async () => {}, roles.notifier);
  assert.equal(delivered.status, "DELIVERED");
});

test("authorized deletion removes data and retains only a synthetic tombstone", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "retry-key-005", roles.receiver, scoping());
  assert.throws(() => fixture.store.delete(receipt.inquiry_id, roles.reviewer), /not authorized/);
  // Archival retention is the default, so removal needs an approved exception.
  assert.throws(
    () => fixture.store.delete(receipt.inquiry_id, roles.steward),
    /requires an approved retention exception/,
  );
  approveDeletion(fixture.store, receipt.inquiry_id);
  const tombstone = fixture.store.delete(receipt.inquiry_id, roles.steward);
  assert.equal(tombstone.status, "DELETED_LOCAL_SYNTHETIC");
  assert.throws(() => fixture.store.read(receipt.inquiry_id, roles.reviewer), /not found/);
  assert.equal(JSON.stringify(fixture.store.state).includes("Compare the reported baseline"), false);
});

test("private export requires the export role and preserves reviewed source bytes", async () => {
  const fixture = temporaryStore();
  const raw = reviewedRaw();
  const receipt = await fixture.store.accept(raw, "retry-key-006", roles.receiver, scoping());
  assert.throws(
    () => fixture.store.export(receipt.inquiry_id, roles.receiver),
    /not authorized/,
  );
  const exported = fixture.store.export(receipt.inquiry_id, roles.reviewer, RELEASE);
  assert.equal(exported.raw_json, raw);
  assert.equal(exported.raw_sha256, receipt.raw_sha256);
  assert.equal(exported.team_fields.queue_state, "READY_FOR_REVIEW");
});

test("team assessments are append-only and retain every superseded revision", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "retry-key-007", roles.receiver, scoping());
  const first = fixture.store.update(
    receipt.inquiry_id,
    1,
    { assigned_reviewer: "Ryan", queue_state: "UNDER_REVIEW", note: "First reading." },
    roles.reviewer,
  );
  // The record's own opening state is a revision too, so it is retained first.
  assert.equal(first.assessments.length, 1);
  assert.equal(first.assessments[0].superseded_team_fields.queue_state, "READY_FOR_REVIEW");
  assert.equal(first.assessments[0].recorded_by, "synthetic-receiver");
  const second = fixture.store.update(
    receipt.inquiry_id,
    2,
    { assigned_reviewer: "Nick", queue_state: "READY_FOR_ROUTE", note: "Corrected." },
    roles.second_reviewer,
  );
  assert.equal(second.version, 3);
  assert.equal(second.assessments.length, 2);
  // The correction adds a revision; the earlier words are still readable.
  assert.equal(second.assessments[1].superseded_team_fields.note, "First reading.");
  assert.equal(second.assessments[1].superseded_team_fields.assigned_reviewer, "Ryan");
  assert.equal(second.assessments[1].recorded_by, "synthetic-reviewer");
  assert.equal(second.assessments[1].superseded_by, "synthetic-second-reviewer");
  assert.equal(second.team_fields.note, "Corrected.");
  const restarted = openStore(fixture.file);
  assert.equal(restarted.read(receipt.inquiry_id, roles.reviewer).assessments.length, 2);
});

test("a v1 store migrates without inventing a history it never retained", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "retry-key-008", roles.receiver, scoping());
  const legacy = JSON.parse(fs.readFileSync(fixture.file, "utf8"));
  legacy.schema_version = "carbon.private-team-intake.store.v1";
  for (const record of Object.values(legacy.inquiries)) {
    record.version = 4;
    delete record.assessments;
    delete record.history_origin;
  }
  fs.writeFileSync(fixture.file, JSON.stringify(legacy, null, 2) + "\n");
  const migrated = openStore(fixture.file);
  const record = migrated.read(receipt.inquiry_id, roles.reviewer);
  assert.deepEqual(record.assessments, []);
  assert.equal(record.history_origin, "MIGRATED_V1_NO_RETAINED_HISTORY");
  assert.equal(record.version, 4);
});

test("a native store whose retained history was edited is refused", async () => {
  const fixture = temporaryStore();
  await fixture.store.accept(reviewedRaw(), "retry-key-009", roles.receiver, scoping());
  const tampered = JSON.parse(fs.readFileSync(fixture.file, "utf8"));
  for (const record of Object.values(tampered.inquiries)) record.version = 9;
  fs.writeFileSync(fixture.file, JSON.stringify(tampered, null, 2) + "\n");
  assert.throws(() => openStore(fixture.file), /does not match the record version/);
});

test("the queued notification carries a minimal summary and no client content", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "retry-key-010", roles.receiver, scoping());
  const events = fixture.store.listOutbox(roles.notifier);
  assert.equal(events.length, 1);
  const event = events[0];
  assert.equal(event.destination, "UNCONFIGURED_SYNTHETIC");
  assert.equal(event.notification.record_path, "/private/intake/" + receipt.inquiry_id);
  assert.equal(event.notification.canonical_digest, receipt.canonical_digest);
  assert.equal(typeof event.notification.summary.unresolved_assumption_count, "number");
  // No reviewed package, client words, contact details or raw bytes travel.
  const body = JSON.stringify(event);
  assert.equal(body.includes("Compare the reported baseline"), false);
  assert.equal(body.includes("Reference adequacy is unknown."), false);
  assert.equal(body.includes(fixture.store.read(receipt.inquiry_id, roles.reviewer).raw_json), false);
  assert.throws(() => fixture.store.listOutbox(roles.reviewer), /not authorized/);
});

test("with no configured transport an attempt fails observably and never claims delivery", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "retry-key-011", roles.receiver, scoping());
  const eventId = "notify-" + receipt.inquiry_id;
  const attempted = await fixture.store.processOutbox(eventId, null, roles.notifier);
  assert.equal(attempted.status, "PENDING");
  // Nothing was attempted, so nothing is counted as an attempt. This used to
  // record an attempt and an error for a delivery nobody tried, which left an
  // operator unable to tell a refused delivery from an unconfigured one.
  assert.equal(attempted.attempts, 0);
  assert.equal(attempted.last_outcome, "NOT_ATTEMPTED_NO_TRANSPORT");
  assert.equal(attempted.last_error, "");
  const retried = await fixture.store.processOutbox(eventId, null, roles.notifier);
  assert.equal(retried.attempts, 0);
  assert.equal(retried.status, "PENDING");
  assert.equal(retried.last_outcome, "NOT_ATTEMPTED_NO_TRANSPORT");

  // A transport that exists and refuses is the other outcome, and it is the
  // one that counts: an attempt happened, it failed, and the reason is kept.
  const refused = await fixture.store.processOutbox(
    eventId,
    async () => {
      throw Error("synthetic transport refused the notification");
    },
    roles.notifier,
  );
  assert.equal(refused.attempts, 1);
  assert.equal(refused.status, "PENDING");
  assert.equal(refused.last_outcome, "ATTEMPT_FAILED");
  assert.match(refused.last_error, /synthetic transport refused/);
  // And the two are distinguishable afterwards, which is the whole point.
  assert.notEqual(attempted.last_outcome, refused.last_outcome);
  // The inquiry survives every failed notification attempt.
  assert.equal(fixture.store.read(receipt.inquiry_id, roles.reviewer).lifecycle, "ACTIVE");
});

test("a configured destination is recorded without opening any connection", async () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "carbon-team-intake-"));
  const store = openStore(path.join(directory, "store.json"), {
    destination: "Hello@carbonphysics.ai",
  });
  const receipt = await store.accept(reviewedRaw(), "retry-key-012", roles.receiver, scoping());
  assert.equal(store.listOutbox(roles.notifier)[0].destination, "Hello@carbonphysics.ai");
  assert.equal(store.listOutbox(roles.notifier)[0].status, "PENDING");
  assert.equal(store.read(receipt.inquiry_id, roles.reviewer).lifecycle, "ACTIVE");
});

test("a storage failure returns no receipt and stores no partial inquiry", async () => {
  const fixture = temporaryStore();
  fs.chmodSync(fixture.directory, 0o500);
  try {
    await assert.rejects(() =>
      fixture.store.accept(reviewedRaw(), "retry-key-013", roles.receiver, scoping()),
    );
  } finally {
    fs.chmodSync(fixture.directory, 0o700);
  }
  assert.equal(fs.existsSync(fixture.file), false);
  assert.deepEqual(Object.keys(fixture.store.state.inquiries), []);
  // The same key succeeds once storage recovers; no phantom record blocks it.
  const receipt = await fixture.store.accept(reviewedRaw(), "retry-key-013", roles.receiver, scoping());
  assert.equal(receipt.disposition, "ACCEPTED");
  assert.equal(fs.readdirSync(fixture.directory).filter((n) => n.includes(".tmp-")).length, 0);
});

test("completing a notification keeps writes made during the await window", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "retry-key-014", roles.receiver, scoping());
  const other = JSON.parse(reviewedRaw());
  other.brief.draft_id = "synthetic-second-inquiry";
  const second = await fixture.store.accept(
    JSON.stringify(other),
    "retry-key-015",
    roles.receiver, scoping(),
);
  assert.notEqual(second.inquiry_id, receipt.inquiry_id);
  let release;
  const opened = new Promise((resolve) => {
    release = resolve;
  });
  // The operator's transport is slow. A reviewer files an assessment and a
  // steward deletes a different inquiry while that delivery is still in flight.
  const delivering = fixture.store.processOutbox(
    "notify-" + receipt.inquiry_id,
    () => opened,
    roles.notifier,
  );
  fixture.store.update(
    receipt.inquiry_id,
    1,
    { assigned_reviewer: "Ryan", queue_state: "UNDER_REVIEW", note: "Filed mid-delivery." },
    roles.reviewer,
  );
  approveDeletion(fixture.store, second.inquiry_id);
  fixture.store.delete(second.inquiry_id, roles.steward);
  release();
  const event = await delivering;
  assert.equal(event.status, "DELIVERED");

  // Neither concurrent write may be erased by the completing notification.
  const current = fixture.store.read(receipt.inquiry_id, roles.reviewer);
  assert.equal(current.team_fields.note, "Filed mid-delivery.");
  assert.equal(current.version, 2);
  assert.equal(current.assessments.length, 1);
  assert.throws(() => fixture.store.read(second.inquiry_id, roles.reviewer), /not found/);
  assert.equal(Boolean(fixture.store.state.tombstones[second.inquiry_id]), true);
  // The same must hold on disk, not only in memory.
  const restarted = openStore(fixture.file);
  assert.equal(restarted.read(receipt.inquiry_id, roles.reviewer).team_fields.note, "Filed mid-delivery.");
  assert.equal(restarted.state.outbox["notify-" + receipt.inquiry_id].status, "DELIVERED");
  assert.equal(restarted.state.inquiries[second.inquiry_id], undefined);
});

test("a transient flush failure does not block every later write", async () => {
  const fixture = temporaryStore();
  await fixture.store.accept(reviewedRaw(), "retry-key-016", roles.receiver, scoping());
  const realFsync = fs.fsyncSync;
  let injected = false;
  fs.fsyncSync = (fd) => {
    if (!injected) {
      injected = true;
      throw Object.assign(Error("synthetic flush failure"), { code: "EIO" });
    }
    return realFsync(fd);
  };
  try {
    assert.throws(
      () =>
        fixture.store.update(
          Object.keys(fixture.store.state.inquiries)[0],
          1,
          { assigned_reviewer: "Ryan", queue_state: "UNDER_REVIEW", note: "blocked" },
          roles.reviewer,
        ),
      /synthetic flush failure/,
    );
  } finally {
    fs.fsyncSync = realFsync;
  }
  // The transient error has cleared. The store must not be wedged by a
  // leftover temporary file from the failed attempt.
  assert.deepEqual(
    fs.readdirSync(fixture.directory).filter((name) => name.includes(".tmp-")),
    [],
  );
  const inquiryId = Object.keys(fixture.store.state.inquiries)[0];
  const updated = fixture.store.update(
    inquiryId,
    1,
    { assigned_reviewer: "Ryan", queue_state: "UNDER_REVIEW", note: "recovered" },
    roles.reviewer,
  );
  assert.equal(updated.team_fields.note, "recovered");
  assert.equal(openStore(fixture.file).read(inquiryId, roles.reviewer).team_fields.note, "recovered");
});

test("a delivery in flight cannot resurrect an inquiry deleted during its await", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "retry-key-017", roles.receiver, scoping());
  const eventId = "notify-" + receipt.inquiry_id;
  let release;
  const opened = new Promise((resolve) => {
    release = resolve;
  });
  const delivering = fixture.store.processOutbox(eventId, () => opened, roles.notifier);
  // The steward exercises the deletion lifecycle while delivery is in flight.
  approveDeletion(fixture.store, receipt.inquiry_id);
  fixture.store.delete(receipt.inquiry_id, roles.steward);
  release();
  await assert.rejects(() => delivering, /removed while its delivery was in flight/);
  assert.equal(fixture.store.state.outbox[eventId], undefined);
  assert.equal(fixture.store.state.inquiries[receipt.inquiry_id], undefined);
  const restarted = openStore(fixture.file);
  assert.equal(restarted.state.outbox[eventId], undefined);
  assert.equal(restarted.state.inquiries[receipt.inquiry_id], undefined);
  assert.equal(Boolean(restarted.state.tombstones[receipt.inquiry_id]), true);
});

// --- versioned retention and archive controls --------------------------------

test("the retention policy is versioned and leaves the legal fields unresolved", () => {
  const { RETENTION_POLICY, RETENTION_VERSION } = require("../tools/team_intake_store.cjs");
  assert.equal(RETENTION_POLICY.schema_version, RETENTION_VERSION);
  assert.equal(RETENTION_POLICY.default_disposition, "ARCHIVE_INDEFINITE");
  // A guess here would be a legal conclusion written by an engineer. These
  // belong to Ryan and Nick under OD-25 and are unresolved on purpose.
  assert.equal(RETENTION_POLICY.approved_by, null);
  assert.equal(RETENTION_POLICY.legal_basis, null);
  assert.equal(RETENTION_POLICY.production_period, null);
  // What a deletion can and cannot reach is stated rather than implied.
  assert.deepEqual(RETENTION_POLICY.deletion_cannot_reach,
    ["RETAINED_ARCHIVE", "PRIOR_EXPORTS", "PROVIDER_RECORDS"]);
});

test("archiving retains the record and removes it from the working set", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "retention-001", roles.receiver, scoping());
  assert.equal(fixture.store.search(roles.reviewer).length, 1);

  assert.throws(() => fixture.store.archive(receipt.inquiry_id, roles.reviewer), /not authorized/);
  const archived = fixture.store.archive(receipt.inquiry_id, roles.steward);
  assert.equal(archived.lifecycle, "ARCHIVED");
  assert.equal(archived.retention.disposition, "ARCHIVE_INDEFINITE");
  assert.equal(archived.retention.archived_by, "synthetic-steward");

  // Out of search and index, still present and readable.
  assert.deepEqual(fixture.store.search(roles.reviewer), []);
  assert.equal(fixture.store.search(roles.reviewer, { includeArchived: true }).length, 1);
  assert.equal(fixture.store.read(receipt.inquiry_id, roles.reviewer).raw_json.length > 0, true);
  // Nothing was erased: the bytes are byte-identical to what was accepted.
  assert.equal(fixture.store.read(receipt.inquiry_id, roles.reviewer).raw_sha256, receipt.raw_sha256);

  // Export of an archived record is a separate decision.
  assert.throws(
    () => fixture.store.export(receipt.inquiry_id, roles.reviewer, RELEASE),
    /requires an explicit archive request/,
  );
  assert.equal(
    fixture.store.export(receipt.inquiry_id, roles.reviewer, { includeArchived: true, ...RELEASE }).raw_sha256,
    receipt.raw_sha256,
  );

  const restored = fixture.store.restore(receipt.inquiry_id, roles.steward);
  assert.equal(restored.lifecycle, "ACTIVE");
  assert.equal(restored.retention.restored_by, "synthetic-steward");
  assert.equal(fixture.store.search(roles.reviewer).length, 1);
  assert.equal(openStore(fixture.file).read(receipt.inquiry_id, roles.reviewer).lifecycle, "ACTIVE");
});

test("a deletion exception is named, reasoned and bounded", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "retention-002", roles.receiver, scoping());

  assert.throws(
    () => fixture.store.approveDeletionException(receipt.inquiry_id, { approver: "", reason: "Synthetic cleanup." }, roles.steward),
    /named approver/,
  );
  assert.throws(
    () => fixture.store.approveDeletionException(receipt.inquiry_id, { approver: "Ryan Bequette", reason: "no" }, roles.steward),
    /stated reason/,
  );
  assert.throws(
    () => fixture.store.approveDeletionException(receipt.inquiry_id, { approver: "Ryan Bequette", reason: "Synthetic cleanup." }, roles.reviewer),
    /not authorized/,
  );

  const exception = approveDeletion(fixture.store, receipt.inquiry_id);
  assert.equal(exception.approver, "Ryan Bequette");
  assert.equal(exception.recorded_by, "synthetic-steward");
  assert.deepEqual(exception.cannot_reach, ["RETAINED_ARCHIVE", "PRIOR_EXPORTS", "PROVIDER_RECORDS"]);
});

test("a tombstone states what the deletion did not reach", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "retention-003", roles.receiver, scoping());
  approveDeletion(fixture.store, receipt.inquiry_id);
  const tombstone = fixture.store.delete(receipt.inquiry_id, roles.steward);

  assert.equal(tombstone.approved_by, "Ryan Bequette");
  assert.deepEqual(tombstone.reached, ["ACTIVE_RECORD", "ACTIVE_INDEX", "PENDING_NOTIFICATIONS"]);
  // Promising removal from retained archives, prior exports or a provider would
  // be a promise this store cannot keep, so the tombstone says so instead.
  assert.deepEqual(tombstone.did_not_reach, ["RETAINED_ARCHIVE", "PRIOR_EXPORTS", "PROVIDER_RECORDS"]);
  assert.equal(JSON.stringify(fixture.store.state).includes("Compare the reported baseline"), false);
  assert.equal(openStore(fixture.file).state.tombstones[receipt.inquiry_id].did_not_reach.length, 3);
});

test("a v2 store migrates to versioned retention without back-dating an archive", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "retention-004", roles.receiver, scoping());
  // A v2 store predates E1, so it is plaintext: built from the in-memory state.
  const legacy = JSON.parse(JSON.stringify(fixture.store.state));
  legacy.schema_version = "carbon.private-team-intake.store.v2";
  delete legacy.exceptions;
  for (const record of Object.values(legacy.inquiries))
    record.retention = { policy: "LOCAL_SYNTHETIC_DELETE_ON_REQUEST", production_period: null };
  fs.writeFileSync(fixture.file, JSON.stringify(legacy, null, 2) + "\n");

  const migrated = openStore(fixture.file);
  const record = migrated.read(receipt.inquiry_id, roles.reviewer);
  assert.equal(record.retention.schema_version, "carbon.private-team-intake.retention.v1");
  assert.equal(record.retention.disposition, "ARCHIVE_INDEFINITE");
  // No archive action was ever taken, so none is recorded.
  assert.equal(record.retention.archived_at, null);
  assert.equal(record.retention.archived_by, null);
  assert.equal(record.retention.exception_id, null);
  // The v2 assessment history survives the migration untouched.
  assert.equal(Array.isArray(record.assessments), true);
});

// --- negative controls for the retention guarantees ---------------------------
//
// A guarantee asserted only against the conforming store is worth nothing: it
// may be true for a reason the assertion never touches. Each guarantee below is
// a single function run twice — once against the real store, once against a
// variant built to violate exactly that guarantee and nothing else. The second
// run must fail. A guarantee whose variant still passes is not being checked.

// The variants below are ordinary store code and must not reach for anything
// the module keeps private; a variant that dies of a ReferenceError would make
// the control pass without ever exercising the guarantee.
const clone = (value) => JSON.parse(JSON.stringify(value));

function variantStore(file, overrides) {
  class NonConforming extends DurableIntakeStore {}
  Object.assign(NonConforming.prototype, overrides);
  return new NonConforming(file, { keyring: keyringFor(file) });
}

const RETENTION_GUARANTEES = [
  {
    name: "archiving takes the record out of the active index",
    async check(store, receipt) {
      store.archive(receipt.inquiry_id, roles.steward);
      assert.deepEqual(store.search(roles.reviewer), []);
    },
    // An index that reports archived records as working items.
    violate: {
      search() {
        return Object.values(this.state.inquiries).map((r) => ({ inquiry_id: r.inquiry_id }));
      },
    },
  },
  {
    name: "archiving retains the record rather than erasing it",
    async check(store, receipt) {
      store.archive(receipt.inquiry_id, roles.steward);
      const record = store.read(receipt.inquiry_id, roles.reviewer);
      assert.equal(record.raw_sha256, receipt.raw_sha256);
      assert.equal(record.raw_json.length > 0, true);
    },
    // "Archive" implemented as quiet erasure — the failure this store exists
    // to prevent, and the one an ARCHIVED lifecycle flag alone would hide.
    violate: {
      archive(inquiryId, principal) {
        const next = clone(this.state);
        next.inquiries[inquiryId].lifecycle = "ARCHIVED";
        next.inquiries[inquiryId].raw_json = "";
        next.inquiries[inquiryId].raw_sha256 = null;
        this.persist(next);
        return clone(next.inquiries[inquiryId]);
      },
    },
  },
  {
    name: "exporting an archived record is a separate explicit decision",
    async check(store, receipt) {
      store.archive(receipt.inquiry_id, roles.steward);
      assert.throws(() => store.export(receipt.inquiry_id, roles.reviewer, RELEASE), /explicit archive request/);
    },
    violate: {
      export(inquiryId) {
        return clone(this.state.inquiries[inquiryId]);
      },
    },
  },
  {
    name: "deletion requires an approved retention exception",
    async check(store, receipt) {
      assert.throws(
        () => store.delete(receipt.inquiry_id, roles.steward),
        /approved retention exception/,
      );
    },
    violate: {
      delete(inquiryId) {
        const next = clone(this.state);
        delete next.inquiries[inquiryId];
        next.tombstones[inquiryId] = { inquiry_id: inquiryId };
        this.persist(next);
        return clone(next.tombstones[inquiryId]);
      },
    },
  },
  {
    name: "the tombstone states what the deletion did not reach",
    async check(store, receipt) {
      approveDeletion(store, receipt.inquiry_id);
      const tombstone = store.delete(receipt.inquiry_id, roles.steward);
      assert.deepEqual(tombstone.did_not_reach,
        ["RETAINED_ARCHIVE", "PRIOR_EXPORTS", "PROVIDER_RECORDS"]);
    },
    // A deletion that claims to have reached everything. Nothing about the
    // bytes differs; the claim does, and the claim is what a person acts on.
    violate: {
      delete(inquiryId, principal) {
        const tombstone = DurableIntakeStore.prototype.delete.call(this, inquiryId, principal);
        return { ...tombstone, did_not_reach: [] };
      },
    },
  },
];

test("every retention guarantee fails against a store built to violate it", async () => {
  for (const guarantee of RETENTION_GUARANTEES) {
    const control = temporaryStore();
    const receipt = await control.store.accept(reviewedRaw(), "control", roles.receiver, scoping());
    await guarantee.check(control.store, receipt);

    const subject = temporaryStore();
    const other = await subject.store.accept(reviewedRaw(), "variant", roles.receiver, scoping());
    // Specifically an assertion failure. Any other error means the variant
    // broke before it reached the behaviour, and the control proved nothing.
    await assert.rejects(
      Promise.resolve().then(() =>
        guarantee.check(variantStore(subject.file, guarantee.violate), other),
      ),
      assert.AssertionError,
      "guarantee did not fail as an assertion against its violating store: " + guarantee.name,
    );
  }
});

test("the migration check rejects a store that back-dates an archive", async () => {
  // The conforming case is asserted above. Here the same assertion meets a
  // store whose migration invented an archive action for a record that was
  // never archived — the plausible mistake, since the accepted time is sitting
  // right there and would make the field look populated and correct.
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "retention-005", roles.receiver, scoping());
  const forged = JSON.parse(fs.readFileSync(fixture.file, "utf8"));
  const record = forged.inquiries[receipt.inquiry_id];
  record.retention = { ...record.retention, archived_at: record.accepted_at, archived_by: "migration" };
  fs.writeFileSync(fixture.file, JSON.stringify(forged, null, 2) + "\n");

  const reopened = openStore(fixture.file);
  assert.throws(() => {
    assert.equal(reopened.read(receipt.inquiry_id, roles.reviewer).retention.archived_at, null);
  });
});

test("the negative-control harness itself fails when nothing is violated", async () => {
  // Guards the harness, not the store. If `violate` were dropped or silently
  // not applied, every control above would still report a pass, because a
  // guarantee holding against a store is indistinguishable from a guarantee
  // that was never given a violating store to run against.
  for (const guarantee of RETENTION_GUARANTEES) {
    const fixture = temporaryStore();
    const receipt = await fixture.store.accept(reviewedRaw(), "meta", roles.receiver, scoping());
    await assert.rejects(
      assert.rejects(
        Promise.resolve().then(() => guarantee.check(variantStore(fixture.file, {}), receipt)),
        assert.AssertionError,
      ),
      "harness accepted a conforming store as a violation: " + guarantee.name,
    );
  }
});

// --- authenticated staff identity --------------------------------------------

test("a principal cannot be constructed without authenticating an account", () => {
  assert.throws(() => new StaffPrincipal(Symbol("guess"), {
    principal: "synthetic-steward", team: TEAM, roles: ["DATA_STEWARD"],
  }), /issued by authenticating/);
  // The directory itself issues nothing: the single-factor path is gone, and
  // a credential only ever names an account for the session authority.
  assert.equal(typeof DIRECTORY.authenticate, "undefined");
  assert.equal(DIRECTORY.accountForCredential("not-a-real-token-000000"), null);

  // The two forgeries that a class check accepts. Both hold the prototype;
  // neither was ever issued, and the spread copy even carries the real id,
  // team and roles of a genuine principal.
  const { isAuthenticatedPrincipal } = require("../tools/team_staff_directory.cjs");
  const hollow = Object.create(StaffPrincipal.prototype);
  assert.equal(hollow instanceof StaffPrincipal, true);
  assert.equal(isAuthenticatedPrincipal(hollow), false);
  const copied = { ...as("steward") };
  assert.equal(copied.id, "synthetic-steward");
  assert.equal(isAuthenticatedPrincipal(copied), false);

  const issued = as("steward");
  assert.equal(isAuthenticatedPrincipal(issued), true);
  assert.equal(issued.id, "synthetic-steward");
  assert.equal(issued.team, TEAM);
  assert.equal(Object.isFrozen(issued), true);
  // The roles travel with the identity and cannot be widened after issue.
  assert.throws(() => { issued.roles.push("TEAM_REVIEWER"); }, TypeError);
  assert.equal(issued.has("TEAM_REVIEWER"), false);
});

test("a directory refuses accounts that would make provenance ambiguous", () => {
  const ok = enrolled("a-steward", TEAM, ["DATA_STEWARD"], "t-1-synthetic-credential");
  const refused = [
    [{ ...ok, token_sha256: "plaintext-token" }, /credential digest, never a credential/],
    [{ ...ok, team: undefined }, /named owning team/],
    [{ ...ok, roles: [] }, /at least one role/],
    [{ ...ok, roles: ["ADMIN"] }, /Unknown staff role/],
    [{ ...ok, status: undefined }, /ACTIVE or DISABLED/],
  ];
  for (const [account, pattern] of refused)
    assert.throws(() => new StaffDirectory([account]), pattern);
  // Two accounts behind one credential: the credential would authenticate as
  // whichever account happened to be listed first, and every later provenance
  // entry would name that one.
  assert.throws(
    () => new StaffDirectory([ok, { ...ok, principal: "b-steward" }]),
    /Duplicate staff credential digest/,
  );
  assert.throws(() => new StaffDirectory([ok, { ...ok, token_sha256: digest("t-2") }]), /Duplicate staff account/);
  // An active account without a second factor is refused when the directory
  // loads, so no session can ever be opened for it.
  assert.throws(() => new StaffDirectory([{ ...ok, totp_secret: undefined }]), /enrolled second factor/);
  assert.throws(() => new StaffDirectory([{ ...ok, totp_secret: "SHORT" }]), /enrolled second factor/);
  // A disabled account holds its roles and still cannot act.
  const disabled = new StaffDirectory([{ ...ok, status: "DISABLED" }]);
  assert.throws(() => principalFor(disabled, "t-1-synthetic-credential"), /AUTHENTICATION_FAILED/);
  // Specimen: the same account, active, does authenticate.
  assert.equal(principalFor(new StaffDirectory([ok]), "t-1-synthetic-credential").id, "a-steward");
});

test("every store endpoint refuses a caller that was never authenticated", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "role-001", roles.receiver, scoping());
  approveDeletion(fixture.store, receipt.inquiry_id);

  // Enumerated from the prototype rather than listed by hand, so an endpoint
  // added later is covered without anyone remembering to add it here. A list
  // maintained by hand is the thing that goes stale.
  // Exempt, with the reason stated rather than assumed. The lock is taken by
  // the process at startup, before any credential has been presented and
  // before any staff identity exists, so there is no principal to check and
  // requiring one would be theatre. Everything a caller can reach over the
  // wire is below.
  const exempt = new Set([
    "constructor",
    "persist",
    "acquireWriterLock",
    "releaseWriterLock",
    // Seals a pre-E1 plaintext store at startup, under the writer lock, before
    // any staff identity exists. It discloses nothing and returns a boolean.
    "sealAtRest",
  ]);
  const endpoints = Object.getOwnPropertyNames(DurableIntakeStore.prototype)
    .filter((name) => !exempt.has(name) && typeof fixture.store[name] === "function");
  assert.equal(endpoints.length >= 10, true, "endpoint enumeration found almost nothing");

  const impostors = [
    undefined,
    null,
    { id: "synthetic-steward", team: TEAM, roles: ["DATA_STEWARD"] },
    { ...as("steward") },
    Object.create(StaffPrincipal.prototype),
  ];
  for (const name of endpoints) {
    for (const impostor of impostors) {
      // Arguments are deliberately generous; the refusal must come from the
      // identity check, before any argument is honoured.
      const call = () => fixture.store[name](receipt.inquiry_id, 1, {}, impostor, impostor);
      await assert.rejects(
        Promise.resolve().then(call).then(
          (value) => { throw Object.assign(Error("endpoint ran unauthenticated: " + name), { leaked: value }); },
          (error) => { throw error; },
        ),
        /authenticated staff principal|Named principal|not authorized/,
        name,
      );
    }
  }
});

test("a principal from another team is refused as if the inquiry did not exist", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "role-002", roles.receiver, scoping());
  const missing = "inquiry-000000000000000";

  // The foreign principal holds every role this receiver defines. Role checks
  // alone would let all of this through.
  for (const attempt of [
    (p) => fixture.store.read(receipt.inquiry_id, p),
    (p) => fixture.store.export(receipt.inquiry_id, p, RELEASE),
    (p) => fixture.store.update(receipt.inquiry_id, 1, { assigned_reviewer: "x", note: "", queue_state: "PARKED" }, p),
    (p) => fixture.store.archive(receipt.inquiry_id, p),
    (p) => fixture.store.restore(receipt.inquiry_id, p),
    (p) => fixture.store.approveDeletionException(receipt.inquiry_id, { approver: "Ryan Bequette", reason: "Synthetic cleanup." }, p),
    (p) => fixture.store.delete(receipt.inquiry_id, p),
  ]) {
    let foreignError, missingError;
    try { await attempt(roles.foreign); } catch (error) { foreignError = error.message; }
    try { await fixture.store.read(missing, roles.foreign); } catch (error) { missingError = error.message; }
    assert.equal(foreignError, missingError);
  }

  // The outbox answers the same way, against its own not-found refusal: an
  // event carries a summary of the record, so it is the same disclosure.
  let foreignOutbox, missingOutbox;
  try { await fixture.store.processOutbox("notify-" + receipt.inquiry_id, null, roles.foreign); }
  catch (error) { foreignOutbox = error.message; }
  try { await fixture.store.processOutbox("notify-nothing", null, roles.foreign); }
  catch (error) { missingOutbox = error.message; }
  assert.equal(foreignOutbox, missingOutbox);

  assert.deepEqual(fixture.store.search(roles.foreign), []);
  assert.deepEqual(fixture.store.listOutbox(roles.foreign), []);
  // The owning team is unaffected, so the denial is about ownership and not
  // about the store having refused everyone.
  assert.equal(fixture.store.search(roles.reviewer).length, 1);
  assert.equal(fixture.store.listOutbox(roles.notifier).length, 1);
  assert.equal(fixture.store.read(receipt.inquiry_id, roles.reviewer).owner_team, TEAM);
});

test("a migrated record has no owning team and is reachable by nobody", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "role-003", roles.receiver, scoping());
  // A v2 store predates E1, so it is plaintext: built from the in-memory state.
  const legacy = JSON.parse(JSON.stringify(fixture.store.state));
  legacy.schema_version = "carbon.private-team-intake.store.v2";
  delete legacy.exceptions;
  for (const record of Object.values(legacy.inquiries)) delete record.owner_team;
  fs.writeFileSync(fixture.file, JSON.stringify(legacy, null, 2) + "\n");

  const migrated = openStore(fixture.file);
  // Not a guessed team, and not a team at all: the placeholder is upper case
  // and a directory team cannot be, so no account can ever match it.
  assert.equal(migrated.state.inquiries[receipt.inquiry_id].owner_team, "MIGRATED_TEAM_UNASSIGNED");
  // Principals that hold the read role, so a refusal here is about ownership.
  for (const principal of [roles.reviewer, roles.receiver, roles.foreign])
    assert.throws(() => migrated.read(receipt.inquiry_id, principal), /Inquiry not found/);
  assert.throws(() => new StaffDirectory([
    enrolled("a-steward", "MIGRATED_TEAM_UNASSIGNED", ["DATA_STEWARD"], "t-3-synthetic-credential"),
  ]), /named owning team/);
});

// --- restart and storage-failure recovery ------------------------------------

test("a store interrupted before its rename restarts on the last good state", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "recover-001", roles.receiver, scoping());
  fixture.store.update(
    receipt.inquiry_id, 1,
    { assigned_reviewer: "Ryan", queue_state: "UNDER_REVIEW", note: "Committed." },
    roles.reviewer,
  );

  // A process killed between the write and the rename. The replacement bytes
  // exist and the directory entry never moved, so the committed state is the
  // one before them — including a revision the dead process was mid-way
  // through, which must not be half-applied.
  const doomed = JSON.parse(JSON.stringify(fixture.store.state));
  doomed.inquiries[receipt.inquiry_id].team_fields.note = "Never committed.";
  doomed.inquiries[receipt.inquiry_id].version = 99;
  fs.writeFileSync(fixture.file + ".tmp-" + process.pid + "-interrupted", JSON.stringify(doomed));

  const restarted = openStore(fixture.file);
  const record = restarted.read(receipt.inquiry_id, roles.reviewer);
  assert.equal(record.team_fields.note, "Committed.");
  assert.equal(record.version, 2);

  // The debris is reported, not deleted: another process may be writing that
  // exact file, and removing a live write would be the worse failure.
  assert.equal(restarted.pendingWriteDebris(roles.steward).length, 1);
  assert.equal(fs.existsSync(restarted.pendingWriteDebris(roles.steward)[0]), true);

  // And it blocks nothing. A unique name per attempt is what makes this true;
  // a fixed temporary name plus an exclusive create wedged every later write.
  const updated = restarted.update(
    receipt.inquiry_id, 2,
    { assigned_reviewer: "Nick", queue_state: "READY_FOR_ROUTE", note: "After recovery." },
    roles.reviewer,
  );
  assert.equal(updated.version, 3);
  assert.equal(openStore(fixture.file).read(receipt.inquiry_id, roles.reviewer).version, 3);
});

test("a damaged store refuses to open rather than starting empty", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "recover-002", roles.receiver, scoping());
  const good = fs.readFileSync(fixture.file, "utf8");

  // Starting empty is the dangerous recovery: every accepted inquiry silently
  // disappears, the idempotency index goes with it, and a client retry is
  // accepted a second time as a new record. Each of these must refuse.
  for (const [name, bytes] of [
    ["truncated", good.slice(0, Math.floor(good.length / 2))],
    ["empty", ""],
    ["not json", "recovered from backup?"],
    ["json but not a store", JSON.stringify({ inquiries: {} })],
    ["unknown schema", good.replace(SEALED_STORE_VERSION, "carbon.private-team-intake.store.v9")],
  ]) {
    fs.writeFileSync(fixture.file, bytes);
    assert.throws(() => openStore(fixture.file), Error, name);
  }

  // The operator restores the file; nothing about the refusals damaged it.
  fs.writeFileSync(fixture.file, good);
  const reopened = openStore(fixture.file);
  assert.equal(reopened.read(receipt.inquiry_id, roles.reviewer).inquiry_id, receipt.inquiry_id);
  // The idempotency index survived, so the client's retry still deduplicates.
  assert.equal(
    (await reopened.accept(reviewedRaw(), "recover-002", roles.receiver, scoping())).disposition,
    "DEDUPLICATED",
  );
});

test("a failed write leaves the previous committed state readable", async () => {
  const fixture = temporaryStore();
  const first = await fixture.store.accept(reviewedRaw(), "recover-003", roles.receiver, scoping());
  approveDeletion(fixture.store, first.inquiry_id);

  const realRename = fs.renameSync;
  fs.renameSync = () => { throw Object.assign(Error("synthetic rename failure"), { code: "EIO" }); };
  try {
    assert.throws(() => fixture.store.delete(first.inquiry_id, roles.steward), /synthetic rename failure/);
  } finally {
    fs.renameSync = realRename;
  }

  // The deletion did not happen and does not half-happen: no tombstone, the
  // record intact, and no debris from the attempt.
  const reopened = openStore(fixture.file);
  assert.deepEqual(Object.keys(reopened.state.tombstones), []);
  assert.equal(reopened.read(first.inquiry_id, roles.reviewer).inquiry_id, first.inquiry_id);
  assert.deepEqual(reopened.pendingWriteDebris(roles.steward), []);
  // The approved exception is still on record, so the retry needs no re-approval.
  assert.equal(
    reopened.delete(first.inquiry_id, roles.steward).approved_by,
    "Ryan Bequette",
  );
});

test("the retention lifecycle is append-only across an archive and restore cycle", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "provenance-001", roles.receiver, scoping());
  fixture.store.archive(receipt.inquiry_id, roles.steward);
  fixture.store.restore(receipt.inquiry_id, roles.steward);
  fixture.store.archive(receipt.inquiry_id, roles.steward);
  approveDeletion(fixture.store, receipt.inquiry_id);

  const record = fixture.store.read(receipt.inquiry_id, roles.reviewer);
  assert.deepEqual(record.retention_events.map((event) => event.action),
    ["ARCHIVED", "RESTORED", "ARCHIVED", "DELETION_EXCEPTION_APPROVED"]);
  assert.deepEqual(record.retention_events.map((event) => event.seq), [1, 2, 3, 4]);
  for (const event of record.retention_events) assert.equal(event.actor, "synthetic-steward");
  assert.equal(record.retention_events[3].approver, "Ryan Bequette");
  // Current state cannot answer this on its own: the restore cleared the first
  // archive's fields, so without the history the first archive never happened.
  assert.equal(record.retention.archived_by, "synthetic-steward");
  assert.equal(record.retention_events.filter((e) => e.action === "ARCHIVED").length, 2);
  assert.equal(openStore(fixture.file).read(receipt.inquiry_id, roles.reviewer)
    .retention_events.length, 4);
});

test("a retention history with an entry removed is refused", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "provenance-002", roles.receiver, scoping());
  fixture.store.archive(receipt.inquiry_id, roles.steward);
  fixture.store.restore(receipt.inquiry_id, roles.steward);
  fixture.store.archive(receipt.inquiry_id, roles.steward);

  const good = JSON.parse(fs.readFileSync(fixture.file, "utf8"));
  // Removing the middle entry leaves a list that reads perfectly naturally:
  // archived, then archived again. The sequence numbers are what make the
  // removal visible, which is the only reason they are written down.
  const edited = JSON.parse(JSON.stringify(good));
  edited.inquiries[receipt.inquiry_id].retention_events.splice(1, 1);
  fs.writeFileSync(fixture.file, JSON.stringify(edited, null, 2) + "\n");
  assert.throws(() => openStore(fixture.file), /contiguous append-only sequence/);

  // A truncation from the end is not detected here, and this says so rather
  // than implying the check is stronger than it is: a local JSON file has no
  // authority over an operator with write access, and the append-only property
  // is enforced against the code, not against the disk.
  const truncated = JSON.parse(JSON.stringify(good));
  truncated.inquiries[receipt.inquiry_id].retention_events.pop();
  fs.writeFileSync(fixture.file, JSON.stringify(truncated, null, 2) + "\n");
  assert.equal(openStore(fixture.file)
    .read(receipt.inquiry_id, roles.reviewer).retention_events.length, 2);

  fs.writeFileSync(fixture.file, JSON.stringify(good, null, 2) + "\n");
  assert.equal(openStore(fixture.file)
    .read(receipt.inquiry_id, roles.reviewer).retention_events.length, 3);
});

test("an archived record cannot be revised until it is restored", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "archive-update-001", roles.receiver, scoping());
  const patch = { assigned_reviewer: "Ryan", queue_state: "UNDER_REVIEW", note: "Synthetic." };
  fixture.store.archive(receipt.inquiry_id, roles.steward);

  assert.throws(
    () => fixture.store.update(receipt.inquiry_id, 1, patch, roles.reviewer),
    /until it is restored/,
  );
  // The refusal is about the archive, not a version conflict: the version the
  // caller holds is the current one.
  assert.equal(fixture.store.read(receipt.inquiry_id, roles.reviewer).version, 1);
  assert.equal(fixture.store.read(receipt.inquiry_id, roles.reviewer).assessments.length, 0);

  fixture.store.restore(receipt.inquiry_id, roles.steward);
  assert.equal(fixture.store.update(receipt.inquiry_id, 1, patch, roles.reviewer).version, 2);
  // And the restore that made it possible is on the record.
  assert.deepEqual(
    fixture.store.read(receipt.inquiry_id, roles.reviewer).retention_events.map((e) => e.action),
    ["ARCHIVED", "RESTORED"],
  );
});

test("each endpoint admits exactly the roles it is supposed to", async () => {
  // The enumeration above proves every endpoint refuses a caller that was never
  // authenticated. It says nothing about which authenticated callers each one
  // admits, so an endpoint wired to the wrong role would pass it. This is that
  // matrix, written out so a change to the roles map has to change a table
  // somebody reads rather than only a line somebody edits.
  const MATRIX = {
    accept: ["receiver"],
    read: ["reviewer", "receiver"],
    update: ["reviewer"],
    export: ["reviewer"],
    search: ["reviewer", "receiver"],
    archive: ["steward"],
    restore: ["steward"],
    approveDeletionException: ["steward"],
    delete: ["steward"],
    pendingWriteDebris: ["steward"],
    capacity: ["steward"],
    listOutbox: ["notifier"],
    processOutbox: ["notifier"],
  };
  const everyone = ["receiver", "reviewer", "second_reviewer", "steward", "notifier"];

  for (const [endpoint, permitted] of Object.entries(MATRIX)) {
    for (const name of everyone) {
      const fixture = temporaryStore();
      const receipt = await fixture.store.accept(reviewedRaw(), "matrix", roles.receiver, scoping());
      approveDeletion(fixture.store, receipt.inquiry_id);
      const id = receipt.inquiry_id;
      const call = {
        accept: (p) => fixture.store.accept(reviewedRaw(), "matrix-2", p, scoping()),
        read: (p) => fixture.store.read(id, p),
        update: (p) => fixture.store.update(id, 1, { assigned_reviewer: "", note: "", queue_state: "PARKED" }, p),
        export: (p) => fixture.store.export(id, p, RELEASE),
        search: (p) => fixture.store.search(p),
        archive: (p) => fixture.store.archive(id, p),
        restore: (p) => fixture.store.restore(id, p),
        approveDeletionException: (p) => fixture.store.approveDeletionException(id, { approver: "Ryan Bequette", reason: "Synthetic cleanup." }, p),
        delete: (p) => fixture.store.delete(id, p),
        pendingWriteDebris: (p) => fixture.store.pendingWriteDebris(p),
        capacity: (p) => fixture.store.capacity(p),
        listOutbox: (p) => fixture.store.listOutbox(p),
        processOutbox: (p) => fixture.store.processOutbox("notify-" + id, async () => {}, p),
      }[endpoint];

      // A reviewer is two accounts, so "reviewer" in the table covers both.
      const allowed = permitted.includes(name) ||
        (permitted.includes("reviewer") && name === "second_reviewer");
      let refusal = null;
      try { await call(roles[name]); } catch (error) { refusal = error.message; }
      if (allowed)
        assert.equal(/not authorized/.test(refusal || ""), false, `${endpoint} refused ${name}: ${refusal}`);
      else
        assert.match(refusal || "", /not authorized for/, `${endpoint} admitted ${name}`);
    }
  }
});

// --- the store ceiling (GW09-D3 structural half) ------------------------------
//
// The reader parsed with a 10 MB limit while persist() enforced nothing, so a
// running receiver wrote past the reader's limit and failed on the next open —
// with the documented remedy, restoring the backup, unable to help, because the
// backup was a copy of the same unopenable file.

test("a file this store writes is provably a file it can read", () => {
  const { DEFAULT_WRITE_CEILING_BYTES, READ_LIMIT_BYTES } = require("../tools/team_intake_store.cjs");
  assert(DEFAULT_WRITE_CEILING_BYTES < READ_LIMIT_BYTES);
  // The invariant is checked where it can still be acted on, not discovered on
  // a later open. This is the configuration that used to be possible.
  assert.throws(
    () => openStore(temporaryStore().file, { writeCeilingBytes: READ_LIMIT_BYTES + 1 }),
    /could not be opened again/,
  );
  for (const bad of [0, -1, 1.5, "32mb", null])
    assert.throws(
      () => openStore(temporaryStore().file, { writeCeilingBytes: bad }),
      /positive byte count/,
    );
});

test("the specimen: a store past the old reader limit really was unopenable", () => {
  // Without this, "the ceiling is now enforced" is a claim about a failure
  // nobody has seen. The old limit is applied to a file that exceeds it, and
  // the refusal is the wedge the decision describes.
  const fixture = temporaryStore();
  const oversize = JSON.stringify({ padding: "x".repeat(11_000_000) });
  assert.throws(
    () => F.strictJsonParse(oversize, { maxBytes: 10_000_000, maxDepth: 18 }),
    /bytes|size|large/i,
    "the old 10 MB reader limit did not refuse an 11 MB document, so the " +
      "wedge this test exists to demonstrate did not exist",
  );
  // The same bytes under the current read limit parse, which is why a store
  // written under any accepted ceiling can always be opened again.
  assert.equal(
    typeof F.strictJsonParse(oversize, {
      maxBytes: require("../tools/team_intake_store.cjs").READ_LIMIT_BYTES,
      maxDepth: 18,
    }),
    "object",
  );
  assert.equal(fs.existsSync(fixture.file), false);
});

test("a write that would breach the ceiling is refused and changes nothing", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "ceiling-001", roles.receiver, scoping());
  const before = fs.readFileSync(fixture.file);
  const digest = crypto.createHash("sha256").update(before).digest("hex");

  // A ceiling below what the store already holds: the next write must refuse.
  // Exercised through the option rather than by generating 32 MB, which tests
  // the same code path and keeps the suite honest about what it ran.
  const tight = openStore(fixture.file, { writeCeilingBytes: before.length + 64 });
  await assert.rejects(
    () => tight.accept(reviewedRaw(true), "ceiling-002", roles.receiver, scoping()),
    /exceeds the .* byte ceiling/,
  );

  // Nothing was written: not a partial record, not a temporary file.
  assert.equal(
    crypto.createHash("sha256").update(fs.readFileSync(fixture.file)).digest("hex"),
    digest,
  );
  assert.deepEqual(tight.pendingWriteDebris(roles.steward), []);
  // And the committed store is still openable, which is the property the
  // ceiling exists to protect.
  const reopened = openStore(fixture.file);
  assert.equal(reopened.read(receipt.inquiry_id, roles.reviewer).inquiry_id, receipt.inquiry_id);

  // The backup is independently openable, because the live file never grew
  // past what can be read. Copying it and opening the copy is the runbook's
  // remedy, and it now works.
  const backup = path.join(fixture.directory, "store.backup.json");
  fs.copyFileSync(fixture.file, backup);
  assert.equal(
    openStore(backup).read(receipt.inquiry_id, roles.reviewer).inquiry_id,
    receipt.inquiry_id,
  );
});

test("the refusal says what to do, and the alternatives it rules out", async () => {
  const fixture = temporaryStore();
  await fixture.store.accept(reviewedRaw(), "ceiling-003", roles.receiver, scoping());
  const tight = openStore(fixture.file, {
    writeCeilingBytes: fs.statSync(fixture.file).size + 32,
  });
  let message = "";
  try {
    await tight.accept(reviewedRaw(true), "ceiling-004", roles.receiver, scoping());
  } catch (error) {
    message = error.message;
  }
  // Archiving does not shrink the file and deletion needs an approved
  // exception, so an operator told only "full" would try two things that
  // cannot work. The refusal names them.
  assert.match(message, /unchanged and still openable/);
  assert.match(message, /rotate/);
  assert.match(message, /archiving does not shrink/);
  assert.match(message, /approved retention exception/);
});

test("capacity reports headroom before the wall rather than at it", async () => {
  const fixture = temporaryStore();
  const empty = fixture.store.capacity(roles.steward);
  assert.equal(empty.used_bytes, 0);
  assert.equal(empty.ceiling_bytes, 32 * 1024 * 1024);
  assert(empty.read_limit_bytes > empty.ceiling_bytes);
  // Sealing (E1) costs base64's 4/3 on top of the measured 2.88, so the
  // pessimistic count is about 72 where it was about 97 before.
  assert(empty.worst_case_inquiries_remaining > 60, "headroom is implausibly small");

  await fixture.store.accept(reviewedRaw(), "ceiling-005", roles.receiver, scoping());
  const used = fixture.store.capacity(roles.steward);
  assert(used.used_bytes > 0);
  assert.equal(used.inquiries, 1);
  assert(used.remaining_bytes < empty.remaining_bytes);
  // Pessimistic on purpose: the figure an operator plans against is the one a
  // 120 KB brief cannot surprise them with.
  assert(used.worst_case_inquiries_remaining <= empty.worst_case_inquiries_remaining);
  assert.throws(() => fixture.store.capacity(roles.reviewer), /not authorized/);
});

test("the adopted retention scope is not narrowed", () => {
  const { RETENTION_POLICY } = require("../tools/team_intake_store.cjs");
  // GW09-D3 adopted the structural half only and says plainly not to narrow
  // this list. Asserted so a later edit has to argue with a test.
  assert.deepEqual(RETENTION_POLICY.deletion_cannot_reach, [
    "RETAINED_ARCHIVE",
    "PRIOR_EXPORTS",
    "PROVIDER_RECORDS",
  ]);
  assert.equal(RETENTION_POLICY.legal_basis, null);
  assert.equal(RETENTION_POLICY.production_period, null);
  assert.equal(RETENTION_POLICY.approved_by, null);
});

// --- one receiver process per store file (adopted stage-1 §1) ----------------

test("a second process cannot start on a store another process is writing", async () => {
  const fixture = temporaryStore();
  await fixture.store.accept(reviewedRaw(), "lock-001", roles.receiver, scoping());
  const lockPath = fixture.store.acquireWriterLock();
  assert.equal(fs.existsSync(lockPath), true);
  const holder = JSON.parse(fs.readFileSync(lockPath, "utf8"));
  assert.equal(holder.pid, process.pid);

  // A genuinely separate process, not a second object in this one: the rule is
  // about processes, so proving it with an in-process call would prove nothing.
  const probe = require("node:child_process").spawnSync(
    process.execPath,
    [
      "-e",
      `const {openStore}=require(${JSON.stringify(path.join(ROOT, "tests/staff_fixture.cjs"))});
       const s=openStore(${JSON.stringify(fixture.file)});
       try { s.acquireWriterLock(); console.log("ACQUIRED"); }
       catch (error) { console.log("REFUSED:" + error.message); }`,
    ],
    { encoding: "utf8" },
  );
  assert.match(probe.stdout, /^REFUSED:/, "a second process took the lock");
  assert.match(probe.stdout, /Another receiver already holds this store/);
  assert.match(probe.stdout, new RegExp("process " + process.pid));
  assert.match(probe.stdout, /Exactly one receiver process per store file/);

  // Released, the same second process starts.
  assert.equal(fixture.store.releaseWriterLock(), true);
  assert.equal(fs.existsSync(lockPath), false);
  const after = require("node:child_process").spawnSync(
    process.execPath,
    [
      "-e",
      `const {openStore}=require(${JSON.stringify(path.join(ROOT, "tests/staff_fixture.cjs"))});
       openStore(${JSON.stringify(fixture.file)}).acquireWriterLock();
       console.log("ACQUIRED");`,
    ],
    { encoding: "utf8" },
  );
  assert.match(after.stdout, /ACQUIRED/);
});

test("a lock left by a dead process does not wedge the next start", async () => {
  const fixture = temporaryStore();
  await fixture.store.accept(reviewedRaw(), "lock-002", roles.receiver, scoping());
  const lockPath = fixture.file + ".writer.lock";

  // A crashed holder: a pid that is gone. Staleness is detected, not assumed,
  // so this reclaims rather than requiring an operator to delete a file.
  fs.writeFileSync(
    lockPath,
    JSON.stringify({ pid: 999999, start_time: "1", acquired_at: "2026-01-01T00:00:00Z" }),
  );
  assert.equal(typeof fixture.store.acquireWriterLock(), "string");
  assert.equal(JSON.parse(fs.readFileSync(lockPath, "utf8")).pid, process.pid);
  fixture.store.releaseWriterLock();

  // A live pid that started at a different time is a reused pid, not the
  // holder. Using this process with a wrong start time is exactly that case.
  fs.writeFileSync(
    lockPath,
    JSON.stringify({ pid: process.pid, start_time: "0", acquired_at: "2026-01-01T00:00:00Z" }),
  );
  assert.equal(typeof fixture.store.acquireWriterLock(), "string");
  fixture.store.releaseWriterLock();

  // An unreadable lock records no live holder and must not block a start.
  fs.writeFileSync(lockPath, "not json at all");
  assert.equal(typeof fixture.store.acquireWriterLock(), "string");
  fixture.store.releaseWriterLock();
});

test("releasing never removes a lock this process does not hold", async () => {
  const fixture = temporaryStore();
  const lockPath = fixture.file + ".writer.lock";
  fixture.store.acquireWriterLock();
  // Someone else's lock, written over ours while we believe we hold it.
  fs.writeFileSync(
    lockPath,
    JSON.stringify({ pid: 424242, start_time: "1", acquired_at: "2026-01-01T00:00:00Z" }),
  );
  assert.equal(fixture.store.releaseWriterLock(), false);
  assert.equal(fs.existsSync(lockPath), true, "released another process's lock");
  assert.equal(JSON.parse(fs.readFileSync(lockPath, "utf8")).pid, 424242);
  fs.rmSync(lockPath, { force: true });
});
