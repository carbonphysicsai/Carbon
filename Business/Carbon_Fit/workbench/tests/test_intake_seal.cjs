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
const run = (args) => childProcess.spawnSync(process.execPath, [TOOL, ...args], { encoding: "utf8" });

test("a sealed package opens with its key, and holds none of its plaintext", async () => {
  const pair = await S.generateKeyPair();
  const sealed = await S.seal(SENTINEL, pair.public_spki);
  const onDisk = JSON.stringify(sealed);
  assert.equal(sealed.schema, S.SCHEMA);
  assert.equal(sealed.key_id, pair.key_id);
  assert.ok(!onDisk.includes("SEALSENTINEL") && !onDisk.includes("0.0123456789"));
  // Specimen: opened with the right key, the plaintext is exactly what went in.
  assert.equal(await S.open(sealed, pair.private_pkcs8, pair.public_spki), SENTINEL);
  // A fresh sender key per package: the same text seals differently each time.
  assert.notEqual((await S.seal(SENTINEL, pair.public_spki)).ciphertext, sealed.ciphertext);
});

test("a package sealed to another key is named, not tried", async () => {
  const first = await S.generateKeyPair();
  const second = await S.generateKeyPair();
  const sealed = await S.seal(SENTINEL, first.public_spki);
  await assert.rejects(S.open(sealed, second.private_pkcs8, second.public_spki), new RegExp("sealed to " + first.key_id));
});

test("an altered package does not authenticate", async () => {
  const pair = await S.generateKeyPair();
  const sealed = await S.seal(SENTINEL, pair.public_spki);
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
  fs.writeFileSync(sealedFile, JSON.stringify(await S.seal(SENTINEL, JSON.parse(fs.readFileSync(publicFile, "utf8")).public_spki)));
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
