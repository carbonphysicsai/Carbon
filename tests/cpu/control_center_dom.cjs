// A small DOM for driving the Control Center's own scripts without a browser
// (LP-PROD-F). It holds enough of the DOM the page uses - elements, text,
// attributes, dataset, classList, selectors, events with capture and
// bubbling, focus, hover, presses, forms, radios and details - to run
// index.html with app.js, research_charts.js, research_view.js and
// research_tools.js against a scripted controller, on a fake clock.
//
// It parses only the page's own index.html. It is a test instrument, not a
// browser: layout, CSS and real networking are absent by design.
"use strict";
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const {webcrypto} = require("node:crypto");

const VOID = new Set(["area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"]);
const FOCUSABLE = new Set(["A", "BUTTON", "INPUT", "SELECT", "TEXTAREA", "SUMMARY"]);
const ENTITIES = {amp: "&", lt: "<", gt: ">", quot: "\"", apos: "'", nbsp: " ", mdash: "—", middot: "·", rarr: "→", larr: "←", hellip: "…"};
const kebab = name => name.replace(/[A-Z]/g, c => "-" + c.toLowerCase());
const decode = text => text.replace(/&(#x?[0-9a-fA-F]+|[a-zA-Z]+);/g, (whole, name) => {
  if (name[0] === "#") return String.fromCodePoint(name[1] === "x" || name[1] === "X" ? parseInt(name.slice(2), 16) : parseInt(name.slice(1), 10));
  return name in ENTITIES ? ENTITIES[name] : whole;
});

class Node {
  constructor(doc) { this.ownerDocument = doc; this.parentNode = null; this.childNodes = []; this.listeners = []; }
  get parentElement() { return this.parentNode && this.parentNode.nodeType === 1 ? this.parentNode : null; }
  get firstChild() { return this.childNodes[0] || null; }
  get lastChild() { return this.childNodes[this.childNodes.length - 1] || null; }
  get children() { return this.childNodes.filter(node => node.nodeType === 1); }
  get isConnected() { let node = this; while (node) { if (node === this.ownerDocument) return true; node = node.parentNode; } return false; }
  get textContent() { return this.childNodes.map(node => node.textContent).join(""); }
  set textContent(value) {
    this._detachAll();
    const text = String(value ?? "");
    if (text !== "") this._insert(new Text(this.ownerDocument, text), null);
  }
  contains(node) { while (node) { if (node === this) return true; node = node.parentNode; } return false; }
  // Removing a subtree that holds focus moves focus to the body, as a browser does.
  _released(node) {
    const doc = this.ownerDocument;
    if (doc && doc._active && node.contains(doc._active)) doc._active = null;
  }
  _detach(node) {
    const index = this.childNodes.indexOf(node);
    if (index >= 0) { this._released(node); this.childNodes.splice(index, 1); node.parentNode = null; this.ownerDocument && this.ownerDocument._mutated(this); }
  }
  _detachAll() { for (const node of [...this.childNodes]) this._detach(node); }
  _insert(node, before) {
    if (typeof node === "string") node = new Text(this.ownerDocument, node);
    if (node.parentNode) node.parentNode._detach(node);
    const index = before ? this.childNodes.indexOf(before) : -1;
    if (index >= 0) this.childNodes.splice(index, 0, node); else this.childNodes.push(node);
    node.parentNode = this;
    this.ownerDocument && this.ownerDocument._mutated(this);
    return node;
  }
  appendChild(node) { return this._insert(node, null); }
  append(...nodes) { for (const node of nodes) this._insert(node, null); }
  prepend(...nodes) { const first = this.childNodes[0] || null; for (const node of nodes) this._insert(node, first); }
  insertBefore(node, before) { return this._insert(node, before); }
  removeChild(node) { this._detach(node); return node; }
  replaceChildren(...nodes) { this._detachAll(); this.append(...nodes); }
  remove() { if (this.parentNode) this.parentNode._detach(this); }
  replaceWith(...nodes) {
    const parent = this.parentNode;
    if (!parent) return;
    for (const node of nodes) parent._insert(node, this);
    parent._detach(this);
  }
  addEventListener(type, fn, options) {
    const capture = options === true || Boolean(options && options.capture);
    this.listeners.push({type, fn, capture, once: Boolean(options && options.once)});
  }
  removeEventListener(type, fn) { this.listeners = this.listeners.filter(entry => entry.type !== type || entry.fn !== fn); }
  dispatchEvent(event) { return dispatch(this, event); }
}

