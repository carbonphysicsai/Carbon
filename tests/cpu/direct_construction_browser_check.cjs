"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const {webcrypto} = require("node:crypto");
const {Document} = require("./control_center_dom.cjs");

const source = fs.readFileSync(path.join(__dirname, "../../scripts/dev/miner_launchpad/research_tools.js"), "utf8");
const base = "/api/v1/tools/direct-development-1.3";

async function panel(configured) {
  const document = new Document();
  const parent = document.createElement("div");
  document.documentElement.append(parent);
  const calls = [];
  let submitCount = 0;
  const closed = {campaign: "direct-development-1.3", open: false};
  const opened = {campaign: "direct-development-1.3", open: true, development_only: true,
    challenge: {id: "synthetic-linear-field-2d", version: "1.3"},
    construction_intake_configured: configured, tools: [], tasks: []};
  const control = {
    el(tag, text, className) {
      const node = document.createElement(tag);
      if (text !== undefined) node.textContent = text;
      if (className) node.className = className;
      return node;
    },
    state: () => ({connected: true}),
    onRender() {},
    setText(node, value) { node.textContent = value; },
    async api(url, body) {
      calls.push({url, body});
      if (url === base && body === undefined) return closed;
      if (url === base + "/open") return opened;
      if (url === base + "/stage_construction_graph") return {ok: true, result: {status: "STAGED"}};
      if (url === base + "/submit_construction") {
        submitCount++;
        return {ok: true, result: submitCount === 1
          ? {state: "ADMITTED", task_id: "task-1"}
          : {state: "RECONSTRUCTED", task_id: "task-1", state_digest: "sha256:" + "e".repeat(64), predictions_digest: "sha256:" + "f".repeat(64)},
        score_status: "SCORE_UNAVAILABLE", official_eligible: false};
      }
      throw new Error("unexpected route " + url);
    },
  };
  const window = {CarbonControlCenter: control};
  vm.runInNewContext(source, {window, document, crypto: webcrypto, TextEncoder, TextDecoder, atob, btoa, console});
  await window.CarbonTools.mountDirect(parent);
  return {document, parent, calls};
}

async function press(parent, label) {
  const button = [...parent.querySelectorAll("button")].find(node => node.textContent === label);
  assert.ok(button, "missing button " + label);
  const click = button.listeners.find(listener => listener.type === "click");
  assert.ok(click, "missing click handler " + label);
  await click.fn();
  await new Promise(resolve => setImmediate(resolve));
}

(async () => {
  const ready = await panel(true);
  assert.match(ready.parent.textContent, /Direct construction · DEVELOPMENT/);
  await press(ready.parent, "Open the tools");
  // A registered-shape recipe. The stubbed answers test browser forwarding,
  // not actual source availability, receiver reconstruction or evaluation.
  const interfaceDigest = "sha256:7413bab4aa4c549c416a687b380dc9ef0731f6471030e451fe9242539a45d504";
  const recipe = {
    schema: "carbon.construction-recipe.v1",
    challenge: {id: "synthetic-linear-field-2d", version: "1.3",
      train_digest: "sha256:95aec24fe064b05bbb8750820c2c95bfac7117ba56496a58bdcc570b8438b867",
      interface_digest: interfaceDigest,
      construction_limits_digest: "sha256:e4486fb177124c6e3db12096855db5601791264df8123a74f26a0747b0f7a158"},
    source: {kind: "graph", submission_digest: "sha256:" + "a".repeat(64)},
    procedure: {entrypoint: null, configuration: {}, train_use: {cases: "all"}, initial_state: null},
    output: {format: "carbon.numeric-graph.v1", interface_digest: interfaceDigest},
  };
  ready.parent.querySelector("textarea").value = "{";
  const before = ready.calls.length;
  await press(ready.parent, "Submit for clean rebuild");
  assert.equal(ready.calls.length, before, "invalid JSON never reaches the route");
  assert.match(ready.parent.textContent, /Not valid JSON/);
  ready.parent.querySelector("textarea").value = JSON.stringify(recipe);
  ready.parent.querySelector("input").value = "sha256:" + "a".repeat(64);
  await press(ready.parent, "Stage graph source");
  assert.deepEqual(JSON.parse(JSON.stringify(ready.calls.at(-1))), {url: base + "/stage_construction_graph",
    body: {recipe, expected_manifest_digest: "sha256:" + "a".repeat(64)}});
  await press(ready.parent, "Submit for clean rebuild");
  assert.deepEqual(JSON.parse(JSON.stringify(ready.calls.at(-1))), {url: base + "/submit_construction", body: {recipe}});
  assert.match(ready.parent.textContent, /ADMITTED/);
  assert.equal(ready.parent.querySelector("textarea").readOnly, true, "the admitted recipe stays pinned while status is checked");
  ready.parent.querySelector("textarea").value = "{}"; // even a programmatic edit cannot switch the status identity
  await press(ready.parent, "Check rebuild status");
  assert.deepEqual(JSON.parse(JSON.stringify(ready.calls.at(-1))), {url: base + "/submit_construction", body: {recipe}});
  assert.deepEqual(JSON.parse(ready.parent.querySelector("textarea").value), recipe, "the displayed recipe is still the admitted one");
  assert.match(ready.parent.textContent, /RECONSTRUCTED/);
  assert.ok([...ready.parent.querySelectorAll("button")].some(node => node.textContent === "Rebuild complete" && node.disabled));
  assert.match(ready.parent.textContent, /SCORE_UNAVAILABLE/);

  const noReceiver = await panel(false);
  await press(noReceiver.parent, "Open the tools");
  assert.match(noReceiver.parent.textContent, /No direct construction receiver is pinned/);
  assert.equal([...noReceiver.parent.querySelectorAll("button")].some(node => node.textContent === "Submit for clean rebuild"), false);
  process.stdout.write("direct construction browser component passed\n");
})().catch(error => { process.stderr.write(String(error.stack || error) + "\n"); process.exit(1); });
