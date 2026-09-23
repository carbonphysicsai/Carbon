"use strict";
// A record-level hold (owner-delegated decision, 2026-09-23). While a hold is
// active, no path destroys the record: not the scheduled job, not an approved
// deletion. Whether a hold is legally required is counsel's question; this
// makes the answer enforceable. Each refusal is paired with the same action
// succeeding once the hold is lifted.
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
if (!globalThis.crypto) globalThis.crypto = crypto.webcrypto;
const { StaffDirectory, totp } = require("../tools/team_staff_directory.cjs");
const { createIntakeServer } = require("../tools/team_intake_server.cjs");
const { enrolled, exportRef, mailed, openStore, principalFor, scoping, secretFor } = require("./staff_fixture.cjs");
const I = require("../src/intake.js");

const ROOT = path.resolve(__dirname, "..");
const TOKENS = { receiver: "hold-receiver-token-00001", reviewer: "hold-reviewer-token-00001", steward: "hold-steward-token-000001" };
const ACCOUNTS = [
  enrolled("hold-receiver", "carbon-fit", ["INTAKE_RECEIVER"], TOKENS.receiver),
  enrolled("hold-reviewer", "carbon-fit", ["TEAM_REVIEWER"], TOKENS.reviewer),
  enrolled("hold-steward", "carbon-fit", ["DATA_STEWARD"], TOKENS.steward),
];
const DIRECTORY = new StaffDirectory(ACCOUNTS);
const as = (name) => principalFor(DIRECTORY, TOKENS[name]);
const DAY = 86_400_000;
const START = Date.UTC(2027, 0, 1);
const VALUES = { closure_events: ["SYNTHETIC_DELIVERABLE_ACCEPTED"], active_period: "P10D", archive_period: "P20D", scoping_expiry: "P5D" };

function raw() {
  const brief = JSON.parse(fs.readFileSync(path.join(ROOT, "intake/fixtures/existing_method_v1.json"), "utf8"));
  brief.draft_id = "hold-" + crypto.randomBytes(4).toString("hex");
  return JSON.stringify({
    schema_version: I.REVIEW_VERSION,
    brief,
    pilot: { label: "Draft pilot for Carbon review", ...Object.fromEntries(I.PILOT_FIELDS.map((f) => [f, ""])), bounded_first_pilot: "Synthetic." },
    field_provenance: [...I.TEXT_FIELDS, ...I.QUANTITY_FIELDS, ...I.PILOT_FIELDS.map((f) => "pilot." + f)].map((field) => ({ field, origin: "UNKNOWN", suggestion_id: null })),
    accepted_suggestions: [],
    unresolved_assumptions: [],
    ai_guidance: { enabled: false, provider: null, guidance_version: I.GUIDANCE_VERSION, notice_version: null, consented_at: null, cleared_locally: false },
    sharing: { include_conversation: false, conversation: [] },
    contact: { name: "", email: "", organization: "" },
    local_scope: I.REVIEW_SCOPE,
  });
}

function world() {
  let now = START;
  const store = openStore(path.join(fs.mkdtempSync(path.join(os.tmpdir(), "carbon-hold-")), "store.json"), { retentionValues: VALUES, clock: () => now });
  return { store, advance: (ms) => { now += ms; } };
}

test("the scheduled job lists a held record and never destroys it; lifted, it does", async () => {
  const w = world();
  const receipt = await w.store.accept(raw(), "hold-001", as("receiver"), scoping(), mailed(), exportRef());
  const hold = w.store.placeHold(receipt.inquiry_id, { reason: "Synthetic preservation request" }, as("steward"));
  assert.equal(hold.active, true);
  w.advance(30 * DAY); // well past the synthetic scoping expiry
  const plan = w.store.retentionPlan(as("steward"));
  assert.deepEqual(plan.held, [{ inquiry_id: receipt.inquiry_id, hold_id: hold.hold_id }]);
  assert.deepEqual(plan.would_apply, []);
  assert.deepEqual(w.store.runScheduledDestruction(as("steward")).applied, []);
  assert.equal(w.store.read(receipt.inquiry_id, as("reviewer")).lifecycle, "ACTIVE");
  // Specimen: lifted, the same record is destroyed on the next run.
  w.store.liftHold(receipt.inquiry_id, { reason: "Synthetic request withdrawn" }, as("steward"));
  const run = w.store.runScheduledDestruction(as("steward"));
  assert.deepEqual(run.applied.map((item) => item.inquiry_id), [receipt.inquiry_id]);
});

