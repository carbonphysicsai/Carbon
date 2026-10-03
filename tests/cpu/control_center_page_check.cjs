// The Control Center's behaviour, driven through its own scripts without a
// browser (LP-PROD-F). Reads the fixture documents a Python test built from
// the real capability, setup and campaign-view code (argv[2]), runs each
// scenario against a scripted controller on a fake clock, and prints
// {"passed": [names]}. Used by tests/cpu/test_control_center_live_page.py
// when Node is installed.
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {openPage, Storage} = require("./control_center_dom.cjs");

// The page under test; a third argument names another copy of it (to show a
// scenario fails on the page before a change, as a specimen).
const ROOT = process.argv[3] || path.join(__dirname, "../../scripts/dev/miner_launchpad");
const fx = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
// Only the scenarios whose names contain argv[4], when given.
const ONLY = process.argv[4] || "";
const copy = value => JSON.parse(JSON.stringify(value));
const REFRESH = 1500;

// ---- A scripted controller over the fixture documents. ----
function world(overrides = {}) {
  const state = {
    caps: copy(fx.caps), options: copy(fx.options), preflight: copy(fx.preflight),
    runs: [], view: null, setup: null, tools: {open: false, idle_close_seconds: 600, tools: []},
    // Answers a test sets for one request (or every one): {match, answer, keep}.
    script: [], posted: [],
    ...overrides,
  };
  state.server = async request => {
    const {method, path: url, body} = request;
    if (method === "POST") state.posted.push({path: url, body, key: request.headers["Idempotency-Key"]});
    const index = state.script.findIndex(entry => entry.match(request));
    if (index >= 0) {
      const entry = state.script[index];
      if (!entry.keep) state.script.splice(index, 1);
      return typeof entry.answer === "function" ? entry.answer(request) : entry.answer;
    }
    if (url === "/api/v1/control-center/capabilities") return {body: state.caps};
    if (url === "/api/v1/capabilities") return {body: fx.catalog};
    if (url === "/api/v1/exam-environment") return {body: fx.exam};
    if (url === "/api/v1/onboarding/requirements") return {body: fx.onboarding};
    if (url === "/api/v1/runs") return {body: {runs: []}};
    if (url === "/api/v1/development") return {body: {sources: []}};
    if (url === "/api/v1/research" && method === "GET") return {body: {preflight: state.preflight, runs: state.runs}};
    if (url === "/api/v1/operations/options") return {body: state.options};
    if (url === "/api/v1/operations" && method === "GET") return {body: {operations: fx.operations}};
    if (url === "/api/v1/setup") return state.setup ? {body: state.setup} : {status: 409, body: {error: "setup_unavailable"}};
    if (url === "/api/v1/operations/campaign_view") return state.view ? {body: state.view} : {status: 409, body: {error: "campaign_view_unavailable"}};
    if (url === "/api/v1/guide/remote-setup") return {body: {available: false, source: "docs", blocks: []}};
    if (/^\/api\/v1\/tools\/[^/]+$/.test(url)) return {body: state.tools};
    if (/^\/api\/v1\/tools\/[^/]+\/close$/.test(url)) { state.tools = {...state.tools, open: false}; return {body: {closed: true}}; }
    if (/^\/api\/v1\/tools\/[^/]+\/open$/.test(url)) { state.tools = {...state.tools, open: true}; return {body: state.tools}; }
    if (/^\/api\/v1\/research\/[^/]+\/[a-z]+$/.test(url)) return {body: state.runs[0] || {}};
    if (/^\/api\/v1\/research\/[^/]+$/.test(url)) return {body: state.runs[0] || {}};
    return {status: 404, body: {error: "not_found"}};
  };
  return state;
}
async function open(state, storage = {}) {
  const page = await openPage(ROOT, state.server, storage);
  page.state = state;
  page.$("token").value = "fixture-token";
  await page.press(page.doc.querySelector("#connect-form button[type=submit]"));
  await page.advance(0);
  assert.equal(page.text("connection-state"), "Connected", "the page connects");
  return page;
}
const refresh = page => page.advance(REFRESH);
const one = (page, selector) => { const node = page.doc.querySelector(selector); assert.ok(node, "no " + selector); return node; };
const all = (page, selector) => page.doc.querySelectorAll(selector);
// A control by its current value (a property, as in a browser, not markup).
const byValue = (page, selector, value) => { const node = all(page, selector).find(item => item.value === value); assert.ok(node, "no " + selector + " valued " + value); return node; };
function clean(page) { assert.deepEqual(page.errors.map(String), [], "the page raised no error"); }
function selectable() { return fx.caps.challenges.find(entry => entry.selectable); }
// A launchable world: the Challenge, the agent and this machine are ready.
function launchable(state, agent = "manual") {
  state.caps.compute.choices[0] = {...state.caps.compute.choices[0], availability: "available"};
  for (const choice of state.caps.agents.choices) if (choice.id === agent || (agent === "manual" && choice.id === "external_mcp")) Object.assign(choice, {availability: "available"});
  state.options.agents = state.options.agents.map(entry => ({...entry, availability: "available", reason: undefined}));
  return state;
}
async function wizardTo(page, step, agent = "manual") {
  page.go("#launch");
  await page.advance(0);
  const challenge = selectable();
  await page.press(byValue(page, "#wizard-challenges input", challenge.challenge_id));
  await page.press(page.$("wizard-next"));
  await page.press(byValue(page, "#research-selects input", agent));
  const order = ["agent", "model", "compute", "limits", "review", "launch"];
  for (const next of order.slice(0, order.indexOf(step))) {
    assert.equal(page.$("wizard-next").disabled, false, "Next can be taken from " + next + ": " + page.text("wizard-next-reason"));
    await page.press(page.$("wizard-next"));
  }
}
function lastPost(state, url) { return [...state.posted].reverse().find(entry => entry.path === url); }

