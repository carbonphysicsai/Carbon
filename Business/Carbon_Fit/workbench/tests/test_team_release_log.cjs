"use strict";
// E5: what was released, to whom, when and why. Prior exports are one of the
// things deletion cannot reach; this log is what lets Carbon find every copy it
// released and ask for its destruction. Each refusal is paired with the
// matching success, and each absence with a specimen.
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
if (!globalThis.crypto) globalThis.crypto = crypto.webcrypto;
const { StaffDirectory, totp } = require("../tools/team_staff_directory.cjs");
const { createIntakeServer } = require("../tools/team_intake_server.cjs");
const { RELEASE, RELEASE_HEADERS, SCOPING_HEADERS, enrolled, openStore, principalFor, scoping, secretFor } = require("./staff_fixture.cjs");
const I = require("../src/intake.js");

const ROOT = path.resolve(__dirname, "..");
const TEAM = "carbon-fit";
const TOKENS = {
  receiver: "release-receiver-token-0001",
  reviewer: "release-reviewer-token-0001",
  steward: "release-steward-token-0001",
  foreign: "release-foreign-steward-token-0001",
};
const ACCOUNTS = [
  enrolled("release-receiver", TEAM, ["INTAKE_RECEIVER"], TOKENS.receiver),
  enrolled("release-reviewer", TEAM, ["TEAM_REVIEWER"], TOKENS.reviewer),
  enrolled("release-steward", TEAM, ["DATA_STEWARD"], TOKENS.steward),
  enrolled("release-foreign", "other-tenant", ["DATA_STEWARD", "TEAM_REVIEWER", "INTAKE_RECEIVER"], TOKENS.foreign),
];
const DIRECTORY = new StaffDirectory(ACCOUNTS);
const as = (name) => principalFor(DIRECTORY, TOKENS[name]);
const SENTINEL = "E5SENTINELCLIENTWORDS";

function raw(words = "Synthetic bounded pilot.", draftId = "release-draft") {
  const brief = JSON.parse(fs.readFileSync(path.join(ROOT, "intake/fixtures/existing_method_v1.json"), "utf8"));
  brief.draft_id = draftId;
  return JSON.stringify({
    schema_version: I.REVIEW_VERSION,
    brief,
    pilot: { label: "Draft pilot for Carbon review", ...Object.fromEntries(I.PILOT_FIELDS.map((f) => [f, ""])), bounded_first_pilot: words },
    field_provenance: [...I.TEXT_FIELDS, ...I.QUANTITY_FIELDS, ...I.PILOT_FIELDS.map((f) => "pilot." + f)].map((field) => ({ field, origin: "UNKNOWN", suggestion_id: null })),
    accepted_suggestions: [],
    unresolved_assumptions: [],
    ai_guidance: { enabled: false, provider: null, guidance_version: I.GUIDANCE_VERSION, notice_version: null, consented_at: null, cleared_locally: false },
    sharing: { include_conversation: false, conversation: [] },
    contact: { name: "", email: "", organization: "" },
    local_scope: I.REVIEW_SCOPE,
  });
}

const fresh = () => openStore(path.join(fs.mkdtempSync(path.join(os.tmpdir(), "carbon-release-")), "store.json"));

test("an export names its recipient and purpose, or releases nothing", async () => {
  const store = fresh();
  const receipt = await store.accept(raw(), "release-001", as("receiver"), scoping());
  for (const terms of [{}, { purpose: "Team review" }, { recipient: { kind: "CARBON_STAFF" }, purpose: "Team review" }, { recipient: { kind: "ANYONE", ref: "someone-1" }, purpose: "Team review" }, { recipient: RELEASE.recipient, purpose: "x" }])
    assert.throws(() => store.export(receipt.inquiry_id, as("reviewer"), terms), /A release (names|states)/);
  assert.deepEqual(store.releases(as("steward")), []);
  // Specimen: with both, the export is returned and logged, and the entry is on
  // disk before the content was handed over.
  const exported = store.export(receipt.inquiry_id, as("reviewer"), RELEASE);
  const [entry] = openStore(store.filePath).releases(as("steward"));
  assert.equal(entry.inquiry_id, receipt.inquiry_id);
  assert.deepEqual(entry.recipient, RELEASE.recipient);
  assert.equal(entry.purpose, RELEASE.purpose);
  assert.equal(entry.released_by, "release-reviewer");
  assert.equal(entry.channel, "RECEIVER_EXPORT");
  assert.equal(entry.record_version, exported.version);
  assert.equal(entry.artifact_sha256, "sha256:" + crypto.createHash("sha256").update(JSON.stringify(exported)).digest("hex"));
});

