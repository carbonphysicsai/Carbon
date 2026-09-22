"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
if (!globalThis.crypto) globalThis.crypto = crypto.webcrypto;
const I = require("../src/intake.js");
const { DurableIntakeStore, STORE_VERSION } = require("../tools/team_intake_store.cjs");
const ROOT = path.resolve(__dirname, "..");

const { StaffDirectory, StaffPrincipal } = require("../tools/team_staff_directory.cjs");

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
  { principal: "synthetic-receiver", team: TEAM, roles: ["INTAKE_RECEIVER"], token_sha256: digest(TOKENS.receiver), status: "ACTIVE" },
  { principal: "synthetic-reviewer", team: TEAM, roles: ["TEAM_REVIEWER"], token_sha256: digest(TOKENS.reviewer), status: "ACTIVE" },
  { principal: "synthetic-second-reviewer", team: TEAM, roles: ["TEAM_REVIEWER"], token_sha256: digest(TOKENS.second_reviewer), status: "ACTIVE" },
  { principal: "synthetic-steward", team: TEAM, roles: ["DATA_STEWARD"], token_sha256: digest(TOKENS.steward), status: "ACTIVE" },
  { principal: "synthetic-notifier", team: TEAM, roles: ["NOTIFICATION_OPERATOR"], token_sha256: digest(TOKENS.notifier), status: "ACTIVE" },
  {
    principal: "synthetic-foreign",
    team: OTHER_TEAM,
    roles: ["INTAKE_RECEIVER", "TEAM_REVIEWER", "DATA_STEWARD", "NOTIFICATION_OPERATOR"],
    token_sha256: digest(TOKENS.foreign),
    status: "ACTIVE",
  },
]);
const as = (name) => DIRECTORY.authenticate("Bearer " + TOKENS[name]);
const roles = {
  receiver: as("receiver"),
  reviewer: as("reviewer"),
  steward: as("steward"),
  notifier: as("notifier"),
  second_reviewer: as("second_reviewer"),
  foreign: as("foreign"),
};

function reviewedRaw() {
  const brief = JSON.parse(
    fs.readFileSync(path.join(ROOT, "intake/fixtures/existing_method_v1.json"), "utf8"),
  );
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
    store: new DurableIntakeStore(path.join(directory, "store.json")),
  };
}

test("accepted inquiry is durable before receipt and exact response-loss retry deduplicates", async () => {
  const fixture = temporaryStore(), raw = reviewedRaw();
  const first = await fixture.store.accept(raw, "retry-key-001", roles.receiver);
  assert.equal(first.disposition, "ACCEPTED");
  assert.equal(fs.existsSync(fixture.file), true);
  const restarted = new DurableIntakeStore(fixture.file);
  const second = await restarted.accept(raw, "retry-key-001", roles.receiver);
  assert.equal(second.disposition, "DEDUPLICATED");
  assert.equal(Object.keys(restarted.state.inquiries).length, 1);
  assert.equal(Object.keys(restarted.state.outbox).length, 1);
});

test("idempotency conflict and unauthorized access reject without mutation", async () => {
  const fixture = temporaryStore(), raw = reviewedRaw();
  await fixture.store.accept(raw, "retry-key-002", roles.receiver);
  const before = JSON.stringify(fixture.store.state);
  await assert.rejects(
    () => fixture.store.accept(raw + " ", "retry-key-002", roles.receiver),
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
  const receipt = await fixture.store.accept(reviewedRaw(), "retry-key-003", roles.receiver);
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
  const receipt = await fixture.store.accept(reviewedRaw(), "retry-key-004", roles.receiver);
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
  const receipt = await fixture.store.accept(reviewedRaw(), "retry-key-005", roles.receiver);
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
  const receipt = await fixture.store.accept(raw, "retry-key-006", roles.receiver);
  assert.throws(
    () => fixture.store.export(receipt.inquiry_id, roles.receiver),
    /not authorized/,
  );
  const exported = fixture.store.export(receipt.inquiry_id, roles.reviewer);
  assert.equal(exported.raw_json, raw);
  assert.equal(exported.raw_sha256, receipt.raw_sha256);
  assert.equal(exported.team_fields.queue_state, "READY_FOR_REVIEW");
});

test("team assessments are append-only and retain every superseded revision", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "retry-key-007", roles.receiver);
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
  const restarted = new DurableIntakeStore(fixture.file);
  assert.equal(restarted.read(receipt.inquiry_id, roles.reviewer).assessments.length, 2);
});

