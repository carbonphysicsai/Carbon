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
// The documents are the real ones with Graphite's part added in the shape
// the cross-slice interface states (control_center_graphite_fixture.py).
// The Library answers from a scripted store over the fixture cards and
// plans: what the controller's operations answer, as the interface states
// it. Bans are never served; a plan citing a banned card or ignoring a pin
// is refused; a write's key replays its first answer.
const G = () => fx.graphite;
function libraryServer(state) {
  const lib = copy(G().library);
  Object.assign(lib, {imports: [], keys: new Map(), next: 1, leakBans: false});
  state.library = lib;
  const ok = body => ({body});
  const refuse = (status, error, next_step) => ({status, body: {error, next_step}});
  const card = id => lib.cards.find(item => item.card_id === id);
  const curation = () => ({curation: {pins: [...lib.pins], bans: [...lib.bans], digest: "fixture-curation-" + lib.pins.join(",") + "|" + lib.bans.join(",")}});
  const served = () => lib.cards.filter(item => lib.leakBans || !lib.bans.includes(item.card_id));
  const curate = (list, add) => body => {
    if (!card(body.card_id)) return refuse(409, "card_not_found", "search the Library for the card's id");
    const ids = lib[list];
    if (add && !ids.includes(body.card_id)) ids.push(body.card_id);
    if (!add) lib[list] = ids.filter(id => id !== body.card_id);
    return ok(curation());
  };
  const routes = {
    "library/search": body => ok({results: served().filter(item => JSON.stringify([item.title, item.technique]).toLowerCase().includes(String(body.query).toLowerCase())).sort((a, b) => b.score - a.score)}),
    "library/card": body => card(body.card_id) ? ok(card(body.card_id)) : refuse(409, "card_not_found", "search the Library for the card's id"),
    "library/list": () => ok({cards: lib.cards.filter(item => item.origin !== "shared"), shared: lib.shared, pending_imports: lib.imports, ...curation()}),
    "library/pin": curate("pins", true),
    "library/unpin": curate("pins", false),
    "library/ban": curate("bans", true),
    "library/unban": curate("bans", false),
    "library/import": body => {
      const import_id = "fixture-import-" + lib.next++;
      lib.imports.push({import_id, title: body.title});
      return ok({import_id});
    },
    "plans/list": () => ok({plans: lib.plans.map(({plan, ...entry}) => entry)}),
    "plans/get": body => {
      const found = lib.plans.find(item => item.digest === body.plan);
      return found ? ok(found.plan) : refuse(409, "plan_not_found", "choose a plan from plan_list");
    },
    "plans/edit": body => {
      const plan = body.plan;
      for (const h of plan.hypotheses || []) for (const cite of h.cites || []) {
        if (lib.bans.includes(cite.card_id)) return refuse(409, "card_banned", "cite a card you have not banned");
        if (!card(cite.card_id)) return refuse(409, "card_not_found", "cite a card in the shared pack or your library");
      }
      if (lib.pins.some(id => !(plan.pins_considered || []).includes(id))) return refuse(409, "plan_invalid", "consider every pinned card");
      const digest = String(lib.next++).padStart(2, "0").repeat(32);
      lib.plans.push({digest, created_by: plan.created_by, parent: plan.parent, created_at: 1800000100, plan});
      return ok({digest});
    },
  };
  state.script.push({keep: true, match: request => /^\/api\/v1\/(library|plans)\//.test(request.path), answer: request => {
    const name = request.path.slice("/api/v1/".length);
    if (!routes[name]) return {status: 404, body: {error: "route_not_found"}};
    // A write's key replays its first answer; another request under it is refused.
    const key = request.body && request.body.idempotency_key;
    if (key) {
      const {idempotency_key: _, ...rest} = request.body;
      const kept = lib.keys.get(key);
      if (kept) return kept.body === JSON.stringify([name, rest]) ? kept.answer : refuse(409, "operation_replay_conflict");
      const answer = routes[name](rest);
      lib.keys.set(key, {body: JSON.stringify([name, rest]), answer});
      return answer;
    }
    return routes[name](request.body || {});
  }});
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

