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
// Text a null field never renders: its reason stays in the board.v2 JSON.
const NULL_TEXTS = ["not yet published", "to be announced", "timing unavailable", "not in feed", "no runner-up", "no king yet",
  "not_in_feed", "rules_unavailable", "sealed_until_grain", "grain_human_input"];
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
  for (const phrase of NULL_TEXTS) {
    assert.ok(!text.toLowerCase().includes(phrase), where + ": no per-field null text: " + phrase);
  }
  const mounted = D.mount(tree, fakeDocument);
  assert.equal(fakeText(mounted).replace(/\s+/g, " ").trim(), text, where + ": mounted text matches the tree");
  return text;
}


// The one muted line per section: present exactly when a field the section
// would draw is null. These lists are the test's own, not the page's.
const nullIn = (obj, keys) => !obj || keys.some(k => obj[k] === null || obj[k] === undefined);
const EXPECT = {
  king: b => nullIn(b.king, ["uid", "value", "margin", "share_now", "next_halving_epoch", "since_block", "since_utc", "crowned_epoch", "defences"]),
  target: b => nullIn(b.target_to_beat, ["value", "posted_margin", "noise_guard"]),
  timing: b => nullIn(b.next_round, ["next_utc", "next_block"]) || (nullIn(b.next_round, ["every"]) && nullIn(b, ["rotation"]))
    || nullIn(b.next_release, ["next_utc", "next_block", "lag"]),
  championship: b => !Array.isArray(b.championship.rounds) || nullIn(b.championship.entry, ["trigger_bar", "king_screening_display", "coldkeys"]),
  network: (b, net) => nullIn(net, ["uids", "validators", "emission"]),
};
function moreLines(node) { let n = 0; D.walk(node, x => { if (x.attrs.class === "more-line") { n += 1; assert.equal(D.textOf(x), D.MORE); } }); return n; }
function sectionLines(tree, board, network, where) {
  let expected = 0;
  D.walk(tree, n => {
    const name = n.attrs["data-section"];
    if (!name) return;
    const lines = moreLines(n);
    if (name in EXPECT) {
      const want = EXPECT[name](board, network);
      assert.equal(lines, want ? 1 : 0, where + ": " + name + " line only when a field is null");
      expected += lines;
    } else assert.equal(lines, 0, where + ": no line in " + name);
  });
  assert.equal(moreLines(tree), expected, where + ": lines only inside sections");
}
function rulesLines(text) { return text.toLowerCase().split("rules unavailable").length - 1; }

