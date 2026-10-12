// Checks the leaderboard pages in Node, without a browser (DASHBOARD-02 S2,
// driven by tests/cpu/test_dashboard_feed.py and test_dashboard_web.py).
// Argument: a built site directory and the clock (whole seconds) it was built
// at. Renders every board.v2 file in each phase, the home, miner and "How to
// mine" pages, then mounts each tree into a minimal DOM.
// Prints {"boards": n, "phases": [...]}.
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const D = require(path.join(__dirname, "../../carbon/dashboard/web/dashboard.js"));

const [site, clock] = process.argv.slice(2);
const now = Number(clock);
assert.ok(site && Number.isInteger(now), "usage: dashboard_check.cjs SITE NOW");
const read = file => JSON.parse(fs.readFileSync(file, "utf8"));
const clone = value => JSON.parse(JSON.stringify(value));
const ctx = {now};

// ---- A minimal DOM: enough to mount a tree the way the browser does ----
class FakeNode {
  constructor(tag, ns) { this.tag = tag; this.ns = ns || null; this.attrs = {}; this.childNodes = []; this.data = null; }
  setAttribute(k, v) {
    assert.ok(!/^on/i.test(k), "no inline handler attribute: " + k);
    assert.notEqual(k.toLowerCase(), "style", "no inline style");
    this.attrs[k] = String(v);
  }
  appendChild(child) { this.childNodes.push(child); return child; }
}
const fakeDocument = {
  createElement: tag => { assert.ok(!["script", "style", "iframe", "object", "embed"].includes(tag), "no " + tag); return new FakeNode(tag); },
  createElementNS: (ns, tag) => { assert.equal(ns, D.SVG_NS); return new FakeNode(tag, ns); },
  createTextNode: text => { const n = new FakeNode("#text"); n.data = String(text); return n; },
};
function fakeText(node) { return node.tag === "#text" ? node.data : node.childNodes.map(fakeText).join(" "); }

// ---- Tree checks ----
function nodes(tree, tag) { const out = []; D.walk(tree, n => { if (n.tag === tag) out.push(n); }); return out; }
function hasClass(tree, cls) { let found = false; D.walk(tree, n => { if (String(n.attrs.class || "").split(" ").includes(cls)) found = true; }); return found; }
function check(tree, where) {
  const text = D.textOf(tree);
  assert.ok(!/qualif/i.test(text), where + ": the page never says qualified");
  assert.ok(!/case_id|prediction/i.test(text), where + ": no per-case or prediction data");
  D.walk(tree, n => {
    if (n.tag === "#text") assert.ok(!/[<>]/.test(n.text), where + ": plain text only: " + n.text);
    for (const [k, v] of Object.entries(n.attrs)) {
      assert.ok(!/^on/i.test(k) && k !== "style", where + ": attribute " + k);
      if (k === "href") assert.ok(v.startsWith("#/") || v.startsWith("https://github.com/carbonphysicsai/Carbon/"), where + ": link " + v);
      if (k === "src") assert.fail(where + ": the pages load nothing: " + v);
    }
  });
  for (const t of nodes(tree, "table")) {
    const body = t.children.find(c => c.tag === "tbody");
    assert.ok(body && body.children.length > 0, where + ": never an empty table");
  }
  const mounted = D.mount(tree, fakeDocument);
  assert.equal(fakeText(mounted).replace(/\s+/g, " ").trim(), text, where + ": mounted text matches the tree");
  return text;
}

