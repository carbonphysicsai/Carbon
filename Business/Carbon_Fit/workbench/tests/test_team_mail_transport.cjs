"use strict";
// E6: the outbox's mail transport, against a local SMTP server. No real mail
// server, account or credential is involved: a missing credential and a wrong
// one are both testable without one, and the credential used here is a
// synthetic specimen that exists only inside this process.
const test = require("node:test");
const assert = require("node:assert/strict");
const childProcess = require("node:child_process");
const crypto = require("node:crypto");
const fs = require("node:fs");
const net = require("node:net");
const os = require("node:os");
const path = require("node:path");
const tls = require("node:tls");
if (!globalThis.crypto) globalThis.crypto = crypto.webcrypto;
const { StaffDirectory, totp } = require("../tools/team_staff_directory.cjs");
const { createIntakeServer } = require("../tools/team_intake_server.cjs");
const { smtpConfigFrom, smtpTransport } = require("../tools/team_smtp_transport.cjs");
const { RELEASE, enrolled, mailed, openStore, principalFor, scoping, secretFor } = require("./staff_fixture.cjs");
const I = require("../src/intake.js");

const ROOT = path.resolve(__dirname, "..");
const TEAM = "carbon-fit";
const SPECIMEN = "E6-SPECIMEN-CREDENTIAL-" + crypto.randomBytes(12).toString("hex");
const CLIENT_WORDS = "E6SENTINELCLIENTWORDS";
const TOKENS = { receiver: "mail-receiver-token-0001", notifier: "mail-notifier-token-0001", reviewer: "mail-reviewer-token-0001" };
const ACCOUNTS = [
  enrolled("mail-receiver", TEAM, ["INTAKE_RECEIVER"], TOKENS.receiver),
  enrolled("mail-notifier", TEAM, ["NOTIFICATION_OPERATOR"], TOKENS.notifier),
  enrolled("mail-reviewer", TEAM, ["TEAM_REVIEWER"], TOKENS.reviewer),
];
const DIRECTORY = new StaffDirectory(ACCOUNTS);
const as = (name) => principalFor(DIRECTORY, TOKENS[name]);

// A throwaway certificate for the local server, made for this run only.
const CERT_DIR = fs.mkdtempSync(path.join(os.tmpdir(), "carbon-smtp-cert-"));
childProcess.execFileSync("openssl", [
  "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", "/CN=localhost",
  "-addext", "subjectAltName=DNS:localhost",
  "-keyout", path.join(CERT_DIR, "key.pem"), "-out", path.join(CERT_DIR, "cert.pem"),
], { stdio: "ignore" });
const CERT = fs.readFileSync(path.join(CERT_DIR, "cert.pem"));
const KEY = fs.readFileSync(path.join(CERT_DIR, "key.pem"));

/** A minimal SMTP server: STARTTLS optional, AUTH PLAIN checked against `expected`. */
async function smtpServer({ offerTls = true, expected = SPECIMEN } = {}) {
  const seen = { connections: 0, credentials: [], plaintextAuth: false, messages: [], recipients: [] };
  const server = net.createServer((raw) => {
    seen.connections += 1;
    let socket = raw, secure = false, buffer = "", inData = false, data = "";
    const reply = (line) => socket.write(line + "\r\n");
    const onLine = (line) => {
      if (inData) {
        if (line === ".") {
          inData = false;
          seen.messages.push(data);
          data = "";
          return reply("250 queued");
        }
        data += line + "\r\n";
        return;
      }
      const [verb, ...rest] = line.split(" ");
      switch (verb.toUpperCase()) {
        case "EHLO":
          if (offerTls && !secure) return reply("250-localhost\r\n250-STARTTLS\r\n250 AUTH PLAIN");
          return reply("250-localhost\r\n250 AUTH PLAIN");
        case "STARTTLS":
          reply("220 go ahead");
          socket.removeAllListeners("data");
          socket = new tls.TLSSocket(raw, { isServer: true, key: KEY, cert: CERT });
          secure = true;
          buffer = "";
          socket.on("data", onData);
          socket.on("error", () => {});
          return;
        case "AUTH": {
          if (!secure) seen.plaintextAuth = true;
          const decoded = Buffer.from(rest[1] || "", "base64").toString("utf8").split("\u0000");
          seen.credentials.push(decoded[2]);
          return reply(decoded[2] === expected ? "235 ok" : "535 5.7.8 credentials rejected " + decoded[2]);
        }
        case "MAIL":
          return reply("250 ok");
        case "RCPT":
          seen.recipients.push(line);
          return reply("250 ok");
        case "DATA":
          inData = true;
          return reply("354 go");
        case "QUIT":
          reply("221 bye");
          return socket.end();
        default:
          return reply("502 unknown");
      }
    };
    const onData = (chunk) => {
      buffer += chunk.toString("utf8");
      let index;
      while ((index = buffer.indexOf("\r\n")) >= 0) {
        const line = buffer.slice(0, index);
        buffer = buffer.slice(index + 2);
        onLine(line);
      }
    };
    raw.on("data", onData);
    raw.on("error", () => {});
    reply("220 localhost ESMTP synthetic");
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  return { seen, port: server.address().port, close: () => server.close() };
}

function credentialFile(value = SPECIMEN, mode = 0o600) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "carbon-smtp-credential-"));
  const file = path.join(directory, "credential");
  fs.writeFileSync(file, value + "\n", { mode });
  fs.chmodSync(file, mode);
  return file;
}

