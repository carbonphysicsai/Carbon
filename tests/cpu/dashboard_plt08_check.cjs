"use strict";
// LP-02: exercise the real pure renderer using projected, signed-feed fixtures.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const D = require("../../carbon/dashboard/web/dashboard.js");
const cases = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const clone = x => JSON.parse(JSON.stringify(x));
const ctx = {now: cases.now};
function nodes(tree, tag) {
  const out = [];
  D.walk(tree, n => { if (n.tag === tag) out.push(n); });
  return out;
}
function section(tree, name) {
  let found = null;
  D.walk(tree, n => { if (n.attrs["data-section"] === name) found = n; });
  return found;
}
function status(board, key = cases.hotkey) {
  return section(D.minerPage(board, key, ctx), "submission-status");
}
function containsNoPayload(tree) {
  const serialized = JSON.stringify(tree);
  for (const canary of ["fixture_unknown_refusal_canary", "fixture_future_refusal_canary", "fixture_case_payload_canary",
    "fixture_window_payload_canary", "918273", "case_id", "window_id", "displayed_score", "screening_value"]) {
    assert.ok(!serialized.includes(canary), "no status payload: " + canary);
  }
  assert.ok(!/\bScore\b|\bWindow\b|\bCase\b/.test(D.textOf(tree)), "status has counts only");
}

assert.deepEqual(Object.keys(D.REFUSALS).sort(), cases.closed_codes, "all closed producer codes have plain labels");
const activity = status(cases.with_status);
assert.ok(activity, "known status row is shown");
const text = D.textOf(activity);
for (const expected of ["Received 12", "Scored 4", "Refused 6", "Malformed submission 2", "Other 4"]) {
  assert.ok(text.includes(expected), "status: " + expected);
}
containsNoPayload(activity);
assert.equal(status(cases.without_status), null, "no fabricated counts for an older feed");
assert.equal(status(cases.with_status, "fixture-miner-98"), null, "another hotkey's counts are not shown");
assert.ok(status(cases.prerelease), "status is visible before a released result");
assert.equal(cases.prerelease.phase, "PRE_FIRST_RELEASE");
const pending = D.textOf(D.minerPage(cases.prerelease, cases.hotkey, ctx));
assert.ok(!/\bRank\b|\bRole\b/.test(pending), "status-only miner has no invented eligibility");

const future = clone(cases.with_status);
future.miner_status[0].refused = JSON.parse('{"constructor":1,"__proto__":1,"fixture_future_refusal_canary":2}');
const futureTree = status(future);
assert.ok(D.textOf(futureTree).includes("Other 4"), "unknown names aggregate safely, including prototype names");
containsNoPayload(futureTree);
future.miner_status[0].received = "fixture_case_payload_canary";
assert.equal(status(future), null, "malformed count data cannot become page text");

for (const name of ["sealed", "sealed_without_rules"]) {
  const board = clone(cases[name]);
  const ladder = section(D.boardPage(board, ctx), "leaderboard");
  assert.ok(D.textOf(ladder).includes(D.SEALED_GRAIN), name + ": sealed explanation");
  const table = nodes(ladder, "table").find(t => t.attrs.id === "ladder");
  for (const row of table.children.find(n => n.tag === "tbody").children) {
    assert.equal(D.textOf(row.children[0]), "", "sealed rank absent");
    assert.equal(D.textOf(row.children[2]), "", "sealed displayed score absent");
  }
  board.eligible_leaderboard.coldkeys[0].displayed_score = 123456.75;
  board.eligible_leaderboard.coldkeys[0].rank = 876543;
  const defensive = section(D.boardPage(board, ctx), "leaderboard");
  const first = nodes(defensive, "table").find(t => t.attrs.id === "ladder").children.find(n => n.tag === "tbody").children[0];
  assert.equal(D.textOf(first.children[0]), "", "malformed sealed rank never renders");
  assert.equal(D.textOf(first.children[2]), "", "malformed sealed score never renders");
}
const empty = section(D.boardPage(cases.empty_sealed, ctx), "leaderboard");
assert.ok(D.textOf(empty).includes(D.SEALED_GRAIN));
assert.equal(nodes(empty, "table").length, 0, "empty sealed ladder cannot fall back to released hotkey scores");
assert.ok(D.textOf(D.boardPage(cases.shown, ctx)).includes("Grain 0.5%"), "posted grain note is retained");

