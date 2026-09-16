"use strict";
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const ROOT = path.resolve(__dirname, "..");
const PREVIEW = path.join(ROOT, "Carbon_Client_Intake_Preview.html");
const WORKBENCH = path.join(ROOT, "Carbon_Opportunity_Workbench.html");
const FIXTURES = path.join(ROOT, "intake", "fixtures");
const ASSESSMENT = path.join(ROOT, "source_assessment/repository_snapshot/v1/candidate/assessment_pending_adoption.json");
const checks = [];
function check(name, value) { assert.ok(value, name); checks.push(name); }
async function saveDownload(page, selector, target) {
  const pending = page.waitForEvent("download");
  await page.locator(selector).click();
  await (await pending).saveAs(target);
}
(async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "carbon-intake-browser-"));
  const errors = [], outbound = [];
  const browser = await chromium.launch({ headless: true, executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" });
  const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 1440, height: 1000 } });
  context.on("request", (request) => { if (/^(https?|wss?):/.test(request.url())) outbound.push(request.url()); });
  const preview = await context.newPage();
  preview.on("pageerror", (error) => errors.push(String(error)));
  await preview.goto("file://" + PREVIEW);
  check("local preview exposes the intake activity in the first viewport", await preview.locator("#intake-form").isVisible());
  const previewText = await preview.locator("body").innerText();
  check("preview states local-only boundary and offers no submit or contact capture", previewText.includes("nothing is transmitted") && !previewText.includes("Inquiry received") && (await preview.locator('input[type="email"], input[type="file"], button:has-text("Submit")').count()) === 0);
  await preview.locator('[data-text="intended_decision"]').fill("Decide whether the current method can support faster design comparisons.");
  await preview.locator('[data-text="requested_result"]').fill("Compare turnaround and one engineering output.");
  await preview.locator('[data-text="current_baseline"]').fill("Existing numerical method");
  await preview.locator('[data-text="baseline_limitation"]').fill("Turnaround is inconvenient; accuracy is unknown.");
  await preview.locator('[data-text="consequential_error"]').fill('Wrong comparison <img src=x onerror="window.intakePwned=true">');
  await preview.locator('[data-quantity-state="prediction_latency"]').selectOption("RANGE");
  await preview.locator('[data-quantity-unit="prediction_latency"]').fill("seconds/query");
  await preview.locator('[data-quantity-min="prediction_latency"]').fill("1");
  await preview.locator('[data-quantity-max="prediction_latency"]').fill("3");
  check("summary preserves unknowns range units and inert text", await preview.locator("#summary-text").innerText().then((text) => text.includes("1–3 seconds/query") && text.includes("onerror") && text.includes("Preparation time: unknown")));
  await preview.screenshot({ path: path.join(ROOT, "tests/preview_intake.png"), fullPage: true });
  const draftPath = path.join(tmp, "downloaded-intake.json");
  await saveDownload(preview, "#export-intake", draftPath);
  check("export reports a local download rather than submission", await preview.locator("#intake-status").innerText().then((text) => text.includes("Nothing was transmitted")));
  const draft = JSON.parse(fs.readFileSync(draftPath, "utf8"));
  check("download is the closed v1 transport with no authority fields", draft.schema_version === "carbon.client-intake.draft.v1" && draft.qualified === undefined && draft.approved === undefined);

  const workbench = await context.newPage();
  workbench.on("pageerror", (error) => errors.push(String(error)));
  workbench.on("dialog", (dialog) => dialog.accept());
  await workbench.goto("file://" + WORKBENCH);
  await workbench.locator('[data-tab="jobs"]').click();
  await workbench.locator("#intake-draft-file").setInputFiles(draftPath);
  await workbench.waitForFunction(() => document.querySelector("#toast").textContent.includes("preview prepared"));
  check("Workbench previews before mutation", (await workbench.locator("#jobs-view").innerText()).includes("CREATE_NEW_JOB") && (await workbench.locator("[data-job-select]").count()) === 0);
  await workbench.locator("#commit-intake-draft").click();
  check("ordinary commit creates one assisted unassessed job with source lineage", (await workbench.locator("[data-job-select]").count()) === 1 && (await workbench.locator("#route-choice").inputValue()) === "UNASSESSED" && (await workbench.locator("#jobs-view").innerText()).includes("Source intake lineage (1)"));
  await workbench.locator('[data-job="lead"]').fill("S1");
  await workbench.locator('[data-job="accountable_owner"]').fill("Synthetic owner");
  await workbench.locator("#route-choice").selectOption("USE_EXISTING_CAPABILITY");
  await workbench.locator("#route-rationale").fill("Review the reported baseline before Challenge authoring.");
  await workbench.locator("#route-source").fill("reported-current-method");
  await workbench.locator("#route-basis").fill("Client assertion only; applicability unverified.");
  await workbench.locator("#route-conditions").fill("output compatibility\ndeployment evidence");
  await workbench.locator("#route-decision").fill("Clarify baseline applicability");
  await workbench.locator("#save-route").click();
  await workbench.locator("#handoff-question").fill("Can the current baseline satisfy the exact requested output and use?");
  await workbench.locator("#prepare-handoff").click();
  check("existing-capability route prepares one handoff without authoring or send", await workbench.locator("#jobs-view").innerText().then((text) => text.includes("USE_EXISTING_CAPABILITY") && text.includes("PREPARED") && text.includes("Send / launch unavailable")));

  await workbench.locator("#intake-draft-file").setInputFiles(draftPath);
  await workbench.waitForFunction(() => document.querySelector("#jobs-view").textContent.includes("EXACT_REPLAY"));
  await workbench.locator("#commit-intake-draft").click();
  check("exact replay creates no duplicate job or lineage", (await workbench.locator("[data-job-select]").count()) === 1 && (await workbench.locator("#jobs-view").innerText()).includes("Source intake lineage (1)"));

  const sessionPath = path.join(tmp, "session.json");
  await saveDownload(workbench, "#export-goal", sessionPath);
  const restored = await context.newPage();
  restored.on("pageerror", (error) => errors.push(String(error)));
  restored.on("dialog", (dialog) => dialog.accept());
  await restored.goto("file://" + WORKBENCH);
  await restored.locator("#goal-workspace-file").setInputFiles(sessionPath);
  await restored.waitForFunction(() => document.querySelector("#toast").textContent.includes("Imported v0.8"));
  await restored.locator('[data-tab="jobs"]').click();
  check("fresh-session save reload retains intake lineage and route", await restored.locator("#jobs-view").innerText().then((text) => text.includes("Source intake lineage (1)") && text.includes("USE_EXISTING_CAPABILITY")));

  await restored.locator("#intake-draft-file").setInputFiles(path.join(FIXTURES, "fresh_burgers_v1.json"));
  await restored.waitForFunction(() => document.querySelector("#jobs-view").textContent.includes("CREATE_NEW_JOB"));
  await restored.locator("#commit-intake-draft").click();
  await restored.locator("#source-assessment-file").setInputFiles(ASSESSMENT);
  await restored.waitForFunction(() => document.querySelector("#toast").textContent.includes("import rejected"));
  check("fresh Burgers-like intake cannot borrow the admitted 07A assessment", !(await restored.locator("#jobs-view").innerText()).includes("MATCHED_APPROVED_SOURCE_SNAPSHOT"));

  const jobsBeforeMalformed = await restored.locator("[data-job-select]").count();
  await restored.locator("#intake-draft-file").setInputFiles({
    name: "malformed-utf8.carbon-intake.json",
    mimeType: "application/json",
    buffer: Buffer.from([0xff, 0xfe, 0x7b]),
  });
  await restored.waitForFunction(() => document.querySelector("#toast").textContent.includes("preview rejected"));
  check("malformed UTF-8 rejects before workspace mutation", (await restored.locator("[data-job-select]").count()) === jobsBeforeMalformed);

  await restored.setViewportSize({ width: 390, height: 844 });
  check("narrow Workbench remains free of page-level horizontal overflow", await restored.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 2));
  await preview.setViewportSize({ width: 390, height: 844 });
  check("narrow intake preview remains free of page-level horizontal overflow", await preview.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 2));
  await preview.screenshot({ path: path.join(ROOT, "tests/preview_intake_mobile.png"), fullPage: true });
  check("preview and Workbench made zero off-device requests", outbound.length === 0);
  check("malicious text never executed", await preview.evaluate(() => window.intakePwned === undefined));
  check("browser contexts reported no page errors", errors.length === 0);
  const previewSource = fs.readFileSync(PREVIEW, "utf8");
  check("public preview excludes internal snapshot evidence and local paths", !previewSource.includes("OWNER-GW07-RYAN-SNAPSHOT-01") && !previewSource.includes("approved_assessments") && !previewSource.includes("/Users/"));
  fs.writeFileSync(path.join(ROOT, "tests/browser_intake_results.json"), JSON.stringify({ browser: "Google Chrome", checks, errors, outbound_requests: outbound, authority: "Local synthetic product-flow evidence only; no customer, scientific, rights, security, hosting, or launch qualification." }, null, 2) + "\n");
  await browser.close();
  console.log(JSON.stringify({ checks: checks.length, failures: 0, outbound_requests: outbound.length }));
})().catch((error) => { console.error(error); process.exit(1); });
