// The dashboard Worker's network snapshot reader: a port of
// carbon/dashboard/snapshot.py (DASHBOARD-02 S3).
//
// The validator host publishes a signed snapshot of the subnet's public state
// (UIDs, hotkeys, incentive, emission, validator permits, stake) beside its
// score feed. The Worker fetches it server-side, checks the Ed25519 signature
// under the snapshot's own domain against the pinned feed keys, and keeps
// only the allow-listed fields, exactly as snapshot.py does.
// tests/cpu/test_dashboard_snapshot.py holds the two equal.
//
// Emission and stake are rao amounts that can exceed a JavaScript number's
// exact range, so they are read from the number's source text (feed.mjs's
// `parse`) and returned as decimal strings, as snapshot.py does.

import {FIXTURE_PUBLIC_KEY, Num, canonical, parse, trust} from "./feed.mjs";

export const SCHEMA = "carbon.validator.network-snapshot.v1";
export const VIEW_SCHEMA = "carbon.dashboard.network.v1";
export const INDEX_SCHEMA = "carbon.dashboard.network-index.v1";
export const DOMAIN = "carbon.validator.network-snapshot.v1\u0000";
export {FIXTURE_PUBLIC_KEY};
const LABELS = ["DEVELOPMENT", "TESTNET"];
const FIXTURE_LABEL = "FIXTURE";
const NETWORKS = ["testnet", "mainnet"];
const UNITS = {incentive: "u16", emission: "rao", stake: "rao"};
export const MAX_AGE_SECONDS = 1800;
const MIN_MAX_AGE_SECONDS = 60;
const MAX_MAX_AGE_SECONDS = 86400;
const FUTURE_SKEW_SECONDS = 300;
const MAX_NEURONS = 4096;
const U16 = 65535;
const MAX_SNAPSHOT_BYTES = 4 * 2 ** 20;

const SS58 = /^[1-9A-HJ-NP-Za-km-z]{46,48}$/u;
const FIXTURE_HOTKEY = /^fixture-[a-z0-9-]{1,32}$/u;
const HASH = /^0x[0-9a-f]{64}$/u;
const HEX_SIGNATURE = /^[0-9a-f]{128}$/u;
const TEXT = /^[^\u0000-\u001f\u007f<>]{1,200}$/u;
const UINT = /^(?:0|[1-9]\d*)$/u;

export class SnapshotRefused extends Error {
  constructor(code, detail = "") {
    super(detail ? `${code}: ${detail}` : code);
    this.code = code;
  }
}

const isNum = v => v instanceof Num;
const isDict = v => v !== null && typeof v === "object" && !Array.isArray(v) && !isNum(v);
const own = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
const get = (o, k) => (isDict(o) && own(o, k) ? o[k] : null);
const hexBytes = hex => Uint8Array.from(hex.match(/../g).map(h => parseInt(h, 16)));
const toHex = buf => Array.from(new Uint8Array(buf), b => b.toString(16).padStart(2, "0")).join("");
async function sha256Hex(bytes) { return toHex(await crypto.subtle.digest("SHA-256", bytes)); }

export function canonicalBytes(document) {
  const body = {};
  for (const k of Object.keys(document)) if (k !== "signature") body[k] = document[k];
  return new TextEncoder().encode(DOMAIN + canonical(body));
}

export async function verify(document, pinned) {
  if (!isDict(document) || get(document, "schema") !== SCHEMA) throw new SnapshotRefused("schema_unsupported");
  const signature = get(document, "signature");
  if (typeof signature !== "string" || !HEX_SIGNATURE.test(signature)) throw new SnapshotRefused("signature_missing");
  let message;
  try { message = canonicalBytes(document); } catch { throw new SnapshotRefused("not_canonical"); }
  for (const pub of pinned.keys) {
    const key = await crypto.subtle.importKey("raw", hexBytes(pub), {name: "Ed25519"}, false, ["verify"]);
    if (await crypto.subtle.verify({name: "Ed25519"}, key, hexBytes(signature), message)) return pub;
  }
  throw new SnapshotRefused("signature_invalid");
}

// A non-negative integer's source text, or a refusal (as snapshot.py's _int).
function uintText(value, code, maximum = null) {
  if (!isNum(value) || !UINT.test(value.text)) throw new SnapshotRefused(code);
  if (maximum !== null && BigInt(value.text) > BigInt(maximum)) throw new SnapshotRefused(code);
  return value.text;
}
const uint = (value, code, maximum = null) => Number(uintText(value, code, maximum));
function hash(value, code) {
  if (typeof value !== "string" || !HASH.test(value)) throw new SnapshotRefused(code);
  return value;
}
function hotkey(value, pinned) {
  const pattern = pinned.fixture ? FIXTURE_HOTKEY : SS58;
  if (typeof value !== "string" || !pattern.test(value)) throw new SnapshotRefused("hotkey_invalid");
  return value;
}
function dict(value, code) {
  if (!isDict(value)) throw new SnapshotRefused(code);
  return value;
}
function unitsMatch(raw) {
  if (!isDict(raw)) return false;
  const keys = Object.keys(raw).sort();
  const want = Object.keys(UNITS).sort();
  return keys.length === want.length && keys.every((k, i) => k === want[i] && raw[k] === UNITS[k]);
}

// A configured freshness bound, clamped as snapshot.max_age.
export function maxAge(value) {
  if (value === undefined || value === null || value === "") return MAX_AGE_SECONDS;
  const n = Math.trunc(Number(value));
  if (!Number.isFinite(n)) return MAX_AGE_SECONDS;
  return Math.max(MIN_MAX_AGE_SECONDS, Math.min(MAX_MAX_AGE_SECONDS, n));
}