const scenarios = [];
const scenario = (name, run) => scenarios.push([name, run]);

// ---- 1. Redraw only on change; never under a hand. ----
scenario("a refresh with nothing new replaces no element of the launch wizard", async () => {
  const state = launchable(world());
  const page = await open(state);
  await wizardTo(page, "review");
  const watched = [
    ...all(page, "#wizard-steps button"), ...all(page, "#wizard-challenges input"), ...all(page, "#research-selects input"),
    ...all(page, "#wizard-model *"), ...all(page, "#wizard-compute *"), ...all(page, "#wizard-review dd"), ...all(page, "#wizard-missing li"),
    ...all(page, "#research-review *"), ...all(page, "#overview-active *"), ...all(page, "#launchpad-strip button"),
  ];
  assert.ok(watched.length > 30, "the wizard is drawn");
  const before = page.doc.mutations;
  page.doc.trace = [];
  for (let i = 0; i < 6; i++) await refresh(page);
  for (const node of watched) assert.ok(node.isConnected, "kept: " + node.tagName + " " + node.textContent.slice(0, 40));
  // Six refreshes of identical data change nothing at all on the page.
  assert.equal(page.doc.mutations, before, "no DOM change from refreshes that brought nothing new: " + [...new Set(page.doc.trace)].join(" | "));
  clean(page);
});

scenario("a click pressed while a refresh redraws its list still lands", async () => {
  const state = launchable(world());
  const run = copy(fx.run);
  state.runs = [run];
  state.view = copy(fx.view);
  const page = await open(state);
  page.go("#campaigns");
  await page.advance(0);
  const card = one(page, "#research-runs a.campaign-card");
  // The campaign moves while the person presses its card: the press holds it.
  run.attempted_experiments = (run.attempted_experiments || 0) + 1;
  const landed = await page.press(card, REFRESH);
  assert.ok(landed, "the pressed card was not replaced under the press");
  assert.equal(page.window.location.hash, "#campaigns/" + encodeURIComponent(run.id) + "/live");
  // Back on the list, it is redrawn with the new count once nothing holds it.
  page.go("#campaigns");
  await refresh(page);
  assert.match(page.text("research-runs"), new RegExp("Attempts: " + run.attempted_experiments));
  clean(page);
});

scenario("a hovered control waits; it is redrawn once the pointer leaves", async () => {
  const state = launchable(world());
  const run = copy(fx.run);
  state.runs = [run];
  state.view = copy(fx.view);
  const page = await open(state);
  page.go("#campaigns");
  await page.advance(0);
  const card = one(page, "#research-runs a.campaign-card");
  page.hover(card);
  run.attempted_experiments = (run.attempted_experiments || 0) + 5;
  await refresh(page);
  assert.ok(card.isConnected, "hovered: not redrawn");
  page.unhover();
  await refresh(page);
  assert.ok(!card.isConnected, "left: redrawn with the new data");
  assert.match(page.text("research-runs"), new RegExp("Attempts: " + run.attempted_experiments));
  clean(page);
});

