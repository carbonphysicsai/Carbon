"use strict";
// E6: the transport copy - the package as it arrived in the intake mailbox.
// Moved to Trash and permanently removed are different states, reached in that
// order, and each is recorded as the receiver's attestation, because the
// mailbox step is a human one this store cannot see.
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
if (!globalThis.crypto) globalThis.crypto = crypto.webcrypto;
const { StaffDirectory, totp } = require("../tools/team_staff_directory.cjs");
const { createIntakeServer } = require("../tools/team_intake_server.cjs");
const { TRASH_PURGE_DAYS, transportAtRelay } = require("../tools/team_intake_store.cjs");
const { SCOPING_HEADERS, enrolled, mailed, openStore, principalFor, scoping, secretFor } = require("./staff_fixture.cjs");
const I = require("../src/intake.js");

const ROOT = path.resolve(__dirname, "..");
const TEAM = "carbon-fit";
const TOKENS = { receiver: "copy-receiver-token-0001", reviewer: "copy-reviewer-token-0001" };
const ACCOUNTS = [
  enrolled("copy-receiver", TEAM, ["INTAKE_RECEIVER"], TOKENS.receiver),
  enrolled("copy-reviewer", TEAM, ["TEAM_REVIEWER"], TOKENS.reviewer),
];
const DIRECTORY = new StaffDirectory(ACCOUNTS);
const as = (name) => principalFor(DIRECTORY, TOKENS[name]);

