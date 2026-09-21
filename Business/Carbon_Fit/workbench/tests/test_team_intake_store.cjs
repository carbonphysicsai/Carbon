"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
if (!globalThis.crypto) globalThis.crypto = crypto.webcrypto;
const I = require("../src/intake.js");
const { DurableIntakeStore } = require("../tools/team_intake_store.cjs");
const ROOT = path.resolve(__dirname, "..");

const roles = {
  receiver: { id: "synthetic-receiver", roles: ["INTAKE_RECEIVER"] },
  reviewer: { id: "synthetic-reviewer", roles: ["TEAM_REVIEWER"] },
  steward: { id: "synthetic-steward", roles: ["DATA_STEWARD"] },
  notifier: { id: "synthetic-notifier", roles: ["NOTIFICATION_OPERATOR"] },
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
    { id: "synthetic-second-reviewer", roles: ["TEAM_REVIEWER"] },
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