const index = read(path.join(site, "data", "index.json"));
assert.equal(typeof index.network, "boolean", "the index says whether a network snapshot exists");
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
  sectionLines(tree, board, null, where);
  assert.ok(text.includes(board.challenge.id), where + ": title");
  assert.ok(text.includes("key " + D.keyShort(board)), where + ": feed key as people know it");
  assert.ok(!text.includes(board.feed.key_id), where + ": internal key id only in an attribute");
  // Rule statements: one "Rules unavailable" line while the card is not OK.
  assert.notEqual(board.rules.status, "OK", "no fixture build has a rules card");
  assert.equal(rulesLines(text), 1, where + ": one rules line");
  assert.ok(!/about \d+ h after a window|First scores publish about|Release lag/.test(text), where + ": no lag without the rules card");
  // What is scored, from the feed's sections.
  for (const s of board.sections) assert.ok(text.includes(s.display), where + ": scored " + s.name);
  assert.equal(D.rotationText(board), null, where + ": no round period without the rules card");
  assert.ok(!text.includes("Rounds rotate"), where + ": no round period without the rules card");
  if (board.phase === "STALE") assert.ok(text.includes("Stale feed."), where + ": stale banner");
  if (board.phase === "PRE_FIRST_RELEASE") {
    assert.ok(hasClass(tree, "hero"), where + ": hero state");
    assert.ok(text.includes("First scores publish"), where + ": first-release message");
    assert.equal(nodes(tree, "table").length, 0, where + ": no table before the first release");
    assert.ok(text.includes("How to mine"), where + ": call to action");
    for (const l of board.labels) assert.ok(text.includes(l), where + ": label " + l);
  } else {
    assert.ok(text.includes(D.ELIGIBLE), where + ": eligible wording");
    assert.ok(text.includes(board.ranking_section.label), where + ": section labelled by name and sense");
    assert.ok(text.includes("accuracy (lower is better)"), where + ": accuracy label");
    assert.ok(!text.includes("Posted margin") && !text.includes("Noise guard the"), where + ": null bars hidden");
    assert.ok(!text.includes("Share now") && !text.includes("Next halving") && !text.includes("Crowned"), where + ": null king fields hidden");
    assert.ok(text.includes(D.shortKey(board.king.hotkey)), where + ": king shown");
    const copies = []; D.walk(tree, n => { if (n.attrs["data-copy"]) copies.push(n.attrs["data-copy"]); });
    assert.ok(copies.includes(board.king.hotkey), where + ": king hotkey copy button");
    const lb = board.eligible_leaderboard;
    const rows = nodes(nodes(tree, "table").find(t => t.attrs.id === "ladder"), "tr").length - 1;
    assert.equal(rows, Array.isArray(lb.coldkeys) ? lb.coldkeys.length : lb.entries.length, where + ": every ladder row drawn");
    if (Array.isArray(lb.coldkeys)) for (const row of lb.coldkeys) assert.ok(text.includes(D.LADDER[row.status][0]), where + ": status chip " + row.status);
    for (const entry of lb.entries) check(D.minerPage(board, entry.hotkey, ctx), where + " miner " + entry.hotkey);
  }
  // A rules card that matches: its lag and rule show, and the rules line goes.
  const ok = clone(board);
  ok.rules = {status: "OK", card_digest: "sha256:" + "0".repeat(64), reasons: {}};
  ok.challenge.rule = "fixture-rule-card";
  const lag = {blocks: 5400, seconds: 64800, hours: 18};
  ok.eligible_leaderboard.release_lag = lag; ok.next_release.lag = lag;
  const okText = check(D.boardPage(ok, ctx), where + " rules OK");
  assert.equal(rulesLines(okText), 0, where + ": no rules line when OK");
  assert.ok(okText.includes("Rule fixture-rule-card"), where + ": rule shown when OK");
  assert.ok(board.phase === "PRE_FIRST_RELEASE" ? okText.includes("First scores publish about 18 h after the first round") : okText.includes("Scores publish about 18 h after a window."), where + ": lag when OK");
  // The same values with the card unavailable never show.
  const withheld = clone(ok); withheld.rules = board.rules;
  const withheldText = check(D.boardPage(withheld, ctx), where + " rules withheld");
  assert.ok(!withheldText.includes("fixture-rule-card") && !withheldText.includes("about 18 h"), where + ": rule text only when OK");
  count += 1;
}

// Every field published: values show and no section line remains.
const live = Object.values(boards).find(b => b.phase === "LIVE" && b.king);
const full = clone(live);
full.rules = {status: "OK", card_digest: "sha256:" + "0".repeat(64), reasons: {}};
Object.assign(full.king, {uid: 7, share_now: 0.5, next_halving_epoch: 43, since_utc: "2026-10-07T01:00:00Z", crowned_epoch: 39, defences: 2});
Object.assign(full.target_to_beat, {value: 0.12, posted_margin: 2.25, noise_guard: "paired test"});
const at = new Date((now + 3723) * 1000).toISOString().replace(/\.\d+Z$/, "Z");
Object.assign(full.next_round, {next_utc: at, next_block: 8200000, every: {blocks: 7200, seconds: 86400, hours: 24}});
Object.assign(full.next_release, {next_utc: at, next_block: 8205400, lag: {blocks: 5400, seconds: 64800, hours: 18}});
full.championship.entry = {trigger_bar: 0.13, king_screening_display: 0.123, coldkeys: [{entered: true}], reasons: {}};
full.championship.rounds = [
  {epoch: 41, chunks_used: 2, stopped: "efficacy", n_solved: 812, margin_pct: 2.25, new_king: null, paid_from_epoch: null,
    entrants: [{hotkey: "fixture-miner-01", est_improvement_pct: 3.1, lower_bound_pct: 2.6, guard_bar_pct: 2.4, gap_to_win_pct: -0.2, safety: "PASS", outcome: "WON"}]},
  {epoch: 40, chunks_used: 0, stopped: null, n_solved: 0, margin_pct: 2.25, entrants: [], new_king: null, paid_from_epoch: null},
];
const fullTree = D.boardPage(full, ctx);
const fullText = check(fullTree, "full");
sectionLines(fullTree, full, null, "full");
assert.equal(moreLines(fullTree), 0, "full: no section line");
for (const want of ["UID 7", "Share now 0.5", "epoch 43", "Held for 1 d", "Crowned epoch 39", "Defences 2", "Posted margin 2.25", "Noise guard paired test",
  "01:02:03", "Every 7,200 blocks", "Release lag 5,400 blocks", "Entry trigger bar 0.13", "Epoch 41", "stopped early: efficacy", "812 solved",
  "3.1%", "2.6%", "2.4%", "-0.2%", D.EMPTY_EPOCH]) {
  assert.ok(fullText.includes(want), "full: " + want);
}
// One null in a section brings its line back.
for (const [name, unset] of [["king", b => { b.king.share_now = null; }], ["target", b => { b.target_to_beat.noise_guard = null; }],
  ["timing", b => { b.next_release.lag = null; }], ["championship", b => { b.championship.entry.trigger_bar = null; }]]) {
  const one = clone(full); unset(one);
  const oneTree = D.boardPage(one, ctx);
  check(oneTree, "one null " + name);
  sectionLines(oneTree, one, null, "one null " + name);
  assert.equal(moreLines(oneTree), 1, "one null in " + name + ": one line");
}
// A king history with a handover marks an era change.
const kings = clone(live);
kings.history.kings = [{hotkey: "a", receipt_block: 1, value: 0.2}, {hotkey: "a", receipt_block: 2, value: 0.19}, {hotkey: "b", receipt_block: 3, value: 0.18}];
const kingsTree = D.boardPage(kings, ctx);
check(kingsTree, "kings");
assert.equal(nodes(kingsTree, "line").filter(n => n.attrs.class === "handover").length, 1, "one handover marked");
// A rule-era change since the last visit is labelled.
assert.ok(D.textOf(D.boardPage(live, {now, eraBefore: "sha256:" + "1".repeat(64)})).includes("New rule era."), "era change labelled");
// A refused newest feed says so.
const refused = clone(live); refused.feed_state = {state: "REFUSED", code: "signature_invalid"};
assert.ok(D.textOf(D.boardPage(refused, ctx)).includes("Newest feed refused"), "refused banner");

