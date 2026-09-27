"use strict";
// E6: the transport copy - the package as it arrived in the intake mailbox.
// Transport-copy schema v2: moved to Trash, purged from the mailbox, and the
// provider's restore window elapsed are different states, reached in that
// order. No state claims a destruction the provider can still reverse. Mailbox
// steps are the receiver's attestation, because this store cannot see them.
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
if (!globalThis.crypto) globalThis.crypto = crypto.webcrypto;
const { StaffDirectory, totp } = require("../tools/team_staff_directory.cjs");
const { createIntakeServer } = require("../tools/team_intake_server.cjs");
const { ADMIN_RESTORE_DAYS, PROVIDER_RESTORE_OBSERVATION, TRANSPORT_SCHEMA, TRASH_PURGE_DAYS, transportAtRelay } = require("../tools/team_intake_store.cjs");
const { SCOPING_HEADERS, enrolled, exportRef, mailed, openStore, principalFor, scoping, secretFor } = require("./staff_fixture.cjs");
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

const DAY = 86_400_000;
const fresh = (clock) => openStore(path.join(fs.mkdtempSync(path.join(os.tmpdir(), "carbon-copy-")), "store.json"), clock ? { clock } : {});
// A store whose time the test moves.
function clocked() {
  let now = Date.UTC(2027, 0, 1);
  const store = fresh(() => now);
  return { store, advance: (ms) => { now += ms; }, now: () => now };
}

test("a relay states its channel and how the package arrived, or nothing is stored", async () => {
  assert.throws(() => transportAtRelay({}), /states its intake channel/);
  assert.throws(() => transportAtRelay({ "x-carbon-intake-channel": "MAIL_INTAKE" }), /states how it arrived/);
  const store = fresh();
  await assert.rejects(store.accept(raw(), "copy-001", as("receiver"), scoping(), undefined, exportRef()), /states how its package arrived/);
  await assert.rejects(
    store.accept(raw(), "copy-001", as("receiver"), scoping(), { channel: "MAIL_INTAKE", arrival: "ENCRYPTED", copy_state: "PERMANENTLY_REMOVED", history: [] }, exportRef()),
    /states how its package arrived/,
  );
  assert.deepEqual(Object.keys(store.state.inquiries), []);
  // Specimen: a complete statement is recorded as it was given.
  const receipt = await store.accept(raw(), "copy-001", as("receiver"), scoping(), mailed(), exportRef());
  const transport = store.read(receipt.inquiry_id, as("reviewer")).transport;
  assert.deepEqual(
    { channel: transport.channel, arrival: transport.arrival, copy_state: transport.copy_state },
    { channel: "MAIL_INTAKE", arrival: "ENCRYPTED", copy_state: "PRESENT_IN_MAILBOX" },
  );
  const handed = transportAtRelay({ "x-carbon-intake-channel": "DIRECT_HANDOVER" });
  assert.equal(handed.copy_state, "NO_TRANSPORT_COPY");
});

test("Trash, purge and the elapsed window are states in that order, each stating its basis", async () => {
  const c = clocked();
  const receipt = await c.store.accept(raw(), "copy-002", as("receiver"), scoping(), mailed(), exportRef());
  const trashed = c.store.recordTransportCopy(receipt.inquiry_id, "MOVED_TO_TRASH", as("receiver"));
  assert.equal(trashed.copy_state, "MOVED_TO_TRASH");
  const [first] = trashed.history;
  assert.equal(first.schema, TRANSPORT_SCHEMA);
  assert.equal(first.basis, "RECEIVER_ATTESTATION");
  assert.equal(first.by, "copy-receiver");
  // The claim in Trash says when the purge is expected, not that it happened.
  assert.equal(Date.parse(first.purge_expected_by) - Date.parse(first.at), TRASH_PURGE_DAYS * DAY);
  // Never backwards, never twice, never an unknown state.
  assert.throws(() => c.store.recordTransportCopy(receipt.inquiry_id, "MOVED_TO_TRASH", as("receiver")), /cannot move/);
  assert.throws(() => c.store.recordTransportCopy(receipt.inquiry_id, "DELETED", as("receiver")), /cannot move/);
  c.advance(DAY);
  const purged = c.store.recordTransportCopy(receipt.inquiry_id, "PURGED_FROM_MAILBOX", as("receiver"));
  assert.equal(purged.copy_state, "PURGED_FROM_MAILBOX");
  assert.deepEqual(purged.history.map((entry) => entry.state), ["MOVED_TO_TRASH", "PURGED_FROM_MAILBOX"]);
  assert.throws(() => c.store.recordTransportCopy(receipt.inquiry_id, "PURGED_FROM_MAILBOX", as("receiver")), /cannot move/);
  assert.throws(() => c.store.recordTransportCopy(receipt.inquiry_id, "MOVED_TO_TRASH", as("receiver")), /cannot move/);
  // Only the receiver who holds the mailbox records what happened in it.
  const other = await c.store.accept(raw(), "copy-003", as("receiver"), scoping(), mailed(), exportRef());
  assert.throws(() => c.store.recordTransportCopy(other.inquiry_id, "MOVED_TO_TRASH", as("reviewer")), /not authorized/);
  // Specimen: purging straight from the mailbox is a valid single step.
  assert.equal(c.store.recordTransportCopy(other.inquiry_id, "PURGED_FROM_MAILBOX", as("receiver")).copy_state, "PURGED_FROM_MAILBOX");
});

