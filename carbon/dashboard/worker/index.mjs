// carbon-dashboard Worker (DASHBOARD-01 D4, DASHBOARD_PLAN.md §6).
//
// Serves the static dashboard built by `python -m carbon.dashboard build` and
// keeps the leaderboard live: /data/index.json and /data/boards/<slug>.json
// and /data/v2/<slug>.json (board.v2, DASHBOARD-02 S1)
// are computed per request (edge-cached briefly) from each configured
// validator's signed score feed, fetched server-side, checked against the
// pinned feed keys and projected exactly as carbon/dashboard/feed.py does.
//
// Configuration, all as Worker secrets (never in the repository):
//   FEED_URLS  comma-separated https feed URLs (GET /carbon/v1/feed/<challenge>)
//   FEED_KEYS  comma-separated pinned validator feed public keys (64 hex)
// Optional var CACHE_SECONDS (default 60).
// Optional var CHALLENGE_NAMES: JSON object of Challenge id to display name, served at
//   /data/names.json (else the build's data/names.json, else the page title-cases the id).
//
// Fail closed:
// - a static build made from FIXTURE data is never served (503 everywhere);
// - the fixture key is never trusted;
// - a refused feed shows the last statically built board for it, marked
//   REFUSED with its reason, or nothing; never a partial board;
// - a feed URL whose door answers 404 (no feed published yet) adds no board: a Challenge named in
//   the display names then shows "Launching soon", so all the launch URLs can be set from day one.
//
// Design showcase replays stay static: they need Carbon's Python optimizer,
// so they are rebuilt and redeployed when the incumbent changes.

import {FETCH_HEADERS, FeedRefused, boardSlug, entry, panelSummary, parse, project, projectV2, restamp, trust} from "./feed.mjs";
// DASHBOARD-02 S3: /data/network.json from the signed network snapshots in
// the optional secret SNAPSHOT_URLS, checked against FEED_KEYS (404 unset).
import {liveNetwork} from "./snapshot.mjs";
// The door queue panel: /data/queue/<slug>.json from each door's public, unsigned queue document (queue.mjs).
import {doorQueue, queueUrl} from "./queue.mjs";

const INDEX_SCHEMA = "carbon.dashboard.index.v1";
const MAX_FEED_BYTES = 16 * 2 ** 20;
const SECURITY_HEADERS = {
  "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
  "X-Frame-Options": "DENY",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
};

function withHeaders(response, extra = {}) {
  const out = new Response(response.body, response);
  for (const [k, v] of Object.entries({...SECURITY_HEADERS, ...extra})) out.headers.set(k, v);
  return out;
}
function json(value, status = 200, seconds = 0) {
  return withHeaders(new Response(JSON.stringify(value) + "\n", {status, headers: {"Content-Type": "application/json; charset=utf-8"}}),
    {"Cache-Control": seconds ? `public, max-age=${seconds}` : "no-store"});
}
function plain(text, status) {
  return withHeaders(new Response(text + "\n", {status, headers: {"Content-Type": "text/plain; charset=utf-8"}}), {"Cache-Control": "no-store"});
}
async function asset(env, request, path) {
  const response = await env.ASSETS.fetch(new Request(new URL(path, request.url), {method: "GET"}));
  if (!response.ok) return null;
  try { return await response.json(); } catch { return null; }
}
const list = value => String(value || "").split(",").map(s => s.trim()).filter(Boolean);

