"use strict";
// E1: per-record archive encryption and key destruction, from the first record.
// Every absence is paired with a specimen showing the thing is present where
// it really is, so a search that stopped matching fails instead of passing.
const test = require("node:test");
const assert = require("node:assert/strict");
const childProcess = require("node:child_process");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
if (!globalThis.crypto) globalThis.crypto = crypto.webcrypto;
const { ArchiveKeyring } = require("../tools/team_archive_keyring.cjs");
const { DurableIntakeStore, SEALED_STORE_VERSION } = require("../tools/team_intake_store.cjs");
const { StaffDirectory } = require("../tools/team_staff_directory.cjs");
const { enrolled, keyringFor, openStore, principalFor, scoping } = require("./staff_fixture.cjs");
const I = require("../src/intake.js");

const ROOT = path.resolve(__dirname, "..");
const TEAM = "carbon-fit";
const TOKENS = {
  receiver: "archive-receiver-token-0001",
  reviewer: "archive-reviewer-token-0001",
  steward: "archive-steward-token-0001",
};
const DIRECTORY = new StaffDirectory([
  enrolled("archive-receiver", TEAM, ["INTAKE_RECEIVER"], TOKENS.receiver),
  enrolled("archive-reviewer", TEAM, ["TEAM_REVIEWER"], TOKENS.reviewer),
  enrolled("archive-steward", TEAM, ["DATA_STEWARD"], TOKENS.steward),
]);
const as = (name) => principalFor(DIRECTORY, TOKENS[name]);
const SENTINEL = "E1SENTINELCLIENTPARAMETER";

function packageWith(words, draftId = "archive-draft") {
  const brief = JSON.parse(fs.readFileSync(path.join(ROOT, "intake/fixtures/existing_method_v1.json"), "utf8"));
  brief.draft_id = draftId;
  return JSON.stringify({
    schema_version: I.REVIEW_VERSION,
    brief,
    pilot: {
      label: "Draft pilot for Carbon review",
      ...Object.fromEntries(I.PILOT_FIELDS.map((field) => [field, ""])),
      bounded_first_pilot: words,
    },
    field_provenance: [...I.TEXT_FIELDS, ...I.QUANTITY_FIELDS, ...I.PILOT_FIELDS.map((f) => "pilot." + f)].map(
      (field) => ({ field, origin: field === "pilot.bounded_first_pilot" ? "CLIENT_TYPED" : "UNKNOWN", suggestion_id: null }),
    ),
    accepted_suggestions: [],
    unresolved_assumptions: [],
    ai_guidance: { enabled: false, provider: null, guidance_version: I.GUIDANCE_VERSION, notice_version: null, consented_at: null, cleared_locally: false },
    sharing: { include_conversation: false, conversation: [] },
    contact: { name: "", email: "", organization: "" },
    local_scope: I.REVIEW_SCOPE,
  });
}

function fresh() {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "carbon-archive-"));
  const file = path.join(directory, "store.json");
  return { directory, file, store: openStore(file) };
}

test("client content never reaches the disk in the clear, in the store or a copy of it", async () => {
  const f = fresh();
  const receipt = await f.store.accept(packageWith(SENTINEL + " confidential operating range"), "e1-001", as("receiver"), scoping());
  f.store.update(receipt.inquiry_id, 1, { assigned_reviewer: "Reviewer", queue_state: "UNDER_REVIEW", note: SENTINEL + " team note" }, as("reviewer"));
  // Specimen: the sentinel really is in the record, as the team reads it.
  const read = f.store.read(receipt.inquiry_id, as("reviewer"));
  assert.ok(read.raw_json.includes(SENTINEL));
  assert.ok(read.team_fields.note.includes(SENTINEL));
  const onDisk = fs.readFileSync(f.file, "utf8");
  assert.equal(JSON.parse(onDisk).schema_version, SEALED_STORE_VERSION);
  assert.ok(!onDisk.includes(SENTINEL), "client text was written in the clear");
  assert.ok(!onDisk.includes("confidential operating range"));
  // A backup taken the ordinary way, by copying the file, is ciphertext too.
  const backup = path.join(f.directory, "store.backup.json");
  fs.copyFileSync(f.file, backup);
  assert.ok(!fs.readFileSync(backup, "utf8").includes(SENTINEL));
  // And the keyring holds keys, never content.
  assert.ok(!fs.readFileSync(keyringFor(f.file).filePath, "utf8").includes(SENTINEL));
});