const index = read(path.join(site, "data", "index.json"));
const boards = {};
const phases = new Set();
let count = 0;
for (const name of fs.readdirSync(path.join(site, "data", "v2")).sort()) {
  const board = read(path.join(site, "data", "v2", name));
  assert.equal(board.schema, "carbon.dashboard.board.v2");
  boards[board.slug] = board;
  phases.add(board.phase);
  const where = board.slug + " (" + board.phase + ")";
  const tree = D.boardPage(board, ctx);
  const text = check(tree, where);
  assert.ok(text.includes(board.challenge.id), where + ": title");
  assert.ok(text.includes(D.CHAMPIONSHIP_PENDING), where + ": championship not yet published");
  assert.ok(text.includes("key " + board.feed.key_id), where + ": feed key shown");
  // Rule statements: none while the rules card is not OK.
  assert.notEqual(board.rules.status, "OK", "no fixture build has a rules card");
  assert.ok(text.includes(D.RULES_UNAVAILABLE), where + ": rules unavailable");
  assert.ok(!/about \d+ h after a window|First scores publish ~/.test(text), where + ": no lag without the rules card");
  if (board.phase === "STALE") assert.ok(text.includes("Stale feed."), where + ": stale banner");
  if (board.phase === "PRE_FIRST_RELEASE") {
    assert.ok(hasClass(tree, "hero"), where + ": hero state");
    assert.ok(text.includes("First scores publish"), where + ": first-release message");
    assert.equal(nodes(tree, "table").length, 0, where + ": no table before the first release");
    assert.ok(text.includes("How to mine"), where + ": call to action");
  } else {
    assert.ok(text.includes(D.ELIGIBLE), where + ": eligible wording");
    assert.ok(text.includes(board.ranking_section.label), where + ": section labelled by name and sense");
    assert.ok(text.includes("accuracy (lower is better)"), where + ": accuracy label");
    // Both bars, each to be announced while null.
    assert.ok(text.includes("Posted margin") && text.includes("Noise guard"), where + ": both bars");
    assert.equal(text.split(D.TBA).length - 1 >= 3, true, where + ": target and both bars to be announced");
    assert.ok(text.includes("Share now " + D.UNPUBLISHED), where + ": share not yet published");
    assert.ok(text.includes(D.shortKey(board.king.hotkey)), where + ": king shown");
    const copies = []; D.walk(tree, n => { if (n.attrs["data-copy"]) copies.push(n.attrs["data-copy"]); });
    assert.ok(copies.includes(board.king.hotkey), where + ": king hotkey copy button");
    const lb = board.eligible_leaderboard;
    const rows = nodes(nodes(tree, "table").find(t => t.attrs.id === "ladder"), "tr").length - 1;
    assert.equal(rows, Array.isArray(lb.coldkeys) ? lb.coldkeys.length : lb.entries.length, where + ": every ladder row drawn");
    if (Array.isArray(lb.coldkeys)) for (const row of lb.coldkeys) assert.ok(text.includes(D.LADDER[row.status][0]), where + ": status chip " + row.status);
    for (const entry of lb.entries) check(D.minerPage(board, entry.hotkey, ctx), where + " miner " + entry.hotkey);
  }
  // A rules card that matches: its lag and rule show (display only).
  const ok = clone(board);
  ok.rules = {status: "OK", card_digest: "sha256:" + "0".repeat(64), reasons: {}};
  ok.challenge.rule = "fixture-rule-card";
  const lag = {blocks: 5400, seconds: 64800, hours: 18};
  ok.eligible_leaderboard.release_lag = lag; ok.next_release.lag = lag;
  const okText = check(D.boardPage(ok, ctx), where + " rules OK");
  assert.ok(okText.includes("Rule fixture-rule-card"), where + ": rule shown when OK");
  assert.ok(board.phase === "PRE_FIRST_RELEASE" ? okText.includes("First scores publish ~18 h after the first round") : okText.includes("Scores publish about 18 h after a window."), where + ": lag when OK");
  // The same values with the card unavailable never show.
  const withheld = clone(ok); withheld.rules = board.rules;
  const withheldText = check(D.boardPage(withheld, ctx), where + " rules withheld");
  assert.ok(!withheldText.includes("fixture-rule-card") && !withheldText.includes("about 18 h"), where + ": rule text only when OK");
  count += 1;
}

