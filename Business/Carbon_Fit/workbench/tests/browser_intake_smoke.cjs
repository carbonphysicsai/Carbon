"use strict";
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const ROOT = path.resolve(__dirname, "..");
const PREVIEW = path.join(ROOT, "Carbon_Client_Pilot_Designer_Preview.html");
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

  const formOnly = await context.newPage();
  formOnly.on("pageerror", (error) => errors.push(String(error)));
  await formOnly.goto("file://" + PREVIEW);
  check("local preview offers guided conversation and the same form", await formOnly.locator("#guided-panel").isVisible() && (await formOnly.locator("#show-form").count()) === 1);
  const previewText = await formOnly.locator("body").innerText();
  check("preview states local-only boundary and has no enabled submit", previewText.includes("nothing is submitted") && !previewText.includes("Inquiry received") && (await formOnly.locator('button:has-text("Submit to Carbon"):not([disabled])').count()) === 0);
  await formOnly.locator("#show-form").click();
  await formOnly.locator('[data-text="intended_decision"]').fill("Decide whether the current method can support faster design comparisons.");
  await formOnly.locator('[data-text="requested_result"]').fill("Compare turnaround and one engineering output.");
  await formOnly.locator('[data-text="current_baseline"]').fill("Existing numerical method");
  await formOnly.locator('[data-text="baseline_limitation"]').fill("Turnaround is inconvenient; accuracy is unknown.");
  await formOnly.locator('[data-text="consequential_error"]').fill('Wrong comparison <img src=x onerror="window.intakePwned=true">');
  await formOnly.locator('[data-quantity-state="prediction_latency"]').selectOption("RANGE");
  await formOnly.locator('[data-quantity-unit="prediction_latency"]').fill("seconds/query");
  await formOnly.locator('[data-quantity-min="prediction_latency"]').fill("1");
  await formOnly.locator('[data-quantity-max="prediction_latency"]').fill("3");
  check("form mode preserves unknowns range units and inert text", await formOnly.locator("#summary-text").innerText().then((text) => text.includes("1–3 seconds/query") && text.includes("onerror") && text.includes("Preparation time: unknown")));
  const formPath = path.join(tmp, "form-only-intake.json");
  await saveDownload(formOnly, "#export-intake", formPath);
  const formPackage = JSON.parse(fs.readFileSync(formPath, "utf8"));
  check("form-only export uses the shared reviewed package without AI consent or conversation", formPackage.schema_version === "carbon.client-intake.reviewed.v1" && formPackage.brief.schema_version === "carbon.client-intake.draft.v1" && formPackage.ai_guidance.enabled === false && formPackage.sharing.conversation.length === 0);
  check("form-only export reports a local download rather than submission", await formOnly.locator("#intake-status").innerText().then((text) => text.includes("Nothing was transmitted")));
  await formOnly.locator("#show-guided").click();
  await formOnly.locator("#show-consent").click();
  await formOnly.locator("#consent-check").check();
  await formOnly.locator("#enable-guidance").click();
  await formOnly.waitForFunction(() => document.querySelector("#guidance-status").textContent.includes("Continue through the form"));
  check("unavailable AI preserves the draft and degrades to the form", await formOnly.locator("#form-panel").isVisible() && (await formOnly.locator('[data-text="intended_decision"]').inputValue()).includes("faster design comparisons"));

  await context.addInitScript(() => {
    let guidanceCalls = 0;
    window.fetch = async (url, options = {}) => {
      if (String(url).endsWith("/health")) return new Response(JSON.stringify({ active: true }), { status: 200, headers: { "content-type": "application/json" } });
      guidanceCalls += 1;
      const request = JSON.parse(options.body);
      window.__pilotRequests = [...(window.__pilotRequests || []), request];
      return new Response(JSON.stringify({
        mode: "PILOT_DESIGN",
        message: guidanceCalls === 1 ? "A draft pilot can connect temperature predictions to the design decision without promising execution." : "The accepted brief remains yours to review.",
        next_question: "Which load and flow conditions vary between designs?",
        proposals: guidanceCalls === 1 ? [
          { suggestion_id: "thermal-pilot-001", field: "pilot.bounded_first_pilot", value: "Compare temperature predictions across an agreed load and flow range, focusing on hotspots and design rankings.", rationale: "This makes the first comparison bounded and decision-relevant." },
          { suggestion_id: "thermal-claim-002", field: "requested_result", value: "Guaranteed 100x speedup", rationale: "A client may request this, but Carbon cannot promise it." },
        ] : [],
        unresolved_assumptions: ["Reference-data coverage and access rights remain unresolved."],
        sources: [], maturity_note: "Draft pilot for Carbon review.", request_id: "mock-guidance-001",
      }), { status: 200, headers: { "content-type": "application/json" } });
    };
  });
  const guided = await context.newPage();
  guided.on("pageerror", (error) => errors.push(String(error)));
  await guided.goto("file://" + PREVIEW);
  await guided.locator("#show-consent").click();
  check("AI data disclosure appears before the first guidance request", await guided.locator("#consent-panel").isVisible() && (await guided.locator("#guidance-input").isDisabled()));
  await guided.locator("#consent-check").check();
  await guided.locator("#enable-guidance").click();
  await guided.waitForFunction(() => !document.querySelector("#guidance-input").disabled);
  await guided.locator("#guidance-input").fill("We want to predict cold-plate temperatures faster.");
  await guided.locator("#send-guidance").click();
  await guided.waitForFunction(() => document.querySelectorAll("#proposal-list .proposal").length === 2);
  await guided.locator("#proposal-list .proposal").nth(0).getByText("Accept change").click();
  await guided.locator("#proposal-list .proposal").getByText("Reject").click();
  check("accepted suggestion changes the shared brief while the rejected claim does not", await guided.locator("#pilot-text").innerText().then((text) => text.includes("hotspots and design rankings")) && (await guided.locator("#summary-text").innerText()).includes("Requested result: Unknown"));
  await guided.locator("#show-form").click();
  check("switching to the form preserves accepted conversational edits", (await guided.locator('[data-pilot="bounded_first_pilot"]').inputValue()).includes("hotspots and design rankings"));
  await guided.locator('[data-text="intended_decision"]').fill("Select a cold-plate design for further engineering review.");
  await guided.locator("#show-guided").click();
  check("switching back to conversation preserves client form edits in the disclosed context", await guided.locator("#context-preview").textContent().then((text) => text.includes("Select a cold-plate design")));
  check("the client can undo an accepted AI edit without losing the rest of the brief", await guided.locator("#undo-suggestion").isEnabled());
  await guided.locator("#undo-suggestion").click();
  check("undo removes only the accepted proposed change", (await guided.locator("#pilot-text").innerText()) === "Not yet proposed." && (await guided.locator("#context-preview").textContent()).includes("Select a cold-plate design"));
  await guided.locator("#guidance-input").fill("Keep the pilot scope unresolved for now.");
  await guided.locator("#send-guidance").click();
  await guided.waitForFunction(() => document.querySelector("#guidance-status").textContent.includes("Review each proposed change"));
  await guided.locator("#clear-conversation").click();
  check("clear is local and does not claim provider deletion", await guided.locator("#conversation").innerText().then((text) => text.includes("does not delete provider records")));
  await guided.screenshot({ path: path.join(ROOT, "tests/preview_intake.png"), fullPage: true });
  const draftPath = path.join(tmp, "downloaded-guided-intake.json");
  await saveDownload(guided, "#export-intake", draftPath);
  const draft = JSON.parse(fs.readFileSync(draftPath, "utf8"));
  check("guided export records consent, local clearing, unresolved assumptions, and conversation opt-out", draft.ai_guidance.enabled === true && draft.ai_guidance.cleared_locally === true && draft.unresolved_assumptions.includes("Reference-data coverage and access rights remain unresolved.") && draft.sharing.include_conversation === false && draft.sharing.conversation.length === 0);
  check("download has no authority-bearing shortcut", draft.qualified === undefined && draft.approved === undefined && draft.trusted === undefined);

  const workbench = await context.newPage();
  workbench.on("pageerror", (error) => errors.push(String(error)));
  workbench.on("dialog", (dialog) => dialog.accept());
  await workbench.goto("file://" + WORKBENCH);
  await workbench.locator('[data-tab="jobs"]').click();
  await workbench.locator("#intake-draft-file").setInputFiles(draftPath);
  await workbench.waitForFunction(() => document.querySelector("#toast").textContent.includes("preview prepared"));
  check("Workbench previews the reviewed package before mutation", (await workbench.locator("#jobs-view").innerText()).includes("CREATE_NEW_JOB") && (await workbench.locator("#jobs-view").innerText()).includes("Reviewed pilot package") && (await workbench.locator("[data-job-select]").count()) === 0);
  await workbench.locator("#commit-intake-draft").click();
  check("ordinary commit creates one unassessed job with retained AI provenance", (await workbench.locator("[data-job-select]").count()) === 1 && (await workbench.locator("#route-choice").inputValue()) === "UNASSESSED" && (await workbench.locator("#jobs-view").innerText()).includes("Source intake lineage (1)"));
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
  check("fresh-session save reload retains reviewed intake lineage and route", await restored.locator("#jobs-view").innerText().then((text) => text.includes("Source intake lineage (1)") && text.includes("USE_EXISTING_CAPABILITY")));
  await restored.locator("#intake-draft-file").setInputFiles(path.join(FIXTURES, "fresh_burgers_v1.json"));
  await restored.waitForFunction(() => document.querySelector("#jobs-view").textContent.includes("CREATE_NEW_JOB"));
  await restored.locator("#commit-intake-draft").click();
  await restored.locator("#source-assessment-file").setInputFiles(ASSESSMENT);
  await restored.waitForFunction(() => document.querySelector("#toast").textContent.includes("import rejected"));
  check("fresh Burgers-like intake cannot borrow the admitted 07A assessment", !(await restored.locator("#jobs-view").innerText()).includes("MATCHED_APPROVED_SOURCE_SNAPSHOT"));
  const jobsBeforeMalformed = await restored.locator("[data-job-select]").count();
  await restored.locator("#intake-draft-file").setInputFiles({ name: "malformed-utf8.carbon-intake.json", mimeType: "application/json", buffer: Buffer.from([0xff, 0xfe, 0x7b]) });
  await restored.waitForFunction(() => document.querySelector("#toast").textContent.includes("preview rejected"));
  check("malformed UTF-8 rejects before workspace mutation", (await restored.locator("[data-job-select]").count()) === jobsBeforeMalformed);

  await restored.setViewportSize({ width: 390, height: 844 });
  check("narrow Workbench remains free of page-level horizontal overflow", await restored.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 2));
  await guided.setViewportSize({ width: 390, height: 844 });
  check("narrow pilot designer remains free of page-level horizontal overflow", await guided.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 2));
  await guided.screenshot({ path: path.join(ROOT, "tests/preview_intake_mobile.png"), fullPage: true });
  check("preview and Workbench made zero off-device requests", outbound.length === 0);
  check("malicious text never executed", await formOnly.evaluate(() => window.intakePwned === undefined));
  check("browser contexts reported no page errors", errors.length === 0);
  const previewSource = fs.readFileSync(PREVIEW, "utf8");
  check("public preview excludes internal snapshot evidence and local paths", !previewSource.includes("OWNER-GW07-RYAN-SNAPSHOT-01") && !previewSource.includes("approved_assessments") && !previewSource.includes("/Users/"));
  fs.writeFileSync(path.join(ROOT, "tests/browser_intake_results.json"), JSON.stringify({ browser: "Google Chrome", checks, errors, outbound_requests: outbound, provider_calls: "MOCK_ONLY", live_model_calls: 0, authority: "Local synthetic product-flow evidence only; no customer, scientific, rights, security, hosting, or launch qualification." }, null, 2) + "\n");
  await browser.close();
  console.log(JSON.stringify({ checks: checks.length, failures: 0, outbound_requests: outbound.length, live_model_calls: 0 }));
})().catch((error) => { console.error(error); process.exit(1); });
