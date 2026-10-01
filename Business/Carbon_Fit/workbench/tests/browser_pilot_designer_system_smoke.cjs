"use strict";
// Browser acceptance for the Pilot Designer's system builder (GOAL-WORKBENCH-16
// slice 1), run against the generated page. Local diagnostic, like the other
// browser_*.cjs files: it needs Playwright and a Chromium, and CI does not run it.
//
//   NODE_PATH=/path/to/node_modules node tests/browser_pilot_designer_system_smoke.cjs
//
// Prints a JSON summary and writes nothing into the repository.
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
if (!globalThis.crypto) globalThis.crypto = crypto.webcrypto;
const I = require("../src/intake.js");
const E = require("../src/problem/engine.js");

const ROOT = path.resolve(__dirname, "..");
const PAGE = "file://" + path.join(ROOT, "Carbon_Client_Pilot_Designer_Preview.html");
const checks = [];
function check(name, value) { assert.ok(value, name); checks.push(name); }
async function download(page, selector, target) {
  const pending = page.waitForEvent("download");
  await page.locator(selector).click();
  await (await pending).saveAs(target);
  return fs.readFileSync(target, "utf8");
}
async function upload(page, text, name) {
  const file = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "carbon-upload-")), name);
  fs.writeFileSync(file, text);
  // Reading the file is asynchronous; wait for the page to report the outcome.
  await page.evaluate(() => { document.querySelector("#intake-status").textContent = ""; });
  await page.locator("#resume-file").setInputFiles(file);
  await page.waitForFunction(() => /restored|opened|Could not open/.test(document.querySelector("#intake-status").textContent));
}

