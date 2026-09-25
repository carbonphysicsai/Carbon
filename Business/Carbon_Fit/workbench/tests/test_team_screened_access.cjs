"use strict";
// E7: client records are reachable only by people screened under the
// configured standard, and only once a record carries its export-control
// reference. The standard is counsel's and is null until set; a null makes a
// record unreachable, never reachable by default. Each refusal is paired with
// the configuration that succeeds.
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
if (!globalThis.crypto) globalThis.crypto = crypto.webcrypto;
const { StaffDirectory, totp } = require("../tools/team_staff_directory.cjs");
const { createIntakeServer } = require("../tools/team_intake_server.cjs");
const { RELEASE, SCOPING_HEADERS, SCREENING_STANDARD, enrolled, exportRef, mailed, openStore, principalFor, scoping, secretFor } = require("./staff_fixture.cjs");
const I = require("../src/intake.js");

const ROOT = path.resolve(__dirname, "..");
const TOKENS = {
  receiver: "screen-receiver-token-001",
  reviewer: "screen-reviewer-token-001",
  unscreened: "screen-unscreened-token-01",
  elsewhere: "screen-elsewhere-token-001",
  steward: "screen-steward-token-0001",
};
const ACCOUNTS = [
  enrolled("screen-receiver", "carbon-fit", ["INTAKE_RECEIVER"], TOKENS.receiver),
  enrolled("screen-reviewer", "carbon-fit", ["TEAM_REVIEWER"], TOKENS.reviewer),
  enrolled("screen-unscreened", "carbon-fit", ["TEAM_REVIEWER"], TOKENS.unscreened, "ACTIVE", { screened: false }),
  { ...enrolled("screen-elsewhere", "carbon-fit", ["TEAM_REVIEWER"], TOKENS.elsewhere), screening: { standard: "some-other-standard", ref: "synthetic-screening-x" } },
  enrolled("screen-steward", "carbon-fit", ["DATA_STEWARD"], TOKENS.steward),
];
const DIRECTORY = new StaffDirectory(ACCOUNTS);
const as = (name) => principalFor(DIRECTORY, TOKENS[name]);