// Home, network strip, How to mine.
const home = check(D.homePage(index, boards, {now, network: null}), "home");
assert.ok(home.includes("Fixture data."), "fixture notice");
assert.equal(D.networkStrip(null), null, "no snapshot, no strip");
const partNet = {uids: 256};
const partTree = D.homePage(index, boards, {now, network: partNet});
sectionLines(partTree, null, partNet, "network partial");
assert.ok(D.textOf(partTree).includes("UIDs 256") && D.textOf(partTree).includes(D.MORE), "network partial");
const fullNet = {uids: 256, validators: 12, emission: 0.5};
const netTree = D.homePage(index, boards, {now, network: fullNet});
sectionLines(netTree, null, fullNet, "network full");
assert.ok(D.textOf(netTree).includes("Validators 12") && !D.textOf(netTree).includes(D.MORE), "network full");
const mine = check(D.minePage(), "mine");
for (const want of ["Start", "Practice", "Submit", "My status"]) assert.ok(mine.includes(want), "how to mine: " + want);
const links = []; D.walk(D.minePage(), n => { if (n.attrs.href) links.push(n.attrs.href); });
assert.ok(links.includes(D.LINKS.launchpad) && links.includes(D.LINKS.journey), "launchpad docs linked");

assert.deepEqual(D.parseRoute("#/b/x--cpu/m/5abc"), {view: "miner", slug: "x--cpu", hotkey: "5abc"});
assert.deepEqual(D.parseRoute("#/mine"), {view: "mine"});
assert.deepEqual(D.parseRoute("#/"), {view: "home"});
assert.equal(D.countdown(3723), "01:02:03");
assert.equal(D.signed(0.015, 3), "+0.015");
assert.equal(D.keyShort({feed: {public_key: "bc45568c50bd8d60a211310ffad7936ee9ff21908c9b14021acd0ba11416d3ae"}}), "bc45568c…d3ae");

