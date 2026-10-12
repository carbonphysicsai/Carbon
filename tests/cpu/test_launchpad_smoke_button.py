"""LP-01: the real page's smoke button over a scripted controller.

The existing DOM and controller-document fixtures exercise requests, focus,
redraws and result rendering. No training, provider, chain or signer runs.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "scripts/dev/miner_launchpad"


@pytest.fixture
def documents(tmp_path):
    """Read-only synthetic campaign and the real page's discovery documents."""
    from carbon.development_session.exam_environment import exam_environment
    from scripts.dev.miner_launchpad import capabilities, controller
    from scripts.dev.miner_launchpad.operations import describe
    from scripts.dev.miner_launchpad.research_fixture import FixtureRunner

    source = FixtureRunner(clock=lambda: 1800000100)
    try:
        value = {
            "caps": capabilities.control_center(),
            "catalog": controller.capability_catalog(),
            "exam": exam_environment(),
            "preflight": source.preflight(),
            "run": source.own(),
            "view": source.view_document(),
            "operations": describe(),
            "options": {"agents": [], "families": []},
            "onboarding": {
                "network": "test",
                "netuid": 567,
                "mechanism": "registration",
                "cost": {"value": "NOT_READ"},
                "you_need": [],
                "carbon_never": [],
            },
        }
    finally:
        source.close()
    path = tmp_path / "smoke-page-documents.json"
    path.write_text(json.dumps(value, default=sorted), encoding="utf-8")
    return path


