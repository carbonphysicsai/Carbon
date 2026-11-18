// Checks the dashboard Worker's door-queue reader (carbon/dashboard/worker/queue.mjs) in Node, driven by
// tests/cpu/test_dashboard_queue.py. Input on stdin: {"cases": [{"name", "text", "challenge"}], "fetches": [...]}.
// Prints {"checked": {name: {ok, value|code}}, "fetched": {name: result}}.
import {checkQueue, checkQueueV4, checkRows, doorPanels, doorQueue, doorRows, rowsUrl, queueUrl, v4Url, QueueRefused} from "../../carbon/dashboard/worker/queue.mjs";

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
// v4 (owner Q15): the closed document, and the panels a /data/queue answer is built from. A panel fetch answers by the
// asked path's ending ("/v4", "/v3" or "" for v1): {status, body} or {throws: true}.
const v4Checked = {};
for (const c of input.v4_cases || []) {
  try {
    v4Checked[c.name] = {ok: true, value: checkQueueV4(c.text, c.challenge)};
  } catch (error) {
    v4Checked[c.name] = {ok: false, code: error instanceof QueueRefused ? error.code : "threw:" + error.message};
  }
}
const panels = {};
for (const f of input.panel_fetches || []) {
  const asked = [];
  const fetcher = async (url) => {
    asked.push(url);
    const end = url.endsWith("/v4") ? "/v4" : url.endsWith("/v3") ? "/v3" : "";
    const answer = f.responses[end];
    if (!answer || answer.throws) throw new Error("network");
    return new Response(answer.body, {status: answer.status});
  };
  panels[f.name] = {...await doorPanels(f.feed, fetcher, {}, 60), asked};
}
const v4Urls = Object.fromEntries((input.urls || []).map(u => [u, v4Url(u)]));
process.stdout.write(JSON.stringify({checked, fetched, urls, rowsChecked, rowsFetched, rowUrls, v4Checked, panels, v4Urls}));