scenario("a message being written survives new events and replies", async () => {
  const state = launchable(world());
  state.runs = [copy(fx.run)];
  state.view = copy(fx.view);
  const page = await open(state);
  page.go("#campaigns/" + fx.run.id + "/live");
  await page.advance(0);
  const box = one(page, "#campaign-detail [data-part=compose] textarea");
  await page.type(box, "Try the wider network next");
  box.blur();
  const events = one(page, "#campaign-detail [data-part=recent] ol");
  // New operations and a reply arrive.
  state.view.events.operations.push({id: "op-new", phase: "practice", state: "RESERVED"});
  state.view.events.total += 1;
  const thread = state.view.conversation.thread;
  thread[thread.length - 1].replies.push({by: "your_agent", sequence: 999, text: "On it."});
  await page.advance(3100);
  await refresh(page);
  assert.ok(box.isConnected && box.value === "Try the wider network next", "the draft is untouched");
  assert.ok(!events.isConnected, "recent events were redrawn");
  assert.match(page.text(one(page, "#campaign-detail [data-part=talk]")), /On it\./);
  clean(page);
});

// ---- 2. The Model step passes with setup's model. ----
scenario("a provider listing no models offers and preselects setup's model", async () => {
  const state = launchable(world({caps: copy(fx.caps_setup_model), options: copy(fx.options_setup_model)}), "autonomous");
  const page = await open(state);
  await wizardTo(page, "model", "autonomous");
  const choice = fx.caps_setup_model.model.setup_choice;
  const radio = byValue(page, "#wizard-model input", choice.provider_id + "/" + choice.model_id);
  assert.ok(radio.checked, "setup's model is preselected");
  assert.match(radio.parentNode.textContent, /your setup choice/);
  assert.equal(page.$("wizard-next").disabled, false, page.text("wizard-next-reason"));
  for (const next of ["compute", "limits", "review", "launch"]) await page.press(page.$("wizard-next"));
  state.script.push({match: r => r.path === "/api/v1/research" && r.method === "POST", answer: {body: {id: "c".repeat(32)}}});
  await page.press(page.$("research-launch"));
  const sent = lastPost(state, "/api/v1/research").body;
  assert.equal(sent.model_provider, choice.provider_id);
  assert.equal(sent.model, choice.model_id);
  clean(page);
});

// ---- 3. A pending launch: kept only while its outcome is unknown. ----
scenario("a definite refusal clears the pending launch; a lost answer keeps it", async () => {
  const state = launchable(world());
  const page = await open(state);
  await wizardTo(page, "launch");
  const storage = page.window.sessionStorage;
  state.script.push({match: r => r.path === "/api/v1/research" && r.method === "POST", answer: {status: 409, body: {error: "challenge_retired"}}});
  await page.press(page.$("research-launch"));
  assert.equal(storage.getItem("carbon.launchpad.pending-research.v1"), null, "a refusal holds nothing");
  assert.match(page.text("message"), /Research launch refused: challenge retired/);
  assert.ok(page.$("research-discard").hidden && page.$("research-pending").hidden);
  // A lost answer: kept, with Retry and Discard.
  state.script.push({match: r => r.path === "/api/v1/research" && r.method === "POST", answer: {network: true}});
  await page.press(page.$("research-launch"));
  const held = JSON.parse(storage.getItem("carbon.launchpad.pending-research.v1"));
  assert.ok(held && held.key && held.unknown === true);
  assert.match(page.text("message"), /Research launch not confirmed/);
  assert.ok(!page.$("research-discard").hidden && !page.$("research-pending").hidden);
  assert.equal(page.text("research-launch"), "Retry the launch with these choices");
  // A refusal now (the review moved on) keeps the key: the first may have
  // been recorded. The retry after it carries the current review.
  state.script.push({match: r => r.path === "/api/v1/research" && r.method === "POST", answer: {status: 409, body: {error: "research_review_changed"}}});
  await page.press(page.$("research-launch"));
  assert.equal(JSON.parse(storage.getItem("carbon.launchpad.pending-research.v1")).key, held.key, "the key is kept after an unknown outcome");
  assert.match(page.text("message"), /may still have been recorded/);
  state.preflight.review_digest = "review-now";
  await refresh(page);
  state.script.push({match: r => r.path === "/api/v1/research" && r.method === "POST", answer: {body: {id: "d".repeat(32)}}});
  await page.press(page.$("research-launch"));
  const sent = lastPost(state, "/api/v1/research");
  assert.equal(sent.key, held.key, "the retry is the same request key");
  assert.equal(sent.body.review_digest, "review-now", "the retry carries the current review, not the stale body");
  assert.equal(storage.getItem("carbon.launchpad.pending-research.v1"), null);
  assert.equal(page.window.location.hash, "#campaigns/" + "d".repeat(32) + "/live");
  clean(page);
});