test("a purge states until when an administrator could restore it, as observed provider behaviour", async () => {
  const c = clocked();
  const receipt = await c.store.accept(raw(), "copy-restore-1", as("receiver"), scoping(), mailed(), exportRef());
  const trashed = c.store.recordTransportCopy(receipt.inquiry_id, "MOVED_TO_TRASH", as("receiver")).history[0];
  c.advance(3 * DAY);
  const purged = c.store.recordTransportCopy(receipt.inquiry_id, "PURGED_FROM_MAILBOX", as("receiver")).history[1];
  // The later of the trash period plus the restore days after the first
  // deletion, and the restore days after the purge.
  const expected = Math.max(Date.parse(trashed.at) + (TRASH_PURGE_DAYS + ADMIN_RESTORE_DAYS) * DAY, Date.parse(purged.at) + ADMIN_RESTORE_DAYS * DAY);
  assert.equal(Date.parse(purged.admin_restore_possible_until), expected);
  // The window is the provider's documented behaviour with its source and read
  // date, never a Carbon retention rule.
  assert.deepEqual(purged.provider_observation, { ...PROVIDER_RESTORE_OBSERVATION });
  assert.equal(purged.provider_observation.status, "OBSERVED_PROVIDER_BEHAVIOUR_NOT_CARBON_POLICY");
  assert.equal(purged.provider_observation.basis, "PROVIDER_DOCUMENTATION_NOT_VERIFIED_AGAINST_ACCOUNT");
  assert.equal(purged.provider_observation.read_on, "2026-09-27");
  // Specimen: the Trash entry makes no such statement; only the purge does.
  assert.equal(trashed.admin_restore_possible_until, undefined);
});

test("while the restore window is open the elapsed state cannot be recorded; once it closes it can", async () => {
  const c = clocked();
  const receipt = await c.store.accept(raw(), "copy-window-1", as("receiver"), scoping(), mailed(), exportRef());
  const purged = c.store.recordTransportCopy(receipt.inquiry_id, "PURGED_FROM_MAILBOX", as("receiver")).history[0];
  const end = Date.parse(purged.admin_restore_possible_until);
  // Refused at the purge, and one millisecond before the window closes.
  assert.throws(() => c.store.recordTransportCopy(receipt.inquiry_id, "PROVIDER_RESTORE_WINDOW_ELAPSED", as("receiver")), /restore window is open/);
  c.advance(end - c.now() - 1);
  assert.throws(() => c.store.recordTransportCopy(receipt.inquiry_id, "PROVIDER_RESTORE_WINDOW_ELAPSED", as("receiver")), /restore window is open/);
  assert.equal(c.store.read(receipt.inquiry_id, as("reviewer")).transport.copy_state, "PURGED_FROM_MAILBOX");
  // Specimen: at the end of the window it is recorded, and it is final.
  c.advance(1);
  const elapsed = c.store.recordTransportCopy(receipt.inquiry_id, "PROVIDER_RESTORE_WINDOW_ELAPSED", as("receiver"));
  assert.equal(elapsed.copy_state, "PROVIDER_RESTORE_WINDOW_ELAPSED");
  const entry = elapsed.history[1];
  assert.equal(entry.basis, "PROVIDER_DOCUMENTED_WINDOW_ELAPSED");
  assert.equal(entry.window_ended_at, purged.admin_restore_possible_until);
  assert.deepEqual(entry.provider_observation, purged.provider_observation);
  assert.throws(() => c.store.recordTransportCopy(receipt.inquiry_id, "PURGED_FROM_MAILBOX", as("receiver")), /cannot move/);
});

