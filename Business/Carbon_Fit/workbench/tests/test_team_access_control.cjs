"use strict";
// E9: rate limiting, lockout and MFA on every account that can reach client
// records. Mechanical controls, built before the security review so the
// reviewer has something to test. Each refusal below is paired with the
// matching success, so a control that stopped refusing and one that refuses
// everything are both caught.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const {
  AccessControl,
  DEFAULT_LIMITS,
  StaffDirectory,
  isAuthenticatedPrincipal,
  totp,
} = require("../tools/team_staff_directory.cjs");
const { createIntakeServer } = require("../tools/team_intake_server.cjs");
const { DurableIntakeStore } = require("../tools/team_intake_store.cjs");
const { enrolled, openStore, secretFor } = require("./staff_fixture.cjs");

const TOKEN = "synthetic-access-control-token-0001";
const OTHER = "synthetic-access-control-token-0002";
const START = Date.UTC(2026, 8, 23, 12, 0, 0);

function harness(limits = {}) {
  let now = START;
  const directory = new StaffDirectory([
    enrolled("reviewer-one", "carbon-fit", ["TEAM_REVIEWER"], TOKEN),
    enrolled("reviewer-two", "carbon-fit", ["TEAM_REVIEWER"], OTHER),
  ]);
  const access = new AccessControl(directory, { clock: () => now, limits });
  return {
    directory,
    access,
    advance: (ms) => { now += ms; },
    now: () => now,
    code: (token = TOKEN, at = now) => totp(secretFor(token), at),
    open: (token = TOKEN, code, source = "10.0.0.1") =>
      access.openSession({ authorization: "Bearer " + token, code: code ?? totp(secretFor(token), now), source }),
  };
}

const refusal = (fn, status, code) => {
  try {
    fn();
  } catch (error) {
    assert.equal(error.status, status, error.message);
    assert.equal(error.code, code);
    return error;
  }
  assert.fail(`expected ${status} ${code}`);
};

test("the second factor is RFC 6238 TOTP, checked against the published vectors", () => {
  // RFC 6238 Appendix B, SHA-1, secret "12345678901234567890", six digits.
  const secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ";
  assert.equal(totp(secret, 59_000), "287082");
  assert.equal(totp(secret, 1_111_111_109_000), "081804");
  assert.equal(totp(secret, 1_234_567_890_000), "005924");
  assert.equal(totp(secret, 2_000_000_000_000), "279037");
});

test("a staff credential alone opens nothing; with a current code it opens a session", () => {
  const h = harness();
  refusal(() => h.open(TOKEN, ""), 401, "AUTHENTICATION_FAILED");
  refusal(() => h.open(TOKEN, "000000" === h.code() ? "111111" : "000000"), 401, "AUTHENTICATION_FAILED");
  refusal(() => h.open(TOKEN, h.code(TOKEN, h.now() - 5 * 30_000)), 401, "AUTHENTICATION_FAILED");
  refusal(() => h.open("not-a-known-credential-0000", h.code()), 401, "AUTHENTICATION_FAILED");
  const opened = h.open();
  const principal = h.access.authenticate("Bearer " + opened.session_token);
  assert.equal(isAuthenticatedPrincipal(principal), true);
  assert.equal(principal.id, "reviewer-one");
});

test("a staff credential is not a session and cannot be presented as one", () => {
  const h = harness();
  h.open(); // a session exists for this account; the credential is still not one
  refusal(() => h.access.authenticate("Bearer " + TOKEN), 401, "AUTHENTICATION_FAILED");
  refusal(() => h.access.authenticate(undefined), 401, "AUTHENTICATION_FAILED");
});

test("a code that was already used cannot open a second session", () => {
  const h = harness();
  const code = h.code();
  h.open(TOKEN, code);
  refusal(() => h.open(TOKEN, code), 401, "AUTHENTICATION_FAILED");
  // The next step's code does.
  h.advance(30_000);
  assert.ok(h.open().session_token);
});