test("a store cannot be opened without a keyring, and a keyring cannot live beside the store", () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "carbon-archive-"));
  const file = path.join(directory, "store.json");
  assert.throws(() => new DurableIntakeStore(file), /requires an archive keyring/);
  assert.throws(() => new DurableIntakeStore(file, { keyring: { seal() {}, open() {} } }), /requires an archive keyring/);
  assert.throws(
    () => ArchiveKeyring.open(path.join(directory, "keys.json"), { storePath: file }),
    /must not live in the store's directory/,
  );
  assert.throws(
    () => ArchiveKeyring.open(path.join(directory, "nested", "keys.json"), { storePath: file }),
    /must not live in the store's directory/,
  );
  // Specimen: the same keyring outside the directory opens, and so does the store.
  const outside = fs.mkdtempSync(path.join(os.tmpdir(), "carbon-archive-keys-"));
  const keyring = ArchiveKeyring.open(path.join(outside, "keys.json"), { storePath: file });
  assert.ok(new DurableIntakeStore(file, { keyring }));
});

test("an approved deletion destroys the key first, and every earlier copy becomes unreadable", async () => {
  const f = fresh();
  const doomed = await f.store.accept(packageWith(SENTINEL + " to be deleted", "archive-doomed"), "e1-002", as("receiver"), scoping());
  const kept = await f.store.accept(packageWith("a record that stays", "archive-kept"), "e1-003", as("receiver"), scoping());
  // The retained archive: a copy of the store taken before the deletion.
  const archive = path.join(f.directory, "store.archive.json");
  fs.copyFileSync(f.file, archive);
  // Specimen: before deletion the archive copy reads the record.
  assert.ok(openStore(archive).read(doomed.inquiry_id, as("reviewer")).raw_json.includes(SENTINEL));

  const keyId = f.store.state.inquiries[doomed.inquiry_id].archive_key_id;
  f.store.approveDeletionException(doomed.inquiry_id, { approver: "Synthetic approver", reason: "E1 fixture" }, as("steward"));
  const tombstone = f.store.delete(doomed.inquiry_id, as("steward"));
  assert.equal(tombstone.archive_key, "DESTROYED");
  assert.ok(tombstone.archive_key_destroyed_at);
  // The bytes remain, and deletion says so rather than claiming otherwise.
  assert.ok(tombstone.did_not_reach.includes("RETAINED_ARCHIVE"));
  assert.ok(fs.readFileSync(archive, "utf8").includes(doomed.inquiry_id));

  // The key material is gone from the keyring; only a tombstone names it.
  const keyring = JSON.parse(fs.readFileSync(keyringFor(f.file).filePath, "utf8"));
  assert.equal(keyring.keys[keyId], undefined);
  assert.ok(keyring.destroyed[keyId]);

  // The archive copy now opens with that record unreadable, and refuses it.
  const restored = openStore(archive);
  assert.equal(restored.state.inquiries[doomed.inquiry_id].lifecycle, "ARCHIVE_KEY_DESTROYED");
  assert.throws(() => restored.read(doomed.inquiry_id, as("reviewer")), /archive key was destroyed/);
  assert.throws(() => restored.export(doomed.inquiry_id, as("reviewer")), /archive key was destroyed/);
  assert.ok(!JSON.stringify(restored.state).includes(SENTINEL));
  // Specimen: the other record in the same archive copy is untouched.
  assert.equal(restored.read(kept.inquiry_id, as("reviewer")).inquiry_id, kept.inquiry_id);
});