// The optional var CHALLENGE_NAMES: a JSON object of Challenge id to display name (a plain label,
// as build.py's NAME_PATTERN). Anything else is ignored, so the page shows the title-cased id.
// A value may also be {name, status, door, about, order} (build.py STATUS_PATTERN, ABOUT_PATTERN, DOOR_PATTERN).
const NAME_PATTERN = /^[A-Za-z0-9][A-Za-z0-9 ._&'+-]{0,39}$/;
const STATUS_PATTERN = /^[A-Za-z0-9][A-Za-z0-9 ._&'+:,-]{0,59}$/;
const ABOUT_PATTERN = /^[A-Za-z0-9][A-Za-z0-9 ._&'+:,()\/-]{0,89}$/;
const DOOR_PATTERN = /^https:\/\/[A-Za-z0-9.-]+(:\d{1,5})?(\/[A-Za-z0-9._~\/-]*)?$/;
export function liveNames(env) {
  if (!env.CHALLENGE_NAMES) return null;
  try {
    const given = JSON.parse(env.CHALLENGE_NAMES);
    if (!given || typeof given !== "object" || Array.isArray(given)) return null;
    const names = {};
    for (const [id, value] of Object.entries(given)) {
      const entry = value && typeof value === "object" && !Array.isArray(value);
      const name = entry ? value.name : value;
      if (typeof name !== "string" || !NAME_PATTERN.test(name)) return null;
      if (entry) {
        if (Object.keys(value).some(k => !["name", "status", "door", "about", "order"].includes(k))) return null;
        if (value.status !== undefined && !(typeof value.status === "string" && STATUS_PATTERN.test(value.status))) return null;
        if (value.about !== undefined && !(typeof value.about === "string" && ABOUT_PATTERN.test(value.about))) return null;
        if (value.order !== undefined && !(Number.isSafeInteger(value.order) && value.order >= 1 && value.order <= 99)) return null;
        if (value.door !== undefined && !(typeof value.door === "string" && DOOR_PATTERN.test(value.door))) return null;
      }
      names[id] = value;
    }
    return Object.keys(names).length ? {schema: "carbon.dashboard.names.v1", names} : null;
  } catch { return null; }
}

export function config(env) {
  const urls = list(env.FEED_URLS);
  if (!urls.length || urls.some(u => !u.startsWith("https://"))) throw new FeedRefused("feed_not_configured");
  let pinned;
  try { pinned = trust(list(env.FEED_KEYS)); } catch { throw new FeedRefused("feed_keys_invalid"); }
  const seconds = Math.max(0, Math.min(600, Number(env.CACHE_SECONDS ?? 60) || 0));
  return {urls, pinned, seconds};
}

async function fetchFeed(url, seconds, fetcher) {
  const response = await fetcher(url, {headers: FETCH_HEADERS, cf: {cacheTtl: seconds, cacheEverything: true}, signal: AbortSignal.timeout(15000)});
  // 404: the validator's door serves no feed for this Challenge yet. The Challenge then shows as
  // "Launching soon" (liveSite skips it); any other failure is shown as a refused card.
  if (response.status === 404) throw new FeedRefused("feed_not_published");
  if (!response.ok) throw new FeedRefused("feed_unavailable", String(response.status));
  const body = await response.text();
  if (body.length > MAX_FEED_BYTES) throw new FeedRefused("feed_too_large");
  return parse(body);
}

// Every board, as build.py's index and boards, from the live feeds.
export async function liveSite(env, request, fetcher = fetch, now = Math.floor(Date.now() / 1000)) {
  const {urls, pinned} = config(env);
  const seconds = config(env).seconds;
  const entries = new Map();
  const boards = new Map();
  const boardsV2 = new Map();
  let n = 0;
  for (const url of urls) {
    let document = null;
    try {
      document = await fetchFeed(url, seconds, fetcher);
      const board = await project(document, pinned);
      if (boards.has(board.slug)) throw new FeedRefused("duplicate_board");
      board.feed_state = {state: "ACCEPTED", code: null};
      board.showcase_panel = panelSummary(board.showcase_panel);
      boards.set(board.slug, board);
      boardsV2.set(board.slug, {...projectV2(board, now), feed_state: board.feed_state});
      entries.set(board.slug, entry(board));
    } catch (error) {
      if (error instanceof FeedRefused && error.code === "feed_not_published") { n += 1; continue; }
      const code = error instanceof FeedRefused ? error.code : "feed_unavailable";
      let slug = null;
      try {
        const deviceClass = document.device_class || (document.submissions?.[0]?.device_class) || "no-class";
        slug = boardSlug(document.challenge.id, deviceClass);
      } catch { slug = null; }
      const previous = slug && !boards.has(slug) ? await asset(env, request, `/data/boards/${slug}.json`) : null;
      if (previous && previous.fixture === false) {
        previous.feed_state = {state: "REFUSED", code};
        boards.set(slug, previous);
        entries.set(slug, entry(previous));
        const kept = await asset(env, request, `/data/v2/${slug}.json`);
        if (kept && kept.fixture === false) boardsV2.set(slug, {...restamp(kept, now), feed_state: previous.feed_state});
      } else {
        entries.set(slug && !entries.has(slug) ? slug : `unreadable-${n}`, {slug: null, state: "REFUSED", code});
      }
    }
    n += 1;
  }
  const keys = [...entries.keys()].sort();
  return {index: {schema: INDEX_SCHEMA, fixture: false, boards: keys.map(k => entries.get(k))}, boards, boardsV2};
}

export default {
  async fetch(request, env, ctx) {
    if (request.method !== "GET" && request.method !== "HEAD") return plain("Method not allowed", 405);
    const url = new URL(request.url);
    const built = await asset(env, request, "/data/index.json");
    if (!built || built.fixture !== false) {
      return plain("This build is not servable: it carries fixture data or no production index.", 503);
    }
    const v2 = url.pathname.startsWith("/data/v2/");
    if (url.pathname === "/data/index.json" || url.pathname.startsWith("/data/boards/") || v2) {
      let site;
      try {
        site = await liveSite(env, request);
      } catch (error) {
        return plain("Feed not configured: " + (error.code || "error"), 503);
      }
      const seconds = config(env).seconds;
      // No signed network snapshot is served yet (S3), so the page never asks.
      if (url.pathname === "/data/index.json") return json({...site.index, brand_assets: built.brand_assets || [], network: false, showcase: built.showcase !== false}, 200, seconds);
      const prefix = v2 ? "/data/v2/" : "/data/boards/";
      const slug = decodeURIComponent(url.pathname.slice(prefix.length)).replace(/\.json$/, "");
      const board = (v2 ? site.boardsV2 : site.boards).get(slug);
      return board ? json(board, 200, seconds) : plain("No such board", 404);
    }
    if (url.pathname === "/data/names.json") {
      const names = liveNames(env) ?? await asset(env, request, "/data/names.json");
      return names ? json(names, 200, Math.max(0, Math.min(600, Number(env.CACHE_SECONDS ?? 60) || 0))) : plain("No display names", 404);
    }
    if (url.pathname === "/data/network.json") {
      let network;
      try { network = await liveNetwork(env); } catch (error) { return plain("Network snapshot not configured: " + (error.code || "error"), 503); }
      return network ? json(network.view, 200, network.seconds) : plain("Network snapshot not configured", 404);
    }
    if (url.pathname.startsWith("/data/queue/")) {
      let cfg;
      try { cfg = config(env); } catch (error) { return plain("Feed not configured: " + (error.code || "error"), 503); }
      const slug = decodeURIComponent(url.pathname.slice("/data/queue/".length)).replace(/\.json$/, "");
      const feed = cfg.urls.find(u => { const q = queueUrl(u); return q && boardSlug(q.challengeId, "no-class") === slug; });
      if (!feed) return plain("No such board", 404);
      return json(await doorQueue(feed, fetch, FETCH_HEADERS, cfg.seconds), 200, cfg.seconds);
    }
    if (url.pathname.startsWith("/data/")) return plain("Not found", 404);
    return withHeaders(await env.ASSETS.fetch(request));
  },
};
