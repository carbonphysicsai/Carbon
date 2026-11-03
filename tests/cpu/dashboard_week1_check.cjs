// Week-1 home and leader-card checks, in Node without a browser (driven by tests/cpu/test_dashboard_week1.py).
//   1. the home page orders the Challenge cards by the names file's `order`, live or not, and shows `about`;
//   2. every launch card says the score to beat and the margin in one plain line;
//   3. the crown-change strip is drawn only from `launch.crown_changes` of the signed board.
// Argument: a built site directory (launch boards f02 and f08-ribbed-bracket, each with a leader) and the clock.
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const D = require(path.join(__dirname, "../../carbon/dashboard/web/dashboard.js"));

const [site, clock] = process.argv.slice(2);
const now = Number(clock);
assert.ok(site && Number.isInteger(now), "usage: dashboard_week1_check.cjs SITE NOW");

const NAMES = { // key order is NOT the display order
  f02: {name: "Burst Thermal", order: 4, about: "Peak top temperature of a part"},
  "f08-ribbed-bracket": {name: "Ribbed Bracket", order: 3, about: "Ribbed bracket: stiffness"},
  "chip-cold-plate": {name: "Cooling", order: 2, about: "Chip cold plate: cooling"},
  "electric-motor-magnetics": {name: "Motor", order: 1, about: "Electric motor magnetics"},
};
D.setNames({names: NAMES});
const titles = tree => { const out = []; D.walk(tree, n => { if (n.tag === "h3") out.push(D.textOf(n).trim()); }); return out; };

// ---- 1. order and description ----
const none = D.homePage({fixture: false, boards: []}, {}, {now});
assert.deepEqual(titles(none), ["Motor", "Cooling", "Ribbed Bracket", "Burst Thermal"]);
const noneText = D.textOf(none);
for (const n of Object.values(NAMES)) assert.ok(noneText.includes(n.about), "about shown: " + n.about);

const index = JSON.parse(fs.readFileSync(path.join(site, "data", "index.json"), "utf8"));
const boards = {};
for (const e of index.boards) boards[e.slug] = JSON.parse(fs.readFileSync(path.join(site, "data", "v2", e.slug + ".json"), "utf8"));
// The score-to-beat block reads v2 boards (floor + step + margin); a v1 leader board states no such rule: not drawn.
const v2 = o => { const c = JSON.parse(JSON.stringify(o)); c.launch.crown_changes = []; return c; };
const boardsV2 = Object.fromEntries(Object.entries(boards).map(([k, b]) => [k, v2(b)]));
assert.ok(!D.textOf(D.homePage(index, boards, {now})).includes("Score to beat"), "v1 leader: no block on the home card");
assert.ok(!D.textOf(D.boardPage(Object.values(boards)[0], {now})).includes("Score to beat"), "v1 leader: no block on the page");
const mixed = D.homePage(index, boardsV2, {now});
assert.deepEqual(titles(mixed), ["Motor", "Cooling", "Ribbed Bracket", "Burst Thermal"], "live and launching cards share one order");
const mixedText = D.textOf(mixed);
assert.ok(mixedText.includes("Score to beat"), "the home card names the score to beat");
assert.ok(mixedText.includes("passing every gate and minimum, to take the crown"), "and says the margin in one plain line");

// A bad order or description is ignored, never drawn; the card still shows by name.
D.setNames({names: {f02: {name: "Burst Thermal", order: 0, about: "<b>x</b>"}, "chip-cold-plate": {name: "Cooling", order: 2.5}}});
assert.ok(!D.textOf(D.homePage({fixture: false, boards: []}, {}, {now})).includes("<b>"), "markup is refused");
D.setNames({names: NAMES});

// ---- 2. the leader card ----
for (const board of Object.values(boardsV2)) {
  assert.ok(board.launch && board.king, board.slug);
  const text = D.textOf(D.boardPage(board, {now}));
  assert.ok(text.includes("Score to beat"), board.slug + ": score to beat");
  const l = board.launch;
  const shown = D.toBeat(l.to_beat);
  assert.ok(text.includes(shown), board.slug + ": the score to beat keeps the page's existing reading (" + shown + ")");
  assert.ok(text.includes("passing every gate and minimum, to take the crown"), board.slug + ": margin line");
  assert.ok(text.includes("No crown has changed hands yet."), board.slug + ": v2 with no history says so");
  // the Validator's 18:56 range: guaranteed bar, and the exact bar's public lower end (floored king total + margin, DOWN)
  assert.ok(text.includes("Score to beat (guaranteed)"), board.slug + ": guaranteed label");
  if (typeof l.margin === "number") {
    const low = D.total(board.king.value + l.margin);
    assert.ok(text.includes("The exact bar is between " + low + " and " + shown + "."), board.slug + ": range " + low);
    assert.ok(Number(low) <= Number(shown), board.slug + ": low end never above the guaranteed bar");
  }
}

