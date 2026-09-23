"use strict";
// One continuous team journey against the supported launcher. Operator-run; see
// tests/service/workbench_team_journey.py, which starts the launcher and the
// stage-1 receiver and performs the two operator steps a browser cannot:
// relaying the client's package into the receiver, and registering the draft.
// This script contains no authentication scheme, registration or evaluator.
const assert = require("node:assert/strict"), fs = require("node:fs"), path = require("node:path");
const { chromium } = require("playwright");
const S = require("../src/scientific_studies.js");

const [origin, directory] = process.argv.slice(2);
if (!origin || !directory) throw Error("Use ORIGIN WORK_DIRECTORY");
const url = new URL(origin);
assert(url.protocol === "http:" && url.hostname === "127.0.0.1", "loopback launcher only");
const token = process.env.CARBON_FIXTURE_STAFF_TOKEN;
if (!token) throw Error("Set CARBON_FIXTURE_STAFF_TOKEN from the launcher's staff file");
const mobile = process.env.CARBON_MOBILE === "1";
const checks = [];
const check = (name, condition) => { assert.ok(condition, name); checks.push(name); };
const file = (name) => path.join(directory, name);

async function save(page, selector, target) {
  const pending = page.waitForEvent("download");
  await page.locator(selector).click();
  await (await pending).saveAs(target);
  return JSON.parse(fs.readFileSync(target, "utf8"));
}

