"use strict";

// E6: the outbox's mail transport. Operator configuration, never a default.
//
// A notification carries the permitted minimal summary and a record path, never
// the client's words. It goes only to an address on the sender's own domain,
// so a configured sender can reach Carbon and nobody else: a configured sender
// is not permission to contact a person.
//
// The credential is read from an operator file at send time. It is never taken
// from the repository, the environment's value or a default. Its absence fails
// closed as its own outcome, distinct from a credential the server rejected.
// It is sent only over a connection that upgraded to TLS, and it can reach no
// log, error, record or export: every failure here is a typed outcome with a
// fixed message, and no server reply text is ever carried, only its code.

const fs = require("node:fs");
const net = require("node:net");
const tls = require("node:tls");

class TransportOutcome extends Error {
  constructor(outcome, message, { attempted }) {
    super(message);
    this.outcome = outcome;
    this.attempted = attempted;
  }
}

const ADDRESS = /^[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+)$/;
const domainOf = (address) => {
  const match = ADDRESS.exec(address || "");
  return match ? match[1].toLowerCase() : null;
};

/**
 * The transport's configuration from operator settings, or null when no mail
 * transport is configured at all (the outbox then reports that, as before).
 * The credential's value is not read here; only where it lives.
 */
function smtpConfigFrom(env) {
  const names = ["CARBON_TEAM_SMTP_HOST", "CARBON_TEAM_SMTP_PORT", "CARBON_TEAM_SMTP_USER", "CARBON_TEAM_SMTP_FROM"];
  if (names.every((name) => !env[name])) return null;
  const missing = names.filter((name) => !env[name]);
  if (missing.length) throw Error("Incomplete mail transport configuration: set " + missing.join(", "));
  const destination = env.CARBON_TEAM_NOTIFY_DESTINATION;
  const port = Number(env.CARBON_TEAM_SMTP_PORT);
  if (!Number.isSafeInteger(port) || port < 1 || port > 65535) throw Error("CARBON_TEAM_SMTP_PORT must be a port number");
  if (!domainOf(env.CARBON_TEAM_SMTP_FROM)) throw Error("CARBON_TEAM_SMTP_FROM must be a mail address");
  if (domainOf(destination) !== domainOf(env.CARBON_TEAM_SMTP_FROM))
    throw Error("A notification goes only to an address on the sender's own domain");
  return {
    host: env.CARBON_TEAM_SMTP_HOST,
    port,
    user: env.CARBON_TEAM_SMTP_USER,
    from: env.CARBON_TEAM_SMTP_FROM,
    to: destination,
    credentialFile: env.CARBON_TEAM_SMTP_CREDENTIAL_FILE || null,
  };
}

function readCredential(file) {
  if (!file) throw new TransportOutcome("NOT_ATTEMPTED_NO_CREDENTIAL", "No mail credential is configured: set CARBON_TEAM_SMTP_CREDENTIAL_FILE", { attempted: false });
  let stat;
  try {
    stat = fs.statSync(file);
  } catch {
    throw new TransportOutcome("NOT_ATTEMPTED_NO_CREDENTIAL", "The configured mail credential file does not exist", { attempted: false });
  }
  if (!stat.isFile() || (stat.mode & 0o077) !== 0)
    throw new TransportOutcome("NOT_ATTEMPTED_CREDENTIAL_UNSAFE", "The mail credential file must be a regular file readable by its owner only (0600)", { attempted: false });
  const value = fs.readFileSync(file, "utf8").replace(/\r?\n$/, "");
  if (!value) throw new TransportOutcome("NOT_ATTEMPTED_NO_CREDENTIAL", "The configured mail credential file is empty", { attempted: false });
  return value;
}

/** A line-oriented SMTP conversation over a socket that may be upgraded. */
function conversation(socket) {
  let buffer = "";
  let waiting = null;
  let failed = null;
  const onData = (chunk) => {
    buffer += chunk.toString("utf8");
    deliver();
  };
  const onError = (error) => {
    failed = error;
    if (waiting) waiting.reject(error);
  };
  const deliver = () => {
    if (!waiting) return;
    const lines = buffer.split("\r\n");
    for (let index = 0; index < lines.length - 1; index++) {
      if (/^\d{3} /.test(lines[index])) {
        const reply = lines.slice(0, index + 1);
        buffer = lines.slice(index + 1).join("\r\n");
        const resolve = waiting.resolve;
        waiting = null;
        resolve({ code: Number(reply[index].slice(0, 3)), lines: reply });
        return;
      }
    }
  };
  const attach = (target) => {
    target.on("data", onData);
    target.on("error", onError);
  };
  attach(socket);
  return {
    attach,
    detach(target) {
      target.removeListener("data", onData);
      target.removeListener("error", onError);
    },
    reply() {
      if (failed) return Promise.reject(failed);
      return new Promise((resolve, reject) => {
        waiting = { resolve, reject };
        deliver();
      });
    },
  };
}