// No leader: the baseline reading, never "the leader's —".
const bare = JSON.parse(JSON.stringify(Object.values(boardsV2)[0]));
bare.king = null; bare.launch.to_beat = 0.5; bare.launch.baseline_total = 0.4; bare.launch.margin = 0.01;
const bareText = D.textOf(D.boardPage(bare, {now}));
assert.ok(bareText.includes("Carbon's baseline") && !bareText.includes("leader's —"), "no leader: baseline wording");

// ---- 3. the crown strip ----
const board = JSON.parse(JSON.stringify(Object.values(boards)[0]));
const A = "5F3sa2TJAWMqDhXG6jhV4N8ko9SxwGy8TpaNS1repo5EYjQX", B = "5DAAnrj7VHTznn2AWBemMuyBwZWs6FNFjdyVXUeYum3PTXFy";
board.launch.crown_changes = [{hotkey: A, from_hotkey: B, since_epoch: 9, total: 0.5}, {hotkey: B, from_hotkey: null, since_epoch: 4, total: 0.4}];
const strip = D.textOf(D.boardPage(board, {now}));
assert.ok(strip.includes("Recent crown changes"));
assert.ok(strip.includes("epoch 9") && strip.includes("epoch 4"));
assert.ok(strip.indexOf("epoch 9") < strip.indexOf("epoch 4"), "newest first");
assert.ok(strip.includes("Carbon's baseline"), "a first crown is taken from the baseline");
// the same hotkey crowned again reads as a re-take, never as taking the crown from itself
board.launch.crown_changes = [{hotkey: A, from_hotkey: A, since_epoch: 12, total: 0.6}];
const again = D.textOf(D.boardPage(board, {now}));
assert.ok(again.includes("re-took the crown") && !again.includes("took the crown from"), "a re-take");
board.launch.crown_changes = [];
assert.ok(D.textOf(D.boardPage(board, {now})).includes("No crown has changed hands yet."));
board.launch.crown_changes = [{hotkey: A, since_epoch: -1}, {hotkey: 5, since_epoch: 1}, null];
assert.ok(!D.textOf(D.boardPage(board, {now})).includes("epoch -1"), "malformed rows are dropped");
// the v3 stability line (OWNER-CROWN-AVG-UNSTABLE-KING-01): drawn only for "UNSTABLE", with the receipted wording and no number
board.launch.crown_changes = [];
const STABILITY_LINE = "The current king's score moved between rebuilds, so its registered score stands and a challenger must beat it by the registered margin.";
delete board.launch.king_stability;
assert.ok(!D.textOf(D.boardPage(board, {now})).includes("moved between rebuilds"), "no flag on a v1/v2 board");
board.launch.king_stability = "STABLE";
assert.ok(!D.textOf(D.boardPage(board, {now})).includes("moved between rebuilds"), "STABLE draws nothing");
board.launch.king_stability = "UNSTABLE";
assert.ok(D.textOf(D.boardPage(board, {now})).includes(STABILITY_LINE), "UNSTABLE draws the receipted line");
board.launch.king_stability = "<b>x";
assert.ok(!D.textOf(D.boardPage(board, {now})).includes("moved between rebuilds"), "any other value draws nothing");
delete board.launch.king_stability;
console.log(JSON.stringify({boards: Object.keys(boards).length}));

// ---- 4. a dead heat inside one Ladder step reads as one, not as a zero lead ----
{
  const b = JSON.parse(JSON.stringify(Object.values(boards)[0]));
  b.king = Object.assign({}, b.king, {margin: 0, runner_up: "5Runner"});
  const text = D.textOf(D.boardPage(b, {now}));
  assert.ok(text.includes("Same Ladder step"), "tie says same Ladder step");
  assert.ok(!/Lead over the runner-up\s*[+Â±-]?0\.0+/.test(text), "no numeric zero lead");
}

// ---- 5. the score to beat is rounded UP to 3 places, never shown below the real bar ----
assert.equal(D.toBeat(0.7285), "0.729");
assert.equal(D.toBeat(0.72801), "0.729");
assert.equal(D.toBeat(0.728), "0.728");
assert.equal(D.toBeat(0.828), "0.828");
{
  const b = JSON.parse(JSON.stringify(Object.values(boardsV2)[0]));
  b.launch.to_beat = 0.7285;
  assert.ok(D.textOf(D.boardPage(b, {now})).includes("0.729"), "a 4-place to_beat reads rounded up on the page");
}