scenario("a retry sends the current choices; Discard lets the launch go", async () => {
  const state = launchable(world());
  const page = await open(state);
  await wizardTo(page, "limits");
  state.script.push({match: r => r.path === "/api/v1/research" && r.method === "POST", answer: {timeout: true}});
  await page.press(page.$("wizard-next"));
  await page.press(page.$("wizard-next"));
  await page.press(page.$("research-launch"));
  const first = lastPost(state, "/api/v1/research");
  assert.equal(first.body.budget, undefined);
  // Change the limits, then retry: the body is today's, the key the same.
  page.window.CarbonControlCenter.goWizard("limits");
  await page.advance(0);
  await page.press(page.$("path-advanced"));
  await page.type(page.$("budget-elapsed"), "600");
  page.window.CarbonControlCenter.goWizard("launch");
  await page.advance(0);
  state.script.push({match: r => r.path === "/api/v1/research" && r.method === "POST", answer: {status: 503, body: {error: "registration_unreadable"}}});
  await page.press(page.$("research-launch"));
  const second = lastPost(state, "/api/v1/research");
  assert.equal(second.key, first.key);
  assert.deepEqual(second.body.budget, {elapsed_seconds: 600});
  // Discard: gone, and the next launch has a new key.
  await page.press(page.$("research-discard"));
  assert.equal(page.window.sessionStorage.getItem("carbon.launchpad.pending-research.v1"), null);
  assert.ok(page.$("research-discard").hidden);
  state.script.push({match: r => r.path === "/api/v1/research" && r.method === "POST", answer: {status: 409, body: {error: "research_launch_replay_conflict"}}});
  await page.press(page.$("research-launch"));
  assert.notEqual(lastPost(state, "/api/v1/research").key, first.key);
  clean(page);
});

scenario("a launch answered as a replay conflict is spent and points to the campaign", async () => {
  const state = launchable(world());
  const storage = new Storage();
  storage.setItem("carbon.launchpad.pending-research.v1", JSON.stringify({key: "k".repeat(36), body: {agent: "none"}}));
  const page = await open(state, {sessionStorage: storage});
  await wizardTo(page, "launch");
  assert.ok(!page.$("research-discard").hidden, "a launch held from before this page loaded is unconfirmed");
  state.script.push({match: r => r.path === "/api/v1/research" && r.method === "POST", answer: {status: 409, body: {error: "research_launch_replay_conflict"}}});
  await page.press(page.$("research-launch"));
  assert.equal(lastPost(state, "/api/v1/research").key, "k".repeat(36));
  assert.equal(storage.getItem("carbon.launchpad.pending-research.v1"), null);
  assert.match(page.text("message"), /earlier launch was recorded/);
  clean(page);
});

