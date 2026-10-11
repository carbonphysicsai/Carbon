// Checks the design showcase's pure drawing functions in Node, without a
// browser (DASHBOARD-01 D2, driven by tests/cpu/test_dashboard_showcase.py).
// Arguments: replay files. Prints {"replays": n}.
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const S = require(path.join(__dirname, "../../carbon/dashboard/web/showcase.js"));

function walk(node, visit) { visit(node); for (const child of node.children || []) walk(child, visit); }
function count(tree, cls) { let n = 0; walk(tree, x => { if (String(x.attrs.class || "").split(" ").includes(cls)) n += 1; }); return n; }

let replays = 0;
for (const file of process.argv.slice(2)) {
  const doc = JSON.parse(fs.readFileSync(file, "utf8"));
  const n = doc.steps.length;
  for (let at = 0; at <= n; at++) {
    const done = at === n;
    const built = S.gridLayout(doc, at, done);
    walk(built.svg, x => assert.ok(!/[<>]/.test(x.text || ""), "svg text is plain"));
    // Every cell drawn; the search path never shows steps not yet taken.
    assert.equal(count(built.svg, "cell"), doc.bank.length, "every candidate drawn");
    assert.equal(count(built.svg, "path-dot"), at, "one dot per step taken");
    const misses = doc.steps.slice(0, at).filter(s => s.safety_miss).length;
    assert.equal(count(built.svg, "miss-ring"), misses, "every safety miss so far is ringed");
    // The solver's surface is hidden until the end (or the viewer asks).
    if (!done) assert.equal(count(built.svg, "infeasible") + count(built.svg, "safe"), 0, "truth hidden mid-replay");
    if (at > 0) {
      const v = S.stepView(doc, at - 1);
      assert.equal(v.rows.length, 3);
      assert.equal(v.safetyMiss, doc.steps[at - 1].safety_miss);
      for (const r of v.rows) assert.ok(!/[<>]/.test(r.predicted + r.truth + r.error));
    }
  }
  const r = S.resultView(doc);
  if (doc.result.false_feasible) {
    assert.match(r.title, /False-feasible/, "a false-feasible pick is named");
    assert.equal(r.regret, "No regret is priced for this outcome.", "never priced as regret");
  }
  if (doc.result.kind === "SELECTED_FEASIBLE" && doc.result.regret_s === null) assert.match(r.regret, /not defined/);
  const final = S.gridLayout(doc, n, true);
  if (doc.result.best) assert.ok(count(final.svg, "best-tag") === 1, "true best marked at the end");
  replays += 1;
}
process.stdout.write(JSON.stringify({replays}) + "\n");