export async function project(document, pinned, {nowMs = Date.now(), maxAgeSeconds = MAX_AGE_SECONDS} = {}) {
  const signer = await verify(document, pinned);
  const rawNetwork = dict(get(document, "network"), "network_invalid");
  const name = get(rawNetwork, "name");
  if (!NETWORKS.includes(name)) throw new SnapshotRefused("network_invalid");
  const network = {
    name,
    netuid: uint(get(rawNetwork, "netuid"), "network_invalid", U16),
    genesis_hash: hash(get(rawNetwork, "genesis_hash"), "network_invalid"),
  };
  const labels = get(document, "labels");
  const allowed = new Set([...LABELS, ...(pinned.fixture ? [FIXTURE_LABEL] : [])]);
  if (!Array.isArray(labels) || labels.some(l => typeof l !== "string") || !labels.includes("DEVELOPMENT")
      || new Set(labels).size !== labels.length || !labels.every(l => allowed.has(l))
      || labels.includes(FIXTURE_LABEL) !== pinned.fixture
      || labels.includes("TESTNET") !== (name === "testnet")) throw new SnapshotRefused("labels_invalid");
  const rawBlock = dict(get(document, "block"), "block_invalid");
  const block = {
    number: uint(get(rawBlock, "number"), "block_invalid"),
    hash: hash(get(rawBlock, "hash"), "block_invalid"),
    timestamp_ms: uint(get(rawBlock, "timestamp_ms"), "block_invalid"),
  };
  const age = nowMs - block.timestamp_ms;
  if (age > maxAgeSeconds * 1000) throw new SnapshotRefused("snapshot_stale");
  if (age < -FUTURE_SKEW_SECONDS * 1000) throw new SnapshotRefused("snapshot_from_future");
  if (!unitsMatch(get(document, "units"))) throw new SnapshotRefused("units_invalid");
  const rawValidator = dict(get(document, "validator"), "validator_invalid");
  const validator = {hotkey: hotkey(get(rawValidator, "hotkey"), pinned)};
  const raw = get(document, "neurons");
  if (!Array.isArray(raw) || raw.length > MAX_NEURONS) throw new SnapshotRefused("neurons_invalid");
  const seen = new Set();
  const rows = raw.map((rawNeuron, index) => {
    const neuron = dict(rawNeuron, "neurons_invalid");
    if (uint(get(neuron, "uid"), "neurons_invalid") !== index) throw new SnapshotRefused("neurons_invalid", `uid ${index}`);
    const key = hotkey(get(neuron, "hotkey"), pinned);
    if (seen.has(key)) throw new SnapshotRefused("neurons_invalid", "duplicate hotkey");
    seen.add(key);
    const permit = get(neuron, "validator_permit");
    if (typeof permit !== "boolean") throw new SnapshotRefused("neurons_invalid", "validator_permit");
    return {
      uid: index,
      hotkey: key,
      incentive: uint(get(neuron, "incentive"), "neurons_invalid", U16),
      emission: uintText(get(neuron, "emission"), "neurons_invalid"),
      stake: uintText(get(neuron, "stake"), "neurons_invalid"),
      validator_permit: permit,
    };
  });
  const generatedAt = get(document, "generated_at");
  if (generatedAt !== null && (typeof generatedAt !== "string" || !TEXT.test(generatedAt))) throw new SnapshotRefused("generated_at_invalid");
  return {
    schema: VIEW_SCHEMA,
    source_schema: SCHEMA,
    fixture: pinned.fixture,
    labels: [...labels],
    network,
    block,
    validator,
    units: {...UNITS},
    neurons: rows,
    summary: {neurons: rows.length, validators: rows.filter(r => r.validator_permit).length},
    generated_at: generatedAt,
    snapshot: {
      key_id: "feed-" + (await sha256Hex(hexBytes(signer))).slice(0, 16),
      digest: "sha256:" + (await sha256Hex(canonicalBytes(document))),
    },
  };
}

// ---- Serving /data/network.json ----
const list = value => String(value || "").split(",").map(s => s.trim()).filter(Boolean);

// The configured snapshots, verified, or null when SNAPSHOT_URLS is not set
// (the Worker answers 404). A snapshot that fails any check is listed as
// REFUSED with its reason and no data: unverified data is never shown.
export async function liveNetwork(env, fetcher = fetch, nowMs = Date.now()) {
  const urls = list(env.SNAPSHOT_URLS);
  if (!urls.length) return null;
  if (urls.some(u => !u.startsWith("https://"))) throw new SnapshotRefused("snapshot_not_configured");
  let pinned;
  try { pinned = trust(list(env.FEED_KEYS)); } catch { throw new SnapshotRefused("feed_keys_invalid"); }
  const seconds = Math.max(0, Math.min(600, Number(env.CACHE_SECONDS ?? 60) || 0));
  const maxAgeSeconds = maxAge(env.SNAPSHOT_MAX_AGE_SECONDS);
  const snapshots = [];
  for (const url of urls) {
    try {
      const response = await fetcher(url, {cf: {cacheTtl: seconds, cacheEverything: true}, signal: AbortSignal.timeout(15000)});
      if (!response.ok) throw new SnapshotRefused("snapshot_unavailable");
      const body = await response.text();
      if (body.length > MAX_SNAPSHOT_BYTES) throw new SnapshotRefused("snapshot_too_large");
      let document;
      try { document = parse(body); } catch { throw new SnapshotRefused("not_canonical"); }
      snapshots.push({state: "ACCEPTED", code: null, ...(await project(document, pinned, {nowMs, maxAgeSeconds}))});
    } catch (error) {
      snapshots.push({state: "REFUSED", code: error instanceof SnapshotRefused ? error.code : "snapshot_unavailable"});
    }
  }
  return {view: {schema: INDEX_SCHEMA, fixture: false, snapshots}, seconds};
}
