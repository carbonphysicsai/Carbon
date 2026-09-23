"use strict";
// E4: record class and a required agreement reference, enforced at
// construction. Each refusal is paired with the construction that succeeds.
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
if (!globalThis.crypto) globalThis.crypto = crypto.webcrypto;
const { RecordBasis, basisFromHeaders, isRecordBasis, scopingBasis, studyBasis } = require("../tools/team_record_basis.cjs");
const { StaffDirectory, totp } = require("../tools/team_staff_directory.cjs");
const { createIntakeServer } = require("../tools/team_intake_server.cjs");
const { SCOPING_HEADERS, enrolled, exportRef, mailed, openStore, principalFor, scoping, secretFor } = require("./staff_fixture.cjs");
const I = require("../src/intake.js");

const ROOT = path.resolve(__dirname, "..");
const TEAM = "carbon-fit";
const TOKENS = {
  receiver: "basis-receiver-token-0001",
  reviewer: "basis-reviewer-token-0001",
  steward: "basis-steward-token-0001",
};
const ACCOUNTS = [
  enrolled("basis-receiver", TEAM, ["INTAKE_RECEIVER"], TOKENS.receiver),
  enrolled("basis-reviewer", TEAM, ["TEAM_REVIEWER"], TOKENS.reviewer),
  enrolled("basis-steward", TEAM, ["DATA_STEWARD"], TOKENS.steward),
];
const DIRECTORY = new StaffDirectory(ACCOUNTS);
const as = (name) => principalFor(DIRECTORY, TOKENS[name]);

function raw(draftId = "basis-draft") {
  const brief = JSON.parse(fs.readFileSync(path.join(ROOT, "intake/fixtures/existing_method_v1.json"), "utf8"));
  brief.draft_id = draftId;
  return JSON.stringify({
    schema_version: I.REVIEW_VERSION,
    brief,
    pilot: { label: "Draft pilot for Carbon review", ...Object.fromEntries(I.PILOT_FIELDS.map((f) => [f, ""])), bounded_first_pilot: "Synthetic bounded pilot." },
    field_provenance: [...I.TEXT_FIELDS, ...I.QUANTITY_FIELDS, ...I.PILOT_FIELDS.map((f) => "pilot." + f)].map((field) => ({ field, origin: "UNKNOWN", suggestion_id: null })),
    accepted_suggestions: [],
    unresolved_assumptions: [],
    ai_guidance: { enabled: false, provider: null, guidance_version: I.GUIDANCE_VERSION, notice_version: null, consented_at: null, cleared_locally: false },
    sharing: { include_conversation: false, conversation: [] },
    contact: { name: "", email: "", organization: "" },
    local_scope: I.REVIEW_SCOPE,
  });
}

const fresh = () => openStore(path.join(fs.mkdtempSync(path.join(os.tmpdir(), "carbon-basis-")), "store.json"));

test("a record cannot be built without an issued agreement basis", async () => {
  const store = fresh();
  const forged = [undefined, null, { ...scoping() }, { record_class: "SCOPING", agreements: { nda: "synthetic-nda-0001" }, legal_basis: "contract:synthetic-nda-0001" }, Object.create(RecordBasis.prototype)];
  for (const basis of forged)
    await assert.rejects(store.accept(raw(), "basis-001", as("receiver"), basis, mailed(), exportRef()), /cannot be created without an agreement reference/);
  assert.deepEqual(Object.keys(store.state.inquiries), []);
  assert.throws(() => new RecordBasis(Symbol("guess"), {}), /can only be issued/);
  // Specimen: an issued basis is accepted, and the record carries it.
  const receipt = await store.accept(raw(), "basis-001", as("receiver"), scoping(), mailed(), exportRef());
  const record = store.read(receipt.inquiry_id, as("reviewer"));
  assert.equal(record.basis.record_class, "SCOPING");
  assert.equal(record.basis.legal_basis, "contract:synthetic-nda-0001");
  assert.equal(record.retention.legal_basis, "contract:synthetic-nda-0001");
  assert.equal(record.basis_history[0].event, "RECEIVED");
});

test("each class requires its own complete set of references", () => {
  assert.throws(() => scopingBasis({}), /mutual NDA reference is required/);
  assert.throws(() => scopingBasis({ nda: "x" }), /mutual NDA reference is required/);
  assert.throws(() => scopingBasis({ nda: "has spaces in it" }), /mutual NDA reference is required/);
  assert.throws(() => studyBasis({ msa: "synthetic-msa-0001" }), /Order Form reference is required/);
  assert.throws(() => studyBasis({ order_form: "synthetic-of-0001" }), /countersigned MSA reference is required/);
  assert.throws(() => basisFromHeaders({}), /record class is required/);
  assert.throws(() => basisFromHeaders({ "x-carbon-record-class": "STUDY", "x-carbon-msa-ref": "synthetic-msa-0001" }), /Order Form/);
  // Specimen: each complete set issues a basis.
  assert.equal(isRecordBasis(scopingBasis({ nda: "synthetic-nda-0001" })), true);
  const study = studyBasis({ msa: "synthetic-msa-0001", order_form: "synthetic-of-0001" });
  assert.equal(study.record_class, "STUDY");
  assert.equal(study.legal_basis, "contract:synthetic-msa-0001/synthetic-of-0001");
  assert.equal(Object.isFrozen(study), true);
});

