"use strict";
// A synthetic development standard (owner-delegated decision, 2026-09-23):
// development and testing continue before counsel names the real screening
// standard, and a real client's record stays unreachable while it is in force.
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
if (!globalThis.crypto) globalThis.crypto = crypto.webcrypto;
const { SYNTHETIC_STANDARD_PREFIX } = require("../tools/team_intake_store.cjs");
const { scopingBasis } = require("../tools/team_record_basis.cjs");
const { StaffDirectory } = require("../tools/team_staff_directory.cjs");
const { enrolled, mailed, openStore, principalFor } = require("./staff_fixture.cjs");
const I = require("../src/intake.js");

const ROOT = path.resolve(__dirname, "..");
const STANDARD = SYNTHETIC_STANDARD_PREFIX + "2026-09";
const TOKENS = { receiver: "synthstd-receiver-token-01", reviewer: "synthstd-reviewer-token-01" };
const screened = (account) => ({ ...account, screening: { standard: STANDARD, ref: "synthetic-screening-" + account.principal } });
const DIRECTORY = new StaffDirectory([
  screened(enrolled("synthstd-receiver", "carbon-fit", ["INTAKE_RECEIVER"], TOKENS.receiver)),
  screened(enrolled("synthstd-reviewer", "carbon-fit", ["TEAM_REVIEWER"], TOKENS.reviewer)),
]);
const as = (name) => principalFor(DIRECTORY, TOKENS[name]);

function raw() {
  const brief = JSON.parse(fs.readFileSync(path.join(ROOT, "intake/fixtures/existing_method_v1.json"), "utf8"));
  brief.draft_id = "synthstd-" + crypto.randomBytes(4).toString("hex");
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

test("a synthetic standard reaches synthetic records and refuses a real reference", async () => {
  const store = openStore(path.join(fs.mkdtempSync(path.join(os.tmpdir(), "carbon-synthstd-")), "store.json"), { screeningStandard: STANDARD });
  const synthetic = await store.accept(raw(), "synth-001", as("receiver"), scopingBasis({ nda: "synthetic-nda-0001" }), mailed(), "synthetic-ec-0001");
  // Specimen: development continues on synthetic records.
  assert.equal(store.read(synthetic.inquiry_id, as("reviewer")).inquiry_id, synthetic.inquiry_id);
  const realAgreement = await store.accept(raw(), "synth-002", as("receiver"), scopingBasis({ nda: "NDA-2026-0042" }), mailed(), "synthetic-ec-0002");
  assert.throws(() => store.read(realAgreement.inquiry_id, as("reviewer")), /synthetic records only/);
  const realDetermination = await store.accept(raw(), "synth-003", as("receiver"), scopingBasis({ nda: "synthetic-nda-0003" }), mailed(), "EC-DETERMINATION-17");
  assert.throws(() => store.read(realDetermination.inquiry_id, as("reviewer")), /synthetic records only/);
});

test("counsel's standard, once configured, is not restricted to synthetic records", async () => {
  const counsel = "COUNSEL-STANDARD-EXAMPLE";
  const accounts = new StaffDirectory([
    { ...enrolled("counsel-receiver", "carbon-fit", ["INTAKE_RECEIVER"], "counsel-receiver-token-01"), screening: { standard: counsel, ref: "screening-record-1" } },
    { ...enrolled("counsel-reviewer", "carbon-fit", ["TEAM_REVIEWER"], "counsel-reviewer-token-01"), screening: { standard: counsel, ref: "screening-record-2" } },
  ]);
  const store = openStore(path.join(fs.mkdtempSync(path.join(os.tmpdir(), "carbon-synthstd-")), "store.json"), { screeningStandard: counsel });
  const receipt = await store.accept(raw(), "synth-004", principalFor(accounts, "counsel-receiver-token-01"), scopingBasis({ nda: "NDA-2026-0042" }), mailed(), "EC-DETERMINATION-17");
  assert.equal(store.read(receipt.inquiry_id, principalFor(accounts, "counsel-reviewer-token-01")).inquiry_id, receipt.inquiry_id);
});
