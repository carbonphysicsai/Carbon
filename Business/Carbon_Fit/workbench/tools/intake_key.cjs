#!/usr/bin/env node
"use strict";
// E6, decision 2: the intake key, and opening a sealed package with it.
//
//   node tools/intake_key.cjs generate --private <file> --public <file>
//     The owner runs this once, on the internal machine. The private key file is
//     written 0600 and never printed; keep one encrypted offline copy of it in
//     the owner's password manager. The public file is safe to publish, and the
//     fingerprint it prints is what the Data Handling Statement carries.
//
//   node tools/intake_key.cjs unseal --key <private file> --in <sealed> --out <file>
//     The receiver opens a mailed package on the internal machine, never in the
//     mailbox. The plaintext is written 0600 and never printed.
//
// Neither command prints key material or package content.
const fs = require("node:fs");
const path = require("node:path");
const S = require("../src/intake_seal.js");

const KEY_SCHEMA = "carbon.intake-key.v1";

function argument(args, name) {
  const index = args.indexOf(name);
  if (index < 0 || !args[index + 1]) throw Error("Missing " + name);
  return path.resolve(args[index + 1]);
}

function writeNew(file, text) {
  fs.mkdirSync(path.dirname(file), { recursive: true, mode: 0o700 });
  // Exclusive create: an existing key or plaintext is never overwritten.
  const handle = fs.openSync(file, "wx", 0o600);
  try {
    fs.writeFileSync(handle, text);
    fs.fsyncSync(handle);
  } finally {
    fs.closeSync(handle);
  }
}

function readPrivate(file) {
  const stat = fs.statSync(file);
  if ((stat.mode & 0o077) !== 0) throw Error("The intake private key file must be readable by its owner only (0600)");
  const key = JSON.parse(fs.readFileSync(file, "utf8"));
  if (key.schema !== KEY_SCHEMA) throw Error("Not a " + KEY_SCHEMA + " file");
  return key;
}

async function main(args) {
  const command = args[0];
  if (command === "generate") {
    const privateFile = argument(args, "--private");
    const publicFile = argument(args, "--public");
    const pair = await S.generateKeyPair();
    writeNew(privateFile, JSON.stringify({ schema: KEY_SCHEMA, created_at: new Date().toISOString(), ...pair }, null, 2) + "\n");
    writeNew(publicFile, JSON.stringify(S.publicRecord(pair), null, 2) + "\n");
    return { key_id: pair.key_id, fingerprint: pair.fingerprint };
  }
  if (command === "unseal") {
    const key = readPrivate(argument(args, "--key"));
    const sealed = JSON.parse(fs.readFileSync(argument(args, "--in"), "utf8"));
    const plaintext = await S.open(sealed, key.private_pkcs8, key.public_spki);
    writeNew(argument(args, "--out"), plaintext);
    return { opened: true, key_id: sealed.key_id, bytes: Buffer.byteLength(plaintext) };
  }
  throw Error("Use: generate --private <file> --public <file> | unseal --key <file> --in <sealed> --out <file>");
}

module.exports = { KEY_SCHEMA, main };

if (require.main === module)
  main(process.argv.slice(2)).then(
    (result) => process.stdout.write(JSON.stringify(result) + "\n"),
    (error) => {
      process.stderr.write(String(error.message || error) + "\n");
      process.exitCode = 1;
    },
  );
