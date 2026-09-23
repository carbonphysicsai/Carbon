"use strict";
// Synthetic staff for tests. Every account is enrolled in a second factor, and
// a principal is obtained the only way the receiver allows: a session opened
// with the credential and a current code, then resolved. Nothing here is a
// real account, credential or secret.
const crypto = require("node:crypto");
const { AccessControl, totp } = require("../tools/team_staff_directory.cjs");

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
function enrolled(principal, team, roles, token, status = "ACTIVE") {
  return { principal, team, roles, token_sha256: digest(token), totp_secret: secretFor(token), status };
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

module.exports = { enrolled, principalFor, secretFor };
