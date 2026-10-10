import test from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdir, mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { EXPIRY_FAIL_DAYS, EXPIRY_WARN_DAYS, validateKnowledge } from "../tools/validate-knowledge.mjs";
import { decideMode } from "../tools/ci-knowledge-check.mjs";
import knowledge from "../knowledge/public-knowledge.v1.json" with { type: "json" };

const DAY_MS = 86_400_000;
const CHECK = fileURLToPath(new URL("../tools/ci-knowledge-check.mjs", import.meta.url));
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

test("the committed knowledge is caught before its soonest cards go quiet", async () => {
  // Read from the committed dates rather than a pinned month. The owner moves
  // these on review (the whole point of the expiry), so a hardcoded month makes
  // the refresh itself fail here instead of a regression. Both assertions are
  // unchanged: warned inside the warning window, failed inside the failure one.
  const soonest = knowledge.cards.map((card) => card.expires_at).sort()[0];
  const due = knowledge.cards.filter((card) => card.expires_at === soonest).map((card) => card.id).sort();
  assert.ok(due.length > 0);
  const before = (days) => new Date(Date.parse(soonest) - days * DAY_MS);

  const warned = await validate(knowledge, before(EXPIRY_WARN_DAYS - 1));
  assert.equal(warned.valid, true);
  assert.deepEqual(warned.warnings.filter((w) => w.startsWith("card_expires")).map((w) => w.split(":")[1]).sort(), due);

  const failed = await validate(knowledge, before(EXPIRY_FAIL_DAYS - 1));
  assert.equal(failed.valid, false);
  assert.deepEqual(failed.errors.map((e) => e.split(":")[1]).sort(), due);
});

test("per-PR CI can demote wall-clock findings, and only those", async () => {
  const aged = clear();
  aged.cards[0].expires_at = at(3 * DAY_MS);
  aged.cards[1].expires_at = at(-DAY_MS);
  aged.release.expires_at = at(5 * DAY_MS);
  const aging = [`card_expires_within_7d:${aged.cards[0].id}`, `card_expired_or_invalid:${aged.cards[1].id}`, "release_expires_within_7d"].sort();
  // Specimen: strict mode fails on exactly these findings.
  const strict = await validate(aged);
  assert.equal(strict.valid, false);
  assert.deepEqual(strict.errors, aging);
  const relaxed = await validateKnowledge(aged, { mode: "production", now: NOW, checkSourceBytes: false, timeFindings: "warning" });
  assert.equal(relaxed.valid, true, JSON.stringify(relaxed.errors));
  for (const code of aging) assert.ok(relaxed.warnings.includes(code), code);

  // A malformed expiry and a structural defect are not ageing; they stay errors.
  const broken = clear();
  broken.cards[0].expires_at = "not-a-date";
  broken.cards[1].passages = [];
  const still = await validateKnowledge(broken, { mode: "production", now: NOW, checkSourceBytes: false, timeFindings: "warning" });
  assert.equal(still.valid, false);
  assert.ok(still.errors.includes(`card_expired_or_invalid:${broken.cards[0].id}`));
  assert.ok(still.errors.includes(`missing_answer_basis:${broken.cards[1].id}`));

  const unknown = await validateKnowledge(clear(), { mode: "production", now: NOW, checkSourceBytes: false, timeFindings: "ignore" });
  assert.deepEqual(unknown.errors, ["invalid_time_findings_mode"]);
});

// --- which check per-PR CI runs ----------------------------------------------

const git = (cwd, ...args) => execFileSync("git", ["-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", ...args], { cwd, encoding: "utf8" });

const fixtureRepository = async () => {
  const root = await mkdtemp(join(tmpdir(), "ask-carbon-knowledge-mode-"));
  await mkdir(join(root, "website/ask-carbon/knowledge"), { recursive: true });
  await writeFile(join(root, "website/ask-carbon/knowledge/cards.json"), "{}\n");
  await writeFile(join(root, "README"), "base\n");
  git(root, "init", "-q", "-b", "main");
  git(root, "add", "-A");
  git(root, "commit", "-q", "-m", "base");
  git(root, "update-ref", "refs/remotes/origin/main", "HEAD");
  return root;
};

test("per-PR CI relaxes expiry only when git shows the knowledge unchanged", async () => {
  const root = await fixtureRepository();
  await writeFile(join(root, "README"), "unrelated change\n");
  git(root, "commit", "-q", "-am", "unrelated");
  assert.equal(decideMode({ repository: root }).mode, "RELAXED");

  await writeFile(join(root, "website/ask-carbon/knowledge/cards.json"), "{\"edited\":true}\n");
  git(root, "commit", "-q", "-am", "edit knowledge");
  const edited = decideMode({ repository: root });
  assert.equal(edited.mode, "STRICT");
  assert.match(edited.reason, /edits website\/ask-carbon\/knowledge/);
});

test("per-PR CI fails closed to the strict check when git cannot compare", async () => {
  const root = await fixtureRepository();
  // Specimen: the same repository with a readable base relaxes, so the strict
  // results below come from the missing comparison and nothing else.
  assert.equal(decideMode({ repository: root }).mode, "RELAXED");
  for (const decision of [
    decideMode({ repository: root, base: "origin/no-such-branch" }),
    decideMode({ repository: join(root, "not-a-repository") }),
  ]) {
    assert.equal(decision.mode, "STRICT");
    assert.match(decision.reason, /git could not compare .* failing closed/);
  }
  git(root, "update-ref", "-d", "refs/remotes/origin/main");
  assert.equal(decideMode({ repository: root }).mode, "STRICT", "a checkout without origin/main is strict");

  // The command CI runs reports the mode it chose.
  const printed = execFileSync(process.execPath, [CHECK, "--repository", root, "--decide-only"], { encoding: "utf8" });
  assert.match(printed, /^Ask Carbon knowledge check: STRICT \(git could not compare/);
});
