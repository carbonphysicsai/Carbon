// The dashboard Worker's feed reader: a port of carbon/dashboard/feed.py.
//
// The Worker fetches a validator's signed score feed server-side, checks the
// Ed25519 signature against a pinned key, and keeps only what may be shown,
// exactly as feed.py does (DASHBOARD_PLAN.md §2). tests/cpu/test_dashboard_worker.py
// holds the two equal on every fixture and every refusal case.
//
// The validator signs DOMAIN + Python's canonical JSON (sorted keys, "," and
// ":" separators, ASCII escapes). JSON.parse would lose number lexemes (1.0
// becomes 1), so `parse` keeps every number's source text and `canonical`
// re-emits it verbatim.

export const SCHEMA = "carbon.validator.score-feed.v1";
export const BOARD_SCHEMA = "carbon.dashboard.board.v1";
export const DOMAIN = "carbon.validator.score-feed.v1\u0000";
// The launch Challenges' signed standing (OWNER-DASHBOARD-01): its own schema and signing
// domain, never the feed's or the network snapshot's (carbon/dashboard/launch.py).
export const LAUNCH_SCHEMA = "carbon.validator.launch-board.v1";
export const LAUNCH_DOMAIN = "carbon.validator.launch-board.v1\u0000";
export const FIXTURE_PUBLIC_KEY = "d55fec2a82d5280786d8282263c8f324f43166eb036d38fb64bce7469d742cc8";
const NUMERIC_SECTIONS = ["accuracy", "design_q", "near_limit", "total"];
const SENSES = ["lower_is_better", "higher_is_better"];
const GATE_VALUES = ["PASS", "FAIL"];
const LABELS = ["DEVELOPMENT", "TESTNET"];
const FIXTURE_LABEL = "FIXTURE";
const CASE_TEXT_FIELDS = ["case_id"];
const CASE_NUMBER_FIELDS = ["error"];
const SHOWCASE_SCHEMA = "carbon.validator.showcase-panel.v1";
const SHOWCASE_STATES = ["PREDICTED", "UNAVAILABLE"];
const SHOWCASE_LIVE = "LIVE";
const SHOWCASE_QUANTITIES = ["time_to_cv_onset_s", "reach_class", "plating_margin_v", "peak_temperature_c"];

const SS58 = /^[1-9A-HJ-NP-Za-km-z]{46,48}$/u;
const FIXTURE_HOTKEY = /^fixture-[a-z0-9-]{1,32}$/u;
const FINGERPRINT = /^sha256:[0-9a-f]{64}$/u;
const HEX_KEY = /^[0-9a-f]{64}$/u;
const HEX_SIGNATURE = /^[0-9a-f]{128}$/u;
const DEVICE = /^(?:cpu|gpu:[A-Za-z0-9][A-Za-z0-9 ._-]{0,63})$/u;
const STATE = /^[A-Z][A-Z0-9_]{0,39}$/u;
const TEXT = /^[^\u0000-\u001f\u007f<>]{1,200}$/u;
const SHOWCASE_CASE = /^ev4:[A-Za-z0-9.-]{1,40}:c1=[0-9.]{1,6},c2=[0-9.]{1,6}:0$/u;
const SHA256 = /^[0-9a-f]{64}$/u;
const BLOCK_HASH = /^0x[0-9a-fA-F]{64}$/u;
const CODE = /^[a-z][a-z0-9_]{0,63}$/u;
const CANDIDATE = /^[^\u0000-\u001f\u007f<]{1,200}$/u;
// feed.py MAX_UTC_MS, SHARE_DIGITS, COMPARISON_INTS (VALIDATOR-33 A, #1143).
export const MAX_UTC_MS = 253402300799999;
const SHARE_DIGITS = 6;
const COMPARISON_INTS = ["n_min", "n_boot", "important_min"];
export const COMPARISON_KEYS = ["alpha", ...COMPARISON_INTS];
// LP-02's count-only public vocabulary, kept in parity with feed.py.
const STATUS_REFUSALS = new Set([
  "malformed_submission", "contract_digest_malformed", "development_variant_not_served",
  "contract_not_served", "challenge_mismatch", "oversized_submission", "strategy_not_utf8",
  "strategy_bom", "strategy_nesting_too_deep", "strategy_not_json", "strategy_not_object",
  "non_finite_value", "duplicate_key", "integer_out_of_range", "hotkey_window_used",
  "receipt_block_missing", "level4_envelope_incomplete", "unclassified_refusal",
]);

export class FeedRefused extends Error {
  constructor(code, detail = "") {
    super(detail ? `${code}: ${detail}` : code);
    this.code = code;
  }
}

// ---- Numbers that keep their source text ----
export class Num {
  constructor(text) {
    this.text = text;
    this.value = Number(text);
    this.isInt = !/[.eE]/.test(text);
  }
}
const isNum = v => v instanceof Num;
const isDict = v => v !== null && typeof v === "object" && !Array.isArray(v) && !isNum(v);
const own = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
const get = (o, k) => (isDict(o) && own(o, k) ? o[k] : null);

// ---- A JSON parser that keeps number lexemes ----
export function parse(text) {
  let i = 0;
  const fail = () => { throw new FeedRefused("not_canonical", "unparseable JSON"); };
  const ws = () => { while (i < text.length && " \t\n\r".includes(text[i])) i += 1; };
  function value() {
    ws();
    const c = text[i];
    if (c === "{") {
      i += 1; const out = Object.create(null); ws();
      if (text[i] === "}") { i += 1; return plain(out); }
      for (;;) {
        ws(); if (text[i] !== "\"") fail();
        const key = string(); ws();
        if (text[i] !== ":") fail(); i += 1;
        if (own(out, key)) fail(); // duplicate keys are never canonical
        out[key] = value(); ws();
        if (text[i] === ",") { i += 1; continue; }
        if (text[i] === "}") { i += 1; return plain(out); }
        fail();
      }
    }
    if (c === "[") {
      i += 1; const out = []; ws();
      if (text[i] === "]") { i += 1; return out; }
      for (;;) {
        out.push(value()); ws();
        if (text[i] === ",") { i += 1; continue; }
        if (text[i] === "]") { i += 1; return out; }
        fail();
      }
    }
    if (c === "\"") return string();
    if (text.startsWith("true", i)) { i += 4; return true; }
    if (text.startsWith("false", i)) { i += 5; return false; }
    if (text.startsWith("null", i)) { i += 4; return null; }
    const m = /^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/.exec(text.slice(i, i + 64));
    if (!m) fail();
    i += m[0].length;
    const n = new Num(m[0]);
    if (!Number.isFinite(n.value)) fail();
    return n;
  }
  function string() {
    i += 1; let out = "";
    for (;;) {
      if (i >= text.length) fail();
      const c = text[i];
      if (c === "\"") { i += 1; return out; }
      if (c === "\\") {
        const e = text[i + 1];
        const simple = {"\"": "\"", "\\": "\\", "/": "/", b: "\b", f: "\f", n: "\n", r: "\r", t: "\t"};
        if (e in simple) { out += simple[e]; i += 2; continue; }
        if (e === "u") {
          const hex = text.slice(i + 2, i + 6);
          if (!/^[0-9a-fA-F]{4}$/.test(hex)) fail();
          out += String.fromCharCode(parseInt(hex, 16)); i += 6; continue;
        }
        fail();
      }
      if (c < " ") fail();
      out += c; i += 1;
    }
  }
  // Preserve even prototype-like JSON keys as own data properties: the signed
  // bytes include them, and unknown refusal names must still count as other.
  const plain = o => ({...o});
  const result = value(); ws();
  if (i !== text.length) fail();
  return result;
}