test("an approved deletion is refused while a hold is active", async () => {
  const w = world();
  const receipt = await w.store.accept(raw(), "hold-002", as("receiver"), scoping(), mailed(), exportRef());
  w.store.approveDeletionException(receipt.inquiry_id, { approver: "Synthetic approver", reason: "Synthetic fixture deletion for the hold test" }, as("steward"));
  w.store.placeHold(receipt.inquiry_id, { reason: "Synthetic preservation request" }, as("steward"));
  assert.throws(() => w.store.delete(receipt.inquiry_id, as("steward")), /under hold/);
  // The key was not destroyed on the way to that refusal.
  const keyId = w.store.state.inquiries[receipt.inquiry_id].archive_key_id;
  assert.equal(w.store.keyring.status(keyId), "LIVE");
  // Specimen: lifted, the approved deletion proceeds.
  w.store.liftHold(receipt.inquiry_id, { reason: "Synthetic request withdrawn" }, as("steward"));
  assert.equal(w.store.delete(receipt.inquiry_id, as("steward")).archive_key, "DESTROYED");
});

test("holds are steward-only, need a reason, and keep an append-only history", async () => {
  const w = world();
  const receipt = await w.store.accept(raw(), "hold-003", as("receiver"), scoping(), mailed(), exportRef());
  assert.throws(() => w.store.placeHold(receipt.inquiry_id, { reason: "x" }, as("steward")), /states its reason/);
  assert.throws(() => w.store.placeHold(receipt.inquiry_id, { reason: "Synthetic" }, as("reviewer")), /not authorized/);
  assert.throws(() => w.store.liftHold(receipt.inquiry_id, { reason: "Synthetic" }, as("steward")), /not under hold/);
  w.store.placeHold(receipt.inquiry_id, { reason: "First synthetic hold" }, as("steward"));
  assert.throws(() => w.store.placeHold(receipt.inquiry_id, { reason: "Again" }, as("steward")), /already under hold/);
  w.store.liftHold(receipt.inquiry_id, { reason: "First lifted" }, as("steward"));
  const second = w.store.placeHold(receipt.inquiry_id, { reason: "Second synthetic hold" }, as("steward"));
  assert.deepEqual(second.history.map((entry) => entry.event), ["PLACED", "LIFTED", "PLACED"]);
  assert.deepEqual(second.history.map((entry) => entry.seq), [1, 2, 3]);
});

test("over HTTP, only a data steward places or lifts a hold", async () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "carbon-hold-http-"));
  const store = openStore(path.join(directory, "store.json"));
  const receipt = await store.accept(raw(), "hold-http", as("receiver"), scoping(), mailed(), exportRef());
  const server = createIntakeServer({ store, users: ACCOUNTS });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  const session = async (token) => {
    const opened = await fetch(base + "/private/session", {
      method: "POST",
      headers: { authorization: "Bearer " + token, "content-type": "application/json" },
      body: JSON.stringify({ code: totp(secretFor(token), Date.now()) }),
    });
    return "Bearer " + (await opened.json()).session_token;
  };
  const call = (who, action) =>
    fetch(`${base}/private/intake/${receipt.inquiry_id}/hold/${action}`, {
      method: "POST",
      headers: { authorization: who, "content-type": "application/json" },
      body: JSON.stringify({ reason: "Synthetic hold over HTTP" }),
    });
  try {
    assert.equal((await call(await session(TOKENS.reviewer), "place")).status, 403);
    const steward = await session(TOKENS.steward);
    assert.equal((await call(steward, "place")).status, 200);
    assert.equal((await call(steward, "lift")).status, 200);
  } finally {
    server.close();
  }
});