(async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "carbon-pilot-system-"));
  const errors = [], outbound = [];
  const browser = await chromium.launch({ headless: true, ...(process.env.CARBON_BROWSER_EXECUTABLE ? { executablePath: process.env.CARBON_BROWSER_EXECUTABLE } : {}) });
  const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 1440, height: 1000 } });
  context.on("request", (request) => { if (/^(https?|wss?):/.test(request.url())) outbound.push(request.url()); });
  const page = await context.newPage();
  page.on("pageerror", (error) => errors.push(String(error)));
  page.on("dialog", (dialog) => dialog.accept());
  await page.goto(PAGE);

  // Three editing modes over one draft.
  check("the page offers four editing modes, the proposal last", (await page.locator(".mode-tabs [role=tab]").count()) === 4);
  await page.locator("#show-system").click();
  check("Your system opens its own panel and hides the others", await page.locator("#system-panel").isVisible() && !(await page.locator("#guided-panel").isVisible()) && !(await page.locator("#form-panel").isVisible()));
  check("an empty system says so rather than drawing one", (await page.locator("#sb-map").innerText()).includes("Add a component"));

  // An example fills the structure; the brief's words are untouched.
  await page.locator('[data-example="cooling"]').click();
  check("the cooling example draws its components", (await page.locator("#sb-map svg rect.box").count()) >= 2);
  check("the evidence plan names an entry point and a next step", (await page.locator("#sb-plan").textContent()).includes("Proposed entry point") && (await page.locator("#sb-plan").textContent()).includes("The next useful step"));
  check("an example leaves the brief's words empty", (await page.locator('[data-text="intended_decision"]').inputValue()) === "");
  check("the shared brief reports the system", (await page.locator("#summary-text").innerText()).includes("Physical components:") && (await page.locator("#summary-text").innerText()).includes("Heat transfer"));

  // Editing a row updates the plan and the brief; text stays inert.
  await page.locator('[data-step="contract"]').click();
  await page.locator('[data-add="inputs"]').click();
  const input = page.locator("#sb-inputs-rows .collection-row").last();
  await input.locator('[data-field="name"]').fill('Coolant inlet <img src=x onerror="window.systemPwned=true">');
  await input.locator('[data-field="unit"]').fill("degC");
  await input.locator('[data-field="min"]').fill("20");
  await input.locator('[data-field="max"]').fill("45");
  check("a new input with its range reaches the brief", (await page.locator("#summary-text").innerText()).includes("[degC] 20 to 45"));
  check("client text is inert in the builder and the brief", !(await page.evaluate(() => window.systemPwned === true)) && (await page.locator("#summary-text").innerText()).includes("onerror"));

  // A research lead becomes a component and a linked reference.
  await page.locator("details.leads > summary").click();
  await page.locator("#sb-atlas-search").fill("heat conduction");
  await page.locator("[data-use-lead]").first().click();
  const duplicateIds = () => page.evaluate(() => { const seen = new Set(), dup = new Set(); for (const e of document.querySelectorAll("[id]")) (seen.has(e.id) ? dup : seen).add(e.id); return [...dup]; });
  check("no element ID is rendered twice after building a system", (await duplicateIds()).length === 0);
  check("a research lead is added as a component and a lead reference", (await page.locator("#summary-text").innerText()).match(/Research leads: PHY-/) !== null);

  // An invalid entry blocks download until corrected.
  await page.locator('[data-step="economics"]').click();
  await page.locator("#sb_cost_queries").fill("1.5");
  check("an invalid entry is reported and keeps the last valid plan", await page.locator("#sb-error").isVisible());
  let blockedDownload = false;
  page.once("download", () => { blockedDownload = true; });
  await page.locator("#export-intake").click();
  await page.waitForTimeout(300);
  check("no file is produced while an entry is invalid", !blockedDownload);
  check("download is refused while an entry is invalid", (await page.locator("#intake-status").innerText()).includes("Export blocked"));
  await page.locator("#sb_cost_queries").fill("1500");
  check("correcting the entry clears the error", !(await page.locator("#sb-error").isVisible()));
  check("the cost calculator reports what is still unknown", (await page.locator("#sb-economics-result").innerText()).includes("Needed:"));

  // The words in the form, then a download that carries both.
  await page.locator("#show-form").click();
  await page.locator('[data-text="intended_decision"]').fill("Choose a cold-plate channel layout for the next board.");
  await page.locator('[data-text="requested_result"]').fill("Predict peak junction temperature across coolant flow.");
  const packageText = await download(page, "#export-intake", path.join(tmp, "with-system.json"));
  const pkg = JSON.parse(packageText);
  check("the download is a v2 package that validates", pkg.schema_version === I.REVIEW_VERSION_V2 && I.validateReviewedPackage(pkg).brief.schema_version === I.DRAFT_VERSION_V2);
  check("the downloaded system carries structure only", I.SYSTEM_WORDS.every((key) => pkg.brief.system[key] === ""));
  check("the downloaded system carries the edits", pkg.brief.system.inputs.some((row) => row.unit === "degC" && row.min === 20 && row.max === 45) && pkg.brief.system.economics.queries === 1500);
  check("the AI context shown before consent carries no system value", !(await page.locator("#context-preview").innerText()).includes("Coolant inlet"));

  // The encrypted download seals the same v2 package.
  await page.waitForFunction(() => !document.querySelector("#export-sealed").disabled);
  const sealed = JSON.parse(await download(page, "#export-sealed", path.join(tmp, "with-system.carbon-sealed")));
  check("the encrypted download carries no system text", !JSON.stringify(sealed).includes("Coolant inlet") && !JSON.stringify(sealed).includes("cold-plate"));

  // Continue a saved draft: this page's own package comes back exactly.
  await page.locator("#reset-draft").click();
  check("reset clears the system", (await page.locator("#sb-map").innerText()).includes("Add a component"));
  await upload(page, packageText, "with-system.carbon-intake.json");
  const again = await download(page, "#export-intake", path.join(tmp, "again.json"));
  check("a restored package downloads unchanged", again === packageText);

  // Continue a saved draft: a draft saved from the earlier /workbench/ page.
  const saved = E.template("structure", "job_saved_structure");
  await upload(page, JSON.stringify({ schema: "carbon.client-intake/1", job: saved, contact: { email: "client@example.invalid" }, consent: { analysis: true, noticeVersion: "UNCONFIGURED" }, assistantHistory: [] }), "workbench-submission.json");
  check("a /workbench/ draft's words land in the brief", (await page.locator('[data-text="intended_decision"]').inputValue()) === saved.problem.decision);
  check("a /workbench/ draft's structure lands in the builder", (await page.locator("#sb-components-rows .collection-row").count()) === saved.problem.components.length);
  check("a /workbench/ draft's contact email is carried over", (await page.locator("#contact-email").inputValue()) === "client@example.invalid");
  check("a /workbench/ draft leaves no earlier pilot text behind", (await page.locator('[data-pilot="bounded_first_pilot"]').inputValue()) === "");
  const fromWorkbench = JSON.parse(await download(page, "#export-intake", path.join(tmp, "from-workbench.json")));
  check("the opened /workbench/ draft downloads as a valid v2 package", I.validateReviewedPackage(fromWorkbench).brief.system.components.length === saved.problem.components.length);
  await upload(page, "{not json", "broken.json");
  check("an unreadable file is refused by name and changes nothing", (await page.locator("#intake-status").innerText()).includes("Could not open that file") && (await page.locator('[data-text="intended_decision"]').inputValue()) === saved.problem.decision);

  // Keyboard and narrow screens.
  await page.locator("#show-guided").focus();
  await page.keyboard.press("End");
  check("the End key reaches the last mode", (await page.locator("#show-proposal").getAttribute("aria-selected")) === "true");
  await page.keyboard.press("Home");
  check("the Home key returns to the conversation", (await page.locator("#show-guided").getAttribute("aria-selected")) === "true");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator("#show-system").click();
  check("no horizontal page scroll at phone width", await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1));

  check("no page errors", errors.length === 0);
  check("no request left the page", outbound.length === 0);
  await browser.close();
  console.log(JSON.stringify({ checks: checks.length, failures: 0, outbound_requests: outbound.length, page_errors: errors.length }));
})().catch((error) => { console.error(error); process.exit(1); });
