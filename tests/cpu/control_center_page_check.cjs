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
const crypto = require("node:crypto");
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
    if (url === "/api/v1/operations" && method === "GET") return {body: {operations: state.operations || fx.operations}};
    if (url === "/api/v1/setup") return state.setup ? {body: state.setup} : {status: 409, body: {error: "setup_unavailable"}};
    if (url === "/api/v1/operations/campaign_view") return state.view ? {body: state.view} : {status: 409, body: {error: "campaign_view_unavailable"}};
    if (url === "/api/v1/guide/remote-setup") return {body: {available: false, source: "docs", blocks: []}};
    if (/^\/api\/v1\/tools\/[^/]+$/.test(url)) return {body: state.tools};
    if (/^\/api\/v1\/tools\/[^/]+\/close$/.test(url)) { state.tools = {...state.tools, open: false}; return {body: {closed: true}}; }
    if (/^\/api\/v1\/tools\/[^/]+\/open$/.test(url)) { state.tools = {...state.tools, open: true}; return {body: state.tools}; }
    if (/^\/api\/v1\/research\/[^/]+\/[a-z]+$/.test(url)) return {body: state.runs[0] || {}};
    if (/^\/api\/v1\/research\/[^/]+$/.test(url)) return {body: state.runs[0] || {}};
    return {status: 404, body: {error: "route_not_found"}};
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

