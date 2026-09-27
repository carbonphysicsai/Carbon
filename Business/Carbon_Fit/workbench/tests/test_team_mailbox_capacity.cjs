"use strict";
// E6: a full intake mailbox bounces a client's mail to the client, unseen by
// Carbon. The pooled storage reading makes that state observable. No test here
// reaches Google: the fetch is a recorder that answers like the two endpoints.
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
if (!globalThis.crypto) globalThis.crypto = crypto.webcrypto;
const { ABOUT_URL, TOKEN_URL, mailboxCapacity } = require("../tools/team_mailbox_capacity.cjs");
const { StaffDirectory, totp } = require("../tools/team_staff_directory.cjs");
const { createIntakeServer } = require("../tools/team_intake_server.cjs");
const { enrolled, openStore, secretFor } = require("./staff_fixture.cjs");

const REFRESH = "synthetic-refresh-" + "r7q2".repeat(8);
const SECRET = "synthetic-client-secret-" + "s9k1".repeat(4);
const ACCESS = "synthetic-access-" + "a4m6".repeat(8);

function credentialFile(mode = 0o600, value = { client_id: "synthetic-client.apps.example", client_secret: SECRET, refresh_token: REFRESH }) {
  const file = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "carbon-quota-")), "quota.json");
  fs.writeFileSync(file, JSON.stringify(value), { mode });
  fs.chmodSync(file, mode);
  return file;
}

function google({ usage, limit, tokenStatus = 200, aboutStatus = 200 }) {
  const calls = [];
  const fetch = async (url, init = {}) => {
    calls.push({ url, init });
    if (url === TOKEN_URL) return new Response(JSON.stringify({ access_token: ACCESS, expires_in: 3599 }), { status: tokenStatus });
    if (url === ABOUT_URL) {
      const storageQuota = { usage: String(usage) };
      if (limit !== undefined) storageQuota.limit = String(limit);
      return new Response(JSON.stringify({ storageQuota }), { status: aboutStatus });
    }
    throw Error("unexpected url " + url);
  };
  return { calls, fetch };
}

test("the pool's usage against its limit gives OK, NEAR_FULL or FULL", async () => {
  const file = credentialFile();
  const read = (usage, limit) => mailboxCapacity({ credentialFile: file, fetch: google({ usage, limit }).fetch });
  assert.equal((await read(50, 100)).state, "OK");
  assert.equal((await read(90, 100)).state, "NEAR_FULL");
  assert.equal((await read(100, 100)).state, "FULL");
  const unlimited = await read(123, undefined);
  assert.equal(unlimited.state, "UNLIMITED");
  assert.equal(unlimited.limit_bytes, null);
  const reading = await read(95, 100);
  assert.deepEqual([reading.usage_bytes, reading.limit_bytes, reading.used_fraction, reading.basis], [95, 100, 0.95, "DRIVE_ABOUT_STORAGE_QUOTA"]);
});

test("the reading asks for the storage quota only, with a token from the refresh credential", async () => {
  const g = google({ usage: 1, limit: 100 });
  await mailboxCapacity({ credentialFile: credentialFile(), fetch: g.fetch });
  assert.equal(g.calls[0].url, "https://oauth2.googleapis.com/token");
  const form = new URLSearchParams(g.calls[0].init.body);
  assert.equal(form.get("grant_type"), "refresh_token");
  assert.equal(form.get("refresh_token"), REFRESH);
  assert.equal(g.calls[1].url, "https://www.googleapis.com/drive/v3/about?fields=storageQuota");
  assert.equal(g.calls[1].init.headers.authorization, "Bearer " + ACCESS);
});

