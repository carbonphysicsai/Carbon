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
  if (doc.challenge_id !== challengeId || typeof doc.challenge_version !== "string" || !ID.test(doc.challenge_version)) {
    throw new QueueRefused("queue_challenge");
  }
  if (!DOOR_STATES.includes(doc.door_state)) throw new QueueRefused("queue_door_state");
  if (!["waiting_to_build", "building_now", "waiting_to_grade"].every(k => count(doc[k])) || !count(doc.grading_now, 1)) {
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
