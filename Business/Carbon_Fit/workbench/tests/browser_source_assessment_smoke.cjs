"use strict";

const { chromium } = require("playwright");
const fs = require("node:fs");
const path = require("node:path");
const ROOT = path.resolve(__dirname, "..");
const ARTIFACT = path.join(ROOT, "Carbon_Opportunity_Workbench.html");
const BASE = path.join(ROOT, "source_assessment", "repository_snapshot", "v1");
const load = (name) => JSON.parse(fs.readFileSync(path.join(BASE, name), "utf8"));
const checks = [];
function check(name, value) { if (!value) throw Error("FAILED: " + name); checks.push(name); }

(async () => {
  const errors = [], outbound = [];
  const browser = await chromium.launch({ headless: true, executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
  page.setDefaultTimeout(15000);
  page.on("pageerror", (error) => errors.push(String(error)));
  page.on("request", (request) => { if (/^https?:/.test(request.url())) outbound.push(request.url()); });
  page.on("dialog", (dialog) => dialog.accept());
  await page.goto("file://" + ARTIFACT);
  await page.locator('[data-tab="jobs"]').click();
  await page.locator("#new-job").click();
  await page.locator("#journey-adapt").click();
  await page.locator("#c05-evidence-file").setInputFiles(path.join(ROOT, "data", "c05_public_development_evidence_v1.json"));
  await page.waitForFunction(() => document.querySelector("#toast").textContent.includes("scientific decision remains unresolved"));
  check("source-assessment panel exposes installed empty production snapshot", await page.locator("#jobs-view").innerText().then((text) => text.includes("OWNER-GW07-RYAN-SNAPSHOT-01/empty-production-index/v1") && text.includes("PENDING_EXACT_OWNER_ADOPTION")));
  await page.locator("#prepare-source-assessment").click();
  await page.waitForFunction(() => document.querySelector("#toast").textContent.includes("Nothing was sent or adopted"));
  check("normal UI freezes and prepares exact request", await page.locator("#jobs-view").innerText().then((text) => text.includes("Frozen request") && text.includes("PREPARED_LOCAL_NOT_TRANSMITTED")));
  const requestDownload = page.waitForEvent("download");
  await page.locator("#export-source-assessment").click();
  const downloaded = await requestDownload;
  const exportedRequest = JSON.parse(fs.readFileSync(await downloaded.path(), "utf8"));
  check("export binds current job design revision and semantic subject", exportedRequest.schema_version === "carbon.goal-workbench.source-assessment-request.v2" && exportedRequest.association.design_revision === 1 && exportedRequest.subject_digest.startsWith("sha256:"));
  await page.locator("#source-assessment-file").setInputFiles(path.join(BASE, "candidate", "assessment_pending_adoption.json"));
  await page.waitForFunction(() => document.querySelector("#toast").textContent.includes("Source-assessment import rejected"));
  check("unadopted candidate remains rejected without positive receipt", await page.locator("#jobs-view").innerText().then((text) => text.includes("PENDING_EXACT_OWNER_ADOPTION") && !text.includes("MATCHED_APPROVED_SOURCE_SNAPSHOT")));
  await page.locator('[data-tab="owner-console"]').click();
  check("Owner Console points to Ryan adoption and never active computation", await page.locator("#owner-console-view").innerText().then((text) => text.includes("WAIT_FOR_EXACT_RYAN_ADOPTION") && text.includes("WAITING_ON_DEPENDENCY") && !text.includes("ACTIVE_NATIVE_EVIDENCE")));
  await page.locator('[data-tab="jobs"]').click();
  const workspaceDownload = page.waitForEvent("download");
  await page.locator("#export-goal").click();
  const workspace = await workspaceDownload;
  await page.locator("#goal-workspace-file").setInputFiles(await workspace.path());
  await page.waitForFunction(() => document.querySelector("#toast").textContent.includes("Imported v0.7"));
  check("save reload preserves frozen request but creates no adoption", await page.locator("#jobs-view").innerText().then((text) => text.includes("Frozen request") && text.includes("PENDING_EXACT_OWNER_ADOPTION")));

  const purePositive = await page.evaluate(async ({ profile, index, responseRaw, design, request }) => {
    design.source_assessments.requests.push(request);
    design.source_assessments.current_request_id = request.request_id;
    const verifier = CarbonSourceAssessment.createVerifier(profile, index, { testMode: true });
    const result = await CarbonSourceAssessment.importResponse(design, responseRaw, verifier);
    return { status: result.status, qualification: design.decision.scientific_qualification, rights: design.decision.security_rights, receipts: design.source_assessments.receipts.length };
  }, {
    profile: load("test_fixtures/profile.test-only.json"),
    index: load("test_fixtures/approved_assessments.test-only.json"),
    responseRaw: fs.readFileSync(path.join(BASE, "test_fixtures", "assessment.test-only.json"), "utf8"),
    design: load("candidate/public_design.json"),
    request: load("candidate/request.json"),
  });
  check("isolated test root exercises actual browser consumer without qualification", purePositive.status === "MATCHED_APPROVED_SOURCE_SNAPSHOT" && purePositive.receipts === 1 && purePositive.qualification === "NOT_QUALIFIED" && purePositive.rights === "UNRESOLVED");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator('[data-tab="jobs"]').click();
  check("source-assessment panel remains usable at narrow width", await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  check("browser emitted no script error", errors.length === 0);
  check("source-assessment workflow emitted zero external requests", outbound.length === 0);
  const result = { artifact: "Carbon_Opportunity_Workbench.html", scope: "GOAL-WORKBENCH-07 repository-snapshot request, rejection, test-only positive, owner state, save/reload, and offline browser journey", engine: "Google Chrome (Chromium)", passed: checks.length, failed: 0, checks, page_errors: errors, outbound_requests: outbound, source_admission: "PENDING_EXACT_OWNER_ADOPTION", positive_path: "TEST_ONLY_ISOLATED_ROOT" };
  fs.writeFileSync(path.join(ROOT, "tests", "browser_source_assessment_results.json"), JSON.stringify(result, null, 2) + "\n");
  console.log(JSON.stringify({ passed: checks.length, failed: 0 }, null, 2));
  await browser.close();
})().catch((error) => { console.error(error); process.exit(1); });
