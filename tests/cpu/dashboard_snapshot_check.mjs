// Drives the dashboard Worker's network snapshot reader in Node (DASHBOARD-02
// S3), for tests/cpu/test_dashboard_snapshot.py. Argument: a JSON spec file.
// Prints JSON.
//
// mode "project": {now_ms, items: [{text, fixture, keys, max_age}]} ->
//   [{view} | {code}], snapshot.mjs's projection, for parity with snapshot.py.
// mode "feed": {items: [{text, fixture, keys}]} -> [{board} | {code}], the
//   feed reader's projection, for the domain separation check.
// mode "worker": {site, env, feeds: {url: text}, requests: [path]} ->
//   [{path, status, headers, body}], the fetch handler over a site directory.
import fs from "node:fs";
import path from "node:path";

const feed = await import(new URL("../../carbon/dashboard/worker/feed.mjs", import.meta.url));
const snapshot = await import(new URL("../../carbon/dashboard/worker/snapshot.mjs", import.meta.url));
const worker = (await import(new URL("../../carbon/dashboard/worker/index.mjs", import.meta.url))).default;
const spec = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));

if (spec.mode === "project") {
  const out = [];
  for (const item of spec.items) {
    try {
      const pinned = feed.trust(item.keys, {fixture: item.fixture});
      const options = {nowMs: spec.now_ms, maxAgeSeconds: item.max_age ?? snapshot.MAX_AGE_SECONDS};
      out.push({view: await snapshot.project(feed.parse(item.text), pinned, options)});
    } catch (error) {
      if (!(error instanceof snapshot.SnapshotRefused)) throw error;
      out.push({code: error.code});
    }
  }
  process.stdout.write(JSON.stringify(out));
} else if (spec.mode === "feed") {
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
