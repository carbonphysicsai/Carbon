"use strict";
// E3: the retention schema. closure_event, active_period and archive_period
// replace production_period; scoping_expiry covers the SCOPING class. The shape
// is approved and every value is counsel's, so every value is null here.
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
if (!globalThis.crypto) globalThis.crypto = crypto.webcrypto;
const { RETENTION_POLICY, RETENTION_VERSION, RETENTION_VERSION_V1, SCOPING_EXPIRY_NOT_APPLICABLE } = require("../tools/team_intake_store.cjs");
const { studyBasis } = require("../tools/team_record_basis.cjs");
const { StaffDirectory } = require("../tools/team_staff_directory.cjs");
const { enrolled, mailed, openStore, principalFor, scoping } = require("./staff_fixture.cjs");
const I = require("../src/intake.js");

const ROOT = path.resolve(__dirname, "..");
const TOKENS = { receiver: "retention-receiver-token-01", reviewer: "retention-reviewer-token-01", steward: "retention-steward-token-01" };
const DIRECTORY = new StaffDirectory([
  enrolled("retention-receiver", "carbon-fit", ["INTAKE_RECEIVER"], TOKENS.receiver),
  enrolled("retention-reviewer", "carbon-fit", ["TEAM_REVIEWER"], TOKENS.reviewer),
  enrolled("retention-steward", "carbon-fit", ["DATA_STEWARD"], TOKENS.steward),
]);
const as = (name) => principalFor(DIRECTORY, TOKENS[name]);
const study = () => studyBasis({ msa: "synthetic-msa-0001", order_form: "synthetic-of-0001" });

function raw() {
  const brief = JSON.parse(fs.readFileSync(path.join(ROOT, "intake/fixtures/existing_method_v1.json"), "utf8"));
  brief.draft_id = "retention-" + crypto.randomBytes(4).toString("hex");
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
const fresh = () => openStore(path.join(fs.mkdtempSync(path.join(os.tmpdir(), "carbon-retention-")), "store.json"));

test("a new record carries the v2 shape, every value null and no production_period", async () => {
  const store = fresh();
  const receipt = await store.accept(raw(), "ret-001", as("receiver"), scoping(), mailed());
  const retention = store.read(receipt.inquiry_id, as("reviewer")).retention;
  assert.equal(retention.schema_version, RETENTION_VERSION);
  assert.equal("production_period" in retention, false);
  assert.deepEqual(retention.closure, { event: null, at: null, recorded_by: null });
  assert.equal(retention.active_period, null);
  assert.equal(retention.archive_period, null);
  assert.equal(retention.scoping_expiry, null);
  assert.equal(retention.legal_basis, "contract:synthetic-nda-0001");
});

test("a STUDY record says the scoping expiry does not apply, which is not the same as unset", async () => {
  const store = fresh();
  const direct = await store.accept(raw(), "ret-002", as("receiver"), study(), mailed());
  assert.equal(store.read(direct.inquiry_id, as("reviewer")).retention.scoping_expiry, SCOPING_EXPIRY_NOT_APPLICABLE);
  // A promoted SCOPING record says the same once it becomes STUDY.
  const promoted = await store.accept(raw(), "ret-003", as("receiver"), scoping(), mailed());
  assert.equal(store.read(promoted.inquiry_id, as("reviewer")).retention.scoping_expiry, null);
  store.attachBasis(promoted.inquiry_id, study(), as("steward"));
  assert.equal(store.read(promoted.inquiry_id, as("reviewer")).retention.scoping_expiry, SCOPING_EXPIRY_NOT_APPLICABLE);
});

test("a v1 retention record migrates, keeping what it recorded and inventing nothing", async () => {
  const store = fresh();
  const receipt = await store.accept(raw(), "ret-004", as("receiver"), scoping(), mailed());
  store.archive(receipt.inquiry_id, as("steward"));
  const archived = store.state.inquiries[receipt.inquiry_id].retention;
  const legacy = JSON.parse(JSON.stringify(store.state));
  const record = legacy.inquiries[receipt.inquiry_id];
  record.retention = {
    schema_version: RETENTION_VERSION_V1,
    policy_id: archived.policy_id,
    disposition: archived.disposition,
    archived_at: archived.archived_at,
    archived_by: archived.archived_by,
    exception_id: null,
    legal_basis: archived.legal_basis,
    production_period: null,
  };
  fs.writeFileSync(store.filePath, JSON.stringify(legacy));
  const migrated = openStore(store.filePath).state.inquiries[receipt.inquiry_id].retention;
  assert.equal(migrated.schema_version, RETENTION_VERSION);
  assert.equal(migrated.migrated_from, RETENTION_VERSION_V1);
  // Carried as recorded: the archive action and who took it.
  assert.equal(migrated.archived_at, archived.archived_at);
  assert.equal(migrated.archived_by, archived.archived_by);
  assert.ok(migrated.archived_by);
  // Not invented: no closure, no periods.
  assert.deepEqual(migrated.closure, { event: null, at: null, recorded_by: null });
  assert.equal(migrated.active_period, null);
  assert.equal(migrated.archive_period, null);
  assert.equal("production_period" in migrated, false);
});

test("a v1 record that carries a production_period is refused rather than reinterpreted", async () => {
  const store = fresh();
  const receipt = await store.accept(raw(), "ret-005", as("receiver"), scoping(), mailed());
  const legacy = JSON.parse(JSON.stringify(store.state));
  legacy.inquiries[receipt.inquiry_id].retention = { schema_version: RETENTION_VERSION_V1, policy_id: "x", disposition: "ARCHIVE_INDEFINITE", archived_at: null, archived_by: null, exception_id: null, production_period: "P1Y" };
  fs.writeFileSync(store.filePath, JSON.stringify(legacy));
  assert.throws(() => openStore(store.filePath), /cannot be split into a closure event and two periods/);
});

test("the policy is frozen with every counsel value null", () => {
  assert.equal(Object.isFrozen(RETENTION_POLICY), true);
  for (const field of ["closure_event", "active_period", "archive_period", "scoping_expiry", "legal_basis", "approved_by"])
    assert.equal(RETENTION_POLICY[field], null, field);
  assert.throws(() => { "use strict"; RETENTION_POLICY.archive_period = "P3Y"; }, TypeError);
});