test("no credential is NOT_CONFIGURED, a failed reading is UNREADABLE, and neither reports room", async () => {
  const none = await mailboxCapacity({ credentialFile: null, fetch: google({ usage: 1, limit: 100 }).fetch });
  assert.equal(none.state, "NOT_CONFIGURED");
  assert.equal(none.usage_bytes, undefined);
  for (const [file, pattern] of [
    [credentialFile(0o644), /owner only/],
    [credentialFile(0o600, { client_id: "x" }), /names client_id, client_secret and refresh_token/],
    [(() => { const t = credentialFile(); fs.symlinkSync(t, t + ".link"); return t + ".link"; })(), /not a link/],
  ]) {
    const g = google({ usage: 1, limit: 100 });
    const reading = await mailboxCapacity({ credentialFile: file, fetch: g.fetch });
    assert.equal(reading.state, "UNREADABLE");
    assert.match(reading.reason, pattern);
    assert.equal(g.calls.length, 0);
  }
  assert.equal((await mailboxCapacity({ credentialFile: credentialFile(), fetch: google({ usage: 1, limit: 100, tokenStatus: 400 }).fetch })).state, "UNREADABLE");
  assert.equal((await mailboxCapacity({ credentialFile: credentialFile(), fetch: google({ usage: 1, limit: 100, aboutStatus: 403 }).fetch })).state, "UNREADABLE");
  const offline = await mailboxCapacity({ credentialFile: credentialFile(), fetch: async () => { throw Error("getaddrinfo ENOTFOUND " + REFRESH); } });
  assert.equal(offline.state, "UNREADABLE");
  // Specimen: the same credential file, with a reachable provider, reads.
  assert.equal((await mailboxCapacity({ credentialFile: credentialFile(), fetch: google({ usage: 1, limit: 100 }).fetch })).state, "OK");
});

test("the credential appears in no reading, even when a failure would carry it", async () => {
  const readings = [
    await mailboxCapacity({ credentialFile: credentialFile(), fetch: google({ usage: 5, limit: 100 }).fetch }),
    await mailboxCapacity({ credentialFile: credentialFile(), fetch: async () => { throw Error("refused " + REFRESH + " " + SECRET); } }),
  ];
  const text = JSON.stringify(readings);
  for (const secret of [REFRESH, SECRET, ACCESS]) assert.ok(!text.includes(secret));
  // Specimen: the credential really was sent where it belongs.
  const g = google({ usage: 5, limit: 100 });
  await mailboxCapacity({ credentialFile: credentialFile(), fetch: g.fetch });
  assert.ok(g.calls[0].init.body.includes(REFRESH));
});

test("the receiver serves the reading to the intake receiver only", async () => {
  const token = { receiver: "quota-receiver-token-0001", reviewer: "quota-reviewer-token-0001" };
  const users = new StaffDirectory([
    enrolled("quota-receiver", "carbon-fit", ["INTAKE_RECEIVER"], token.receiver),
    enrolled("quota-reviewer", "carbon-fit", ["TEAM_REVIEWER"], token.reviewer),
  ]);
  const store = openStore(path.join(fs.mkdtempSync(path.join(os.tmpdir(), "carbon-quota-store-")), "store.json"));
  for (const configured of [false, true]) {
    const mailbox = configured ? () => mailboxCapacity({ credentialFile: credentialFile(), fetch: google({ usage: 99, limit: 100 }).fetch }) : null;
    const server = createIntakeServer({ store, users, mailbox });
    await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
    const base = `http://127.0.0.1:${server.address().port}`;
    const session = async (t) => {
      const opened = await fetch(base + "/private/session", {
        method: "POST",
        headers: { authorization: "Bearer " + t, "content-type": "application/json" },
        body: JSON.stringify({ code: totp(secretFor(t), Date.now()) }),
      });
      return "Bearer " + (await opened.json()).session_token;
    };
    try {
      assert.equal((await fetch(base + "/private/mailbox", { headers: { authorization: await session(token.reviewer) } })).status, 403);
      const answer = await fetch(base + "/private/mailbox", { headers: { authorization: await session(token.receiver) } });
      assert.equal(answer.status, 200);
      assert.equal((await answer.json()).state, configured ? "NEAR_FULL" : "NOT_CONFIGURED");
    } finally {
      server.close();
    }
  }
});
