import test from "node:test";
import assert from "node:assert/strict";
import { EXPIRY_FAIL_DAYS, EXPIRY_WARN_DAYS, validateKnowledge } from "../tools/validate-knowledge.mjs";
import knowledge from "../knowledge/public-knowledge.v1.json" with { type: "json" };

const DAY_MS = 86_400_000;
const NOW = new Date("2026-09-23T12:00:00Z");
const at = (ms) => new Date(NOW.getTime() + ms).toISOString();
const validate = (subject, now = NOW) => validateKnowledge(subject, { mode: "production", now, checkSourceBytes: false });

// Every card and the release pushed well clear of both windows, so one card can
// be moved into a window and be the only thing reported.
const clear = () => {
  const subject = structuredClone(knowledge);
  subject.release.expires_at = at(365 * DAY_MS);
  for (const card of subject.cards) card.expires_at = at(365 * DAY_MS);
  return subject;
};

const withCardExpiry = (expiresAt) => {
  const subject = clear();
  subject.cards[0].expires_at = expiresAt;
  return { subject, id: subject.cards[0].id };
};

test("thresholds are the reviewed values", () => {
  assert.equal(EXPIRY_WARN_DAYS, 30);
  assert.equal(EXPIRY_FAIL_DAYS, 7);
});

test("a card inside the warning window warns and one just outside it does not", async () => {
  const inside = withCardExpiry(at(EXPIRY_WARN_DAYS * DAY_MS));
  const warned = await validate(inside.subject);
  assert.equal(warned.valid, true);
  assert.deepEqual(warned.warnings.filter((w) => w.startsWith("card_expires")), [`card_expires_within_30d:${inside.id}`]);
  assert.equal(warned.expiring.length, 1);
  assert.equal(warned.expiring[0].days_left, 30);

  // The specimen above shows this check reports; here it must report nothing.
  const outside = withCardExpiry(at(EXPIRY_WARN_DAYS * DAY_MS + 1));
  const quiet = await validate(outside.subject);
  assert.equal(quiet.valid, true);
  assert.deepEqual(quiet.warnings.filter((w) => w.includes("expires")), []);
  assert.deepEqual(quiet.expiring, []);
});

test("a card inside the failure window fails validation, and one just outside only warns", async () => {
  const inside = withCardExpiry(at(EXPIRY_FAIL_DAYS * DAY_MS));
  const failed = await validate(inside.subject);
  assert.equal(failed.valid, false);
  assert.deepEqual(failed.errors, [`card_expires_within_7d:${inside.id}`]);

  const outside = withCardExpiry(at(EXPIRY_FAIL_DAYS * DAY_MS + 1));
  const warned = await validate(outside.subject);
  assert.equal(warned.valid, true);
  assert.ok(warned.warnings.includes(`card_expires_within_30d:${outside.id}`));
});

test("an expired or unreadable card expiry fails validation instead of going quiet", async () => {
  for (const expiresAt of [at(0), at(-DAY_MS), "not-a-date", undefined]) {
    const { subject, id } = withCardExpiry(expiresAt);
    const result = await validate(subject);
    assert.equal(result.valid, false, String(expiresAt));
    assert.deepEqual(result.errors, [`card_expired_or_invalid:${id}`], String(expiresAt));
  }
});

test("the release expiry is held to the same windows", async () => {
  const warn = clear();
  warn.release.expires_at = at(20 * DAY_MS);
  const warned = await validate(warn);
  assert.equal(warned.valid, true);
  assert.ok(warned.warnings.includes("release_expires_within_30d"));

  const fail = clear();
  fail.release.expires_at = at(3 * DAY_MS);
  const failed = await validate(fail);
  assert.equal(failed.valid, false);
  assert.deepEqual(failed.errors, ["release_expires_within_7d"]);
});

test("the committed knowledge is caught before its October cards go quiet", async () => {
  const october = knowledge.cards.filter((card) => card.expires_at.startsWith("2026-10-16")).map((card) => card.id).sort();
  assert.ok(october.length > 0);
  const warned = await validate(knowledge, new Date("2026-09-23T00:00:00Z"));
  assert.equal(warned.valid, true);
  assert.deepEqual(warned.warnings.filter((w) => w.startsWith("card_expires")).map((w) => w.split(":")[1]).sort(), october);

  const failed = await validate(knowledge, new Date("2026-10-10T00:00:00Z"));
  assert.equal(failed.valid, false);
  assert.deepEqual(failed.errors.map((e) => e.split(":")[1]).sort(), october);
});
