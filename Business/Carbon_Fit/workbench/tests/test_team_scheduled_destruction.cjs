"use strict";
// E2: the scheduled destruction job. The mechanism is approved; the values are
// counsel's and are operator configuration. With any value null the job does
// not run: it records the refusal and names what is missing. It never skips a
// record silently and never deletes on a guess. The durations below are
// synthetic test inputs chosen for arithmetic, not proposed values.
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
if (!globalThis.crypto) globalThis.crypto = crypto.webcrypto;
const { retentionValuesFrom } = require("../tools/team_intake_store.cjs");
const { studyBasis } = require("../tools/team_record_basis.cjs");
const { StaffDirectory, totp } = require("../tools/team_staff_directory.cjs");
const { createIntakeServer } = require("../tools/team_intake_server.cjs");
const { enrolled, keyringFor, mailed, openStore, principalFor, scoping, secretFor } = require("./staff_fixture.cjs");
const I = require("../src/intake.js");

const ROOT = path.resolve(__dirname, "..");
const TOKENS = { receiver: "schedule-receiver-token-1", reviewer: "schedule-reviewer-token-1", steward: "schedule-steward-token-01" };
const ACCOUNTS = [
  enrolled("schedule-receiver", "carbon-fit", ["INTAKE_RECEIVER"], TOKENS.receiver),
  enrolled("schedule-reviewer", "carbon-fit", ["TEAM_REVIEWER"], TOKENS.reviewer),
  enrolled("schedule-steward", "carbon-fit", ["DATA_STEWARD"], TOKENS.steward),
];
const DIRECTORY = new StaffDirectory(ACCOUNTS);
const as = (name) => principalFor(DIRECTORY, TOKENS[name]);
const study = () => studyBasis({ msa: "synthetic-msa-0001", order_form: "synthetic-of-0001" });
const DAY = 86_400_000;
const START = Date.UTC(2027, 0, 1);
// Synthetic, for arithmetic only.
const COMPLETE = { closure_events: ["SYNTHETIC_DELIVERABLE_ACCEPTED"], active_period: "P10D", archive_period: "P20D", scoping_expiry: "P5D" };

function raw() {
  const brief = JSON.parse(fs.readFileSync(path.join(ROOT, "intake/fixtures/existing_method_v1.json"), "utf8"));
  brief.draft_id = "schedule-" + crypto.randomBytes(4).toString("hex");
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

function world(retentionValues) {
  let now = START;
  const file = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "carbon-schedule-")), "store.json");
  const store = openStore(file, { retentionValues, clock: () => now });
  return { store, file, advance: (ms) => { now += ms; }, now: () => now };
}

test("with no values the job refuses, names every missing value and touches nothing", async () => {
  const w = world(null);
  const receipt = await w.store.accept(raw(), "sched-001", as("receiver"), scoping(), mailed());
  w.advance(10_000 * DAY); // long after any plausible expiry
  const plan = w.store.retentionPlan(as("steward"));
  assert.equal(plan.status, "REFUSED");
  assert.deepEqual(plan.missing_values, ["closure_events", "active_period", "archive_period", "scoping_expiry"]);
  // With no period there is nothing to compute: not "keep", not "delete".
  assert.deepEqual(plan.would_apply, []);
  const run = w.store.runScheduledDestruction(as("steward"));
  assert.equal(run.status, "REFUSED");
  assert.deepEqual(run.applied, []);
  // The record is untouched and still readable.
  assert.equal(w.store.read(receipt.inquiry_id, as("reviewer")).lifecycle, "ACTIVE");
  // And the refusal is recorded, so a job that did nothing is not silent.
  assert.equal(w.store.state.retention_runs.length, 1);
  assert.equal(w.store.state.retention_runs[0].status, "REFUSED");
});

