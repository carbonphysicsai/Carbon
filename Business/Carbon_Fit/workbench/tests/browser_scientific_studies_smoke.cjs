"use strict";
// Local browser interaction against a deterministic HTTP fixture, not science.
const assert = require("node:assert/strict"), fs = require("node:fs"), http = require("node:http"), path = require("node:path");
const { pathToFileURL } = require("node:url"), { chromium } = require("playwright");
const S = require("../src/scientific_studies.js");
const privateHtml = process.argv[2], offlineHtml = process.argv[3];
if (!privateHtml || !offlineHtml) throw Error("Provide separately built private and offline HTML paths");
const physical = { domain_length: 2 * Math.PI, viscosity: 0.1, mean: 0, cosine_coefficients: Array(12).fill(0), sine_coefficients: [1, ...Array(11).fill(0)], requested_times: Array.from({ length: 13 }, (_, i) => i / 12), output_points: 64, units: "dimensionless" };
const cap = { schema: S.CAPABILITIES, template_id: S.TEMPLATE, physical, method: "browser-fixture-method-v1", environment: "browser-fixture-environment-v1", available: true };
const calls = [];
// The real private host authenticates every scientific route with a named staff
// token, so this fixture does too. A journey that never sends the credential
// must fail here rather than quietly pass and hide a broken browser path.
const TOKEN = "browser-fixture-staff-token-00000000";
const unauthenticated = [];
function authenticated(request) {
  return request.headers.authorization === "Bearer " + TOKEN;
}
function response(request, status) { return { schema: S.RESPONSE, operation_id: request.operation_id, task_id: "browser-fixture-task-1", status, binding: request.binding, remaining_budget: { research_trials_remaining: 1, numerical_milliseconds_remaining: null, reference_invocations_remaining: null }, method: cap.method, environment: cap.environment, result: status === "COMPLETE" ? { metadata: { fixture_only: true, note: "<script>globalThis.injected=true</script>", qualification: "Data only; NOT_QUALIFIED" }, values: Array.from({ length: 13 }, (_, t) => Array.from({ length: 64 }, (_, x) => Math.sin(x / 10) / (t + 1))) } : null, official_eligible: false, qualification: "NOT_QUALIFIED" }; }
const server = http.createServer(async (request, reply) => {
  if (request.url === "/") { reply.setHeader("Content-Type", "text/html; charset=utf-8"); reply.end(fs.readFileSync(privateHtml)); return; }
  if (request.url.startsWith("/api/scientific-studies/") && !authenticated(request)) {
    unauthenticated.push(request.url);
    reply.writeHead(401, { "Content-Type": "application/json" }).end(JSON.stringify({ error: "AUTHENTICATION_REQUIRED" }));
    return;
  }
  if (request.url === "/api/scientific-studies/capabilities") { reply.setHeader("Content-Type", "application/json"); reply.end(JSON.stringify(cap)); return; }
  if (request.method !== "POST" || !/^\/api\/scientific-studies\/(start|status|cancel|result)$/.test(request.url)) { reply.writeHead(404).end(); return; }
  let raw = ""; for await (const chunk of request) raw += chunk;
  const value = JSON.parse(raw); calls.push({ path: request.url, value });
  reply.setHeader("Content-Type", "application/json"); reply.end(JSON.stringify(response(value, request.url.endsWith("cancel") ? "CANCEL_REQUESTED" : "COMPLETE")));
});
async function openDraft(page, url) {
  page.on("dialog", (dialog) => dialog.accept("Public scientific study fixture"));
  await page.goto(url); await page.locator('[data-tab="jobs"]').click(); await page.locator("#new-job").click(); await page.locator("#burgers-demo").click(); await page.locator("#scientific-study-panel").waitFor();
}
(async () => {
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const browser = await chromium.launch({ headless: true, ...(process.env.CARBON_BROWSER_EXECUTABLE ? { executablePath: process.env.CARBON_BROWSER_EXECUTABLE } : {}) });
  const errors = [], checks = [];
  try {
    for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
      const page = await browser.newPage({ viewport, acceptDownloads: true }); page.on("pageerror", (error) => errors.push(error.message)); page.setDefaultTimeout(15000);
      await openDraft(page, "http://127.0.0.1:" + server.address().port + "/");
      await page.locator("#science-check").click(); assert.match(await page.locator("#science-check-result").textContent(), /INPUTS_UNRESOLVED/);
      // Connecting with no credential must state the next usable action and
      // leave the browser silent, not surface a bare transport failure.
      const quiet = unauthenticated.length; await page.locator("#science-connect").click();
      await page.waitForFunction(() => /staff access token/i.test(document.body.textContent));
      assert.equal(unauthenticated.length, quiet, "no request may leave the browser without a credential");
      assert.equal(await page.locator("#science-adopt").isDisabled(), true);
      // Enter the operator-issued token, exactly as a staff member would.
      await page.locator("#science-token").fill(TOKEN);
      const before = calls.length; await page.locator("#science-connect").click();
      await page.locator("#science-credential-state").waitFor();
      await page.locator("#science-adopt:not([disabled])").waitFor();
      await page.locator("#science-adopt").click(); await page.locator("#science-run:not([disabled])").waitFor(); assert.equal(calls.length, before);
      // The credential is held in memory only: it is in no input value, no
      // storage and no part of the rendered document.
      assert.equal(await page.locator("#science-token").count(), 0);
      assert.equal(await page.evaluate((t) => document.documentElement.outerHTML.includes(t), TOKEN), false);
      assert.deepEqual(await page.evaluate(() => [Object.keys(localStorage).length, Object.keys(sessionStorage).length]), [0, 0]);
      await page.locator("#science-run").click(); await page.locator("#science-plot svg").waitFor();
      assert.match(await page.locator("#science-state").textContent(), /CURRENT.*PRIVATE_SERVICE_RESPONSE.*COMPLETE/);
      assert.match(await page.locator("#science-budget").textContent(), /unknown/);
      assert.equal(await page.locator("#science-metadata script").count(), 0);
      const saved = page.waitForEvent("download"); await page.locator("#science-save").click(); const download = await saved; const file = await download.path();
      await page.locator("#science-file").setInputFiles(file); await page.waitForFunction(() => document.querySelector("#science-state").textContent.includes("SAVED_UNVERIFIED"));
      await page.locator("#science-status").click(); await page.waitForFunction(() => document.querySelector("#science-state").textContent.includes("PRIVATE_SERVICE_RESPONSE"));
      const requests = calls.length; await page.locator('[data-scope="commercial_context"]').fill("Editorial note"); assert.equal(calls.length, requests);
      await page.locator("#science-run:not([disabled])").waitFor();
      await page.locator('[data-scope="conditions"]').fill("Changed physical condition"); await page.waitForFunction(() => document.querySelector("#science-state").textContent.includes("STALE"));
      assert(await page.locator("#science-run").isDisabled());
      await page.locator("#science-cancel").click(); await page.waitForFunction(() => document.querySelector("#science-state").textContent.includes("CANCEL_REQUESTED"));
      const width = await page.locator("#scientific-study-panel").boundingBox(); assert(width.width <= viewport.width); assert.equal(await page.locator("#science-plot svg").count(), 0);
      checks.push({ viewport, study: "fixture complete, saved, reopened, stale, cancel requested" }); await page.close();
    }
    const page = await browser.newPage(); const network = []; page.on("request", (request) => { if (/^https?:/.test(request.url())) network.push(request.url()); });
    await openDraft(page, pathToFileURL(path.resolve(offlineHtml)).href);
    assert(await page.locator("#science-connect").isDisabled()); assert(await page.locator("#science-run").isDisabled()); assert.deepEqual(network, []);
    checks.push({ offline: "no network; service controls unavailable" }); await page.close();
    assert.deepEqual(errors, []);
    assert.deepEqual(unauthenticated, [], "every fixture request carried the staff credential");
    process.stdout.write(JSON.stringify({ fixture_only: true, checks, page_errors: errors, requests: calls.length, authenticated_requests: calls.length }) + "\n");
  } finally { await browser.close(); await new Promise((resolve) => server.close(resolve)); }
})().catch((error) => { server.close(); console.error(error); process.exitCode = 1; });
