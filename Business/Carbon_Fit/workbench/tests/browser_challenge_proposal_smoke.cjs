"use strict";
// Browser acceptance for the Pilot Designer's proposed Challenge
// (GOAL-WORKBENCH-16 slice 2), against the generated page. Local diagnostic:
// it needs Playwright and a Chromium, and CI does not run it.
//
//   NODE_PATH=/path/to/node_modules node tests/browser_challenge_proposal_smoke.cjs
//
// Prints a JSON summary and writes nothing into the repository.
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const ROOT = path.resolve(__dirname, "..");
const PAGE = "file://" + path.join(ROOT, "Carbon_Client_Pilot_Designer_Preview.html");
const checks = [];
function check(name, value) { assert.ok(value, name); checks.push(name); }
const text = async (page, selector) => (await page.locator(selector).textContent()) || "";

(async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "carbon-proposal-"));
  const errors = [], outbound = [];
  const browser = await chromium.launch({ headless: true, ...(process.env.CARBON_BROWSER_EXECUTABLE ? { executablePath: process.env.CARBON_BROWSER_EXECUTABLE } : {}) });
  const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 1440, height: 1000 } });
  context.on("request", (request) => { if (/^(https?|wss?):/.test(request.url())) outbound.push(request.url()); });
  const page = await context.newPage();
  page.on("pageerror", (error) => errors.push(String(error)));
  page.on("dialog", (dialog) => dialog.accept());
  await page.goto(PAGE);

  await page.locator("#show-proposal").click();
  check("a blank brief proposes nothing and says why", (await text(page, "#proposal-view")).includes("No launch-portfolio family matches"));

  // Words alone are enough to reach a family.
  await page.locator("#show-form").click();
  await page.locator('[data-text="intended_decision"]').fill("Choose a fast-charge protocol for a lithium pouch cell without plating.");
  await page.locator("#show-proposal").click();
  const battery = await text(page, "#proposal-view");
  check("the battery family is proposed with its evidence", battery.includes("Battery fast charging and ageing") && battery.includes("Evidence-backed family"));
  check("every proposed setting is shown with its reason", ["Public training set", "Screening batch size", "Rotation", "Equivalence margin", "What can be promoted", "Physical gates", "Compute cost per submission"].every((label) => battery.includes(label)));
  check("missing conditions are proposed from the tested design", (await page.locator(".condition.proposed_from_tested_design").count()) === 4);
  check("the margin is shown as proposed and not approved", battery.includes("approved: not yet"));
  await page.locator("details.setting").nth(1).locator("summary").click();
  check("opening a setting shows its measured table", (await page.locator("details.setting").nth(1).locator("table").first().textContent()).includes("0.93"));

  // A client range outside the tested range is flagged.
  await page.locator("#show-system").click();
  await page.locator('[data-step="contract"]').click();
  await page.locator('[data-add="inputs"]').click();
  const row = page.locator("#sb-inputs-rows .collection-row").last();
  await row.locator('[data-field="name"]').fill("First-stage charge rate");
  await row.locator('[data-field="unit"]').fill("C-rate");
  await row.locator('[data-field="min"]').fill("0.5");
  await row.locator('[data-field="max"]').fill("3");
  await page.locator("#show-proposal").click();
  check("an out-of-range condition is flagged", (await page.locator(".condition.outside_tested_range").count()) === 1 && (await text(page, "#proposal-view")).includes("Part of your brief is outside the tested range"));

  // The client can choose another family; one without evidence proposes no setting.
  await page.locator("#proposal-family").selectOption("chip-cold-plate");
  const cold = await text(page, "#proposal-view");
  check("a family without evidence proposes no exam setting", cold.includes("No exam-design evidence yet") && (await page.locator("details.setting").count()) === 0);
  check("unmeasured costs are named, never given a figure", cold.includes("Cost items not yet measured"));
  await page.locator("#proposal-family").selectOption("battery-fastcharge-ageing-development-v1");

  // The proposal downloads as the same text the engine produces.
  const pending = page.waitForEvent("download");
  await page.locator("#export-proposal").click();
  const saved = path.join(tmp, "proposal.md");
  await (await pending).saveAs(saved);
  const markdown = fs.readFileSync(saved, "utf8");
  check("the downloaded proposal carries the settings, the evidence source and the flag", markdown.includes("## Proposed exam settings and why") && markdown.includes("docs/development/EXAM_DESIGN_CAMPAIGN_RESULT.md") && markdown.includes("OUTSIDE_TESTED_RANGE"));
  check("the download says it approves nothing", markdown.includes("registers, runs, prices and approves nothing"));

  // The proposal is not part of what the guidance provider could see.
  check("the AI context carries no proposal", !(await text(page, "#context-preview")).includes("Screening batch size"));

  // Keyboard reaches the fourth tab; narrow screens do not scroll sideways.
  await page.locator("#show-guided").focus();
  await page.keyboard.press("End");
  check("the End key reaches Proposed Challenge", (await page.locator("#show-proposal").getAttribute("aria-selected")) === "true");
  await page.setViewportSize({ width: 390, height: 844 });
  check("no horizontal page scroll at phone width", await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1));

  check("no page errors", errors.length === 0);
  check("no request left the page", outbound.length === 0);
  await browser.close();
  console.log(JSON.stringify({ checks: checks.length, failures: 0, outbound_requests: outbound.length, page_errors: errors.length }));
})().catch((error) => { console.error(error); process.exit(1); });
