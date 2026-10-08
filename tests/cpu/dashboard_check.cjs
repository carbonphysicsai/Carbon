// Checks the leaderboard's view-models in Node, without a browser
// (DASHBOARD-01 D1, driven by tests/cpu/test_dashboard_feed.py).
// Arguments: built board files. Prints {"boards": n}.
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const D = require(path.join(__dirname, "../../carbon/dashboard/web/dashboard.js"));

function texts(value, out) {
  if (typeof value === "string") out.push(value);
  else if (Array.isArray(value)) value.forEach(v => texts(v, out));
  else if (value && typeof value === "object") Object.values(value).forEach(v => texts(v, out));
  return out;
}
function walk(node, visit) { visit(node); for (const child of node.children || []) walk(child, visit); }

let count = 0;
for (const file of process.argv.slice(2)) {
  const board = JSON.parse(fs.readFileSync(file, "utf8"));
  const view = D.boardView(board);
  assert.equal(view.labels[0], "DEVELOPMENT", "board view labelled");
  assert.ok(view.labels.includes("FIXTURE"), "fixture board says so");
  assert.equal(view.standing.length, board.standing.length, "every standing row drawn");
  assert.deepEqual(view.standing.map(r => r.rank), board.standing.map(r => r.rank), "rank copied, not computed");
  assert.equal(view.incumbent.hotkey, board.incumbent.hotkey, "incumbent copied");
  // Rounded text at the feed's precision, never more digits.
  const digits = D.decimals(board.values.precision);
  for (const row of view.standing) for (const s of row.sections) {
    if (s.text !== "—") assert.match(s.text, new RegExp("^-?\\d+\\.\\d{" + digits + "}$"), "rounded " + s.text);
  }
  // Sense only from the feed.
  for (const [key] of D.SECTIONS) {
    const meta = (board.section_meta || {})[key];
    assert.equal(D.sectionInfo(board, key).sense !== "", !!(meta && meta.sense), "sense from feed: " + key);
  }
  for (const hotkey of Object.keys(board.miners)) {
    const miner = D.minerView(board, hotkey);
    assert.equal(miner.labels[0], "DEVELOPMENT", "miner view labelled");
    assert.equal(miner.recipe, "Recipe not disclosed");
    for (const d of miner.detail) assert.ok(board.released_windows.some(w => w.slice(7, 19) === d.window), "detail only for released windows");
  }
  assert.equal(D.minerView(board, "nobody"), null);
  for (const t of texts([view, Object.keys(board.miners).map(h => D.minerView(board, h))], [])) assert.ok(!/[<>]/.test(t), "plain text: " + t);
  for (const [key] of D.SECTIONS) {
    const built = D.trendLayout(D.trendSeries(board, key, null), {title: key, precision: board.values.precision});
    let paths = 0;
    walk(built.svg, n => { if (n.tag === "path") paths += 1; assert.ok(!/[<>]/.test(n.text || ""), "chart text plain"); });
    assert.ok(paths >= 1, "trend draws lines for " + key);
  }
  count += 1;
}
assert.deepEqual(D.parseRoute("#/b/x--cpu/m/5abc"), {view: "miner", slug: "x--cpu", hotkey: "5abc"});
assert.deepEqual(D.parseRoute("#/"), {view: "home"});
assert.equal(D.fmt(0.4, 0.001), "0.400");
process.stdout.write(JSON.stringify({boards: count}) + "\n");