test("the log carries digests and names, never the client's content", async () => {
  const store = fresh();
  const receipt = await store.accept(raw(SENTINEL + " operating range"), "release-002", as("receiver"), scoping());
  const exported = store.export(receipt.inquiry_id, as("reviewer"), RELEASE);
  // Specimen: the export itself holds the client's words.
  assert.ok(JSON.stringify(exported).includes(SENTINEL));
  assert.ok(!JSON.stringify(store.releases(as("steward"))).includes(SENTINEL));
});

test("the log outlives the record, and the tombstone names every prior release", async () => {
  const store = fresh();
  const receipt = await store.accept(raw(), "release-003", as("receiver"), scoping());
  const first = store.export(receipt.inquiry_id, as("reviewer"), RELEASE);
  const second = store.recordRelease(
    receipt.inquiry_id,
    { recipient: { kind: "CLIENT", ref: "synthetic-client-contact" }, purpose: "Pilot brief sent", artifact_sha256: "sha256:" + "a".repeat(64) },
    as("reviewer"),
  );
  assert.ok(first && second.channel === "RECORDED_EXTERNAL");
  store.approveDeletionException(receipt.inquiry_id, { approver: "Synthetic approver", reason: "E5 fixture" }, as("steward"));
  const tombstone = store.delete(receipt.inquiry_id, as("steward"));
  const logged = store.releases(as("steward"), { inquiryId: receipt.inquiry_id });
  assert.equal(logged.length, 2);
  assert.deepEqual(tombstone.prior_releases, logged.map((entry) => entry.release_id));
  assert.ok(tombstone.did_not_reach.includes("PRIOR_EXPORTS"));
});

test("a recorded release needs its artifact digest, and only the team may record or list", async () => {
  const store = fresh();
  const receipt = await store.accept(raw(), "release-004", as("receiver"), scoping());
  assert.throws(
    () => store.recordRelease(receipt.inquiry_id, { ...RELEASE, artifact_sha256: "not-a-digest" }, as("reviewer")),
    /by its sha256 digest/,
  );
  assert.throws(() => store.recordRelease(receipt.inquiry_id, { ...RELEASE, artifact_sha256: "sha256:" + "b".repeat(64) }, as("receiver")), /not authorized/);
  assert.throws(() => store.releases(as("reviewer")), /not authorized/);
  store.recordRelease(receipt.inquiry_id, { ...RELEASE, artifact_sha256: "sha256:" + "b".repeat(64) }, as("steward"));
  // Another team's steward sees none of this team's releases.
  assert.deepEqual(store.releases(as("foreign")), []);
  // Specimen: this team's steward sees it.
  assert.equal(store.releases(as("steward")).length, 1);
});

test("a store written before E5 says its earlier releases were not logged", async () => {
  const store = fresh();
  await store.accept(raw(), "release-005", as("receiver"), scoping());
  assert.equal(store.state.release_log.origin, "NATIVE");
  const legacy = JSON.parse(JSON.stringify(store.state));
  delete legacy.releases;
  delete legacy.release_log;
  fs.writeFileSync(store.filePath, JSON.stringify(legacy));
  const reopened = openStore(store.filePath);
  assert.equal(reopened.state.release_log.origin, "PRE_E5_RELEASES_NOT_LOGGED");
  assert.deepEqual(reopened.releases(as("steward")), []);
});

test("over HTTP, an export without its release terms is refused, and a steward reads the log", async () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "carbon-release-http-"));
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
    const accepted = await fetch(base + "/private/intake", {
      method: "POST",
      headers: { authorization: receiver, "content-type": "application/json", "idempotency-key": "http-release-1", ...SCOPING_HEADERS },
      body: raw(),
    });
    const { inquiry_id: id } = await accepted.json();
    const bare = await fetch(`${base}/private/intake/${id}/export`, { headers: { authorization: reviewer } });
    assert.equal(bare.status, 400);
    const exported = await fetch(`${base}/private/intake/${id}/export`, { headers: { authorization: reviewer, ...RELEASE_HEADERS } });
    assert.equal(exported.status, 200);
    const log = await fetch(`${base}/private/releases?inquiry=${id}`, { headers: { authorization: steward } });
    assert.equal(log.status, 200);
    assert.equal((await log.json()).releases.length, 1);
    assert.equal((await fetch(`${base}/private/releases`, { headers: { authorization: reviewer } })).status, 403);
  } finally {
    server.close();
  }
});
