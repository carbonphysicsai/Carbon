"use strict";
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const ROOT = path.resolve(__dirname, "..");
const ARTIFACT = path.join(ROOT, "Carbon_Opportunity_Workbench.html");
const checks = [];
function check(name, condition) {
  assert.ok(condition, name);
  checks.push(name);
}
async function download(page, selector, target) {
  const waiting = page.waitForEvent("download");
  await page.locator(selector).click();
  const item = await waiting;
  await item.saveAs(target);
  return JSON.parse(fs.readFileSync(target, "utf8"));
}

(async () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "carbon-team-review-"));
  const outbound = [], errors = [];
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.CARBON_BROWSER_EXECUTABLE
      ? { executablePath: process.env.CARBON_BROWSER_EXECUTABLE }
      : {}),
  });
  const page = await browser.newPage({ viewport: process.env.CARBON_MOBILE === "1" ? { width: 390, height: 844 } : { width: 1440, height: 1000 } });
  page.on("request", (request) => {
    if (/^(https?|wss?):/.test(request.url())) outbound.push(request.url());
  });
  page.on("pageerror", (error) => errors.push(String(error)));
  await page.goto("file://" + ARTIFACT);
  await page.locator('[data-tab="jobs"]').click();
  await page.locator("#new-job").click();
  await page.locator('[data-job="title"]').fill("Synthetic cold-plate review");
  await page.locator('[data-assignment="client_words"]').fill("We want to predict cold-plate temperatures faster.");
  await page.locator('[data-assignment="intended_decision"]').fill("Choose a design without waiting for every full simulation.");
  await page.locator('[data-assignment="credible_baseline"]').fill("Current simulation workflow; duration unknown.");
  await page.locator("#team-reviewer").fill("Synthetic reviewer");
  await page.locator("#team-queue-state").selectOption("UNDER_REVIEW");
  await page.locator("#team-current-action").fill("Clarify the operating range before selecting a route.");
  await page.locator("#save-team-review").click();
  check("queue state is visible", (await page.locator("#team-review-panel").innerText()).includes("UNDER_REVIEW"));
  await page.locator("#team-correction-field").fill("assignment.client_words");
  await page.locator("#team-correction-value").fill("We want faster cold-plate temperature predictions.");
  await page.locator("#team-correction-reason").fill("Transcription only");
  await page.locator("#add-team-correction").click();
  await page.waitForSelector("#team-review-panel details");
  check("original words remain visible", (await page.locator('[data-assignment="client_words"]').inputValue()).includes("predict cold-plate"));
  check("correction is separately visible", (await page.locator("#team-review-panel").textContent()).includes("Transcription only"));
  await page.locator('[data-assessment="operating_envelope"]').fill("Proposed load and flow range; exact bounds unknown.");
  await page.locator('[data-assessment="smallest_useful_pilot"]').fill("Compare hotspot and ranking behavior on an agreed synthetic subset.");
  await page.locator('[data-assessment="measurement_requirements"]').fill("Hotspot and ranking observations; limits unresolved.");
  await page.locator('[data-assessment="measurement_requirements"]').blur();
  await page.locator("#team-note").fill("private-team-sentinel");
  await page.locator("#add-team-note").click();
  const client = await download(page, "#export-pilot-brief", path.join(directory, "client.json"));
  const internal = await download(page, "#export-execution-brief", path.join(directory, "internal.json"));
  check("outputs bind the same design", client.design_id === internal.design_id && client.design_revision === internal.design_revision);
  check("client output contains bounded pilot", client.proposed_scope.includes("Compare hotspot"));
  check("private note is excluded from client output", !JSON.stringify(client).includes("private-team-sentinel"));
  check("private note remains in internal workspace projection only", !JSON.stringify(internal).includes("private-team-sentinel"));
  check("accepted and pending core dependencies remain distinct", internal.assessment.scientific_task_dependencies.map((item) => item.availability).join(",") === "AVAILABLE_NOT_REQUESTED,CORE_INTERFACE_PENDING,AVAILABLE_NOT_REQUESTED");
  await page.locator("#team-review-panel details").last().locator("summary").click();
  await page.locator("#run-physical-definition-check").click();
  const checkedInternal = await download(page, "#export-execution-brief", path.join(directory, "internal-checked.json"));
  const physical = checkedInternal.assessment.scientific_task_dependencies[0];
  check("physical definition check returns through accepted adapter", physical.availability === "RETURNED" && physical.result.status === "INPUTS_UNRESOLVED");
  check("structural result has no qualification effect", physical.result.qualification === "NOT_QUALIFIED" && physical.result.authority_effect === "NONE");
  const sessionPath = path.join(directory, "session.json");
  await download(page, "#export-goal", sessionPath);
  await page.reload();
  await page.locator("#goal-workspace-file").setInputFiles(sessionPath);
  await page.locator('[data-tab="jobs"]').click();
  const reopenedInternal = await download(page, "#export-execution-brief", path.join(directory, "internal-reopened.json"));
  check("save and reload revalidate the same exact observation", reopenedInternal.assessment.scientific_task_dependencies[0].check_id === physical.check_id && reopenedInternal.assessment.scientific_task_dependencies[0].availability === "RETURNED");
  await page.locator('[data-tab="owner-console"]').click();
  check("Owner Console intake queue contains job", (await page.locator("#owner-console-view").innerText()).includes("Synthetic cold-plate review"));
  check("Owner Console keeps reviewer and action", (await page.locator("#owner-console-view").innerText()).includes("Synthetic reviewer") && (await page.locator("#owner-console-view").innerText()).includes("Clarify the operating range"));
  await page.setViewportSize({ width: 390, height: 844 });
  check("narrow Owner Console remains rendered", await page.locator("#owner-console-view").isVisible());
  check("offline artifact made zero external requests", outbound.length === 0);
  check("no browser page errors", errors.length === 0);
  await browser.close();
  fs.writeFileSync(
    path.join(ROOT, "tests/browser_team_review_results.json"),
    JSON.stringify({ passed: checks.length, failed: 0, checks }, null, 2) + "\n",
  );
  console.log(JSON.stringify({ passed: checks.length, failed: 0 }, null, 2));
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