// ---- 4. A refusal is shown; a submit is "submitted" only once admitted. ----
function manualRun() {
  const run = copy(fx.run);
  Object.assign(run, {selects: "miner", state: "READY", journey: {submitted_epochs: [], final_exams_remaining: 2, frozen_awaiting_submission: true}});
  return run;
}
scenario("a submit says started, then refused with what to do", async () => {
  const state = launchable(world());
  const run = manualRun();
  state.runs = [run];
  state.view = copy(fx.view);
  const page = await open(state);
  page.go("#campaigns/" + run.id + "/submission");
  await page.advance(0);
  state.script.push({match: r => r.path === "/api/v1/operations/submit", answer: () => ({body: {...run, state: "SUBMITTING"}})});
  run.state = "SUBMITTING";
  await page.press(one(page, "#journey-submit-" + run.id));
  assert.doesNotMatch(page.text("message"), /Submitted for the DEVELOPMENT comparison/);
  assert.match(page.text("message"), /Submit started/);
  assert.match(page.text(one(page, "#campaign-detail [data-operation]")), /Submitting your frozen candidate/);
  // The controller records a refusal: shown with its next action.
  Object.assign(run, {state: "READY", last_refusal: {code: "registration_required", next_action: "Register your hotkey, then submit again.", at: 1800000100}});
  await refresh(page);
  await refresh(page);
  assert.match(page.text("message"), /Not done: registration required\. Register your hotkey/);
  const banner = one(page, "#campaign-detail [data-part=attention] .refusal-note");
  assert.match(banner.textContent, /Refused: registration required/);
  assert.match(banner.textContent, /What to do: Register your hotkey/);
  assert.equal(one(page, "#campaign-detail [data-part=attention] a.button").getAttribute("href"), "#setup/register");
  assert.doesNotMatch(page.text("campaign-detail"), /Submitted for the DEVELOPMENT comparison/);
  clean(page);
});

scenario("a submit says submitted only when the record shows it admitted", async () => {
  const state = launchable(world());
  const run = manualRun();
  state.runs = [run];
  state.view = copy(fx.view);
  const page = await open(state);
  page.go("#campaigns/" + run.id + "/submission");
  await page.advance(0);
  state.script.push({match: r => r.path === "/api/v1/operations/submit", answer: () => ({body: {...run, state: "SUBMITTING"}})});
  run.state = "SUBMITTING";
  await page.press(one(page, "#journey-submit-" + run.id));
  await refresh(page);
  assert.doesNotMatch(page.text("campaign-detail"), /Submitted for the DEVELOPMENT comparison/);
  Object.assign(run, {state: "READY", journey: {submitted_epochs: [1], final_exams_remaining: 1, frozen_awaiting_submission: false}});
  await refresh(page);
  await refresh(page);
  assert.match(page.text("message"), /Submitted for the DEVELOPMENT comparison/);
  assert.match(page.text(one(page, "#campaign-detail [data-operation]")), /Submitted for the DEVELOPMENT comparison/);
  clean(page);
});

scenario("a campaign without last_refusal shows no refusal", async () => {
  const state = launchable(world());
  state.runs = [copy(fx.run)];
  state.view = copy(fx.view);
  const page = await open(state);
  page.go("#campaigns/" + fx.run.id + "/live");
  await page.advance(0);
  assert.equal(all(page, "#campaign-detail .refusal-note").length, 0);
  clean(page);
});

// ---- 5. Reconcile in reach whenever the state needs it. ----
for (const stateName of ["RECONCILIATION_REQUIRED", "INTERRUPTED", "PAUSE_REQUESTED"]) {
  scenario("Reconcile is on the Live tab, with why, for " + stateName, async () => {
    const state = launchable(world());
    const run = {...copy(fx.run), state: stateName};
    state.runs = [run];
    state.view = copy(fx.view);
    state.view.fixture = false;
    state.view.campaign.state = stateName;
    state.view.controls = state.view.controls.map(control => ({...control, available: true, reason: null}));
    const page = await open(state);
    page.go("#campaigns/" + run.id + "/live");
    await page.advance(0);
    const button = one(page, "#campaign-detail [data-part=now] [data-action=reconcile]");
    assert.equal(button.disabled, false);
    assert.match(page.text(one(page, "#campaign-detail [data-part=attention]")), /Needs attention/);
    await page.press(button);
    assert.ok(state.posted.some(entry => entry.path === "/api/v1/research/" + run.id + "/reconcile"));
    clean(page);
  });
}
scenario("a healthy campaign's Live tab keeps Reconcile in the header only", async () => {
  const state = launchable(world());
  state.runs = [copy(fx.run)];
  state.view = copy(fx.view);
  const page = await open(state);
  page.go("#campaigns/" + fx.run.id + "/live");
  await page.advance(0);
  assert.equal(all(page, "#campaign-detail [data-part=now] [data-action=reconcile]").length, 0);
  assert.equal(all(page, "#campaign-detail .rs-head [data-action=reconcile]").length, 1);
  assert.equal(page.text(one(page, "#campaign-detail [data-part=attention]")), "");
  clean(page);
});
scenario("a queued campaign with no frozen record can be reconciled without its view", async () => {
  const state = launchable(world());
  const run = {id: "e".repeat(32), state: "QUEUED", experiments: [], refusals: []};
  state.runs = [run];
  state.view = null;
  const page = await open(state);
  page.go("#campaigns/" + run.id + "/live");
  await page.advance(0);
  assert.match(page.text("campaign-detail"), /never started here/);
  const button = one(page, "#campaign-detail [data-part=attention] [data-action=reconcile]");
  await page.press(button);
  assert.ok(state.posted.some(entry => entry.path === "/api/v1/research/" + run.id + "/reconcile"));
  // The Overview's card offers it too.
  page.go("#overview");
  await page.advance(0);
  assert.ok(one(page, "#active-campaign [data-action=reconcile]"));
  clean(page);
});

