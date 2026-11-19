// The door queue panel (owner 6 Nov: "We need this and the Dashboard upgrade that shows the Queue information going
// asap"). Each door serves a public, read-only queue document at GET /carbon/v1/queue/<challenge_id>
// (carbon/challenge_validator/queue_public.py, schema carbon.queue.public.v1): COUNTS and the door's state in plain
// words, nothing else. The Worker fetches it from the same door as the board's feed (FEED_URLS: /carbon/v1/feed/<id>
// -> /carbon/v1/queue/<id>), checks its closed shape exactly as queue_public.py writes it, and serves
// /data/queue/<slug>.json as {state, code, queue}. The document is NOT signed: the page labels it "reported by the door".
//
// Fail closed: a door that serves no queue yet -> {state: "NOT_SERVED"}; anything that is not exactly the closed shape
// -> {state: "UNAVAILABLE", code}; never a partial document.

export const QUEUE_SCHEMA = "carbon.queue.public.v1";
export const DOOR_STATES = ["grading", "paused", "draining for an update", "re-measuring the king"];
const MAX_QUEUE_BYTES = 4096;
const FIELDS = ["as_of", "building_now", "challenge_id", "challenge_version", "door_state", "grading_now", "schema",
  "wait_24h", "waiting_to_build", "waiting_to_grade"];
const WAIT_FIELDS = ["median_s", "p90_s", "reason", "verdicts"];
const TOO_FEW = "fewer_than_5_verdicts_in_24h";
const UTC = /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/u;
const ID = /^[^\u0000-\u001f\u007f<>]{1,200}$/u;
const MAX_COUNT = 10 ** 7;

export class QueueRefused extends Error {
  constructor(code) { super(code); this.code = code; }
}
const isDict = v => v !== null && typeof v === "object" && !Array.isArray(v);
const sameKeys = (o, names) => isDict(o) && Object.keys(o).sort().join("\u0000") === [...names].sort().join("\u0000");
const count = (v, max = MAX_COUNT) => Number.isSafeInteger(v) && v >= 0 && v <= max;
const seconds = v => v === null || (typeof v === "number" && Number.isFinite(v) && v >= 0);

// The closed queue document, or QueueRefused: the shape queue_public.document writes, for THIS Challenge.
export function checkQueue(text, challengeId) {
  if (typeof text !== "string" || text.length > MAX_QUEUE_BYTES) throw new QueueRefused("queue_too_large");
  let doc;
  try { doc = JSON.parse(text); } catch { throw new QueueRefused("queue_not_json"); }
  if (!sameKeys(doc, FIELDS) || doc.schema !== QUEUE_SCHEMA) throw new QueueRefused("queue_fields");
  return checkCounts(doc, challengeId, 1);
}

// The counts and the door state of a parsed queue document (v1's checks); `gradingMax` 1 for v1's 0/1 flag.
function checkCounts(doc, challengeId, gradingMax) {
  if (doc.challenge_id !== challengeId || typeof doc.challenge_version !== "string" || !ID.test(doc.challenge_version)) {
    throw new QueueRefused("queue_challenge");
  }
  if (!DOOR_STATES.includes(doc.door_state)) throw new QueueRefused("queue_door_state");
  if (!["waiting_to_build", "building_now", "waiting_to_grade"].every(k => count(doc[k])) || !count(doc.grading_now, gradingMax)) {
    throw new QueueRefused("queue_counts");
  }
  const w = doc.wait_24h;
  if (!sameKeys(w, WAIT_FIELDS) || !count(w.verdicts) || !seconds(w.median_s) || !seconds(w.p90_s)
      || (w.reason !== null && w.reason !== TOO_FEW)
      || ((w.reason === TOO_FEW) !== (w.median_s === null)) || ((w.median_s === null) !== (w.p90_s === null))) {
    throw new QueueRefused("queue_wait");
  }
  if (typeof doc.as_of !== "string" || !UTC.test(doc.as_of)) throw new QueueRefused("queue_time");
  return {
    challenge_id: doc.challenge_id, challenge_version: doc.challenge_version, door_state: doc.door_state,
    waiting_to_build: doc.waiting_to_build, building_now: doc.building_now, waiting_to_grade: doc.waiting_to_grade,
    grading_now: doc.grading_now, as_of: doc.as_of,
    wait_24h: {verdicts: w.verdicts, median_s: w.median_s, p90_s: w.p90_s, reason: w.reason},
  };
}

// The queue URL of a feed URL: same door, /carbon/v1/feed/<id> -> /carbon/v1/queue/<id>; null for any other shape.
export function queueUrl(feedUrl) {
  let url;
  try { url = new URL(feedUrl); } catch { return null; }
  const m = /^\/carbon\/v1\/feed\/([^/]+)$/u.exec(url.pathname);
  if (url.protocol !== "https:" || !m) return null;
  return {url: `${url.origin}/carbon/v1/queue/${m[1]}`, challengeId: decodeURIComponent(m[1])};
}

