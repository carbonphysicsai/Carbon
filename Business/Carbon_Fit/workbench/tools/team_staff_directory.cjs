"use strict";

// Authenticated staff identity for the private intake receiver.
//
// The store used to take a caller-supplied `{ id, roles }` object and check the
// roles at the point of use. That check was true and unenforced: any call site,
// including a future endpoint nobody has written yet, could hand it a literal
// naming any role it liked, and nothing in the type said where those roles came
// from. The question worth asking is not "is this object shaped correctly" but
// "what established that this principal is who it says it is".
//
// So a principal is issued here or not at all. The brand below is module-private
// and is never exported, which means a structurally perfect literal — the right
// id, the real roles, the correct team — is still refused, because nothing
// authenticated it. That refusal is the property; the shape check never was.
//
// The directory holds credential digests, never credentials. A real deployment's
// accounts and their credentials are unresolved owner input under OD-25; the
// fixtures used in tests are synthetic and local.

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const DIRECTORY_VERSION = "carbon.private-team-intake.staff-directory.v1";
const ROLES = Object.freeze([
  "INTAKE_RECEIVER",
  "TEAM_REVIEWER",
  "DATA_STEWARD",
  "NOTIFICATION_OPERATOR",
]);

const ISSUED_BY_AUTHENTICATION = Symbol("carbon.private-team-intake.authenticated");

// Every principal this module has actually issued. `instanceof` is not an
// authentication check and never was: `Object.create(StaffPrincipal.prototype)`
// satisfies it while holding no id, no team and no roles, so a consumer relying
// on the class alone would accept a value that authenticated nothing. Set
// membership is the property, and it can only be gained by going through
// `authenticate`. A test found this; the class-based version passed review.
const ISSUED = new WeakSet();

/** True only for a principal this module issued after a credential matched. */
function isAuthenticatedPrincipal(value) {
  return typeof value === "object" && value !== null && ISSUED.has(value);
}

class StaffPrincipal {
  constructor(brand, account) {
    if (brand !== ISSUED_BY_AUTHENTICATION)
      throw Error("A staff principal can only be issued by authenticating a directory account");
    this.id = account.principal;
    this.team = account.team;
    this.roles = Object.freeze([...account.roles]);
    this.authenticated_at = new Date().toISOString();
    Object.freeze(this);
    ISSUED.add(this);
  }

  has(role) {
    return this.roles.includes(role);
  }
}

function validateAccount(account, seenIds, seenDigests) {
  if (!account || typeof account !== "object") throw Error("Invalid staff account");
  if (typeof account.principal !== "string" || !/^[a-z0-9][a-z0-9._-]{2,63}$/.test(account.principal))
    throw Error("Staff account requires a stable account identifier");
  // A team is how cross-owner denial is decided, so it is required rather than
  // defaulted; a default here would silently place every account together.
  if (typeof account.team !== "string" || !/^[a-z0-9][a-z0-9._-]{2,63}$/.test(account.team))
    throw Error("Staff account requires a named owning team");
  if (!Array.isArray(account.roles) || !account.roles.length)
    throw Error("Staff account requires at least one role");
  for (const role of account.roles)
    if (!ROLES.includes(role)) throw Error("Unknown staff role: " + role);
  if (typeof account.token_sha256 !== "string" || !/^[0-9a-f]{64}$/.test(account.token_sha256))
    throw Error("Staff account requires a credential digest, never a credential");
  if (account.status !== "ACTIVE" && account.status !== "DISABLED")
    throw Error("Staff account requires an explicit ACTIVE or DISABLED status");
  // E9: every account that can reach client records has a second factor. An
  // active account without one is refused when the directory loads, so it can
  // never be the account a session is opened for.
  if (account.totp_secret !== undefined || account.status === "ACTIVE") {
    if (typeof account.totp_secret !== "string" || decodeBase32(account.totp_secret).length < 20)
      throw Error("Staff account requires an enrolled second factor (a base32 TOTP secret of at least 160 bits)");
  }
  if (seenIds.has(account.principal)) throw Error("Duplicate staff account identifier");
  // Two accounts sharing a digest means one credential resolves to two
  // identities, and provenance would then name whichever was listed first.
  if (seenDigests.has(account.token_sha256)) throw Error("Duplicate staff credential digest");
  seenIds.add(account.principal);
  seenDigests.add(account.token_sha256);
  return account;
}

class StaffDirectory {
  constructor(accounts) {
    const seenIds = new Set(), seenDigests = new Set();
    if (!Array.isArray(accounts) || !accounts.length)
      throw Error("A staff directory requires at least one named account");
    this.accounts = accounts.map((account) => validateAccount(account, seenIds, seenDigests));
    this.schema_version = DIRECTORY_VERSION;
  }