const environment = (port, credential) => ({
  CARBON_TEAM_SMTP_HOST: "localhost",
  CARBON_TEAM_SMTP_PORT: String(port),
  CARBON_TEAM_SMTP_USER: "intake-synthetic@example.test",
  CARBON_TEAM_SMTP_FROM: "notifications-synthetic@example.test",
  CARBON_TEAM_NOTIFY_DESTINATION: "team-synthetic@example.test",
  ...(credential === undefined ? {} : { CARBON_TEAM_SMTP_CREDENTIAL_FILE: credential }),
});

const transportFor = (port, credential) =>
  smtpTransport(smtpConfigFrom(environment(port, credential)), {
    connect: (options, ready) => net.connect({ host: "127.0.0.1", port: options.port }, ready),
    tlsOptions: { ca: CERT, servername: "localhost" },
  });

function packageWith(words) {
  const brief = JSON.parse(fs.readFileSync(path.join(ROOT, "intake/fixtures/existing_method_v1.json"), "utf8"));
  brief.draft_id = "mail-draft-" + crypto.randomBytes(4).toString("hex");
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

async function pendingEvent() {
  const store = openStore(path.join(fs.mkdtempSync(path.join(os.tmpdir(), "carbon-mail-store-")), "store.json"), { destination: "team-synthetic@example.test" });
  const receipt = await store.accept(packageWith(CLIENT_WORDS), "mail-" + crypto.randomBytes(4).toString("hex"), as("receiver"), scoping(), mailed());
  return { store, eventId: "notify-" + receipt.inquiry_id, receipt };
}

test("configuration: none is none, partial is refused, and mail goes only to the sender's own domain", () => {
  assert.equal(smtpConfigFrom({}), null);
  assert.throws(() => smtpConfigFrom({ CARBON_TEAM_SMTP_HOST: "localhost" }), /set CARBON_TEAM_SMTP_PORT, CARBON_TEAM_SMTP_USER, CARBON_TEAM_SMTP_FROM/);
  assert.throws(
    () => smtpConfigFrom({ ...environment(25), CARBON_TEAM_NOTIFY_DESTINATION: "someone@elsewhere.test" }),
    /only to an address on the sender's own domain/,
  );
  // Specimen: the same configuration with an own-domain destination is accepted.
  assert.equal(smtpConfigFrom(environment(25)).to, "team-synthetic@example.test");
});

test("a missing credential fails closed, attempts nothing, and is not a rejected one", async () => {
  const server = await smtpServer();
  try {
    const missing = await pendingEvent();
    const absent = await missing.store.processOutbox(missing.eventId, transportFor(server.port, undefined), as("notifier"));
    assert.equal(absent.last_outcome, "NOT_ATTEMPTED_NO_CREDENTIAL");
    assert.equal(absent.attempts, 0);
    assert.match(absent.last_error, /CARBON_TEAM_SMTP_CREDENTIAL_FILE/);
    const gone = await missing.store.processOutbox(missing.eventId, transportFor(server.port, "/nonexistent/credential"), as("notifier"));
    assert.equal(gone.last_outcome, "NOT_ATTEMPTED_NO_CREDENTIAL");
    const unsafe = await missing.store.processOutbox(missing.eventId, transportFor(server.port, credentialFile(SPECIMEN, 0o644)), as("notifier"));
    assert.equal(unsafe.last_outcome, "NOT_ATTEMPTED_CREDENTIAL_UNSAFE");
    assert.equal(server.seen.connections, 0, "nothing was contacted without a usable credential");

    // The other state: a configured credential the server rejects.
    const wrong = await pendingEvent();
    const rejected = await wrong.store.processOutbox(wrong.eventId, transportFor(server.port, credentialFile("not-the-right-one")), as("notifier"));
    assert.equal(rejected.last_outcome, "CREDENTIAL_REJECTED");
    assert.equal(rejected.attempts, 1);
    assert.notEqual(rejected.last_outcome, absent.last_outcome);
  } finally {
    server.close();
  }
});

test("the credential is never sent over a connection that did not upgrade to TLS", async () => {
  const server = await smtpServer({ offerTls: false });
  try {
    const event = await pendingEvent();
    const refused = await event.store.processOutbox(event.eventId, transportFor(server.port, credentialFile()), as("notifier"));
    assert.equal(refused.last_outcome, "TRANSPORT_REFUSED_NO_TLS");
    assert.equal(server.seen.plaintextAuth, false);
    assert.deepEqual(server.seen.credentials, []);
    // Specimen: the connection really happened; only the credential was withheld.
    assert.equal(server.seen.connections, 1);
  } finally {
    server.close();
  }
});

test("a delivery carries the notification and no client words, to the configured address", async () => {
  const server = await smtpServer();
  try {
    const event = await pendingEvent();
    // Specimen: the client's words really are in the record.
    assert.ok(event.store.read(event.receipt.inquiry_id, as("reviewer")).raw_json.includes(CLIENT_WORDS));
    const delivered = await event.store.processOutbox(event.eventId, transportFor(server.port, credentialFile()), as("notifier"));
    assert.equal(delivered.last_outcome, "DELIVERED");
    assert.equal(delivered.status, "DELIVERED");
    assert.equal(server.seen.messages.length, 1);
    assert.ok(server.seen.messages[0].includes(event.receipt.inquiry_id));
    assert.ok(!server.seen.messages[0].includes(CLIENT_WORDS));
    assert.deepEqual(server.seen.recipients, ["RCPT TO:<team-synthetic@example.test>"]);
  } finally {
    server.close();
  }
});

test("the credential reaches no record, response, export, log or error, on any path", async () => {
  const captured = [];
  const originals = { log: console.log, error: console.error, warn: console.warn, out: process.stdout.write, err: process.stderr.write };
  const capture = (...parts) => captured.push(parts.map(String).join(" "));
  console.log = console.error = console.warn = capture;
  process.stdout.write = function (chunk, ...rest) { captured.push(String(chunk)); return originals.out.call(this, chunk, ...rest); };
  process.stderr.write = function (chunk, ...rest) { captured.push(String(chunk)); return originals.err.call(this, chunk, ...rest); };
  const good = await smtpServer();
  const noTls = await smtpServer({ offerTls: false });
  const rejecting = await smtpServer({ expected: "something-else-entirely" });
  const outputs = [];
  const stores = [];
  try {
    const specimenFile = credentialFile();
    const unsafeFile = credentialFile(SPECIMEN, 0o644);
    const closed = await smtpServer();
    const closedPort = closed.port;
    closed.close(); // nothing listens there now, so the connection is refused
    const scenarios = [
      transportFor(good.port, specimenFile),
      transportFor(noTls.port, specimenFile),
      transportFor(rejecting.port, specimenFile),
      transportFor(good.port, unsafeFile),
      transportFor(closedPort, specimenFile),
    ];
    for (const transport of scenarios) {
      const event = await pendingEvent();
      stores.push(event.store);
      try {
        outputs.push(JSON.stringify(await event.store.processOutbox(event.eventId, transport, as("notifier"))));
      } catch (error) {
        outputs.push(String(error.stack || error));
      }
      outputs.push(JSON.stringify(event.store.listOutbox(as("notifier"))));
      outputs.push(JSON.stringify(event.store.export(event.receipt.inquiry_id, as("reviewer"), RELEASE)));
    }
    // And over HTTP, through the receiver's own outbox route.
    const event = await pendingEvent();
    stores.push(event.store);
    const http = createIntakeServer({ store: event.store, users: ACCOUNTS, transport: transportFor(rejecting.port, specimenFile) });
    await new Promise((resolve) => http.listen(0, "127.0.0.1", resolve));
    const base = `http://127.0.0.1:${http.address().port}`;
    const opened = await fetch(base + "/private/session", {
      method: "POST",
      headers: { authorization: "Bearer " + TOKENS.notifier, "content-type": "application/json" },
      body: JSON.stringify({ code: totp(secretFor(TOKENS.notifier), Date.now()) }),
    });
    const session = "Bearer " + (await opened.json()).session_token;
    const attempt = await fetch(`${base}/private/outbox/${event.eventId}/attempt`, { method: "POST", headers: { authorization: session } });
    assert.equal(attempt.status, 502);
    outputs.push(await attempt.text());
    outputs.push(await (await fetch(`${base}/private/outbox`, { headers: { authorization: session } })).text());
    http.close();
  } finally {
    Object.assign(console, { log: originals.log, error: originals.error, warn: originals.warn });
    process.stdout.write = originals.out;
    process.stderr.write = originals.err;
    good.close();
    noTls.close();
    rejecting.close();
  }
  // Specimen: the credential was really in play. The servers received it, over
  // TLS, and the rejecting one even echoed it back in its refusal.
  assert.ok(good.seen.credentials.includes(SPECIMEN));
  assert.ok(rejecting.seen.credentials.includes(SPECIMEN));
  const everything = [
    ...outputs,
    ...captured,
    ...stores.flatMap((store) => [fs.readFileSync(store.filePath, "utf8"), fs.readFileSync(store.keyring.filePath, "utf8"), JSON.stringify(store.state)]),
  ].join("\n");
  assert.ok(everything.length > 1000, "the search covered real output");
  assert.equal(everything.includes(SPECIMEN), false, "the credential reached an output");
  assert.equal(everything.includes(Buffer.from(SPECIMEN).toString("base64")), false, "the encoded credential reached an output");
});