// ---- Python's json.dumps(sort_keys=True, separators=(",", ":")) ----
function pyString(s) {
  let out = "\"";
  for (const unit of s) {
    for (let k = 0; k < unit.length; k += 1) {
      const code = unit.charCodeAt(k);
      const ch = unit[k];
      if (ch === "\"") out += "\\\"";
      else if (ch === "\\") out += "\\\\";
      else if (ch === "\n") out += "\\n";
      else if (ch === "\r") out += "\\r";
      else if (ch === "\t") out += "\\t";
      else if (ch === "\b") out += "\\b";
      else if (ch === "\f") out += "\\f";
      else if (code < 0x20 || code > 0x7e) out += "\\u" + code.toString(16).padStart(4, "0");
      else out += ch;
    }
  }
  return out + "\"";
}
function codePointCompare(a, b) {
  const x = Array.from(a), y = Array.from(b);
  for (let k = 0; k < Math.min(x.length, y.length); k += 1) {
    const d = x[k].codePointAt(0) - y[k].codePointAt(0);
    if (d) return d;
  }
  return x.length - y.length;
}
export function canonical(value) {
  if (value === null) return "null";
  if (value === true) return "true";
  if (value === false) return "false";
  if (isNum(value)) return value.text;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new FeedRefused("not_canonical");
    return String(value);
  }
  if (typeof value === "string") return pyString(value);
  if (Array.isArray(value)) return "[" + value.map(canonical).join(",") + "]";
  const keys = Object.keys(value).sort(codePointCompare);
  return "{" + keys.map(k => pyString(k) + ":" + canonical(value[k])).join(",") + "}";
}
export function canonicalBytes(document, domain = DOMAIN) {
  const body = {};
  for (const k of Object.keys(document)) if (k !== "signature") body[k] = document[k];
  return new TextEncoder().encode(domain + canonical(body));
}

const hexBytes = hex => Uint8Array.from(hex.match(/../g).map(h => parseInt(h, 16)));
const toHex = buf => Array.from(new Uint8Array(buf), b => b.toString(16).padStart(2, "0")).join("");
async function sha256Hex(bytes) { return toHex(await crypto.subtle.digest("SHA-256", bytes)); }

// ---- Trust: pinned keys, never the fixture key in production ----
export function trust(keys, {fixture = false} = {}) {
  const set = new Set(keys);
  if (!set.size || [...set].some(k => typeof k !== "string" || !HEX_KEY.test(k))) throw new Error("trust needs one or more 32-byte hex public keys");
  if (fixture && (set.size !== 1 || !set.has(FIXTURE_PUBLIC_KEY))) throw new Error("a fixture trust holds only the fixture key");
  if (!fixture && set.has(FIXTURE_PUBLIC_KEY)) throw new Error("the fixture key is never a production key");
  return Object.freeze({keys: [...set].sort(), fixture});
}

export async function verify(document, pinned, domain = DOMAIN, schema = SCHEMA) {
  if (!isDict(document) || get(document, "schema") !== schema) throw new FeedRefused("schema_unsupported");
  const signature = get(document, "signature");
  if (typeof signature !== "string" || !HEX_SIGNATURE.test(signature)) throw new FeedRefused("signature_missing");
  const message = canonicalBytes(document, domain);
  for (const pub of pinned.keys) {
    const key = await crypto.subtle.importKey("raw", hexBytes(pub), {name: "Ed25519"}, false, ["verify"]);
    if (await crypto.subtle.verify({name: "Ed25519"}, key, hexBytes(signature), message)) return pub;
  }
  throw new FeedRefused("signature_invalid");
}