  static load(filePath) {
    const value = JSON.parse(fs.readFileSync(path.resolve(filePath), "utf8"));
    const accounts = Array.isArray(value) ? value : value.accounts;
    return new StaffDirectory(accounts);
  }

  /** The account a staff credential names, or null. Issues nothing. */
  accountForCredential(token) {
    const presented = Buffer.from(crypto.createHash("sha256").update(token).digest("hex"));
    let matched = null;
    for (const account of this.accounts) {
      // Every account is compared on every attempt, so the work done does not
      // depend on where in the directory a match occurs.
      if (crypto.timingSafeEqual(Buffer.from(account.token_sha256), presented)) matched = account;
    }
    return matched;
  }
}

// ---------------------------------------------------------------------------
// Second factor: RFC 6238 TOTP, HMAC-SHA1, 30-second steps, six digits.

const BASE32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";

function decodeBase32(text) {
  if (typeof text !== "string") return Buffer.alloc(0);
  const clean = text.replace(/=+$/, "").toUpperCase();
  if (!/^[A-Z2-7]*$/.test(clean)) return Buffer.alloc(0);
  let bits = 0, value = 0;
  const out = [];
  for (const char of clean) {
    value = (value << 5) | BASE32.indexOf(char);
    bits += 5;
    if (bits >= 8) {
      out.push((value >>> (bits - 8)) & 0xff);
      bits -= 8;
    }
  }
  return Buffer.from(out);
}

const TOTP_STEP_MS = 30_000;

function totpAt(secret, counter, digits = 6) {
  const message = Buffer.alloc(8);
  message.writeBigUInt64BE(BigInt(counter));
  const mac = crypto.createHmac("sha1", decodeBase32(secret)).update(message).digest();
  const offset = mac[mac.length - 1] & 0x0f;
  const code = (mac.readUInt32BE(offset) & 0x7fffffff) % 10 ** digits;
  return String(code).padStart(digits, "0");
}

/** The code an authenticator shows at `nowMs` for this secret. */
function totp(secret, nowMs) {
  return totpAt(secret, Math.floor(nowMs / TOTP_STEP_MS));
}

// ---------------------------------------------------------------------------
// E9: rate limiting, lockout and MFA. The only way to a principal.
//
// A staff credential alone opens nothing. A session is opened by the
// credential together with a current second-factor code, and only a live
// session resolves to a principal. That principal is issued here, in the
// module that owns the brand, so there is no single-factor path left to call.
//
// The limits are mechanical controls with engineering defaults, built before
// the security review so the reviewer has something to test and change. What
// happens beyond them (escalation, notification, abuse response) is policy and
// stays behind that review. State is held in this process: a restart clears
// lockouts and sessions alike, which the runbook states.

const DEFAULT_LIMITS = Object.freeze({
  sessionTtlMs: 8 * 60 * 60 * 1000,
  openAttemptsPerSource: 10,
  openWindowMs: 5 * 60 * 1000,
  failuresBeforeLockout: 5,
  lockoutMs: 15 * 60 * 1000,
  requestsPerSessionPerMinute: 120,
  totpDriftSteps: 1,
});

class AccessDenied extends Error {
  constructor(status, code, retryAfterMs) {
    super(code);
    this.status = status;
    this.code = code;
    if (retryAfterMs !== undefined) this.retryAfterSeconds = Math.max(1, Math.ceil(retryAfterMs / 1000));
  }
}

class AccessControl {
  constructor(directory, { clock = Date.now, limits = {} } = {}) {
    if (!(directory instanceof StaffDirectory)) throw Error("Access control requires a loaded staff directory");
    this.directory = directory;
    this.clock = clock;
    this.limits = Object.freeze({ ...DEFAULT_LIMITS, ...limits });
    this.sources = new Map(); // source -> { windowStart, attempts }
    this.accounts = new Map(); // principal -> { failures, lockedUntil, lastCounter }
    this.sessions = new Map(); // sha256(session) -> { account, expiresAt, windowStart, requests }
  }

  accountState(id) {
    if (!this.accounts.has(id)) this.accounts.set(id, { failures: 0, lockedUntil: 0, lastCounter: -1 });
    return this.accounts.get(id);
  }

