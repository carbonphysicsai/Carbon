"use strict";
// E6, decision 2: sealing a package to the intake key. Tested with throwaway
// keys generated here; the real key is the owner's to generate.
const test = require("node:test");
const assert = require("node:assert/strict");
const childProcess = require("node:child_process");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
if (!globalThis.crypto) globalThis.crypto = crypto.webcrypto;
const S = require("../src/intake_seal.js");

const TOOL = path.join(__dirname, "../tools/intake_key.cjs");
const SENTINEL = "SEALSENTINELCLIENTPARAMETER viscosity 0.0123456789";
const to = (pair) => S.recipient(S.publicRecord(pair));
const run = (args) => childProcess.spawnSync(process.execPath, [TOOL, ...args], { encoding: "utf8" });

test("a sealed package opens with its key, and holds none of its plaintext", async () => {
  const pair = await S.generateKeyPair();
  const sealed = await S.seal(SENTINEL, await to(pair));
  const onDisk = JSON.stringify(sealed);
  assert.equal(sealed.schema, S.SCHEMA);
  assert.equal(sealed.key_id, pair.key_id);
  assert.ok(!onDisk.includes("SEALSENTINEL") && !onDisk.includes("0.0123456789"));
  // Specimen: opened with the right key, the plaintext is exactly what went in.
  assert.equal(await S.open(sealed, pair.private_pkcs8, pair.public_spki), SENTINEL);
  // A fresh sender key per package: the same text seals differently each time.
  assert.notEqual((await S.seal(SENTINEL, await to(pair))).ciphertext, sealed.ciphertext);
});

test("a package sealed to another key is named, not tried", async () => {
  const first = await S.generateKeyPair();
  const second = await S.generateKeyPair();
  const sealed = await S.seal(SENTINEL, await to(first));
  await assert.rejects(S.open(sealed, second.private_pkcs8, second.public_spki), new RegExp("sealed to " + first.key_id));
});

test("an altered package does not authenticate", async () => {
  const pair = await S.generateKeyPair();
  const sealed = await S.seal(SENTINEL, await to(pair));
  const flip = (text) => { const bytes = Buffer.from(text, "base64"); bytes[0] ^= 1; return bytes.toString("base64"); };
  for (const field of ["ciphertext", "nonce", "salt"])
    await assert.rejects(S.open({ ...sealed, [field]: flip(sealed[field]) }, pair.private_pkcs8, pair.public_spki), /does not authenticate/, field);
  await assert.rejects(S.open({ ...sealed, extra: 1 }, pair.private_pkcs8, pair.public_spki), /Not a carbon.intake-sealed.v1/);
});

test("the fingerprint is stable and readable, and names the key", async () => {
  const pair = await S.generateKeyPair();
  assert.equal(await S.fingerprint(pair.public_spki), pair.fingerprint);
  assert.match(pair.fingerprint, /^([0-9a-f]{4} ){15}[0-9a-f]{4}$/);
  assert.equal(pair.key_id, "intake-key-" + pair.fingerprint.replace(/ /g, "").slice(0, 32));
});

