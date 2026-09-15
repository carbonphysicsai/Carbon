"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const WB = path.resolve(__dirname, "..");
const DELIVERY = path.join(WB, "source_assessment", "delivery", "v1");
const D = require("../tools/source_assessment_delivery_integrity.cjs");
const G = require("../src/workflow.js");
const response = JSON.parse(fs.readFileSync(path.join(WB, "source_assessment", "v1", "fixtures", "response.json"), "utf8"));
const body = fs.readFileSync(path.join(DELIVERY, "corrected_owner_notification.md"), "utf8");

test("a local-path-only body is malformed and locator existence does not deliver it", () => {
  const comment = { id: 5674263522, body: "@/private/tmp/gw06-owner-notification.md" };
  assert.equal(D.deliveryState(comment), "DELIVERY_MALFORMED_CONTENT_NOT_DELIVERED");
  assert.throws(() => D.validateNotification(comment.body), /LOCAL_PATH_ONLY/);
});

test("corrected body has all decision markers, stable links, and no local or secret marker", () => {
  assert.equal(D.validateNotification(body), true);
});

test("delivery readback requires byte-identical body, issue, and author", () => {
  const comment = { body, issue_url: "https://api.github.com/repos/carbonphysicsai/Carbon/issues/42", user: { login: "fitz-lang6" } };
  const expected = { issueNumber: 42, authorLogin: "fitz-lang6" };
  assert.deepEqual(D.verifyReadback(body, comment, expected), { posted: D.sha256(Buffer.from(body)), readback: D.sha256(Buffer.from(body)) });
  assert.throws(() => D.verifyReadback(`${body}changed`, comment, expected), /MISSING_REQUIRED_MARKER|READBACK_DIGEST_MISMATCH/);
});

test("checked-in receipt reproduces from the exact notification and readback observation", () => {
  const receipt = JSON.parse(fs.readFileSync(path.join(DELIVERY, "delivery_receipt.json"), "utf8"));
  const readback = JSON.parse(fs.readFileSync(path.join(DELIVERY, "corrected_comment_readback.json"), "utf8"));
  assert.equal(D.validateReceipt(receipt, body, readback), true);
  const changed = { ...readback, body_sha256: `sha256:${"0".repeat(64)}` };
  assert.throws(() => D.validateReceipt(receipt, body, changed), /READBACK_EVIDENCE/);
});

test("duplicate corrected delivery is rejected", () => {
  const comment = { body };
  assert.equal(D.detectDuplicate([comment]), comment);
  assert.throws(() => D.detectDuplicate([comment, { body }]), /DUPLICATE/);
});

test("posting alone infers neither acknowledgment nor acceptance", () => {
  const comment = { body, issue_url: "https://api.github.com/repos/carbonphysicsai/Carbon/issues/42", user: { login: "fitz-lang6" } };
  assert.equal(D.deliveryState(comment, { issueNumber: 42 }), "DELIVERED_VERIFIED_UNACKNOWLEDGED");
  assert.equal(D.classifyOwnerResponse(null, "2026-09-15T00:00:00Z", ["harshaa765"]), null);
});

test("only a later eligible exact owner response advances, with distinct forms", () => {
  const at = "2026-09-15T04:00:00Z";
  const c = (login, created, text) => ({ user: { login }, created_at: created, body: text });
  assert.equal(D.classifyOwnerResponse(c("other", "2026-09-15T05:00:00Z", `KEEP ${D.DECISION_ID}`), at, ["harshaa765"]), null);
  assert.equal(D.classifyOwnerResponse(c("harshaa765", "2026-09-15T03:00:00Z", `KEEP ${D.DECISION_ID}`), at, ["harshaa765"]), null);
  assert.equal(D.classifyOwnerResponse(c("harshaa765", "2026-09-15T05:00:00Z", "unrelated"), at, ["harshaa765"]), null);
  for (const form of ["KEEP", "CHANGE", "BLOCKED"]) assert.equal(D.classifyOwnerResponse(c("harshaa765", "2026-09-15T05:00:00Z", `${form} ${D.DECISION_ID}`), at, ["harshaa765"]), form);
});

test("owner response classification cannot mint science, rights, or app authority", () => {
  assert.ok(Object.values(response.authority_ceiling).every((value) => value === false));
  const job = G.newJob("job-001", "closed consumer");
  const before = JSON.stringify(job.designs[0]);
  assert.throws(() => G.importResponse(job.designs[0], response));
  assert.equal(JSON.stringify(job.designs[0]), before);
});

test("historical malformed and verified delivery receipts preserve sequence", () => {
  const history = JSON.parse(fs.readFileSync(path.join(DELIVERY, "delivery_history.json"), "utf8"));
  assert.deepEqual(history.events.map((event) => event.status), [
    "PREPARED",
    "DELIVERY_MALFORMED_CONTENT_NOT_DELIVERED",
    "DELIVERY_MALFORMED_CONTENT_NOT_DELIVERED",
    "DELIVERED_VERIFIED_UNACKNOWLEDGED",
    "DELIVERED_VERIFIED_UNACKNOWLEDGED",
    "DELIVERED_VERIFIED_UNACKNOWLEDGED",
  ]);
  assert.equal(history.owner_response.status, "NO_ELIGIBLE_OWNER_RESPONSE_AT_ONE_TIME_CHECK");
  assert.equal(history.follow_on_ticket.generated, false);
});

test("historical delivery stays immutable while the successor changes only the application and leaves Wave selection intact", () => {
  const html = fs.readFileSync(path.join(WB, "Carbon_Opportunity_Workbench.html"));
  assert.notEqual(crypto.createHash("sha256").update(html).digest("hex"), "19a8cc52f2c8dd55d4549a4cb581c39e94aa3293803f7ec0193dc3858daf3404");
  assert.match(html.toString("utf8"), /CarbonSourceAssessment/);
  assert.match(
    fs.readFileSync(path.join(DELIVERY, "delivery_receipt.json"), "utf8"),
    /DELIVERED_VERIFIED_UNACKNOWLEDGED/,
  );
  assert.match(fs.readFileSync(path.resolve(WB, "../../../.agent/WAVE_C.md"), "utf8"), /C-W1-D1/);
});