  countOpenAttempt(source, now) {
    const key = String(source || "unknown");
    let entry = this.sources.get(key);
    if (!entry || now - entry.windowStart >= this.limits.openWindowMs) entry = { windowStart: now, attempts: 0 };
    entry.attempts += 1;
    this.sources.set(key, entry);
    if (entry.attempts > this.limits.openAttemptsPerSource)
      throw new AccessDenied(429, "RATE_LIMITED", entry.windowStart + this.limits.openWindowMs - now);
  }

  /** Open a session from a staff credential and a current second-factor code. */
  openSession({ authorization, code, source }) {
    const now = this.clock();
    this.countOpenAttempt(source, now);
    const match = /^Bearer ([A-Za-z0-9._~-]{20,300})$/.exec(authorization || "");
    const account = match ? this.directory.accountForCredential(match[1]) : null;
    // One refusal for a missing, unknown or disabled credential: which it was
    // is information the caller has not earned. Only the source limit applies,
    // because an unknown credential names no account to lock.
    if (!account || account.status !== "ACTIVE") throw new AccessDenied(401, "AUTHENTICATION_FAILED");
    const state = this.accountState(account.principal);
    // A locked account is refused even with a correct second factor; otherwise
    // the lockout would only slow down the guesses it exists to stop.
    if (state.lockedUntil > now) throw new AccessDenied(423, "ACCOUNT_LOCKED", state.lockedUntil - now);
    const counter = this.acceptedCounter(account.totp_secret, code, now, state.lastCounter);
    if (counter === null) {
      state.failures += 1;
      if (state.failures >= this.limits.failuresBeforeLockout) {
        state.failures = 0;
        state.lockedUntil = now + this.limits.lockoutMs;
        throw new AccessDenied(423, "ACCOUNT_LOCKED", this.limits.lockoutMs);
      }
      throw new AccessDenied(401, "AUTHENTICATION_FAILED");
    }
    state.failures = 0;
    state.lastCounter = counter;
    const session = crypto.randomBytes(32).toString("base64url");
    const expiresAt = now + this.limits.sessionTtlMs;
    this.sessions.set(sessionKey(session), { account, expiresAt, windowStart: now, requests: 0 });
    return { session_token: session, expires_at: new Date(expiresAt).toISOString() };
  }

  /** The step a code belongs to, or null. A code already used is refused. */
  acceptedCounter(secret, code, now, lastCounter) {
    if (typeof code !== "string" || !/^[0-9]{6}$/.test(code)) return null;
    const current = Math.floor(now / TOTP_STEP_MS);
    let accepted = null;
    for (let drift = -this.limits.totpDriftSteps; drift <= this.limits.totpDriftSteps; drift++) {
      const counter = current + drift;
      if (crypto.timingSafeEqual(Buffer.from(totpAt(secret, counter)), Buffer.from(code))) accepted = counter;
    }
    return accepted !== null && accepted > lastCounter ? accepted : null;
  }

  /** Resolve a live session to a principal, or refuse. The only issuer. */
  authenticate(authorization) {
    const now = this.clock();
    const match = /^Bearer ([A-Za-z0-9_-]{43})$/.exec(authorization || "");
    const entry = match ? this.sessions.get(sessionKey(match[1])) : undefined;
    if (!entry || entry.expiresAt <= now) {
      if (entry) this.sessions.delete(sessionKey(match[1]));
      throw new AccessDenied(401, "AUTHENTICATION_FAILED");
    }
    // An account disabled or locked after the session opened loses it.
    const current = this.directory.accounts.find((account) => account.principal === entry.account.principal);
    if (!current || current.status !== "ACTIVE" || this.accountState(current.principal).lockedUntil > now) {
      this.sessions.delete(sessionKey(match[1]));
      throw new AccessDenied(401, "AUTHENTICATION_FAILED");
    }
    if (now - entry.windowStart >= 60_000) {
      entry.windowStart = now;
      entry.requests = 0;
    }
    entry.requests += 1;
    if (entry.requests > this.limits.requestsPerSessionPerMinute)
      throw new AccessDenied(429, "RATE_LIMITED", entry.windowStart + 60_000 - now);
    return new StaffPrincipal(ISSUED_BY_AUTHENTICATION, current);
  }

  closeSession(authorization) {
    const match = /^Bearer ([A-Za-z0-9_-]{43})$/.exec(authorization || "");
    if (match) this.sessions.delete(sessionKey(match[1]));
  }
}

const sessionKey = (session) => crypto.createHash("sha256").update(session).digest("hex");

module.exports = {
  DIRECTORY_VERSION,
  ROLES,
  DEFAULT_LIMITS,
  AccessControl,
  AccessDenied,
  StaffPrincipal,
  StaffDirectory,
  isAuthenticatedPrincipal,
  totp,
};