/**
 * An outbox handler that sends one notification over SMTP with STARTTLS.
 * `connect` and `tlsOptions` exist so tests can use a local server; nothing
 * else about the conversation can be changed from outside.
 */
function smtpTransport(config, { connect = net.connect, tlsOptions = {}, timeoutMs = 20_000 } = {}) {
  if (!config) return null;
  return async function send(event) {
    // Read first: without a credential nothing is attempted and nothing counted.
    const credential = readCredential(config.credentialFile);
    let socket;
    const fail = (outcome, message) => new TransportOutcome(outcome, message, { attempted: true });
    try {
      socket = await new Promise((resolve, reject) => {
        const opened = connect({ host: config.host, port: config.port }, () => resolve(opened));
        opened.once("error", reject);
        opened.setTimeout(timeoutMs, () => opened.destroy(Object.assign(Error("timeout"), { code: "ETIMEDOUT" })));
      });
    } catch (error) {
      throw fail("TRANSPORT_FAILED", "Could not reach the mail server (" + (error.code || "connection error") + ")");
    }
    const talk = conversation(socket);
    let active = socket;
    const expect = async (codes, step) => {
      let reply;
      try {
        reply = await talk.reply();
      } catch (error) {
        throw fail("TRANSPORT_FAILED", "The mail server connection failed during " + step + " (" + (error.code || "error") + ")");
      }
      if (!codes.includes(reply.code)) {
        if (step === "authentication" && reply.code === 535)
          throw fail("CREDENTIAL_REJECTED", "The mail server rejected the configured credential (535)");
        throw fail("TRANSPORT_FAILED", "The mail server refused " + step + " (" + reply.code + ")");
      }
      return reply;
    };
    const write = (line) => active.write(line + "\r\n");
    try {
      await expect([220], "greeting");
      write("EHLO carbon-private-intake");
      const capabilities = await expect([250], "EHLO");
      if (!capabilities.lines.some((line) => /^250[- ]STARTTLS\b/i.test(line)))
        throw fail("TRANSPORT_REFUSED_NO_TLS", "The mail server offered no STARTTLS, so the credential was not sent");
      write("STARTTLS");
      await expect([220], "STARTTLS");
      talk.detach(socket);
      active = await new Promise((resolve, reject) => {
        const upgraded = tls.connect({ socket, servername: config.host, ...tlsOptions }, () => resolve(upgraded));
        upgraded.once("error", reject);
      }).catch((error) => {
        throw fail("TRANSPORT_REFUSED_NO_TLS", "The mail server's TLS could not be verified (" + (error.code || "tls error") + "), so the credential was not sent");
      });
      talk.attach(active);
      write("EHLO carbon-private-intake");
      await expect([250], "EHLO after STARTTLS");
      write("AUTH PLAIN " + Buffer.from("\u0000" + config.user + "\u0000" + credential).toString("base64"));
      await expect([235], "authentication");
      write("MAIL FROM:<" + config.from + ">");
      await expect([250], "sender");
      write("RCPT TO:<" + config.to + ">");
      await expect([250, 251], "recipient");
      write("DATA");
      await expect([354], "message");
      const body = JSON.stringify(event.payload || event.notification || {}, null, 2).replace(/^\./gm, "..");
      write(
        [
          "From: <" + config.from + ">",
          "To: <" + config.to + ">",
          "Subject: Carbon private intake: " + (event.inquiry_id || "notification"),
          "Date: " + new Date().toUTCString(),
          "Content-Type: application/json; charset=utf-8",
          "",
          body,
          ".",
        ].join("\r\n"),
      );
      await expect([250], "delivery");
      write("QUIT");
    } finally {
      active.end();
      if (active !== socket) socket.destroy();
    }
  };
}

module.exports = { TransportOutcome, smtpConfigFrom, smtpTransport };
