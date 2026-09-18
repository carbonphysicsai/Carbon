"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const F = require("../src/engine.js");
const { DurableIntakeStore } = require("./team_intake_store.cjs");

const storePath = process.env.CARBON_TEAM_INTAKE_STORE;
const usersPath = process.env.CARBON_TEAM_USERS_FILE;
if (!storePath || !usersPath)
  throw Error("Set CARBON_TEAM_INTAKE_STORE and CARBON_TEAM_USERS_FILE");
const users = JSON.parse(fs.readFileSync(path.resolve(usersPath), "utf8"));
if (!Array.isArray(users) || !users.length) throw Error("Named users are required");
const store = new DurableIntakeStore(storePath);
const port = Number(process.env.CARBON_TEAM_INTAKE_PORT || "8789");

function authenticate(request) {
  const match = /^Bearer ([A-Za-z0-9._~-]{20,300})$/.exec(
    request.headers.authorization || "",
  );
  if (!match) throw Error("Authentication required");
  const digest = crypto.createHash("sha256").update(match[1]).digest("hex");
  const user = users.find(
    (candidate) =>
      typeof candidate.token_sha256 === "string" &&
      /^[0-9a-f]{64}$/.test(candidate.token_sha256) &&
      crypto.timingSafeEqual(Buffer.from(candidate.token_sha256), Buffer.from(digest)),
  );
  if (!user) throw Error("Authentication failed");
  return { id: user.principal, roles: user.roles };
}

function body(request) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    request.on("data", (chunk) => {
      size += chunk.length;
      if (size > 130_000) {
        reject(Error("Request body exceeds 130 KB"));
        request.destroy();
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

http
  .createServer(async (request, response) => {
    try {
      const principal = authenticate(request);
      const url = new URL(request.url, "http://127.0.0.1");
      if (request.method === "POST" && url.pathname === "/private/intake") {
        const raw = await body(request);
        const key = request.headers["idempotency-key"];
        return send(response, 201, await store.accept(raw, key, principal));
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
      const status = /Authentication|required|authorized/.test(message)
        ? 403
        : /not found/i.test(message)
          ? 404
          : /conflict/i.test(message)
            ? 409
            : 400;
      send(response, status, { error: message });
    }
  })
  .listen(port, "127.0.0.1", () => {
    process.stdout.write(
      `Carbon private synthetic intake listening on http://127.0.0.1:${port}\n`,
    );
  });