// Hand one step to the operator driver and wait for its answer file.
async function operator(step, request) {
  fs.writeFileSync(file(`need-${step}.json`), JSON.stringify(request));
  for (let waited = 0; waited < 600; waited++) {
    if (fs.existsSync(file(`done-${step}.json`))) return JSON.parse(fs.readFileSync(file(`done-${step}.json`), "utf8"));
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw Error(`operator step ${step} never completed`);
}

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.CARBON_BROWSER_EXECUTABLE ? { executablePath: process.env.CARBON_BROWSER_EXECUTABLE } : {}) });
  const offOrigin = [], errors = [];
  try {
    const context = await browser.newContext({ viewport: mobile ? { width: 390, height: 844 } : { width: 1440, height: 1000 }, acceptDownloads: true });
    context.on("request", (request) => { if (!request.url().startsWith(origin + "/") && /^(https?|wss?):/.test(request.url())) offOrigin.push(request.url()); });
    const page = await context.newPage();
    page.setDefaultTimeout(30000);
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("dialog", (dialog) => dialog.accept());

    // 1. The client states the problem on the preview this host serves.
    await page.goto(origin + "/Carbon_Client_Pilot_Designer_Preview.html");
    await page.locator("#show-form").click();
    await page.locator('[data-text="intended_decision"]').fill("Decide whether a faster Burgers surrogate is worth a pilot.");
    await page.locator('[data-text="requested_result"]').fill("Compare turnaround and field evolution on public cases.");
    await page.locator('[data-text="current_baseline"]').fill("Existing periodic Burgers solver");
    await page.locator('[data-text="baseline_limitation"]').fill("Turnaround is inconvenient; accuracy is unknown.");
    const inquiry = await save(page, "#export-intake", file("inquiry.json"));
    check("the client package is the reviewed intake schema", inquiry.schema_version === "carbon.client-intake.reviewed.v1");

    // 2. Operator: relay the exact bytes into the receiver and read them back.
    const relayed = await operator("relay", { package: file("inquiry.json") });
    check("the receiver stored the exact bytes the client downloaded", relayed.raw_sha256 === relayed.downloaded_sha256);

    // 3. The team imports the stored inquiry, assesses it and adopts the source.
    await page.goto(origin + "/");
    await page.locator('[data-tab="jobs"]').click();
    await page.locator("#intake-draft-file").setInputFiles(relayed.stored_package);
    await page.waitForFunction(() => document.querySelector("#toast").textContent.includes("preview prepared"));
    await page.locator("#commit-intake-draft").click();
    check("the stored inquiry becomes one job", (await page.locator("[data-job-select]").count()) === 1);
    await page.locator("#team-reviewer").fill("Journey reviewer");
    await page.locator("#team-queue-state").selectOption("UNDER_REVIEW");
    await page.locator("#team-current-action").fill("Run the public Burgers reference study before scoping.");
    await page.locator("#save-team-review").click();
    check("the assessment is recorded on the job", (await page.locator("#team-review-panel").innerText()).includes("UNDER_REVIEW"));
    await page.locator("#burgers-demo").click();
    const drafted = await save(page, "#export-goal", file("workspace-drafted.json"));
    const job = drafted.jobs[0], design = job.designs[job.designs.length - 1];

    // 4. Operator: register exactly this design revision. A browser cannot.
    await operator("register", { job_id: design.job_id, design_id: design.design_id, revision: design.revision, draft_scope: S.scope(design) });

    // 5. The study, on the same job, through the launcher's scientific routes.
    await page.locator("#science-token").fill(token);
    await page.locator("#science-connect").click();
    await page.locator("#science-credential-state").waitFor();
    await page.locator("#science-adopt:not([disabled])").waitFor();
    await page.locator("#science-adopt").click();
    await page.locator("#science-run:not([disabled])").waitFor();
    await page.locator("#science-run").click();
    for (let poll = 0; poll < 60; poll++) {
      await page.locator("#science-status:not([disabled])").waitFor();
      const state = await page.locator("#science-state").textContent();
      if (state.includes("NOT_EXECUTED")) throw Error("Start was not admitted: " + await page.locator("#toast").textContent());
      if (state.includes("COMPLETE")) break;
      if (/FAILED|CANCELLED|REQUIRES_RECONCILIATION/.test(state)) throw Error(state);
      await page.waitForTimeout(500);
      await page.locator("#science-status").click();
    }
    await page.locator("#science-result:not([disabled])").waitFor();
    await page.locator("#science-result").click();
    await page.locator("#science-plot svg").first().waitFor();
    const study = await save(page, "#science-save", file("study.json"));
    check("the study completed on a real worker and qualifies nothing", study.response.status === "COMPLETE" && study.response.qualification === "NOT_QUALIFIED" && study.response.result.metadata.fixture_only !== true);
    check("the study is bound to the inquiry's design", study.request.binding.job_id === design.job_id && study.request.binding.design_id === design.design_id);
    const saved = await save(page, "#export-goal", file("workspace-saved.json"));

    // 6. Reopen from the saved bytes in a fresh page and find all three again.
    await page.reload();
    await page.locator("#goal-workspace-file").setInputFiles(file("workspace-saved.json"));
    await page.locator('[data-tab="jobs"]').click();
    const reopened = await save(page, "#export-goal", file("workspace-reopened.json"));
    check("the reopened workspace holds the same job and design", reopened.jobs.length === 1 && reopened.jobs[0].job_id === saved.jobs[0].job_id && reopened.jobs[0].designs.at(-1).design_id === design.design_id);
    check("the inquiry's own words survive the reopen", (await page.locator('[data-assignment="client_words"]').inputValue()) === saved.jobs[0].assignment.client_words && saved.jobs[0].assignment.client_words.length > 0);
    // Read the fields' values: innerText does not include what an input holds.
    check("the assessment survives the reopen in the page",
      (await page.locator("#team-reviewer").inputValue()) === "Journey reviewer"
      && (await page.locator("#team-queue-state").inputValue()) === "UNDER_REVIEW"
      && (await page.locator("#team-current-action").inputValue()).startsWith("Run the public Burgers reference study"));
    check("the assessment survives the reopen in the saved bytes", JSON.stringify(reopened.jobs[0].team_review) === JSON.stringify(saved.jobs[0].team_review) && JSON.stringify(saved.jobs[0].team_review).includes("Journey reviewer"));
    await page.locator("#science-file").setInputFiles(file("study.json"));
    await page.waitForFunction(() => document.querySelector("#science-state").textContent.includes("SAVED_UNVERIFIED"));
    check("a reopened study is unverified until the service rereads it", true);
    await page.locator("#science-token").fill(token);
    await page.locator("#science-connect").click();
    await page.locator("#science-credential-state").waitFor();
    await page.locator("#science-status").click();
    await page.waitForFunction(() => document.querySelector("#science-state").textContent.includes("PRIVATE_SERVICE_RESPONSE"));
    check("the service rereads the same study after reopen", true);
    check("nothing left the launcher's origin", offOrigin.length === 0);
    check("no page errors", errors.length === 0);
  } finally {
    await browser.close();
  }
  const result = { viewport: mobile ? "390x844" : "1440x1000", passed: checks.length, failed: 0, checks, off_origin: offOrigin, errors };
  fs.writeFileSync(file("journey-result.json"), JSON.stringify(result, null, 2) + "\n");
  console.log(JSON.stringify({ viewport: result.viewport, passed: result.passed, failed: 0 }));
})().catch((error) => { console.error(error); process.exitCode = 1; });
