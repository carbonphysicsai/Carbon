// Display rules of the dashboard page, checked in Node without a browser (driven by tests/cpu/test_dashboard_display.py).
//   1. every public total is shown TRUNCATED to 3 decimals, never rounded up;
//   2. the device-class chip is hidden while the feed carries one class, and shown again when a second class appears.
// Argument: a built site directory (with at least one launch board that has a leader) and the clock (whole seconds).
// Prints {"boards": n}.
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const D = require(path.join(__dirname, "../../carbon/dashboard/web/dashboard.js"));

const [site, clock] = process.argv.slice(2);
const now = Number(clock);
assert.ok(site && Number.isInteger(now), "usage: dashboard_display_check.cjs SITE NOW");

// ---- 1. the truncation itself ----
const cases = [
  [0.519901, "0.519"], [0.52, "0.520"], [0.5199999999999999, "0.520"], [0.519999999, "0.519"], [0.64, "0.640"],
  [0.999999999, "0.999"], [1, "1.000"], [0, "0.000"], [0.0005, "0.000"], [0.001, "0.001"], [0.1234, "0.123"],
];
for (const [value, shown] of cases) assert.equal(D.total(value), shown, "total(" + value + ")");
for (const bad of [null, undefined, NaN, Infinity, "0.5", {}]) assert.equal(D.total(bad), "—", "total of " + String(bad));
// For any value with at most 9 decimals the shown number is never above the value and within one unit of the 3rd place.
let seed = 12345;
const next = () => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed; };
for (let i = 0; i < 4000; i += 1) {
  const nine = String(next() % 1000000000).padStart(9, "0");
  const value = Number("0." + nine);
  const shown = D.total(value);
  assert.equal(shown, "0." + nine.slice(0, 3), "total of 0." + nine);
  assert.ok(Number(shown) <= value + 1e-12, "never rounded up: " + nine);
}

// ---- 2. the class chip rule ----
assert.equal(D.classChipShown([]), false);
assert.equal(D.classChipShown(undefined), false);
assert.equal(D.classChipShown(["cpu"]), false);
assert.equal(D.classChipShown(["cpu", "cpu", null]), false);
assert.equal(D.classChipShown([null, null]), false);
assert.equal(D.classChipShown(["cpu", "gpu:rtx4090"]), true);
assert.equal(D.classChipShown(["gpu:rtx4090", null, "cpu"]), true);

// ---- 3. the pages ----
function chipTexts(tree) {
  const out = [];
  D.walk(tree, n => { if (n.tag === "span" && String(n.attrs.class || "").split(" ").includes("chip")) out.push(D.textOf(n).trim()); });
  return out;
}
let boards = 0;
const index = JSON.parse(fs.readFileSync(path.join(site, "data", "index.json"), "utf8"));
for (const name of fs.readdirSync(path.join(site, "data", "v2")).sort()) {
  const board = JSON.parse(fs.readFileSync(path.join(site, "data", "v2", name), "utf8"));
  if (!board.launch || !board.king || typeof board.king.value !== "number") continue;
  boards += 1;
  const where = board.slug;
  board.device_class = "gpu:rtx4090";
  const alone = D.textOf(D.boardPage(board, {now, classes: ["gpu:rtx4090"]}));
  const shown = D.total(board.king.value);
  assert.ok(alone.includes(shown), where + ": the leader's total reads " + shown);
  // never the longer, rounded-up reading of the same number
  const longer = String(board.king.value);
  if (longer.length > shown.length) assert.ok(!alone.includes(longer), where + ": no longer number " + longer);
  assert.ok(!chipTexts(D.boardPage(board, {now, classes: ["gpu:rtx4090"]})).includes("gpu:rtx4090"), where + ": one class hides the chip");
  assert.ok(!chipTexts(D.boardPage(board, {now})).includes("gpu:rtx4090"), where + ": no feed context hides it too");
  assert.ok(chipTexts(D.boardPage(board, {now, classes: ["gpu:rtx4090", "cpu"]})).includes("gpu:rtx4090"), where + ": a second class shows it again");
  // the ladder and the miner pages use the same reading
  for (const entry of board.eligible_leaderboard.entries) {
    if (typeof entry.screening_value === "number") {
      assert.ok(D.textOf(D.minerPage(board, entry.hotkey, {now})).includes(D.total(entry.screening_value)), where + ": miner total");
    }
  }
  // the home cards: the chip follows the whole feed
  const one = {...index, boards: index.boards.map(b => ({...b, device_class: "cpu"}))};
  const two = {...index, boards: index.boards.map((b, i) => ({...b, device_class: i % 2 ? "gpu:rtx4090" : "cpu"}))};
  const boardsBySlug = {[board.slug]: board};
  assert.ok(!chipTexts(D.homePage(one, boardsBySlug, {now})).includes("cpu"), "the home page hides a single class");
  if (index.boards.length > 1) assert.ok(chipTexts(D.homePage(two, boardsBySlug, {now})).includes("cpu"), "the home page shows two classes");
}
assert.ok(boards > 0, "the site has a launch board with a leader");
process.stdout.write(JSON.stringify({boards}));