// ---- 6. The Tools tab: one key until answered, progress, readable text. ----
scenario("Tools: a submit retried after a timeout reuses its key and follows the record", async () => {
  const state = launchable(world());
  const run = manualRun();
  state.runs = [run];
  state.view = copy(fx.view);
  state.tools = {open: true, idle_close_seconds: 600, holds: "", tools: [], tasks: []};
  const page = await open(state);
  page.go("#campaigns/" + run.id + "/tools");
  await page.advance(0);
  const submit = [...all(page, "#campaign-detail button")].find(b => b.textContent === "Close the tools and submit the candidate");
  assert.ok(submit, "the submit button is drawn");
  state.script.push({match: r => r.path === "/api/v1/operations/submit", answer: {timeout: true}});
  await page.press(submit);
  const first = lastPost(state, "/api/v1/operations/submit").body.idempotency_key;
  const line = one(page, "#campaign-detail .rs-workbench > p[role=status]");
  assert.match(line.textContent, /Not confirmed: .*same key/);
  // Reopen, retry: the same key, and progress from the record.
  await page.press([...all(page, "#campaign-detail button")].find(b => b.textContent === "Open the tools"));
  run.state = "SUBMITTING";
  state.script.push({match: r => r.path === "/api/v1/operations/submit", answer: () => ({body: {...run}})});
  await page.press([...all(page, "#campaign-detail button")].find(b => b.textContent === "Close the tools and submit the candidate"));
  assert.equal(lastPost(state, "/api/v1/operations/submit").body.idempotency_key, first, "one key until answered");
  await refresh(page);
  assert.match(line.textContent, /Submitting your frozen candidate/);
  assert.doesNotMatch(line.textContent, /\{|\}/, "readable text, not JSON");
  Object.assign(run, {state: "READY", journey: {submitted_epochs: [1], final_exams_remaining: 1, frozen_awaiting_submission: false}});
  await refresh(page);
  assert.match(line.textContent, /Submitted for the DEVELOPMENT comparison/);
  clean(page);
});

scenario("Tools: a result reads as lines of text", async () => {
  const state = launchable(world());
  state.runs = [copy(fx.run)];
  state.view = copy(fx.view);
  const page = await open(state);
  const readable = page.window.CarbonTools.readable;
  const text = readable({verdict: "submittable", findings: [{field: "width", ok: true}], cost: {trials: 1}, note: null, list: []});
  assert.equal(text, ["verdict: submittable", "findings:", "  -", "    field: width", "    ok: yes", "cost:", "  trials: 1", "note: none", "list: (none)"].join("\n"));
  clean(page);
});