// Championship rounds, once the feed carries them (rev 7 shape).
const live = Object.values(boards).find(b => b.phase === "LIVE" && b.king);
const rounds = clone(live);
rounds.championship.rounds = [
  {epoch: 41, chunks_used: 2, stopped: "efficacy", n_solved: 812, margin_pct: 2.25, new_king: null, paid_from_epoch: null,
    entrants: [{hotkey: "fixture-miner-01", est_improvement_pct: 3.1, lower_bound_pct: 2.6, guard_bar_pct: 2.4, gap_to_win_pct: -0.2, safety: "PASS", outcome: "WON"}]},
  {epoch: 40, chunks_used: 0, stopped: null, n_solved: 0, margin_pct: 2.25, entrants: [], new_king: null, paid_from_epoch: null},
];
rounds.king.share_now = 0.5; rounds.king.next_halving_epoch = 43; rounds.king.uid = 7;
rounds.target_to_beat.posted_margin = 2.25; rounds.target_to_beat.noise_guard = "paired test";
const roundsText = check(D.boardPage(rounds, ctx), "rounds");
for (const want of ["Epoch 41", "stopped early: efficacy", "812 solved", "3.1%", "2.6%", "2.4%", "-0.2%", D.EMPTY_EPOCH, "UID 7", "epoch 43", "2.25", "paired test"]) {
  assert.ok(roundsText.includes(want), "rounds: " + want);
}
assert.ok(!roundsText.includes(D.CHAMPIONSHIP_PENDING), "rounds replace the pending note");
// A king history with a handover marks an era change.
const kings = clone(live);
kings.history.kings = [{hotkey: "a", receipt_block: 1, value: 0.2}, {hotkey: "a", receipt_block: 2, value: 0.19}, {hotkey: "b", receipt_block: 3, value: 0.18}];
const kingsTree = D.boardPage(kings, ctx);
check(kingsTree, "kings");
assert.equal(nodes(kingsTree, "line").filter(n => n.attrs.class === "handover").length, 1, "one handover marked");
// Timing: a countdown from a published time, else "timing unavailable".
const timed = clone(live);
timed.next_round.next_utc = new Date((now + 3723) * 1000).toISOString().replace(/\.\d+Z$/, "Z");
const timedTree = D.boardPage(timed, ctx);
assert.ok(D.textOf(timedTree).includes("01:02:03"), "countdown from next_utc");
assert.ok(D.textOf(D.boardPage(live, ctx)).includes(D.TIMING_UNAVAILABLE), "timing unavailable");
// A rule-era change since the last visit is labelled.
assert.ok(D.textOf(D.boardPage(live, {now, eraBefore: "sha256:" + "1".repeat(64)})).includes("New rule era."), "era change labelled");
// A refused newest feed says so.
const refused = clone(live); refused.feed_state = {state: "REFUSED", code: "signature_invalid"};
assert.ok(D.textOf(D.boardPage(refused, ctx)).includes("Newest feed refused"), "refused banner");

// Home, network strip, How to mine.
const home = check(D.homePage(index, boards, {now, network: null}), "home");
assert.ok(home.includes("Fixture data."), "fixture notice");
assert.equal(D.networkStrip(null), null, "no snapshot, no strip");
assert.equal(D.networkStrip({other: 1}), null, "unknown fields, no strip");
assert.ok(D.textOf(D.homePage(index, boards, {now, network: {uids: 256, validators: 12, emission: 0.5}})).includes("Validators 12"), "network strip");
const mine = check(D.minePage(), "mine");
for (const want of ["Start", "Practice", "Submit", "My status"]) assert.ok(mine.includes(want), "how to mine: " + want);
const links = []; D.walk(D.minePage(), n => { if (n.attrs.href) links.push(n.attrs.href); });
assert.ok(links.includes(D.LINKS.launchpad) && links.includes(D.LINKS.journey), "launchpad docs linked");

assert.deepEqual(D.parseRoute("#/b/x--cpu/m/5abc"), {view: "miner", slug: "x--cpu", hotkey: "5abc"});
assert.deepEqual(D.parseRoute("#/mine"), {view: "mine"});
assert.deepEqual(D.parseRoute("#/"), {view: "home"});
assert.equal(D.countdown(3723), "01:02:03");
assert.equal(D.signed(0.015, 3), "+0.015");
process.stdout.write(JSON.stringify({boards: count, phases: [...phases].sort()}) + "\n");
