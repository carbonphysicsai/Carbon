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

// ---- 5. The controller's recovery in reach whenever the state needs it. ----
// The page offers what the controller publishes (slice C's `recovery`), and
// each state's documents are the controller's own for that state
// (fx.recovering: the observe row with `supervisor.recovery_actions`, and the
// campaign view built for that state by the real campaign-view code), so a
// state is never paired with another state's recovery.
const LABELS = {reconcile: "Reconcile", resume: "Resume", stop: "Stop"};
for (const stateName of ["RECONCILIATION_REQUIRED", "INTERRUPTED", "PAUSE_REQUESTED"]) {
  scenario("the controller's recovery is on the Live tab, with why, for " + stateName, async () => {
    const real = fx.recovering[stateName];
    const offered = real.view.recovery.map(item => item.action);
    assert.ok(offered.length, "the controller offers recovery for " + stateName);
    assert.deepEqual(real.run.recovery, real.view.recovery, "the list row and the view agree");
    const state = launchable(world());
    const run = copy(real.run);
    state.runs = [run];
    state.view = copy(real.view);
    const page = await open(state);
    page.go("#campaigns/" + run.id + "/live");
    await page.advance(0);
    const now = "#campaign-detail [data-part=now]";
    // Each action the controller offers is first among the Live tab's
    // controls, ready, and the way forward (Stop aside) is the primary one.
    for (const action of offered) {
      const button = one(page, now + " [data-action=" + action + "]");
      assert.equal(button.disabled, false, action);
      assert.equal(button.classList.contains("primary"), action !== "stop", action);
    }
    // Reconcile is on the Live tab exactly when the controller asks for it.
    assert.equal(all(page, now + " [data-action=reconcile]").length, offered.includes("reconcile") ? 1 : 0);
    const attention = page.text(one(page, "#campaign-detail [data-part=attention]"));
    assert.match(attention, /Needs attention/);
    assert.ok(attention.includes(LABELS[offered[0]]), "why names the way forward: " + attention);
    await page.press(one(page, now + " [data-action=" + offered[0] + "]"));
    assert.ok(state.posted.some(entry => entry.path === "/api/v1/research/" + run.id + "/" + offered[0]));
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

(async () => {
  const passed = [], failed = [];
  for (const [name, run] of scenarios) {
    if (ONLY && !name.includes(ONLY)) continue;
    try { await run(); passed.push(name); }
    catch (error) { failed.push(name + ": " + String(error && error.message || error).split("\n")[0]); if (!process.argv[3]) { error.message = name + ": " + error.message; throw error; } }
  }
  process.stdout.write(JSON.stringify({passed, failed}));
})().catch(error => { process.stderr.write(String(error && error.stack || error) + "\n"); process.exit(1); });
