// Checks the dashboard Worker's door-queue reader (carbon/dashboard/worker/queue.mjs) in Node, driven by
// tests/cpu/test_dashboard_queue.py. Input on stdin: {"cases": [{"name", "text", "challenge"}], "fetches": [...]}.
// Prints {"checked": {name: {ok, value|code}}, "fetched": {name: result}}.
import {checkQueue, checkRows, doorQueue, doorRows, rowsUrl, queueUrl, QueueRefused} from "../../carbon/dashboard/worker/queue.mjs";

const input = JSON.parse(await new Promise(resolve => {
  let data = "";
  process.stdin.on("data", chunk => { data += chunk; });
  process.stdin.on("end", () => resolve(data));
}));
const checked = {};
for (const c of input.cases) {
  try {
    checked[c.name] = {ok: true, value: checkQueue(c.text, c.challenge)};
  } catch (error) {
    checked[c.name] = {ok: false, code: error instanceof QueueRefused ? error.code : "threw:" + error.message};
  }
}
const rowsChecked = {};
for (const c of input.row_cases || []) {
  try {
    rowsChecked[c.name] = {ok: true, value: checkRows(c.text, c.challenge)};
  } catch (error) {
    rowsChecked[c.name] = {ok: false, code: error instanceof QueueRefused ? error.code : "threw:" + error.message};
  }
}
const rowsFetched = {};
for (const f of input.row_fetches || []) {
  const asked = [];
  const fetcher = async (url) => {
    asked.push(url);
    if (f.throws) throw new Error("network");
    return new Response(f.body, {status: f.status});
  };
  rowsFetched[f.name] = {...await doorRows(f.feed, fetcher, {}, 60), asked};
}
const rowUrls = Object.fromEntries((input.urls || []).map(u => [u, rowsUrl(u)]));
const fetched = {};
for (const f of input.fetches) {
  const asked = [];
  const fetcher = async (url) => {
    asked.push(url);
    if (f.throws) throw new Error("network");
    return new Response(f.body, {status: f.status});
  };
  fetched[f.name] = {...await doorQueue(f.feed, fetcher, {}, 60), asked};
}
const urls = Object.fromEntries((input.urls || []).map(u => [u, queueUrl(u)]));
process.stdout.write(JSON.stringify({checked, fetched, urls, rowsChecked, rowsFetched, rowUrls}));
