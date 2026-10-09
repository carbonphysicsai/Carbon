// Drives the dashboard Worker's modules in Node (DASHBOARD-01 D4), for
// tests/cpu/test_dashboard_worker.py. Argument: a JSON spec file. Prints JSON.
//
// mode "project": [{text, fixture, keys}] -> [{board} | {code}], the Worker's
//   projection of each served feed text, for parity with feed.py.
// mode "worker": {site, env, feeds: {url: text}, requests: [path]} ->
//   [{path, status, headers, body}], the fetch handler over a built site.
import fs from "node:fs";
import path from "node:path";

const feed = await import(new URL("../../carbon/dashboard/worker/feed.mjs", import.meta.url));
const worker = (await import(new URL("../../carbon/dashboard/worker/index.mjs", import.meta.url))).default;
const spec = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));

if (spec.mode === "project") {
  const out = [];
  for (const item of spec.items) {
    try {
      const pinned = feed.trust(item.keys, {fixture: item.fixture});
      out.push({board: await feed.project(feed.parse(item.text), pinned)});
    } catch (error) {
      if (!(error instanceof feed.FeedRefused)) throw error;
      out.push({code: error.code});
    }
  }
  process.stdout.write(JSON.stringify(out));
} else {
  const site = spec.site;
  const ASSETS = {
    async fetch(request) {
      const url = new URL(request.url);
      const file = path.join(site, decodeURIComponent(url.pathname === "/" ? "/index.html" : url.pathname));
      if (!file.startsWith(site) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return new Response("missing", {status: 404});
      return new Response(fs.readFileSync(file), {status: 200});
    },
  };
  const realFetch = globalThis.fetch;
  globalThis.fetch = async url => (url in spec.feeds ? new Response(spec.feeds[url], {status: 200}) : new Response("down", {status: 502}));
  const out = [];
  for (const p of spec.requests) {
    const response = await worker.fetch(new Request("https://dashboard.example" + p), {...spec.env, ASSETS}, {});
    const body = await response.text();
    out.push({path: p, status: response.status, headers: Object.fromEntries(response.headers), body});
  }
  globalThis.fetch = realFetch;
  process.stdout.write(JSON.stringify(out));
}