class Text extends Node {
  constructor(doc, data) { super(doc); this.nodeType = 3; this.data = String(data); }
  get textContent() { return this.data; }
  set textContent(value) { this.data = String(value ?? ""); this.ownerDocument && this.ownerDocument._mutated(this.parentNode || this); }
}

function datasetOf(element) {
  return new Proxy({}, {
    get: (_, name) => typeof name === "string" ? element.getAttribute("data-" + kebab(name)) ?? undefined : undefined,
    set: (_, name, value) => { element.setAttribute("data-" + kebab(name), String(value)); return true; },
    deleteProperty: (_, name) => { element.removeAttribute("data-" + kebab(name)); return true; },
    has: (_, name) => element.hasAttribute("data-" + kebab(name)),
    ownKeys: () => [...element.attributes.keys()].filter(key => key.startsWith("data-")).map(key => key.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())),
    getOwnPropertyDescriptor: (_, name) => element.hasAttribute("data-" + kebab(name)) ? {enumerable: true, configurable: true, value: element.getAttribute("data-" + kebab(name))} : undefined,
  });
}

class Element extends Node {
  constructor(doc, tag, namespace = null) {
    super(doc);
    this.nodeType = 1;
    this.namespaceURI = namespace;
    this.tagName = namespace ? tag : tag.toUpperCase();
    this.localName = tag.toLowerCase();
    this.attributes = new Map();
    this.dataset = datasetOf(this);
    this.style = {setProperty(name, value) { this[name] = value; }};
    this._checked = null;
    this._value = null;
  }
  getAttribute(name) { return this.attributes.has(name) ? this.attributes.get(name) : null; }
  // Counted as a change only when the value moves: setting what is already
  // there redraws nothing.
  setAttribute(name, value) {
    const text = String(value);
    if (this.attributes.get(name) === text) return;
    this.attributes.set(name, text); this.ownerDocument && this.ownerDocument._mutated(this);
  }
  removeAttribute(name) { if (this.attributes.delete(name)) this.ownerDocument && this.ownerDocument._mutated(this); }
  hasAttribute(name) { return this.attributes.has(name); }
  toggleAttribute(name, on) { if (on) this.setAttribute(name, ""); else this.removeAttribute(name); }
  get classList() {
    const element = this;
    const names = () => (element.getAttribute("class") || "").split(/\s+/).filter(Boolean);
    return {
      add(...more) { element.setAttribute("class", [...new Set([...names(), ...more])].join(" ")); },
      remove(...less) { element.setAttribute("class", names().filter(name => !less.includes(name)).join(" ")); },
      toggle(name, force) { const on = force === undefined ? !names().includes(name) : force; if (on) this.add(name); else this.remove(name); return on; },
      contains(name) { return names().includes(name); },
    };
  }
  get className() { return this.getAttribute("class") || ""; }
  set className(value) { this.setAttribute("class", value); }
  get id() { return this.getAttribute("id") || ""; }
  set id(value) { this.setAttribute("id", value); }
  get htmlFor() { return this.getAttribute("for") || ""; }
  set htmlFor(value) { this.setAttribute("for", value); }
  get type() {
    if (this.tagName === "INPUT") return (this.getAttribute("type") || "text").toLowerCase();
    if (this.tagName === "BUTTON") return (this.getAttribute("type") || "submit").toLowerCase();
    return this.getAttribute("type") || "";
  }
  set type(value) { this.setAttribute("type", value); }
  get checked() { return this._checked === null ? this.hasAttribute("checked") : this._checked; }
  set checked(value) {
    const on = Boolean(value);
    if (on && this.type === "radio" && this.getAttribute("name")) {
      const root = this.ownerDocument;
      for (const other of root.querySelectorAll("input[type=radio]")) if (other !== this && other.getAttribute("name") === this.getAttribute("name")) other._checked = false;
    }
    this._checked = on;
  }
  get value() {
    if (this.tagName === "SELECT") { const chosen = this.options.find(option => option.selected) || this.options[0]; return chosen ? chosen.value : ""; }
    if (this.tagName === "OPTION") return this.hasAttribute("value") ? this.getAttribute("value") : this.textContent;
    if (this.tagName === "TEXTAREA") return this._value === null ? this.textContent : this._value;
    if (this.tagName === "INPUT") {
      const raw = this._value === null ? (this.getAttribute("value") || "") : this._value;
      // A number input answers "" for text that is not a number, as a browser's does.
      return this.type === "number" && raw !== "" && !/^-?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$/.test(raw) ? "" : raw;
    }
    return this.getAttribute("value") || "";
  }
  set value(value) {
    if (this.tagName === "SELECT") { for (const option of this.options) option._selected = option.value === String(value); return; }
    if (this.tagName === "OPTION") { this.setAttribute("value", value); return; }
    this._value = String(value ?? "");
  }
  get selected() { return Boolean(this._selected); }
  set selected(value) { if (value && this.parentNode) for (const option of this.parentNode.children) option._selected = false; this._selected = Boolean(value); }
  get options() { return this.tagName === "SELECT" ? this.querySelectorAll("option") : []; }
  get form() { let node = this.parentNode; while (node && node.tagName !== "FORM") node = node.parentNode; return node || null; }
  get disabledHere() {
    if (this.hasAttribute("disabled")) return true;
    let node = this.parentNode;
    while (node && node.nodeType === 1) { if (node.tagName === "FIELDSET" && node.hasAttribute("disabled")) return true; node = node.parentNode; }
    return false;
  }
  focus() { if (this.isConnected) this.ownerDocument._active = this; }
  blur() { if (this.ownerDocument._active === this) this.ownerDocument._active = null; }
  click() { return activate(this); }
  scrollIntoView() {}
  getBoundingClientRect() { return {left: 0, top: 0, width: 480, height: 200, right: 480, bottom: 200}; }
  matches(selector) { return parse(selector).some(chain => matchChain(this, chain, null)); }
  closest(selector) { let node = this; while (node && node.nodeType === 1) { if (node.matches(selector)) return node; node = node.parentNode; } return null; }
  querySelectorAll(selector) { return select(this, selector); }
  querySelector(selector) { return select(this, selector)[0] || null; }
}
for (const [property, attribute] of [["href", "href"], ["name", "name"], ["title", "title"], ["placeholder", "placeholder"], ["min", "min"], ["max", "max"], ["step", "step"], ["autocomplete", "autocomplete"], ["alt", "alt"], ["src", "src"], ["role", "role"], ["download", "download"]]) {
  Object.defineProperty(Element.prototype, property, {get() { return this.getAttribute(attribute) || ""; }, set(value) { this.setAttribute(attribute, value); }});
}
for (const [property, attribute] of [["rows", "rows"], ["maxLength", "maxlength"], ["start", "start"]]) {
  Object.defineProperty(Element.prototype, property, {get() { return Number(this.getAttribute(attribute) || 0); }, set(value) { this.setAttribute(attribute, value); }});
}
for (const [property, attribute] of [["hidden", "hidden"], ["disabled", "disabled"], ["open", "open"], ["readOnly", "readonly"], ["required", "required"]]) {
  Object.defineProperty(Element.prototype, property, {get() { return this.hasAttribute(attribute); }, set(value) { this.toggleAttribute(attribute, Boolean(value)); }});
}
Object.defineProperty(Element.prototype, "spellcheck", {get() { return this.getAttribute("spellcheck") !== "false"; }, set(value) { this.setAttribute("spellcheck", String(Boolean(value))); }});