test("a v1 store migrates without inventing a history it never retained", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "retry-key-008", roles.receiver);
  const legacy = JSON.parse(fs.readFileSync(fixture.file, "utf8"));
  legacy.schema_version = "carbon.private-team-intake.store.v1";
  for (const record of Object.values(legacy.inquiries)) {
    record.version = 4;
    delete record.assessments;
    delete record.history_origin;
  }
  fs.writeFileSync(fixture.file, JSON.stringify(legacy, null, 2) + "\n");
  const migrated = new DurableIntakeStore(fixture.file);
  const record = migrated.read(receipt.inquiry_id, roles.reviewer);
  assert.deepEqual(record.assessments, []);
  assert.equal(record.history_origin, "MIGRATED_V1_NO_RETAINED_HISTORY");
  assert.equal(record.version, 4);
});

test("a native store whose retained history was edited is refused", async () => {
  const fixture = temporaryStore();
  await fixture.store.accept(reviewedRaw(), "retry-key-009", roles.receiver);
  const tampered = JSON.parse(fs.readFileSync(fixture.file, "utf8"));
  for (const record of Object.values(tampered.inquiries)) record.version = 9;
  fs.writeFileSync(fixture.file, JSON.stringify(tampered, null, 2) + "\n");
  assert.throws(() => new DurableIntakeStore(fixture.file), /does not match the record version/);
});

test("the queued notification carries a minimal summary and no client content", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "retry-key-010", roles.receiver);
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
  const receipt = await fixture.store.accept(reviewedRaw(), "retry-key-011", roles.receiver);
  const eventId = "notify-" + receipt.inquiry_id;
  const attempted = await fixture.store.processOutbox(eventId, null, roles.notifier);
  assert.equal(attempted.status, "PENDING");
  assert.equal(attempted.attempts, 1);
  assert.match(attempted.last_error, /No notification transport is configured/);
  const retried = await fixture.store.processOutbox(eventId, null, roles.notifier);
  assert.equal(retried.attempts, 2);
  assert.equal(retried.status, "PENDING");
  // The inquiry survives every failed notification attempt.
  assert.equal(fixture.store.read(receipt.inquiry_id, roles.reviewer).lifecycle, "ACTIVE");
});

test("a configured destination is recorded without opening any connection", async () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "carbon-team-intake-"));
  const store = new DurableIntakeStore(path.join(directory, "store.json"), {
    destination: "Hello@carbonphysics.ai",
  });
  const receipt = await store.accept(reviewedRaw(), "retry-key-012", roles.receiver);
  assert.equal(store.listOutbox(roles.notifier)[0].destination, "Hello@carbonphysics.ai");
  assert.equal(store.listOutbox(roles.notifier)[0].status, "PENDING");
  assert.equal(store.read(receipt.inquiry_id, roles.reviewer).lifecycle, "ACTIVE");
});

test("a storage failure returns no receipt and stores no partial inquiry", async () => {
  const fixture = temporaryStore();
  fs.chmodSync(fixture.directory, 0o500);
  try {
    await assert.rejects(() =>
      fixture.store.accept(reviewedRaw(), "retry-key-013", roles.receiver),
    );
  } finally {
    fs.chmodSync(fixture.directory, 0o700);
  }
  assert.equal(fs.existsSync(fixture.file), false);
  assert.deepEqual(Object.keys(fixture.store.state.inquiries), []);
  // The same key succeeds once storage recovers; no phantom record blocks it.
  const receipt = await fixture.store.accept(reviewedRaw(), "retry-key-013", roles.receiver);
  assert.equal(receipt.disposition, "ACCEPTED");
  assert.equal(fs.readdirSync(fixture.directory).filter((n) => n.includes(".tmp-")).length, 0);
});

test("completing a notification keeps writes made during the await window", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "retry-key-014", roles.receiver);
  const other = JSON.parse(reviewedRaw());
  other.brief.draft_id = "synthetic-second-inquiry";
  const second = await fixture.store.accept(
    JSON.stringify(other),
    "retry-key-015",
    roles.receiver,
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
  const restarted = new DurableIntakeStore(fixture.file);
  assert.equal(restarted.read(receipt.inquiry_id, roles.reviewer).team_fields.note, "Filed mid-delivery.");
  assert.equal(restarted.state.outbox["notify-" + receipt.inquiry_id].status, "DELIVERED");
  assert.equal(restarted.state.inquiries[second.inquiry_id], undefined);
});

test("a transient flush failure does not block every later write", async () => {
  const fixture = temporaryStore();
  await fixture.store.accept(reviewedRaw(), "retry-key-016", roles.receiver);
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
  assert.equal(new DurableIntakeStore(fixture.file).read(inquiryId, roles.reviewer).team_fields.note, "recovered");
});