test("with some values set the job still refuses, though the plan shows what they would do", async () => {
  const w = world({ closure_events: null, active_period: null, archive_period: null, scoping_expiry: "P5D" });
  const receipt = await w.store.accept(raw(), "sched-002", as("receiver"), scoping(), mailed());
  w.advance(6 * DAY);
  const plan = w.store.retentionPlan(as("steward"));
  assert.equal(plan.status, "REFUSED");
  assert.deepEqual(plan.missing_values, ["closure_events", "active_period", "archive_period"]);
  assert.deepEqual(plan.would_apply, [{ inquiry_id: receipt.inquiry_id, action: "DESTROY", reason: "SCOPING_EXPIRY" }]);
  assert.deepEqual(w.store.runScheduledDestruction(as("steward")).applied, []);
  assert.equal(w.store.read(receipt.inquiry_id, as("reviewer")).lifecycle, "ACTIVE");
});

test("with every value set, each record is handled when it is due and not before", async () => {
  const w = world(COMPLETE);
  const expiring = await w.store.accept(raw(), "sched-003", as("receiver"), scoping(), mailed());
  w.advance(3 * DAY);
  const fresh = await w.store.accept(raw(), "sched-004", as("receiver"), scoping(), mailed());
  const open = await w.store.accept(raw(), "sched-005", as("receiver"), study(), mailed());
  const closed = await w.store.accept(raw(), "sched-006", as("receiver"), study(), mailed());
  w.store.recordClosure(closed.inquiry_id, { event: "SYNTHETIC_DELIVERABLE_ACCEPTED", at: new Date(w.now()).toISOString() }, as("steward"));
  const keyId = w.store.state.inquiries[expiring.inquiry_id].archive_key_id;

  // Day 3: nothing is due yet.
  assert.deepEqual(w.store.runScheduledDestruction(as("steward")).applied, []);
  // Day 6: the first SCOPING record has passed its expiry; the second has not.
  w.advance(3 * DAY);
  const first = w.store.runScheduledDestruction(as("steward"));
  assert.equal(first.status, "READY");
  assert.deepEqual(first.applied, [{ inquiry_id: expiring.inquiry_id, action: "DESTROY", reason: "SCOPING_EXPIRY" }]);
  const tombstone = w.store.state.tombstones[expiring.inquiry_id];
  assert.equal(tombstone.status, "DESTROYED_BY_SCHEDULE");
  assert.equal(tombstone.archive_key, "DESTROYED");
  assert.equal(keyringFor(w.file).status(keyId), "DESTROYED");
  assert.equal(w.store.read(fresh.inquiry_id, as("reviewer")).lifecycle, "ACTIVE");
  // Day 14: the closed study's active period has ended, so it is archived.
  w.advance(8 * DAY);
  const second = w.store.runScheduledDestruction(as("steward"));
  assert.ok(second.applied.some((item) => item.inquiry_id === closed.inquiry_id && item.action === "ARCHIVE"));
  assert.equal(w.store.state.inquiries[closed.inquiry_id].lifecycle, "ARCHIVED");
  // Day 24: its archive period has ended, so it is destroyed.
  w.advance(10 * DAY);
  const third = w.store.runScheduledDestruction(as("steward"));
  assert.ok(third.applied.some((item) => item.inquiry_id === closed.inquiry_id && item.action === "DESTROY"));
  // A study that never closed is kept throughout: closure starts every clock.
  assert.equal(w.store.read(open.inquiry_id, as("reviewer")).lifecycle, "ACTIVE");
  assert.equal(w.store.state.retention_runs.length, 4);
});

