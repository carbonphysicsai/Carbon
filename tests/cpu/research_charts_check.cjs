// Draws chart documents with the Control Center's renderer, without a browser.
// Reads a JSON list of charts on stdin; prints {"drawn": n}. Used by
// tests/cpu/test_research_surface.py when Node is installed (RSURF-D8).
"use strict";
const assert = require("node:assert/strict");
const path = require("node:path");
const charts = require(path.join(__dirname, "../../scripts/dev/miner_launchpad/research_charts.js"));

// The smallest document the renderer needs: elements with attributes,
// children and text. No HTML parser exists here, so none can be used.
function fakeDocument() {
  function element(tag) {
    return {
      tag, attributes: {}, children: [], textContent: "", className: "", dataset: {}, hidden: false, listeners: {},
      setAttribute(k, v) { this.attributes[k] = String(v); },
      append(...nodes) { this.children.push(...nodes); },
      addEventListener(type, fn) { this.listeners[type] = fn; },
      getBoundingClientRect() { return {left: 0, width: 480}; },
    };
  }
  return {createElement: element, createElementNS: (_ns, tag) => element(tag)};
}
function walk(node, visit) { visit(node); for (const child of node.children || []) walk(child, visit); }

let input = "";
process.stdin.on("data", chunk => { input += chunk; });
process.stdin.on("end", () => {
  // A shell may prefix a byte-order mark; it is not part of the document.
  const specs = JSON.parse(input.replace(/^\ufeff/, ""));
  const kinds = new Set();
  for (const spec of specs) {
    const built = charts.layout(spec);
    const marks = {path: 0, circle: 0, rect: 0, text: 0};
    walk(built.svg, n => { if (n.tag in marks) marks[n.tag] += 1; });
    if (spec.kind === "time_series" || spec.kind === "checkpoint_vector") assert.ok(marks.path >= 1, spec.id + " draws lines");
    if (spec.kind === "scalar") assert.ok(marks.circle >= 1, spec.id + " draws dots");
    if (spec.kind === "field_2d" || spec.kind === "bars") assert.ok(marks.rect >= 1, spec.id + " draws cells or bars");
    assert.ok(marks.text >= 1, spec.id + " labels itself");
    // Every label is text: no attribute or text carries markup.
    walk(built.svg, n => { assert.ok(!/[<>]/.test(n.text || ""), spec.id + " text is plain"); });
    const figure = charts.render(spec, fakeDocument());
    assert.equal(figure.dataset.kind, spec.kind);
    const table = charts.table(spec);
    assert.equal(table.rows.length, spec.series.length);
    kinds.add(spec.kind);
  }
  // A chart kind the renderer does not know is refused, never guessed.
  assert.throws(() => charts.layout({kind: "pie", series: [{}]}));
  process.stdout.write(JSON.stringify({drawn: specs.length, kinds: [...kinds].sort()}));
});