function raw() {
  const brief = JSON.parse(fs.readFileSync(path.join(ROOT, "intake/fixtures/existing_method_v1.json"), "utf8"));
  brief.draft_id = "screen-" + crypto.randomBytes(4).toString("hex");
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
const storeWith = (screeningStandard) =>
  openStore(path.join(fs.mkdtempSync(path.join(os.tmpdir(), "carbon-screen-")), "store.json"), { screeningStandard });

test("with the screening standard unset, no record's content is reachable by anyone", async () => {
  const store = storeWith(null);
  const receipt = await store.accept(raw(), "screen-001", as("receiver"), scoping(), mailed(), exportRef());
  for (const attempt of [
    () => store.read(receipt.inquiry_id, as("reviewer")),
    () => store.export(receipt.inquiry_id, as("reviewer"), RELEASE),
    () => store.update(receipt.inquiry_id, 1, { assigned_reviewer: "x", queue_state: "UNDER_REVIEW", note: "x" }, as("reviewer")),
    () => store.archive(receipt.inquiry_id, as("steward")),
  ])
    assert.throws(attempt, /screening standard \(counsel's\) is unset/);
  // Metadata that discloses no content still works: the queue, the plan.
  assert.equal(store.search(as("reviewer")).length, 1);
  assert.equal(store.retentionPlan(as("steward")).status, "REFUSED");
  // Specimen: the same record, the same screened account, a configured standard.
  const configured = storeWith(SCREENING_STANDARD);
  const other = await configured.accept(raw(), "screen-002", as("receiver"), scoping(), mailed(), exportRef());
  assert.equal(configured.read(other.inquiry_id, as("reviewer")).inquiry_id, other.inquiry_id);
});

test("an unscreened account, or one screened under another standard, is refused", async () => {
  const store = storeWith(SCREENING_STANDARD);
  const receipt = await store.accept(raw(), "screen-003", as("receiver"), scoping(), mailed(), exportRef());
  assert.throws(() => store.read(receipt.inquiry_id, as("unscreened")), /not screened under the configured standard/);
  assert.throws(() => store.read(receipt.inquiry_id, as("elsewhere")), /not screened under the configured standard/);
  // Specimen: screened under the configured standard.
  assert.ok(store.read(receipt.inquiry_id, as("reviewer")));
  // Changing the standard invalidates the old screenings.
  const changed = openStore(store.filePath, { screeningStandard: "a-newer-standard" });
  assert.throws(() => changed.read(receipt.inquiry_id, as("reviewer")), /not screened under the configured standard/);
});

test("a record without its export-control reference is unreachable until a steward records one", async () => {
  const store = storeWith(SCREENING_STANDARD);
  const receipt = await store.accept(raw(), "screen-004", as("receiver"), scoping(), mailed());
  assert.throws(() => store.read(receipt.inquiry_id, as("reviewer")), /no export-control reference recorded/);
  assert.throws(() => store.recordExportControl(receipt.inquiry_id, "synthetic-ec-0002", as("reviewer")), /not authorized/);
  assert.throws(() => store.recordExportControl(receipt.inquiry_id, "has spaces", as("steward")), /opaque identifier/);
  const recorded = store.recordExportControl(receipt.inquiry_id, "synthetic-ec-0002", as("steward"));
  assert.equal(recorded.ref, "synthetic-ec-0002");
  assert.equal(recorded.recorded_by, "screen-steward");
  // Specimen: now reachable. And the reference is never replaced.
  assert.equal(store.read(receipt.inquiry_id, as("reviewer")).export_control.ref, "synthetic-ec-0002");
  assert.throws(() => store.recordExportControl(receipt.inquiry_id, "synthetic-ec-0003", as("steward")), /already recorded/);
});

test("a record written before E7 carries no reference, and none is invented", async () => {
  const store = storeWith(SCREENING_STANDARD);
  const receipt = await store.accept(raw(), "screen-005", as("receiver"), scoping(), mailed(), exportRef());
  const legacy = JSON.parse(JSON.stringify(store.state));
  delete legacy.inquiries[receipt.inquiry_id].export_control;
  fs.writeFileSync(store.filePath, JSON.stringify(legacy));
  const reopened = openStore(store.filePath);
  assert.deepEqual(reopened.state.inquiries[receipt.inquiry_id].export_control, { ref: null, recorded_by: null, recorded_at: null });
  assert.throws(() => reopened.read(receipt.inquiry_id, as("reviewer")), /no export-control reference recorded/);
});

test("over HTTP, a relay without the reference yields an unreachable record until it is recorded", async () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "carbon-screen-http-"));
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
    const receiver = await session(TOKENS.receiver);
    const reviewer = await session(TOKENS.reviewer);
    const steward = await session(TOKENS.steward);
    const { "x-carbon-export-control-ref": _ref, ...withoutReference } = SCOPING_HEADERS;
    const accepted = await fetch(base + "/private/intake", {
      method: "POST",
      headers: { authorization: receiver, "content-type": "application/json", "idempotency-key": "screen-http-1", ...withoutReference },
      body: raw(),
    });
    const { inquiry_id: id } = await accepted.json();
    assert.equal((await fetch(`${base}/private/intake/${id}`, { headers: { authorization: reviewer } })).status, 403);
    const recorded = await fetch(`${base}/private/intake/${id}/export-control`, {
      method: "POST",
      headers: { authorization: steward, "content-type": "application/json" },
      body: JSON.stringify({ ref: "synthetic-ec-0004" }),
    });
    assert.equal(recorded.status, 200);
    assert.equal((await fetch(`${base}/private/intake/${id}`, { headers: { authorization: reviewer } })).status, 200);
  } finally {
    server.close();
  }
});