// ---- Field checks, as feed.py's helpers ----
function int(value, code, {minimum = 0, optional = false} = {}) {
  if (value === null && optional) return null;
  if (!isNum(value) || !value.isInt || value.value < minimum) throw new FeedRefused(code);
  return value.value;
}
function text(value, code) {
  if (typeof value !== "string" || !TEXT.test(value)) throw new FeedRefused(code);
  return value;
}
function number(value, code) {
  if (!isNum(value)) throw new FeedRefused(code);
  return value.value;
}
function digitsOf(precision) {
  const digits = -Math.log10(precision);
  if (Math.abs(digits - Math.round(digits)) > 1e-9 || Math.round(digits) < 0) throw new FeedRefused("feed_values_unregistered", "precision");
  return Math.round(digits);
}
function rounded(value, digits, where) {
  if (value === null) return null;
  const v = number(value, "section_not_a_number");
  if (Number(v.toFixed(digits)) !== v) throw new FeedRefused("unrounded_value", where);
  return v;
}
function hotkey(value, pinned) {
  const pattern = pinned.fixture ? FIXTURE_HOTKEY : SS58;
  if (typeof value !== "string" || !pattern.test(value)) throw new FeedRefused("hotkey_invalid");
  return value;
}
function sections(raw, digits, where) {
  if (raw === null) return {};
  if (!isDict(raw)) throw new FeedRefused("sections_invalid", where);
  const out = {};
  for (const name of NUMERIC_SECTIONS) if (own(raw, name)) out[name] = rounded(raw[name], digits, `${where}.${name}`);
  if (own(raw, "gates")) {
    const gates = raw.gates;
    if (!isDict(gates)) throw new FeedRefused("gates_invalid", where);
    out.gates = {};
    for (const gate of Object.keys(gates).sort(codePointCompare)) {
      if (!GATE_VALUES.includes(gates[gate])) throw new FeedRefused("gates_invalid", where);
      out.gates[text(gate, "gates_invalid")] = gates[gate];
    }
  }
  return out;
}
function values(raw) {
  if (!isDict(raw)) throw new FeedRefused("feed_values_unregistered");
  if (get(raw, "live") !== null) throw new FeedRefused("live_not_authorized");
  const released = get(raw, "released");
  if (!isDict(released)) throw new FeedRefused("feed_values_unregistered");
  const precision = get(released, "precision");
  if (!isNum(precision) || precision.value <= 0) throw new FeedRefused("feed_values_unregistered");
  const threshold = get(released, "display_threshold");
  return {
    precision: precision.value,
    digits: digitsOf(precision.value),
    display_threshold: threshold === null ? null : number(threshold, "feed_values_unregistered"),
    registered: text(get(raw, "registered"), "feed_values_unregistered"),
  };
}
function sectionMeta(raw) {
  if (raw === null) return {};
  if (!isDict(raw)) throw new FeedRefused("section_meta_invalid");
  const out = {};
  for (const name of [...NUMERIC_SECTIONS, "gates"]) {
    const meta = get(raw, name);
    if (meta === null) continue;
    const sense = isDict(meta) ? get(meta, "sense") : "invalid";
    if ((name === "gates" && sense !== null) || (name !== "gates" && !SENSES.includes(sense))) throw new FeedRefused("section_meta_invalid", name);
    const unit = get(meta, "unit");
    out[name] = {
      display: text(own(meta, "display") ? meta.display : name, "section_meta_invalid"),
      unit: unit === null || unit === "" ? null : text(unit, "section_meta_invalid"),
      sense,
    };
  }
  return out;
}
function detail(raw, released, used, where) {
  if (raw === null) return {};
  if (!isDict(raw)) throw new FeedRefused("detail_invalid", where);
  const out = {};
  for (const fingerprint of Object.keys(raw).sort(codePointCompare)) {
    if (!released.has(fingerprint) || !used.has(fingerprint)) throw new FeedRefused("detail_not_released", where);
    const body = raw[fingerprint];
    const cases = isDict(body) ? get(body, "cases") : null;
    if (!Array.isArray(cases)) throw new FeedRefused("detail_invalid", where);
    out[fingerprint] = {cases: cases.map(c => {
      if (!isDict(c)) throw new FeedRefused("detail_invalid", where);
      const row = {};
      for (const f of CASE_TEXT_FIELDS) row[f] = text(get(c, f), "detail_invalid");
      for (const f of CASE_NUMBER_FIELDS) if (own(c, f)) row[f] = number(c[f], "detail_invalid");
      return row;
    })};
  }
  return out;
}
function device(value) {
  if (typeof value !== "string" || !DEVICE.test(value)) throw new FeedRefused("device_class_invalid");
  return value;
}
function release(raw) {
  if (raw === null) return null;
  if (!isDict(raw)) throw new FeedRefused("release_invalid");
  const predicate = get(raw, "predicate");
  const out = {predicate: predicate === null ? null : text(predicate, "release_invalid")};
  for (const k of ["retire_at", "rotation_every_blocks", "expected_lag_blocks", "next_rotation_block"]) out[k] = int(get(raw, k), "release_invalid", {optional: true});
  return out;
}
// ---- VALIDATOR-33 A (#1143): chain time, king, handovers, target (feed.py) ----
function utcMs(value, code) {
  if (value === null) return null;
  if (!isNum(value) || !value.isInt || value.value < 0 || value.value > MAX_UTC_MS) throw new FeedRefused(code);
  return value.value;
}
function flag(value, code) {
  if (value === null) return null;
  if (typeof value !== "boolean") throw new FeedRefused(code);
  return value;
}
const maybeText = (value, code) => (value === null ? null : text(value, code));
function asOfBlock(raw) {
  if (raw === null) return null;
  if (!isDict(raw)) throw new FeedRefused("as_of_block_invalid");
  const hash = get(raw, "hash");
  if (typeof hash !== "string" || !BLOCK_HASH.test(hash)) throw new FeedRefused("as_of_block_invalid");
  const stamp = utcMs(get(raw, "timestamp_ms"), "as_of_block_invalid");
  if (stamp === null) throw new FeedRefused("as_of_block_invalid");
  return {number: int(get(raw, "number"), "as_of_block_invalid"), hash, timestamp_ms: stamp};
}
function kingOf(raw, pinned) {
  if (raw === null) return null;
  if (!isDict(raw)) throw new FeedRefused("king_invalid");
  let share = get(raw, "share_now");
  if (share !== null) {
    share = number(share, "king_invalid");
    if (!(share >= 0 && share <= 1)) throw new FeedRefused("king_invalid");
    if (Number(share.toFixed(SHARE_DIGITS)) !== share) throw new FeedRefused("unrounded_value", "king.share_now");
  }
  const coldkey = get(raw, "coldkey");
  return {
    hotkey: hotkey(get(raw, "hotkey"), pinned),
    uid: int(get(raw, "uid"), "king_invalid", {optional: true}),
    coldkey: coldkey === null ? null : hotkey(coldkey, pinned),
    submission_id: maybeText(get(raw, "submission_id"), "king_invalid"),
    crowned_utc_ms: utcMs(get(raw, "crowned_utc_ms"), "king_invalid"),
    eligible: flag(get(raw, "eligible"), "king_invalid"),
    reason: maybeText(get(raw, "reason"), "king_invalid"),
    share_now: share,
    next_halving_utc_ms: utcMs(get(raw, "next_halving_utc_ms"), "king_invalid"),
    challenges_survived: int(get(raw, "challenges_survived"), "king_invalid", {optional: true}),
  };
}
function handovers(raw, pinned) {
  if (raw === null) return null;
  if (!Array.isArray(raw)) throw new FeedRefused("handovers_invalid");
  return raw.map(row => {
    if (!isDict(row)) throw new FeedRefused("handovers_invalid");
    const to = get(row, "to_hotkey"), from = get(row, "from_hotkey");
    return {
      utc_ms: utcMs(get(row, "utc_ms"), "handovers_invalid"),
      to_hotkey: to === null ? null : hotkey(to, pinned),
      from_hotkey: from === null ? null : hotkey(from, pinned),
      kind: maybeText(get(row, "kind"), "handovers_invalid"),
      eligible: flag(get(row, "eligible"), "handovers_invalid"),
      reason: maybeText(get(row, "reason"), "handovers_invalid"),
    };
  });
}
function margin(value) {
  if (value === null) return null;
  const v = number(value, "target_invalid");
  if (v < 0) throw new FeedRefused("target_invalid");
  return v;
}
function comparison(raw) {
  if (raw === null) return null;
  if (!isDict(raw)) throw new FeedRefused("target_invalid");
  const out = {};
  for (const k of COMPARISON_INTS) out[k] = int(get(raw, k), "target_invalid", {optional: true});
  let alpha = get(raw, "alpha");
  if (alpha !== null) {
    alpha = number(alpha, "target_invalid");
    if (!(alpha > 0 && alpha < 1)) throw new FeedRefused("target_invalid");
  }
  return {alpha, ...out};
}
function target(raw) {
  if (raw === null) return null;
  if (!isDict(raw)) throw new FeedRefused("target_invalid");
  const kind = get(raw, "kind");
  if (typeof kind !== "string" || !CODE.test(kind)) throw new FeedRefused("target_invalid");
  let score = get(raw, "score");
  if (score !== null) {
    if (!isDict(score)) throw new FeedRefused("target_invalid");
    const candidate = get(score, "candidate"), digest = get(score, "registry_sha256");
    if (candidate !== null && (typeof candidate !== "string" || !CANDIDATE.test(candidate))) throw new FeedRefused("target_invalid");
    if (digest !== null && (typeof digest !== "string" || !SHA256.test(digest))) throw new FeedRefused("target_invalid");
    score = {candidate, registry_sha256: digest, decision: maybeText(get(score, "decision"), "target_invalid")};
  }
  let gates = get(raw, "gates");
  if (gates !== null) {
    if (!Array.isArray(gates) || gates.some(g => typeof g !== "string" || !CODE.test(g))) throw new FeedRefused("target_invalid");
    gates = [...gates];
  }
  return {
    kind,
    screening_margin_rel: margin(get(raw, "screening_margin_rel")),
    final_margin_rel: margin(get(raw, "final_margin_rel")),
    final_comparison: comparison(get(raw, "final_comparison")),
    score,
    gates,
  };
}
function showcase(raw, incumbent, pinned) {
  if (raw === null) return null;
  if (!isDict(raw) || get(raw, "schema") !== SHOWCASE_SCHEMA) throw new FeedRefused("showcase_invalid");
  const task = get(raw, "task");
  const mode = isDict(task) ? get(task, "incumbent") : null;
  if (mode !== null && mode !== SHOWCASE_LIVE) throw new FeedRefused("showcase_invalid");
  if (mode === null && incumbent === null) throw new FeedRefused("showcase_without_incumbent");
  const model = get(raw, "model");
  if (!isDict(task) || !isDict(model)) throw new FeedRefused("showcase_invalid");
  if (get(task, "data_scope") !== "PUBLIC_SYNTHETIC" || get(task, "split") !== "development") throw new FeedRefused("showcase_not_public");
  const sha = get(task, "contract_sha256");
  if (typeof sha !== "string" || !SHA256.test(sha)) throw new FeedRefused("showcase_invalid");
  const key = hotkey(get(model, "hotkey"), pinned);
  if (mode === null && key !== incumbent.hotkey) throw new FeedRefused("showcase_not_incumbent");
  const state = get(raw, "state");
  if (!SHOWCASE_STATES.includes(state)) throw new FeedRefused("showcase_invalid");
  const label = get(raw, "label");
  const submission = get(model, "submission_id");
  const panel = {
    task: {
      task_id: text(get(task, "task_id"), "showcase_invalid"),
      contract: text(get(task, "contract"), "showcase_invalid"),
      contract_sha256: sha,
      split: "development",
      incumbent: mode || "RELEASED",
    },
    label: label === null ? null : text(label, "showcase_invalid"),
    contract_digest: text(get(raw, "contract_digest"), "showcase_invalid"),
    model: {hotkey: key, submission_id: submission === null ? null : text(submission, "showcase_invalid")},
    state,
    code: null,
    predictions: {},
  };
  if (state === "UNAVAILABLE") {
    const code = get(raw, "code");
    panel.code = code === null ? null : text(code, "showcase_invalid");
    return panel;
  }
  const predictions = get(raw, "predictions");
  if (!isDict(predictions)) throw new FeedRefused("showcase_invalid");
  for (const caseId of Object.keys(predictions).sort(codePointCompare)) {
    if (!SHOWCASE_CASE.test(caseId)) throw new FeedRefused("showcase_case_invalid");
    const v = predictions[caseId];
    if (!isDict(v)) throw new FeedRefused("showcase_invalid");
    const row = {};
    for (const q of SHOWCASE_QUANTITIES) row[q] = number(get(v, q), "showcase_invalid");
    if (![-1, 0, 1].includes(row.reach_class)) throw new FeedRefused("showcase_invalid");
    panel.predictions[caseId] = row;
  }
  return panel;
}