test("a delivery in flight cannot resurrect an inquiry deleted during its await", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "retry-key-017", roles.receiver);
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
  const restarted = new DurableIntakeStore(fixture.file);
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
  const receipt = await fixture.store.accept(reviewedRaw(), "retention-001", roles.receiver);
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
    () => fixture.store.export(receipt.inquiry_id, roles.reviewer),
    /requires an explicit archive request/,
  );
  assert.equal(
    fixture.store.export(receipt.inquiry_id, roles.reviewer, { includeArchived: true }).raw_sha256,
    receipt.raw_sha256,
  );

  const restored = fixture.store.restore(receipt.inquiry_id, roles.steward);
  assert.equal(restored.lifecycle, "ACTIVE");
  assert.equal(restored.retention.restored_by, "synthetic-steward");
  assert.equal(fixture.store.search(roles.reviewer).length, 1);
  assert.equal(new DurableIntakeStore(fixture.file).read(receipt.inquiry_id, roles.reviewer).lifecycle, "ACTIVE");
});

test("a deletion exception is named, reasoned and bounded", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "retention-002", roles.receiver);

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
  const receipt = await fixture.store.accept(reviewedRaw(), "retention-003", roles.receiver);
  approveDeletion(fixture.store, receipt.inquiry_id);
  const tombstone = fixture.store.delete(receipt.inquiry_id, roles.steward);

  assert.equal(tombstone.approved_by, "Ryan Bequette");
  assert.deepEqual(tombstone.reached, ["ACTIVE_RECORD", "ACTIVE_INDEX", "PENDING_NOTIFICATIONS"]);
  // Promising removal from retained archives, prior exports or a provider would
  // be a promise this store cannot keep, so the tombstone says so instead.
  assert.deepEqual(tombstone.did_not_reach, ["RETAINED_ARCHIVE", "PRIOR_EXPORTS", "PROVIDER_RECORDS"]);
  assert.equal(JSON.stringify(fixture.store.state).includes("Compare the reported baseline"), false);
  assert.equal(new DurableIntakeStore(fixture.file).state.tombstones[receipt.inquiry_id].did_not_reach.length, 3);
});

test("a v2 store migrates to versioned retention without back-dating an archive", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "retention-004", roles.receiver);
  const legacy = JSON.parse(fs.readFileSync(fixture.file, "utf8"));
  legacy.schema_version = "carbon.private-team-intake.store.v2";
  delete legacy.exceptions;
  for (const record of Object.values(legacy.inquiries))
    record.retention = { policy: "LOCAL_SYNTHETIC_DELETE_ON_REQUEST", production_period: null };
  fs.writeFileSync(fixture.file, JSON.stringify(legacy, null, 2) + "\n");

  const migrated = new DurableIntakeStore(fixture.file);
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
  return new NonConforming(file);
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
      assert.throws(() => store.export(receipt.inquiry_id, roles.reviewer), /explicit archive request/);
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
    const receipt = await control.store.accept(reviewedRaw(), "control", roles.receiver);
    await guarantee.check(control.store, receipt);

    const subject = temporaryStore();
    const other = await subject.store.accept(reviewedRaw(), "variant", roles.receiver);
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
  const receipt = await fixture.store.accept(reviewedRaw(), "retention-005", roles.receiver);
  const forged = JSON.parse(fs.readFileSync(fixture.file, "utf8"));
  const record = forged.inquiries[receipt.inquiry_id];
  record.retention = { ...record.retention, archived_at: record.accepted_at, archived_by: "migration" };
  fs.writeFileSync(fixture.file, JSON.stringify(forged, null, 2) + "\n");

  const reopened = new DurableIntakeStore(fixture.file);
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
    const receipt = await fixture.store.accept(reviewedRaw(), "meta", roles.receiver);
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
  assert.throws(() => DIRECTORY.authenticate("Bearer not-a-real-token-000000"), /Authentication failed/);
  // A missing credential and a wrong one are refused identically.
  assert.throws(() => DIRECTORY.authenticate(""), /Authentication failed/);
  assert.throws(() => DIRECTORY.authenticate(null), /Authentication failed/);

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
  const ok = { principal: "a-steward", team: TEAM, roles: ["DATA_STEWARD"], token_sha256: digest("t-1"), status: "ACTIVE" };
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
  // A disabled account holds its roles and still cannot act.
  const disabled = new StaffDirectory([{ ...ok, status: "DISABLED" }]);
  assert.throws(() => disabled.authenticate("Bearer t-1"), /Authentication failed/);
});