// ---- Selectors: tag, *, #id, .class, [attr], [attr=value], :checked,
// :hover, :scope, descendant and child combinators, comma lists. ----
function splitTop(text, separator) {
  const parts = []; let depth = 0, quote = null, start = 0;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quote) { if (c === quote) quote = null; continue; }
    if (c === "\"" || c === "'") quote = c;
    else if (c === "[" || c === "(") depth++;
    else if (c === "]" || c === ")") depth--;
    else if (c === separator && depth === 0) { parts.push(text.slice(start, i)); start = i + 1; }
  }
  parts.push(text.slice(start));
  return parts;
}
const cache = new Map();
function parse(selector) {
  if (cache.has(selector)) return cache.get(selector);
  const chains = splitTop(selector, ",").map(part => {
    const tokens = part.trim().replace(/\s*>\s*/g, " > ").split(/\s+(?![^[]*\])/).filter(Boolean);
    const chain = []; let combinator = " ";
    for (const token of tokens) {
      if (token === ">") { combinator = ">"; continue; }
      chain.push({combinator, compound: compound(token)}); combinator = " ";
    }
    return chain;
  });
  cache.set(selector, chains);
  return chains;
}
function compound(token) {
  const out = {tag: null, ids: [], classes: [], attrs: [], pseudos: []};
  const pattern = /(^[a-zA-Z][a-zA-Z0-9-]*|^\*)|#([\w-]+)|\.([\w-]+)|\[([\w-]+)(?:=(?:"([^"]*)"|'([^']*)'|([^\]]*)))?\]|:([\w-]+)/g;
  let match;
  while ((match = pattern.exec(token))) {
    if (match[1]) out.tag = match[1] === "*" ? null : match[1].toUpperCase();
    else if (match[2]) out.ids.push(match[2]);
    else if (match[3]) out.classes.push(match[3]);
    else if (match[4]) out.attrs.push([match[4], match[5] ?? match[6] ?? match[7] ?? null]);
    else if (match[8]) out.pseudos.push(match[8]);
  }
  return out;
}
function matchCompound(element, c, scope) {
  if (element.nodeType !== 1) return false;
  if (c.tag && element.tagName.toUpperCase() !== c.tag) return false;
  for (const id of c.ids) if (element.id !== id) return false;
  for (const name of c.classes) if (!element.classList.contains(name)) return false;
  for (const [name, value] of c.attrs) {
    if (name === "type" && element.tagName === "INPUT") { if (value !== null && element.type !== value) return false; continue; }
    if (!element.hasAttribute(name)) return false;
    if (value !== null && element.getAttribute(name) !== value) return false;
  }
  for (const pseudo of c.pseudos) {
    if (pseudo === "checked" && !(element.checked || element.selected)) return false;
    if (pseudo === "hover" && !(element.ownerDocument._hovered && element.contains(element.ownerDocument._hovered))) return false;
    if (pseudo === "scope" && element !== scope) return false;
  }
  return true;
}
function matchChain(element, chain, scope) {
  const at = (node, index) => {
    if (!matchCompound(node, chain[index].compound, scope)) return false;
    if (index === 0) return true;
    if (chain[index].combinator === ">") return node.parentNode && node.parentNode.nodeType === 1 && at(node.parentNode, index - 1);
    let up = node.parentNode;
    while (up && up.nodeType === 1) { if (at(up, index - 1)) return true; up = up.parentNode; }
    return false;
  };
  return at(element, chain.length - 1);
}
function select(root, selector) {
  const chains = parse(selector);
  const found = [];
  const walk = node => { for (const child of node.childNodes) if (child.nodeType === 1) { if (chains.some(chain => matchChain(child, chain, root))) found.push(child); walk(child); } };
  walk(root);
  return found;
}

