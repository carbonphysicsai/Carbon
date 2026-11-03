// Checks the launch boards' pages in Node, without a browser (OWNER-DASHBOARD-01,
// driven by tests/cpu/test_launch_board.py). Argument: a built site directory and
// the clock (whole seconds). Renders every board.v2 file that carries `launch`, the
// board and each ladder hotkey's page, mounts each tree into a minimal DOM, and
// checks the disclosure the page owes: rounded totals and counts only.
// Prints {"boards": n, "phases": [...]}.
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const D = require(path.join(__dirname, "../../carbon/dashboard/web/dashboard.js"));

const [site, clock] = process.argv.slice(2);
const now = Number(clock);
assert.ok(site && Number.isInteger(now), "usage: dashboard_launch_check.cjs SITE NOW");
const ctx = {now};

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
  createElementNS: (ns, tag) => new FakeNode(tag, ns),
  createTextNode: text => { const n = new FakeNode("#text"); n.data = String(text); return n; },
};
function fakeText(node) { return node.tag === "#text" ? node.data : node.childNodes.map(fakeText).join(" "); }
function nodes(tree, tag) { const out = []; D.walk(tree, n => { if (n.tag === tag) out.push(n); }); return out; }
function hasClass(tree, cls) { let found = false; D.walk(tree, n => { if (String(n.attrs.class || "").split(" ").includes(cls)) found = true; }); return found; }

// Words and shapes a launch page never carries: a case, a target, a pool, a seed,
// a section below the total, a qualification claim, or the released-window lag.
const FORBIDDEN = /case[_ ]?id|prediction|\bseed\b|\btarget value|\bpool\b|accuracy|design q|near-limit|qualif|released window|lag/i;

function check(tree, where) {
  const text = D.textOf(tree);
  assert.ok(!FORBIDDEN.test(text), where + ": forbidden wording: " + (text.match(FORBIDDEN) || [])[0]);
  D.walk(tree, n => {
    if (n.tag === "#text") assert.ok(!/[<>]/.test(n.text), where + ": plain text only");
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

const GATE_HINT = "These hotkeys' latest result failed a mandatory gate. A hotkey with an earlier scored result keeps its rank on that best result; the failed result is not scored.";
const phases = new Set();
let count = 0;
let ranked_and_failed = 0;
for (const name of fs.readdirSync(path.join(site, "data", "v2")).sort()) {
  const board = JSON.parse(fs.readFileSync(path.join(site, "data", "v2", name), "utf8"));
  if (!board.launch) continue;
  phases.add(board.phase);
  const where = board.slug + " (" + board.phase + ")";
  const tree = D.boardPage(board, ctx);
  const text = check(tree, where);
  assert.ok(D.textOf(nodes(tree, "h1")[0]).trim() === D.nameOf(board.challenge.id), where + ": the title is the name, never the raw id");
  assert.ok(hasClass(tree, "card") || hasClass(tree, "hero"), where + ": a standing is drawn");
  assert.ok(text.includes("Graded") && text.includes("Failed a gate") && text.includes(String(board.launch.counts.graded)), where + ": the counts");
  assert.ok(!text.includes("Eligible for the championship"), where + ": a launch board is not a championship");
  assert.ok(!text.includes("Rules unavailable"), where + ": no rules line on a launch board");
  assert.ok(text.includes("Design showcase") && hasClass(tree, "teaser"), where + ": the public design showcase is offered");
  assert.ok(!text.includes("Rules unavailable") && !text.includes("More coming"), where + ": no filler lines");
  assert.ok(board.labels.includes("DEVELOPMENT") && board.labels.every(l => l !== "FIXTURE"), where + ": labels");
  // Before the margin is registered the page says so in words and shows no placeholder number.
  if (board.launch.margin === null) assert.ok(/not yet registered/i.test(text), where + ": an unregistered margin is named");
  if (board.phase === "PRE_FIRST_RELEASE") {
    assert.equal(board.launch.counts.graded, 0, where + ": no grade yet");
    assert.ok(hasClass(tree, "hero"), where + ": hero state");
    assert.ok(text.includes("No hotkey has a graded result yet"), where + ": the empty state says so");
    assert.equal(nodes(tree, "table").length, 0, where + ": no table before the first grade");
    assert.ok(text.includes("How to mine"), where + ": call to action");
  } else {
    assert.ok(hasClass(tree, "leader"), where + ": the leader card comes first");
    assert.ok(/total score/i.test(text) && text.includes("higher is better"), where + ": the one scored section, in words");
    // A hotkey that failed a gate is named with its gates; with no leader the baseline is the bar.
    for (const [key, gates] of Object.entries(board.launch.gate_names || {})) {
      assert.ok(text.includes(D.shortKey(key)) && gates.every(g => text.includes(g.replaceAll("_", " "))), where + ": a failed gate is named");
    }
    // A row is best total + latest status: a hotkey whose latest result failed a gate but has an earlier scored best is
    // listed in both places, and the hint says so (never "not scored or ranked").
    if (Object.keys(board.launch.gate_names || {}).length) {
      assert.ok(text.includes(GATE_HINT), where + ": the failed-gate hint");
      assert.ok(!text.includes("not scored or ranked"), where + ": no claim that a gate failure unranks a best");
      const ladderText = D.textOf(nodes(tree, "table").find(t => t.attrs.id === "ladder"));
      const gateText = D.textOf(nodes(tree, "table").find(t => D.textOf(t).includes("Gates failed")));
      for (const entry of board.eligible_leaderboard.entries) {
        if (!(entry.hotkey in board.launch.gate_names)) continue;
        assert.ok(ladderText.includes(D.shortKey(entry.hotkey)) && gateText.includes(D.shortKey(entry.hotkey)), where + ": ranked on its best and named with its gate");
        ranked_and_failed += 1;
      }
    }
    if (board.king === null && typeof board.launch.baseline_total === "number") assert.ok(text.includes("Carbon's baseline"), where + ": the baseline is shown");
    assert.ok(text.includes(board.eligible_leaderboard.label), where + ": the ladder is named");
    assert.ok(board.king === null || text.includes(D.shortKey(board.king.hotkey)), where + ": king shown");
    const table = nodes(tree, "table").find(t => t.attrs.id === "ladder");
    if (board.eligible_leaderboard.entries.length) {
      assert.equal(nodes(table, "tr").length - 1, board.eligible_leaderboard.entries.length, where + ": every ranked hotkey drawn");
    }
    // Totals show truncated to 3 decimals, never rounded up and never a longer number.
    for (const entry of board.eligible_leaderboard.entries) {
      const shown = entry.screening_value;
      if (typeof shown === "number") assert.ok(text.includes(D.total(shown)), where + ": total " + shown);
      check(D.minerPage(board, entry.hotkey, ctx), where + " miner " + entry.hotkey);
    }
  }
  count += 1;
}
assert.ok(count > 0, "the site has a launch board");
process.stdout.write(JSON.stringify({boards: count, phases: [...phases].sort(), ranked_and_failed}));