// OWNER-BATTERY-CHAMPIONSHIP-03: the proposed `leaderboard.ladder` (feed.py _ladder).
const LADDER_STATES = ["SHOWN", "NO_IMPROVEMENT_BEYOND_GRAIN", "SEALED_UNTIL_GRAIN"];
const UNRANKED = 10 ** 9;
function ladder(raw, digits, pinned) {
  if (raw === null) return null;
  if (!isDict(raw) || !Array.isArray(get(raw, "coldkeys"))) throw new FeedRefused("ladder_invalid");
  const grainRaw = get(raw, "grain_pct");
  const grain = grainRaw === null ? null : number(grainRaw, "ladder_invalid");
  if (grain !== null && grain <= 0) throw new FeedRefused("ladder_invalid");
  const geometric = own(raw, "display_grid");
  const sense = get(raw, "sense");
  if (geometric && (raw.display_grid !== "geometric" ||
      !["lower_is_better", "higher_is_better", null].includes(sense) ||
      (grain !== null && sense === null))) throw new FeedRefused("ladder_invalid");
  const rows = [], seen = new Set();
  for (const row of raw.coldkeys) {
    if (!isDict(row)) throw new FeedRefused("ladder_invalid");
    const coldkey = hotkey(get(row, "coldkey"), pinned);
    const status = get(row, "status");
    if (seen.has(coldkey) || !LADDER_STATES.includes(status)) throw new FeedRefused("ladder_invalid");
    seen.add(coldkey);
    let score;
    if (geometric) {
      score = get(row, "displayed_score");
      if (score !== null) {
        score = number(score, "ladder_invalid");
        if (grain === null) throw new FeedRefused("ladder_grain_unposted");
        if (score <= 0) throw new FeedRefused("ladder_invalid");
        const base = 1 + grain / 100;
        const exponent = Math.round(Math.log(score) / Math.log(base));
        const expected = base ** exponent;
        if (!Number.isFinite(expected) || base <= 1) throw new FeedRefused("ladder_invalid");
        if (Math.abs(score - expected) > 8 * Number.EPSILON * Math.max(Math.abs(score), Math.abs(expected)))
          throw new FeedRefused("ladder_unrounded");
      }
    } else score = rounded(get(row, "displayed_score"), digits, "ladder");
    if (status === "SEALED_UNTIL_GRAIN" && score !== null) throw new FeedRefused("ladder_sealed_value");
    if (status !== "SEALED_UNTIL_GRAIN" && score === null) throw new FeedRefused("ladder_invalid");
    if (status !== "SEALED_UNTIL_GRAIN" && grain === null) throw new FeedRefused("ladder_grain_unposted");
    const keys = get(row, "hotkeys");
    if (!Array.isArray(keys)) throw new FeedRefused("ladder_invalid");
    rows.push({
      coldkey,
      rank: int(get(row, "rank"), "ladder_invalid", {minimum: 1, optional: true}),
      displayed_score: score,
      status,
      hotkeys: [...new Set(keys.map(h => hotkey(h, pinned)))].sort(codePointCompare),
      best_submission_id: get(row, "best_submission_id") === null ? null : text(row.best_submission_id, "ladder_invalid"),
      displayed_at_block: int(get(row, "displayed_at_block"), "ladder_invalid", {optional: true}),
    });
  }
  const order = r => (r.rank === null ? UNRANKED : r.rank);
  const result = {grain_pct: grain, coldkeys: rows.sort((a, b) => order(a) - order(b) || cmp(a.coldkey, b.coldkey))};
  if (geometric) Object.assign(result, {display_grid: "geometric", sense});
  return result;
}

function statusCount(value) {
  const count = int(value, "miner_status_invalid");
  if (!Number.isSafeInteger(count)) throw new FeedRefused("miner_status_invalid");
  return count;
}
function minerStatus(raw, pinned) {
  if (raw === null) return null;
  if (!Array.isArray(raw)) throw new FeedRefused("miner_status_invalid");
  const rows = [], seen = new Set();
  for (const row of raw) {
    const rawRefused = get(row, "refused");
    if (!isDict(row) || !isDict(rawRefused)) throw new FeedRefused("miner_status_invalid");
    const key = hotkey(get(row, "hotkey"), pinned);
    if (seen.has(key)) throw new FeedRefused("miner_status_invalid");
    seen.add(key);
    const refused = {};
    let total = 0;
    for (const [code, rawCount] of Object.entries(rawRefused)) {
      const count = statusCount(rawCount);
      const kept = STATUS_REFUSALS.has(code) && code !== "unclassified_refusal" ? code : "other";
      refused[kept] = (refused[kept] ?? 0) + count;
      total += count;
      if (!Number.isSafeInteger(refused[kept]) || !Number.isSafeInteger(total))
        throw new FeedRefused("miner_status_invalid");
    }
    const sortedRefused = {};
    for (const code of Object.keys(refused).sort(codePointCompare)) sortedRefused[code] = refused[code];
    rows.push({hotkey: key, received: statusCount(get(row, "received")),
      scored: statusCount(get(row, "scored")), refused: sortedRefused});
  }
  return rows.sort((a, b) => cmp(a.hotkey, b.hotkey));
}

export function boardSlug(challengeId, deviceClass) {
  return `${challengeId}--${deviceClass}`.toLowerCase().replace(/[^a-z0-9.-]+/g, "-").replace(/^-+|-+$/g, "");
}
const keyOf = (blockOrNull, id) => [blockOrNull || 0, id];
const cmp = (a, b) => (a < b ? -1 : a > b ? 1 : 0);