test("every store endpoint refuses a caller that was never authenticated", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "role-001", roles.receiver);
  approveDeletion(fixture.store, receipt.inquiry_id);

  // Enumerated from the prototype rather than listed by hand, so an endpoint
  // added later is covered without anyone remembering to add it here. A list
  // maintained by hand is the thing that goes stale.
  const exempt = new Set(["constructor", "persist"]);
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
  const receipt = await fixture.store.accept(reviewedRaw(), "role-002", roles.receiver);
  const missing = "inquiry-000000000000000";

  // The foreign principal holds every role this receiver defines. Role checks
  // alone would let all of this through.
  for (const attempt of [
    (p) => fixture.store.read(receipt.inquiry_id, p),
    (p) => fixture.store.export(receipt.inquiry_id, p),
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
  const receipt = await fixture.store.accept(reviewedRaw(), "role-003", roles.receiver);
  const legacy = JSON.parse(fs.readFileSync(fixture.file, "utf8"));
  legacy.schema_version = "carbon.private-team-intake.store.v2";
  delete legacy.exceptions;
  for (const record of Object.values(legacy.inquiries)) delete record.owner_team;
  fs.writeFileSync(fixture.file, JSON.stringify(legacy, null, 2) + "\n");

  const migrated = new DurableIntakeStore(fixture.file);
  // Not a guessed team, and not a team at all: the placeholder is upper case
  // and a directory team cannot be, so no account can ever match it.
  assert.equal(migrated.state.inquiries[receipt.inquiry_id].owner_team, "MIGRATED_TEAM_UNASSIGNED");
  // Principals that hold the read role, so a refusal here is about ownership.
  for (const principal of [roles.reviewer, roles.receiver, roles.foreign])
    assert.throws(() => migrated.read(receipt.inquiry_id, principal), /Inquiry not found/);
  assert.throws(() => new StaffDirectory([{
    principal: "a-steward", team: "MIGRATED_TEAM_UNASSIGNED", roles: ["DATA_STEWARD"],
    token_sha256: digest("t-3"), status: "ACTIVE",
  }]), /named owning team/);
});

// --- restart and storage-failure recovery ------------------------------------

test("a store interrupted before its rename restarts on the last good state", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "recover-001", roles.receiver);
  fixture.store.update(
    receipt.inquiry_id, 1,
    { assigned_reviewer: "Ryan", queue_state: "UNDER_REVIEW", note: "Committed." },
    roles.reviewer,
  );

  // A process killed between the write and the rename. The replacement bytes
  // exist and the directory entry never moved, so the committed state is the
  // one before them — including a revision the dead process was mid-way
  // through, which must not be half-applied.
  const doomed = JSON.parse(fs.readFileSync(fixture.file, "utf8"));
  doomed.inquiries[receipt.inquiry_id].team_fields.note = "Never committed.";
  doomed.inquiries[receipt.inquiry_id].version = 99;
  fs.writeFileSync(fixture.file + ".tmp-" + process.pid + "-interrupted", JSON.stringify(doomed));

  const restarted = new DurableIntakeStore(fixture.file);
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
  assert.equal(new DurableIntakeStore(fixture.file).read(receipt.inquiry_id, roles.reviewer).version, 3);
});

test("a damaged store refuses to open rather than starting empty", async () => {
  const fixture = temporaryStore();
  const receipt = await fixture.store.accept(reviewedRaw(), "recover-002", roles.receiver);
  const good = fs.readFileSync(fixture.file, "utf8");

  // Starting empty is the dangerous recovery: every accepted inquiry silently
  // disappears, the idempotency index goes with it, and a client retry is
  // accepted a second time as a new record. Each of these must refuse.
  for (const [name, bytes] of [
    ["truncated", good.slice(0, Math.floor(good.length / 2))],
    ["empty", ""],
    ["not json", "recovered from backup?"],
    ["json but not a store", JSON.stringify({ inquiries: {} })],
    ["unknown schema", good.replace(STORE_VERSION, "carbon.private-team-intake.store.v9")],
  ]) {
    fs.writeFileSync(fixture.file, bytes);
    assert.throws(() => new DurableIntakeStore(fixture.file), Error, name);
  }

  // The operator restores the file; nothing about the refusals damaged it.
  fs.writeFileSync(fixture.file, good);
  const reopened = new DurableIntakeStore(fixture.file);
  assert.equal(reopened.read(receipt.inquiry_id, roles.reviewer).inquiry_id, receipt.inquiry_id);
  // The idempotency index survived, so the client's retry still deduplicates.
  assert.equal(
    (await reopened.accept(reviewedRaw(), "recover-002", roles.receiver)).disposition,
    "DEDUPLICATED",
  );
});

test("a failed write leaves the previous committed state readable", async () => {
  const fixture = temporaryStore();
  const first = await fixture.store.accept(reviewedRaw(), "recover-003", roles.receiver);
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
  const reopened = new DurableIntakeStore(fixture.file);
  assert.deepEqual(Object.keys(reopened.state.tombstones), []);
  assert.equal(reopened.read(first.inquiry_id, roles.reviewer).inquiry_id, first.inquiry_id);
  assert.deepEqual(reopened.pendingWriteDebris(roles.steward), []);
  // The approved exception is still on record, so the retry needs no re-approval.
  assert.equal(
    reopened.delete(first.inquiry_id, roles.steward).approved_by,
    "Ryan Bequette",
  );
});
