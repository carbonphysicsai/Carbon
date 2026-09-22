"use strict";
// GOAL-WORKBENCH-14 browser journeys for the public onboarding edition.
//
// Run against the generated artifact, never a rebuilt one: the file a visitor
// would open is the thing under test. The internal Workbench page is opened
// only to prove the exported draft reaches it.
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const ROOT = path.resolve(__dirname, "..");
const PUBLIC = path.join(ROOT, "Carbon_Public_Workbench_Onboarding.html");
const checks = [];
const check = (name, value) => {
  assert.ok(value, name);
  checks.push(name);
};

(async () => {
  assert.ok(fs.existsSync(PUBLIC), "the public artifact must be generated before this runs");
  const before = crypto.createHash("sha256").update(fs.readFileSync(PUBLIC)).digest("hex");
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "carbon-public-browser-"));
  const errors = [], outbound = [], blocked = [];
  const narrow = process.env.CARBON_MOBILE === "1";
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.CARBON_BROWSER_EXECUTABLE
      ? { executablePath: process.env.CARBON_BROWSER_EXECUTABLE }
      : {}),
  });
  const context = await browser.newContext({
    acceptDownloads: true,
    viewport: narrow ? { width: 390, height: 844 } : { width: 1440, height: 1000 },
  });
  // Any request that leaves the page, and separately anything the CSP refuses
  // to let become a request at all.
  context.on("request", (request) => {
    if (/^(https?|wss?):/.test(request.url())) outbound.push(request.url());
  });

  const page = await context.newPage();
  page.on("pageerror", (error) => errors.push(String(error)));
  page.on("console", (message) => {
    if (/Content Security Policy|Refused to/i.test(message.text())) blocked.push(message.text());
  });
  await page.goto("file://" + PUBLIC);

  // --- a cold visitor -------------------------------------------------------
  check("only the first stage is open to a cold visitor",
    (await page.locator("fieldset.stage:visible").count()) === 1);
  check("the first stage is the one about the answer they need",
    (await page.locator("fieldset.stage:visible legend").first().innerText()).includes("predict"));
  check("the check has already run and says what is undefined",
    (await page.locator("#yours-list li").count()) > 0);
  check("nothing claims qualification",
    (await page.locator("#check-limitations").innerText()).includes("Structural"));

  // --- concrete issues, in the visitor's language ---------------------------
  const firstIssues = await page.locator("#yours-list").innerText();
  check("an undefined problem names its own gaps, not a score",
    /Missing conditions\.|Missing inputs\./.test(firstIssues));
  check("each issue carries a plain-language note",
    (await page.locator("#yours-list li .plain").count()) ===
      (await page.locator("#yours-list li .issue").count()));
  check("what only Carbon can close is listed separately",
    (await page.locator("#carbon-list").innerText()).includes("source study"));

  // --- progressive disclosure ----------------------------------------------
  await page.locator('[data-field="requested_goal"]').fill("Dynamics");
  check("answering the first stage opens the next",
    (await page.locator("fieldset.stage:visible").count()) === 2);
  await page.locator("#open-all").click();
  check("an expert can open every question at once",
    (await page.locator("fieldset.stage:visible").count()) === 5);

  // --- the issues clear as the draft is filled -----------------------------
  const answers = {
    physics_family: "periodic_viscous_burgers_1d_v1",
    intended_use: "Decide whether to scope a pilot",
    inputs: "Twelve Fourier coefficients, viscosity and requested times",
    outputs: "Velocity at 64 points for each requested time",
    units: "dimensionless",
    geometry: "Periodic line of unit length",
    conditions: "Periodic and unforced",
    regime: "Smooth through steepening",
    exclusions: "No shock capture",
    query_workload: "A few hundred per iteration",
    turnaround: "Same working day",
    failure_consequences: "A wasted design iteration",
    data_access: "Synthetic cases only",
    rights_scope: "SYNTHETIC_INTERNAL",
    commercial_context: "Evaluating a pilot",
    disclosure_scope: "Internal use only",
    deployment_environment: "An engineer's laptop",
    "reference_plan.equation": "Viscous Burgers equation",
    "reference_plan.method": "Spectral reference solver",
  };
  const remaining = [];
  for (const [field, value] of Object.entries(answers)) {
    await page.locator('[data-field="' + field + '"]').fill(value);
    remaining.push(await page.locator("#yours-list li:not(.clear)").count());
  }
  check("the count of open issues never rises as fields are filled",
    remaining.every((count, index) => index === 0 || count <= remaining[index - 1]));
  check("the visitor can close every issue that is theirs",
    (await page.locator("#yours-list li.clear").count()) === 1);
  // And the one that is not theirs is still shown, not quietly dropped.
  check("what remains is attributed to Carbon rather than hidden",
    (await page.locator("#carbon-list li:not(.clear)").count()) === 1);
  check("the status says what the check said, not that the draft passed",
    (await page.locator("#check-status").innerText()).includes("closed"));

  // --- export ---------------------------------------------------------------
  const pending = page.waitForEvent("download");
  await page.locator("#export-draft").click();
  const download = await pending;
  const saved = path.join(tmp, "public-draft.json");
  await download.saveAs(saved);
  const artifact = JSON.parse(fs.readFileSync(saved, "utf8"));
  check("the download is the public workspace artifact",
    artifact.schema_version === "carbon.public-workbench.workspace.v1");
  check("it carries its own digest", /^sha256:[a-f0-9]{64}$/.test(artifact.digest));
  check("it claims no authority",
    artifact.authority.effect === "NONE" && artifact.authority.qualification === "NOT_QUALIFIED");
  check("it carries the check result the page displayed",
    artifact.structural_check.issues.length === 1);
  check("the export status says nothing was sent",
    (await page.locator("#export-status").innerText()).includes("Nothing was sent"));

  // --- the artifact reaches the internal Workbench --------------------------
  // Exercised in the browser through the same modules the internal bundle
  // ships, against the file the visitor actually downloaded.
  const roundTrip = await page.evaluate(async (downloaded) => {
    const P = globalThis.CarbonPublicWorkbench;
    const S = globalThis.CarbonScientificStudies;
    const checked = S.check(P.checkable(downloaded));
    await P.validateArtifact(downloaded, S);
    return { status: checked.status, issues: checked.issues };
  }, artifact);
  check("the downloaded file validates and re-checks identically in the page",
    roundTrip.status === artifact.structural_check.status &&
      JSON.stringify(roundTrip.issues) === JSON.stringify(artifact.structural_check.issues));

  // --- and into the internal Workbench, in a browser ----------------------
  // The Node suite proves the import path accepts the artifact. This proves it
  // in the internal bundle as shipped, from the file the visitor downloaded,
  // which is the journey a Carbon engineer would actually perform.
  const internalPage = await context.newPage();
  internalPage.on("pageerror", (error) => errors.push("internal: " + String(error)));
  await internalPage.goto("file://" + path.join(ROOT, "Carbon_Opportunity_Workbench.html"));
  const imported = await internalPage.evaluate((downloaded) => {
    const W = globalThis.CarbonGoalWorkflow;
    const S = globalThis.CarbonScientificStudies;
    const P = globalThis.CarbonPublicWorkbench;
    const { job, design } = W.importPublicScoping(downloaded);
    W.validateJob(job);
    W.validateDesign(design, job.job_id);
    const recomputed = S.check(P.checkable(design));
    return {
      design_id: design.design_id,
      revision: design.revision,
      status: recomputed.status,
      issues: recomputed.issues,
      qualification: design.decision.scientific_qualification,
      launch: design.decision.launch_authorization,
      scope: design.scope,
    };
  }, artifact);
  check("the internal bundle imports the downloaded artifact",
    imported.design_id === artifact.design_id && imported.revision === artifact.revision);
  check("the internal side recomputes the same structural check",
    imported.status === artifact.structural_check.status &&
      JSON.stringify(imported.issues) === JSON.stringify(artifact.structural_check.issues));
  check("no scope field needed retyping",
    Object.keys(artifact.scope).every((field) => imported.scope[field] === artifact.scope[field]));
  check("importing a client draft promotes nothing",
    imported.qualification === "NOT_QUALIFIED" && imported.launch === "NOT_AUTHORIZED");

  // --- the guarantees that hold the whole thing up -------------------------
  check("nothing left the page", outbound.length === 0);
  check("no script error occurred", errors.length === 0);
  check("reset clears the draft without storing anything",
    await (async () => {
      await page.locator("#reset-draft").click();
      const count = await page.locator("fieldset.stage:visible").count();
      const status = await page.locator("#export-status").innerText();
      return count === 1 && status.includes("Nothing was stored");
    })());
  check("no browser storage is used",
    await page.evaluate(() => {
      try {
        return localStorage.length === 0 && sessionStorage.length === 0;
      } catch (error) {
        return true;
      }
    }));

  // --- the same file with scripting disabled --------------------------------
  // A public page that promises questions and then shows none is worse than
  // one that says why. The check runs in the visitor's browser, which is the
  // reason nothing is sent anywhere, so it is also the reason the page needs
  // scripting at all — and that is what the fallback says.
  const quiet = await browser.newContext({
    javaScriptEnabled: false,
    viewport: narrow ? { width: 390, height: 844 } : { width: 1440, height: 1000 },
  });
  quiet.on("request", (request) => {
    if (/^(https?|wss?):/.test(request.url())) outbound.push(request.url());
  });
  const withoutScript = await quiet.newPage();
  await withoutScript.goto("file://" + PUBLIC);
  const fallback = await withoutScript.locator("body").innerText();
  check("without scripting the page says why the questions are missing",
    /need JavaScript/.test(fallback));
  check("it still states that nothing is sent",
    /makes no network request/.test(fallback));
  check("it lists what it would have asked",
    (await withoutScript.locator(".stage-outline li").count()) === 5);
  check("no control is offered that cannot work",
    (await withoutScript.locator("button:not([disabled])").count()) === 0);
  check("and nothing left the page without scripting either", outbound.length === 0);
  await quiet.close();

  const after = crypto.createHash("sha256").update(fs.readFileSync(PUBLIC)).digest("hex");
  check("the artifact under test was not rebuilt by this run", before === after);

  await browser.close();
  fs.rmSync(tmp, { recursive: true, force: true });
  process.stdout.write(
    (narrow ? "narrow" : "desktop") +
      " public onboarding journeys passed: " +
      checks.length +
      " checks\n" +
      (blocked.length ? "CSP refusals observed: " + blocked.length + "\n" : ""),
  );
})().catch((error) => {
  process.stderr.write("public onboarding browser journeys failed: " + error.message + "\n");
  process.exit(1);
});
