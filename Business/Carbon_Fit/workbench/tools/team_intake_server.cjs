"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const F = require("../src/engine.js");
const { DurableIntakeStore, runRetention, transportAtRelay } = require("./team_intake_store.cjs");
const { ArchiveKeyring } = require("./team_archive_keyring.cjs");
const { basisFromHeaders } = require("./team_record_basis.cjs");
const { smtpConfigFrom, smtpTransport } = require("./team_smtp_transport.cjs");
const { AccessControl, StaffDirectory } = require("./team_staff_directory.cjs");
const { scheduledProviderFrom, signedOptIn } = require("./team_model_provider.cjs");

function loadUsers(usersPath) {
  return StaffDirectory.load(usersPath);
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

function createIntakeServer({ store, users, clock, limits, transport = null, modelProvider = null }) {
  // E9: a staff credential alone reaches nothing. It opens a session together
  // with a current second-factor code, and only a live session resolves to a
  // principal. Rate limiting and lockout are applied where that happens.
  const directory = users instanceof StaffDirectory ? users : new StaffDirectory(users);
  const access = new AccessControl(directory, { clock, limits });
  return http.createServer(async (request, response) => {
    try {
      const url = new URL(request.url, "http://127.0.0.1");
      if (url.pathname === "/private/session" && request.method === "POST") {
        const offered = F.strictJsonParse(await body(request), { maxBytes: 1_000, maxDepth: 2 });
        if (!offered || typeof offered !== "object" || Object.keys(offered).join() !== "code")
          throw Object.assign(Error("A session request carries exactly one field, code"), { status: 400 });
        return send(
          response,
          201,
          access.openSession({
            authorization: request.headers.authorization,
            code: offered.code,
            source: request.socket.remoteAddress,
          }),
        );
      }
      if (url.pathname === "/private/session" && request.method === "DELETE") {
        access.closeSession(request.headers.authorization);
        return send(response, 200, { closed: true });
      }
      const principal = access.authenticate(request.headers.authorization);
      if (request.method === "POST" && url.pathname === "/private/intake") {
        // E4: the agreement basis comes from the relay's headers; the body is
        // the client's package and is stored byte for byte.
        const basis = basisFromHeaders(request.headers);
        // E6: how the package arrived is stated at relay, beside it.
        const transport = transportAtRelay(request.headers);
        const raw = await body(request);
        const key = request.headers["idempotency-key"];
        // E7: the export-control reference, when the relay has it; otherwise
        // the record is unreachable until a data steward records one.
        const exportControl = request.headers["x-carbon-export-control-ref"] || null;
        return send(response, 201, await store.accept(raw, key, principal, basis, transport, exportControl));
      }
      const holdMatch = /^\/private\/intake\/([A-Za-z0-9._:-]+)\/hold\/(place|lift)$/.exec(url.pathname);
      if (holdMatch && request.method === "POST") {
        const offered = F.strictJsonParse(await body(request), { maxBytes: 1_000, maxDepth: 2 });
        if (!offered || typeof offered !== "object" || Object.keys(offered).join() !== "reason")
          throw Object.assign(Error("A hold request carries exactly one field, reason"), { status: 400 });
        const act = holdMatch[2] === "place" ? store.placeHold.bind(store) : store.liftHold.bind(store);
        return send(response, 200, act(holdMatch[1], offered, principal));
      }
      const exportControlMatch = /^\/private\/intake\/([A-Za-z0-9._:-]+)\/export-control$/.exec(url.pathname);
      if (exportControlMatch && request.method === "POST") {
        const offered = F.strictJsonParse(await body(request), { maxBytes: 1_000, maxDepth: 2 });
        if (!offered || typeof offered !== "object" || Object.keys(offered).join() !== "ref")
          throw Object.assign(Error("An export-control record carries exactly one field, ref"), { status: 400 });
        return send(response, 200, store.recordExportControl(exportControlMatch[1], offered.ref, principal));
      }
      // External model processing: a per-client switch, off by default. A data
      // steward records the client's signed opt-in; a reviewer then asks one
      // question at a time. Nothing reaches a provider any other way.
      const optInMatch = /^\/private\/intake\/([A-Za-z0-9._:-]+)\/model-opt-in(\/withdraw)?$/.exec(url.pathname);
      if (optInMatch && request.method === "POST") {
        const offered = F.strictJsonParse(await body(request), { maxBytes: 1_000, maxDepth: 2 });
        if (optInMatch[2]) {
          if (!offered || typeof offered !== "object" || Object.keys(offered).join() !== "reason")
            throw Object.assign(Error("A withdrawal carries exactly one field, reason"), { status: 400 });
          return send(response, 200, store.withdrawModelOptIn(optInMatch[1], offered, principal));
        }
        if (!offered || typeof offered !== "object" || Object.keys(offered).sort().join() !== "provider,ref")
          throw Object.assign(Error("An opt-in record carries exactly two fields, provider and ref"), { status: 400 });
        return send(response, 200, store.recordModelOptIn(optInMatch[1], signedOptIn(offered), principal));
      }
      const assistMatch = /^\/private\/intake\/([A-Za-z0-9._:-]+)\/model-assist$/.exec(url.pathname);
      if (assistMatch && request.method === "POST") {
        const offered = F.strictJsonParse(await body(request), { maxBytes: 5_000, maxDepth: 2 });
        if (!offered || typeof offered !== "object" || Object.keys(offered).sort().join() !== "purpose,question")
          throw Object.assign(Error("A model request carries exactly two fields, purpose and question"), { status: 400 });
        try {
          return send(response, 200, await store.modelAssist(assistMatch[1], offered, principal, modelProvider));
        } catch (error) {
          // A typed provider outcome: nothing was reached (501), or the
          // provider was reached and failed (502). The message is fixed text.
          if (error.outcome) error.status = error.attempted ? 502 : 501;
          throw error;
        }
      }
      const transportMatch = /^\/private\/intake\/([A-Za-z0-9._:-]+)\/transport-copy$/.exec(url.pathname);
      if (transportMatch && request.method === "POST") {
        const offered = F.strictJsonParse(await body(request), { maxBytes: 1_000, maxDepth: 2 });
        if (!offered || typeof offered !== "object" || Object.keys(offered).join() !== "state")
          throw Object.assign(Error("A transport-copy record carries exactly one field, state"), { status: 400 });
        return send(response, 200, store.recordTransportCopy(transportMatch[1], offered.state, principal));
      }
      const basisMatch = /^\/private\/intake\/([A-Za-z0-9._:-]+)\/basis$/.exec(url.pathname);
      if (basisMatch && request.method === "POST")
        return send(response, 200, store.attachBasis(basisMatch[1], basisFromHeaders(request.headers), principal));
      if (request.method === "GET" && url.pathname === "/private/outbox")
        return send(response, 200, { events: store.listOutbox(principal) });
      const outboxMatch =
        /^\/private\/outbox\/([A-Za-z0-9._:-]+)\/attempt$/.exec(url.pathname);
      if (outboxMatch && request.method === "POST") {
        // Retried by the operator and observable either way. With no configured
        // transport the attempt is recorded as a failure rather than a delivery.
        const event = await store.processOutbox(outboxMatch[1], transport, principal);
        // 502 says a gateway was reached and misbehaved. With no destination
        // configured nothing was reached, and answering 502 sends an operator
        // looking for a network fault that does not exist. 501 says this
        // server cannot perform the delivery at all, which is the true state
        // and is distinguishable from a real upstream failure later.
        const status =
          event.last_outcome === "DELIVERED"
            ? 200
            : event.last_outcome.startsWith("NOT_ATTEMPTED")
              ? // No transport, no credential, or an unsafe one: nothing was
                // reached. A server that was reached and refused is 502 below.
                501
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
            // E5: who the export is for, and why, are required and logged
            // before anything is returned.
            recipient: {
              kind: request.headers["x-carbon-release-recipient-kind"],
              ref: request.headers["x-carbon-release-recipient-ref"],
            },
            purpose: request.headers["x-carbon-release-purpose"],
          }),
        );
      const releasesMatch = /^\/private\/intake\/([A-Za-z0-9._:-]+)\/releases$/.exec(url.pathname);
      if (releasesMatch && request.method === "POST") {
        const offered = F.strictJsonParse(await body(request), { maxBytes: 4_000, maxDepth: 3 });
        return send(response, 201, store.recordRelease(releasesMatch[1], offered, principal));
      }
      // E2: what the scheduled job would do, and a steward-triggered run.
      if (request.method === "GET" && url.pathname === "/private/retention/plan")
        return send(response, 200, store.retentionPlan(principal));
      if (request.method === "POST" && url.pathname === "/private/retention/run")
        return send(response, 200, store.runScheduledDestruction(principal));
      if (request.method === "GET" && url.pathname === "/private/releases")
        return send(response, 200, {
          releases: store.releases(principal, { inquiryId: url.searchParams.get("inquiry") || undefined }),
        });
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
      if (error.retryAfterSeconds) response.setHeader("retry-after", String(error.retryAfterSeconds));
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
  // E1: the archive keyring is required, and it must live outside the store's
  // directory so that backing up the store never backs up its keys.
  const keyringPath = process.env.CARBON_TEAM_ARCHIVE_KEYRING;
  if (!keyringPath)
    throw Error("Set CARBON_TEAM_ARCHIVE_KEYRING: client records are encrypted from the first one");
  // E2: counsel's retention values are operator configuration. Absent, the
  // scheduled job refuses every run and records that it did.
  const valuesFile = process.env.CARBON_TEAM_RETENTION_VALUES_FILE;
  const retentionValues = valuesFile ? JSON.parse(fs.readFileSync(valuesFile, "utf8")) : null;
  const store = new DurableIntakeStore(storePath, {
    retentionValues,
    // E7: counsel's screening standard, as operator configuration. Unset, no
    // client record's content is reachable by anyone.
    screeningStandard: process.env.CARBON_TEAM_SCREENING_STANDARD || null,
    destination: process.env.CARBON_TEAM_NOTIFY_DESTINATION,
    keyring: ArchiveKeyring.open(path.resolve(keyringPath), { storePath }),
  });
  // Exactly one receiver process per store file. Every accepted inquiry
  // rewrites the whole file, so a second process would not interleave with
  // this one, it would overwrite its records. Refused here, before the port is
  // bound, so the failure is a start that did not happen rather than two
  // receivers quietly disagreeing about the contents of one file.
  store.acquireWriterLock();
  // A store written before E1 is sealed now, under the lock, rather than at
  // whatever write happens to come next. Earlier plaintext copies of it remain.
  if (store.sealAtRest()) process.stdout.write("Sealed a pre-E1 plaintext store at rest.\n");
  // E2: the scheduled run, once a day, inside this process because it holds
  // the store's writer lock. A timer cannot present a second factor, so it runs
  // as a named system actor and every run, refused or not, is recorded.
  const scheduled = setInterval(() => {
    try {
      runRetention(store, "scheduled-retention-job", Date.now());
    } catch {
      process.stderr.write("Scheduled retention run failed; see the store's retention_runs.\n");
    }
  }, 24 * 60 * 60 * 1000);
  scheduled.unref();
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
  // E6: a mail transport only when the operator configured one. The credential
  // is read from its file at send time and never here.
  const transport = smtpTransport(smtpConfigFrom(process.env));
  // External model processing: a scheduled provider only when the operator
  // configured one. Its credential is read from its file at send time.
  const modelProvider = scheduledProviderFrom(process.env);
  createIntakeServer({ store, users: loadUsers(usersPath), transport, modelProvider }).listen(
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