SCRIPT = r"""
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const root = process.argv[2];
const {openPage} = require(path.join(root, "../../../tests/cpu/control_center_dom.cjs"));
const fx = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
const scenario = process.argv[3];
const copy = v => JSON.parse(JSON.stringify(v));
const run = {...copy(fx.run), selects: "miner", state: "READY", experiments: [],
  refusals: [], journey: {submitted_epochs: [], final_exams_remaining: 2,
    frozen_awaiting_submission: false}};
delete run.last_refusal;
const state = {runs: [run], posted: [], answer: null, view: copy(fx.view), offline: false};
state.view.experiments = {rows: [], total: 0};
state.view.charts = [];
const server = async r => {
  if (r.method === "POST") state.posted.push(r);
  if (r.path === "/api/v1/operations/practice") {
    if (state.answer) return state.answer(r);
    run.state = "PRACTICING";
    return {body: copy(run)};
  }
  if (r.path === "/api/v1/control-center/capabilities") return {body: fx.caps};
  if (r.path === "/api/v1/capabilities") return {body: fx.catalog};
  if (r.path === "/api/v1/exam-environment") return {body: fx.exam};
  if (r.path === "/api/v1/onboarding/requirements") return {body: fx.onboarding};
  if (r.path === "/api/v1/runs") return state.offline ? {network: true} : {body: {runs: []}};
  if (r.path === "/api/v1/development") return {body: {sources: []}};
  if (r.path === "/api/v1/research") return {body: {preflight: fx.preflight, runs: state.runs}};
  if (r.path === "/api/v1/operations/options") return {body: fx.options};
  if (r.path === "/api/v1/operations") return {body: {operations: fx.operations}};
  if (r.path === "/api/v1/operations/campaign_view") {
    const doc = copy(state.view); doc.campaign.id = r.body.campaign;
    return {body: doc};
  }
  if (r.path === "/api/v1/setup") return {status: 409, body: {error: "setup_unavailable"}};
  if (r.path === "/api/v1/guide/remote-setup") return {body: {available: false, blocks: []}};
  if (/^\/api\/v1\/tools\//.test(r.path)) return {body: {open: false, tools: []}};
  throw new Error("Unexpected fixture request: " + r.path);
};
const refresh = p => p.advance(1500);
const button = (p, smoke = false, campaign = run.id) => {
  const node = p.$((smoke ? "journey-smoke-" : "journey-practice-") + campaign);
  assert.ok(node, "journey button exists"); return node;
};
const last = () => state.posted.filter(r => r.path === "/api/v1/operations/practice").at(-1).body;
async function open() {
  const p = await openPage(root, server);
  p.$("token").value = "fixture-token";
  await p.press(p.doc.querySelector("#connect-form button[type=submit]"));
  assert.equal(p.text("connection-state"), "Connected");
  p.go("#campaigns/" + run.id + "/experiments"); await p.advance(0);
  await p.type(p.$("journey-recipe-" + run.id), JSON.stringify({backbone: "fixture", parameters: {steps: 12345}}));
  p.$("journey-recipe-" + run.id).blur();
  return p;
}
const smokeResult = status => ({id: "smoke-fixture", outcome: "SMOKE", status,
  schema: "carbon.autoresearch.smoke-practice-result.v1", provenance: "SMOKE_PRACTICE",
  recipe: {parameters: {steps: 999999}}, runtime_seconds: 888888,
  summary: {score: 777777}, diagnostics: {descriptive_score: 666666}});
const row = (id, index, score) => ({id, index, backbone: "fixture", eligible: true,
  score, components: {}, fit: {final_loss: 555555}, budget_status: null});
async function main() {
  const p = await open();
  if (scenario === "requests") {
    const recipe = {backbone: "fixture", parameters: {steps: 12345}};
    await p.type(p.$("journey-recipe-" + run.id), JSON.stringify(recipe));
    await p.type(p.$("journey-hypothesis-" + run.id), "same hypothesis");
    await p.press(button(p, true));
    assert.deepEqual(last().strategy, recipe); assert.equal(last().hypothesis, "same hypothesis");
    assert.equal(last().campaign, run.id); assert.equal(last().mode, "smoke");
    run.state = "READY"; await refresh(p);
    await p.press(button(p));
    assert.deepEqual(last().strategy, recipe); assert.equal(last().hypothesis, "same hypothesis");
    assert.equal(Object.hasOwn(last(), "mode"), false, "full body has no mode key");
  } else if (scenario === "disabled") {
    assert.equal(button(p).disabled, false); assert.equal(button(p, true).disabled, false);
    for (const change of [{state: "PRACTICING"}, {state: "READY", journey: {...run.journey, final_exams_remaining: 0}}]) {
      Object.assign(run, change); await refresh(p);
      assert.equal(button(p).disabled, true); assert.equal(button(p, true).disabled, true);
    }
    run.journey.final_exams_remaining = 2; run.state = "READY"; await refresh(p);
    let release;
    state.answer = () => new Promise(resolve => { release = resolve; });
    await p.press(button(p));
    assert.equal(button(p).disabled, true); assert.equal(button(p, true).disabled, true);
    release({body: copy(run)}); await p.settle(); await p.advance(0);
    state.offline = true; await refresh(p);
    assert.equal(button(p).disabled, true); assert.equal(button(p, true).disabled, true);
  } else if (scenario === "budget" || scenario === "async_budget") {
    if (scenario === "budget") state.answer = () => ({status: 409, body: {error: "practice_time_budget_reached", next_step: "carbon_practice mode: smoke"}});
    await p.press(button(p));
    if (scenario === "async_budget") {
      run.state = "READY"; run.last_refusal = {operation: "practice", code: "practice_time_budget_reached", at: 1800000100};
      await refresh(p);
    }
    assert.match(p.text("message"), /Next, run a smoke practice/);
    assert.doesNotMatch(p.text("message"), /carbon_practice/);
    assert.equal(p.doc.activeElement.id, "journey-smoke-" + run.id);
    assert.equal(button(p, true).disabled, false);
  } else if (scenario === "unknown") {
    state.answer = () => ({status: 503, body: {error: "smoke_practice_unavailable"}});
    await p.press(button(p, true));
    assert.match(p.text("message"), /Not confirmed/);
    assert.doesNotMatch(p.text("message"), /This Challenge has no smoke practice/);
    assert.equal(button(p, true).disabled, false, "unknown outcome grants no availability fact");
  } else if (scenario === "unavailable") {
    state.answer = () => ({status: 409, body: {error: "smoke_practice_unavailable"}});
    await p.press(button(p, true));
    assert.match(p.text("message"), /This Challenge has no smoke practice/);
    assert.equal(button(p, true).disabled, true); assert.equal(button(p).disabled, false);
    await refresh(p); await refresh(p);
    assert.equal(button(p, true).disabled, true);
    const other = {...copy(run), id: "b".repeat(32)}; state.runs.push(other); await refresh(p);
    p.go("#campaigns/" + other.id + "/experiments"); await p.advance(0);
    assert.equal(button(p, true, other.id).disabled, false, "only the refused campaign is disabled");
    p.go("#campaigns/" + run.id + "/experiments"); await p.advance(0);
    assert.equal(button(p, true).disabled, true);
  } else if (scenario === "passed" || scenario === "failed" || scenario === "mixed") {
    await p.press(button(p, true));
    assert.match(p.text("message"), /Smoke practice started/);
    const smoke = smokeResult(scenario === "failed" ? "FAILED" : "PASSED");
    run.state = "READY"; run.experiments = [smoke];
    state.view.experiments = {rows: [row(smoke.id, 71, 777777)], total: 1};
    if (scenario === "mixed") {
      run.experiments.push({id: "full-fixture", recipe: {}, summary: {score: 0.125}});
      state.view.experiments.rows.unshift(row("full-fixture", 72, 0.125));
      state.view.experiments.total = 2;
    }
    await refresh(p); await refresh(p);
    const expected = scenario === "failed" ? "Smoke: failed" : "Smoke: passed";
    assert.match(p.text("message"), new RegExp(expected));
    assert.match(p.doc.querySelector("[data-operation=done]").textContent, new RegExp(expected));
    const result = p.doc.querySelector(".smoke-result"); assert.ok(result);
    assert.match(result.textContent, new RegExp(expected));
    assert.doesNotMatch(result.textContent, /[0-9]/, "smoke displays no numeric result");
    const results = p.doc.querySelector("[data-part=runs]");
    assert.doesNotMatch(results.textContent, /777777|666666|888888|999999/);
    if (scenario === "mixed") assert.match(results.textContent, /0\.125/);
    else assert.equal(results.querySelector("table"), null, "no score table for smoke alone");
  }
  assert.deepEqual(p.errors.map(String), [], "page has no runtime errors");
  console.log(JSON.stringify({passed: scenario}));
}
main().catch(error => { console.error(error.stack); process.exitCode = 1; });
"""


@pytest.mark.parametrize(
    "scenario",
    [
        "requests",
        "disabled",
        "budget",
        "async_budget",
        "unavailable",
        "unknown",
        "passed",
        "failed",
        "mixed",
    ],
)
def test_smoke_button_on_the_real_page(documents, scenario):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed here")
    result = subprocess.run(
        [node, "-e", SCRIPT, str(documents), str(PAGE), scenario],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-5000:]
    assert json.loads(result.stdout) == {"passed": scenario}
