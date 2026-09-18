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