// ---- The launch board (OWNER-DASHBOARD-01): a port of carbon/dashboard/launch.py ----
const LAUNCH_STATUSES = ["IMPROVED", "NO_IMPROVEMENT", "GATE_FAILED", "NOT_SCORED"];
const LAUNCH_NETWORK_LABELS = {testnet: ["DEVELOPMENT", "TESTNET"], mainnet: ["DEVELOPMENT"]};
const LAUNCH_MAX_LADDER = 512;
const LAUNCH_MAX_GATES = 16;
const LAUNCH_FIELDS = ["challenge", "counts", "generated_at", "king", "labels", "ladder", "network", "schema", "signature", "validator", "version"];
const LAUNCH_KING_FIELDS = ["baseline_total", "king", "margin", "to_beat"];
const LAUNCH_KING_ROW = ["hotkey", "since_epoch", "total"];
const LAUNCH_LADDER_FIELDS = ["gate_names", "hotkey", "rank", "status", "total"];
const LAUNCH_SS58 = /^[1-9A-HJ-NP-Za-km-z]{47,48}$/u;
const LAUNCH_NAME = /^[a-z0-9][a-z0-9._-]{0,63}$/u;
const LAUNCH_LABEL = /^[A-Za-z0-9][A-Za-z0-9 ._:+-]{0,63}$/u;
const LAUNCH_GATE = /^[a-z][a-z0-9_.-]{0,63}$/u;
const LAUNCH_UTC = /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/u;
const LAUNCH_ID = /^[^\u0000-\u001f\u007f<>]{1,200}$/u;
const sameKeys = (o, names) => isDict(o) && Object.keys(o).length === names.length && Object.keys(o).sort().join("\u0000") === [...names].sort().join("\u0000");
const launchUnit = (value, code, nullable = false) => {
  if (value === null && nullable) return null;
  if (!isNum(value) || !Number.isFinite(value.value) || value.value < 0 || value.value > 1) throw new FeedRefused(code);
  return value.value;
};
const launchInt = value => isNum(value) && value.isInt;
// The fewest decimal places (at least 3) that hold every value exactly: a display parameter.
function launchDigits(values) {
  for (let d = 3; d < 10; d += 1) if (values.every(v => Number(v.toFixed(d)) === v)) return d;
  throw new FeedRefused("total_unrounded");
}
function launchCheck(document) {
  if (!sameKeys(document, LAUNCH_FIELDS)) throw new FeedRefused("board_fields");
  const network = get(document, "network");
  const labels = get(document, "labels");
  if (typeof network !== "string" || !own(LAUNCH_NETWORK_LABELS, network) || !Array.isArray(labels)
      || labels.length !== LAUNCH_NETWORK_LABELS[network].length || labels.some((l, i) => l !== LAUNCH_NETWORK_LABELS[network][i])) throw new FeedRefused("labels_invalid");
  const version = get(document, "version");
  if (!launchInt(version) || version.value < 1) throw new FeedRefused("version_invalid");
  const generated = get(document, "generated_at");
  if (typeof generated !== "string" || !LAUNCH_UTC.test(generated)) throw new FeedRefused("generated_at_invalid");
  const challenge = get(document, "challenge");
  if (!sameKeys(challenge, ["exam_version_label", "id", "version"])
      || ["id", "version", "exam_version_label"].some(k => typeof challenge[k] !== "string" || !LAUNCH_ID.test(challenge[k]))
      || !LAUNCH_NAME.test(challenge.version) || !LAUNCH_LABEL.test(challenge.exam_version_label)) throw new FeedRefused("challenge_invalid");
  const validator = get(document, "validator");
  if (!sameKeys(validator, ["feed_key"]) || typeof validator.feed_key !== "string" || !HEX_KEY.test(validator.feed_key)) throw new FeedRefused("validator_invalid");
  const king = get(document, "king");
  if (!sameKeys(king, LAUNCH_KING_FIELDS)) throw new FeedRefused("king_invalid");
  const row = king.king;
  if (row !== null) {
    if (!sameKeys(row, LAUNCH_KING_ROW) || typeof row.hotkey !== "string" || !LAUNCH_SS58.test(row.hotkey)
        || !launchInt(row.since_epoch) || row.since_epoch.value < 0) throw new FeedRefused("king_invalid");
    launchUnit(row.total, "king_invalid");
  }
  for (const name of ["margin", "to_beat", "baseline_total"]) launchUnit(king[name], "king_invalid", true);
  const ladder = get(document, "ladder");
  if (!Array.isArray(ladder) || ladder.length > LAUNCH_MAX_LADDER) throw new FeedRefused("ladder_invalid");
  const seen = new Set();
  const tally = {};
  for (const status of LAUNCH_STATUSES) tally[status] = 0;
  for (const entry of ladder) {
    if (!sameKeys(entry, LAUNCH_LADDER_FIELDS) || !launchInt(entry.rank) || entry.rank.value < 1
        || typeof entry.hotkey !== "string" || !LAUNCH_SS58.test(entry.hotkey) || seen.has(entry.hotkey)
        || typeof entry.status !== "string" || !LAUNCH_STATUSES.includes(entry.status)) throw new FeedRefused("ladder_invalid");
    seen.add(entry.hotkey);
    launchUnit(entry.total, "ladder_invalid", true);
    const gates = entry.gate_names;
    if (gates !== null && (entry.status !== "GATE_FAILED" || !Array.isArray(gates) || gates.length > LAUNCH_MAX_GATES
        || gates.some(g => typeof g !== "string" || !LAUNCH_GATE.test(g)))) throw new FeedRefused("ladder_invalid");
    tally[entry.status] += 1;
  }
  const counts = {
    graded: ladder.length,
    scored: tally.IMPROVED + tally.NO_IMPROVEMENT,
    gate_failed: tally.GATE_FAILED,
    not_scored: tally.NOT_SCORED,
  };
  const given = get(document, "counts");
  if (!sameKeys(given, Object.keys(counts)) || Object.keys(counts).some(k => !launchInt(given[k]) || given[k].value !== counts[k])) throw new FeedRefused("counts_invalid");
  return counts;
}
async function projectLaunch(document, pinned) {
  if (pinned.fixture) throw new FeedRefused("fixture_launch_board");
  const signer = await verify(document, pinned, LAUNCH_DOMAIN, LAUNCH_SCHEMA);
  const counts = launchCheck(document);
  const ladder = document.ladder;
  const king = document.king;
  const totals = ladder.filter(e => e.total !== null).map(e => e.total.value);
  if (king.king !== null) totals.push(king.king.total.value);
  for (const k of ["margin", "to_beat", "baseline_total"]) if (king[k] !== null) totals.push(king[k].value);
  const digits = launchDigits(totals);
  const challenge = document.challenge;
  const standing = ladder.filter(e => e.total !== null).map(e => ({
    rank: e.rank.value, hotkey: e.hotkey, best: {total: e.total.value}, best_at_block: null,
  })).sort((a, b) => a.rank - b.rank || cmp(a.hotkey, b.hotkey));
  const incumbent = king.king === null ? null : {
    hotkey: king.king.hotkey, submission_id: null, since_block: null, sections: {total: king.king.total.value},
  };
  const gateNames = {};
  for (const e of ladder) if (e.gate_names !== null && e.gate_names.length) gateNames[e.hotkey] = [...e.gate_names];
  const bytes = canonicalBytes(document, LAUNCH_DOMAIN);
  return {
    schema: BOARD_SCHEMA,
    source_schema: LAUNCH_SCHEMA,
    fixture: false,
    labels: [...document.labels],
    challenge: {id: challenge.id, version: challenge.version, rule_digest: "exam:" + challenge.exam_version_label, rule: null},
    device_class: null,
    slug: boardSlug(challenge.id, "no-class"),
    version: document.version.value,
    released_through_block: null,
    generated_at: document.generated_at,
    values: {precision: 10 ** -digits, digits, display_threshold: null, registered: "launch board: the Ladder's own rounding"},
    section_meta: {total: {display: "Total score", unit: "0 to 1, rounded down to the Ladder step", sense: "higher_is_better"}},
    release: null,
    as_of_block: null,
    king: null,
    handovers: null,
    target_to_beat: null,
    released_windows: [],
    // Graded hotkeys stand in for released windows: PRE_FIRST_RELEASE until one has a result.
    released_count: counts.graded,
    incumbent,
    challengers: ladder.map(e => ({hotkey: e.hotkey, state: e.status})),
    standing,
    ladder: null,
    history: {},
    miners: {},
    excluded_canaries: 0,
    showcase_panel: null,
    launch: {
      counts,
      margin: king.margin === null ? null : king.margin.value,
      to_beat: king.to_beat === null ? null : king.to_beat.value,
      baseline_total: king.baseline_total === null ? null : king.baseline_total.value,
      king_since_epoch: king.king === null ? null : king.king.since_epoch.value,
      exam_version_label: challenge.exam_version_label,
      network: document.network,
      gate_names: gateNames,
    },
    feed: {
      key_id: "feed-" + (await sha256Hex(hexBytes(signer))).slice(0, 16),
      public_key: signer,
      digest: "sha256:" + (await sha256Hex(bytes)),
    },
  };
}

