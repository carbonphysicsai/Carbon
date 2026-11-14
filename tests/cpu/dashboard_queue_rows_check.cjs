// The queue block's per-submission rows table, checked in Node without a browser (driven by tests/cpu/test_dashboard_queue.py).
// Stdin: {"panel": <the /data/queue/<slug>.json answer>}. Prints {"text": <the block's text>, "tables": n, "rows": [[cells]...]}.
"use strict";
const path = require("node:path");
const D = require(path.join(__dirname, "../../carbon/dashboard/web/dashboard.js"));
let data = "";
process.stdin.on("data", c => { data += c; });
process.stdin.on("end", () => {
  const panel = JSON.parse(data).panel;
  const block = D.queueBlock(panel);
  const rows = [];
  let tables = 0;
  D.walk(block, n => {
    if (n.tag === "table") tables += 1;
    if (n.tag === "tr" && n.children.some(c => c.tag === "td")) rows.push(n.children.map(c => D.textOf(c)));
  });
  process.stdout.write(JSON.stringify({text: D.textOf(block), tables, rows, inQueue: [0, 299, 300, 900, 3600, 5400, null].map(v => D.inQueueText(v))}));
});