// Supply every rule-derived field so each missing-card assertion exercises a
// populated path rather than proving absence from an empty fixture.
const ruled = clone(cases.with_status);
ruled.challenge.rule = "fixture-rule-copy";
ruled.rotation = {blocks: 7200, hours: 24};
ruled.next_round.every = {blocks: 7200, hours: 24};
const lag = {blocks: 5400, hours: 18};
ruled.next_release.lag = lag;
ruled.eligible_leaderboard.release_lag = lag;
ruled.eligible_leaderboard.grain_pct = 0.5;
Object.assign(ruled.target_to_beat, {posted_margin: 0.015, screening_margin: 0.01, noise_guard: "paired test",
  registered_score: {decision: "fixture-deciding-rule-copy"}, gates: ["fixture-rule-gate"]});
ruled.championship.entry = {trigger_bar: 0.13, king_screening_display: 0.123, coldkeys: [{entered: true}]};
ruled.championship.rounds = [
  {epoch: 41, chunks_used: 2, stopped: "efficacy", n_solved: 812, margin_pct: 0.9,
    entrants: [{hotkey: "fixture-miner-01", est_improvement_pct: 3.1, lower_bound_pct: 2.6, guard_bar_pct: 2.4, gap_to_win_pct: -0.2, safety: "PASS", outcome: "WON"}]},
  {epoch: 40, entrants: []},
];
const gated = ["Rule fixture-rule-copy", "Every 7,200 blocks", "Release lag 5,400 blocks", "Scores publish about 18 h after a window",
  "Grain 0.5%", "Posted margin", "Screening margin", "Noise guard", "Registered score", "fixture-rule-gate",
  "Two bars, the posted margin", "A failed safety gate is never offset", "Entry trigger bar", "margin 0.9%", "Guard bar", "Gap to win", D.EMPTY_EPOCH];
const ruledText = D.textOf(D.boardPage(ruled, ctx));
for (const sentence of gated) assert.ok(ruledText.includes(sentence), "populated ruled fixture: " + sentence);
for (const missing of [null, undefined, {status: "UNAVAILABLE"}, {status: "DIGEST_MISMATCH"}]) {
  const withheld = clone(ruled);
  withheld.rules = missing;
  const page = D.boardPage(withheld, ctx);
  const absentText = D.textOf(page);
  for (const sentence of gated) assert.ok(!absentText.includes(sentence), "no rule assertion without matching card: " + sentence);
  assert.ok(absentText.includes(D.RULES_LINE), "missing-card explanation");
  for (const fact of ["Epoch 41", "812 solved", "stopped early: efficacy", "3.1%", "2.6%", "no contenders"]) {
    assert.ok(absentText.includes(fact), "observed feed field remains: " + fact);
  }
  containsNoPayload(status(withheld));
}
const pre = clone(cases.prerelease);
pre.rules = {status: "OK"};
pre.rotation = ruled.rotation;
pre.next_release.lag = lag;
const preText = D.textOf(D.boardPage(pre, ctx));
assert.ok(preText.includes("First scores publish about 18 h") && preText.includes("Rounds rotate every"));
pre.rules = null;
const noPreRules = D.textOf(D.boardPage(pre, ctx));
assert.ok(!noPreRules.includes("First scores publish about 18 h") && !noPreRules.includes("Rounds rotate every"));
for (const board of [cases.with_status, cases.shown, cases.sealed, pre]) {
  for (const tree of [D.boardPage(board, ctx), D.minerPage(board, cases.hotkey, ctx)]) {
    assert.ok(!/qualif/i.test(D.textOf(tree)), "eligible, never qualified");
    assert.ok(!D.textOf(tree).includes("~"), "about, never approximate tilde");
  }
}
process.stdout.write(JSON.stringify({status: "counts_only", sealed: "no_values", rules: "fail_closed"}));
