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
export const FIXTURE_PUBLIC_KEY = "d55fec2a82d5280786d8282263c8f324f43166eb036d38fb64bce7469d742cc8";
const NUMERIC_SECTIONS = ["accuracy", "design_q", "near_limit"];
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
  const plain = o => Object.assign({}, o);
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
export function canonicalBytes(document) {
  const body = {};
  for (const k of Object.keys(document)) if (k !== "signature") body[k] = document[k];
  return new TextEncoder().encode(DOMAIN + canonical(body));
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

export async function verify(document, pinned) {
  if (!isDict(document) || get(document, "schema") !== SCHEMA) throw new FeedRefused("schema_unsupported");
  const signature = get(document, "signature");
  if (typeof signature !== "string" || !HEX_SIGNATURE.test(signature)) throw new FeedRefused("signature_missing");
  const message = canonicalBytes(document);
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
  for (const k of ["retire_at", "rotation_every_blocks", "expected_lag_blocks"]) out[k] = int(get(raw, k), "release_invalid", {optional: true});
  return out;
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

export function boardSlug(challengeId, deviceClass) {
  return `${challengeId}--${deviceClass}`.toLowerCase().replace(/[^a-z0-9.-]+/g, "-").replace(/^-+|-+$/g, "");
}
const keyOf = (blockOrNull, id) => [blockOrNull || 0, id];
const cmp = (a, b) => (a < b ? -1 : a > b ? 1 : 0);

export async function project(document, pinned) {
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
  return {
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
    released_windows: [...windows],
    incumbent,
    challengers,
    standing,
    history,
    miners: sortedMiners,
    excluded_canaries: canaries,
    showcase_panel: showcase(get(document, "showcase"), incumbent, pinned),
    feed: {
      key_id: "feed-" + (await sha256Hex(hexBytes(signer))).slice(0, 16),
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
