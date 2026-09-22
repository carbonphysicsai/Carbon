"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const F = require("../src/engine.js");
const { DurableIntakeStore } = require("./team_intake_store.cjs");
const { StaffDirectory } = require("./team_staff_directory.cjs");

function loadUsers(usersPath) {
  return StaffDirectory.load(usersPath);
}

function authenticator(users) {
  // The directory issues the principal. This function no longer builds one,
  // which is the point: there is now no code path that produces a principal
  // without a credential that matched an account.
  const directory = users instanceof StaffDirectory ? users : new StaffDirectory(users);
  return (request) => directory.authenticate(request.headers.authorization);
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
        // 502 says a gateway was reached and misbehaved. With no destination
        // configured nothing was reached, and answering 502 sends an operator
        // looking for a network fault that does not exist. 501 says this
        // server cannot perform the delivery at all, which is the true state
        // and is distinguishable from a real upstream failure later.
        const status =
          event.last_outcome === "DELIVERED"
            ? 200
            : event.last_outcome === "NOT_ATTEMPTED_NO_TRANSPORT"
              ? 501
              : 502;
        return send(response, status, event);
      }
      if (request.method === "GET" && url.pathname === "/private/capacity")
        return send(response, 200, store.capacity(principal));
      if (request.method === "GET" && url.pathname === "/private/intake")
        return send(response, 200, {
          inquiries: store.search(principal, {
            includeArchived: url.searchParams.get("archived") === "include",
          }),
        });
      const retentionMatch =
        /^\/private\/intake\/([A-Za-z0-9._:-]+)\/(archive|restore|deletion-exception)$/
          .exec(url.pathname);
      if (retentionMatch && request.method === "POST") {
        const [, inquiryId, action] = retentionMatch;
        if (action === "archive")
          return send(response, 200, store.archive(inquiryId, principal));
        if (action === "restore")
          return send(response, 200, store.restore(inquiryId, principal));
        // Deletion is the exception to archival retention, so the approval is
        // its own request with its own role. Without this route the delete
        // endpoint below is unreachable, which is the shape of the problem:
        // a precondition added at one layer and not served at the other.
        const approval = F.strictJsonParse(await body(request), {
          maxBytes: 8_000,
          maxDepth: 4,
        });
        return send(
          response,
          201,
          store.approveDeletionException(
            inquiryId,
            { approver: approval.approver, reason: approval.reason },
            principal,
          ),
        );
      }
      const exportMatch =
        /^\/private\/intake\/([A-Za-z0-9._:-]+)\/export$/.exec(url.pathname);
      if (exportMatch && request.method === "GET")
        return send(
          response,
          200,
          store.export(exportMatch[1], principal, {
            includeArchived: url.searchParams.get("archived") === "include",
          }),
        );
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
              : // A relayed export that the store had no room for was not a bad
                // request, and telling the relaying receiver it was sends them
                // to correct a package that is fine.
                /byte ceiling/.test(message)
                ? 507
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
  // Exactly one receiver process per store file. Every accepted inquiry
  // rewrites the whole file, so a second process would not interleave with
  // this one, it would overwrite its records. Refused here, before the port is
  // bound, so the failure is a start that did not happen rather than two
  // receivers quietly disagreeing about the contents of one file.
  store.acquireWriterLock();
  const release = () => {
    store.releaseWriterLock();
  };
  process.on("exit", release);
  for (const signal of ["SIGINT", "SIGTERM"])
    process.on(signal, () => {
      release();
      process.exit(0);
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