test("PERMANENTLY_REMOVED is no longer recordable, and a v1 record keeps what it recorded", async () => {
  const c = clocked();
  const receipt = await c.store.accept(raw(), "copy-v1-1", as("receiver"), scoping(), mailed(), exportRef());
  assert.throws(() => c.store.recordTransportCopy(receipt.inquiry_id, "PERMANENTLY_REMOVED", as("receiver")), /v1 state.*record PURGED_FROM_MAILBOX/);
  // A record written under v1: no schema on the block or its entries, ending
  // in v1's terminal state, the way the store holds one written before v2.
  const v1 = await c.store.accept(raw(), "copy-v1-2", as("receiver"), scoping(), mailed(), exportRef());
  const removedAt = new Date(c.now()).toISOString();
  const v1Entry = { seq: 1, state: "PERMANENTLY_REMOVED", at: removedAt, by: "copy-receiver", basis: "RECEIVER_ATTESTATION", purge_expected_by: null };
  const legacy = { channel: "MAIL_INTAKE", arrival: "ENCRYPTED", required_disposition: "PERMANENTLY_REMOVED", copy_state: "PERMANENTLY_REMOVED", history: [v1Entry] };
  const next = JSON.parse(JSON.stringify(c.store.state));
  next.inquiries[v1.inquiry_id].transport = legacy;
  c.store.persist(next);
  // Not reinterpreted: reopened from disk, the v1 state, disposition and entry
  // are exactly as recorded.
  const fromDisk = openStore(c.store.filePath, { clock: c.now });
  assert.deepEqual(fromDisk.read(v1.inquiry_id, as("reviewer")).transport, legacy);
  // Its only next step is the elapsed state, and only after the window its own
  // recorded time implies.
  assert.throws(() => c.store.recordTransportCopy(v1.inquiry_id, "PURGED_FROM_MAILBOX", as("receiver")), /cannot move from PERMANENTLY_REMOVED/);
  assert.throws(() => c.store.recordTransportCopy(v1.inquiry_id, "PROVIDER_RESTORE_WINDOW_ELAPSED", as("receiver")), /restore window is open/);
  c.advance((TRASH_PURGE_DAYS + ADMIN_RESTORE_DAYS) * DAY);
  const moved = c.store.recordTransportCopy(v1.inquiry_id, "PROVIDER_RESTORE_WINDOW_ELAPSED", as("receiver"));
  // The v1 entry is untouched; the new entry and the block say where v2 began.
  assert.deepEqual(moved.history[0], v1Entry);
  assert.equal(moved.history[1].schema, TRANSPORT_SCHEMA);
  assert.equal(moved.schema, TRANSPORT_SCHEMA);
  assert.equal(moved.schema_before, "carbon.private-team-intake.transport-copy.v1");
  assert.equal(moved.schema_changed_at_seq, 2);
  assert.equal(moved.required_disposition, "PERMANENTLY_REMOVED");
});

test("a plaintext arrival records that its copy is to be removed without delay", async () => {
  const store = fresh();
  const plaintext = transportAtRelay({ "x-carbon-intake-channel": "MAIL_INTAKE", "x-carbon-transport-arrival": "PLAINTEXT" });
  const receipt = await store.accept(raw(), "copy-004", as("receiver"), scoping(), plaintext, exportRef());
  const transport = store.read(receipt.inquiry_id, as("reviewer")).transport;
  assert.equal(transport.arrival, "PLAINTEXT");
  assert.equal(transport.required_disposition, "PURGED_FROM_MAILBOX_WITHOUT_DELAY");
  assert.equal(transport.schema, TRANSPORT_SCHEMA);
  // Specimen: an encrypted arrival carries the ordinary requirement.
  assert.equal(mailed().required_disposition, "PURGED_FROM_MAILBOX");
});

test("a direct handover has no transport copy to record against", async () => {
  const store = fresh();
  const receipt = await store.accept(raw(), "copy-005", as("receiver"), scoping(), transportAtRelay({ "x-carbon-intake-channel": "DIRECT_HANDOVER" }), exportRef());
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
    assert.equal((await record("PERMANENTLY_REMOVED")).status, 400);
    const purged = await record("PURGED_FROM_MAILBOX");
    assert.equal(purged.status, 200);
    assert.equal((await purged.json()).copy_state, "PURGED_FROM_MAILBOX");
    assert.equal((await record("PROVIDER_RESTORE_WINDOW_ELAPSED")).status, 409);
    assert.equal((await record("MOVED_TO_TRASH")).status, 400);
  } finally {
    server.close();
  }
});