// ---- the per-submission rows (owner 14 Nov: "show the actual queue"): GET /carbon/v1/queue/<id>/v3 =
// carbon.queue.public.v3 (queue_public.py document_v3): v2's closed fields plus `rows` (at most 100: position, short hotkey, state,
// time in queue), `more_rows` and `rows_as_of`. A row says WHERE a submission waits, never WHAT it is. The rows are rebuilt by the
// door only on a 300 s wall-clock boundary and every time is floored to it (the timing mitigation lives at the door). Checked
// exactly here too; anything else -> {state: "UNAVAILABLE", code}, a door with no v3 yet -> {state: "NOT_SERVED"}.
export const ROWS_SCHEMA = "carbon.queue.public.v3";
// "in grading" = built, no verdict yet (waiting to be graded or being graded: not told apart per row, V2C 14 Nov).
export const ROW_STATES = ["waiting to build", "building", "in grading", "crown check"];
// v4 rows (queue_public.py ROW_STATES_V4, Lead 19 Nov 2026): a built row is "grading" only while its grade runs, else
// "waiting to grade". A v4 document still carrying "in grading" (a door before that fix) is refused: v1 + v3 as before.
export const ROW_STATES_V4 = ["waiting to build", "building", "waiting to grade", "grading", "crown check"];
export const ROWS_QUANTUM_S = 300;
// held equal to the door's queue_public.MAX_ROWS / MAX_BYTES_V3 (all rows, Lead 15 Nov)
export const MAX_ROWS = 1000;
export const MAX_ROWS_BYTES = 131072;
const FIELDS_V3 = [...FIELDS, "held_for_review", "more_rows", "rows", "rows_as_of"];
const ROW_FIELDS = ["hotkey", "in_queue_s", "position", "state"];
const SHORT_KEY = /^[1-9A-HJ-NP-Za-km-z]{4}\u2026[1-9A-HJ-NP-Za-km-z]{4}$/u;

// {rows: [...], more_rows, rows_as_of} from the closed v3 document for THIS Challenge, or QueueRefused.
export function checkRows(text, challengeId) {
  if (typeof text !== "string" || text.length > MAX_ROWS_BYTES) throw new QueueRefused("rows_too_large");
  let doc;
  try { doc = JSON.parse(text); } catch { throw new QueueRefused("rows_not_json"); }
  if (!sameKeys(doc, FIELDS_V3) || doc.schema !== ROWS_SCHEMA) throw new QueueRefused("rows_fields");
  return checkRowList(doc, challengeId);
}

// {rows, more_rows, rows_as_of} of a parsed v3-shaped document (v3's checks; `states`: the row states allowed).
function checkRowList(doc, challengeId, states = ROW_STATES) {
  if (doc.challenge_id !== challengeId) throw new QueueRefused("rows_challenge");
  if (typeof doc.rows_as_of !== "string" || !UTC.test(doc.rows_as_of)) throw new QueueRefused("rows_time");
  if (!count(doc.more_rows) || !Array.isArray(doc.rows) || doc.rows.length > MAX_ROWS) throw new QueueRefused("rows_count");
  const rows = doc.rows.map((row, i) => {
    if (!sameKeys(row, ROW_FIELDS) || row.position !== i + 1 || !states.includes(row.state)
        || !(row.hotkey === null || (typeof row.hotkey === "string" && SHORT_KEY.test(row.hotkey)))
        || !Number.isSafeInteger(row.in_queue_s) || row.in_queue_s < 0 || row.in_queue_s % ROWS_QUANTUM_S !== 0) {
      throw new QueueRefused("rows_row");
    }
    return {position: row.position, hotkey: row.hotkey, state: row.state, in_queue_s: row.in_queue_s};
  });
  return {rows, more_rows: doc.more_rows, rows_as_of: doc.rows_as_of};
}

// The rows URL of a feed URL: same door, /carbon/v1/feed/<id> -> /carbon/v1/queue/<id>/v3; null for any other shape.
export function rowsUrl(feedUrl) {
  const base = queueUrl(feedUrl);
  return base === null ? null : {url: base.url + "/v3", challengeId: base.challengeId};
}

// {state, code, rows} for one feed URL's door; never throws. 404 = the door has no v3 yet (counts still come from doorQueue).
export async function doorRows(feedUrl, fetcher, headers, ttl) {
  const target = rowsUrl(feedUrl);
  if (!target) return {state: "UNAVAILABLE", code: "rows_url", rows: null};
  try {
    const response = await fetcher(target.url, {headers, cf: {cacheTtl: ttl, cacheEverything: true}, signal: AbortSignal.timeout(8000)});
    if (response.status === 404) return {state: "NOT_SERVED", code: null, rows: null};
    if (!response.ok) return {state: "UNAVAILABLE", code: "rows_http_" + response.status, rows: null};
    return {state: "ACCEPTED", code: null, rows: checkRows(await response.text(), target.challengeId)};
  } catch (error) {
    return {state: "UNAVAILABLE", code: error instanceof QueueRefused ? error.code : "rows_unreachable", rows: null};
  }
}