scenario("Graphite: offered in place of the autonomous agent, which is said to be replaced", async () => {
  const state = graphiteWorld();
  assert.ok(state.caps.agents.choices.some(choice => choice.launch_agent === "autonomous"), "the controller still lists the autonomous choice");
  const page = await open(state);
  await wizardTo(page, "agent", "graphite");
  const offered = [...all(page, "#research-selects input")].map(input => input.value);
  assert.ok(offered.includes("graphite"));
  assert.ok(!offered.includes("autonomous"), "never offered for a new launch: " + offered);
  assert.equal(one(page, "#wizard-graphite").hidden, false, "Graphite's choices show once it is chosen");
  page.go("#agents");
  await page.advance(0);
  assert.match(page.text(one(page, "#agent-catalog [data-agent=replaced]")), /Replaced by Graphite for new campaigns/);
  assert.match(page.text(one(page, "#agent-catalog [data-agent=graphite]")), /Open the Library/);
  // A template saved with the autonomous agent is not loaded, and says why.
  const local = new Storage();
  local.setItem("carbon.launchpad.launch-templates.v1", JSON.stringify({old: {agent: "autonomous"}}));
  const second = await open(graphiteWorld(), {localStorage: local});
  await wizardTo(second, "limits", "graphite");
  await second.press(second.$("template-load"));
  assert.match(second.text("message"), /not loaded: Carbon's autonomous agent was replaced by Graphite/);
  // Choosing Manual hides Graphite's choices; a manual launch carries none.
  await toAgentStep(page);
  await page.press(byValue(page, "#research-selects input", "manual"));
  assert.equal(one(page, "#wizard-graphite").hidden, true);
  const body = await launchNow(page, state);
  assert.equal(body.agent, "none");
  for (const key of GRAPHITE_KEYS) assert.ok(!(key in body), "a manual launch carries no " + key);
  clean(page); clean(second);
});

scenario("Graphite: each mode launches with exactly its own fields", async () => {
  const state = graphiteWorld();
  const page = await open(state);
  await wizardTo(page, "agent", "graphite");
  // Full is the default, with a 10% research share and a hunt of 200 papers.
  assert.ok(one(page, "#wizard-graphite-mode-full").checked);
  assert.equal(page.$("wizard-research-share").value, "10");
  assert.equal(one(page, "#wizard-graphite-plan-box").hidden, true);
  let body = await launchNow(page, state);
  assert.equal(body.agent, "graphite");
  assert.equal(body.graphite_mode, "FULL");
  assert.equal(body.research_share, 0.1);
  assert.deepEqual(body.hunt, {max_records: 200});
  assert.ok(!("plan" in body) && !("limits" in body));
  assert.equal(body.model, G().caps.model.setup_choice.model_id, "Graphite runs on the miner's chosen model");
  // A typed share is sent exactly as the fraction it names.
  await toAgentStep(page);
  await page.type(page.$("wizard-research-share"), "12.5");
  page.$("wizard-research-share").blur();
  body = await launchNow(page, state);
  assert.equal(body.research_share, 0.125);
  // Research: the hunt, no share, no plan.
  await toAgentStep(page);
  await page.press(one(page, "#wizard-graphite-mode-research"));
  assert.equal(one(page, "#wizard-graphite-share").hidden, true);
  body = await launchNow(page, state);
  assert.equal(body.graphite_mode, "RESEARCH");
  assert.deepEqual(body.hunt, {max_records: 200});
  assert.ok(!("research_share" in body) && !("plan" in body));
  // Research without a hunt: the shared pack and the Library only.
  await toAgentStep(page);
  await page.press(page.$("wizard-hunt"));
  body = await launchNow(page, state);
  assert.ok(!("hunt" in body));
  // Build with no plan (its Planner writes one), then with the Library's plan.
  await toAgentStep(page);
  await page.press(one(page, "#wizard-graphite-mode-build"));
  assert.equal(one(page, "#wizard-graphite-hunt").hidden, true);
  body = await launchNow(page, state);
  assert.equal(body.graphite_mode, "BUILD");
  for (const key of ["plan", "hunt", "research_share", "limits"]) assert.ok(!(key in body), key);
  await toAgentStep(page);
  const picker = page.$("wizard-graphite-plan");
  const digest = G().library.plans[0].digest;
  assert.ok([...picker.options].some(option => option.value === digest), "the Library's plan is offered");
  assert.match(page.text("wizard-graphite-plan-note"), /1 plan in your Library/);
  await page.change(picker, digest);
  body = await launchNow(page, state);
  assert.equal(body.plan, digest);
  // The review says it all before launch.
  page.window.CarbonControlCenter.goWizard("review");
  await page.advance(0);
  assert.match(page.text("wizard-review"), /Build mode · plan /);
  // Back to Full: the plan chosen for Build stays with Build.
  await toAgentStep(page);
  await page.press(one(page, "#wizard-graphite-mode-full"));
  body = await launchNow(page, state);
  assert.equal(body.graphite_mode, "FULL");
  assert.ok(!("plan" in body), "a Full launch carries no plan: its research writes one");
  clean(page);
});

scenario("Graphite: the hunt estimate uses the model's listed price; queries keep to the closed grammar", async () => {
  const state = graphiteWorld({setup: copy(fx.setup_send)});
  const page = await open(state);
  await wizardTo(page, "model", "graphite");
  const model = state.caps.model.providers.find(row => row.id === "openai-responses").models[0].id;
  await page.press(byValue(page, "#wizard-model input", "openai-responses/" + model));
  await toAgentStep(page);
  // 600 input and 150 output tokens a paper at the listed per-token price.
  const pricing = fx.setup_send.choices.inference.find(choice => choice.id === "openai-responses").models.find(entry => entry.model_id === model).pricing;
  const each = 600 * pricing.input + 150 * pricing.output_including_reasoning;
  const usd = nano => "$" + String(Number((nano / 1e9).toPrecision(2)));
  const estimate = page.text("wizard-hunt-estimate");
  assert.ok(estimate.includes("about " + usd(each * 200) + " for up to 200 papers"), estimate);
  assert.ok(estimate.includes(usd(each) + " each"), estimate);
  assert.match(estimate, /skipped before any model call/);
  await page.type(page.$("wizard-hunt-records"), "50");
  assert.ok(page.text("wizard-hunt-estimate").includes(usd(each * 50) + " for up to 50 papers"));
  // The closed grammar: refused here before anything is sent.
  const queries = page.$("wizard-hunt-queries");
  for (const [typed, said] of [["neural operator AND surrogate:pde", /characters other than letters/], ["one two three four five six seven", /more than 6 terms/], [Array.from({length: 9}, (_, i) => "query " + i).join("\n"), /at most 8 queries/]]) {
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
  // A model with no listed price (setup's choice, priced live): no figure is invented.
  page.window.CarbonControlCenter.goWizard("model");
  await page.advance(0);
  await page.press(byValue(page, "#wizard-model input", G().caps.model.setup_choice.provider_id + "/" + G().caps.model.setup_choice.model_id));
  await toAgentStep(page);
  assert.match(page.text("wizard-hunt-estimate"), /No price is listed here for this model/);
  clean(page);
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
  assert.match(page.text("wizard-next-reason"), /per-epoch limits: model calls per epoch is a whole number/);
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

scenario("Graphite: the campaign shows its stage, plan, research and build spend, and the hunt", async () => {
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
  const box = one(page, "#campaign-detail [data-part=graphite]");
  assert.equal(box.hidden, false);
  const text = page.text(box);
  const g = state.view.graphite, spend = state.view.tiles.spend;
  const usd = nano => "$" + String(Number((nano / 1e9).toPrecision(2)));
  assert.match(text, /Graphite · Full mode/);
  assert.match(text, /Now: Building/);
  assert.ok(text.includes("Research spend" + usd(g.research_spent) + " · its share 10% (" + usd(spend.ceiling_nanodollars * 0.1) + " of your " + usd(spend.ceiling_nanodollars) + ")"), text);
  assert.ok(text.includes("Build spend" + usd(spend.used_nanodollars - g.research_spent)), text);
  assert.ok(text.includes("2 found on arXiv · 1 already known, not paid for again · 0 set aside at first reading · 1 read into your Library · cost " + usd(g.hunt.cost_nanodollars)), text);
  // The plan, read from the Library by its digest: its first hypotheses.
  const plan = G().library.plans[0].plan;
  assert.ok(text.includes(plan.hypotheses[0].hypothesis) && text.includes(plan.hypotheses[2].hypothesis), text);
  assert.ok(!text.includes(plan.hypotheses[3].hypothesis), "three shown, the rest in the Library");
  assert.match(text, /1 more in the Library/);
  assert.equal(one(page, "#campaign-detail [data-part=graphite] a.link").getAttribute("href"), "#library/plans/" + g.plan_digest);
  // A campaign without Graphite: the part is there, hidden, and empty.
  const plain = copy(G().view); delete plain.graphite;
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
  assert.deepEqual(sent, {query: "mlp", challenge: chosen.challenge_id, challenge_version: chosen.version, limit: 20});
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
  // The banned card is never shown, here or in the results.
  assert.ok(!page.text(one(page, "#library-body [data-part=results]")).includes("banned MLP variant"));
  // Even when a controller serves one by mistake.
  state.library.leakBans = true;
  await page.press(page.$("library-search-go"));
  assert.ok(!page.text(one(page, "#library-body [data-part=results]")).includes("banned MLP variant"), "a banned card is never shown in results");
  state.library.leakBans = false;
  // Your library: hunted and imported cards, labelled the same way.
  const mine = one(page, "#library-body [data-part=mine]");
  assert.match(page.text(mine), /Shared pack: 1773 cards/);
  for (const node of mine.querySelectorAll(".lib-card")) assert.equal(node.querySelector("[data-check]").textContent, "UNCHECKED");
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
  // Already pinned: says so.
  assert.equal(button("fixture-shared-0001", "pin").getAttribute("aria-pressed"), "true");
  await page.press(button("fixture-hunt-0001", "pin"));
  const pin = lastPost(state, "/api/v1/library/pin");
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
  // A lost answer keeps the key: the retry is the same request.
  state.script.unshift({match: r => r.path === "/api/v1/library/unpin", answer: {timeout: true}});
  await page.press(button("fixture-hunt-0001", "pin"));
  const lost = lastPost(state, "/api/v1/library/unpin").body.idempotency_key;
  assert.match(page.text("library-note"), /Not confirmed: .*same key/);
  await page.press(button("fixture-hunt-0001", "pin"));
  assert.equal(lastPost(state, "/api/v1/library/unpin").body.idempotency_key, lost, "the retry is replayed, never repeated");
  assert.equal(button("fixture-hunt-0001", "pin").getAttribute("aria-pressed"), "false");
  // A refusal is shown with the controller's next step, and lets the key go.
  state.script.unshift({match: r => r.path === "/api/v1/library/pin", answer: {status: 409, body: {error: "card_banned", next_step: "unban it first"}}});
  await page.press(button("fixture-import-0001", "pin"));
  assert.match(page.text("library-note"), /Refused: card banned\. Next: unban it first\./);
  assert.equal(button("fixture-import-0001", "pin").getAttribute("aria-pressed"), "false", "a refused pin pins nothing");
  assert.equal(page.window.sessionStorage.getItem("carbon.launchpad.pending-operation.v1"), "{}");
  clean(page);
});

scenario("Library: a route the controller does not have falls back to the operations door", async () => {
  const state = graphiteWorld();
  state.script.unshift({keep: true, match: r => r.path === "/api/v1/library/search", answer: {status: 404, body: {error: "route_not_found"}}});
  state.script.unshift({keep: true, match: r => r.path === "/api/v1/operations/library_search", answer: {body: {results: [G().library.cards[0]]}}});
  const page = await open(state);
  page.go("#library");
  await page.advance(0);
  await page.type(page.$("library-query"), "anything");
  await page.press(page.$("library-search-go"));
  assert.equal(lastPost(state, "/api/v1/operations/library_search").body.query, "anything");
  assert.ok(one(page, "#library-body [data-part=results] [data-card=fixture-shared-0001]"));
  // A refusal on the route itself is never retried elsewhere.
  state.script.unshift({match: r => r.path === "/api/v1/library/card", answer: {status: 409, body: {error: "card_not_found"}}});
  page.go("#library/card/nope");
  await page.advance(0);
  assert.equal(posts(state, "/api/v1/operations/library_card").length, 0);
  assert.match(page.text(one(page, "#library-body [data-part=card]")), /could not be read: card not found/);
  clean(page);
});

scenario("Library: an import queues text for the next Reader stage", async () => {
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
  assert.equal(sent.title, "My notes on residual MLPs");
  assert.equal(sent.text, "Residual connections helped when the data was small.");
  assert.ok(sent.idempotency_key);
  assert.match(page.text("library-import-result"), /Queued as fixture-import-1: “My notes on residual MLPs”/);
  assert.equal(page.$("library-import-title").value, "");
  assert.equal(page.$("library-import-text").value, "");
  assert.match(page.text(one(page, "#library-body [data-part=pending]")), /My notes on residual MLPs · fixture-import-1/);
  clean(page);
});

scenario("Library: the plan editor checks a plan, then saves it as a new version", async () => {
  const state = graphiteWorld();
  const page = await open(state);
  const first = G().library.plans[0];
  page.go("#library/plans/" + first.digest);
  await page.advance(0);
  await refresh(page);
  const view = () => page.text(one(page, "#library-body [data-part=plan]"));
  assert.match(view(), /Written byGraphite's Planner/);
  assert.ok(view().includes(first.plan.hypotheses[0].hypothesis));
  assert.ok(view().includes("Stops when: " + first.plan.hypotheses[0].stopping_rule));
  // Each cited card links to it and says where it came from.
  const cites = one(page, "#library-body [data-part=plan] .lib-cites");
  assert.deepEqual([...cites.querySelectorAll("[data-origin]")].map(node => node.dataset.origin), ["miner_hunt", "shared"]);
  assert.equal(cites.querySelector("a").getAttribute("href"), "#library/card/fixture-hunt-0001");
  await page.press(page.$("library-plan-edit"));
  assert.equal(page.$("library-plan-hypothesis-0").value, first.plan.hypotheses[0].hypothesis);
  assert.ok(page.$("library-plan-pin-0").checked, "the plan considered the pin");
  await page.type(page.$("library-plan-hypothesis-0"), "A wider and deeper residual MLP lowers the practice error.");
  // Ignoring a pin is refused here, before anything is sent.
  await page.press(page.$("library-plan-pin-0"));
  await page.press(page.$("library-plan-save"));
  assert.match(page.text("library-plan-result"), /consider every pinned card: Fixture card: residual MLP surrogate .* \(plan invalid\)/);
  await page.press(page.$("library-plan-pin-0"));
  // Citing a banned card is refused here too.
  await page.type(page.$("library-plan-cites-1"), "fixture-shared-0001\nfixture-shared-0003");
  await page.press(page.$("library-plan-save"));
  assert.match(page.text("library-plan-result"), /hypothesis 2 cites Fixture card: a banned MLP variant, which you banned \(card banned\)/);
  // A card that is in neither the pack nor the library is read first, and refused.
  await page.type(page.$("library-plan-cites-1"), "fixture-shared-0001, nowhere-0001");
  await page.press(page.$("library-plan-save"));
  assert.match(page.text("library-plan-result"), /cites nowhere-0001, which is in neither the shared pack nor your library \(card not found\)/);
  // A recipe that is not a JSON object is refused.
  await page.type(page.$("library-plan-cites-1"), "fixture-shared-0001");
  await page.type(page.$("library-plan-recipe-1"), "[1, 2]");
  await page.press(page.$("library-plan-save"));
  assert.match(page.text("library-plan-result"), /hypothesis 2: the recipe is a JSON object/);
  assert.equal(posts(state, "/api/v1/plans/edit").length, 0, "nothing was sent while the plan was refused here");
  await page.type(page.$("library-plan-recipe-1"), "");
  // Reorder: the third hypothesis first. Typed text survives the redraw.
  await page.press([...one(page, "#library-body [data-part=editor] [data-row='2']").querySelectorAll("button")].find(b => b.textContent === "Move up"));
  assert.equal(page.$("library-plan-hypothesis-0").value, "A wider and deeper residual MLP lowers the practice error.");
  assert.equal(page.$("library-plan-hypothesis-1").value, first.plan.hypotheses[2].hypothesis);
  await page.press(page.$("library-plan-save"));
  const sent = lastPost(state, "/api/v1/plans/edit").body;
  assert.ok(sent.idempotency_key);
  const plan = sent.plan;
  assert.equal(plan.schema, "carbon.graphite.miner-plan.v1");
  assert.equal(plan.parent, first.digest);
  assert.equal(plan.created_by, "miner");
  assert.deepEqual(plan.pins_considered, ["fixture-shared-0001"]);
  assert.equal(plan.hypotheses[0].hypothesis, "A wider and deeper residual MLP lowers the practice error.");
  assert.deepEqual(plan.hypotheses[0].recipe, first.plan.hypotheses[0].recipe);
  assert.deepEqual(plan.hypotheses[0].cites, first.plan.hypotheses[0].cites);
  assert.equal(plan.hypotheses[1].hypothesis, first.plan.hypotheses[2].hypothesis);
  assert.deepEqual(plan.hypotheses[2].cites, [{card_id: "fixture-shared-0001", origin: "shared"}]);
  assert.ok(!("recipe" in plan.hypotheses[2]));
  // Saved: the new version opens, read back as stored; the first is kept.
  const created = state.library.plans[state.library.plans.length - 1].digest;
  assert.equal(page.window.location.hash, "#library/plans/" + created);
  await refresh(page);
  assert.match(view(), /Written byYour edit/);
  assert.equal(all(page, "#library-body [data-part=list] tr[data-plan]").length, 2);
  assert.match(page.text("library-note"), /Saved as a new version/);
  // The controller's own refusal is shown with its next step.
  await page.press(page.$("library-plan-edit"));
  state.script.unshift({match: r => r.path === "/api/v1/plans/edit", answer: {status: 409, body: {error: "plan_invalid", next_step: "write each hypothesis's stopping rule"}}});
  await page.press(page.$("library-plan-save"));
  assert.match(page.text("library-plan-result"), /Refused: plan invalid\. Next: write each hypothesis's stopping rule\./);
  clean(page);
});

scenario("Library: a plan written from scratch has no parent", async () => {
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
  await page.type(page.$("library-plan-hypothesis-0"), "Mine: a smaller MLP keeps the score.");
  await page.type(page.$("library-plan-expected_effect-0"), "the same score");
  await page.type(page.$("library-plan-stopping_rule-0"), "one practice run");
  const typed = page.$("library-plan-stopping_rule-0");
  await page.press(page.$("library-plan-pin-0"));
  // A card pinned meanwhile (from another door) gets its own box, once the
  // box in hand is let go; the hypothesis being written is never redrawn.
  state.library.pins.push("fixture-hunt-0001");
  for (let i = 0; i < 8; i++) await refresh(page);
  assert.equal(all(page, "#library-plan-pin-1").length, 0, "not redrawn under a focused box");
  page.$("library-plan-pin-0").blur();
  await refresh(page);
  assert.ok(typed.isConnected, "the hypothesis fields were not redrawn for a pin");
  assert.equal(page.$("library-plan-hypothesis-0").value, "Mine: a smaller MLP keeps the score.");
  assert.ok(page.$("library-plan-pin-0").checked, "the box ticked before is still ticked");
  assert.match(page.text(page.$("library-plan-pin-1").parentNode), /MLP width schedule/);
  await page.press(page.$("library-plan-save"));
  assert.match(page.text("library-plan-result"), /consider every pinned card: Fixture card: MLP width schedule from a hunt \(plan invalid\)/);
  await page.press(page.$("library-plan-pin-1"));
  await page.press(page.$("library-plan-save"));
  const plan = lastPost(state, "/api/v1/plans/edit").body.plan;
  assert.equal(plan.parent, null);
  assert.equal(plan.created_by, "miner");
  assert.deepEqual(plan.pins_considered, ["fixture-shared-0001", "fixture-hunt-0001"]);
  assert.deepEqual(plan.hypotheses, [{hypothesis: "Mine: a smaller MLP keeps the score.", expected_effect: "the same score", stopping_rule: "one practice run", cites: []}]);
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
  await page.press(one(page, "#wizard-graphite-mode-build"));
  await still("the wizard's Graphite choices");
  page.window.CarbonControlCenter.goWizard("review");
  await page.advance(0);
  await still("the review");
  page.go("#library");
  await page.advance(0);
  await page.type(page.$("library-query"), "mlp");
  await page.press(page.$("library-search-go"));
  page.$("library-query").blur();
  await still("the Library's cards");
  page.go("#library/plans/" + G().library.plans[0].digest);
  await page.advance(0);
  await still("a plan");
  page.go("#campaigns/" + run.id + "/live");
  await page.advance(0);
  await still("the campaign's Graphite part");
  // Typing in the Library survives a re-read that brings new cards.
  page.go("#library/import");
  await page.advance(0);
  const text = page.$("library-import-text");
  await page.type(text, "Half-written notes");
  page.go("#library");
  await page.advance(0);
  const query = page.$("library-query");
  await page.type(query, "graph");
  state.library.cards.push({card_id: "fixture-hunt-0002", origin: "miner_hunt", check_status: "UNCHECKED", title: "Fixture card: found by a running hunt", score: 1, reasons: []});
  for (let i = 0; i < 9; i++) await refresh(page);
  assert.ok(query.isConnected && query.value === "graph", "the query being typed is untouched");
  assert.match(page.text(one(page, "#library-body [data-part=mine]")), /found by a running hunt/);
  page.go("#library/import");
  await page.advance(0);
  assert.ok(text.isConnected && text.value === "Half-written notes", "an import being written is untouched");
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
  page.go("#library/plans/" + G().library.plans[0].digest);
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
  process.stdout.write(JSON.stringify({passed, failed}));
})().catch(error => { process.stderr.write(String(error && error.stack || error) + "\n"); process.exit(1); });
