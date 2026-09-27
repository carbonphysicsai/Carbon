"use strict";

// E6: whether the intake mailbox has room, observed rather than assumed.
//
// The intake mailbox shares the organization's pooled storage. When the pool
// is full, mail to it bounces, and the bounce goes to the client who sent it,
// not to Carbon. A client's material then silently does not arrive. This reads
// the pool's usage and limit so that state can be seen before it happens.
//
// Source: the Drive API's `about.get` with `fields=storageQuota`. For a user in
// an organization with pooled storage, its `limit` and `usage` are the
// organization's, across all services (Drive API reference, "about"). The
// narrowest scope that permits the call is `drive.file`, which grants no access
// to mail and none to any file the application did not create itself. The
// reading needs only that.
//
// The credential is the operator's: an OAuth client and a refresh token issued
// by the owner for the intake account, in a 0600 file named by
// CARBON_TEAM_MAILBOX_QUOTA_CREDENTIAL_FILE. It is read at check time and never
// logged, returned or recorded. Without it the state is NOT_CONFIGURED, which
// is a different fact from a reading that failed (UNREADABLE). Neither is
// reported as room.

const fs = require("node:fs");

const TOKEN_URL = "https://oauth2.googleapis.com/token";
const ABOUT_URL = "https://www.googleapis.com/drive/v3/about?fields=storageQuota";
const CREDENTIAL_MAX_BYTES = 4096;
// An engineering default, for the operator to change: warn with a tenth of the
// pool left, because a pool shared across the organization fills from anywhere.
const NEAR_FULL_FRACTION = 0.9;

function readCredential(file) {
  if (!file) return { state: "NOT_CONFIGURED", reason: "No mailbox quota credential is configured: set CARBON_TEAM_MAILBOX_QUOTA_CREDENTIAL_FILE" };
  let stat;
  try {
    stat = fs.lstatSync(file);
  } catch {
    return { state: "NOT_CONFIGURED", reason: "The configured mailbox quota credential file does not exist" };
  }
  if (!stat.isFile() || (stat.mode & 0o077) !== 0 || stat.size > CREDENTIAL_MAX_BYTES)
    return { state: "UNREADABLE", reason: "The mailbox quota credential must be a regular file, not a link, readable by its owner only, and at most 4096 bytes" };
  let value;
  try {
    value = JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    return { state: "UNREADABLE", reason: "The mailbox quota credential file is not JSON" };
  }
  const fields = ["client_id", "client_secret", "refresh_token"];
  if (!value || typeof value !== "object" || fields.some((name) => typeof value[name] !== "string" || !value[name]))
    return { state: "UNREADABLE", reason: "The mailbox quota credential names client_id, client_secret and refresh_token" };
  return { credential: value };
}

/**
 * One reading of the pool. Every outcome is a typed state with a fixed reason;
 * no provider response text is carried, because it is not ours to vouch for.
 */
async function mailboxCapacity({ credentialFile, fetch = globalThis.fetch, now = () => new Date(), nearFull = NEAR_FULL_FRACTION } = {}) {
  const observedAt = now().toISOString();
  const read = readCredential(credentialFile);
  if (!read.credential) return { state: read.state, reason: read.reason, observed_at: observedAt };
  const unreadable = (reason) => ({ state: "UNREADABLE", reason, observed_at: observedAt });
  let token;
  try {
    const response = await fetch(TOKEN_URL, {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ ...read.credential, grant_type: "refresh_token" }).toString(),
    });
    if (!response.ok) return unreadable(`The token endpoint refused the credential (${response.status})`);
    token = (await response.json()).access_token;
  } catch {
    return unreadable("The token endpoint could not be reached or returned an unreadable response");
  }
  if (typeof token !== "string" || !token) return unreadable("The token endpoint returned no access token");
  let quota;
  try {
    const response = await fetch(ABOUT_URL, { headers: { authorization: "Bearer " + token } });
    if (!response.ok) return unreadable(`The storage reading was refused (${response.status})`);
    quota = (await response.json()).storageQuota;
  } catch {
    return unreadable("The storage reading could not be reached or returned an unreadable response");
  }
  const usage = quota && Number(quota.usage);
  if (!quota || !Number.isFinite(usage)) return unreadable("The storage reading carried no usage");
  // No limit means unlimited storage, per the API. It is stated, not assumed.
  if (quota.limit === undefined) return { state: "UNLIMITED", usage_bytes: usage, limit_bytes: null, observed_at: observedAt, basis: "DRIVE_ABOUT_STORAGE_QUOTA" };
  const limit = Number(quota.limit);
  if (!Number.isFinite(limit) || limit <= 0) return unreadable("The storage reading carried an unusable limit");
  const fraction = usage / limit;
  const state = usage >= limit ? "FULL" : fraction >= nearFull ? "NEAR_FULL" : "OK";
  return { state, usage_bytes: usage, limit_bytes: limit, used_fraction: Math.round(fraction * 10_000) / 10_000, observed_at: observedAt, basis: "DRIVE_ABOUT_STORAGE_QUOTA" };
}

module.exports = { ABOUT_URL, NEAR_FULL_FRACTION, TOKEN_URL, mailboxCapacity };

// `node tools/team_mailbox_capacity.cjs`: one reading, printed as JSON. The exit
// status is 0 only for OK or UNLIMITED, so a scheduler can alert on anything else.
if (require.main === module) {
  mailboxCapacity({ credentialFile: process.env.CARBON_TEAM_MAILBOX_QUOTA_CREDENTIAL_FILE }).then((reading) => {
    process.stdout.write(JSON.stringify(reading) + "\n");
    process.exit(["OK", "UNLIMITED"].includes(reading.state) ? 0 : 1);
  });
}