test("the same package under a different agreement is not a retry", async () => {
  const store = fresh();
  await store.accept(raw(), "basis-002", as("receiver"), scoping(), mailed(), exportRef());
  const again = await store.accept(raw(), "basis-002", as("receiver"), scoping(), mailed(), exportRef());
  assert.equal(again.disposition, "DEDUPLICATED");
  await assert.rejects(
    store.accept(raw(), "basis-002", as("receiver"), studyBasis({ msa: "synthetic-msa-0001", order_form: "synthetic-of-0001" }), mailed(), exportRef()),
    /different agreement basis/,
  );
});

test("a record written before E4 is unusable until a steward attaches its basis", async () => {
  const store = fresh();
  const receipt = await store.accept(raw(), "basis-003", as("receiver"), scoping(), mailed(), exportRef());
  // A pre-E4 store: the same state with no basis recorded, as it was written.
  const legacy = JSON.parse(JSON.stringify(store.state));
  for (const record of Object.values(legacy.inquiries)) {
    delete record.basis;
    delete record.basis_history;
    delete record.retention.legal_basis;
  }
  fs.writeFileSync(store.filePath, JSON.stringify(legacy));
  const reopened = openStore(store.filePath);
  assert.equal(reopened.state.inquiries[receipt.inquiry_id].basis_origin, "PRE_E4_NONE_RECORDED");
  assert.throws(() => reopened.read(receipt.inquiry_id, as("reviewer")), /no recorded agreement basis/);
  // Only a data steward may attach it.
  assert.throws(() => reopened.attachBasis(receipt.inquiry_id, scoping(), as("reviewer")), /not authorized/);
  reopened.attachBasis(receipt.inquiry_id, scoping(), as("steward"));
  const record = reopened.read(receipt.inquiry_id, as("reviewer"));
  assert.equal(record.basis.legal_basis, "contract:synthetic-nda-0001");
  assert.deepEqual(record.basis_history.map((entry) => entry.event), ["ATTACHED_PRE_E4"]);
});

test("SCOPING is promoted to STUDY once, and never goes back", async () => {
  const store = fresh();
  const receipt = await store.accept(raw(), "basis-004", as("receiver"), scoping(), mailed(), exportRef());
  assert.throws(() => store.attachBasis(receipt.inquiry_id, scoping(), as("steward")), /only a missing basis may be attached/);
  const study = studyBasis({ msa: "synthetic-msa-0001", order_form: "synthetic-of-0001" });
  store.attachBasis(receipt.inquiry_id, study, as("steward"));
  const record = store.read(receipt.inquiry_id, as("reviewer"));
  assert.equal(record.basis.record_class, "STUDY");
  assert.equal(record.retention.legal_basis, study.legal_basis);
  assert.deepEqual(record.basis_history.map((entry) => entry.event), ["RECEIVED", "PROMOTED_TO_STUDY"]);
  assert.equal(record.basis_history[0].record_class, "SCOPING");
  assert.throws(() => store.attachBasis(receipt.inquiry_id, scoping(), as("steward")), /only a missing basis may be attached/);
  assert.throws(() => store.attachBasis(receipt.inquiry_id, study, as("steward")), /only a missing basis may be attached/);
});

test("over HTTP, a relay without a complete basis stores nothing", async () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "carbon-basis-http-"));
  const store = openStore(path.join(directory, "store.json"));
  const server = createIntakeServer({ store, users: ACCOUNTS });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  try {
    const opened = await fetch(base + "/private/session", {
      method: "POST",
      headers: { authorization: "Bearer " + TOKENS.receiver, "content-type": "application/json" },
      body: JSON.stringify({ code: totp(secretFor(TOKENS.receiver), Date.now()) }),
    });
    const session = (await opened.json()).session_token;
    const relay = (headers, key) =>
      fetch(base + "/private/intake", {
        method: "POST",
        headers: { authorization: "Bearer " + session, "content-type": "application/json", "idempotency-key": key, ...headers },
        body: raw(),
      });
    assert.equal((await relay({}, "http-001")).status, 400);
    assert.equal((await relay({ "x-carbon-record-class": "STUDY", "x-carbon-msa-ref": "synthetic-msa-0001" }, "http-002")).status, 400);
    assert.deepEqual(Object.keys(store.state.inquiries), []);
    // Specimen: the same relay with a complete basis is stored.
    const accepted = await relay(SCOPING_HEADERS, "http-003");
    assert.equal(accepted.status, 201);
    assert.equal(Object.keys(store.state.inquiries).length, 1);
  } finally {
    server.close();
  }
});