test("a closure needs a configured event, a STUDY record and a time that has passed", async () => {
  const unset = world(null);
  const a = await unset.store.accept(raw(), "sched-007", as("receiver"), study(), mailed());
  assert.throws(
    () => unset.store.recordClosure(a.inquiry_id, { event: "SYNTHETIC_DELIVERABLE_ACCEPTED", at: new Date(START).toISOString() }, as("steward")),
    /closure_event is counsel's and is unset/,
  );
  const set = world(COMPLETE);
  const b = await set.store.accept(raw(), "sched-008", as("receiver"), study(), mailed());
  const s = await set.store.accept(raw(), "sched-009", as("receiver"), scoping(), mailed());
  const at = new Date(START).toISOString();
  assert.throws(() => set.store.recordClosure(b.inquiry_id, { event: "INVENTED_EVENT", at }, as("steward")), /Not a configured closure event/);
  assert.throws(() => set.store.recordClosure(s.inquiry_id, { event: "SYNTHETIC_DELIVERABLE_ACCEPTED", at }, as("steward")), /Only a STUDY record closes/);
  assert.throws(() => set.store.recordClosure(b.inquiry_id, { event: "SYNTHETIC_DELIVERABLE_ACCEPTED", at: new Date(START + DAY).toISOString() }, as("steward")), /has passed/);
  assert.throws(() => set.store.recordClosure(b.inquiry_id, { event: "SYNTHETIC_DELIVERABLE_ACCEPTED", at }, as("reviewer")), /not authorized/);
  // Specimen: the configured event, on a STUDY record, is recorded once.
  assert.equal(set.store.recordClosure(b.inquiry_id, { event: "SYNTHETIC_DELIVERABLE_ACCEPTED", at }, as("steward")).event, "SYNTHETIC_DELIVERABLE_ACCEPTED");
  assert.throws(() => set.store.recordClosure(b.inquiry_id, { event: "SYNTHETIC_DELIVERABLE_ACCEPTED", at }, as("steward")), /already recorded/);
});

test("a record whose receipt time is unknown stops the job rather than being guessed at", async () => {
  const w = world(COMPLETE);
  const receipt = await w.store.accept(raw(), "sched-010", as("receiver"), scoping(), mailed());
  const legacy = JSON.parse(JSON.stringify(w.store.state));
  delete legacy.inquiries[receipt.inquiry_id].received_at;
  legacy.inquiries[receipt.inquiry_id].basis_history = [];
  fs.writeFileSync(w.file, JSON.stringify(legacy));
  const reopened = openStore(w.file, { retentionValues: COMPLETE, clock: () => START + 100 * DAY });
  const run = reopened.runScheduledDestruction(as("steward"));
  assert.equal(run.status, "REFUSED");
  assert.deepEqual(run.blockers, [{ inquiry_id: receipt.inquiry_id, reason: "RECEIPT_TIME_UNKNOWN" }]);
  assert.equal(reopened.read(receipt.inquiry_id, as("reviewer")).lifecycle, "ACTIVE");
});

test("retention values are validated: durations, event names and exactly the four fields", () => {
  assert.equal(retentionValuesFrom(null), null);
  assert.throws(() => retentionValuesFrom({ ...COMPLETE, extra: 1 }), /carry exactly/);
  assert.throws(() => retentionValuesFrom({ ...COMPLETE, active_period: "6 months" }), /ISO-8601 duration/);
  assert.throws(() => retentionValuesFrom({ ...COMPLETE, active_period: "P" }), /ISO-8601 duration/);
  assert.throws(() => retentionValuesFrom({ ...COMPLETE, closure_events: [] }), /closure_events/);
  // Specimen: the complete synthetic set is accepted and frozen.
  assert.equal(Object.isFrozen(retentionValuesFrom(COMPLETE)), true);
});

test("over HTTP, only a data steward sees the plan or runs the job", async () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "carbon-schedule-http-"));
  const store = openStore(path.join(directory, "store.json"));
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
  try {
    const steward = await session(TOKENS.steward);
    const reviewer = await session(TOKENS.reviewer);
    assert.equal((await fetch(base + "/private/retention/plan", { headers: { authorization: reviewer } })).status, 403);
    assert.equal((await fetch(base + "/private/retention/run", { method: "POST", headers: { authorization: reviewer } })).status, 403);
    const plan = await fetch(base + "/private/retention/plan", { headers: { authorization: steward } });
    assert.equal(plan.status, 200);
    assert.equal((await plan.json()).status, "REFUSED");
    const run = await fetch(base + "/private/retention/run", { method: "POST", headers: { authorization: steward } });
    assert.equal((await run.json()).status, "REFUSED");
  } finally {
    server.close();
  }
});
