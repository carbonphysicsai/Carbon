"use strict";
// Synthetic staff for tests. Every account is enrolled in a second factor, and
// a principal is obtained the only way the receiver allows: a session opened
// with the credential and a current code, then resolved. Nothing here is a
// real account, credential or secret.
const crypto = require("node:crypto");
const os = require("node:os");
const path = require("node:path");
const { AccessControl, totp } = require("../tools/team_staff_directory.cjs");
const { ArchiveKeyring } = require("../tools/team_archive_keyring.cjs");
const { scopingBasis } = require("../tools/team_record_basis.cjs");

const BASE32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";

/** A deterministic synthetic 160-bit TOTP secret for a test token. */
function secretFor(token) {
  const bytes = crypto.createHash("sha256").update("totp:" + token).digest().subarray(0, 20);
  let bits = 0, value = 0, out = "";
  for (const byte of bytes) {
    value = (value << 8) | byte;
    bits += 8;
    while (bits >= 5) {
      out += BASE32[(value >>> (bits - 5)) & 31];
      bits -= 5;
    }
  }
  return out;
}

const digest = (value) => crypto.createHash("sha256").update(value).digest("hex");

/** A directory account for a token, enrolled in a second factor. */
/** The synthetic screening standard the test stores are configured with (E7). */
const SCREENING_STANDARD = "synthetic-screening-standard";

function enrolled(principal, team, roles, token, status = "ACTIVE", { screened = true } = {}) {
  return {
    principal,
    team,
    roles,
    token_sha256: digest(token),
    totp_secret: secretFor(token),
    status,
    ...(screened ? { screening: { standard: SCREENING_STANDARD, ref: "synthetic-screening-" + principal } } : {}),
  };
}

/** A principal for direct store calls, through a real session. */
function principalFor(directory, token, { clock = Date.now } = {}) {
  const access = new AccessControl(directory, { clock });
  const { session_token } = access.openSession({
    authorization: "Bearer " + token,
    code: totp(secretFor(token), clock()),
    source: "test",
  });
  return access.authenticate("Bearer " + session_token);
}

/**
 * The archive keyring for a store file: the same one every time that store is
 * reopened, as a restarted receiver would use, and never inside the store's own
 * directory, which is where a backup would copy it from.
 */
function keyringFor(storePath) {
  // One keyring per store directory: a backup copied beside the store and
  // opened there uses the same keys, as a restore on the same host would.
  const name = crypto.createHash("sha256").update(path.dirname(path.resolve(storePath))).digest("hex").slice(0, 32);
  return ArchiveKeyring.open(path.join(os.tmpdir(), "carbon-test-keyrings", name + ".json"), { storePath });
}

/** A store opened the only way a store can be: with its archive keyring. */
function openStore(storePath, options = {}) {
  const { DurableIntakeStore } = require("../tools/team_intake_store.cjs");
  return new DurableIntakeStore(storePath, { screeningStandard: SCREENING_STANDARD, ...options, keyring: keyringFor(storePath) });
}

/** A synthetic SCOPING basis: a record received under a (synthetic) NDA. */
const scoping = () => scopingBasis({ nda: "synthetic-nda-0001" });
/** The same basis as a relay sends it, in headers beside the package. */
const SCOPING_HEADERS = Object.freeze({
  "x-carbon-record-class": "SCOPING",
  "x-carbon-nda-ref": "synthetic-nda-0001",
  // E6: a mailed, encrypted package is the ordinary case.
  "x-carbon-intake-channel": "MAIL_INTAKE",
  "x-carbon-transport-arrival": "ENCRYPTED",
  // E7: the export-control determination the record is held under.
  "x-carbon-export-control-ref": "synthetic-ec-0001",
});

/** A synthetic release: to a named member of Carbon staff, for review. */
const RELEASE = Object.freeze({ recipient: { kind: "CARBON_STAFF", ref: "synthetic-reviewer" }, purpose: "Team review" });
const RELEASE_HEADERS = Object.freeze({
  "x-carbon-release-recipient-kind": "CARBON_STAFF",
  "x-carbon-release-recipient-ref": "synthetic-reviewer",
  "x-carbon-release-purpose": "Team review",
});

/** How a synthetic package arrived: mailed, encrypted, still in the mailbox. */
const mailed = () => {
  const { transportAtRelay } = require("../tools/team_intake_store.cjs");
  return transportAtRelay(SCOPING_HEADERS);
};

/** A synthetic export-control reference for direct store calls (E7). */
const exportRef = () => "synthetic-ec-0001";

module.exports = { SCREENING_STANDARD, exportRef, mailed, RELEASE, RELEASE_HEADERS, SCOPING_HEADERS, enrolled, keyringFor, openStore, principalFor, scoping, secretFor };