export async function project(document, pinned) {
  if (isDict(document) && get(document, "schema") === LAUNCH_SCHEMA) return projectLaunch(document, pinned);
  const signer = await verify(document, pinned);
  if (own(document, "live")) throw new FeedRefused("live_not_authorized");
  const vals = values(get(document, "values"));
  const digits = vals.digits;
  const labels = get(document, "labels");
  const allowed = new Set([...LABELS, ...(pinned.fixture ? [FIXTURE_LABEL] : [])]);
  if (!Array.isArray(labels) || !labels.includes("DEVELOPMENT") || new Set(labels).size !== labels.length
      || !labels.every(l => allowed.has(l)) || labels.includes(FIXTURE_LABEL) !== pinned.fixture) throw new FeedRefused("labels_invalid");
  const rawChallenge = get(document, "challenge");
  if (!isDict(rawChallenge)) throw new FeedRefused("challenge_invalid");
  const challenge = {};
  for (const k of ["id", "version", "rule_digest"]) challenge[k] = text(get(rawChallenge, k), "challenge_invalid");
  const rule = get(rawChallenge, "rule");
  challenge.rule = rule === null ? null : text(rule, "challenge_invalid");

  const windows = get(document, "released_windows");
  if (!Array.isArray(windows)) throw new FeedRefused("released_windows_invalid");
  for (const f of windows) if (typeof f !== "string" || !FINGERPRINT.test(f)) throw new FeedRefused("released_windows_invalid");
  const released = new Set(windows);

  const submissions = get(document, "submissions");
  if (!Array.isArray(submissions)) throw new FeedRefused("submissions_invalid");
  const classes = new Set();
  if (get(document, "device_class") !== null) classes.add(device(document.device_class));
  const miners = {};
  submissions.forEach((raw, index) => {
    const where = `submissions[${index}]`;
    if (!isDict(raw)) throw new FeedRefused("submissions_invalid", where);
    const key = hotkey(get(raw, "hotkey"), pinned);
    const used = get(raw, "windows");
    if (!Array.isArray(used) || !used.length) throw new FeedRefused("submissions_invalid", where);
    if (used.some(w => !released.has(w))) throw new FeedRefused("unreleased_window", where);
    const state = get(raw, "state");
    if (typeof state !== "string" || !STATE.test(state)) throw new FeedRefused("submissions_invalid", where);
    if (own(raw, "device_class")) classes.add(device(raw.device_class));
    const row = {
      submission_id: text(get(raw, "submission_id"), "submissions_invalid"),
      receipt_block: int(get(raw, "receipt_block"), "submissions_invalid", {optional: true}),
      windows: [...used].sort(codePointCompare),
      state,
      sections: sections(get(raw, "sections"), digits, where),
      detail: detail(get(raw, "detail"), released, new Set(used), where),
    };
    (miners[key] ||= {hotkey: key, submissions: []}).submissions.push(row);
  });
  if (classes.size > 1) throw new FeedRefused("device_class_mixed");
  const deviceClass = classes.size ? [...classes][0] : null;
  for (const m of Object.values(miners)) {
    m.submissions.sort((a, b) => { const x = keyOf(a.receipt_block, a.submission_id), y = keyOf(b.receipt_block, b.submission_id); return x[0] - y[0] || cmp(x[1], y[1]); });
  }

  const board = get(document, "leaderboard");
  if (!isDict(board)) throw new FeedRefused("leaderboard_invalid");
  let incumbent = get(board, "incumbent");
  if (incumbent !== null) {
    if (!isDict(incumbent)) throw new FeedRefused("leaderboard_invalid");
    const sub = get(incumbent, "submission_id");
    incumbent = {
      hotkey: hotkey(get(incumbent, "hotkey"), pinned),
      submission_id: sub === null ? null : text(sub, "leaderboard_invalid"),
      since_block: int(get(incumbent, "since_block"), "leaderboard_invalid", {optional: true}),
      sections: sections(get(incumbent, "sections"), digits, "incumbent"),
    };
  }
  const rawChallengers = get(board, "challengers") ?? [];
  if (!Array.isArray(rawChallengers)) throw new FeedRefused("leaderboard_invalid", "challengers");
  const challengers = rawChallengers.map(raw => {
    if (!isDict(raw)) throw new FeedRefused("leaderboard_invalid", "challengers");
    const state = get(raw, "state");
    if (typeof state !== "string" || !STATE.test(state)) throw new FeedRefused("leaderboard_invalid", "challengers");
    return {hotkey: hotkey(get(raw, "hotkey"), pinned), state};
  });
  const rawStanding = get(board, "standing") ?? [];
  if (!Array.isArray(rawStanding)) throw new FeedRefused("leaderboard_invalid", "standing");
  const standing = rawStanding.map(raw => {
    if (!isDict(raw)) throw new FeedRefused("leaderboard_invalid", "standing");
    return {
      rank: int(get(raw, "rank"), "leaderboard_invalid", {minimum: 1}),
      hotkey: hotkey(get(raw, "hotkey"), pinned),
      best: sections(get(raw, "best"), digits, "standing"),
      best_at_block: int(get(raw, "best_at_block"), "leaderboard_invalid", {optional: true}),
    };
  }).sort((a, b) => a.rank - b.rank || cmp(a.hotkey, b.hotkey));
  const rawHistory = get(board, "history") ?? {};
  if (!isDict(rawHistory)) throw new FeedRefused("leaderboard_invalid", "history");
  const history = {};
  for (const key of Object.keys(rawHistory).sort(codePointCompare)) {
    hotkey(key, pinned);
    const points = rawHistory[key];
    if (!Array.isArray(points)) throw new FeedRefused("leaderboard_invalid", "history");
    history[key] = points.map(p => {
      if (!isDict(p)) throw new FeedRefused("leaderboard_invalid", "history");
      return {
        receipt_block: int(get(p, "receipt_block"), "leaderboard_invalid", {optional: true}),
        sections: sections(get(p, "sections"), digits, "history"),
      };
    }).sort((a, b) => (a.receipt_block || 0) - (b.receipt_block || 0));
  }
  const excluded = own(document, "excluded") ? document.excluded : {};
  const canaries = int(isDict(excluded) ? (own(excluded, "canary_hotkeys") ? excluded.canary_hotkeys : new Num("0")) : null, "excluded_invalid");
  const generatedAt = get(document, "generated_at");
  const sortedMiners = {};
  for (const k of Object.keys(miners).sort(codePointCompare)) sortedMiners[k] = miners[k];
  const bytes = canonicalBytes(document);
  const status = minerStatus(get(document, "miner_status"), pinned);
  return {
    ...(status === null ? {} : {miner_status: status}),
    schema: BOARD_SCHEMA,
    source_schema: SCHEMA,
    fixture: pinned.fixture,
    labels: [...labels],
    challenge,
    device_class: deviceClass,
    slug: boardSlug(challenge.id, deviceClass || "no-class"),
    version: int(get(document, "version"), "version_invalid", {minimum: 1}),
    released_through_block: int(get(document, "released_through_block"), "block_invalid", {optional: true}),
    generated_at: generatedAt === null ? null : text(generatedAt, "generated_at_invalid"),
    values: vals,
    section_meta: sectionMeta(get(document, "sections")),
    release: release(get(document, "release")),
    as_of_block: asOfBlock(get(document, "as_of_block")),
    king: kingOf(get(document, "king"), pinned),
    handovers: handovers(get(document, "handovers"), pinned),
    target_to_beat: target(get(document, "target_to_beat")),
    released_windows: [...windows],
    incumbent,
    challengers,
    standing,
    ladder: ladder(get(board, "ladder"), digits, pinned),
    history,
    miners: sortedMiners,
    excluded_canaries: canaries,
    showcase_panel: showcase(get(document, "showcase"), incumbent, pinned),
    feed: {
      key_id: "feed-" + (await sha256Hex(hexBytes(signer))).slice(0, 16),
      public_key: signer,
      digest: "sha256:" + (await sha256Hex(bytes)),
    },
  };
}

// As build.py: the board without the panel's predictions, and its index entry.
export function panelSummary(panel) {
  if (panel === null) return null;
  return {state: panel.state, code: panel.code, cases: Object.keys(panel.predictions).length};
}
export function entry(board) {
  return {
    slug: board.slug,
    state: board.feed_state.state,
    code: board.feed_state.code,
    challenge: board.challenge,
    device_class: board.device_class,
    labels: board.labels,
    fixture: board.fixture,
    version: board.version,
    released_through_block: board.released_through_block,
    incumbent: board.incumbent === null ? null : board.incumbent.hotkey,
    miners: Object.keys(board.miners).length,
  };
}

// ---- board.v2 (DASHBOARD-02 S1): a port of carbon/dashboard/board_v2.py ----
// Projected from the verified board.v1 model only. Every null has a reason at
// reasons[<key>] of the object that holds it; tests/cpu/test_dashboard_worker.py
// holds this equal to board_v2.py.
export const BOARD_V2_SCHEMA = "carbon.dashboard.board.v2";
export const BLOCK_SECONDS = 12;
// ENGINEERING UI DEFAULT, not a registered value (board_v2.STALE_AFTER_SECONDS).
export const STALE_AFTER_SECONDS = 2 * 60 * 60;
const UTC = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z$/u;
export const ELIGIBLE_LABEL = "Eligible for the championship";
export const LAUNCH_LADDER_LABEL = "Ladder: best total per hotkey";
const CARD_DIGEST = /^sha256:[0-9a-f]{64}$/u;
// The rules card is the only source of a rule statement (board_v2._rules).
function rulesStatus(board, card) {
  if (card === null || card === undefined) {
    return [fields(["status", "UNAVAILABLE", null], ["card_digest", null, "rules_unavailable"]), "rules_unavailable"];
  }
  const digest = isDict(card) ? pick(card, "digest") : null;
  const rule = isDict(card) ? pick(card, "rule") : null;
  if (typeof digest !== "string" || !CARD_DIGEST.test(digest)) throw new Error("a rules card summary names its sha256 digest");
  if (!isDict(rule) || typeof pick(rule, "digest") !== "string") throw new Error("a rules card summary names its rule digest");
  const ok = rule.digest === board.challenge.rule_digest;
  return [fields(["status", ok ? "OK" : "DIGEST_MISMATCH", null], ["card_digest", digest, null]), ok ? null : "rules_digest_mismatch"];
}
const ruled = (value, gate) => (gate !== null ? [null, gate] : [value, "not_in_feed"]);