// ---- Events, with capture and bubbling; errors are kept, not thrown. ----
function dispatch(target, event) {
  const doc = target.ownerDocument || target.document || target;
  const pathUp = [];
  for (let node = target; node; node = node.parentNode) pathUp.push(node);
  if (doc && doc.defaultView && pathUp[pathUp.length - 1] === doc) pathUp.push(doc.defaultView);
  event.target = target;
  const call = (node, phase) => {
    for (const entry of [...node.listeners]) {
      if (entry.type !== event.type) continue;
      if (phase === "capture" && !entry.capture) continue;
      if (phase === "bubble" && entry.capture) continue;
      event.currentTarget = node;
      if (entry.once) node.removeEventListener(entry.type, entry.fn);
      try {
        const result = entry.fn.call(node, event);
        if (result && typeof result.catch === "function") result.catch(error => doc._errors.push(error));
      } catch (error) { doc._errors.push(error); }
      if (event._stopped) return;
    }
  };
  for (const node of [...pathUp].reverse().slice(0, -1)) { call(node, "capture"); if (event._stopped) return !event.defaultPrevented; }
  call(target, "target");
  if (event.bubbles) for (const node of pathUp.slice(1)) { if (event._stopped) break; call(node, "bubble"); }
  return !event.defaultPrevented;
}
function makeEvent(type, init = {}) {
  return {type, bubbles: Boolean(init.bubbles), cancelable: Boolean(init.cancelable), defaultPrevented: false, isTrusted: true,
    preventDefault() { if (this.cancelable) this.defaultPrevented = true; }, stopPropagation() { this._stopped = true; }, ...init.detail};
}
// What a click does after its handlers: toggles, radios, submits, links,
// labels and summaries, as a browser does.
function activate(element) {
  if (["BUTTON", "INPUT", "SELECT", "TEXTAREA"].includes(element.tagName) && element.disabledHere) return false;
  const doc = element.ownerDocument;
  let changed = false, before = null;
  if (element.tagName === "INPUT" && element.type === "checkbox") { before = element.checked; element.checked = !before; changed = true; }
  if (element.tagName === "INPUT" && element.type === "radio" && !element.checked) { element.checked = true; changed = true; }
  const allowed = dispatch(element, makeEvent("click", {bubbles: true, cancelable: true}));
  if (!allowed && before !== null) { element.checked = before; return false; }
  if (changed) { dispatch(element, makeEvent("input", {bubbles: true})); dispatch(element, makeEvent("change", {bubbles: true})); }
  if (!allowed) return false;
  if (element.tagName === "BUTTON" && element.type === "submit" && element.form) {
    dispatch(element.form, makeEvent("submit", {bubbles: true, cancelable: true}));
  } else if (element.tagName === "A" && element.getAttribute("href")?.startsWith("#")) {
    doc.defaultView.location.hash = element.getAttribute("href");
  } else if (element.tagName === "LABEL") {
    const control = element.htmlFor ? doc.getElementById(element.htmlFor) : element.querySelector("input, select, textarea, button");
    if (control && control !== element) activate(control);
  } else if (element.tagName === "SUMMARY" && element.parentNode?.tagName === "DETAILS") {
    element.parentNode.open = !element.parentNode.open;
    dispatch(element.parentNode, makeEvent("toggle"));
  }
  return true;
}