test("consecutive second-factor failures lock the account, even against a correct code", () => {
  const h = harness();
  const live = h.open();
  h.advance(30_000);
  for (let attempt = 1; attempt < DEFAULT_LIMITS.failuresBeforeLockout; attempt++)
    refusal(() => h.open(TOKEN, "999999" === h.code() ? "888888" : "999999"), 401, "AUTHENTICATION_FAILED");
  const locked = refusal(() => h.open(TOKEN, "999999" === h.code() ? "888888" : "999999"), 423, "ACCOUNT_LOCKED");
  assert.equal(locked.retryAfterSeconds, DEFAULT_LIMITS.lockoutMs / 1000);
  // The correct code is refused while locked, or the lock only slows guessing.
  refusal(() => h.open(), 423, "ACCOUNT_LOCKED");
  // A session opened before the lock is lost with it.
  refusal(() => h.access.authenticate("Bearer " + live.session_token), 401, "AUTHENTICATION_FAILED");
  // Another account is unaffected.
  assert.ok(h.open(OTHER).session_token);
  // After the lockout period, the correct code opens a session again.
  h.advance(DEFAULT_LIMITS.lockoutMs);
  assert.ok(h.open().session_token);
});

test("session opening is rate limited per source, and the window resets", () => {
  const h = harness();
  for (let attempt = 0; attempt < DEFAULT_LIMITS.openAttemptsPerSource; attempt++)
    refusal(() => h.open("not-a-known-credential-0000", "123456"), 401, "AUTHENTICATION_FAILED");
  const limited = refusal(() => h.open(), 429, "RATE_LIMITED");
  assert.ok(limited.retryAfterSeconds > 0);
  // A different source is not held up by this one.
  assert.ok(h.open(TOKEN, undefined, "10.0.0.2").session_token);
  h.advance(DEFAULT_LIMITS.openWindowMs);
  h.advance(30_000);
  assert.ok(h.open().session_token);
});

test("requests on one session are rate limited per minute", () => {
  const h = harness();
  const bearer = "Bearer " + h.open().session_token;
  for (let request = 0; request < DEFAULT_LIMITS.requestsPerSessionPerMinute; request++)
    h.access.authenticate(bearer);
  refusal(() => h.access.authenticate(bearer), 429, "RATE_LIMITED");
  h.advance(60_000);
  assert.ok(h.access.authenticate(bearer));
});

test("a session expires, and a disabled account loses its live session", () => {
  const h = harness();
  const bearer = "Bearer " + h.open().session_token;
  assert.ok(h.access.authenticate(bearer));
  h.advance(DEFAULT_LIMITS.sessionTtlMs);
  refusal(() => h.access.authenticate(bearer), 401, "AUTHENTICATION_FAILED");

  const other = "Bearer " + h.open(OTHER).session_token;
  assert.ok(h.access.authenticate(other));
  h.directory.accounts.find((account) => account.principal === "reviewer-two").status = "DISABLED";
  refusal(() => h.access.authenticate(other), 401, "AUTHENTICATION_FAILED");
});

test("over HTTP, lockout and rate limiting answer 423 and 429 with Retry-After", async () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "carbon-access-http-"));
  const store = openStore(path.join(directory, "store.json"));
  const server = createIntakeServer({
    store,
    users: [enrolled("reviewer-one", "carbon-fit", ["TEAM_REVIEWER"], TOKEN)],
    limits: { failuresBeforeLockout: 2, openAttemptsPerSource: 3 },
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  const open = (code) =>
    fetch(base + "/private/session", {
      method: "POST",
      headers: { authorization: "Bearer " + TOKEN, "content-type": "application/json" },
      body: JSON.stringify({ code }),
    });
  try {
    // Specimen: a correct code opens a session over HTTP, and the session reads.
    const opened = await open(totp(secretFor(TOKEN), Date.now()));
    assert.equal(opened.status, 201);
    const session = (await opened.json()).session_token;
    const search = await fetch(base + "/private/intake", { headers: { authorization: "Bearer " + session } });
    assert.equal(search.status, 200);
    // The staff credential presented directly is refused.
    const direct = await fetch(base + "/private/intake", { headers: { authorization: "Bearer " + TOKEN } });
    assert.equal(direct.status, 401);

    assert.equal((await open("000001")).status, 401);
    const locked = await open("000002");
    assert.equal(locked.status, 423);
    assert.ok(Number(locked.headers.get("retry-after")) > 0);
    const limited = await open("000003");
    assert.equal(limited.status, 429);
    assert.ok(Number(limited.headers.get("retry-after")) > 0);
  } finally {
    server.close();
    fs.rmSync(directory, { recursive: true, force: true });
  }
});