function fields(...items) {
  const out = {}, reasons = {};
  for (const [key, value, reason] of items) {
    out[key] = value;
    if (value === null) reasons[key] = reason;
  }
  out.reasons = reasons;
  return out;
}
export function utcSeconds(textValue) {
  const m = typeof textValue === "string" ? UTC.exec(textValue) : null;
  if (!m) return null;
  const [y, mo, d, h, mi, s] = m.slice(1).map(Number);
  if (y < 1970) return null;
  const ms = Date.UTC(y, mo - 1, d, h, mi, s);
  const t = new Date(ms);
  if (t.getUTCFullYear() !== y || t.getUTCMonth() !== mo - 1 || t.getUTCDate() !== d
      || t.getUTCHours() !== h || t.getUTCMinutes() !== mi || t.getUTCSeconds() !== s) return null;
  return ms / 1000;
}
function span(blocks) {
  if (blocks === null || blocks === undefined) return null;
  return {blocks, seconds: blocks * BLOCK_SECONDS, hours: Math.round(blocks / 3) / 100};
}
// board_v2.utc_text: whole seconds as YYYY-MM-DDTHH:MM:SSZ, or null out of range.
const MAX_UTC_SECONDS = Math.floor(MAX_UTC_MS / 1000);
export function utcText(seconds) {
  if (seconds === null || seconds === undefined || !(seconds >= 0 && seconds <= MAX_UTC_SECONDS)) return null;
  return new Date(seconds * 1000).toISOString().slice(0, 19) + "Z";
}
const utcOfMs = ms => (ms === null ? null : utcText(Math.floor(ms / 1000)));
export function freshness(generatedAt, releasedCount, now, asOf = null) {
  if (!Number.isInteger(now)) throw new Error("now is whole seconds since the epoch");
  const [stamp, basis] = asOf !== null ? [asOf, "as_of_block"] : [utcSeconds(generatedAt), "generated_at"];
  const age = stamp === null ? null : now - stamp;
  const phase = age === null || age > STALE_AFTER_SECONDS ? "STALE" : releasedCount === 0 ? "PRE_FIRST_RELEASE" : "LIVE";
  const reason = generatedAt === null ? "not_in_feed" : "generated_at_unparseable";
  return [phase, {...fields(["age_seconds", age, reason]), stale_after_seconds: STALE_AFTER_SECONDS, basis}];
}
export function restamp(board, now) {
  const asOf = pick(board, "as_of_block");
  const [phase, fresh] = freshness(board.generated_at, board.next_release.released_windows, now,
    asOf === null ? null : utcSeconds(asOf.timestamp_utc));
  return {...board, phase, freshness: fresh};
}
const has = (o, k) => o !== null && o !== undefined && own(o, k);
const pick = (o, k) => (has(o, k) ? o[k] : null);
function rankingSection(board) {
  const names = new Set();
  for (const row of board.standing) for (const k of Object.keys(row.best)) if (NUMERIC_SECTIONS.includes(k)) names.add(k);
  if (!board.standing.length) return [null, "no_standing"];
  if (names.size !== 1) return [null, "ranking_section_ambiguous"];
  const [name] = names;
  const meta = pick(board.section_meta, name);
  const sense = meta === null ? null : meta.sense;
  return [fields(
    ["name", name, null],
    ["display", meta === null ? null : meta.display, "not_in_feed"],
    ["unit", meta === null ? null : meta.unit, "not_in_feed"],
    ["sense", sense, "not_in_feed"],
    ["label", sense === null ? null : `${name} (${sense.replaceAll("_", " ")})`, "not_in_feed"],
  ), null];
}
function king(board, section, challengers) {
  const incumbent = board.incumbent;
  if (incumbent === null) return [null, "no_released_incumbent"];
  const name = section === null ? null : section.name;
  const value = name === null ? null : pick(incumbent.sections, name);
  const runner = name === null ? null
    : board.standing.find(row => row.hotkey !== incumbent.hotkey && pick(row.best, name) !== null) || null;
  let margin = null, marginReason = null;
  if (name === null) marginReason = "no_ranking_section";
  else if (value === null) marginReason = "not_in_feed";
  else if (runner === null) marginReason = "no_runner_up";
  else if (section.sense === null) marginReason = "not_in_feed";
  else {
    const scale = 10 ** board.values.digits;
    const k = Math.round(value * scale), o = Math.round(runner.best[name] * scale);
    margin = (section.sense === "lower_is_better" ? o - k : k - o) / scale;
  }
  const gates = pick(incumbent.sections, "gates");
  const [ledger, why] = ledgerKing(board, incumbent);
  const of = key => (ledger === null ? null : ledger[key]);
  const crownedMs = of("crowned_utc_ms");
  const crowned = utcOfMs(crownedMs);
  const asOf = pick(board, "as_of_block");
  const held = crownedMs !== null && asOf !== null && asOf.timestamp_ms >= crownedMs
    ? Math.floor((asOf.timestamp_ms - crownedMs) / 1000) : null;
  const unpaid = ledger !== null && (ledger.eligible === false || ledger.share_now === 0);
  return [fields(
    ["hotkey", incumbent.hotkey, null],
    ["uid", of("uid"), why],
    ["coldkey", of("coldkey"), why],
    ["submission_id", incumbent.submission_id === null ? of("submission_id") : incumbent.submission_id, "not_in_feed"],
    ["section", name, "no_ranking_section"],
    ["value", value, name === null ? "no_ranking_section" : "not_in_feed"],
    ["registered_score", null, "not_in_feed"],
    ["since_block", incumbent.since_block, "not_in_feed"],
    ["since_utc", crowned, why],
    ["crowned_utc", crowned, why],
    ["held_for", held, why],
    ["crowned_epoch", null, "not_in_feed"],
    ["eligible", of("eligible"), why],
    ["eligibility_reason", of("reason"), why],
    ["share_now", of("share_now"), why],
    ["next_halving_utc", utcOfMs(of("next_halving_utc_ms")), unpaid ? "king_not_paid" : why],
    ["next_halving_epoch", null, "not_in_feed"],
    ["defences", of("challenges_survived"), why],
    ["margin", margin, marginReason],
    ["runner_up", runner === null ? null : runner.hotkey, name === null ? "no_ranking_section" : "no_runner_up"],
    ["challenger_state", has(challengers, incumbent.hotkey) ? challengers[incumbent.hotkey] : null, "not_a_challenger"],
    ["gates", gates === null ? null : {...gates}, "not_in_feed"],
  ), null];
}
// board_v2._ledger_king, _target and _next_release_time (VALIDATOR-33 A).
function ledgerKing(board, incumbent) {
  const k = pick(board, "king");
  if (k === null) return [null, "not_in_feed"];
  if (k.hotkey !== incumbent.hotkey) return [null, "king_not_released"];
  return [k, "not_in_feed"];
}
function targetV2(board) {
  const t = pick(board, "target_to_beat");
  const of = key => (t === null ? null : t[key]);
  const cmp = of("final_comparison"), score = of("score"), gates = of("gates");
  return fields(
    ["value", null, "not_in_feed"],
    ["kind", of("kind"), "not_in_feed"],
    ["posted_margin", of("final_margin_rel"), "not_in_feed"],
    ["screening_margin", of("screening_margin_rel"), "not_in_feed"],
    ["noise_guard", cmp === null ? null : fields(...COMPARISON_KEYS.map(k => [k, cmp[k], "not_in_feed"])), "not_in_feed"],
    ["registered_score", score === null ? null : fields(
      ["candidate", score.candidate, "not_in_feed"],
      ["registry_sha256", score.registry_sha256, "not_in_feed"],
      ["decision", score.decision, "not_in_feed"]), t === null ? "not_in_feed" : "no_registered_score"],
    ["gates", gates === null ? null : [...gates], "not_in_feed"],
  );
}
function nextReleaseTime(board, relGet) {
  const block = relGet("next_rotation_block");
  const asOf = pick(board, "as_of_block");
  if (block === null || asOf === null) return [block, null];
  return [block, utcText(Math.floor(asOf.timestamp_ms / 1000) + (block - asOf.number) * BLOCK_SECONDS)];
}
function coldkeys(board) {
  const ladder = pick(board, "ladder");
  if (ladder === null) return null;
  return ladder.coldkeys.map(row => ({
    ...fields(
      ["coldkey", row.coldkey, null],
      ["rank", row.rank, "not_in_feed"],
      ["displayed_score", row.displayed_score, "sealed_until_grain"],
      ["status", row.status, null],
      ["best_submission_id", row.best_submission_id, "not_in_feed"],
      ["displayed_at_block", row.displayed_at_block, "not_in_feed"],
    ),
    hotkeys: [...row.hotkeys],
  }));
}
function grainPct(board, gate) {
  const ladder = pick(board, "ladder");
  if (gate !== null) return [null, gate];
  if (ladder === null) return [null, "not_in_feed"];
  return [ladder.grain_pct, "grain_human_input"];
}
function leaderboard(board, section, challengers, lag, gate) {
  const name = section === null ? null : section.name;
  const kingKey = board.incumbent === null ? null : board.incumbent.hotkey;
  const entries = board.standing.map(row => ({
    ...fields(
      ["rank", row.rank, null],
      ["hotkey", row.hotkey, null],
      ["uid", null, "not_in_feed"],
      ["screening_value", name === null ? null : pick(row.best, name), name === null ? "no_ranking_section" : "not_in_feed"],
      ["registered_score", null, "not_in_feed"],
      ["best_at_block", row.best_at_block, "not_in_feed"],
      ["challenger_state", has(challengers, row.hotkey) ? challengers[row.hotkey] : null, "not_a_challenger"],
    ),
    is_king: row.hotkey === kingKey,
  }));
  return {...fields(["section", name, "no_ranking_section"], ["release_lag", ...lag], ["coldkeys", coldkeys(board), "not_in_feed"], ["grain_pct", ...grainPct(board, gate)]), label: has(board, "launch") ? LAUNCH_LADDER_LABEL : ELIGIBLE_LABEL, entries};
}
function historyV2(board, section) {
  const name = section === null ? null : section.name;
  const points = {};
  if (name !== null) {
    for (const key of Object.keys(board.history).sort(codePointCompare)) {
      const kept = board.history[key]
        .filter(p => p.receipt_block !== null && pick(p.sections, name) !== null)
        .map(p => ({receipt_block: p.receipt_block, value: p.sections[name]}));
      if (kept.length) points[key] = kept;
    }
  }
  const list = pick(board, "handovers");
  let rows = null, kings = null;
  if (list !== null) {
    rows = list.map(x => fields(
      ["utc", utcOfMs(x.utc_ms), "not_in_feed"],
      ["to_hotkey", x.to_hotkey, "not_in_feed"],
      ["from_hotkey", x.from_hotkey, "not_in_feed"],
      ["kind", x.kind, "not_in_feed"],
      ["eligible", x.eligible, "not_in_feed"],
      ["eligibility_reason", x.reason, "not_in_feed"],
    ));
    kings = rows.map((row, i) => fields(
      ["hotkey", row.to_hotkey, "not_in_feed"],
      ["crowned_utc", row.utc, "not_in_feed"],
      ["until_utc", i + 1 < rows.length ? rows[i + 1].utc : null, i + 1 < rows.length ? "not_in_feed" : "reigning"],
      ["eligible", row.eligible, "not_in_feed"],
    ));
  }
  return {
    ...fields(["era", board.challenge.rule_digest, null], ["section", name, "no_ranking_section"], ["kings", kings, "not_in_feed"], ["handovers", rows, "not_in_feed"]),
    points,
  };
}
function gatesV2(board, kingView) {
  const meta = pick(board.section_meta, "gates");
  const names = new Set(), failing = {};
  let count = 0;
  for (const miner of Object.values(board.miners)) {
    for (const row of miner.submissions) {
      const gates = pick(row.sections, "gates");
      if (gates === null) continue;
      count += 1;
      for (const gate of Object.keys(gates)) {
        names.add(gate);
        if (gates[gate] === "FAIL") failing[gate] = (failing[gate] || 0) + 1;
      }
    }
  }
  const sortedFailing = {};
  for (const g of Object.keys(failing).sort(codePointCompare)) sortedFailing[g] = failing[g];
  return {
    ...fields(
      ["display", meta === null ? null : meta.display, "not_in_feed"],
      ["unit", meta === null ? null : meta.unit, "not_in_feed"],
      ["king", kingView === null ? null : kingView.gates, kingView === null ? "no_released_incumbent" : "not_in_feed"],
    ),
    names: [...names].sort(codePointCompare),
    submissions_with_gates: count,
    failing: sortedFailing,
  };
}
export function projectV2(board, now, rulesCard = null) {
  if (board.schema !== BOARD_SCHEMA) throw new Error("board.v2 is projected from a verified board.v1 model");
  const rel = board.release || {};
  const relGet = k => (own(rel, k) ? rel[k] : null);
  // A launch board has no windows: its graded hotkeys stand in (launchProject).
  const released = has(board, "released_count") ? board.released_count : board.released_windows.length;
  const asOf = pick(board, "as_of_block");
  const [phase, fresh] = freshness(board.generated_at, released, now, asOf === null ? null : Math.floor(asOf.timestamp_ms / 1000));
  const [nextBlock, nextUtc] = nextReleaseTime(board, relGet);
  const [section, sectionReason] = rankingSection(board);
  const challengers = {};
  for (const row of board.challengers) if (!own(challengers, row.hotkey)) challengers[row.hotkey] = row.state;
  const lag = span(relGet("expected_lag_blocks"));
  const [kingView, kingReason] = king(board, section, challengers);
  const [rules, gate] = rulesStatus(board, rulesCard);
  const challenge = {};
  for (const k of Object.keys(board.challenge)) if (k !== "rule") challenge[k] = board.challenge[k];
  const status = pick(board, "miner_status");
  return {
    ...(status === null ? {} : {miner_status: status.map(row => ({
      hotkey: row.hotkey, received: row.received, scored: row.scored, refused: {...row.refused},
    }))}),
    ...fields(
      ["generated_at", board.generated_at, "not_in_feed"],
      ["ranking_section", section, sectionReason],
      ["king", kingView, kingReason],
      ["rotation", span(relGet("rotation_every_blocks")), "not_in_feed"],
      ["as_of_block", asOf === null ? null : {number: asOf.number, hash: asOf.hash, timestamp_utc: utcOfMs(asOf.timestamp_ms)}, "not_in_feed"],
    ),
    sections: Object.entries(board.section_meta).map(([name, meta]) => fields(
      ["name", name, null], ["display", meta.display, "not_in_feed"], ["unit", meta.unit, "not_in_feed"],
      ["sense", meta.sense, name === "gates" ? "not_a_numeric_section" : "not_in_feed"])),
    championship: fields(
      ["rounds", null, "not_in_feed"],
      ["entry", fields(["trigger_bar", null, "not_in_feed"], ["king_screening_display", null, "not_in_feed"], ["coldkeys", null, "not_in_feed"]), null],
    ),
    rules,
    target_to_beat: targetV2(board),
    schema: BOARD_V2_SCHEMA,
    source_schema: board.source_schema,
    fixture: board.fixture,
    labels: [...board.labels],
    challenge: {...challenge, ...fields(["rule", ...ruled(board.challenge.rule, gate)])},
    era: board.challenge.rule_digest,
    device_class: board.device_class,
    slug: board.slug,
    version: board.version,
    feed: {...board.feed},
    phase,
    freshness: fresh,
    block_seconds: BLOCK_SECONDS,
    eligible_leaderboard: leaderboard(board, section, challengers, ruled(lag, gate), gate),
    history: historyV2(board, section),
    next_round: fields(["every", ...ruled(span(relGet("rotation_every_blocks")), gate)], ["next_block", null, "not_in_feed"], ["next_utc", null, "not_in_feed"]),
    next_release: {
      ...fields(
        ["predicate", ...ruled(relGet("predicate"), gate)],
        ["retire_at", ...ruled(relGet("retire_at"), gate)],
        ["lag", ...ruled(lag, gate)],
        ["next_block", nextBlock, "not_in_feed"],
        ["next_utc", nextUtc, "not_in_feed"],
      ),
      released_windows: released,
    },
    gates: gatesV2(board, kingView),
    excluded_canaries: board.excluded_canaries,
    ...launchV2(board),
  };
}
// The launch board's standing as the validator signed it (board_v2._launch); absent for a score feed.
function launchV2(board) {
  const launch = pick(board, "launch");
  if (launch === null) return {};
  const gateNames = {};
  for (const k of Object.keys(launch.gate_names)) gateNames[k] = [...launch.gate_names[k]];
  return {launch: {
    counts: {...launch.counts},
    ...fields(
      ["margin", launch.margin, "no_registered_noise"],
      ["to_beat", launch.to_beat, "no_registered_noise"],
      ["baseline_total", launch.baseline_total, "a_king_is_crowned"],
      ["king_since_epoch", launch.king_since_epoch, "no_king"],
    ),
    exam_version_label: launch.exam_version_label,
    network: launch.network,
    gate_names: gateNames,
  }};
}

// Sent with every server-side fetch of a feed or snapshot. Cloudflare can
// refuse a request with no browser-like agent, so name this one plainly.
export const FETCH_HEADERS = Object.freeze({"User-Agent": "carbon-dashboard/1 (+https://dashboard.carbonphysics.ai)", "Accept": "application/json"});
