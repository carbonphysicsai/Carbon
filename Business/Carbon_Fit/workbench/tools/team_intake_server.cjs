"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const F = require("../src/engine.js");
const { DurableIntakeStore } = require("./team_intake_store.cjs");

function loadUsers(usersPath) {
  const users = JSON.parse(fs.readFileSync(path.resolve(usersPath), "utf8"));
  if (!Array.isArray(users) || !users.length) throw Error("Named users are required");
  return users;
}

function authenticator(users) {
  return function authenticate(request) {
    const match = /^Bearer ([A-Za-z0-9._~-]{20,300})$/.exec(
      request.headers.authorization || "",
    );
    if (!match) throw Error("Authentication required");
    const digest = crypto.createHash("sha256").update(match[1]).digest("hex");
    const user = users.find(
      (candidate) =>
        typeof candidate.token_sha256 === "string" &&
        /^[0-9a-f]{64}$/.test(candidate.token_sha256) &&
        crypto.timingSafeEqual(
          Buffer.from(candidate.token_sha256),
          Buffer.from(digest),
        ),
    );
    if (!user) throw Error("Authentication failed");
    return { id: user.principal, roles: user.roles };
  };
}

function body(request) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    request.on("data", (chunk) => {
      size += chunk.length;
      if (size > 130_000) {
        // Stop reading, but leave the socket alive so the caller still receives
        // the refusal. Destroying it here left a submitter with a reset
        // connection and no way to learn that the brief was too large.
        request.pause();
        const error = Error("Request body exceeds 130 KB");
        error.status = 413;
        reject(error);
        return;
      }
      chunks.push(chunk);
    });
    request.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    request.on("error", reject);
  });
}

function send(response, status, value) {
  response.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
  });
  response.end(JSON.stringify(value) + "\n");
}

function createIntakeServer({ store, users }) {
  const authenticate = authenticator(users);
  return http.createServer(async (request, response) => {
    try {
      const principal = authenticate(request);
      const url = new URL(request.url, "http://127.0.0.1");
      if (request.method === "POST" && url.pathname === "/private/intake") {
        const raw = await body(request);
        const key = request.headers["idempotency-key"];
        return send(response, 201, await store.accept(raw, key, principal));
      }
      if (request.method === "GET" && url.pathname === "/private/outbox")
        return send(response, 200, { events: store.listOutbox(principal) });
      const outboxMatch =
        /^\/private\/outbox\/([A-Za-z0-9._:-]+)\/attempt$/.exec(url.pathname);
      if (outboxMatch && request.method === "POST") {
        // Retried by the operator and observable either way. With no configured
        // transport the attempt is recorded as a failure rather than a delivery.
        const event = await store.processOutbox(outboxMatch[1], null, principal);
        return send(response, event.status === "DELIVERED" ? 200 : 502, event);
      }
      const exportMatch =
        /^\/private\/intake\/([A-Za-z0-9._:-]+)\/export$/.exec(url.pathname);
      if (exportMatch && request.method === "GET")
        return send(response, 200, store.export(exportMatch[1], principal));
      const match = /^\/private\/intake\/([A-Za-z0-9._:-]+)$/.exec(url.pathname);
      if (match && request.method === "GET")
        return send(response, 200, store.read(match[1], principal));
      if (match && request.method === "PATCH") {
        const patch = F.strictJsonParse(await body(request), {
          maxBytes: 130_000,
          maxDepth: 8,
        });
        return send(
          response,
          200,
          store.update(match[1], Number(request.headers["if-match"]), patch, principal),
        );
      }
      if (match && request.method === "DELETE")
        return send(response, 200, store.delete(match[1], principal));
      send(response, 404, { error: "NOT_FOUND" });
    } catch (error) {
      const message = String(error.message || error);
      const status =
        error.status ||
        (/Authentication|authorized/.test(message)
          ? 403
          : /not found/i.test(message)
            ? 404
            : /conflict/i.test(message)
              ? 409
              : 400);
      // A refused oversized body leaves the request unread. Answer first, then
      // release the connection, so the caller always sees why it was refused.
      if (!request.readableEnded)
        response.on("finish", () => request.destroy());
      send(response, status, { error: message });
    }
  });
}

function main() {
  const storePath = process.env.CARBON_TEAM_INTAKE_STORE;
  const usersPath = process.env.CARBON_TEAM_USERS_FILE;
  if (!storePath || !usersPath)
    throw Error("Set CARBON_TEAM_INTAKE_STORE and CARBON_TEAM_USERS_FILE");
  // Configuring a destination records where a notification would go. It is not a
  // mailbox credential, a sender, or permission to contact anyone; this process
  // never opens an outbound connection.
  const store = new DurableIntakeStore(storePath, {
    destination: process.env.CARBON_TEAM_NOTIFY_DESTINATION,
  });
  const port = Number(process.env.CARBON_TEAM_INTAKE_PORT || "8789");
  createIntakeServer({ store, users: loadUsers(usersPath) }).listen(
    port,
    "127.0.0.1",
    () => {
      process.stdout.write(
        `Carbon private synthetic intake listening on http://127.0.0.1:${port}\n`,
      );
    },
  );
}

module.exports = { createIntakeServer, loadUsers };

if (require.main === module) main();