test("the key tool writes the private key 0600, never overwrites, and prints no key material", async () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "carbon-intake-key-"));
  const privateFile = path.join(directory, "private", "intake-key.json");
  const publicFile = path.join(directory, "intake-key.public.json");
  const generated = run(["generate", "--private", privateFile, "--public", publicFile]);
  assert.equal(generated.status, 0, generated.stderr);
  const key = JSON.parse(fs.readFileSync(privateFile, "utf8"));
  assert.equal(fs.statSync(privateFile).mode & 0o777, 0o600);
  assert.ok(!generated.stdout.includes(key.private_pkcs8));
  assert.deepEqual(Object.keys(JSON.parse(generated.stdout)).sort(), ["fingerprint", "key_id"]);
  assert.ok(!fs.readFileSync(publicFile, "utf8").includes(key.private_pkcs8));
  // Never overwrites an existing key.
  assert.notEqual(run(["generate", "--private", privateFile, "--public", publicFile + ".2"]).status, 0);

  // Unseal: a package sealed to the published key opens into a new 0600 file.
  const sealedFile = path.join(directory, "package.carbon-sealed");
  fs.writeFileSync(sealedFile, JSON.stringify(await S.seal(SENTINEL, await S.recipient(JSON.parse(fs.readFileSync(publicFile, "utf8"))))));
  const out = path.join(directory, "opened", "package.json");
  const opened = run(["unseal", "--key", privateFile, "--in", sealedFile, "--out", out]);
  assert.equal(opened.status, 0, opened.stderr);
  assert.equal(fs.readFileSync(out, "utf8"), SENTINEL);
  assert.equal(fs.statSync(out).mode & 0o777, 0o600);
  assert.ok(!opened.stdout.includes("SEALSENTINEL"));
  // A private key file anyone else can read is refused.
  fs.chmodSync(privateFile, 0o644);
  const unsafe = run(["unseal", "--key", privateFile, "--in", sealedFile, "--out", out + ".2"]);
  assert.notEqual(unsafe.status, 0);
  assert.match(unsafe.stderr, /0600/);
});

test("only a recipient built from a published record can be sealed to", async () => {
  const pair = await S.generateKeyPair();
  const record = S.publicRecord(pair);
  // Specimen: the published record builds a recipient that seals and opens.
  const built = await S.recipient(record);
  assert.equal(built.fingerprint, pair.fingerprint);
  assert.equal(await S.open(await S.seal(SENTINEL, built), pair.private_pkcs8, pair.public_spki), SENTINEL);
  // A valid key, passed in its raw form or as a look-alike object, is refused:
  // it did not come through the record check.
  await assert.rejects(S.seal(SENTINEL, pair.public_spki), /recipient built by recipient\(\)/);
  await assert.rejects(S.seal(SENTINEL, { ...built }), /recipient built by recipient\(\)/);
});

test("a key record is refused when it is private, open, or mislabelled", async () => {
  const pair = await S.generateKeyPair();
  const other = await S.generateKeyPair();
  const record = S.publicRecord(pair);
  // The private key file itself, the mistake most likely to be made by hand.
  await assert.rejects(S.recipient({ schema: "carbon.intake-key.v1", created_at: "2026-09-24T00:00:00Z", ...pair }), /intake private key/);
  await assert.rejects(S.recipient({ ...record, note: "extra" }), /Not a carbon.intake-key.v1-public record/);
  await assert.rejects(S.recipient({ ...record, schema: "carbon.intake-key.v1" }), /Not a carbon.intake-key.v1-public record/);
  // A label copied from another key does not travel with this one.
  await assert.rejects(S.recipient({ ...record, fingerprint: other.fingerprint }), /fingerprint does not match its key/);
  await assert.rejects(S.recipient({ ...record, key_id: other.key_id }), /key_id does not match its key/);
  await assert.rejects(S.recipient({ ...record, public_spki: "not a key" }), /Invalid sealed package encoding/);
});

test("the published intake key is the one the owner generated on 2026-09-24", async () => {
  // Pinned to the fingerprint the owner confirmed. A rotation changes this line
  // deliberately, together with the Data Handling Statement.
  const OWNER_CONFIRMED = "5a38 c3ea bbd2 dd56 ce57 d3e1 f2c5 b1f1 6cd5 c1e0 f5bc 62a8 bb62 9699 8eec 5c18";
  const record = JSON.parse(fs.readFileSync(path.join(__dirname, "../data/intake_public_key.json"), "utf8"));
  const built = await S.recipient(record);
  assert.equal(built.fingerprint, OWNER_CONFIRMED);
  assert.equal(built.key_id, "intake-key-5a38c3eabbd2dd56ce57d3e1f2c5b1f1");
  const sealed = await S.seal(SENTINEL, built);
  assert.equal(sealed.key_id, built.key_id);
  assert.ok(!JSON.stringify(sealed).includes("SEALSENTINEL"));
});