// ---- 7. Budgets in human units; links; the MCP command. ----
scenario("limits are typed in dollars and minutes and sent in the ledger's units", async () => {
  const state = launchable(world());
  const page = await open(state);
  await wizardTo(page, "limits");
  await page.press(page.$("path-advanced"));
  assert.equal(page.text(one(page, "label[for=ceiling-provider_nanodollars]")), "model spend · USD");
  assert.equal(page.text(one(page, "label[for=ceiling-numerical_milliseconds]")), "worker time · minutes");
  await page.type(page.$("ceiling-provider_nanodollars"), "5");
  await page.type(page.$("ceiling-numerical_milliseconds"), "30");
  await page.type(page.$("ceiling-research_trials"), "12");
  const summary = page.text("composition-summary");
  assert.match(summary, /model spend ≤ \$5\.00/);
  assert.match(summary, /worker time ≤ 30 min/);
  assert.match(summary, /research trials ≤ 12/);
  await page.type(page.$("ceiling-provider_nanodollars"), "0.0000000001");
  assert.match(page.text("composition-summary"), /model spend ≤ \$0\.00/);
  await page.type(page.$("ceiling-provider_nanodollars"), "2.5");
  await page.press(page.$("wizard-next"));
  await page.press(page.$("wizard-next"));
  state.script.push({match: r => r.path === "/api/v1/research" && r.method === "POST", answer: {body: {id: "f".repeat(32)}}});
  await page.press(page.$("research-launch"));
  assert.deepEqual(lastPost(state, "/api/v1/research").body.budget, {ceilings: {provider_nanodollars: 2500000000, numerical_milliseconds: 1800000, research_trials: 12}});
  clean(page);
});

scenario("old campaign links open the tab they meant, under its own name", async () => {
  const state = launchable(world());
  state.runs = [copy(fx.run)];
  state.view = copy(fx.view);
  const page = await open(state);
  for (const [written, shown] of [["overview", "live"], ["metrics", "experiments"], ["journal", "reasoning"], ["", "live"], ["tools", "tools"]]) {
    page.go("#campaigns/" + fx.run.id + (written ? "/" + written : ""));
    await page.advance(0);
    assert.equal(one(page, "#campaign-detail .rs-tab").dataset.tab, shown, written);
    assert.equal(page.window.location.hash, "#campaigns/" + fx.run.id + "/" + shown);
    assert.equal(one(page, "#campaign-detail nav.tabs [aria-current=page]").getAttribute("href"), "#campaigns/" + fx.run.id + "/" + shown);
  }
  page.go("#overview");
  await page.advance(0);
  for (const link of all(page, "a.campaign-card")) assert.match(link.getAttribute("href"), /\/live$/);
  clean(page);
});

scenario("Connections shows the real MCP command and the profile it names", async () => {
  const state = launchable(world());
  const mcp = state.caps.agents.choices.find(choice => choice.id === "external_mcp");
  Object.assign(mcp, {command: "/venv/bin/carbon-mcp --configuration /home/miner/profile.json", profile_path: "/home/miner/profile.json"});
  const page = await open(state);
  page.go("#connections");
  await page.advance(0);
  assert.match(page.text("connection-catalog"), /\/venv\/bin\/carbon-mcp --configuration \/home\/miner\/profile\.json/);
  assert.match(page.text("connection-catalog"), /Your runner profile: \/home\/miner\/profile\.json/);
  assert.doesNotMatch(page.text("connection-catalog"), /<your runner profile>/);
  clean(page);
});

// ---- 8. Sending the worker shows its progress. ----
scenario("sending the worker shows how long it has been going until it answers", async () => {
  const state = launchable(world({setup: copy(fx.setup_send)}));
  let release;
  state.script.push({match: r => r.path === "/api/v1/setup/send_worker", answer: () => new Promise(resolve => { release = resolve; })});
  const page = await open(state);
  page.go("#setup/compute");
  await page.advance(0);
  await page.press(page.$("setup-send-worker-consent"));
  const send = [...all(page, "#setup-body form[data-step=send_worker] button")][0];
  await page.press(send);
  assert.equal(lastPost(state, "/api/v1/setup/send_worker").body.consent.send.destination, fx.setup_send.steps.compute.remote_machine.destination);
  await page.advance(65000);
  assert.match(page.text("setup-send-progress"), /1m 05s so far/);
  assert.ok(one(page, "#setup-result progress"));
  release({body: copy(fx.setup_send)});
  await page.advance(0);
  assert.equal(page.text("setup-result"), "Checked: send_worker.");
  clean(page);
});

(async () => {
  const passed = [], failed = [];
  for (const [name, run] of scenarios) {
    if (ONLY && !name.includes(ONLY)) continue;
    try { await run(); passed.push(name); }
    catch (error) { failed.push(name + ": " + String(error && error.message || error).split("\n")[0]); if (!process.argv[3]) { error.message = name + ": " + error.message; throw error; } }
  }
  process.stdout.write(JSON.stringify({passed, failed}));
})().catch(error => { process.stderr.write(String(error && error.stack || error) + "\n"); process.exit(1); });
