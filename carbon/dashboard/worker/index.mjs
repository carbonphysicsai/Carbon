// carbon-dashboard Worker (DASHBOARD-01 D4, DASHBOARD_PLAN.md §6).
//
// Serves the static dashboard built by `python -m carbon.dashboard build` and
// keeps the leaderboard live: /data/index.json and /data/boards/<slug>.json
// are computed per request (edge-cached briefly) from each configured
// validator's signed score feed, fetched server-side, checked against the
// pinned feed keys and projected exactly as carbon/dashboard/feed.py does.
//
// Configuration, all as Worker secrets (never in the repository):
//   FEED_URLS  comma-separated https feed URLs (GET /carbon/v1/feed/<challenge>)
//   FEED_KEYS  comma-separated pinned validator feed public keys (64 hex)
// Optional var CACHE_SECONDS (default 60).
//
// Fail closed:
// - a static build made from FIXTURE data is never served (503 everywhere);
// - the fixture key is never trusted;
// - a refused feed shows the last statically built board for it, marked
//   REFUSED with its reason, or nothing; never a partial board.
//
// Design showcase replays stay static: they need Carbon's Python optimizer,
// so they are rebuilt and redeployed when the incumbent changes.

import {FeedRefused, boardSlug, entry, panelSummary, parse, project, trust} from "./feed.mjs";

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

export function config(env) {
  const urls = list(env.FEED_URLS);
  if (!urls.length || urls.some(u => !u.startsWith("https://"))) throw new FeedRefused("feed_not_configured");
  let pinned;
  try { pinned = trust(list(env.FEED_KEYS)); } catch { throw new FeedRefused("feed_keys_invalid"); }
  const seconds = Math.max(0, Math.min(600, Number(env.CACHE_SECONDS ?? 60) || 0));
  return {urls, pinned, seconds};
}

async function fetchFeed(url, seconds, fetcher) {
  const response = await fetcher(url, {cf: {cacheTtl: seconds, cacheEverything: true}, signal: AbortSignal.timeout(15000)});
  if (!response.ok) throw new FeedRefused("feed_unavailable", String(response.status));
  const body = await response.text();
  if (body.length > MAX_FEED_BYTES) throw new FeedRefused("feed_too_large");
  return parse(body);
}

// Every board, as build.py's index and boards, from the live feeds.
export async function liveSite(env, request, fetcher = fetch) {
  const {urls, pinned} = config(env);
  const seconds = config(env).seconds;
  const entries = new Map();
  const boards = new Map();
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
      entries.set(board.slug, entry(board));
    } catch (error) {
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
      } else {
        entries.set(slug && !entries.has(slug) ? slug : `unreadable-${n}`, {slug: null, state: "REFUSED", code});
      }
    }
    n += 1;
  }
  const keys = [...entries.keys()].sort();
  return {index: {schema: INDEX_SCHEMA, fixture: false, boards: keys.map(k => entries.get(k))}, boards};
}

export default {
  async fetch(request, env, ctx) {
    if (request.method !== "GET" && request.method !== "HEAD") return plain("Method not allowed", 405);
    const url = new URL(request.url);
    const built = await asset(env, request, "/data/index.json");
    if (!built || built.fixture !== false) {
      return plain("This build is not servable: it carries fixture data or no production index.", 503);
    }
    if (url.pathname === "/data/index.json" || url.pathname.startsWith("/data/boards/")) {
      let site;
      try {
        site = await liveSite(env, request);
      } catch (error) {
        return plain("Feed not configured: " + (error.code || "error"), 503);
      }
      const seconds = config(env).seconds;
      if (url.pathname === "/data/index.json") return json({...site.index, brand_assets: built.brand_assets || []}, 200, seconds);
      const slug = decodeURIComponent(url.pathname.slice("/data/boards/".length)).replace(/\.json$/, "");
      const board = site.boards.get(slug);
      return board ? json(board, 200, seconds) : plain("No such board", 404);
    }
    if (url.pathname.startsWith("/data/")) return plain("Not found", 404);
    return withHeaders(await env.ASSETS.fetch(request));
  },
};