scenario("a resting pointer holds a redraw back only briefly", async () => {
  const state = launchable(world());
  const run = copy(fx.run);
  state.runs = [run];
  state.view = copy(fx.view);
  const page = await open(state);
  page.go("#campaigns");
  await page.advance(0);
  // An agent's pointer, left on the card it last clicked: `:hover` holds the
  // whole card, and with it the list.
  const card = one(page, "#research-runs a.campaign-card");
  page.hover(card.querySelector("h3"));
  run.state = "PAUSED";
  await refresh(page);
  assert.ok(card.isConnected, "held while the pointer rests on it");
  for (let i = 0; i < 3; i++) await refresh(page);
  assert.match(page.text("research-runs"), /PAUSED/, "shown within the hold's bound, the pointer still resting");
  // The same for the campaign's header, under a pointer resting on Export.
  page.go("#campaigns/" + run.id + "/live");
  await page.advance(0);
  page.hover([...all(page, "#campaign-detail .rs-head button")].find(b => b.textContent === "Export"));
  state.view.campaign.state = "PAUSED";
  for (let i = 0; i < 6; i++) await refresh(page);
  assert.match(page.text(one(page, "#campaign-detail .rs-meta")), /PAUSED/);
  page.unhover();
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
// Carbon's agent: Graphite where the controller offers it (it replaced the
// autonomous agent for new launches), the autonomous agent before.
const carbonAgent = caps => caps.agents.choices.some(choice => choice.launch_agent === "graphite") ? "graphite" : "autonomous";
scenario("a provider listing no models offers and preselects setup's model", async () => {
  const agent = carbonAgent(fx.caps_setup_model);
  const state = launchable(world({caps: copy(fx.caps_setup_model), options: copy(fx.options_setup_model)}), agent);
  const page = await open(state);
  await wizardTo(page, "model", agent);
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

scenario("a lost submit that ran lets its key go: the next epoch's submit is a new request", async () => {
  const state = launchable(world());
  const run = manualRun();
  state.runs = [run];
  state.view = copy(fx.view);
  const page = await open(state);
  page.go("#campaigns/" + run.id + "/submission");
  await page.advance(0);
  state.script.push({match: r => r.path === "/api/v1/operations/submit", answer: {timeout: true}});
  await page.press(one(page, "#journey-submit-" + run.id));
  const first = lastPost(state, "/api/v1/operations/submit").body.idempotency_key;
  assert.match(page.text("message"), /Not confirmed: .*same key/);
  assert.ok(one(page, "#journey-discard-submit-" + run.id), "a held submit can be let go");
  // The controller ran it: epoch 1 is submitted, and its key is spent.
  Object.assign(run, {journey: {submitted_epochs: [1], final_exams_remaining: 1, frozen_awaiting_submission: false}});
  await refresh(page);
  assert.equal(all(page, "#journey-discard-submit-" + run.id).length, 0, "the record shows how it ended");
  assert.equal(page.window.sessionStorage.getItem("carbon.launchpad.pending-operation.v1"), "{}");
  // The next candidate is frozen, then submitted: a new request, dispatched.
  state.script.push({match: r => r.path === "/api/v1/operations/freeze_candidate", answer: () => ({body: {...run, state: "FREEZING"}})});
  await page.press(one(page, "#journey-freeze-" + run.id));
  run.journey = {submitted_epochs: [1], final_exams_remaining: 1, frozen_awaiting_submission: true};
  await refresh(page);
  state.script.push({match: r => r.path === "/api/v1/operations/submit", answer: () => ({body: {...run, state: "SUBMITTING"}})});
  await page.press(one(page, "#journey-submit-" + run.id));
  assert.notEqual(lastPost(state, "/api/v1/operations/submit").body.idempotency_key, first, "never epoch 1's key");
  clean(page);
});

scenario("a retried submit answered after its work finished reads as submitted", async () => {
  const state = launchable(world());
  const run = manualRun();
  state.runs = [run];
  state.view = copy(fx.view);
  const page = await open(state);
  page.go("#campaigns/" + run.id + "/submission");
  await page.advance(0);
  state.script.push({match: r => r.path === "/api/v1/operations/submit", answer: {timeout: true}});
  await page.press(one(page, "#journey-submit-" + run.id));
  const first = lastPost(state, "/api/v1/operations/submit").body.idempotency_key;
  // The retry's answer is slow; meanwhile the record shows the epoch
  // submitted. The answer is a replay of that finished work.
  let release;
  state.script.push({match: r => r.path === "/api/v1/operations/submit", answer: () => new Promise(resolve => { release = resolve; })});
  await page.press(one(page, "#journey-submit-" + run.id));
  assert.equal(lastPost(state, "/api/v1/operations/submit").body.idempotency_key, first, "the same request, under its key");
  Object.assign(run, {journey: {submitted_epochs: [1], final_exams_remaining: 1, frozen_awaiting_submission: false}});
  await refresh(page);
  release({body: copy(run)});
  await page.advance(0);
  await refresh(page);
  assert.match(page.text("message"), /Submitted for the DEVELOPMENT comparison/);
  assert.doesNotMatch(page.text("campaign-detail"), /without the change it was for/);
  clean(page);
});

scenario("an edited retry is a new request under a new key, said so; Discard lets one go", async () => {
  const state = launchable(world());
  const run = manualRun();
  run.journey.frozen_awaiting_submission = false;
  state.runs = [run];
  state.view = copy(fx.view);
  const page = await open(state);
  page.go("#campaigns/" + run.id + "/experiments");
  await page.advance(0);
  const practice = () => one(page, "#journey-practice-" + run.id);
  const key = () => lastPost(state, "/api/v1/operations/practice").body.idempotency_key;
  await page.type(one(page, "#journey-hypothesis-" + run.id), "a wider network");
  state.script.push({match: r => r.path === "/api/v1/operations/practice", answer: {network: true}});
  await page.press(practice());
  const first = key();
  // The same values again: the same key.
  state.script.push({match: r => r.path === "/api/v1/operations/practice", answer: {status: 503, body: {error: "registration_unreadable"}}});
  await page.press(practice());
  assert.equal(key(), first);
  // Edited: a new request, under a new key, and the page says so.
  await page.type(one(page, "#journey-hypothesis-" + run.id), "a deeper network");
  state.script.push({match: r => r.path === "/api/v1/operations/practice", answer: () => ({body: {...run, state: "PRACTICING"}})});
  await page.press(practice());
  const second = key();
  assert.notEqual(second, first);
  assert.match(page.text("message"), /went as a new request under a new key/);
  // Another lost practice, let go by Discard: the next one is new.
  await refresh(page);
  state.script.push({match: r => r.path === "/api/v1/operations/practice", answer: {timeout: true}});
  await page.press(practice());
  const third = key();
  assert.notEqual(third, second);
  await page.press(one(page, "#journey-discard-practice-" + run.id));
  assert.equal(all(page, "#journey-discard-practice-" + run.id).length, 0);
  assert.match(page.text("message"), /Discarded/);
  state.script.push({match: r => r.path === "/api/v1/operations/practice", answer: () => ({body: {...run, state: "PRACTICING"}})});
  await page.press(practice());
  assert.notEqual(key(), third);
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
// The page offers what the controller publishes (slice C's `recovery`), and
// each state's documents are the controller's own for that state
// (fx.recovering: the observe row with `supervisor.recovery_actions`, and the
// campaign view built for that state by the real campaign-view code), so a
// state is never paired with another state's recovery. The controller offers
// Reconcile for each of these states (the lead's W3 contract; review repair).
const LABELS = {reconcile: "Reconcile", resume: "Resume", stop: "Stop"};
for (const stateName of ["RECONCILIATION_REQUIRED", "INTERRUPTED", "PAUSE_REQUESTED"]) {
  scenario("Reconcile is on the Live tab, with why, for " + stateName, async () => {
    const real = fx.recovering[stateName];
    const offered = real.view.recovery.map(item => item.action);
    assert.ok(offered.includes("reconcile"), "the controller offers Reconcile for " + stateName + ": " + offered);
    assert.deepEqual(real.run.recovery, real.view.recovery, "the list row and the view agree");
    const state = launchable(world());
    const run = copy(real.run);
    state.runs = [run];
    state.view = copy(real.view);
    const page = await open(state);
    page.go("#campaigns/" + run.id + "/live");
    await page.advance(0);
    const now = "#campaign-detail [data-part=now]";
    // Each action the controller offers is among the Live tab's controls,
    // ready, and the ways forward (Stop aside) are primary.
    for (const action of offered) {
      const button = one(page, now + " [data-action=" + action + "]");
      assert.equal(button.disabled, false, action);
      assert.equal(button.classList.contains("primary"), action !== "stop", action);
    }
    // Reconcile is there, once, ready.
    assert.equal(all(page, now + " [data-action=reconcile]").length, 1);
    const button = one(page, now + " [data-action=reconcile]");
    assert.equal(button.disabled, false);
    // Why, naming the way forward and Reconcile.
    const attention = page.text(one(page, "#campaign-detail [data-part=attention]"));
    assert.match(attention, /Needs attention/);
    assert.ok(attention.includes(LABELS[offered[0]]), "why names the way forward: " + attention);
    assert.match(attention, /Reconcile/, "why says what Reconcile is for: " + attention);
    await page.press(button);
    assert.ok(state.posted.some(entry => entry.path === "/api/v1/research/" + run.id + "/reconcile"));
    clean(page);
  });
}
scenario("a controller that publishes no recovery list gets Reconcile from the state, with why", async () => {
  // A controller before slice C: the page reads the state itself.
  for (const name of Object.keys(fx.recovering)) {
    const state = launchable(world());
    const run = copy(fx.recovering[name].run);
    delete run.recovery;
    state.runs = [run];
    state.view = copy(fx.recovering[name].view);
    delete state.view.recovery;
    const page = await open(state);
    page.go("#campaigns/" + run.id + "/live");
    await page.advance(0);
    const button = one(page, "#campaign-detail [data-part=now] [data-action=reconcile]");
    assert.equal(button.disabled, false, name);
    assert.match(page.text(one(page, "#campaign-detail [data-part=attention]")), /Needs attention/, name);
    await page.press(button);
    assert.ok(state.posted.some(entry => entry.path === "/api/v1/research/" + run.id + "/reconcile"), name);
    clean(page);
  }
});
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
  // No model call's outcome is unknown: nothing to settle is shown.
  assert.equal(one(page, "#campaign-detail [data-part=settlement]").hidden, true);
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
  // A fresh launch is QUEUED until its run thread creates its ledger: no
  // alarm at first, only once it has stayed so.
  assert.doesNotMatch(page.text("campaign-detail"), /never started here|Needs attention/);
  for (let i = 0; i < 21; i++) await refresh(page);
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
scenario("the controller's own recovery actions are offered when its record carries them", async () => {
  const state = launchable(world());
  // Slice C's record: admitted, nothing carrying it out, and what moves it.
  const run = {id: "e".repeat(32), state: "QUEUED", experiments: [], refusals: [], in_flight: null, recovery: [{action: "resume", operation: "resume"}, {action: "stop", operation: "halt"}]};
  state.runs = [run];
  state.view = null;
  const page = await open(state);
  page.go("#campaigns/" + run.id + "/live");
  await page.advance(0);
  const attention = () => one(page, "#campaign-detail [data-part=attention]");
  assert.match(page.text(attention()), /nothing is carrying it out\. Resume dispatches it again/);
  assert.equal(all(page, "#campaign-detail [data-part=attention] [data-action=reconcile]").length, 0, "the controller did not ask for Reconcile");
  const resume = one(page, "#campaign-detail [data-part=attention] [data-action=resume]");
  assert.ok(resume.classList.contains("primary"));
  await page.press(resume);
  assert.ok(state.posted.some(entry => entry.path === "/api/v1/research/" + run.id + "/resume"));
  // Carried out again: nothing is needed, and nothing is said.
  Object.assign(run, {in_flight: {operation: "run", state: "RUNNING", since: 1800000000, supervisor_running: true}, recovery: []});
  await refresh(page);
  assert.equal(page.text(attention()), "");
  clean(page);
});
// What Reconcile settles (LP-PROD-W2), over a real campaign's documents
// (fx.reconciled: a model call answered by another model, so its outcome is
// unknown, published awaiting Reconcile and again once it settled it).
scenario("the Live tab says what Reconcile books before the press, and what it booked after", async () => {
  const {awaiting, settled} = fx.reconciled;
  const state = launchable(world());
  const run = copy(awaiting.run);
  state.runs = [run];
  state.view = copy(awaiting.view);
  const page = await open(state);
  page.go("#campaigns/" + run.id + "/live");
  await page.advance(0);
  const panel = () => one(page, "#campaign-detail [data-part=settlement]");
  // Before: the call, what Reconcile books for it and that nothing is resent,
  // beside the Reconcile control; the line above says the same.
  const pending = awaiting.view.reconciliation.awaiting_settlement[0];
  assert.equal(panel().hidden, false);
  let text = page.text(panel());
  assert.ok(text.includes(pending.identity + " · Reconcile books $"), text);
  assert.match(text, /at its full reservation/);
  assert.match(text, /It resends nothing/);
  assert.ok(text.includes(awaiting.view.reconciliation.accounting), "the accounting rule is shown");
  assert.match(page.text(one(page, "#campaign-detail [data-part=attention]")), /books each model call whose outcome is unknown at its full reservation; it resends nothing/);
  // A press refused with the settlement's own step: the page says that step.
  const step = "a model call of this campaign is still being admitted or in flight; settle once it has ended";
  state.script.push({match: r => r.path === "/api/v1/research/" + run.id + "/reconcile", answer: {status: 409, body: {error: "call_in_flight", next_step: step}}});
  await page.press(one(page, "#campaign-detail [data-part=now] [data-action=reconcile]"));
  assert.match(page.text("message"), /call_in_flight/);
  assert.ok(page.text("message").includes("Next: " + step + "."), page.text("message"));
  // The press, answered as the controller answers it: the settled campaign.
  state.script.push({match: r => r.path === "/api/v1/research/" + run.id + "/reconcile", answer: () => {
    state.runs = [copy(settled.run)];
    state.view = copy(settled.view);
    return {body: settled.run};
  }});
  await page.press(one(page, "#campaign-detail [data-part=now] [data-action=reconcile]"));
  assert.ok(state.posted.some(entry => entry.path === "/api/v1/research/" + run.id + "/reconcile"));
  for (let i = 0; i < 3; i++) await refresh(page);
  // After: what it booked, why the outcome was unknown, and the caveat that
  // the booking is not a proven bound for a call another model answered.
  const done = settled.view.reconciliation.settled[0];
  assert.equal(panel().hidden, false);
  text = page.text(panel());
  assert.match(text, /Settled by Reconcile · booked \$/);
  assert.ok(text.includes(done.identity + " · " + done.reason.replaceAll("_", " ") + " · booked $"), text);
  assert.ok(done.caveat && text.includes(done.caveat), "the model caveat is shown: " + text);
  assert.ok(text.includes(settled.view.reconciliation.accounting));
  assert.doesNotMatch(text, /Reconcile books/, "nothing awaits settlement now");
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

scenario("a cap keeps its exact ledger value when another limit is edited, and is never rounded up", async () => {
  const state = launchable(world());
  // Saved by the page before human units: caps finer than the editor shows
  // at a glance (a nanodollar, a millisecond).
  const local = new Storage();
  local.setItem("carbon.control-center.wizard.v1", JSON.stringify({launchPath: "advanced", budget: {ceilings: {provider_nanodollars: 1234567891, numerical_milliseconds: 1000, retained_bytes: 1}}}));
  const page = await open(state, {localStorage: local});
  await wizardTo(page, "limits");
  const field = name => page.$("ceiling-" + name);
  // Read across the page's realm as plain data.
  const caps = () => copy(page.window.CarbonControlCenter.state().composition.budget.ceilings);
  // Shown exactly (minutes rounded up in the last place, so they read back the same).
  assert.equal(field("provider_nanodollars").value, "1.234567891");
  assert.equal(field("numerical_milliseconds").value, "0.01667");
  assert.equal(field("retained_bytes").value, "0.000001");
  assert.match(page.text("composition-summary"), /model spend ≤ \$1\.234567891/);
  assert.match(page.text("composition-summary"), /worker time ≤ 1 s/);
  // Editing another limit leaves them exactly as they were.
  await page.type(page.$("budget-elapsed"), "600");
  assert.deepEqual(caps(), {provider_nanodollars: 1234567891, numerical_milliseconds: 1000, retained_bytes: 1});
  // Typed: read exactly and rounded down, never up.
  await page.type(field("provider_nanodollars"), "0.0015");
  assert.equal(caps().provider_nanodollars, 1500000);
  await page.type(field("provider_nanodollars"), "0.29");
  assert.equal(caps().provider_nanodollars, 290000000);
  await page.type(field("provider_nanodollars"), "0.0000000019");
  assert.equal(caps().provider_nanodollars, 1, "1.9 nanodollars is a cap of 1, never 2");
  await page.type(field("numerical_milliseconds"), "0.5");
  assert.equal(caps().numerical_milliseconds, 30000);
  // Typed as shown before (with a trailing 0, so it is read, not kept).
  await page.type(field("numerical_milliseconds"), "0.016670");
  assert.equal(caps().numerical_milliseconds, 1000, "the shown minutes read back as the same milliseconds");
  // The reviewer's round trip: typed, Quick, reopened, another field edited.
  await page.type(field("provider_nanodollars"), "0.0015");
  await page.press(page.$("path-quick"));
  await page.press(page.$("path-advanced"));
  assert.equal(field("provider_nanodollars").value, "0.0015");
  await page.type(page.$("budget-elapsed"), "900");
  assert.equal(caps().provider_nanodollars, 1500000, "not raised to $0.002");
  assert.match(page.text("composition-summary"), /model spend ≤ \$0\.0015/);
  await page.press(page.$("wizard-next"));
  await page.press(page.$("wizard-next"));
  state.script.push({match: r => r.path === "/api/v1/research" && r.method === "POST", answer: {body: {id: "f".repeat(32)}}});
  await page.press(page.$("research-launch"));
  assert.deepEqual(lastPost(state, "/api/v1/research").body.budget, {elapsed_seconds: 900, ceilings: {provider_nanodollars: 1500000, numerical_milliseconds: 1000, retained_bytes: 1}});
  clean(page);
});

scenario("the usage table reads in the units its limits are set in", async () => {
  const state = launchable(world());
  const run = copy(fx.run);
  state.runs = [run];
  state.view = copy(fx.view);
  const page = await open(state);
  page.go("#campaigns/" + run.id + "/logs");
  await page.advance(0);
  const cells = label => {
    const row = [...all(page, "#campaign-detail [data-part=logs] tr")].find(tr => tr.querySelector("td")?.textContent === label);
    assert.ok(row, "a row for " + label);
    return [...row.querySelectorAll("td")].map(td => td.textContent);
  };
  // usage: budget $0.05 and 16 trials; reported $0.00421, 812 s of worker
  // time and 8 trials; reserved $0.00012 and 1 trial.
  assert.deepEqual(cells("model spend · USD"), ["model spend · USD", "$0.05", "$0.00421", "$0.00012", "–"]);
  assert.deepEqual(cells("worker time · minutes"), ["worker time · minutes", "No limit", "13 min 32 s", "–", "–"]);
  assert.deepEqual(cells("research trials"), ["research trials", "16", "8", "1", "–"]);
  assert.doesNotMatch(page.text(one(page, "#campaign-detail [data-part=logs]")), /4210000|812000/);
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
  Object.assign(mcp, {command: "/venv/bin/carbon-mcp --configuration /srv/miner/profile.json", profile_path: "/srv/miner/profile.json"});
  const page = await open(state);
  page.go("#connections");
  await page.advance(0);
  assert.match(page.text("connection-catalog"), /\/venv\/bin\/carbon-mcp --configuration \/srv\/miner\/profile\.json/);
  assert.match(page.text("connection-catalog"), /Your runner profile: \/srv\/miner\/profile\.json/);
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

scenario("a send that does not go through leaves its button ready again", async () => {
  const state = launchable(world({setup: copy(fx.setup_send)}));
  state.script.push({match: r => r.path === "/api/v1/setup/send_worker", answer: {status: 409, body: {error: "remote_unreachable", next_step: "Check that ssh me@box works."}}});
  const page = await open(state);
  page.go("#setup/compute");
  await page.advance(0);
  await page.press(page.$("setup-send-worker-consent"));
  const send = [...all(page, "#setup-body form[data-step=send_worker] button")][0];
  await page.press(send);
  assert.match(page.text("setup-result"), /remote unreachable/);
  assert.ok(send.isConnected, "the form is still drawn");
  assert.equal(send.textContent, "Send my worker");
  assert.equal(send.disabled, false);
  clean(page);
});

// ---- 9. The Tools tab reads a file under either research tools rule. ----
scenario("Tools: a read answered as text (v2 rule) or as base64 (historical) shows the same file", async () => {
  const state = launchable(world());
  const run = copy(fx.run);
  state.runs = [run];
  state.view = copy(fx.view);
  const text = "loss = 0.25\nstep = 42 · é\n";
  const bytes = Buffer.from(text, "utf8");
  const file = {name: "notes.txt", bytes: bytes.length, digest: "sha256:" + "0".repeat(64)};
  let rule = "v2";
  state.tools = {open: true, idle_close_seconds: 600, holds: "", tasks: [], tools: [{name: "carbon_research_v2__start_research_task", operation: "start_research_task", description: "One task.", input_schema: {type: "object", properties: {}, required: []}}]};
  const reply = result => ({body: {ok: true, result: {payload: {status: "OK", public_result: {result}}}}});
  state.script.push({keep: true, match: r => /^\/api\/v1\/tools\/[^/]+\/call$/.test(r.path), answer: r => {
    const args = r.body.arguments;
    if (args.action === "inventory") return reply({files: [file]});
    if (args.action !== "read_file") return reply({});
    const {offset, count} = args.arguments;
    const chunk = bytes.subarray(offset, offset + count);
    // The v2 rule returns the bytes once, as text; the historical rule, base64 alone.
    const content = rule === "v2" ? {content_utf8: chunk.toString("utf8"), content_base64: null} : {content_base64: chunk.toString("base64")};
    return reply({name: file.name, digest: file.digest, bytes: file.bytes, offset, ...content});
  }});
  const page = await open(state);
  page.go("#campaigns/" + run.id + "/tools");
  await page.advance(0);
  for (rule of ["v2", "historical"]) {
    await page.press([...all(page, "#campaign-detail .rs-files button")].find(b => b.textContent === "View"));
    assert.equal(one(page, "#campaign-detail .rs-viewer pre").textContent, text, rule);
  }
  const {readBytes} = page.window.CarbonTools;
  assert.deepEqual([...readBytes({content_utf8: "é", content_base64: null})], [0xc3, 0xa9]);
  assert.deepEqual([...readBytes({content_base64: "w6k="})], [0xc3, 0xa9]);
  assert.throws(() => readBytes({content_utf8: null, content_base64: null}), /read_file_result_unreadable/);
  clean(page);
});

// ---- 10. The session link (LP-PROD-C D14): read once, kept nowhere. ----
const kept = storage => [...storage.map.values()].join("\n");
scenario("a session link connects once and leaves its token nowhere", async () => {
  const LINK = "link_" + "A1b2-C3d4_".repeat(4);
  const state = launchable(world());
  const session = new Storage(), local = new Storage();
  const page = await openPage(ROOT, state.server, {sessionStorage: session, localStorage: local, hash: "#token=" + LINK});
  page.state = state;
  await page.advance(0);
  assert.equal(page.text("connection-state"), "Connected", "connected by the link alone");
  assert.equal(page.window.location.hash, "", "the fragment is gone from the address");
  assert.deepEqual(page.replaced, ["http://127.0.0.1:8788/"], "this history entry replaced, no other");
  assert.ok(page.requests.length > 3 && page.requests.every(r => r.headers.Authorization === "Bearer " + LINK));
  assert.equal(page.$("token").value, "");
  // Browsing on saves routes, never the token.
  page.go("#campaigns");
  await page.advance(0);
  assert.match(kept(local), /#campaigns/);
  assert.ok(!kept(local).includes(LINK) && !kept(session).includes(LINK));
  // A link opened later in this same tab (the Control Center restarted with
  // a new token) is taken the same way, before the route is read.
  const OTHER = "other_" + "Z9y8-X7w6_".repeat(4);
  const before = page.requests.length;
  page.go("#token=" + OTHER);
  await page.advance(0);
  assert.equal(page.window.location.hash, "");
  assert.equal(page.text("connection-state"), "Connected");
  const after = page.requests.slice(before);
  assert.ok(after.length && after.every(r => r.headers.Authorization === "Bearer " + OTHER));
  assert.ok(!kept(local).includes(OTHER) && !kept(session).includes(OTHER));
  assert.ok(page.replaced.every(address => !address.includes(LINK) && !address.includes(OTHER)));
  clean(page);
});
scenario("an unreadable session link is removed, kept nowhere, and said", async () => {
  const state = launchable(world());
  const local = new Storage();
  const page = await openPage(ROOT, state.server, {localStorage: local, hash: "#token=has%20a%20space"});
  await page.advance(0);
  assert.equal(page.window.location.hash, "");
  assert.notEqual(page.text("connection-state"), "Connected");
  assert.match(page.text("message"), /session link this page cannot read/);
  assert.equal(page.requests.length, 0, "nothing sent with it");
  assert.ok(!kept(local).includes("space"));
  clean(page);
});

// ---- 11. Setup says what an install changed (LP-PROD-E). ----
scenario("setup shows a stale compute check, why, and the installer's update that clears it", async () => {
  const doc = fx.setups.stale;
  const compute = doc.steps.compute;
  const state = launchable(world({setup: copy(doc)}));
  const page = await open(state);
  page.go("#setup/compute");
  await page.advance(0);
  const box = one(page, "#setup-compute-stale");
  assert.match(box.textContent, /no longer matches this install/);
  for (const reason of compute.stale) assert.ok(box.textContent.includes(reason), reason);
  assert.ok(box.textContent.includes("Next: " + compute.next_step + "."));
  // The installer's update is a command the miner runs: ready to copy.
  assert.equal(one(page, "#setup-compute-stale code").textContent, compute.next_step.replace(/^run /, ""));
  // Overview's path says so too.
  page.go("#overview");
  await page.advance(0);
  assert.ok(page.text("getting-started-steps").includes("Next: " + compute.next_step + "."));
  clean(page);
});

scenario("Review shows each Challenge's evaluation and names a set-aside intake again", async () => {
  const doc = fx.setups.set_aside;
  const item = doc.steps.evaluation.challenges[0];
  assert.ok(item.set_aside_intake && item.note, "an intake the update set aside");
  const state = launchable(world({setup: copy(doc)}));
  const page = await open(state);
  page.go("#setup/compute");
  await page.advance(0);
  assert.match(one(page, "#setup-compute-stale").textContent, /An update set your compute check aside/);
  page.go("#setup/review");
  await page.advance(0);
  const row = [...all(page, "#setup-evaluation .evaluation-row")].find(node => node.dataset.challenge === item.id);
  assert.ok(row, "a row for " + item.id);
  assert.ok(row.textContent.includes(item.note));
  assert.ok(row.textContent.includes("set aside by the update: " + item.set_aside_intake));
  await page.press([...row.querySelectorAll("button")].find(b => b.textContent === "Name it again"));
  assert.equal(page.$("setup-review-intake_challenge").value, item.id);
  assert.equal(page.$("setup-review-intake_url").value, item.set_aside_intake);
  clean(page);
});

scenario("Review's answer names what it could not do; Carbon's endpoint shows its receiver, for reference", async () => {
  const state = launchable(world({setup: copy(fx.setups.none)}));
  const page = await open(state);
  page.go("#setup/review");
  await page.advance(0);
  const none = fx.setups.none.steps.evaluation.challenges[0];
  assert.match(page.text("setup-evaluation"), /None yet/);
  assert.ok(page.text("setup-evaluation").includes(none.note));
  const answer = fx.setups.review_answer;
  assert.ok(answer.warnings.length, "the real review warned");
  state.script.push({match: r => r.path === "/api/v1/setup/review", answer: () => { state.setup = copy(fx.setups.none_reviewed); return {body: copy(answer)}; }});
  await page.press([...all(page, "#setup-body form[data-step=review] button")].find(b => /Write my profile/.test(b.textContent)));
  assert.deepEqual(lastPost(state, "/api/v1/setup/review").body, {confirm: true});
  for (const warning of answer.warnings) assert.ok(page.text("setup-result").includes(warning.message), warning.code);
  // Carbon's published endpoint: whose it is, and its receiver for reference.
  const published = fx.setups.published.steps.evaluation.challenges[0];
  assert.equal(published.source, "published");
  const second = launchable(world({setup: copy(fx.setups.published)}));
  const other = await open(second);
  other.go("#setup/review");
  await other.advance(0);
  const text = other.text("setup-evaluation");
  assert.match(text, /Carbon's endpoint/);
  assert.ok(text.includes(published.intake) && text.includes("Receiver hotkey: " + published.receiver_hotkey));
  assert.ok(text.includes("For reference" + published.receiver_hotkey_note.slice("for reference".length)));
  clean(page);
  clean(other);
});

// ---- 12. Graphite and its Library (GRAPHITE-MINER-S5). ----
// The documents are slice S4's: its own where its code is present, else
// built in its shape, field for field (control_center_graphite_fixture.py).
// The Library answers from a scripted store as S4's operations answer: the
// operation listing's closed fields, S4's answer shapes, and S3's plan rule
// (plan.check_shape and validate_plan) for an edited plan. Bans are never
// served; a refused write frees its key; a write's key replays its answer.
const G = () => fx.graphite;
// Every plan document the scripted controller was sent, printed with the
// results, so the Python side checks each against S3's own rule as well.
const PLANS_SENT = [];
const sha256 = text => "sha256:" + crypto.createHash("sha256").update(text).digest("hex");
const NOTICE = {check_status: "UNCHECKED", untrusted: true, rights: "arXiv titles and abstracts are CC0 descriptive metadata; the other fields are Carbon's extraction, not a claim Carbon makes", shown_as: "untrusted text"};
const CARD_FIELDS = ["card_id", "title", "abstract", "technique", "claimed_effect", "data_regime", "cost", "code_available", "applicability", "provenance"];
const PLAN_RULE = {
  fields: "challenge,created_by,hypotheses,parent,pins_considered,schema",
  hypothesis: ["cites", "expected_effect", "hypothesis", "rank", "stopping_rule"],
  origins: ["shared", "miner_hunt", "miner_import"],
  digest: /^sha256:[0-9a-f]{64}$/,
  cardId: /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/,
};
// S3's plan rule: the closed code that refuses `plan`, or null.
function planRule(plan, lib) {
  const object = value => Boolean(value) && typeof value === "object" && !Array.isArray(value);
  const keys = value => Object.keys(value).sort().join(",");
  const textOk = value => typeof value === "string" && value.trim().length >= 1 && value.length <= 2000;
  if (!object(plan) || keys(plan) !== PLAN_RULE.fields || plan.schema !== "carbon.graphite.miner-plan.v1") return "plan_invalid";
  const c = plan.challenge;
  if (!object(c) || keys(c) !== "id,version" || typeof c.id !== "string" || !c.id) return "plan_invalid";
  if (!["planner", "miner"].includes(plan.created_by)) return "plan_invalid";
  if (plan.parent !== null && !(typeof plan.parent === "string" && PLAN_RULE.digest.test(plan.parent))) return "plan_invalid";
  const hypotheses = plan.hypotheses;
  if (!Array.isArray(hypotheses) || hypotheses.length < 1 || hypotheses.length > 8) return "plan_invalid";
  for (const [index, h] of hypotheses.entries()) {
    if (!object(h)) return "plan_invalid";
    const own = Object.keys(h);
    if (!PLAN_RULE.hypothesis.every(name => own.includes(name)) || own.some(name => !PLAN_RULE.hypothesis.includes(name) && name !== "recipe") || h.rank !== index + 1) return "plan_invalid";
    if (![h.hypothesis, h.expected_effect, h.stopping_rule].every(textOk)) return "plan_invalid";
    if (!Array.isArray(h.cites) || h.cites.length > 12) return "plan_invalid";
    for (const cite of h.cites) if (!object(cite) || keys(cite) !== "card_id,origin" || typeof cite.card_id !== "string" || !PLAN_RULE.cardId.test(cite.card_id) || !PLAN_RULE.origins.includes(cite.origin)) return "plan_invalid";
    if ("recipe" in h && (!object(h.recipe) || JSON.stringify(h.recipe).length > 16384)) return "plan_invalid";
  }
  const pins = plan.pins_considered;
  if (!Array.isArray(pins) || pins.length > 64) return "plan_invalid";
  for (const pin of pins) if (!object(pin) || keys(pin) !== "card_id,consideration" || typeof pin.card_id !== "string" || !PLAN_RULE.cardId.test(pin.card_id) || !textOk(pin.consideration)) return "plan_invalid";
  if (new Set(pins.map(pin => pin.card_id)).size !== pins.length) return "plan_invalid";
  for (const h of hypotheses) for (const cite of h.cites) {
    if (lib.bans.includes(cite.card_id)) return "card_banned";
    const card = lib.cards.find(item => item.card_id === cite.card_id);
    if (!card) return "card_not_found";
    if (card.origin !== cite.origin) return "plan_invalid";
  }
  if (lib.pins.some(id => !pins.some(pin => pin.card_id === id))) return "plan_invalid";
  return null;
}
function libraryServer(state) {
  const lib = copy(G().library);
  Object.assign(lib, {imports: [], keys: new Map(), next: 1, leakBans: false});
  state.library = lib;
  const ok = body => ({body});
  const refuse = (status, error, next_step) => ({status, body: next_step ? {error, next_step} : {error}});
  const card = id => lib.cards.find(item => item.card_id === id);
  const curation = () => ({pins: [...lib.pins], bans: [...lib.bans], digest: sha256(JSON.stringify([lib.pins, lib.bans]))});
  const served = (item, ranked = false) => ({
    ...Object.fromEntries(CARD_FIELDS.filter(name => name in item).map(name => [name, item[name]])),
    origin: item.origin, check_status: "UNCHECKED", pinned: lib.pins.includes(item.card_id),
    ...(ranked ? {score: item.score ?? null, reasons: item.reasons || [], plan_input: typeof item.plan_input === "boolean" ? item.plan_input : null, capability_request_candidate: typeof item.capability_request_candidate === "boolean" ? item.capability_request_candidate : null} : {}),
  });
  const entries = () => lib.plans.map(({plan, ...entry}) => entry);
  const curate = operation => body => {
    const id = body.card_id;
    if (operation === "library_pin" && lib.bans.includes(id)) return refuse(409, "card_banned", "You banned this card, so it is not served or pinned. Lift the ban first.");
    if (!card(id) && !lib.bans.includes(id)) return refuse(404, "card_not_found", "Search for it and send an id it returns.");
    const [list, add] = {library_pin: ["pins", true], library_unpin: ["pins", false], library_ban: ["bans", true], library_unban: ["bans", false]}[operation];
    if (add && !lib[list].includes(id)) lib[list].push(id);
    if (!add) lib[list] = lib[list].filter(item => item !== id);
    const after = curation();
    return ok({schema: "carbon.launchpad.library-curation.v1", operation, card_id: id, curation_digest: after.digest, curation: after, applies_to: "Graphite launches from now on; a campaign keeps the curation frozen at its launch"});
  };
  const routes = {
    "library/search": body => {
      const query = typeof body.query === "string" ? body.query.trim() : "";
      if (!query || query.length > 200) return refuse(400, "library_query_invalid");
      const limit = body.card_limit ?? 10;
      if (!Number.isInteger(limit) || limit < 1 || limit > 50) return refuse(400, "card_limit_out_of_bounds");
      const found = lib.cards.filter(item => lib.leakBans || !lib.bans.includes(item.card_id)).filter(item => JSON.stringify([item.title, item.technique]).toLowerCase().includes(query.toLowerCase())).sort((a, b) => b.score - a.score).slice(0, limit);
      return ok({schema: "carbon.launchpad.library-search.v1", query, challenge: {id: body.challenge, version: body.challenge_version}, cards: found.map(item => served(item, true)), curation_digest: curation().digest, ...NOTICE});
    },
    "library/card": body => {
      if (lib.bans.includes(body.card_id)) return refuse(409, "card_banned", "Lift the ban first.");
      const found = card(body.card_id);
      return found ? ok({schema: "carbon.launchpad.library-card.v1", card: served(found), ...NOTICE}) : refuse(404, "card_not_found", "Search for it and send an id it returns.");
    },
    "library/list": () => ok({schema: "carbon.launchpad.library.v1", shared_pack: lib.shared_pack, private_snapshot: lib.private_snapshot, curation: curation(), pending_imports: lib.imports, plans: entries(), where: "your own machine, owner-only; nothing is uploaded", ...NOTICE}),
    "library/pin": curate("library_pin"),
    "library/unpin": curate("library_unpin"),
    "library/ban": curate("library_ban"),
    "library/unban": curate("library_unban"),
    "library/import": body => {
      if (typeof body.title !== "string" || !body.title.trim() || body.title.length > 300 || typeof body.text !== "string" || !body.text.trim() || body.text.length > 20000) return refuse(400, "import_invalid");
      const import_id = "fixture-import-" + lib.next++;
      lib.imports.push({import_id, title: body.title, characters: body.text.length, origin: "miner_import"});
      return ok({schema: "carbon.launchpad.library-import.v1", import_id, queued: true, origin: "miner_import", check_status: "UNCHECKED", read_at: "the next Graphite launch that hunts (RESEARCH or FULL with hunt set)"});
    },
    "plans/list": () => ok({schema: "carbon.launchpad.plans.v1", plans: entries()}),
    "plans/get": body => {
      const found = lib.plans.find(item => item.digest === body.plan);
      return found ? ok({schema: "carbon.launchpad.plan.v1", digest: found.digest, plan: copy(found.plan), untrusted: true, shown_as: "untrusted text"}) : refuse(404, "plan_not_found", "List your plans and send one of their digests.");
    },
    "plans/edit": body => {
      let document = body.plan_document;
      if (typeof document === "string") { try { document = JSON.parse(document); } catch (_) { document = null; } }
      if (!document || typeof document !== "object" || Array.isArray(document)) return refuse(400, "plan_document_required");
      PLANS_SENT.push(copy(document));
      if (document.schema !== "carbon.graphite.miner-plan.v1") return refuse(409, "plan_invalid");
      if (document.parent !== undefined && document.parent !== null && !lib.plans.some(item => item.digest === document.parent)) return refuse(404, "plan_not_found", "List your plans and send one of their digests.");
      const plan = {...document, created_by: "miner"};
      const reason = planRule(plan, lib);
      if (reason) return refuse(409, "plan_invalid", "The plan cites a card that is unknown or banned, or leaves out a pinned card. Correct it and save it. Reason: " + reason + ".");
      const digest = sha256(JSON.stringify(plan) + lib.next++);
      lib.plans.push({digest, created_by: "miner", parent: plan.parent, created_at: 1800000000 + lib.next, plan});
      return ok({schema: "carbon.launchpad.plan-edit.v1", digest, parent: plan.parent, created_by: "miner", launch_with: {agent: "graphite", graphite_mode: "BUILD", plan: digest}});
    },
  };
  // One request, through S4's gates: the closed request (exactly the fields
  // the listing declares), then the replay gate for a keyed write.
  state.libraryAnswer = request => {
    const name = request.path.slice("/api/v1/".length);
    if (!routes[name]) return {status: 404, body: {error: "route_not_found"}};
    const operation = name.startsWith("plans/") ? "plan_" + name.slice("plans/".length) : "library_" + name.slice("library/".length);
    const op = (state.operations || G().operations).find(item => item.operation === operation);
    const body = request.body || {};
    const fields = new Set([...(op?.required || []), ...(op?.optional || [])]);
    if (!op || Object.keys(body).some(key => !fields.has(key)) || op.required.some(key => !(key in body))) return refuse(400, "closed_request_required");
    const {idempotency_key: key, ...rest} = body;
    if (key === undefined) return routes[name](rest);
    const recorded = JSON.stringify([operation, rest]);
    const kept = lib.keys.get(key);
    if (kept) return kept.request === recorded ? kept.answer : refuse(409, "operation_replay_conflict");
    const answer = routes[name](rest);
    // A refused write frees its key; an answer is kept with it.
    if (!(answer.status >= 400)) lib.keys.set(key, {request: recorded, answer});
    return answer;
  };
  state.script.push({keep: true, match: request => /^\/api\/v1\/(library|plans)\//.test(request.path), answer: state.libraryAnswer});
  return lib;
}
// A launchable world whose controller offers Graphite and the Library.
function graphiteWorld(overrides = {}) {
  const state = world({caps: copy(G().caps), options: copy(G().options), operations: copy(G().operations), ...overrides});
  libraryServer(state);
  return launchable(state, "graphite");
}
function graphiteRun(extra = {}) {
  return {...copy(G().run), ...extra};
}
const posts = (state, url) => state.posted.filter(entry => entry.path === url);
async function launchNow(page, state, id = "g".repeat(32)) {
  page.window.CarbonControlCenter.goWizard("launch");
  await page.advance(0);
  assert.equal(page.$("research-launch").disabled, false, "launch is ready: " + page.text("wizard-launch-reason"));
  state.script.push({match: r => r.path === "/api/v1/research" && r.method === "POST", answer: {body: {id}}});
  await page.press(page.$("research-launch"));
  return lastPost(state, "/api/v1/research").body;
}
async function toAgentStep(page) {
  page.window.CarbonControlCenter.goWizard("agent");
  await page.advance(0);
}
const GRAPHITE_KEYS = ["graphite_mode", "research_share", "plan", "hunt", "limits"];
const planHref = digest => "#library/plans/" + encodeURIComponent(digest);
const usd = nano => "$" + String(Number((nano / 1e9).toPrecision(2)));

scenario("Graphite: offered in place of the autonomous agent, which is said to be replaced", async () => {
  const state = graphiteWorld();
  assert.ok(!state.caps.agents.choices.some(choice => choice.launch_agent === "autonomous"), "the controller no longer lists the autonomous agent");
  const page = await open(state);
  await wizardTo(page, "agent", "graphite");
  const offered = [...all(page, "#research-selects input")].map(input => input.value);
  assert.ok(offered.includes("graphite") && !offered.includes("autonomous"), String(offered));
  assert.equal(one(page, "#wizard-graphite").hidden, false, "Graphite's choices show once it is chosen");
  page.go("#agents");
  await page.advance(0);
  assert.match(page.text(one(page, "#agent-catalog [data-agent=replaced]")), /Replaced by Graphite for new campaigns/);
  assert.match(page.text(one(page, "#agent-catalog [data-agent=graphite]")), /Open the Library/);
  // A template saved with the autonomous agent is refused with the reason,
  // though the controller no longer lists that agent at all.
  const local = new Storage();
  local.setItem("carbon.launchpad.launch-templates.v1", JSON.stringify({old: {agent: "autonomous"}}));
  const second = await open(graphiteWorld(), {localStorage: local});
  await wizardTo(second, "limits", "graphite");
  await second.press(second.$("template-load"));
  assert.match(second.text("message"), /not loaded: Carbon's autonomous agent was replaced by Graphite/);
  // A controller between versions that lists both: the autonomous agent is
  // not offered for a new launch.
  const both = graphiteWorld();
  both.caps.agents.choices.push({...copy(both.caps.agents.choices.find(choice => choice.id === "graphite")), id: "autonomous", launch_agent: "autonomous", label: "Carbon's autonomous research agent"});
  const third = await open(both);
  await wizardTo(third, "agent", "graphite");
  assert.ok(![...all(third, "#research-selects input")].some(input => input.value === "autonomous"), "never offered for a new launch");
  // Choosing Manual hides Graphite's choices; a manual launch carries none.
  await toAgentStep(page);
  await page.press(byValue(page, "#research-selects input", "manual"));
  assert.equal(one(page, "#wizard-graphite").hidden, true);
  const body = await launchNow(page, state);
  assert.equal(body.agent, "none");
  for (const key of GRAPHITE_KEYS) assert.ok(!(key in body), "a manual launch carries no " + key);
  // Where Graphite does not run, as each Challenge's setup_offers says: not
  // offered there, before any launch is tried.
  const nowhere = graphiteWorld();
  for (const entry of nowhere.caps.challenges) if (entry.setup_offers) entry.setup_offers.graphite = false;
  const fourth = await open(nowhere);
  fourth.go("#launch");
  await fourth.advance(0);
  await fourth.press(byValue(fourth, "#wizard-challenges input", selectable().challenge_id));
  await fourth.press(fourth.$("wizard-next"));
  assert.equal(byValue(fourth, "#research-selects input", "graphite").disabled, true);
  assert.match(fourth.text("research-selects"), /Not offered for .*graphite not offered for challenge/);
  clean(page); clean(second); clean(third); clean(fourth);
});

scenario("Graphite: each mode launches with exactly its own fields; the hunt is off until asked", async () => {
  const state = graphiteWorld();
  const offer = state.options.graphite;
  assert.ok(offer.hunt.max_records > offer.hunt.default_records, "the controller's bound is not its default");
  const page = await open(state);
  await wizardTo(page, "agent", "graphite");
  // Full is the default, with a 10% research share and no hunt.
  assert.ok(one(page, "#wizard-graphite-mode-full").checked);
  assert.equal(page.$("wizard-research-share").value, "10");
  assert.equal(page.$("wizard-research-share").step, "0.01");
  assert.equal(page.$("wizard-hunt").checked, false, "the hunt is off until the miner turns it on");
  assert.equal(one(page, "#wizard-graphite-plan-box").hidden, true);
  // With no model ceiling, the share limits nothing yet, and says so.
  assert.match(page.text("wizard-research-share-note"), /set no model-spend or model-call ceiling, so this share does not limit research yet/);
  let body = await launchNow(page, state);
  assert.equal(body.agent, "graphite");
  assert.equal(body.graphite_mode, "FULL");
  assert.equal(body.research_share, 0.1);
  for (const key of ["hunt", "plan", "limits"]) assert.ok(!(key in body), "a default launch carries no " + key);
  assert.equal(body.model, G().caps.model.setup_choice.model_id, "Graphite runs on the miner's chosen model");
  // Turned on, the hunt reads the controller's default number of papers.
  await toAgentStep(page);
  await page.press(page.$("wizard-hunt"));
  assert.equal(page.$("wizard-hunt-records").value, String(offer.hunt.default_records));
  body = await launchNow(page, state);
  assert.deepEqual(body.hunt, {max_records: offer.hunt.default_records});
  // A typed share is sent exactly as the fraction it names.
  await toAgentStep(page);
  await page.type(page.$("wizard-research-share"), "12.5");
  page.$("wizard-research-share").blur();
  body = await launchNow(page, state);
  assert.equal(body.research_share, 0.125);
  // Research: the hunt as chosen, no share, no plan.
  await toAgentStep(page);
  await page.press(one(page, "#wizard-graphite-mode-research"));
  assert.equal(one(page, "#wizard-graphite-share").hidden, true);
  body = await launchNow(page, state);
  assert.equal(body.graphite_mode, "RESEARCH");
  assert.deepEqual(body.hunt, {max_records: offer.hunt.default_records});
  assert.ok(!("research_share" in body) && !("plan" in body));
  await toAgentStep(page);
  await page.press(page.$("wizard-hunt"));
  body = await launchNow(page, state);
  assert.ok(!("hunt" in body), "turned off: no hunt");
  // Build: the controller runs no hunt in Build (its options say where a
  // hunt runs), so none is offered or sent, though one was on for Research.
  assert.deepEqual(offer.hunt.modes, ["RESEARCH", "FULL"]);
  await toAgentStep(page);
  await page.press(page.$("wizard-hunt"));
  await page.press(one(page, "#wizard-graphite-mode-build"));
  assert.equal(one(page, "#wizard-graphite-hunt").hidden, true, "Build runs no hunt");
  body = await launchNow(page, state);
  assert.equal(body.graphite_mode, "BUILD");
  for (const key of ["plan", "hunt", "research_share", "limits"]) assert.ok(!(key in body), key);
  // Build from the Library's plan.
  await toAgentStep(page);
  const picker = page.$("wizard-graphite-plan");
  const digest = G().library.plans[0].digest;
  assert.ok([...picker.options].some(option => option.value === digest), "the Library's plan is offered");
  assert.match(page.text("wizard-graphite-plan-note"), /1 plan in your Library/);
  await page.change(picker, digest);
  assert.equal(one(page, "#wizard-graphite-hunt").hidden, true);
  body = await launchNow(page, state);
  assert.equal(body.plan, digest);
  assert.ok(!("hunt" in body), "a Build from a plan never hunts");
  page.window.CarbonControlCenter.goWizard("review");
  await page.advance(0);
  assert.match(page.text("wizard-review"), /Build mode · plan /);
  // Back to Full: the plan chosen for Build stays with Build.
  await toAgentStep(page);
  await page.press(one(page, "#wizard-graphite-mode-full"));
  body = await launchNow(page, state);
  assert.equal(body.graphite_mode, "FULL");
  assert.ok(!("plan" in body), "a Full launch carries no plan: its research writes one");
  // With a model-spend ceiling, the share is said in dollars.
  page.window.CarbonControlCenter.goWizard("limits");
  await page.advance(0);
  await page.press(page.$("path-advanced"));
  const ceiling = page.$("ceiling-provider_nanodollars");
  assert.ok(ceiling, "the model-spend ceiling is offered");
  await page.type(ceiling, "2");
  ceiling.blur();
  await toAgentStep(page);
  assert.match(page.text("wizard-research-share-note"), /% of your model budget: \$[0-9.]+ of your .* model spend\. When that is used, research stops \(research share reached\)/);
  clean(page);
});

scenario("Graphite: a choice the controller's launch does not take blocks the launch, never dropped", async () => {
  const state = graphiteWorld();
  state.operations = state.operations.map(op => op.operation === "launch" ? {...op, optional: op.optional.filter(name => name !== "graphite_mode")} : op);
  const page = await open(state);
  await wizardTo(page, "agent", "graphite");
  await page.press(one(page, "#wizard-graphite-mode-research"));
  assert.equal(page.$("wizard-next").disabled, true, "a Research launch sent without its mode would run as Full");
  assert.match(page.text("wizard-next-reason"), /launch does not take graphite_mode, so these choices cannot be sent\. Next: update Carbon/);
  page.window.CarbonControlCenter.goWizard("launch");
  await page.advance(0);
  assert.equal(page.$("research-launch").disabled, true);
  assert.equal(posts(state, "/api/v1/research").length, 0);
  clean(page);
});

scenario("Graphite: the hunt estimate is Carbon's for the chosen model, else the model's listed price; queries keep to the closed grammar", async () => {
  const state = graphiteWorld({setup: copy(fx.setup_send)});
  // The controller's estimate is for another model: the chosen model's
  // listed price is used, at the controller's Reader tokens per paper.
  const hunt = state.options.graphite.hunt;
  hunt.estimate = {...hunt.estimate, model: "another:model", nanodollars_per_abstract: 1};
  const tokens = hunt.estimate.reader_tokens_per_abstract;
  const page = await open(state);
  await wizardTo(page, "model", "graphite");
  const model = state.caps.model.providers.find(row => row.id === "openai-responses").models[0].id;
  await page.press(byValue(page, "#wizard-model input", "openai-responses/" + model));
  await toAgentStep(page);
  await page.press(page.$("wizard-hunt"));
  const pricing = fx.setup_send.choices.inference.find(choice => choice.id === "openai-responses").models.find(entry => entry.model_id === model).pricing;
  const each = tokens.input * pricing.input + tokens.output * pricing.output_including_reasoning;
  const records = hunt.default_records;
  const estimate = page.text("wizard-hunt-estimate");
  assert.ok(estimate.includes("about " + usd(each * records) + " for up to " + records + " papers"), estimate);
  assert.ok(estimate.includes(usd(each) + " each") && estimate.includes(tokens.input + " input and " + tokens.output + " output tokens a paper"), estimate);
  assert.match(estimate, /skipped before any model call/);
  await page.type(page.$("wizard-hunt-records"), "50");
  assert.ok(page.text("wizard-hunt-estimate").includes(usd(each * 50) + " for up to 50 papers"));
  // Past the controller's own bound: said here, before anything is sent.
  await page.type(page.$("wizard-hunt-records"), String(hunt.max_records + 1));
  assert.equal(page.$("wizard-next").disabled, true);
  assert.match(page.text("wizard-next-reason"), new RegExp("whole number from 1 to " + hunt.max_records));
  await page.type(page.$("wizard-hunt-records"), "50");
  // The closed grammar: refused here before anything is sent.
  const queries = page.$("wizard-hunt-queries");
  for (const [typed, said] of [["neural operator AND surrogate:pde", /characters other than letters/], ["one two three four five six seven", /more than 6 terms/], [Array.from({length: 9}, (_, i) => "query " + i).join("\n"), /at most 8 queries/], ["a" + "b".repeat(40) + " surrogate", /a term longer than 40 characters/]]) {
    await page.type(queries, typed);
    assert.equal(page.$("wizard-next").disabled, true, typed);
    assert.match(page.text("wizard-next-reason"), /hunt query invalid/);
    assert.match(page.text("wizard-next-reason"), said);
  }
  await page.type(queries, "residual MLP surrogate\n  neural   operator  \n\n");
  queries.blur();
  assert.equal(page.$("wizard-next").disabled, false, page.text("wizard-next-reason"));
  const body = await launchNow(page, state);
  assert.deepEqual(body.hunt, {max_records: 50, queries: ["residual MLP surrogate", "neural operator"]});
  // A model with no listed price (setup's choice, priced live): no figure.
  page.window.CarbonControlCenter.goWizard("model");
  await page.advance(0);
  await page.press(byValue(page, "#wizard-model input", G().caps.model.setup_choice.provider_id + "/" + G().caps.model.setup_choice.model_id));
  await toAgentStep(page);
  assert.match(page.text("wizard-hunt-estimate"), /No price is listed here for this model/);
  // The controller's own figure, when it is for the model chosen.
  const second = graphiteWorld({setup: copy(fx.setup_send)});
  second.options.graphite.hunt.estimate = {...second.options.graphite.hunt.estimate, model: "openai-responses:" + model, nanodollars_per_abstract: 123456};
  const other = await open(second);
  await wizardTo(other, "model", "graphite");
  await other.press(byValue(other, "#wizard-model input", "openai-responses/" + model));
  await toAgentStep(other);
  await other.press(other.$("wizard-hunt"));
  const stated = other.text("wizard-hunt-estimate");
  assert.ok(stated.includes("about " + usd(123456 * records) + " for up to " + records + " papers (" + usd(123456) + " each, at Carbon's estimate for " + model + ")"), stated);
  clean(page); clean(other);
});

scenario("Graphite: per-epoch limits are optional; blank sends none, set sends whole numbers", async () => {
  const state = graphiteWorld();
  const page = await open(state);
  await wizardTo(page, "limits", "graphite");
  await page.press(page.$("path-advanced"));
  assert.equal(one(page, "#graphite-limits").hidden, false);
  for (const key of ["calls_per_epoch", "trials_per_epoch", "planner_calls"]) assert.equal(page.$("graphite-limit-" + key).value, "", key);
  assert.match(page.text("graphite-limits"), /only your campaign's own limits bind/);
  await page.type(page.$("graphite-limit-calls_per_epoch"), "0");
  assert.equal(page.$("wizard-next").disabled, true);
  assert.ok(page.text("wizard-next-reason").includes("per-epoch limits: model calls per epoch is a whole number from 1 to " + state.options.graphite.limits.maximum), page.text("wizard-next-reason"));
  assert.equal(page.$("graphite-limit-calls_per_epoch").max, String(state.options.graphite.limits.maximum), "the input's bound is the controller's");
  await page.type(page.$("graphite-limit-calls_per_epoch"), String(state.options.graphite.limits.maximum + 1));
  assert.equal(page.$("wizard-next").disabled, true, "past the controller's own maximum");
  await page.type(page.$("graphite-limit-calls_per_epoch"), "60");
  await page.type(page.$("graphite-limit-planner_calls"), "12");
  page.$("graphite-limit-planner_calls").blur();
  let body = await launchNow(page, state);
  assert.deepEqual(body.limits, {calls_per_epoch: 60, planner_calls: 12});
  page.window.CarbonControlCenter.goWizard("limits");
  await page.advance(0);
  await page.type(page.$("graphite-limit-calls_per_epoch"), "");
  await page.type(page.$("graphite-limit-planner_calls"), "");
  page.$("graphite-limit-planner_calls").blur();
  body = await launchNow(page, state);
  assert.ok(!("limits" in body), "blank: only the campaign's own limits bind");
  clean(page);
});

scenario("Graphite: a template carries its choices, as launch fields, and loads them back", async () => {
  const state = graphiteWorld();
  const page = await open(state);
  await wizardTo(page, "agent", "graphite");
  await page.press(one(page, "#wizard-graphite-mode-research"));
  await page.press(page.$("wizard-hunt"));
  await page.type(page.$("wizard-hunt-records"), "40");
  page.$("wizard-hunt-records").blur();
  page.window.CarbonControlCenter.goWizard("limits");
  await page.advance(0);
  await page.type(page.$("template-name"), "research forty");
  await page.press(page.$("template-save"));
  const saved = JSON.parse(page.window.localStorage.getItem("carbon.launchpad.launch-templates.v1"))["research forty"];
  assert.deepEqual(saved, {agent: "graphite", graphite_mode: "RESEARCH", hunt: {max_records: 40}});
  await toAgentStep(page);
  await page.press(one(page, "#wizard-graphite-mode-build"));
  page.window.CarbonControlCenter.goWizard("limits");
  await page.advance(0);
  await page.press(page.$("template-load"));
  assert.match(page.text("message"), /loaded/);
  const body = await launchNow(page, state);
  assert.equal(body.graphite_mode, "RESEARCH");
  assert.deepEqual(body.hunt, {max_records: 40});
  clean(page);
});

scenario("Graphite: the campaign shows its stage, plan, research and build spend, the hunt, and an ended campaign as ended", async () => {
  const state = graphiteWorld();
  const run = graphiteRun();
  state.runs = [run];
  state.view = copy(G().view);
  const page = await open(state);
  page.go("#campaigns");
  await page.advance(0);
  assert.match(page.text(one(page, "#research-runs a.campaign-card")), /Graphite · Full mode · Building/);
  page.go("#campaigns/" + run.id + "/live");
  await page.advance(0);
  await refresh(page);
  const box = () => one(page, "#campaign-detail [data-part=graphite]");
  assert.equal(box().hidden, false);
  const text = page.text(box());
  const g = state.view.graphite, spend = state.view.tiles.spend;
  const research = g.research_spent.provider_nanodollars;
  assert.match(text, /Graphite · Full mode/);
  assert.match(text, /Now: Building/);
  // Each stage with its state; the Planner stopped at the research share.
  assert.ok(text.includes("StagesHunt: done · Plan: stopped (research share reached) · Build: running"), text);
  // The cap the share sets, as the campaign states it.
  assert.equal(g.research_cap.provider_nanodollars, Math.floor(spend.ceiling_nanodollars * 0.1));
  assert.ok(text.includes("Research spend" + usd(research) + " · its share 10% (up to " + usd(g.research_cap.provider_nanodollars) + " of your " + usd(spend.ceiling_nanodollars) + ")"), text);
  assert.ok(text.includes("Build spend" + usd(spend.used_nanodollars - research)), text);
  assert.ok(text.includes("Research model calls" + g.research_spent.provider_attempts), text);
  assert.ok(text.includes("2 found on arXiv · 1 already known, not paid for again · 0 set aside at first reading · 1 read into your Library · 2 Reader calls · cost " + usd(g.hunt.cost_nanodollars)), text);
  assert.ok(!text.includes("literature fetch failed"), "arXiv answered");
  // The plan, read from the Library by its digest: its first hypotheses.
  const plan = G().library.plans[0].plan;
  assert.ok(text.includes(plan.hypotheses[0].hypothesis) && text.includes(plan.hypotheses[2].hypothesis), text);
  assert.ok(!text.includes(plan.hypotheses[3].hypothesis), "three shown, the rest in the Library");
  assert.match(text, /1 more in the Library/);
  assert.equal(one(page, "#campaign-detail [data-part=graphite] a.link").getAttribute("href"), planHref(g.plan_digest));
  // arXiv unreachable (the hunt report's FAILED_INFRA, counted 0 or 1 by
  // the view): said, with its next step, and never as a verdict on a paper.
  state.view = copy(G().view);
  state.view.graphite.hunt.failed_infra = 1;
  for (let i = 0; i < 3; i++) await refresh(page);
  assert.match(page.text(box()), /Could not be reached, so the hunt ended where it was \(literature fetch failed\)\. That is not a verdict on any paper.*Next: hunt again in a later campaign\./);
  // Ended: the campaign says so, with the stage it ended in.
  run.state = "COMPLETED";
  state.view.campaign.state = "COMPLETED";
  for (let i = 0; i < 3; i++) await refresh(page);
  assert.match(page.text(box()), /Now: Done \(last stage: building\)/);
  page.go("#campaigns");
  await page.advance(0);
  assert.match(page.text(one(page, "#research-runs a.campaign-card")), /Graphite · Full mode · Done \(last stage: building\)/);
  // Finished as Graphite says it (its stage `complete`): done, no more.
  page.go("#campaigns/" + run.id + "/live");
  await page.advance(0);
  state.view = copy(state.view);
  state.view.graphite.stage = "complete";
  for (let i = 0; i < 3; i++) await refresh(page);
  assert.match(page.text(box()), /Now: Done(?! \()/);
  // A campaign without Graphite: the part is there, hidden, and empty.
  page.go("#campaigns/" + run.id + "/live");
  await page.advance(0);
  const plain = copy(G().view);
  plain.graphite = null;
  state.view = plain;
  for (let i = 0; i < 3; i++) await refresh(page);
  assert.equal(one(page, "#campaign-detail [data-part=graphite]").hidden, true);
  clean(page);
});

scenario("Library: every card says where it came from and UNCHECKED; search ranks with reasons", async () => {
  const state = graphiteWorld();
  const page = await open(state);
  page.go("#library");
  await page.advance(0);
  assert.match(page.text("library-body"), /Your pins and bans/);
  await page.type(page.$("library-query"), "mlp");
  await page.press(page.$("library-search-go"));
  const sent = lastPost(state, "/api/v1/library/search").body;
  const chosen = selectable();
  assert.deepEqual(sent, {query: "mlp", challenge: chosen.challenge_id, challenge_version: chosen.version, card_limit: 20});
  const cards = [...all(page, "#library-body [data-part=results] .lib-card")];
  const expected = G().library.cards.filter(card => /mlp/i.test(card.title + card.technique) && !G().library.bans.includes(card.card_id));
  assert.deepEqual(cards.map(node => node.dataset.card).sort(), expected.map(card => card.card_id).sort());
  for (const node of cards) {
    const card = expected.find(item => item.card_id === node.dataset.card);
    assert.equal(one(page, "#library-body [data-part=results] [data-card=" + card.card_id + "] [data-origin]").dataset.origin, card.origin);
    assert.ok(node.textContent.includes({shared: "Shared pack", miner_hunt: "Your hunt", miner_import: "Your import"}[card.origin]), card.card_id);
    assert.equal(node.querySelector("[data-check]").textContent, "UNCHECKED");
    assert.ok(node.textContent.includes("Relevance " + card.score + " of 3"));
    for (const reason of card.reasons) assert.ok(node.textContent.includes(reason), reason);
  }
  // Buildable under the Challenge's contract, as the ranking flags it.
  assert.equal(one(page, "#library-body [data-part=results] [data-card=fixture-shared-0001] [data-buildable]").dataset.buildable, "yes");
  // The banned card is never shown, here or in the results.
  assert.ok(!page.text(one(page, "#library-body [data-part=results]")).includes("banned MLP variant"));
  // Even when a controller serves one by mistake.
  state.library.leakBans = true;
  await page.press(page.$("library-search-go"));
  assert.ok(!page.text(one(page, "#library-body [data-part=results]")).includes("banned MLP variant"), "a banned card is never shown in results");
  state.library.leakBans = false;
  // Not buildable under the contract: a capability request candidate.
  await page.type(page.$("library-query"), "graph");
  await page.press(page.$("library-search-go"));
  const graph = one(page, "#library-body [data-part=results] [data-card=fixture-shared-0002]");
  assert.equal(graph.querySelector("[data-buildable]").dataset.buildable, "no");
  assert.match(graph.textContent, /Not buildable here: a capability request candidate/);
  // Your library: the shared pack, the private snapshot, imports waiting and
  // plans, as the controller states them; no count it did not give.
  const mine = () => page.text(one(page, "#library-body [data-part=mine]"));
  assert.match(mine(), /Shared pack: 1773 cards/);
  assert.match(mine(), /Search above finds them beside the shared pack/);
  assert.match(mine(), /1 plan in your library/);
  assert.ok(!/\b0 so far\b/.test(mine()), mine());
  // A shared pack that is missing is said, with its next step.
  state.library.shared_pack = {available: false, code: "literature_pack_missing"};
  for (let i = 0; i < 9; i++) await refresh(page);
  assert.match(mine(), /\(literature pack missing\)\. Next: re-run the installer with --update/);
  clean(page);
});

scenario("Library: pin and ban are the controller's operations, under a key, and steer what is shown", async () => {
  const state = graphiteWorld();
  const page = await open(state);
  page.go("#library");
  await page.advance(0);
  await page.type(page.$("library-query"), "mlp");
  await page.press(page.$("library-search-go"));
  const button = (id, action) => one(page, "#library-body [data-part=results] [data-card=" + id + "] button[data-curate=" + action + "]");
  const held = () => JSON.parse(page.window.sessionStorage.getItem("carbon.launchpad.pending-operation.v1") || "{}");
  // Already pinned: says so.
  assert.equal(button("fixture-shared-0001", "pin").getAttribute("aria-pressed"), "true");
  await page.press(button("fixture-hunt-0001", "pin"));
  const pin = lastPost(state, "/api/v1/library/pin");
  assert.deepEqual(Object.keys(pin.body).sort(), ["card_id", "idempotency_key"]);
  assert.equal(pin.body.card_id, "fixture-hunt-0001");
  assert.match(pin.body.idempotency_key, /^[0-9a-f-]{36}$/);
  assert.equal(button("fixture-hunt-0001", "pin").getAttribute("aria-pressed"), "true");
  assert.match(page.text(one(page, "#library-body [data-part=curation] [data-list=pin]")), /MLP width schedule/);
  // Ban: gone from the results, listed with Unban.
  await page.press(button("fixture-import-0001", "ban"));
  assert.equal(lastPost(state, "/api/v1/library/ban").body.card_id, "fixture-import-0001");
  assert.equal(all(page, "#library-body [data-part=results] [data-card=fixture-import-0001]").length, 0);
  const banned = one(page, "#library-body [data-part=curation] [data-list=ban]");
  assert.match(page.text(banned), /imported notes on MLP depth/);
  await page.press([...banned.querySelectorAll("button")].find(b => b.textContent === "Unban" && b.dataset.card === "fixture-import-0001"));
  assert.equal(lastPost(state, "/api/v1/library/unban").body.card_id, "fixture-import-0001");
  assert.ok(one(page, "#library-body [data-part=results] [data-card=fixture-import-0001]"));
  // A lost answer to a request that never arrived: the retry is the same
  // request under the same key, never a second one.
  state.script.unshift({match: r => r.path === "/api/v1/library/unpin", answer: {timeout: true}});
  await page.press(button("fixture-hunt-0001", "pin"));
  const lost = lastPost(state, "/api/v1/library/unpin").body.idempotency_key;
  assert.match(page.text("library-note"), /Not confirmed: .*same key/);
  assert.ok(state.library.pins.includes("fixture-hunt-0001"), "the lost request never arrived");
  await page.press(button("fixture-hunt-0001", "pin"));
  assert.equal(lastPost(state, "/api/v1/library/unpin").body.idempotency_key, lost, "the retry is replayed, never repeated");
  assert.equal(button("fixture-hunt-0001", "pin").getAttribute("aria-pressed"), "false");
  // A lost answer to a request that was done: once the library shows its
  // effect, its key is let go, so pinning again later is a new request
  // (never a replay of the first answer, which would pin nothing).
  state.script.unshift({match: r => r.path === "/api/v1/library/pin", answer: request => { state.libraryAnswer(request); return {timeout: true}; }});
  await page.press(button("fixture-hunt-0001", "pin"));
  const first = lastPost(state, "/api/v1/library/pin").body.idempotency_key;
  assert.ok(state.library.pins.includes("fixture-hunt-0001"), "the controller pinned it");
  assert.ok(held()["library_pin:fixture-hunt-0001"], "held while its outcome is unknown");
  for (let i = 0; i < 9; i++) await refresh(page);
  assert.equal(button("fixture-hunt-0001", "pin").getAttribute("aria-pressed"), "true");
  assert.ok(!held()["library_pin:fixture-hunt-0001"], "the library shows it pinned: its key is let go");
  await page.press(button("fixture-hunt-0001", "pin"));
  assert.ok(!state.library.pins.includes("fixture-hunt-0001"), "unpinned");
  await page.press(button("fixture-hunt-0001", "pin"));
  assert.notEqual(lastPost(state, "/api/v1/library/pin").body.idempotency_key, first, "a new request, under a new key");
  assert.ok(state.library.pins.includes("fixture-hunt-0001"), "pinned again");
  // A refusal is shown with the controller's next step, and lets the key go:
  // a card banned from another door since this page last read the library.
  state.library.bans.push("fixture-import-0001");
  await page.press(button("fixture-import-0001", "pin"));
  assert.match(page.text("library-note"), /Refused: card banned\. Next: You banned this card, so it is not served or pinned\. Lift the ban first\./);
  assert.ok(!state.library.pins.includes("fixture-import-0001"), "a refused pin pins nothing");
  assert.equal(page.window.sessionStorage.getItem("carbon.launchpad.pending-operation.v1"), "{}");
  clean(page);
});

scenario("Library: a route the controller does not have falls back to the operations door", async () => {
  const state = graphiteWorld();
  state.script.unshift({keep: true, match: r => r.path === "/api/v1/library/search", answer: {status: 404, body: {error: "route_not_found"}}});
  state.script.unshift({keep: true, match: r => r.path === "/api/v1/operations/library_search", answer: {body: {cards: [{...G().library.cards[0], check_status: "UNCHECKED", pinned: true}]}}});
  const page = await open(state);
  page.go("#library");
  await page.advance(0);
  await page.type(page.$("library-query"), "anything");
  await page.press(page.$("library-search-go"));
  assert.equal(lastPost(state, "/api/v1/operations/library_search").body.query, "anything");
  assert.ok(one(page, "#library-body [data-part=results] [data-card=fixture-shared-0001]"));
  // A refusal on the route itself is never retried elsewhere.
  state.script.unshift({match: r => r.path === "/api/v1/library/card", answer: {status: 404, body: {error: "card_not_found"}}});
  page.go("#library/card/nope");
  await page.advance(0);
  assert.equal(posts(state, "/api/v1/operations/library_card").length, 0);
  assert.match(page.text(one(page, "#library-body [data-part=card]")), /could not be read: card not found/);
  clean(page);
});

scenario("Library: an import queues text for the next launch that hunts", async () => {
  const state = graphiteWorld();
  const page = await open(state);
  page.go("#library/import");
  await page.advance(0);
  // Nothing to import: said here, nothing sent.
  await page.press(page.$("library-import-go"));
  assert.match(page.text("library-import-result"), /Write a title and the text/);
  assert.equal(posts(state, "/api/v1/library/import").length, 0);
  // Longer than an import carries: said here, nothing sent.
  await page.type(page.$("library-import-title"), "Too long");
  await page.type(page.$("library-import-text"), "x".repeat(20001));
  await page.press(page.$("library-import-go"));
  assert.match(page.text("library-import-result"), /at most 20,000 characters; this is 20,001/);
  assert.equal(posts(state, "/api/v1/library/import").length, 0);
  const notes = "Residual connections helped when the data was small.";
  await page.type(page.$("library-import-title"), "My notes on residual MLPs");
  await page.type(page.$("library-import-text"), notes);
  assert.equal(page.text("library-import-count"), notes.length + " / 20,000 characters");
  await page.press(page.$("library-import-go"));
  const sent = lastPost(state, "/api/v1/library/import").body;
  assert.deepEqual(Object.keys(sent).sort(), ["idempotency_key", "text", "title"]);
  assert.equal(sent.title, "My notes on residual MLPs");
  assert.equal(sent.text, notes);
  assert.match(page.text("library-import-result"), /Queued as fixture-import-1: “My notes on residual MLPs”/);
  assert.equal(page.$("library-import-title").value, "");
  assert.equal(page.$("library-import-text").value, "");
  assert.match(page.text(one(page, "#library-body [data-part=pending]")), new RegExp("My notes on residual MLPs · fixture-import-1 · " + notes.length + " characters"));
  clean(page);
});

scenario("Library: the plan editor checks a plan against Graphite's rule, then saves it as a new version", async () => {
  const state = graphiteWorld();
  const page = await open(state);
  const first = G().library.plans[0];
  const chosen = selectable();
  page.go(planHref(first.digest));
  await page.advance(0);
  await refresh(page);
  const view = () => page.text(one(page, "#library-body [data-part=plan]"));
  assert.match(view(), /Written byGraphite's Planner/);
  assert.ok(view().includes("For" + chosen.title + " · v" + chosen.version), view());
  assert.ok(view().includes(first.plan.pins_considered[0].consideration), "how the Planner considered the pin");
  assert.ok(view().includes(first.plan.hypotheses[0].hypothesis));
  assert.ok(view().includes("Stops when: " + first.plan.hypotheses[0].stopping_rule));
  // Each cited card links to it and says where it came from.
  const cites = one(page, "#library-body [data-part=plan] .lib-cites");
  assert.deepEqual([...cites.querySelectorAll("[data-origin]")].map(node => node.dataset.origin), ["miner_hunt", "shared"]);
  assert.equal(cites.querySelector("a").getAttribute("href"), "#library/card/fixture-hunt-0001");
  await page.press(page.$("library-plan-edit"));
  assert.equal(page.$("library-plan-hypothesis-0").value, first.plan.hypotheses[0].hypothesis);
  assert.equal(page.$("library-plan-consider-0").value, first.plan.pins_considered[0].consideration, "the Planner's line for the pin is kept");
  await page.type(page.$("library-plan-hypothesis-0"), "A wider and deeper residual MLP lowers the practice error.");
  const save = () => page.press(page.$("library-plan-save"));
  const said = () => page.text("library-plan-result");
  // A pinned card the plan does not consider is refused here, before
  // anything is sent.
  await page.type(page.$("library-plan-consider-0"), "   ");
  await save();
  assert.match(said(), /say how the plan considers every pinned card: Fixture card: residual MLP surrogate .* \(plan invalid\)/);
  await page.type(page.$("library-plan-consider-0"), "Kept: the wider MLP builds on it.");
  // Citing a banned card, or something that is not a card id, is refused here too.
  await page.type(page.$("library-plan-cites-1"), "fixture-shared-0001\nfixture-shared-0003");
  await save();
  // (A banned card is never served, so it is named by its id.)
  assert.match(said(), /hypothesis 2 cites fixture-shared-0003, which you banned \(card banned\)/);
  await page.type(page.$("library-plan-cites-1"), "fixture-shared-0001, bad!id");
  await save();
  assert.match(said(), /hypothesis 2: “bad!id” is not a card id/);
  // A card that is in neither the pack nor the library is read first, and refused.
  await page.type(page.$("library-plan-cites-1"), "fixture-shared-0001, nowhere-0001");
  await save();
  assert.match(said(), /cites nowhere-0001, which is in neither the shared pack nor your library \(card not found\)/);
  // A recipe that is not a JSON object, and text longer than the rule takes.
  await page.type(page.$("library-plan-cites-1"), "fixture-shared-0001");
  await page.type(page.$("library-plan-recipe-1"), "[1, 2]");
  await page.type(page.$("library-plan-stopping_rule-2"), "x".repeat(2001));
  await save();
  assert.match(said(), /hypothesis 2: the recipe is a JSON object/);
  assert.match(said(), /hypothesis 3: its stopping rule is at most 2000 characters/);
  assert.equal(posts(state, "/api/v1/plans/edit").length, 0, "nothing was sent while the plan was refused here");
  await page.type(page.$("library-plan-recipe-1"), "");
  await page.type(page.$("library-plan-stopping_rule-2"), first.plan.hypotheses[2].stopping_rule);
  // Reorder: the third hypothesis first. Typed text survives the redraw.
  await page.press([...one(page, "#library-body [data-part=editor] [data-row='2']").querySelectorAll("button")].find(b => b.textContent === "Move up"));
  assert.equal(page.$("library-plan-hypothesis-0").value, "A wider and deeper residual MLP lowers the practice error.");
  assert.equal(page.$("library-plan-hypothesis-1").value, first.plan.hypotheses[2].hypothesis);
  await save();
  const sent = lastPost(state, "/api/v1/plans/edit").body;
  assert.deepEqual(Object.keys(sent).sort(), ["idempotency_key", "plan_document"]);
  const plan = sent.plan_document;
  // Graphite's plan in its closed shape: exactly these fields.
  assert.deepEqual(Object.keys(plan).sort(), ["challenge", "created_by", "hypotheses", "parent", "pins_considered", "schema"]);
  assert.equal(plan.schema, "carbon.graphite.miner-plan.v1");
  assert.deepEqual(plan.challenge, first.plan.challenge);
  assert.equal(plan.parent, first.digest);
  assert.equal(plan.created_by, "miner");
  assert.deepEqual(plan.pins_considered, [{card_id: "fixture-shared-0001", consideration: "Kept: the wider MLP builds on it."}]);
  assert.deepEqual(plan.hypotheses.map(h => h.rank), [1, 2, 3, 4], "ranked by place, after the move");
  for (const h of plan.hypotheses) assert.ok(Object.keys(h).every(name => ["rank", "hypothesis", "expected_effect", "stopping_rule", "cites", "recipe"].includes(name)), Object.keys(h).join());
  assert.equal(plan.hypotheses[0].hypothesis, "A wider and deeper residual MLP lowers the practice error.");
  assert.deepEqual(plan.hypotheses[0].recipe, first.plan.hypotheses[0].recipe);
  assert.deepEqual(plan.hypotheses[0].cites, first.plan.hypotheses[0].cites);
  assert.equal(plan.hypotheses[1].hypothesis, first.plan.hypotheses[2].hypothesis);
  assert.deepEqual(plan.hypotheses[2].cites, [{card_id: "fixture-shared-0001", origin: "shared"}]);
  assert.ok(!("recipe" in plan.hypotheses[2]));
  // Graphite's rule took it: the new version opens, read back as stored.
  const created = state.library.plans[state.library.plans.length - 1];
  assert.equal(created.parent, first.digest, "saved by the controller");
  assert.equal(page.window.location.hash, planHref(created.digest));
  await refresh(page);
  assert.match(view(), /Written byYour edit/);
  assert.equal(all(page, "#library-body [data-part=list] tr[data-plan]").length, 2);
  assert.match(page.text("library-note"), /Saved as a new version/);
  // The controller's own refusal, with the rule's reason and its next step:
  // a card pinned from another door since, which this edit leaves out.
  await page.press(page.$("library-plan-edit"));
  state.library.pins.push("fixture-hunt-0001");
  await save();
  assert.match(said(), /Refused: plan invalid\. Next: .*Reason: plan_invalid\./);
  clean(page);
});

scenario("Library: a plan written from scratch names its Challenge and has no parent", async () => {
  const state = graphiteWorld();
  const page = await open(state);
  page.go("#library/plans");
  await page.advance(0);
  // Cancel lets a new plan go and leaves its page.
  await page.press(page.$("library-plan-new"));
  assert.equal(one(page, "#library-body [data-part=editor]").hidden, false);
  await page.press(page.$("library-plan-cancel"));
  assert.equal(page.window.location.hash, "#library/plans");
  assert.equal(one(page, "#library-body [data-part=editor]").hidden, true);
  await page.press(page.$("library-plan-new"));
  const chosen = selectable();
  assert.equal(page.$("library-plan-challenge").value, JSON.stringify({id: chosen.challenge_id, version: chosen.version}), "the Library's Challenge, to start with");
  await page.type(page.$("library-plan-hypothesis-0"), "Mine: a smaller MLP keeps the score.");
  await page.type(page.$("library-plan-expected_effect-0"), "the same score");
  await page.type(page.$("library-plan-stopping_rule-0"), "one practice run");
  const typed = page.$("library-plan-stopping_rule-0");
  await page.type(page.$("library-plan-consider-0"), "Mine starts from it.");
  // A card pinned meanwhile (from another door) gets its own line, once the
  // line in hand is let go; the hypothesis being written is never redrawn.
  state.library.pins.push("fixture-hunt-0001");
  for (let i = 0; i < 8; i++) await refresh(page);
  assert.equal(all(page, "#library-plan-consider-1").length, 0, "not redrawn under a focused line");
  page.$("library-plan-consider-0").blur();
  await refresh(page);
  assert.ok(typed.isConnected, "the hypothesis fields were not redrawn for a pin");
  assert.equal(page.$("library-plan-hypothesis-0").value, "Mine: a smaller MLP keeps the score.");
  assert.equal(page.$("library-plan-consider-0").value, "Mine starts from it.", "the line written before is kept");
  assert.match(page.text(one(page, "#library-body [data-part=considered]")), /MLP width schedule from a hunt · pinned/);
  await page.press(page.$("library-plan-save"));
  assert.match(page.text("library-plan-result"), /say how the plan considers every pinned card: Fixture card: MLP width schedule from a hunt \(plan invalid\)/);
  await page.type(page.$("library-plan-consider-1"), "Its widening schedule is the second idea.");
  await page.press(page.$("library-plan-save"));
  const plan = lastPost(state, "/api/v1/plans/edit").body.plan_document;
  assert.deepEqual(plan, {
    schema: "carbon.graphite.miner-plan.v1",
    challenge: {id: chosen.challenge_id, version: chosen.version},
    hypotheses: [{rank: 1, hypothesis: "Mine: a smaller MLP keeps the score.", expected_effect: "the same score", stopping_rule: "one practice run", cites: []}],
    pins_considered: [{card_id: "fixture-shared-0001", consideration: "Mine starts from it."}, {card_id: "fixture-hunt-0001", consideration: "Its widening schedule is the second idea."}],
    parent: null,
    created_by: "miner",
  });
  assert.equal(state.library.plans.length, 2, "Graphite's rule took it");
  clean(page);
});

scenario("Library: a draft is kept when another plan is opened or a new one started", async () => {
  const state = graphiteWorld();
  const page = await open(state);
  const first = G().library.plans[0];
  page.go(planHref(first.digest));
  await page.advance(0);
  await refresh(page);
  await page.press(page.$("library-plan-edit"));
  await page.type(page.$("library-plan-hypothesis-0"), "Half-edited hypothesis.");
  page.$("library-plan-hypothesis-0").blur();
  await page.press(page.$("library-plan-new"));
  await page.advance(0);
  assert.equal(page.$("library-plan-hypothesis-0").value, "", "a new plan starts empty");
  await page.type(page.$("library-plan-hypothesis-0"), "A new idea.");
  page.$("library-plan-hypothesis-0").blur();
  page.go(planHref(first.digest));
  await page.advance(0);
  assert.equal(page.$("library-plan-hypothesis-0").value, "Half-edited hypothesis.", "the edit is kept");
  assert.match(page.text(one(page, "#library-body [data-part=list]")), /editing/);
  page.go("#library/plans/new");
  await page.advance(0);
  assert.equal(page.$("library-plan-hypothesis-0").value, "A new idea.", "the new plan is kept too");
  clean(page);
});

scenario("Graphite and the Library: a refresh with nothing new changes nothing; typing survives new data", async () => {
  const state = graphiteWorld();
  const run = graphiteRun({state: "COMPLETED"});
  const view = copy(G().view);
  view.campaign.state = "COMPLETED";
  view.tiles.elapsed_seconds = null;
  state.runs = [run];
  state.view = view;
  const page = await open(state);
  const still = async label => {
    for (let i = 0; i < 2; i++) await refresh(page);
    const before = page.doc.mutations;
    page.doc.trace = [];
    // Past the Library's own re-read, and the campaign view's.
    for (let i = 0; i < 9; i++) await refresh(page);
    assert.equal(page.doc.mutations, before, label + ": " + [...new Set(page.doc.trace)].join(" | "));
  };
  await wizardTo(page, "agent", "graphite");
  await page.press(one(page, "#wizard-graphite-mode-research"));
  await page.press(page.$("wizard-hunt"));
  await still("the wizard's Graphite choices");
  await page.press(one(page, "#wizard-graphite-mode-build"));
  await still("the wizard's Graphite choices, in Build");
  page.window.CarbonControlCenter.goWizard("review");
  await page.advance(0);
  await still("the review");
  page.go("#library");
  await page.advance(0);
  await page.type(page.$("library-query"), "mlp");
  await page.press(page.$("library-search-go"));
  page.$("library-query").blur();
  await still("the Library's cards");
  page.go(planHref(G().library.plans[0].digest));
  await page.advance(0);
  await still("a plan");
  await page.press(page.$("library-plan-edit"));
  await still("the plan editor");
  page.go("#campaigns/" + run.id + "/live");
  await page.advance(0);
  await still("the campaign's Graphite part");
  // Typing in the Library survives a re-read that brings something new.
  page.go("#library/import");
  await page.advance(0);
  const text = page.$("library-import-text");
  await page.type(text, "Half-written notes");
  page.go("#library");
  await page.advance(0);
  const query = page.$("library-query");
  await page.type(query, "graph");
  state.library.imports.push({import_id: "fixture-import-9", title: "Queued from another door", characters: 12, origin: "miner_import"});
  for (let i = 0; i < 9; i++) await refresh(page);
  assert.ok(query.isConnected && query.value === "graph", "the query being typed is untouched");
  assert.match(page.text(one(page, "#library-body [data-part=mine]")), /1 import waiting for a launch that hunts/);
  page.go("#library/import");
  await page.advance(0);
  assert.ok(text.isConnected && text.value === "Half-written notes", "an import being written is untouched");
  assert.match(page.text(one(page, "#library-body [data-part=pending]")), /Queued from another door/);
  clean(page);
});

scenario("Library: opened before connecting, it says to connect", async () => {
  const state = graphiteWorld();
  const page = await openPage(ROOT, state.server, {hash: "#library"});
  await page.advance(0);
  assert.equal(page.$("library").hidden, false);
  assert.equal(page.text("library-body"), "Connect this browser to read your library.");
  assert.equal(page.requests.length, 0, "nothing is asked before connecting");
  clean(page);
});

scenario("Library: a controller without it says so, and nothing is asked of it", async () => {
  const state = graphiteWorld({operations: copy(G().operations_without_library)});
  const page = await open(state);
  page.go("#library");
  await page.advance(0);
  assert.match(page.text("library-body"), /does not offer the Library: it predates Graphite's miner edition/);
  await wizardTo(page, "agent", "graphite");
  await page.press(one(page, "#wizard-graphite-mode-build"));
  assert.match(page.text("wizard-graphite-plan-note"), /does not list plans/);
  assert.equal(page.requests.filter(r => /^\/api\/v1\/(library|plans)\//.test(r.path)).length, 0);
  clean(page);
});

scenario("Library: a session link opened on a Library address connects and keeps its token nowhere", async () => {
  const LINK = "link_" + "L1b2-R3d4_".repeat(4);
  const state = graphiteWorld();
  const session = new Storage(), local = new Storage();
  const page = await openPage(ROOT, state.server, {sessionStorage: session, localStorage: local, hash: "#token=" + LINK});
  page.state = state;
  await page.advance(0);
  assert.equal(page.text("connection-state"), "Connected");
  assert.equal(page.window.location.hash, "");
  page.go(planHref(G().library.plans[0].digest));
  await page.advance(0);
  await refresh(page);
  assert.match(page.text(one(page, "#library-body [data-part=plan]")), /Written by/);
  assert.match(kept(local), /#library\/plans\//);
  assert.ok(!kept(local).includes(LINK) && !kept(session).includes(LINK));
  assert.ok(page.requests.every(r => r.headers.Authorization === "Bearer " + LINK));
  for (const r of page.requests) assert.ok(!JSON.stringify(r.body || {}).includes(LINK) && !r.path.includes(LINK));
  clean(page);
});

(async () => {
  const passed = [], failed = [];
  for (const [name, run] of scenarios) {
    if (ONLY && !name.includes(ONLY)) continue;
    try { await run(); passed.push(name); }
    catch (error) { failed.push(name + ": " + String(error && error.message || error).split("\n")[0]); if (!process.argv[3]) { error.message = name + ": " + error.message; throw error; } }
  }
  process.stdout.write(JSON.stringify({passed, failed, plans_sent: PLANS_SENT}));
})().catch(error => { process.stderr.write(String(error && error.stack || error) + "\n"); process.exit(1); });
