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

  /** Issue a principal for a presented credential, or refuse. */
  authenticate(authorization) {
    const match = /^Bearer ([A-Za-z0-9._~-]{20,300})$/.exec(authorization || "");
    // The same refusal for a missing header and a wrong credential: which of
    // the two it was is information the caller has not earned.
    if (!match) throw Error("Authentication failed");
    const digest = crypto.createHash("sha256").update(match[1]).digest("hex");
    const presented = Buffer.from(digest);
    let authenticated = null;
    for (const account of this.accounts) {
      // Every account is compared on every attempt, so the work done does not
      // depend on where in the directory a match occurs.
      if (crypto.timingSafeEqual(Buffer.from(account.token_sha256), presented))
        authenticated = account;
    }
    if (!authenticated || authenticated.status !== "ACTIVE")
      throw Error("Authentication failed");
    return new StaffPrincipal(ISSUED_BY_AUTHENTICATION, authenticated);
  }
}

module.exports = {
  DIRECTORY_VERSION,
  ROLES,
  StaffPrincipal,
  StaffDirectory,
  isAuthenticatedPrincipal,
};
