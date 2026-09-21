"use strict";
// Operator-run local integration helper. The host owns grants/draft registration.
// This script contains no authentication, grant creation or scientific evaluator.
const assert = require("node:assert/strict"), fs = require("node:fs"), path = require("node:path");
const { pathToFileURL } = require("node:url"), { chromium } = require("playwright");
const S = require("../src/scientific_studies.js");
const [mode, target, workspaceFile, outputFile] = process.argv.slice(2);
const envelope = process.env.CARBON_ENVELOPE === "1";
if (!["prepare", "run"].includes(mode) || !target || !workspaceFile || !outputFile) throw Error("Use prepare OFFLINE_HTML WORKSPACE_JSON REGISTRATION_JSON or run PRIVATE_URL WORKSPACE_JSON STUDY_JSON");
if (mode === "run") { const url = new URL(target); assert(["127.0.0.1", "localhost", "[::1]"].includes(url.hostname) && url.protocol === "http:", "Only explicitly local HTTP integration hosts are supported"); }
async function save(page, button, destination) { const pending = page.waitForEvent("download"); await page.locator(button).click(); await (await pending).saveAs(destination); }
(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.CARBON_BROWSER_EXECUTABLE ? { executablePath: process.env.CARBON_BROWSER_EXECUTABLE } : {}) });
  const errors = [];
  try {
    const page = await browser.newPage({ viewport: process.env.CARBON_MOBILE === "1" ? { width: 390, height: 844 } : { width: 1440, height: 1000 }, acceptDownloads: true }); page.setDefaultTimeout(30000); page.on("pageerror", (error) => errors.push(error.message)); page.on("dialog", (dialog) => dialog.accept());
    await page.goto(mode === "prepare" ? pathToFileURL(path.resolve(target)).href : target);
    await page.locator('[data-tab="jobs"]').click();
    if (mode === "prepare") {
      await page.locator("#new-job").click(); await page.locator("#burgers-demo").click();
      await save(page, "#export-goal", workspaceFile);
      const w = JSON.parse(fs.readFileSync(workspaceFile)), d = w.jobs[0].designs[0];
      fs.writeFileSync(outputFile, JSON.stringify({ job_id: d.job_id, design_id: d.design_id, revision: d.revision, current_revision: d.revision, scope: S.scope(d), fixture_scope: "PUBLIC_SOURCE_TEMPLATE_BROWSER_INTEGRATION" }, null, 2) + "\n");
      console.log(JSON.stringify({ prepared_only: true, job_id: d.job_id, design_id: d.design_id, registration_file: outputFile }));
    } else {
      await page.locator("#goal-workspace-file").setInputFiles(workspaceFile);
      await page.locator("#scientific-study-panel").waitFor({ state: "attached" });
      await page.locator('[data-tab="jobs"]').click();
      // The loopback host authenticates like the supported host, so the
      // operator's fixture token must be entered before connecting.
      const token = process.env.CARBON_FIXTURE_STAFF_TOKEN;
      if (!token) throw Error("Set CARBON_FIXTURE_STAFF_TOKEN from the native host's startup record");
      await page.locator("#science-token").fill(token);
      await page.locator("#science-connect").click(); await page.locator("#science-credential-state").waitFor(); await page.locator("#science-adopt:not([disabled])").waitFor(); await page.locator("#science-adopt").click(); await page.locator("#science-run:not([disabled])").waitFor(); await page.locator(envelope ? "#science-envelope" : "#science-run").click();
      for (let poll = 0; poll < 30; poll++) {
        await page.locator("#science-status:not([disabled])").waitFor();
        const state = await page.locator("#science-state").textContent();
        if (state.includes("NOT_EXECUTED")) throw Error("Start did not return an admitted operation: " + await page.locator("#toast").textContent());
        if (state.includes("COMPLETE")) break;
        if (/FAILED|CANCELLED|REQUIRES_RECONCILIATION/.test(state)) throw Error(state);
        await page.waitForTimeout(500); await page.locator("#science-status").click();
      }
      await page.locator("#science-result:not([disabled])").waitFor(); await page.locator("#science-result").click(); await page.locator("#science-plot svg").first().waitFor();
      await save(page, "#science-save", outputFile);
      const bundle = JSON.parse(fs.readFileSync(outputFile)), result = bundle.response;
      assert.equal(result.status, "COMPLETE"); assert.equal(result.official_eligible, false); assert.equal(result.qualification, "NOT_QUALIFIED"); const numerical = envelope ? result.result.children.map((c) => c.result) : [result.result]; assert.equal(numerical.length, envelope ? 2 : 1); for (const n of numerical) { assert.equal(n.values.length, 13); assert(n.values.every((row) => row.length === 64 && row.every(Number.isFinite))); }
      assert.equal(result.result.metadata.training_support_eligible, false); assert.notEqual(result.result.metadata.fixture_only, true);
      await page.locator("#science-file").setInputFiles(outputFile); await page.waitForFunction(() => document.querySelector("#science-state").textContent.includes("SAVED_UNVERIFIED"));
      await page.locator("#science-status").click(); await page.waitForFunction(() => document.querySelector("#science-state").textContent.includes("PRIVATE_SERVICE_RESPONSE"));
      assert.deepEqual(errors, []);
      console.log(JSON.stringify({ native_service_response_observed: true, production_authentication: false, scientific_qualification: false, operation_id: result.operation_id, task_id: result.task_id, method: result.method, environment: result.environment, shape: envelope ? [2, 13, 64] : [13, 64], saved_and_reopened: true, metadata: result.result.metadata, page_errors: errors }));
    }
  } finally { await browser.close(); }
})().catch((error) => { console.error(error); process.exitCode = 1; });