class Document extends Node {
  constructor() {
    super(null);
    this.ownerDocument = this;
    this.nodeType = 9;
    this._active = null; this._hovered = null; this._errors = []; this.mutations = 0;
    this.documentElement = new Element(this, "html");
    this._insert(this.documentElement, null);
  }
  // Every change of the tree, text or an attribute, with where it happened.
  _mutated(node) {
    this.mutations++;
    if (this.trace) {
      const where = [];
      for (let n = node; n && n.nodeType === 1 && where.length < 4; n = n.parentNode) where.push(n.localName + (n.id ? "#" + n.id : "") + (n.getAttribute("data-part") ? "[" + n.getAttribute("data-part") + "]" : ""));
      this.trace.push(where.join(" < ") || (node.nodeType === 3 ? "text" : "?"));
    }
  }
  get body() { return this.querySelector("body") || this.documentElement; }
  get head() { return this.querySelector("head"); }
  get activeElement() { return this._active && this._active.isConnected ? this._active : this.body; }
  createElement(tag) { return new Element(this, tag); }
  createElementNS(namespace, tag) { return new Element(this, tag, namespace); }
  createTextNode(text) { return new Text(this, text); }
  createRange() { return {selectNodeContents() {}}; }
  execCommand() { return false; }
  getElementById(id) { return this.querySelector("#" + CSS_ESCAPE(id)); }
  querySelectorAll(selector) { return select(this, selector); }
  querySelector(selector) { return select(this, selector)[0] || null; }
}
const CSS_ESCAPE = value => String(value).replace(/([^\w-])/g, "\\$1");
// getElementById by a scan: ids here are plain, so no escaping is needed.
Document.prototype.getElementById = function (id) {
  let found = null;
  const walk = node => { for (const child of node.childNodes) { if (found) return; if (child.nodeType === 1) { if (child.getAttribute("id") === id) { found = child; return; } walk(child); } } };
  walk(this);
  return found;
};

