"use strict";

const { chromium } = require("playwright");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const ROOT = path.resolve(__dirname, "..");
const ARTIFACT = path.join(ROOT, "Carbon_Opportunity_Workbench.html");
const BASE = path.join(ROOT, "source_assessment", "repository_snapshot", "v1");
const EXAMPLE = path.join(BASE, "candidate", "public_example_workspace.json");
const ASSESSMENT = path.join(BASE, "candidate", "assessment_pending_adoption.json");
const checks = [];

function check(name, value) {
  if (!value) throw Error("FAILED: " + name);
  checks.push(name);
}

async function pageText(page, selector) {
  return page.locator(selector).innerText();
}

(async () => {
  const errors = [], outbound = [];
  const browser = await chromium.launch({
    headless: true,
    executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  });
  const context = await browser.newContext({ acceptDownloads: true });
  context.on("request", (request) => {
    if (/^https?:/.test(request.url())) outbound.push(request.url());
  });
  context.on("page", (opened) =>
    opened.on("pageerror", (error) => errors.push(String(error))),
  );
  const page = await context.newPage();
  page.setDefaultTimeout(15000);
  page.on("dialog", (dialog) => dialog.accept());
  await page.goto("file://" + ARTIFACT);

  await page.locator("#goal-workspace-file").setInputFiles(EXAMPLE);
  await page.waitForFunction(() =>
    document.querySelector("#toast").textContent.includes("Imported v0.8"),
  );
  await page.locator('[data-tab="jobs"]').click();
  let text = await pageText(page, "#jobs-view");
  check(
    "ordinary workspace import loads the exact retained request without a response or trusted root",
    text.includes("GW07-BURGERS-DYNAMICS-REQUEST-001") &&
      text.includes("PENDING_EXACT_OWNER_ADOPTION") &&
      !text.includes("MATCHED_APPROVED_SOURCE_SNAPSHOT"),
  );
  check(
    "application exposes the new content-bound installed snapshot",
    text.includes("OWNER-GW07-RYAN-SNAPSHOT-01/sha256-49acb3598d034cf7/v1") &&
      text.includes("as of 2026-09-16"),
  );

  await page.locator("#source-assessment-file").setInputFiles(ASSESSMENT);
  await page.waitForFunction(() =>
    document.querySelector("#toast").textContent.includes("matched the installed repository snapshot"),
  );
  text = await pageText(page, "#jobs-view");
  check(
    "ordinary file control verifies the real admitted production assessment",
    text.includes("MATCHED_APPROVED_SOURCE_SNAPSHOT") &&
      text.includes("CONSUMER_DERIVED_REPOSITORY_SNAPSHOT_MATCH"),
  );
  check(
    "two technical questions are answered and the fixed-evidence relationship remains partial",
    (text.match(/ANSWERED_TECHNICAL/g) || []).length === 2 &&
      text.includes("PARTIAL_STILL_OPEN") &&
      text.includes("resolves 0 review reasons"),
  );
  check(
    "preparer owner and authority ceiling remain distinct and visible",
    text.includes("Prepared by: GOAL-WORKBENCH-07 Engineering") &&
      text.includes("admitted owner: github:jbequ5") &&
      text.includes("qualification effect NONE") &&
      text.includes("rights effect NONE"),
  );

  await page.locator('[data-tab="owner-console"]').click();
  const ownerText = await pageText(page, "#owner-console-view");
  check(
    "Owner Console shows a returned scoped answer and its open question",
    ownerText.includes("REVIEW_SCOPED_SOURCE_ASSESSMENT") &&
      ownerText.includes("GW07:FIXED_EVIDENCE_RELATIONSHIP") &&
      ownerText.includes("SOURCE_ASSESSMENT_RETURNED"),
  );
  check(
    "Owner Console does not report active compute or another adoption wait",
    !ownerText.includes("ACTIVE_NATIVE_EVIDENCE") &&
      !ownerText.includes("WAIT_FOR_EXACT_RYAN_ADOPTION") &&
      !ownerText.includes("PREPARED_AWAITING_EXACT_OWNER_ADOPTION"),
  );

  await page.locator('[data-tab="jobs"]').click();
  await page.locator("#source-assessment-file").setInputFiles(ASSESSMENT);
  await page.waitForFunction(() =>
    document.querySelector("#toast").textContent.includes("replay deduplicated"),
  );
  check(
    "exact replay deduplicates without another owner decision",
    (await pageText(page, "#jobs-view")).includes("MATCHED_APPROVED_SOURCE_SNAPSHOT"),
  );

  const changedPath = path.join(os.tmpdir(), "gw07a-whitespace-changed-assessment.json");
  fs.writeFileSync(
    changedPath,
    fs.readFileSync(ASSESSMENT, "utf8").replace("{\n", "{  \n"),
  );
  const beforeChangedImport = await pageText(page, "#jobs-view");
  await page.locator("#source-assessment-file").setInputFiles(changedPath);
  await page.waitForFunction(() =>
    document.querySelector("#toast").textContent.includes("import rejected"),
  );
  check(
    "changed raw bytes reject atomically and retain the prior verified state",
    (await pageText(page, "#jobs-view")) === beforeChangedImport,
  );

  const workspaceDownload = page.waitForEvent("download");
  await page.locator("#export-goal").click();
  const exported = await workspaceDownload;
  const exportedPath = await exported.path();
  const fresh = await context.newPage();
  fresh.setDefaultTimeout(15000);
  fresh.on("dialog", (dialog) => dialog.accept());
  await fresh.goto("file://" + ARTIFACT);
  await fresh.locator("#goal-workspace-file").setInputFiles(exportedPath);
  await fresh.waitForFunction(() =>
    document.querySelector("#toast").textContent.includes("Imported v0.8"),
  );
  await fresh.locator('[data-tab="jobs"]').click();
  const reloaded = await pageText(fresh, "#jobs-view");
  check(
    "fresh application save/reload revalidates from installed root",
    reloaded.includes("MATCHED_APPROVED_SOURCE_SNAPSHOT") &&
      reloaded.includes("PARTIAL_STILL_OPEN") &&
      reloaded.includes("resolves 0 review reasons"),
  );

  await fresh.setViewportSize({ width: 390, height: 844 });
  check(
    "admitted source-assessment panel remains usable at narrow width",
    await fresh.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  );
  check("browser emitted no script error", errors.length === 0);
  check("source-assessment workflow emitted zero external requests", outbound.length === 0);

  const result = {
    artifact: "Carbon_Opportunity_Workbench.html",
    scope: "GOAL-WORKBENCH-07A real installed-snapshot import, owner status, replay, raw-byte rejection, save/reload, narrow-width, and offline browser journey",
    engine: "Google Chrome (Chromium)",
    passed: checks.length,
    failed: 0,
    checks,
    page_errors: errors,
    outbound_requests: outbound,
    source_admission: "OWNER_ADOPTED_ASSESSMENT_ADMITTED",
    positive_path: "REAL_INSTALLED_PRODUCTION_SNAPSHOT",
    snapshot_id: "OWNER-GW07-RYAN-SNAPSHOT-01/sha256-49acb3598d034cf7/v1",
    safari_webkit: "UNAVAILABLE_NOT_RUN",
    authority_effect: "NONE"
  };
  fs.writeFileSync(
    path.join(ROOT, "tests", "browser_source_assessment_results.json"),
    JSON.stringify(result, null, 2) + "\n",
  );
  console.log(JSON.stringify({ passed: checks.length, failed: 0 }, null, 2));
  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