function raw(draftId = "copy-draft-" + crypto.randomBytes(4).toString("hex")) {
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

const fresh = () => openStore(path.join(fs.mkdtempSync(path.join(os.tmpdir(), "carbon-copy-")), "store.json"));

test("a relay states its channel and how the package arrived, or nothing is stored", async () => {
  assert.throws(() => transportAtRelay({}), /states its intake channel/);
  assert.throws(() => transportAtRelay({ "x-carbon-intake-channel": "MAIL_INTAKE" }), /states how it arrived/);
  const store = fresh();
  await assert.rejects(store.accept(raw(), "copy-001", as("receiver"), scoping(), undefined), /states how its package arrived/);
  await assert.rejects(
    store.accept(raw(), "copy-001", as("receiver"), scoping(), { channel: "MAIL_INTAKE", arrival: "ENCRYPTED", copy_state: "PERMANENTLY_REMOVED", history: [] }),
    /states how its package arrived/,
  );
  assert.deepEqual(Object.keys(store.state.inquiries), []);
  // Specimen: a complete statement is recorded as it was given.
  const receipt = await store.accept(raw(), "copy-001", as("receiver"), scoping(), mailed());
  const transport = store.read(receipt.inquiry_id, as("reviewer")).transport;
  assert.deepEqual(
    { channel: transport.channel, arrival: transport.arrival, copy_state: transport.copy_state },
    { channel: "MAIL_INTAKE", arrival: "ENCRYPTED", copy_state: "PRESENT_IN_MAILBOX" },
  );
  const handed = transportAtRelay({ "x-carbon-intake-channel": "DIRECT_HANDOVER" });
  assert.equal(handed.copy_state, "NO_TRANSPORT_COPY");
});

test("Trash and permanent removal are two states, in that order, each the receiver's attestation", async () => {
  const store = fresh();
  const receipt = await store.accept(raw(), "copy-002", as("receiver"), scoping(), mailed());
  const before = Date.now();
  const trashed = store.recordTransportCopy(receipt.inquiry_id, "MOVED_TO_TRASH", as("receiver"));
  assert.equal(trashed.copy_state, "MOVED_TO_TRASH");
  const [first] = trashed.history;
  assert.equal(first.basis, "RECEIVER_ATTESTATION");
  assert.equal(first.by, "copy-receiver");
  // The claim in Trash says when the purge is expected, not that it happened.
  const expected = Date.parse(first.purge_expected_by) - Date.parse(first.at);
  assert.equal(expected, TRASH_PURGE_DAYS * 86_400_000);
  assert.ok(Date.parse(first.at) >= before - 1000);
  // Never backwards, never twice, never an unknown state.
  assert.throws(() => store.recordTransportCopy(receipt.inquiry_id, "MOVED_TO_TRASH", as("receiver")), /cannot move/);
  assert.throws(() => store.recordTransportCopy(receipt.inquiry_id, "DELETED", as("receiver")), /cannot move/);
  const removed = store.recordTransportCopy(receipt.inquiry_id, "PERMANENTLY_REMOVED", as("receiver"));
  assert.equal(removed.copy_state, "PERMANENTLY_REMOVED");
  assert.deepEqual(removed.history.map((entry) => entry.state), ["MOVED_TO_TRASH", "PERMANENTLY_REMOVED"]);
  assert.equal(removed.history[1].purge_expected_by, null);
  assert.throws(() => store.recordTransportCopy(receipt.inquiry_id, "PERMANENTLY_REMOVED", as("receiver")), /cannot move/);
  // Only the receiver who holds the mailbox records what happened in it.
  const other = await store.accept(raw(), "copy-003", as("receiver"), scoping(), mailed());
  assert.throws(() => store.recordTransportCopy(other.inquiry_id, "MOVED_TO_TRASH", as("reviewer")), /not authorized/);
  // Specimen: permanent removal straight from the mailbox is a valid single step.
  assert.equal(store.recordTransportCopy(other.inquiry_id, "PERMANENTLY_REMOVED", as("receiver")).copy_state, "PERMANENTLY_REMOVED");
});

test("a plaintext arrival records that its copy is to be removed without delay", async () => {
  const store = fresh();
  const plaintext = transportAtRelay({ "x-carbon-intake-channel": "MAIL_INTAKE", "x-carbon-transport-arrival": "PLAINTEXT" });
  const receipt = await store.accept(raw(), "copy-004", as("receiver"), scoping(), plaintext);
  const transport = store.read(receipt.inquiry_id, as("reviewer")).transport;
  assert.equal(transport.arrival, "PLAINTEXT");
  assert.equal(transport.required_disposition, "PERMANENTLY_REMOVED_WITHOUT_DELAY");
  // Specimen: an encrypted arrival carries the ordinary requirement.
  assert.equal(mailed().required_disposition, "PERMANENTLY_REMOVED");
});

test("a direct handover has no transport copy to record against", async () => {
  const store = fresh();
  const receipt = await store.accept(raw(), "copy-005", as("receiver"), scoping(), transportAtRelay({ "x-carbon-intake-channel": "DIRECT_HANDOVER" }));
  assert.throws(() => store.recordTransportCopy(receipt.inquiry_id, "MOVED_TO_TRASH", as("receiver")), /cannot move from NO_TRANSPORT_COPY/);
});

test("over HTTP, the relay and the transport-copy record work end to end", async () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "carbon-copy-http-"));
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
    const session = "Bearer " + (await opened.json()).session_token;
    const { "x-carbon-intake-channel": _c, ...withoutChannel } = SCOPING_HEADERS;
    const refused = await fetch(base + "/private/intake", {
      method: "POST",
      headers: { authorization: session, "content-type": "application/json", "idempotency-key": "copy-http-1", ...withoutChannel },
      body: raw(),
    });
    assert.equal(refused.status, 400);
    assert.deepEqual(Object.keys(store.state.inquiries), []);
    const accepted = await fetch(base + "/private/intake", {
      method: "POST",
      headers: { authorization: session, "content-type": "application/json", "idempotency-key": "copy-http-2", ...SCOPING_HEADERS },
      body: raw(),
    });
    const { inquiry_id: id } = await accepted.json();
    const record = (state) =>
      fetch(`${base}/private/intake/${id}/transport-copy`, {
        method: "POST",
        headers: { authorization: session, "content-type": "application/json" },
        body: JSON.stringify({ state }),
      });
    assert.equal((await record("MOVED_TO_TRASH")).status, 200);
    const removed = await record("PERMANENTLY_REMOVED");
    assert.equal(removed.status, 200);
    assert.equal((await removed.json()).copy_state, "PERMANENTLY_REMOVED");
    assert.equal((await record("MOVED_TO_TRASH")).status, 400);
  } finally {
    server.close();
  }
});