function parseHTML(doc, html) {
  const root = doc.documentElement;
  const stack = [root];
  const pattern = /<!--[\s\S]*?-->|<!doctype[^>]*>|<(\/?)([a-zA-Z][a-zA-Z0-9-]*)((?:\s+[^\s=>/]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+))?)*)\s*(\/?)>|([^<]+)/gi;
  let match, inScript = false;
  while ((match = pattern.exec(html))) {
    const [whole, closing, tag, attributes, selfClosing, text] = match;
    if (whole.startsWith("<!")) continue;
    const top = stack[stack.length - 1];
    if (text !== undefined) { if (!inScript && text) top.append(new Text(doc, decode(text))); continue; }
    const name = tag.toLowerCase();
    if (closing) {
      if (name === "script" || name === "noscript") { inScript = false; continue; }
      for (let i = stack.length - 1; i > 0; i--) if (stack[i].localName === name) { stack.length = i; break; }
      continue;
    }
    if (name === "script" || name === "noscript") { inScript = !selfClosing; continue; }
    if (name === "html") { readAttributes(root, attributes); continue; }
    const element = new Element(doc, name);
    readAttributes(element, attributes);
    top.append(element);
    if (!VOID.has(name) && !selfClosing) stack.push(element);
  }
}
function readAttributes(element, text) {
  const pattern = /([^\s=>/]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g;
  let match;
  while ((match = pattern.exec(text || ""))) element.attributes.set(match[1].toLowerCase(), decode(match[2] ?? match[3] ?? match[4] ?? ""));
}

class Storage {
  constructor() { this.map = new Map(); this.broken = false; }
  getItem(key) { if (this.broken) throw new Error("storage refused"); return this.map.has(key) ? this.map.get(key) : null; }
  setItem(key, value) { if (this.broken) throw new Error("storage refused"); this.map.set(key, String(value)); }
  removeItem(key) { if (this.broken) throw new Error("storage refused"); this.map.delete(key); }
  clear() { this.map.clear(); }
}

// A fake clock: timers run only when a test advances time.
class Clock {
  constructor(start = 1_800_000_000_000) { this.now = start; this.timers = []; this.next = 1; }
  set(fn, ms, repeat) { const id = this.next++; this.timers.push({id, at: this.now + Math.max(0, Number(ms) || 0), fn, repeat: repeat ? Math.max(1, Number(ms) || 0) : 0}); return id; }
  clear(id) { this.timers = this.timers.filter(timer => timer.id !== id); }
}

// The page: index.html and its scripts in one context, against `server`.
// `server(request)` answers {status, body} or {network: true} or
// {timeout: true}, or a promise of one; it sees {method, path, body, headers}.
async function openPage(root, server, {sessionStorage, localStorage, clock} = {}) {
  const doc = new Document();
  parseHTML(doc, fs.readFileSync(path.join(root, "index.html"), "utf8"));
  const time = clock || new Clock();
  const requests = [];
  let pending = 0;
  const location = {
    _hash: "",
    get hash() { return this._hash; },
    set hash(value) {
      const next = String(value).startsWith("#") || value === "" ? String(value) : "#" + value;
      if (next === this._hash) return;
      this._hash = next === "#" ? "" : next;
      dispatch(window, makeEvent("hashchange"));
    },
    get href() { return "http://127.0.0.1:8788/" + this._hash; },
  };
  const window = {
    document: doc, location,
    history: {replaceState(_, __, url) { location._hash = String(url).startsWith("#") ? String(url) : location._hash; }},
    sessionStorage: sessionStorage || new Storage(), localStorage: localStorage || new Storage(),
    crypto: webcrypto,
    AbortSignal: {timeout: ms => ({timeout: ms})},
    CSS: {escape: CSS_ESCAPE},
    URL: {createObjectURL: () => "blob:fixture", revokeObjectURL() {}},
    Blob, TextEncoder, TextDecoder, atob, btoa,
    navigator: {clipboard: {writeText: async () => {}}},
    getSelection: () => ({removeAllRanges() {}, addRange() {}}),
    confirm: () => true,
    console: {log() {}, info() {}, warn() {}, error: (...args) => doc._errors.push(new Error(args.map(String).join(" ")))},
    setTimeout: (fn, ms) => time.set(fn, ms, false),
    clearTimeout: id => time.clear(id),
    setInterval: (fn, ms) => time.set(fn, ms, true),
    clearInterval: id => time.clear(id),
    Event: function Event(type, init) { return makeEvent(type, init); },
    listeners: [],
    addEventListener: Node.prototype.addEventListener,
    removeEventListener: Node.prototype.removeEventListener,
    fetch: async (url, init = {}) => {
      const request = {method: init.method || "GET", path: String(url), headers: init.headers || {}, body: init.body === undefined ? undefined : JSON.parse(init.body), timeout: init.signal?.timeout};
      requests.push(request);
      pending++;
      try {
        const answer = await server(request);
        if (answer.network) throw new TypeError("Failed to fetch");
        if (answer.timeout) { const error = new Error("The operation timed out."); error.name = "TimeoutError"; throw error; }
        const status = answer.status ?? 200;
        return {ok: status >= 200 && status < 300, status, json: async () => { if (answer.raw !== undefined) return JSON.parse(answer.raw); return JSON.parse(JSON.stringify(answer.body ?? {})); }};
      } finally { pending--; }
    },
  };
  window.window = window; window.self = window;
  doc.defaultView = window;
  const context = vm.createContext(window);
  vm.runInContext("Date.now = () => __now();", Object.assign(context, {__now: () => time.now}));
  const page = {
    doc, window, context, requests, clock: time,
    $: id => doc.getElementById(id),
    errors: doc._errors,
    // Let every promise settle: answers, their handlers and what they start.
    // A request a test holds open stays open; everything else settles.
    async settle() {
      for (let round = 0; round < 60; round++) {
        await new Promise(resolve => setImmediate(resolve));
        if (!pending && round > 3) { await new Promise(resolve => setImmediate(resolve)); if (!pending) return; }
      }
    },
    // Advance the clock, running each timer when it falls due.
    async advance(ms) {
      const end = time.now + ms;
      for (;;) {
        time.timers.sort((a, b) => a.at - b.at || a.id - b.id);
        const due = time.timers.find(timer => timer.at <= end);
        if (!due) break;
        time.now = Math.max(time.now, due.at);
        if (due.repeat) due.at += due.repeat; else time.clear(due.id);
        try { due.fn(); } catch (error) { doc._errors.push(error); }
        await page.settle();
      }
      time.now = end;
      await page.settle();
    },
    go(hash) { location.hash = hash; },
    // A person's click: press, (optionally) let time pass, release, click.
    // A click lands only if its element is still on the page, as in a browser.
    async press(element, during = 0) {
      dispatch(element, makeEvent("pointerdown", {bubbles: true}));
      dispatch(element, makeEvent("mousedown", {bubbles: true}));
      if (FOCUSABLE.has(element.tagName)) element.focus();
      if (during) await page.advance(during);
      const landed = element.isConnected;
      dispatch(landed ? element : doc.body, makeEvent("pointerup", {bubbles: true}));
      if (landed) activate(element);
      await page.settle();
      await page.advance(0);
      return landed;
    },
    hover(element) { doc._hovered = element; },
    unhover() { doc._hovered = null; },
    // Typing: the value changes and the field says so, as a keyboard does.
    async type(element, text) {
      element.focus();
      element.value = text;
      dispatch(element, makeEvent("input", {bubbles: true}));
      await page.settle();
    },
    async change(element, value) {
      element.value = value;
      dispatch(element, makeEvent("input", {bubbles: true}));
      dispatch(element, makeEvent("change", {bubbles: true}));
      await page.settle();
    },
    text(id) { const node = typeof id === "string" ? doc.getElementById(id) : id; return node ? node.textContent : ""; },
  };
  for (const name of ["app.js", "research_charts.js", "research_view.js", "research_tools.js"]) {
    vm.runInContext(fs.readFileSync(path.join(root, name), "utf8"), context, {filename: name});
  }
  await page.settle();
  return page;
}

module.exports = {openPage, Clock, Storage, parseHTML, Document};
