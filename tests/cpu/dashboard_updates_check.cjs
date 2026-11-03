// Checks the Updates page (#/updates) in Node, without a browser (driven by
// tests/cpu/test_dashboard_updates.py). Argument: a built site directory. Renders the
// page from the site's updates.json against the site's own index and against an index
// with a live board for every Challenge it names, mounts each tree into a minimal DOM,
// and checks every section, every Challenge and every line is drawn as plain text.
// Prints {"sections": [...], "challenges": n, "lines": n}.
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const D = require(path.join(__dirname, "../../carbon/dashboard/web/dashboard.js"));

const [site] = process.argv.slice(2);
assert.ok(site, "usage: dashboard_updates_check.cjs SITE");
const read = name => JSON.parse(fs.readFileSync(path.join(site, name), "utf8"));
const updates = read("updates.json");
const index = read(path.join("data", "index.json"));
// The display names the live site is built with (`live --names`).
D.setNames({names: JSON.parse(fs.readFileSync(path.join(__dirname, "../../carbon/dashboard/names.static.json"), "utf8"))});

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
function nodes(tree, test) { const out = []; D.walk(tree, n => { if (test(n)) out.push(n); }); return out; }
const flat = s => s.replace(/\s+/g, " ").trim();

const SECTIONS = ["challenges", "every-version", "fixes", "known-issues", "faq"];
function check(tree, where) {
  const text = D.textOf(tree);
  D.walk(tree, n => {
    if (n.tag === "#text") assert.ok(!/[<>]/.test(n.text), where + ": plain text only");
    for (const [k, v] of Object.entries(n.attrs)) {
      assert.ok(!/^on/i.test(k) && k !== "style", where + ": attribute " + k);
      if (k === "href") assert.ok(v.startsWith("#/"), where + ": an Updates link stays on the site: " + v);
      if (k === "src") assert.fail(where + ": the page loads nothing: " + v);
    }
  });
  const drawn = nodes(tree, n => n.attrs["data-section"]).map(n => n.attrs["data-section"]);
  assert.deepEqual(drawn, SECTIONS, where + ": every section, in order");
  for (const name of SECTIONS) {
    const part = nodes(tree, n => n.attrs["data-section"] === name)[0];
    assert.ok(nodes(part, n => n.tag === "h2").length === 1, where + ": " + name + " has its heading");
  }
  const mounted = D.mount(tree, fakeDocument);
  assert.equal(flat(fakeText(mounted)), text, where + ": mounted text matches the tree");
  return text;
}

assert.equal(D.parseRoute("#/updates").view, "updates", "the route");
// Every line of the file is drawn, word for word.
const lines = [updates.intro, updates.next_label, ...updates.every_version, ...updates.fixes, ...updates.known_issues];
for (const c of updates.challenges) for (const n of c.next) lines.push(...n.changes);
for (const f of updates.faq) lines.push(f.q, ...f.a);

// The site's own index: a Challenge with no board says so, with no version.
const own = check(D.updatesPage(index, updates), "site index");
for (const line of lines) assert.ok(own.includes(flat(line)), "site index: line drawn: " + line);
const onSite = new Set(index.boards.filter(e => e.slug && e.challenge).map(e => e.challenge.id));
for (const c of updates.challenges) {
  const card = nodes(D.updatesPage(index, updates), n => n.attrs["data-challenge"] === c.id);
  assert.equal(card.length, 1, c.id + ": one card");
  const text = D.textOf(card[0]);
  assert.equal(D.textOf(nodes(card[0], n => n.tag === "h3")[0]), D.nameOf(c.id), c.id + ": titled by its display name");
  assert.ok(D.nameOf(c.id) !== c.id, c.id + ": a display name, never the raw id");
  if (!onSite.has(c.id)) assert.ok(text.includes("No live board yet.") && !text.includes("Live:"), c.id + ": no board, no version");
  for (const n of c.next) assert.ok(text.includes("Next: " + D.nameOf(c.id) + " " + n.version + " " + flat(updates.next_label)), c.id + ": next version " + n.version + ", labelled planned");
  assert.equal(text.split(flat(updates.next_label)).length - 1, c.next.length, c.id + ": every next version carries the label");
}

// An index with a live board for every Challenge: each card links its board with the live version.
const live = {boards: updates.challenges.map((c, i) => ({slug: c.id + "--no-class", state: "ACCEPTED", challenge: {id: c.id, version: "0." + (i + 1)}}))};
const tree = D.updatesPage(live, updates);
check(tree, "live index");
updates.challenges.forEach((c, i) => {
  const card = nodes(tree, n => n.attrs["data-challenge"] === c.id)[0];
  const links = nodes(card, n => n.tag === "a");
  assert.equal(links.length, 1, c.id + ": one live link");
  assert.equal(links[0].attrs.href, D.boardHref(c.id + "--no-class"), c.id + ": links its board");
  assert.equal(D.textOf(links[0]), "Live: " + D.nameOf(c.id) + " 0." + (i + 1), c.id + ": the index's live version");
  assert.ok(!D.textOf(card).includes("No live board yet."), c.id + ": live");
});

// A missing or broken file still draws every section, each saying there is nothing.
for (const broken of [null, {}, {challenges: "x", faq: [1]}]) {
  const text = check(D.updatesPage(live, broken), "broken " + JSON.stringify(broken));
  assert.ok(text.includes("None right now."), "an empty list says so");
}
process.stdout.write(JSON.stringify({sections: SECTIONS, challenges: updates.challenges.length, lines: lines.length}));