// {state, code, queue} for one feed URL's door; never throws.
export async function doorQueue(feedUrl, fetcher, headers, ttl) {
  const target = queueUrl(feedUrl);
  if (!target) return {state: "UNAVAILABLE", code: "queue_url", queue: null};
  try {
    const response = await fetcher(target.url, {headers, cf: {cacheTtl: ttl, cacheEverything: true}, signal: AbortSignal.timeout(8000)});
    if (response.status === 404) return {state: "NOT_SERVED", code: null, queue: null};
    if (!response.ok) return {state: "UNAVAILABLE", code: "queue_http_" + response.status, queue: null};
    return {state: "ACCEPTED", code: null, queue: checkQueue(await response.text(), target.challengeId)};
  } catch (error) {
    return {state: "UNAVAILABLE", code: error instanceof QueueRefused ? error.code : "queue_unreachable", queue: null};
  }
}

// ---- v4 (owner Q15, 18 Nov 2026: "grading now" showed none while 4 grades ran): GET /carbon/v1/queue/<id>/v4 =
// carbon.queue.public.v4 (queue_public.py document_v4): v3's closed field set and rows, with the counts read from what actually
// runs: building_now = builds holding a build slot, waiting_to_build = every other unfinished build, grading_now = the NUMBER of
// grades in flight (not v1's 0/1 flag), waiting_to_grade = built and not claimed. One fetch gives both panels. A door with no v4
// yet (404), or a v4 refused, -> the v1 counts + v3 rows path as before, so the board never goes blank for v4's sake.
export const V4_SCHEMA = "carbon.queue.public.v4";

// {queue, rows} from the closed v4 document for THIS Challenge, or QueueRefused.
export function checkQueueV4(text, challengeId) {
  if (typeof text !== "string" || text.length > MAX_ROWS_BYTES) throw new QueueRefused("v4_too_large");
  let doc;
  try { doc = JSON.parse(text); } catch { throw new QueueRefused("v4_not_json"); }
  if (!sameKeys(doc, FIELDS_V3) || doc.schema !== V4_SCHEMA) throw new QueueRefused("v4_fields");
  return {queue: checkCounts(doc, challengeId, MAX_COUNT), rows: checkRowList(doc, challengeId, ROW_STATES_V4)};
}

// The v4 URL of a feed URL: same door, /carbon/v1/feed/<id> -> /carbon/v1/queue/<id>/v4; null for any other shape.
export function v4Url(feedUrl) {
  const base = queueUrl(feedUrl);
  return base === null ? null : {url: base.url + "/v4", challengeId: base.challengeId};
}

// {state, code, queue, rows} for one feed URL's door from its v4 document; never throws. 404 = no v4 yet.
export async function doorQueueV4(feedUrl, fetcher, headers, ttl) {
  const target = v4Url(feedUrl);
  if (!target) return {state: "UNAVAILABLE", code: "v4_url", queue: null, rows: null};
  try {
    const response = await fetcher(target.url, {headers, cf: {cacheTtl: ttl, cacheEverything: true}, signal: AbortSignal.timeout(8000)});
    if (response.status === 404) return {state: "NOT_SERVED", code: null, queue: null, rows: null};
    if (!response.ok) return {state: "UNAVAILABLE", code: "v4_http_" + response.status, queue: null, rows: null};
    return {state: "ACCEPTED", code: null, ...checkQueueV4(await response.text(), target.challengeId)};
  } catch (error) {
    return {state: "UNAVAILABLE", code: error instanceof QueueRefused ? error.code : "v4_unreachable", queue: null, rows: null};
  }
}

// The /data/queue/<slug>.json body for one feed URL's door: {state, code, queue, counts, rows_panel}. `counts` says what
// the numbers count: "running" (v4) or "tasks" (v1: a RUNNING task waiting for a slot counts as building; grading 0/1).
export async function doorPanels(feedUrl, fetcher, headers, ttl) {
  const v4 = await doorQueueV4(feedUrl, fetcher, headers, ttl);
  if (v4.state === "ACCEPTED") {
    return {state: "ACCEPTED", code: null, queue: v4.queue, counts: "running",
      rows_panel: {state: "ACCEPTED", code: null, rows: v4.rows}};
  }
  const [counts, rows] = await Promise.all([doorQueue(feedUrl, fetcher, headers, ttl), doorRows(feedUrl, fetcher, headers, ttl)]);
  return {...counts, counts: "tasks", rows_panel: rows};
}