// ---- VALIDATOR-33 A (#1143, DASHBOARD-02 S1b) ----
// An optional third argument: a site built from fixtures.chain_documents(), whose
// feeds carry chain time, the ledger king, handovers and the target to beat.
const chainSite = process.argv[4];
let chainCount = 0;
function countdownNode(tree, at) {
  let found = null;
  D.walk(tree, n => { if (n.attrs["data-until"] !== undefined && Number(n.attrs["data-until"]) === at) found = n; });
  return found;
}
function sectionNode(tree, name) { let found = null; D.walk(tree, n => { if (n.attrs["data-section"] === name) found = n; }); return found; }
if (chainSite) {
  for (const name of fs.readdirSync(path.join(chainSite, "data", "v2")).sort()) {
    const board = read(path.join(chainSite, "data", "v2", name));
    const where = "chain " + board.slug;
    assert.equal(board.phase, "LIVE", where + ": the chain time is fresh");
    assert.equal(board.freshness.basis, "as_of_block", where + ": age from the chain time");
    const tree = D.boardPage(board, ctx);
    const text = check(tree, where);
    const k = board.king;
    const kingNode = sectionNode(tree, "king");
    if (k.share_now !== null) {
      // The king card shows the share and the halving, with a live countdown.
      const halving = D.utcSeconds(k.next_halving_utc);
      assert.ok(text.includes("Share now " + D.fmt(k.share_now)), where + ": share");
      assert.ok(text.includes("Next halving"), where + ": halving");
      const count = countdownNode(kingNode, halving);
      assert.ok(count, where + ": halving countdown");
      assert.equal(D.textOf(count), D.countdown(halving - now), where + ": halving countdown text");
      assert.match(D.textOf(count), /^(\d+ d )?\d\d:\d\d:\d\d$/, where + ": a clock");
      for (const want of ["UID " + k.uid, "Crowned " + D.utc(D.utcSeconds(k.crowned_utc)), "Defences " + k.defences, "Reward eligible", "Held for"]) {
        assert.ok(text.includes(want), where + ": " + want);
      }
      assert.equal(moreLines(kingNode), 0, where + ": every king field present");
    } else {
      // The ledger's king is not the released incumbent yet: nothing of it shows.
      assert.equal(k.reasons.share_now, "king_not_released", where);
      for (const absent of ["Share now", "Next halving", "Crowned", "Reward", "Defences"]) assert.ok(!D.textOf(kingNode).includes(absent), where + ": " + absent);
      assert.equal(moreLines(kingNode), 1, where + ": the king's line");
    }
    // The next release: block, an estimated time, and a live countdown.
    const at = D.utcSeconds(board.next_release.next_utc);
    const release = countdownNode(sectionNode(tree, "timing"), at);
    assert.ok(release, where + ": release countdown");
    assert.equal(D.textOf(release), D.countdown(at - now), where + ": release countdown text");
    assert.ok(text.includes("block " + D.block(board.next_release.next_block) + ", about " + D.utc(at) + " at 12 s per block"), where + ": estimated release time");
    assert.ok(!text.includes("~"), where + ": about, never a tilde");
    // The target's values, posted by the validator, show without a rules card;
    // their prose waits for it. The registered score's candidate is never drawn.
    const t = board.target_to_beat;
    assert.notEqual(board.rules.status, "OK");
    assert.ok(text.includes("Posted margin " + D.fmt(t.posted_margin)), where + ": posted margin");
    assert.ok(text.includes("Screening margin " + D.fmt(t.screening_margin)), where + ": screening margin");
    assert.ok(text.includes("Noise guard " + D.guardText(t.noise_guard)), where + ": noise guard");
    assert.ok(text.includes(D.POSTED), where + ": labelled posted by the validator");
    assert.ok(!text.includes("rules card sets them"), where + ": the bars' prose waits for the rules card");
    assert.ok(!text.includes(t.registered_score.candidate), where + ": candidate never drawn");
    assert.ok(text.includes("Registered score: " + t.registered_score.decision), where + ": registered score decision");
    const ok = clone(board); ok.rules = {status: "OK", card_digest: "sha256:" + "0".repeat(64), reasons: {}};
    assert.ok(check(D.boardPage(ok, ctx), where + " rules OK").includes("rules card sets them"), where + ": prose with the card");
    // Handovers, newest first, and the chain time in the feed block.
    assert.ok(text.includes("Handovers"), where + ": handovers");
    const handovers = nodes(nodes(tree, "table").find(t2 => D.textOf(t2).includes("New king")), "tr").length - 1;
    assert.equal(handovers, board.history.handovers.length, where + ": every handover drawn");
    assert.ok(text.includes("Chain time block " + D.block(board.as_of_block.number)), where + ": chain time");
    chainCount += 1;
  }
  assert.ok(chainCount >= 2, "chain fixtures: a released and an unreleased ledger king");
}
process.stdout.write(JSON.stringify({boards: count, phases: [...phases].sort(), chain: chainCount}) + "\n");
