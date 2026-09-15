"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");

const DECISION_ID = "GOAL-WORKBENCH-06-C-AUTH1-CONTRACT-V1";
const DELIVERY_MARKER = "GOAL-WORKBENCH-06A-CORRECTED-DELIVERY-V1";
const REQUIRED_MARKERS = Object.freeze([
  DECISION_ID,
  "Field semantics",
  "Issuer and scope verification",
  "Fixture/source mapping",
  "Authority ceiling",
  "https://github.com/carbonphysicsai/Carbon/blob/d2067bd4da85edafc24be5917d480089a514c670/",
  DELIVERY_MARKER,
]);
const FORBIDDEN_MARKERS = Object.freeze([
  "/private/tmp",
  "/Users/",
  "BEGIN PRIVATE KEY",
  "github_pat_",
  "ghp_",
]);
const OWNER_FORMS = Object.freeze(["KEEP", "CHANGE", "BLOCKED"]);

function sha256(bytes) {
  return `sha256:${crypto.createHash("sha256").update(bytes).digest("hex")}`;
}

function validateNotification(body) {
  if (typeof body !== "string" || !body.trim()) throw new Error("EMPTY_NOTIFICATION");
  if (/^@(?:\/|[A-Za-z]:\\)/.test(body.trim())) throw new Error("LOCAL_PATH_ONLY_NOTIFICATION");
  for (const marker of REQUIRED_MARKERS) {
    if (!body.includes(marker)) throw new Error(`MISSING_REQUIRED_MARKER:${marker}`);
  }
  for (const marker of FORBIDDEN_MARKERS) {
    if (body.includes(marker)) throw new Error(`FORBIDDEN_MARKER:${marker}`);
  }
  return true;
}

function deliveryState(comment, expected = {}) {
  if (!comment || typeof comment !== "object") return "PREPARED";
  const body = comment.body || "";
  if (/^@(?:\/|[A-Za-z]:\\)/.test(body.trim())) return "DELIVERY_MALFORMED_CONTENT_NOT_DELIVERED";
  try { validateNotification(body); } catch (_) { return "DELIVERY_MALFORMED_CONTENT_NOT_DELIVERED"; }
  if (expected.issueNumber && !String(comment.issue_url || "").endsWith(`/issues/${expected.issueNumber}`)) throw new Error("WRONG_ISSUE");
  if (expected.authorLogin && comment.user?.login !== expected.authorLogin) throw new Error("WRONG_AUTHOR");
  return "DELIVERED_VERIFIED_UNACKNOWLEDGED";
}

function verifyReadback(postedBody, comment, expected) {
  validateNotification(postedBody);
  if (deliveryState(comment, expected) !== "DELIVERED_VERIFIED_UNACKNOWLEDGED") throw new Error("READBACK_NOT_DELIVERED");
  const posted = sha256(Buffer.from(postedBody, "utf8"));
  const readback = sha256(Buffer.from(comment.body, "utf8"));
  if (posted !== readback) throw new Error("READBACK_DIGEST_MISMATCH");
  return { posted, readback };
}

function detectDuplicate(comments) {
  const matches = comments.filter((comment) => String(comment.body || "").includes(DELIVERY_MARKER));
  if (matches.length > 1) throw new Error("DUPLICATE_CORRECTED_DELIVERY");
  return matches.length === 1 ? matches[0] : null;
}

function classifyOwnerResponse(comment, correctedCreatedAt, eligibleLogins) {
  if (!comment || !eligibleLogins.includes(comment.user?.login)) return null;
  if (Date.parse(comment.created_at) <= Date.parse(correctedCreatedAt)) return null;
  const body = String(comment.body || "");
  if (!body.includes(DECISION_ID)) return null;
  for (const form of OWNER_FORMS) {
    if (new RegExp(`(?:^|\\n)${form}\\s+${DECISION_ID}(?:\\s*:|\\s*$)`, "m").test(body)) return form;
  }
  const questions = REQUIRED_MARKERS.slice(1, 4).every((marker) => body.includes(marker));
  return questions ? "OTHER_EXPLICIT_OWNER_RESPONSE" : null;
}

function validateReceipt(receipt, postedBody, readback) {
  const allowed = ["schema_version", "decision_id", "issue_number", "comment_id", "comment_url", "posted_body_sha256", "verified_readback_body_sha256", "required_markers", "forbidden_markers_checked", "delivery_status", "created_at_or_github_timestamp"];
  if (JSON.stringify(Object.keys(receipt).sort()) !== JSON.stringify(allowed.sort())) throw new Error("RECEIPT_FIELDS");
  validateNotification(postedBody);
  if (readback.issue_number !== receipt.issue_number || readback.comment_id !== receipt.comment_id || readback.comment_url !== receipt.comment_url) throw new Error("RECEIPT_ASSOCIATION");
  const posted = sha256(Buffer.from(postedBody, "utf8"));
  if (readback.body_sha256 !== posted || readback.required_markers_verified !== true || readback.forbidden_markers_absent !== true || readback.duplicate_corrected_comment_count !== 1) throw new Error("READBACK_EVIDENCE");
  if (receipt.decision_id !== DECISION_ID || receipt.delivery_status !== "DELIVERED_VERIFIED_UNACKNOWLEDGED") throw new Error("RECEIPT_STATUS");
  if (receipt.posted_body_sha256 !== posted || receipt.verified_readback_body_sha256 !== readback.body_sha256) throw new Error("RECEIPT_DIGEST");
  return true;
}

function main(argv) {
  const [bodyPath, readbackPath, receiptPath] = argv.slice(2);
  if (!bodyPath || !readbackPath || !receiptPath) throw new Error("usage: node source_assessment_delivery_integrity.cjs BODY READBACK RECEIPT");
  const body = fs.readFileSync(bodyPath, "utf8");
  const readback = JSON.parse(fs.readFileSync(readbackPath, "utf8"));
  const receipt = JSON.parse(fs.readFileSync(receiptPath, "utf8"));
  validateReceipt(receipt, body, readback);
  process.stdout.write(`${JSON.stringify({ status: receipt.delivery_status, comment_id: receipt.comment_id, sha256: receipt.posted_body_sha256 })}\n`);
}

module.exports = { DECISION_ID, DELIVERY_MARKER, REQUIRED_MARKERS, FORBIDDEN_MARKERS, sha256, validateNotification, deliveryState, verifyReadback, detectDuplicate, classifyOwnerResponse, validateReceipt };
if (require.main === module) main(process.argv);