test("a sealed record cannot be moved onto another record", async () => {
  const f = fresh();
  const a = await f.store.accept(packageWith("record a", "archive-a"), "e1-004", as("receiver"), scoping());
  const b = await f.store.accept(packageWith("record b", "archive-b"), "e1-005", as("receiver"), scoping());
  const onDisk = JSON.parse(fs.readFileSync(f.file, "utf8"));
  onDisk.inquiries[b.inquiry_id].sealed = onDisk.inquiries[a.inquiry_id].sealed;
  fs.writeFileSync(f.file, JSON.stringify(onDisk));
  assert.throws(() => openStore(f.file), /unable to authenticate data|Unsupported state/);
});

test("a store written before E1 is sealed at rest, and says what it could not reach", async () => {
  const f = fresh();
  const receipt = await f.store.accept(packageWith(SENTINEL + " pre-E1 plaintext", "archive-legacy"), "e1-006", as("receiver"), scoping());
  // A pre-E1 store: the plaintext v3 state, as the receiver wrote it before E1.
  const legacy = JSON.parse(JSON.stringify(f.store.state));
  for (const record of Object.values(legacy.inquiries)) delete record.archive_key_id;
  fs.writeFileSync(f.file, JSON.stringify(legacy));
  // Specimen: the plaintext is on disk before sealing.
  assert.ok(fs.readFileSync(f.file, "utf8").includes(SENTINEL));
  const reopened = openStore(f.file);
  assert.equal(reopened.plaintextAtRest, true);
  assert.equal(reopened.sealAtRest(), true);
  assert.ok(!fs.readFileSync(f.file, "utf8").includes(SENTINEL));
  assert.equal(reopened.sealAtRest(), false);
  assert.ok(openStore(f.file).read(receipt.inquiry_id, as("reviewer")).raw_json.includes(SENTINEL));
});

test("two handles on one keyring neither lose a key nor bring a destroyed one back", () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "carbon-archive-keys-"));
  const file = path.join(directory, "keys.json");
  const first = ArchiveKeyring.open(file);
  const second = ArchiveKeyring.open(file);
  const kept = first.create();
  const doomed = second.create();
  // Neither write dropped the other's key.
  assert.equal(ArchiveKeyring.open(file).status(kept), "LIVE");
  assert.equal(ArchiveKeyring.open(file).status(doomed), "LIVE");
  first.destroy(doomed);
  // The second handle still remembers the key; writing must not restore it.
  second.create();
  assert.equal(ArchiveKeyring.open(file).status(doomed), "DESTROYED");
  assert.equal(ArchiveKeyring.open(file).status(kept), "LIVE");
});

test("the receiver will not start without a keyring, or with one beside the store", () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "carbon-archive-server-"));
  const users = path.join(directory, "users.json");
  fs.writeFileSync(users, JSON.stringify(DIRECTORY.accounts));
  const run = (extra) =>
    childProcess.spawnSync(process.execPath, [path.join(ROOT, "tools/team_intake_server.cjs")], {
      env: {
        PATH: process.env.PATH,
        CARBON_TEAM_INTAKE_STORE: path.join(directory, "store.json"),
        CARBON_TEAM_USERS_FILE: users,
        CARBON_TEAM_INTAKE_PORT: "0",
        ...extra,
      },
      encoding: "utf8",
      timeout: 5000,
    });
  const missing = run({});
  assert.notEqual(missing.status, 0);
  assert.match(missing.stderr, /CARBON_TEAM_ARCHIVE_KEYRING/);
  const beside = run({ CARBON_TEAM_ARCHIVE_KEYRING: path.join(directory, "keys.json") });
  assert.notEqual(beside.status, 0);
  assert.match(beside.stderr, /must not live in the store's directory/);
});
