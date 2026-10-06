"use strict";
(() => {
  let token = "";
  // ---- The session link (LP-PROD-C D14). The Control Center prints its
  // loopback address with #token=<token> once this page declares, in its
  // own head, that it reads the fragment (index.html, carbon-session-link
  // fragment-v1). The fragment is read here, first, and removed from the
  // address bar by replacing this history entry, before anything reads or
  // stores the route; the token then lives in this tab's memory only, as a
  // pasted one does. A fragment is never sent to the server. Returns the
  // token, "" for a link this page cannot read, or null for no link.
  const SESSION_LINK = /^#token=([A-Za-z0-9_-]{1,512})$/;
  function takeSessionLink() {
    const hash = location.hash;
    if (!hash.startsWith("#token=")) return null;
    history.replaceState(null, "", location.pathname + location.search);
    const match = SESSION_LINK.exec(hash);
    return match ? match[1] : "";
  }
  const linkToken = takeSessionLink();
  let selected = "";
  let runs = [];
  let pending = null;
  let busy = false;
  let polling = false;
  let connected = false;
  let landed = false;
  let developmentSources = [];
  let research = {preflight: {available: false}, runs: []};
  let pendingResearch = null;
  const expandedResearch = new Set();
  // The Control Center's capability document: every choice this page offers is
  // rendered from it, with its real availability. Never a static list.
  let caps = null;
  // Bumped on each read, so the views built from it rebuild only then.
  let capsVersion = 0;
  const CAPS_SCHEMA = "carbon.control-center.capabilities.v1";
  // Every launch-time choice with its true availability, from the options
  // operation - the same one an MCP client reads.
  let launchOptions = null;
  // The one launch composition. The no-limits and set-limits paths edit this
  // same object, templates save and load it, and the launch body is built from
  // it; there is no second copy to disagree with. `agent` stays null until the
  // person or a template chooses, so a default is never mistaken for a choice.
  let composition = {agent: null, budget: {}};
  let launchPath = "quick";
  let launchShape = null;
  // Every operation the controller lists (GET /api/v1/operations), with the
  // fields each takes: Graphite's launch fields and the Library's requests
  // carry only what the controller declares.
  let operationsListed = null;
  // The wizard's own choices. Persisted in this browser (never a token or key).
  let wizard = {step: "challenge", challenge: null, agentChoice: null, provider: null, model: null};
  const STEPS = [["challenge", "Challenge"], ["agent", "Agent"], ["model", "Model"], ["compute", "Compute"], ["limits", "Tools & limits"], ["review", "Review"], ["launch", "Launch"]];
  const TABS = [["overview", "Overview"], ["experiments", "Experiments"], ["metrics", "Metrics"], ["journal", "Research Journal"], ["artifacts", "Artifacts"], ["submission", "Submission"], ["logs", "Logs"], ["settings", "Settings"]];
  const TERMINAL = ["COMPLETED", "STOPPED", "READBACK_UNAVAILABLE", "EXPIRED"];
  // The keyed operations, as a person names them.
  const OPERATION_NAMES = {practice: "practice", freeze_candidate: "freeze", submit: "submit"};
  // The prelaunch review's evaluation statuses under which a submit can be
  // sent (LP-PROD-E); any other is said plainly as unavailable.
  const EVALUABLE = ["INTAKE_CONFIGURED", "VALIDATOR_ON_THIS_MACHINE"];
  const templateKey = "carbon.launchpad.launch-templates.v1";
  const wizardKey = "carbon.control-center.wizard.v1";
  const draftKey = "carbon.control-center.journey-drafts.v1";
  const routeKey = "carbon.control-center.route.v1";
  const researchKey = "carbon.launchpad.pending-research.v1";
  const pendingKey = "carbon.launchpad.pending.v1";
  let storageError = false;
  try { pending = JSON.parse(sessionStorage.getItem(pendingKey) || "null"); pendingResearch = JSON.parse(sessionStorage.getItem(researchKey) || "null"); }
  catch (_) { storageError = true; }
  // A request held from before this page loaded was sent and not answered:
  // its outcome is unknown, whatever version of the page held it.
  for (const kept of [pending, pendingResearch]) if (kept && typeof kept === "object" && kept.unknown !== false) kept.unknown = true;
  // Local conveniences only: a refused storage never blocks the page.
  function stored(key, fallback) {
    try { const value = JSON.parse(localStorage.getItem(key) || "null"); return value && typeof value === "object" && !Array.isArray(value) ? value : fallback; }
    catch (_) { return fallback; }
  }
  function store(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch (_) { return false; } }
  // What a person has typed into a campaign's journey, kept across reloads.
  const journeyDrafts = stored(draftKey, {});
  {
    const saved = stored(wizardKey, null);
    if (saved) {
      wizard = {...wizard, ...saved};
      if (saved.budget && typeof saved.budget === "object") composition = {...composition, budget: saved.budget};
      if (saved.launchPath === "advanced") launchPath = "advanced";
    }
  }
  function saveWizard() { store(wizardKey, {...wizard, budget: composition.budget, launchPath}); }
  const $ = id => document.getElementById(id);
  const message = (text, error = false) => {
    setText($("message"), text);
    const kind = error ? "message error" : "message";
    if ($("message").className !== kind) $("message").className = kind;
  };
  function words(value) { return String(value ?? "").replaceAll("_", " "); }
  function el(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function researchNote(parent, text, className = "") {
    const note = document.createElement("p"); note.textContent = text; note.className = className; parent.append(note);
  }
  // An unavailable thing, shown as such (LINKONLY-D10): one plain sentence,
  // one link to the place that fixes it, and its code and full next action
  // behind Details.
  function unavailableNote(parent, item, extra = []) {
    const plain = item.plain || {sentence: "Unavailable: " + words(item.reason) + ".", next: null};
    parent.append(el("p", plain.sentence, "status-line"));
    if (plain.next) parent.append(link(plain.next, "button fix"));
    details(parent, "Details", [item.reason ? "Code: " + item.reason : null, item.next_action ? "Next: " + item.next_action : null, ...extra]);
  }
  function link(go, className = "link") {
    const anchor = el("a", go.label, className); anchor.href = go.href; return anchor;
  }
  function pill(text, kind = "") { return el("span", text, ("pill " + kind).trim()); }
  function details(parent, summary, lines) {
    const box = el("details"); box.append(el("summary", summary));
    const body = el("div", undefined, "detail-body");
    for (const line of lines.filter(Boolean)) body.append(typeof line === "string" ? el("p", line) : line);
    box.append(body); parent.append(box);
    return box;
  }
  function card(parent, title, tag, kind) {
    const box = el("div", undefined, "integration card");
    const head = el("div", undefined, "card-head");
    head.append(el("h3", title));
    if (tag) head.append(pill(tag, kind));
    box.append(head); parent.append(box);
    return box;
  }
  // ---- Live regions (LP-PROD-F). The page reads the controller every 1.5 s;
  // a region is redrawn only when what it shows changed, and never under a
  // person's hand. A region holding a control being typed into, or an edit
  // not yet sent, is never rebuilt. During a background refresh it is also
  // left alone while a pointer is pressed in it: a click is never swallowed
  // by a redraw. A pointer resting on one of its controls holds it too, so an
  // element an agent just read stays the element it clicks, but only for
  // HOVER_HOLD_MS: `:hover` matches every ancestor of the element under the
  // pointer (a whole campaign card), and an agent leaves its pointer where it
  // last clicked, so a resting pointer must never keep a state it is
  // watching for stale. A held region is redrawn on the first refresh after
  // the hold ends.
  const FORM_TAGS = ["INPUT", "SELECT", "TEXTAREA"];
  const HOVERED = "a:hover, button:hover, input:hover, select:hover, textarea:hover, label:hover, summary:hover";
  const HOVER_HOLD_MS = 3000;
  // When a resting pointer first held each region's change back.
  const hoverHeld = new WeakMap();
  let pressed = null;
  let background = false;
  document.addEventListener("pointerdown", event => { pressed = event.target; }, true);
  // The click follows pointerup in the same task; the press ends after it,
  // and the page then draws what the click changed.
  for (const type of ["pointerup", "pointercancel"]) {
    document.addEventListener(type, () => { setTimeout(() => { if (pressed) { pressed = null; render(); } }, 0); }, true);
  }
  // An edit not yet sent is marked by the input itself (a person's or an
  // agent's), never by the page filling a field. Only typed text counts: a
  // radio, a checkbox or a select commits its choice at once. A field backed
  // by a saved draft is restored on a rebuild, so it does not hold its region.
  const TYPED = ["text", "password", "number", "search", "email", "url", "tel"];
  document.addEventListener("input", event => {
    const target = event.target;
    if (!target || !target.dataset || target.dataset.draft) return;
    if (target.tagName === "TEXTAREA" || (target.tagName === "INPUT" && TYPED.includes(target.type))) target.dataset.edited = "1";
  }, true);
  function sent(...controls) { for (const control of controls) if (control?.dataset) delete control.dataset.edited; }
  function held(region, quiet = background) {
    if (!region) return false;
    const active = document.activeElement;
    if (active && region.contains(active) && FORM_TAGS.includes(active.tagName)) return true;
    if (region.querySelector("[data-edited]")) return true;
    if (!quiet) return false;
    if (pressed && region.contains(pressed)) return true;
    let hovered = false;
    try { hovered = Boolean(region.querySelector(HOVERED)); } catch (_) { hovered = false; }
    if (!hovered) { hoverHeld.delete(region); return false; }
    const since = hoverHeld.get(region);
    if (since === undefined) { hoverHeld.set(region, Date.now()); return true; }
    if (Date.now() - since < HOVER_HOLD_MS) return true;
    // Held long enough: drawn now, under the pointer; the next change waits again.
    hoverHeld.delete(region);
    return false;
  }
  // A render the page did not ask for: the refresh timer or a campaign read.
  function quietly(draw) {
    const was = background; background = true;
    try { draw(); } finally { background = was; }
  }
  // Rebuild a region only when what it shows changed and nothing holds it,
  // keeping open Details open: a person reading one is never collapsed by the
  // 1.5 s refresh. Returns whether it was rebuilt.
  function rebuild(target, key, build) {
    if (target.dataset.key === key || held(target)) return false;
    hoverHeld.delete(target);
    const open = new Set([...target.querySelectorAll("details[open]")].map(node => node.dataset.key));
    target.replaceChildren();
    build(target);
    [...target.querySelectorAll("details")].forEach((node, index) => { node.dataset.key = String(index); node.open = open.has(String(index)); });
    target.dataset.key = key;
    return true;
  }
  // Text set only when it differs: an unchanged line is never replaced.
  function setText(node, text) { if (node && node.textContent !== text) node.textContent = text; }
  // ---- Refusals (LP-PROD-F). A refusal is known only when the controller
  // answered with a 4xx and its own code: nothing was started for that
  // request. A network failure, a timeout, a 5xx, an unreadable answer, or the
  // controller's catch-all for an unexpected failure leaves the outcome
  // unknown, and a request whose outcome is unknown keeps its key.
  const OUTCOME_UNKNOWN = new Set(["research_reconciliation_required", "request_failed", "unreadable_response"]);
  function refused(error) {
    return Number.isInteger(error?.status) && error.status >= 400 && error.status < 500 && !OUTCOME_UNKNOWN.has(error.code);
  }
  // An error's code or message, read as words, without a closing stop.
  function said(error) { return words(error?.message).replace(/\.$/, ""); }
  // Human units for the ledger's resources (LP-PROD-F): what the miner types
  // and reads, and the whole number the ledger counts. A resource without an
  // entry is a count. Conversions are exact decimal arithmetic on the whole
  // number, never floating point: a cap shown is the cap stored, and a cap
  // read back is never raised above what was typed.
  const UNITS = {
    provider_nanodollars: {short: "model spend", unit: "USD", scale: 1e9, step: "0.01", show: value => "$" + cents(fromLedger("provider_nanodollars", value))},
    numerical_milliseconds: {short: "worker time", unit: "minutes", scale: 60000, step: "0.5", show: value => durationText(value)},
    retained_bytes: {short: "retained storage", unit: "MB", scale: 1e6, step: "1", show: value => fromLedger("retained_bytes", value) + " MB"},
  };
  // Decimal text with at least two places: "2.5" as "2.50"; finer amounts
  // keep every digit ("0.0015"), so no cap reads as $0.00 unless it is 0.
  function cents(text) { const [whole, fraction = ""] = text.split("."); return whole + "." + fraction.padEnd(2, "0"); }
  // Milliseconds as hours, minutes and seconds, exactly: "30 min",
  // "13 min 32 s", "1 h 2 min 3.456 s", "0.001 s".
  function durationText(ms) {
    const parts = [];
    const hours = Math.floor(ms / 3600000), minutes = Math.floor(ms % 3600000 / 60000), rest = ms % 60000;
    if (hours) parts.push(hours + " h");
    if (minutes) parts.push(minutes + " min");
    if (rest || !parts.length) parts.push(Math.floor(rest / 1000) + (rest % 1000 ? "." + String(rest % 1000).padStart(3, "0").replace(/0+$/, "") : "") + " s");
    return parts.join(" ");
  }
  // A short decimal for a quantity a person reads beside another (minutes
  // beside seconds), at most three places.
  function trimmed(value) { return String(Math.round(value * 1000) / 1000); }
  function resourceName(name) { return UNITS[name] ? UNITS[name].short + " · " + UNITS[name].unit : words(name); }
  function resourceShort(name) { return UNITS[name]?.short || words(name); }
  // A ledger amount as a person reads it: in its unit when it is a ledger
  // whole number, otherwise as recorded, named in the ledger's own unit.
  function resourceValue(name, value) {
    if (value === undefined || value === null) return "no limit";
    if (!UNITS[name] || typeof value !== "number") return String(value);
    return Number.isSafeInteger(value) && value >= 0 ? UNITS[name].show(value) : String(value) + " " + words(name);
  }
  // A typed amount in the resource's human unit, as the ledger's whole
  // number, rounded down; undefined when blank, NaN when it is not an
  // amount, Infinity when it is too large to count exactly.
  function toLedger(name, text) {
    const typed = String(text ?? "").trim();
    if (typed === "") return undefined;
    const scale = UNITS[name]?.scale || 1;
    if (scale === 1) return /^\d+(\.\d+)?$/.test(typed) ? Number(typed) : NaN;
    const match = /^(\d*)(?:\.(\d*))?$/.exec(typed);
    if (!match || !(match[1] || match[2])) return NaN;
    const fraction = match[2] || "";
    const unit = 10n ** BigInt(fraction.length);
    const ledger = (BigInt(match[1] || "0") * unit + BigInt(fraction || "0")) * BigInt(scale) / unit;
    return ledger <= BigInt(Number.MAX_SAFE_INTEGER) ? Number(ledger) : Infinity;
  }
  // A ledger whole number in its human unit, as decimal text: exact whenever
  // the unit can say it in as many places as its scale has digits (always,
  // for USD and MB). Otherwise (minutes) the last place is rounded up, so
  // reading the text back, which rounds down, gives the same whole number.
  function fromLedger(name, value) {
    if (value === undefined || value === null) return "";
    const scale = UNITS[name]?.scale || 1;
    if (scale === 1 || !(Number.isSafeInteger(value) && value >= 0)) return String(value);
    const divisor = BigInt(scale);
    let places = 0;
    while (10n ** BigInt(places) < divisor) places++;
    const unit = 10n ** BigInt(places);
    const scaled = BigInt(value) * unit;
    const digits = scaled / divisor + (scaled % divisor ? 1n : 0n);
    const fraction = (digits % unit).toString().padStart(places, "0").replace(/0+$/, "");
    return (digits / unit).toString() + (fraction ? "." + fraction : "");
  }
  // " (10 min)" beside a number of seconds a person would rather read so.
  function longer(seconds) {
    if (!(typeof seconds === "number" && seconds >= 60)) return "";
    const minutes = seconds / 60;
    return " (" + (minutes >= 60 ? trimmed(minutes / 60) + " h" : trimmed(minutes) + " min") + ")";
  }
  // A command the miner runs, with a button that copies it.
  function copyRow(parent, label, command, id) {
    const row = el("div", undefined, "copy-row");
    if (label) row.append(el("p", label));
    const line = el("div", undefined, "copy-line");
    const code = el("code", command);
    const button = el("button", "Copy"); button.type = "button"; button.className = "copy";
    if (id) button.id = id;
    button.setAttribute("aria-label", "Copy " + (label || "this command"));
    button.addEventListener("click", async () => {
      let copied = false;
      try { await navigator.clipboard.writeText(code.textContent); copied = true; } catch (_) { copied = false; }
      if (!copied) {
        // Without clipboard access the command is selected, ready to copy.
        const range = document.createRange(); range.selectNodeContents(code);
        const selection = getSelection(); selection.removeAllRanges(); selection.addRange(range);
        try { copied = document.execCommand("copy"); } catch (_) { copied = false; }
      }
      button.textContent = copied ? "Copied" : "Selected";
      setTimeout(() => { button.textContent = "Copy"; }, 1600);
    });
    line.append(code, button); row.append(line); parent.append(row);
    return code;
  }
  // The wiring guide's text data (guide.py), rendered as text: never HTML.
  function renderSpans(parent, spans) {
    for (const span of spans || []) {
      let node;
      if (span.code) node = el("code", span.text);
      else if (span.anchor) { node = el("a", span.text); node.href = "#guide/" + span.anchor; }
      else if (span.strong) node = el("strong", span.text, /^UNVERIFIED/.test(span.text) ? "unverified" : undefined);
      else node = document.createTextNode(span.text);
      if (span.strong && (span.code || span.anchor)) { const strong = el("strong"); strong.append(node); node = strong; }
      parent.append(node);
    }
  }
  function renderList(ordered, items) {
    const list = el(ordered ? "ol" : "ul");
    for (const item of items) {
      const entry = el("li"); renderSpans(entry, item.text);
      if (item.items?.length) entry.append(renderList(item.ordered, item.items));
      list.append(entry);
    }
    return list;
  }
  function renderBlocks(parent, blocks) {
    for (const block of blocks || []) {
      if (block.type === "heading") {
        const heading = el(block.level <= 2 ? "h2" : "h3"); heading.dataset.anchor = "guide/" + block.anchor;
        renderSpans(heading, block.text); parent.append(heading);
      } else if (block.type === "paragraph") { const p = el("p"); renderSpans(p, block.text); parent.append(p); }
      else if (block.type === "list") parent.append(renderList(block.ordered, block.items));
      else if (block.type === "table") {
        const wrap = el("div", undefined, "guide-table-wrap"); const table = el("table", undefined, "guide-table");
        const head = el("tr"); for (const cell of block.header) { const th = el("th"); renderSpans(th, cell); head.append(th); }
        table.append(head);
        for (const row of block.rows) { const tr = el("tr"); for (const cell of row) { const td = el("td"); renderSpans(td, cell); tr.append(td); } table.append(tr); }
        wrap.append(table); parent.append(wrap);
      }
    }
  }
  // Carbon holds no key: the miner's own `carbon-miner-signer` signs. Each
  // way reaching it can fail is its own code and its own correction.
  const SIGNER_HELP = {
    signer_not_running: "your signer is not running. Start `carbon-miner-signer --wallet NAME --hotkey HOTKEY` in a terminal and leave it open",
    signer_refused: "your signer declined the request; its terminal shows why",
    signer_wrong_hotkey: "the signer running holds a different hotkey than this profile's registered miner",
    signer_timeout: "your signer did not answer in time. Check its terminal",
    signer_invalid_signature: "your signer returned a signature that does not verify for this hotkey",
    signer_protocol: "something other than carbon-miner-signer answered on the signer socket"
  };
  async function api(path, body, key, timeout = 5000) {
    const headers = {Authorization: "Bearer " + token};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (key) headers["Idempotency-Key"] = key;
    const response = await fetch(path, {
      method: body === undefined ? "GET" : "POST", headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(timeout), cache: "no-store", redirect: "error"
    });
    // An answer that is not JSON (a proxy's error page, a cut-off body) is
    // an unknown outcome, never a refusal.
    let result = null;
    try { result = await response.json(); } catch (_) { result = null; }
    if (!response.ok || result === null || typeof result !== "object") {
      const code = (response.ok ? null : result?.error) || (response.ok ? "unreadable_response" : "request_failed");
      const error = new Error(SIGNER_HELP[code] ? code + ": " + SIGNER_HELP[code] : code);
      error.status = response.status;
      error.code = code;
      // A setup refusal names its field and, when there is one, the next step.
      error.field = result?.field || null;
      error.nextStep = result?.next_step || null;
      throw error;
    }
    return result;
  }

  // ---- Routing. One view at a time; a campaign has its own deep link. ----
  // A campaign's tabs are the research surface's (research_view.js: live,
  // conversation, experiments, ...). Links this page wrote before it named
  // them (#.../overview, /metrics, /journal) still open; these are the
  // fallback page's names for the research surface's own.
  const LEGACY_TAB = {live: "overview", reasoning: "journal", conversation: "journal", tools: "experiments", contract: "settings"};
  function route() {
    const parts = location.hash.replace(/^#\/?/, "").split("/").map(part => { try { return decodeURIComponent(part); } catch (_) { return part; } });
    const views = [...document.querySelectorAll("main > .view")].map(view => view.id);
    const tab = LEGACY_TAB[parts[2]] || parts[2];
    return {view: views.includes(parts[0]) ? parts[0] : "overview", id: parts[1] || "", tab: TABS.some(([name]) => name === tab) ? tab : "overview"};
  }
  function campaignHref(id, tab = "live") { return "#campaigns/" + encodeURIComponent(id) + "/" + tab; }
  function show() {
    const current = route();
    for (const view of document.querySelectorAll("main > .view")) view.hidden = view.id !== current.view;
    for (const link of document.querySelectorAll("#tool-nav a")) {
      if (link.getAttribute("href") === "#" + current.view) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    }
    if (location.hash) store(routeKey, {hash: location.hash});
    render();
    // Setup shows one step at a time; #setup/<step> names it.
    if (current.view === "setup") applySetupStep();
  }
  // A session link opened in a tab already showing this page changes only
  // the fragment: it is taken (and removed) before the route is read.
  window.addEventListener("hashchange", () => {
    const fresh = takeSessionLink();
    show();
    if (fresh !== null) connectFromLink(fresh);
  });
  // The navigation is built from the page's own views: a view marked data-nav
  // is listed, and nothing else can be, so the two cannot drift. Development
  // diagnostics are listed apart, under their own label.
  function buildNavigation() {
    const nav = $("tool-nav");
    const primary = document.createElement("ul");
    const development = document.createElement("ul"); development.className = "nav-development";
    for (const section of document.querySelectorAll("[data-nav]")) {
      const item = document.createElement("li");
      const link = document.createElement("a");
      link.href = "#" + section.id; link.textContent = section.dataset.nav;
      item.append(link);
      (section.dataset.navGroup === "development" ? development : primary).append(item);
    }
    const label = el("p", "Development", "nav-label");
    nav.replaceChildren(primary, label, development);
  }

  // ---- Rendering. ----
  function render() {
    renderOnboarding();
    renderDevelopment();
    renderOverview();
    renderCatalogs();
    renderCampaigns();
    renderWizard();
    if (route().view === "guide") renderGuide(route().id);
    $("settings-recheck").disabled = !connected || busy;
    // Connected: the token form steps aside; interrupted or new, it returns.
    $("connect-panel").hidden = connected;
    // The research surface (research_view.js) redraws with the page.
    for (const hook of renderHooks) hook();
  }
  const renderHooks = [];
  // ---- The wiring guide, served by this controller (LINKONLY-D10). ----
  let guideDoc = null;
  let guideLoading = null;
  let guideAnchor = null;
  async function renderGuide(anchor) {
    const body = $("guide-body");
    if (!connected) { if (body.dataset.built !== "disconnected") body.replaceChildren(el("p", "Connect this browser to read the guide.", "hint")); body.dataset.built = "disconnected"; return; }
    if (!guideDoc) {
      guideLoading ||= api("/api/v1/guide/remote-setup").then(value => { guideDoc = value; }, error => { body.replaceChildren(el("p", "The guide could not be read: " + error.message, "reason")); }).finally(() => { guideLoading = null; });
      await guideLoading;
      if (!guideDoc) return;
    }
    if (body.dataset.built !== "1") {
      body.replaceChildren();
      if (!guideDoc.available) body.append(el("p", "This checkout has no guide at " + guideDoc.source + ".", "reason"));
      else { $("guide-heading").textContent = guideDoc.title; renderBlocks(body, guideDoc.blocks); }
      body.dataset.built = "1";
    }
    // Scroll once per anchor, not on every refresh.
    if (anchor && anchor !== guideAnchor) document.querySelector('[data-anchor="guide/' + CSS.escape(anchor) + '"]')?.scrollIntoView();
    guideAnchor = anchor || null;
  }
  function renderDevelopment() {
    const sources = $("development-sources");
    const listed = connected ? developmentSources.map(source => [source.id, source.status, source.receipt?.receipt_id ?? null, source.receipt?.disposition ?? null]) : null;
    rebuild(sources, JSON.stringify(listed), target => {
      if (!connected || !developmentSources.length) {
        const note = document.createElement("p"); note.className = "hint";
        note.textContent = connected ? "No historical DEVELOPMENT source is attached. Current research campaigns are under Campaigns." : "Reconnect to verify current source state.";
        target.append(note);
      }
      if (connected) for (const source of developmentSources) {
        const box = document.createElement("div"); box.className = "integration";
        const title = document.createElement("h3");
        title.textContent = source.receipt ? source.receipt.disposition : "Readback unavailable";
        const note = document.createElement("p");
        note.textContent = source.receipt ? "DEVELOPMENT EVALUATION · Receipt " + source.receipt.receipt_id : "Source validation failed. No receipt or result is being inferred.";
        const button = document.createElement("button"); button.type = "button";
        button.textContent = "Export verified public receipt";
        button.dataset.verified = source.status === "VERIFIED_SOURCE" ? "1" : "";
        button.addEventListener("click", async () => {
          if (busy || !connected) return;
          busy = true; render();
          try {
            const fresh = await api("/api/v1/development/" + source.id);
            if (fresh.status !== "VERIFIED_SOURCE") throw new Error("development_source_unavailable");
            download(fresh, "carbon-development-" + source.id + ".json");
          } catch (error) { message("Receipt export unavailable: " + error.message, true); }
          finally { busy = false; await refresh(); render(); }
        });
        box.append(title, note, button); target.append(box);
      }
    });
    // Patched in place: a busy page disables, it does not redraw.
    for (const button of sources.querySelectorAll("button[data-verified]")) button.disabled = busy || !button.dataset.verified;
    $("launch-fields").disabled = !connected || storageError;
    $("launch-button").disabled = busy;
    setText($("launch-button").firstChild, pending ? "Retry same launch " : "Launch rehearsal ");
    $("launch-discard").hidden = !pending;
    $("steps").disabled = Boolean(pending);
    $("seconds").disabled = Boolean(pending);
    const picker = $("run-picker");
    rebuild(picker, JSON.stringify(runs.map(run => [run.id, run.state])), target => {
      for (const run of runs) {
        const option = document.createElement("option");
        option.value = run.id;
        option.textContent = run.id.slice(0, 10) + " · " + run.state;
        target.append(option);
      }
    });
    const run = runs.find(r => r.id === selected) || runs[0];
    $("empty").hidden = Boolean(run);
    $("run-detail").hidden = !run;
    picker.hidden = !run;
    $("picker-label").hidden = !run;
    if (!run) return;
    selected = run.id;
    if (picker.value !== selected && !held(picker)) picker.value = selected;
    setText($("run-id"), run.id);
    setText($("run-state"), run.state);
    setText($("run-steps"), run.steps + " / " + run.spec.max_steps);
    $("progress").max = run.spec.max_steps;
    $("progress").value = run.steps;
    setText($("deadline"), "Fixed deadline: " + new Date(run.deadline * 1000).toLocaleString());
    $("pause").disabled = !connected || busy || !["QUEUED", "RUNNING"].includes(run.state);
    $("resume").disabled = !connected || busy || !["PAUSED", "INTERRUPTED"].includes(run.state);
    $("stop").disabled = !connected || busy || !["QUEUED", "RUNNING", "PAUSED", "INTERRUPTED"].includes(run.state);
    $("export").disabled = !connected || busy;
    const shown = run.events.slice(-30).reverse();
    rebuild($("events"), run.id + "|" + JSON.stringify(shown.map(event => [event.at, event.kind])), events => {
      for (const event of shown) {
        const item = document.createElement("li");
        const at = document.createElement("time");
        at.textContent = new Date(event.at * 1000).toLocaleTimeString();
        const kind = document.createElement("span");
        kind.textContent = event.kind.replaceAll("_", " ");
        item.append(at, kind);
        events.append(item);
      }
    });
  }
  function download(value, name) {
    const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], {type: "application/json"}));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = name;
    anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  // Registration. The panel exists because the endpoints were reachable and the
  // page was not: a human with no agent could not begin the journey at all.
  function onboardingLine(text, kind) {
    const node = document.createElement("p");
    node.className = kind === "error" ? "notice" : "hint";
    node.textContent = text;
    return node;
  }

  function showOnboarding(nodes) {
    const target = $("onboarding-result");
    target.replaceChildren(...nodes);
    target.dataset.key = "";
  }

  function renderOnboarding() {
    for (const control of ["onboarding-address", "onboarding-status",
                           "onboarding-prepare", "onboarding-confirm"]) {
      $(control).disabled = !connected || busy;
    }
    if (!connected) {
      if ($("onboarding-facts").children.length) $("onboarding-facts").replaceChildren();
      rebuild($("onboarding-result"), "disconnected", target => target.append(onboardingLine(
        "Connect this browser to read the current registration requirements. "
        + "Registration itself needs no Carbon account - this page just needs "
        + "its local session token."
      )));
    }
  }

  async function onboardingRequirements() {
    try {
      const value = await api("/api/v1/onboarding/requirements");
      // The network this controller registers on, always in view.
      $("network-pill").textContent = (String(value.network).includes("test") ? "Testnet" : words(value.network)) + " · netuid " + value.netuid;
      const facts = $("onboarding-facts");
      facts.replaceChildren();
      // The cost is shown as Carbon actually knows it. NOT_READ is a different
      // claim from unknown, and neither is a figure to plan around.
      const rows = [
        ["Network", value.network + " · netuid " + value.netuid],
        ["Mechanism", value.mechanism],
        ["Recycle amount", value.cost && value.cost.value === "NOT_READ"
          ? "Not read by Carbon — your wallet shows it at signing"
          : String((value.cost || {}).value)],
        ["Carbon signs", "Never"]
      ];
      for (const [label, detail] of rows) {
        const key = document.createElement("dt");
        key.textContent = label;
        const definition = document.createElement("dd");
        definition.textContent = detail;
        facts.append(key, definition);
      }
      const listed = [
        ["You need", value.you_need || []],
        ["Carbon never", value.carbon_never || []]
      ];
      for (const [label, items] of listed) {
        const key = document.createElement("dt");
        key.textContent = label;
        facts.append(key);
        for (const item of items) {
          const definition = document.createElement("dd");
          definition.textContent = item;
          facts.append(definition);
        }
      }
      return value;
    } catch (error) {
      showOnboarding([onboardingLine("Could not read the registration requirements: " + error.message, "error")]);
      return null;
    }
  }

  async function onboardingCall(action) {
    if (busy || !connected) return;
    const address = $("onboarding-address").value.trim();
    if (!address) {
      showOnboarding([onboardingLine("Enter the hotkey address you want to register.", "error")]);
      return;
    }
    try {
      const value = await api("/api/v1/onboarding/" + action, {address});
      const lines = [];
      if (action === "status" || action === "confirm") {
        lines.push(onboardingLine(
          value.registered
            ? "Registered. UID " + value.uid + " at block " + (value.observed_block ?? "unknown") + "."
            : "Not registered on netuid " + value.netuid + " yet."
        ));
        lines.push(onboardingLine("Research environment: " + value.research_environment));
        if (action === "confirm" && value.registered && value.confirmed) {
          // Registered: setup opens at its next step, and reads the chain
          // again itself.
          const begun = await setupCall("begin", {address});
          location.hash = begun ? "#setup/agent" : "#setup/register";
        }
      } else {
        lines.push(onboardingLine("Prepared an UNSIGNED " + value.extrinsic + ". Carbon has not signed and will not submit it."));
        lines.push(onboardingLine("Execute it in " + value.execute_in + ". The recycle amount comes from your coldkey."));
      }
      showOnboarding(lines);
    } catch (error) {
      // Refusals carry a reason and a next action; show both rather than a
      // generic failure, because the reason is what tells a miner what to do.
      showOnboarding([onboardingLine(error.message, "error")]);
    }
  }

  // ---- Environment setup (C-MLP-03): six steps, one at a time. ----
  // OWNER-MINER-COMPUTE-LINK-ONLY-01, LINKONLY-D10: the miner's path is the
  // same six steps on Overview and here. A step is done only when the
  // controller confirmed it: registration by its chain read, each check by its
  // live check, the signer by the Agent step's handshake, the last step by a
  // campaign on record.
  // The order an agent follows too (OWNER-MINER-SETUP-AGENT-FIRST-01): who
  // researches comes before Inference, which only an agent calling setup's
  // model needs. Step ids are stable anchors: #setup/<id>.
  const SETUP_STEPS = [
    ["signer", "Start your signer", "Your signer holds your hotkey on this machine. Carbon never sees your key."],
    ["register", "Register on the subnet", "Your hotkey must be registered on the subnet. You sign that in your own wallet."],
    ["agent", "Who researches?", "Carbon's agent, or your own agent over MCP. This step also checks your signer."],
    ["inference", "Inference", "Choose the model Carbon's agent calls, with your own key."],
    ["compute", "Compute", "Choose where practice runs: this machine, or a GPU you run elsewhere."],
    ["review", "Review and launch", "Carbon writes your runner profile and loads it. Then you choose a Challenge."],
  ];
  const SETUP_IDS = SETUP_STEPS.map(([id]) => id);
  // One step reads Next; others a miner can take now, in any order, read Open.
  const STATE_LABEL = {done: "Done", next: "Next", open: "Open", waiting: "Waiting", skipped: "Skipped"};
  // A per-browser convenience only: never a token, key or address.
  const whereKey = "carbon.control-center.where.v1";
  let setupState = null;
  let setupRead = false;
  let setupVersion = 0;
  let setupStepShown = null;
  // The setup state the steps' forms were last drawn from.
  let setupDrawn = null;
  // A worker being sent to the miner's machine: its start, while it runs.
  let sendingWorker = null;
  function setupLine(text, kind) { const line = el("p", text, kind === "error" ? "reason" : ""); return line; }
  async function readSetup() {
    if (!connected) return;
    try { setupState = await api("/api/v1/setup"); }
    catch (_) { setupState = null; }
    setupVersion++;
    renderSetup();
    render();
  }
  // Progress an agent makes over MCP shows here too: the setup records are
  // shared, so the page reads them again every few seconds and rebuilds only
  // when they changed, and never under a person's cursor.
  let setupPolls = 0;
  let setupPolling = false;
  function setupKey(value) {
    return JSON.stringify([value?.registered_hotkey ?? null, value?.steps ?? null, value?.status?.done ?? null]);
  }
  async function pollSetup() {
    if (!connected || setupPolling || ++setupPolls % 3) return;
    setupPolling = true;
    try {
      const fresh = await api("/api/v1/setup");
      const changed = setupKey(fresh) !== setupKey(setupState);
      if (changed) {
        setupState = fresh; setupVersion++;
        // A profile written elsewhere changes what can launch.
        if (fresh.steps?.review?.profile_written && !caps?.profile?.configured) { try { await readCapabilities(); } catch (_) { /* re-read on request */ } }
      }
      // What is done (the step list, Overview) follows at once. The steps'
      // forms wait while anything holds them: typing, an unsent edit (a key,
      // an endpoint), a press or a resting pointer.
      if (setupKey(setupState) !== setupDrawn && !held($("setup-body"), true)) renderSetup();
      else if (changed) applySetupStep();
      if (changed) render();
    } catch (_) { /* the next poll tries again */ }
    finally { setupPolling = false; }
  }
  async function setupCall(step, body, timeout = 60000) {
    try {
      const result = await api("/api/v1/setup/" + step, body, undefined, timeout);
      // A step only the miner can take (their signer, their registration):
      // the exact instruction, not an error, and nothing marked done.
      if (result.result === "human_action_required") {
        const box = $("setup-result");
        box.replaceChildren(el("p", result.for_miner, "reason"));
        if (result.command) copyRow(box, null, result.command);
        await readSetup();
        return false;
      }
      // Carbon rents no compute (OWNER-MINER-COMPUTE-LINK-ONLY-01): when the
      // compute check deleted Carbon's copy of a rented-GPU key, it says so.
      const removed = step === "compute" ? result.steps?.compute?.check?.retired_compute_key : null;
      // Review writes the profile and says what it could not do: a Challenge
      // with no evaluation endpoint, an unreadable published list (LP-PROD-E).
      const warnings = step === "review" && Array.isArray(result.warnings) ? result.warnings.filter(item => typeof item?.message === "string") : [];
      $("setup-result").replaceChildren(setupLine(step === "review" ? (result.attached ? "Profile written and loaded. Choose a Challenge to launch." : "Profile written. A different profile is already loaded here, so restart the controller to use this one.") : step === "begin" ? "Registration confirmed. Set up inference, compute and agent next." : "Checked: " + step + "." + (removed ? " " + removed : "")), ...warnings.map(item => setupLine(item.message, "error")));
      // The written profile changes what can launch: read it again now.
      if (step === "review") { try { await readCapabilities(); } catch (_) { /* re-read on request */ } }
      await readSetup();
      if (step === "review") refresh();
      return true;
    } catch (error) {
      const text = (error.field ? error.field.replaceAll("_", " ") + ": " : "") + words(error.message) + (error.nextStep ? ". Next: " + error.nextStep : "");
      $("setup-result").replaceChildren(setupLine(text, "error"));
      return false;
    }
  }
  // Sending the GPU worker streams an image over the miner's own SSH: minutes,
  // up to an hour. Until the controller answers, the page says it is still
  // going and for how long; it never sends twice at once.
  const SEND_WORKER_MS = 3600000;
  function clock(seconds) {
    const whole = Math.max(0, Math.floor(seconds));
    const h = Math.floor(whole / 3600), m = Math.floor(whole % 3600 / 60), s = whole % 60;
    return (h ? h + "h " : "") + (h || m ? m + "m " : "") + String(s).padStart(h || m ? 2 : 1, "0") + "s";
  }
  async function sendWorker(body, target) {
    if (sendingWorker) return false;
    sendingWorker = {started: Date.now()};
    const line = setupLine("");
    line.id = "setup-send-progress";
    const bar = el("progress"); bar.setAttribute("aria-label", "Sending your worker");
    $("setup-result").replaceChildren(line, bar);
    const tick = () => {
      setText(line, "Sending your worker to " + target + " over your SSH: " + clock((Date.now() - sendingWorker.started) / 1000) + " so far. It can take up to an hour; leave this page open until it answers.");
    };
    tick();
    const timer = setInterval(tick, 1000);
    try { return await setupCall("send_worker", body, SEND_WORKER_MS); }
    finally { clearInterval(timer); sendingWorker = null; }
  }
  // Where the miner is on the path: the controller's own status, the same one
  // an agent loops on, so the page and the agent never disagree.
  function journey() {
    const steps = setupState?.steps || {};
    const registered = Boolean(setupState?.registered_hotkey);
    const sendPending = Boolean(steps.compute?.checked && steps.compute.check?.next_step);
    const profile = Boolean(caps?.profile?.configured);
    const state = {};
    for (const row of setupState?.status?.steps || []) state[row.id] = row.state;
    for (const id of SETUP_IDS) state[id] ||= id === "signer" || id === "register" ? "open" : "waiting";
    // Step 6 is done with a campaign on record; a written profile is next.
    if (state.review === "done" && !research.runs.length) state.review = "open";
    for (const id of SETUP_IDS) if (state[id] === "next") state[id] = "open";
    const done = Object.fromEntries(SETUP_IDS.map(id => [id, state[id] === "done"]));
    const skipped = Object.fromEntries(SETUP_IDS.map(id => [id, state[id] === "skipped"]));
    // The first open step is the one next; the rest can be taken in any order.
    const current = SETUP_IDS.find(id => state[id] === "open") || null;
    if (current) state[current] = "next";
    const ready = ["agent", "inference", "compute"].every(id => done[id] || skipped[id]);
    return {state, done, skipped, current, registered, ready, profile, sendPending, steps};
  }
  function stepTitle(id, j) {
    if (id === "review" && j.profile && !j.done.review) return "Choose a Challenge and launch";
    return SETUP_STEPS.find(([step]) => step === id)[1];
  }
  function shortKey(value) { return value ? value.slice(0, 6) + "…" + value.slice(-4) : ""; }
  // A setup choice by the name setup offers it under, not its id.
  function choiceName(step, id) {
    return (setupState?.choices?.[step] || []).find(choice => choice.id === id)?.display_name || words(id);
  }
  // What a checked step holds, in plain words.
  function checkedText(id, steps) {
    if (id === "inference") return choiceName("inference", steps.inference.provider_id) + " · " + steps.inference.model_id;
    if (id === "compute") return choiceName("compute", steps.compute.choice) + (steps.compute.remote_machine ? " · " + steps.compute.remote_machine.destination + " (" + steps.compute.remote_machine.transport + ")" : "");
    return choiceName("agent", steps.agent.choice);
  }
  // A compute check setup no longer counts (LP-PROD-E), as setup states it:
  // stale, with its reasons and the one step that clears them (checking
  // again, or the installer's update), or set aside by an update. Null when
  // neither.
  function staleCompute(steps) {
    const compute = steps?.compute || {};
    const reasons = list => Array.isArray(list) ? list.filter(item => typeof item === "string") : [];
    if (reasons(compute.stale).length && typeof compute.next_step === "string") return {title: "Your compute check no longer matches this install", reasons: reasons(compute.stale), next: compute.next_step};
    if (reasons(compute.set_aside?.reasons).length) return {title: "An update set your compute check aside", reasons: reasons(compute.set_aside.reasons), next: "check Compute again"};
    return null;
  }
  // What setup says must happen before a step counts: why, each reason, and
  // the step that clears it (a command, copyable, when it is one to run).
  function setupAttention(parent, id, title, reasons, next) {
    const box = el("div", undefined, "setup-attention"); box.id = "setup-" + id; box.setAttribute("role", "status");
    box.append(el("p", title + ":", "reason"));
    const list = el("ul"); for (const reason of reasons) list.append(el("li", reason)); box.append(list);
    if (next) {
      box.append(el("p", "Next: " + next + ".", "status-line"));
      const command = /^run (\S.*)$/.exec(next);
      if (command) copyRow(box, null, command[1]);
    }
    parent.append(box);
    return box;
  }
  // Where each Challenge's frozen candidates are evaluated (LP-PROD-E):
  // Carbon's published endpoint, the miner's own intake, or plainly none
  // yet, as setup's `steps.evaluation` says. An intake of the miner's own
  // that an update set aside is named again with one click.
  function evaluationSection(parent, evaluation, nameAgain) {
    const items = Array.isArray(evaluation?.challenges) ? evaluation.challenges : [];
    if (!items.length && !evaluation?.problem) return null;
    const box = el("section", undefined, "setup-evaluation"); box.id = "setup-evaluation";
    box.append(el("h3", "Where your candidates are evaluated"));
    for (const item of items) {
      const row = el("div", undefined, "evaluation-row"); row.dataset.challenge = item.id;
      const head = el("p");
      const [tag, kind] = item.intake ? [item.source === "published" ? "Carbon's endpoint" : "Your intake", "pill-done"] : ["None yet", "pill-need"];
      head.append(el("strong", (item.title || item.id) + " · v" + item.version), " ", pill(tag, kind));
      row.append(head);
      if (item.intake) row.append(el("p", "A frozen candidate is submitted to " + item.intake + ".", "status-line"));
      if (item.receiver_hotkey) {
        row.append(el("p", "Receiver hotkey: " + item.receiver_hotkey, "hint"));
        const note = item.receiver_hotkey_note;
        if (typeof note === "string" && note) row.append(el("p", note[0].toUpperCase() + note.slice(1), "hint"));
      }
      if (item.note) row.append(el("p", item.note, item.intake ? "hint" : "reason"));
      if (item.set_aside_intake) {
        row.append(el("p", "Your own intake, set aside by the update: " + item.set_aside_intake, "status-line"));
        const again = el("button", "Name it again"); again.type = "button"; again.dataset.nameAgain = item.id;
        again.addEventListener("click", () => nameAgain(item.id, item.set_aside_intake));
        row.append(again);
      }
      box.append(row);
    }
    if (evaluation.problem) box.append(el("p", "Carbon's list of evaluation endpoints could not be read (" + words(evaluation.problem) + "), so none is offered.", "reason"));
    if (evaluation.published_by) box.append(el("p", "Carbon publishes its endpoints in " + evaluation.published_by + ", in this checkout.", "hint"));
    parent.append(box);
    return box;
  }
  function stepSentence(id, j) {
    const state = j.state[id];
    const steps = j.steps;
    if (id === "signer") return state === "done" ? "Your signer answered for " + shortKey(steps.signer?.hotkey || setupState?.registered_hotkey) + "." : "Start carbon-miner-signer in your own terminal, then check it here.";
    if (id === "register") return state === "done" ? "Registered: " + shortKey(setupState.registered_hotkey) + "." : "Confirm your hotkey is registered on the subnet." + (state === "open" ? " Steps 1 and 2 can be done in either order." : "");
    if (state === "waiting" && id !== "review") return "Opens once your registration is confirmed.";
    if (state === "skipped") return "Skipped: your agent uses its own model.";
    if (id === "inference") return state === "done" ? "Checked: " + checkedText(id, steps) + "." : "Choose a provider and model, and check your key.";
    if (id === "compute") {
      const stale = staleCompute(steps);
      return state === "done" ? "Checked: " + checkedText(id, steps) + "." : j.sendPending ? "Send your worker to your machine." : stale ? stale.title + ". Next: " + stale.next + "." : "Choose where practice runs.";
    }
    if (id === "agent") return state === "done" ? "Checked: " + checkedText(id, steps) + ", and your signer answered." : "Carbon's agent, or your own agent over MCP.";
    if (state === "done") return "Campaigns on record: " + research.runs.length + ".";
    if (state === "waiting") return "Opens when steps 3 to 5 are done.";
    return j.profile ? "Your profile is loaded. Pick a Challenge that is ready." : "Write your profile, then choose a Challenge.";
  }
  function stepHref(id, j) {
    if (id === "review" && j.profile) return j.done.review ? "#launch" : "#challenges";
    return "#setup/" + id;
  }
  function reachable(id, j) { return id === "signer" || id === "register" || j.registered; }
  // Why Next cannot be taken from this step yet, or null.
  function nextProblem(id, j) {
    if (id === "signer") return null;
    if (id === "register") return j.registered ? null : "Confirm your registration first.";
    if (id === "compute" && j.sendPending) return "Send your worker first.";
    if (["inference", "compute", "agent"].includes(id)) return j.done[id] || j.skipped[id] ? null : "Run this step's check first.";
    return null;
  }
  // The step after (or before) `id` on this miner's path: a skipped one is
  // passed over.
  function stepFrom(id, direction, j) {
    let index = SETUP_IDS.indexOf(id) + direction;
    while (index >= 0 && index < SETUP_IDS.length && j.skipped[SETUP_IDS[index]]) index += direction;
    return SETUP_IDS[index] || null;
  }
  function setupTarget() {
    const j = journey();
    const current = route();
    let wanted = current.view === "setup" && SETUP_IDS.includes(current.id) ? current.id : setupStepShown || j.current || "review";
    if (!reachable(wanted, j)) wanted = j.state.signer === "next" ? "signer" : "register";
    return wanted;
  }
  // Show one step: its heading, progress, done state, Back and Next.
  function applySetupStep() {
    const body = $("setup-body");
    const panels = body.querySelectorAll("[data-step-panel]");
    const j = journey();
    const id = setupTarget();
    // A result belongs to the step it came from.
    if (setupStepShown && setupStepShown !== id) $("setup-result").replaceChildren();
    setupStepShown = id;
    const index = SETUP_IDS.indexOf(id);
    for (const panel of panels) panel.hidden = panel.dataset.stepPanel !== id;
    const [, title, lede] = SETUP_STEPS[index];
    setText($("setup-eyebrow"), "Set up · Step " + (index + 1) + " of " + SETUP_STEPS.length);
    setText($("setup-heading"), id === "review" ? stepTitle(id, j) : title);
    setText($("setup-lede"), lede);
    const progress = $("setup-progress");
    // Built once; each step's state is patched in place, so a step button is
    // the same element from one refresh to the next.
    if (progress.children.length !== SETUP_STEPS.length) {
      progress.replaceChildren();
      SETUP_STEPS.forEach(([step, label], position) => {
        const item = el("li");
        const button = el("button"); button.type = "button"; button.dataset.setupStep = step;
        button.append(el("span", String(position + 1).padStart(2, "0"), "wp-num"), el("span", label));
        button.addEventListener("click", () => { location.hash = "#setup/" + step; });
        item.append(button); progress.append(item);
      });
    }
    SETUP_STEPS.forEach(([step, label], position) => {
      const item = progress.children[position];
      const button = item.firstChild;
      item.className = "is-" + j.state[step];
      button.disabled = !connected || !setupState || !reachable(step, j);
      if (step === id) button.setAttribute("aria-current", "step"); else button.removeAttribute("aria-current");
      button.setAttribute("aria-label", "Step " + (position + 1) + ": " + label + " · " + STATE_LABEL[j.state[step]]);
    });
    const ready = connected && Boolean(setupState);
    progress.hidden = !ready;
    $("setup-nav").hidden = !ready;
    $("setup-back").disabled = index === 0;
    const problem = nextProblem(id, j);
    const following = stepFrom(id, 1, j);
    $("setup-next").hidden = !following;
    $("setup-next").disabled = Boolean(problem);
    setText($("setup-next"), following ? "Next: " + SETUP_STEPS[SETUP_IDS.indexOf(following)][1] : "Next");
    setText($("setup-next-reason"), problem || "");
  }
  $("setup-back").addEventListener("click", () => {
    const before = stepFrom(setupStepShown, -1, journey());
    if (before) location.hash = "#setup/" + before;
  });
  $("setup-next").addEventListener("click", () => {
    const j = journey();
    const following = stepFrom(setupStepShown, 1, j);
    if (!following || nextProblem(setupStepShown, j)) return;
    location.hash = "#setup/" + following;
  });
  function setupField(form, name, labelText, type = "text") {
    const id = "setup-" + form.dataset.step + "-" + name;
    const label = el("label", labelText); label.htmlFor = id;
    const input = document.createElement("input");
    input.id = id; input.name = name; input.type = type; input.autocomplete = "off"; input.spellcheck = false;
    form.append(label, input);
    return input;
  }
  function setupSelect(form, name, labelText, options) {
    const id = "setup-" + form.dataset.step + "-" + name;
    const label = el("label", labelText); label.htmlFor = id;
    const select = document.createElement("select"); select.id = id; select.name = name;
    for (const [value, text] of options) { const option = el("option", text); option.value = value; select.append(option); }
    form.append(label, select);
    return select;
  }
  // One wizard step's panel, with its done state when the controller has one.
  function stepPanel(parent, id, doneText) {
    const panel = el("section", undefined, "setup-step"); panel.dataset.stepPanel = id;
    if (doneText) { const done = el("p", undefined, "step-done"); done.append(pill("Done", "pill-done"), el("span", doneText)); panel.append(done); }
    parent.append(panel);
    return panel;
  }
  function stepForm(parent, step) {
    const form = document.createElement("form"); form.dataset.step = step;
    parent.append(form);
    return form;
  }
  function advanced(parent, summary = "Advanced") {
    const box = el("details", undefined, "advanced"); box.append(el("summary", summary));
    const body = el("div", undefined, "detail-body"); body.dataset.step = parent.dataset.step;
    box.append(body); parent.append(box);
    return body;
  }
  function costNote(form, choice) {
    if (!choice) return;
    researchNote(form, "Cost: " + choice.cost_basis, "hint");
    researchNote(form, "Live check: " + choice.live_check, "hint");
  }
  async function confirmRegistration(address) {
    if (busy || !connected) return;
    const result = $("setup-result");
    if (!address) { result.replaceChildren(setupLine("Enter the hotkey address you registered.", "error")); return; }
    try {
      const value = await api("/api/v1/onboarding/confirm", {address});
      if (value.registered && value.confirmed) {
        if (await setupCall("begin", {address})) location.hash = "#setup/agent";
        return;
      }
      const line = el("p", "Not registered on netuid " + value.netuid + " yet. Prepare the unsigned registration under Wallet & Identity, sign it in your own wallet, then check again.", "reason");
      result.replaceChildren(line, link({label: "Wallet & Identity", href: "#wallet"}));
    } catch (error) {
      result.replaceChildren(setupLine(error.message, "error"));
    }
  }
  function renderSetup() {
    const body = $("setup-body");
    setupDrawn = setupKey(setupState);
    if (!connected) { body.replaceChildren(el("p", "Connect this browser to begin.", "hint")); applySetupStep(); return; }
    if (!setupState) {
      body.replaceChildren(el("p", "Setup is off on this controller: start it with a state directory (the installer does).", "reason"));
      applySetupStep();
      return;
    }
    const offered = setupState.choices || {inference: [], compute: [], agent: []};
    const steps = setupState.steps || {};
    const j = journey();
    body.replaceChildren();

    // 1. Start your signer, then check it: the public hotkey address names
    // its socket, and the signer says which hotkey it holds. Nothing is
    // signed, and Carbon never sees the key.
    const signerHotkey = steps.signer?.hotkey || setupState.registered_hotkey || "";
    const signer = stepPanel(body, "signer", j.done.signer ? "Your signer answered for " + (signerHotkey || "your registered hotkey") + "." : null);
    signer.append(el("p", "Start it in your own terminal and leave it open:", "step-lede"));
    copyRow(signer, null, offered.signer?.command || "carbon-miner-signer --wallet <your wallet> --hotkey <your hotkey>", "setup-signer-copy");
    researchNote(signer, "Use your own wallet and hotkey names. Carbon never asks for your key or its password.", "hint");
    const signerLabel = el("label", "Your hotkey address (ss58)"); signerLabel.htmlFor = "setup-signer-address";
    const signerAddress = el("input"); signerAddress.id = "setup-signer-address"; signerAddress.type = "text"; signerAddress.autocomplete = "off"; signerAddress.spellcheck = false; signerAddress.placeholder = "5...";
    signerAddress.value = signerHotkey || $("onboarding-address").value.trim();
    const signerCheck = el("button", j.done.signer ? "Check my signer again" : "Check my signer", j.done.signer ? "" : "primary"); signerCheck.type = "button"; signerCheck.id = "setup-signer-check";
    signerCheck.addEventListener("click", () => {
      const address = signerAddress.value.trim();
      if (!address) { $("setup-result").replaceChildren(setupLine("Enter your hotkey address: its public ss58 address, never a key or phrase.", "error")); return; }
      setupCall("signer", {address});
    });
    const signerAction = el("div", undefined, "step-action"); signerAction.append(signerCheck);
    signer.append(signerLabel, signerAddress, signerAction);
    researchNote(signer, "This asks your signer which hotkey it holds. Nothing is signed. You can also register first: steps 1 and 2 go in either order.", "hint");

    // 2. Register on the subnet: confirmed here, prepared under Wallet.
    const register = stepPanel(body, "register", j.registered ? "Registered: " + setupState.registered_hotkey : null);
    if (!j.registered) {
      register.append(el("p", "Paste your hotkey address. Carbon reads the chain to confirm it is registered.", "step-lede"));
      const label = el("label", "Your hotkey address (ss58)"); label.htmlFor = "setup-register-address";
      const address = el("input"); address.id = "setup-register-address"; address.type = "text"; address.autocomplete = "off"; address.spellcheck = false; address.placeholder = "5...";
      address.value = steps.signer?.hotkey || $("onboarding-address").value.trim();
      const confirm = el("button", "Check my registration", "primary go"); confirm.type = "button"; confirm.id = "setup-register-confirm";
      confirm.addEventListener("click", () => confirmRegistration(address.value.trim()));
      const action = el("div", undefined, "step-action"); action.append(confirm);
      register.append(label, address, action);
      researchNote(register, "Not registered yet? Wallet & Identity prepares the unsigned call; you sign it in your own wallet, paid from your coldkey.", "hint");
      register.append(link({label: "Register under Wallet & Identity", href: "#wallet"}));
      // What opens once registration is confirmed.
      register.append(el("p", "What happens next", "eyebrow"));
      const next = el("ol", undefined, "guide-steps");
      next.start = 3;
      for (const [, title, lede] of SETUP_STEPS.slice(2)) { const item = el("li"); item.append(el("strong", title + ": "), lede); next.append(item); }
      register.append(next);
    }

    // 3. Inference.
    const inferencePanel = stepPanel(body, "inference", steps.inference?.checked ? "Checked: " + checkedText("inference", steps) + "." : null);
    if (j.skipped.inference) {
      // The miner's own agent brings its own model.
      const skip = el("p", undefined, "step-done"); skip.id = "setup-inference-skipped";
      skip.append(pill("Skipped", "pill-wait"), el("span", "Your agent uses its own model. Set one here only if you also want Carbon's agent."));
      inferencePanel.prepend(skip);
    }
    const inference = stepForm(inferencePanel, "inference");
    const provider = setupSelect(inference, "provider_id", "Provider", offered.inference.map(c => [c.id, c.display_name]));
    const model = setupField(inference, "model_id", "Model id");
    // A generic adapter has no endpoint of its own: the miner names it here,
    // with an optional declared price (nanodollars per token). Without one the
    // spend is stated as unknown and no money ceiling can be set.
    const generic = el("div"); generic.dataset.step = "inference"; inference.append(generic);
    const endpoint = setupField(generic, "endpoint", "Endpoint URL (https, the full completion route)");
    const priceBox = advanced(generic, "Your price (optional)");
    researchNote(priceBox, "Nanodollars per token, the date you read it and where.", "hint");
    const declared = {};
    for (const [name, label, type] of [["input_nano", "Input", "number"], ["cached_input_nano", "Cached input", "number"], ["output_nano", "Output (including reasoning)", "number"], ["observed", "Observed (YYYY-MM-DD)", "text"], ["note", "Where this price comes from", "text"]]) {
      declared[name] = setupField(priceBox, name, label, type);
    }
    const key = setupField(inference, "key", "API key (entered once; leave empty to keep the stored key)", "password");
    researchNote(inference, "Written once to an owner-only file on this machine, never shown again, and sent only to this provider.", "hint");
    const inferenceCost = el("div"); inference.append(inferenceCost);
    const describeProvider = () => {
      const choice = offered.inference.find(c => c.id === provider.value);
      inferenceCost.replaceChildren();
      if (choice) researchNote(inferenceCost, "Billed by " + choice.display_name + " to your account. Carbon bills nothing.", "hint");
      const listed = (choice?.models || []).map(m => m.model_id);
      const about = details(inferenceCost, "About this provider", []);
      const aboutBody = about.querySelector(".detail-body");
      costNote(aboutBody, choice);
      if (choice) researchNote(aboutBody, "Price: " + choice.pricing, "hint");
      researchNote(aboutBody, (listed.length ? "Models: " + listed.join(", ") + " (" : "Models: (") + (choice?.model_policy || "") + ")", "hint");
      generic.hidden = !choice?.needs_endpoint;
      if (!model.value) model.value = (choice?.models || []).find(m => m.default)?.model_id || listed[0] || "";
    };
    const inferenceSpec = () => {
      const choice = offered.inference.find(c => c.id === provider.value);
      const spec = {provider_id: provider.value, model_id: model.value.trim()};
      if (!choice?.needs_endpoint) return spec;
      spec.endpoint = endpoint.value.trim();
      if (Object.values(declared).some(input => input.value.trim())) {
        spec.declared_pricing = {};
        for (const [name, input] of Object.entries(declared)) {
          const value = input.value.trim();
          spec.declared_pricing[name] = input.type === "number" && value !== "" && /^\d+$/.test(value) ? Number(value) : value;
        }
      }
      return spec;
    };
    // Consent is to a quoted amount: the server states the check's maximum
    // cost for this model, the miner ticks to agree to that amount, and only
    // that amount is sent. Nothing is ticked by default, and any change of
    // provider or model clears the agreement.
    const agree = document.createElement("input");
    agree.type = "checkbox"; agree.id = "setup-inference-consent"; agree.checked = false;
    const agreeLabel = el("label", "Quoting the cost of this check..."); agreeLabel.htmlFor = agree.id;
    const agreeRow = el("div", undefined, "consent"); agreeRow.append(agree, agreeLabel);
    inference.append(agreeRow);
    const check = el("button", "Check with my key (billed to me)", "primary"); check.disabled = true;
    inference.append(check);
    let quote = null, quoting = 0;
    const requote = async () => {
      const mine = ++quoting;
      quote = null; agree.checked = false; check.disabled = true; agree.disabled = true;
      const wanted = inferenceSpec();
      if (!wanted.model_id) { agreeLabel.textContent = "Choose a model to see what this check costs."; return; }
      if (wanted.endpoint === "") { agreeLabel.textContent = "Enter your endpoint to see what this check costs."; return; }
      try {
        const answer = await api("/api/v1/setup/quote", wanted, undefined, 15000);
        if (mine !== quoting) return;
        quote = answer; agree.disabled = false;
        agreeLabel.textContent = "I agree to this charge on my own account: " + answer.statement;
      } catch (error) {
        if (mine !== quoting) return;
        agreeLabel.textContent = "No quote: " + (error.field ? error.field + ": " : "") + words(error.message);
      }
    };
    agree.addEventListener("change", () => { check.disabled = !(agree.checked && quote); });
    provider.addEventListener("change", () => { model.value = ""; describeProvider(); requote(); });
    model.addEventListener("change", requote);
    for (const input of [endpoint, ...Object.values(declared)]) input.addEventListener("change", requote);
    if (steps.inference?.checked) {
      provider.value = steps.inference.provider_id; model.value = steps.inference.model_id;
      endpoint.value = steps.inference.endpoint || "";
      for (const [name, input] of Object.entries(declared)) input.value = steps.inference.declared_pricing?.[name] ?? "";
    }
    describeProvider();
    requote();
    inference.addEventListener("submit", async event => {
      event.preventDefault();
      if (!(agree.checked && quote)) return;
      // The quote was for this exact spec; any edit since re-quoted it.
      const request = {...inferenceSpec(), consent: {max_cost_nano: quote.max_cost_nano}};
      if (key.value) request.key = key.value;
      key.value = "";
      await setupCall("inference", request);
    });

    // 4. Compute: "Where's your GPU?" (LINKONLY-D10).
    // Checked but still waiting for its worker is not done yet.
    const computeDone = steps.compute?.checked && !j.sendPending ? "Checked: " + checkedText("compute", steps) + "." : null;
    const computePanel = stepPanel(body, "compute", computeDone);
    // A check that no longer describes this install, or one an update set
    // aside (LP-PROD-E): why, and setup's own step that clears it.
    const computeStale = staleCompute(steps);
    if (computeStale) setupAttention(computePanel, "compute-stale", computeStale.title, computeStale.reasons, computeStale.next);
    const compute = stepForm(computePanel, "compute");
    const remoteChoice = offered.compute.find(c => c.needs_remote);
    const guides = remoteChoice?.guides || {cards: [], notes: []};
    const where = el("fieldset", undefined, "where"); where.append(el("legend", "Where's your GPU?"));
    const grid = el("div", undefined, "where-grid"); where.append(grid);
    compute.append(where);
    const wherePanel = el("div", undefined, "guide-panel"); wherePanel.id = "setup-guide-panel"; wherePanel.hidden = true;
    compute.append(wherePanel);
    // Shown for a GPU choice: the Challenge to practise.
    const gpuBox = el("div"); gpuBox.dataset.step = "compute"; compute.append(gpuBox);
    const gpuChallenge = setupSelect(gpuBox, "challenge", "Challenge to practise on the GPU", []);
    // Your own remote machine or container (OWNER-MINER-COMPUTE-LINK-ONLY-01,
    // amended 2026-10-02): you start, stop and pay for it; Carbon reaches it
    // with your own SSH and never starts, stops or bills it.
    const remoteBox = el("div"); remoteBox.dataset.step = "compute"; compute.append(remoteBox);
    const destination = setupField(remoteBox, "destination", "SSH destination (user@host, or your ssh-config alias)");
    const sshPort = setupField(remoteBox, "port", "SSH port (optional; leave empty for your ssh config's)", "number");
    researchNote(remoteBox, "Make `ssh <destination>` work from this machine without a prompt first: your key in your agent, the host key in your known hosts. Carbon passes no key and installs nothing.", "hint");
    const missing = el("div"); compute.append(missing);
    // Everything setup fills in for you, or a miner changes on purpose.
    const more = advanced(compute, "Advanced: images and transport");
    const computeChoice = setupSelect(more, "choice", "Where research runs (set by the cards above)", offered.compute.map(c => [c.id, c.display_name]));
    const transportBox = el("div"); transportBox.dataset.step = "compute"; more.append(transportBox);
    const transport = setupSelect(transportBox, "transport", "How Carbon reaches it (set by your card)", []);
    const transportNote = el("div"); transportBox.append(transportNote);
    const images = setupState.images || {};
    const installed = setupState.installed || {};
    const imageNote = field => {
      const found = images[field];
      return found?.path ? "Filled in: found by " + found.found_by + "." : "Not found yet.";
    };
    const image = setupField(more, "image_manifest", "Your worker image (manifest path)");
    researchNote(more, imageNote("image_manifest"), "hint");
    const analysis = setupField(more, "analysis_image_manifest", "Your analysis image (manifest path)");
    researchNote(more, imageNote("analysis_image_manifest"), "hint");
    const gpuImageBox = el("div"); gpuImageBox.dataset.step = "compute"; more.append(gpuImageBox);
    const gpuImage = setupField(gpuImageBox, "gpu_image_manifest", "Your GPU worker image (manifest path)");
    researchNote(gpuImageBox, imageNote("gpu_image_manifest"), "hint");
    // Filled in from what scripts/install_miner.sh built here (C-MLP-04), or
    // where the GPU worker's build script wrote it.
    image.value = images.image_manifest?.path || installed.image_manifest || "";
    analysis.value = images.analysis_image_manifest?.path || installed.analysis_image_manifest || "";
    gpuImage.value = images.gpu_image_manifest?.path || installed.gpu_image_manifest || "";
    const computeButton = el("button", "Check on this machine", "primary"); computeButton.id = "setup-compute-submit";
    const commandCodes = [];
    const fill = command => {
      const target = destination.value.trim();
      if (!command.destination || !target) return command.command;
      return command.command.replace("<destination>", (sshPort.value.trim() ? "-p " + sshPort.value.trim() + " " : "") + target);
    };
    const updateCommands = () => { for (const [code, command] of commandCodes) code.textContent = fill(command); };
    destination.addEventListener("input", updateCommands);
    sshPort.addEventListener("input", updateCommands);
    const describeMissing = () => {
      missing.replaceChildren();
      if (!image.value.trim() || !analysis.value.trim()) {
        missing.append(el("p", "Carbon hasn't found your worker images. Build and record them in your Carbon checkout, then reload this page:", "reason"));
        copyRow(missing, null, images.image_manifest?.build || "scripts/install_miner.sh --no-start");
      }
      if (!gpuImageBox.hidden && !gpuImage.value.trim()) {
        missing.append(el("p", "Build your GPU worker image once (no GPU needed here), then reload this page:", "reason"));
        copyRow(missing, null, images.gpu_image_manifest?.build || "scripts/dev/accelerator_worker_image.sh");
      }
    };
    for (const input of [image, analysis, gpuImage]) input.addEventListener("input", describeMissing);
    const describeTransport = () => {
      const choice = offered.compute.find(c => c.id === computeChoice.value);
      const chosen = (choice?.transports || []).find(t => t.id === transport.value);
      transportNote.replaceChildren();
      if (chosen?.summary) researchNote(transportNote, chosen.summary, "hint");
    };
    transport.addEventListener("change", describeTransport);
    const describeCompute = () => {
      const choice = offered.compute.find(c => c.id === computeChoice.value);
      gpuBox.hidden = !choice?.needs_gpu_image;
      gpuImageBox.hidden = !choice?.needs_gpu_image;
      remoteBox.hidden = !choice?.needs_remote;
      transportBox.hidden = !choice?.needs_remote;
      computeButton.textContent = choice?.needs_remote ? "Check my setup over my SSH" : "Check on this machine";
      const forChallenges = choice?.for_challenges || [];
      const previous = gpuChallenge.value;
      gpuChallenge.replaceChildren(...forChallenges.map(item => { const option = el("option", item.title + " · v" + item.version); option.value = JSON.stringify({id: item.id, version: item.version}); return option; }));
      if ([...gpuChallenge.options].some(option => option.value === previous)) gpuChallenge.value = previous;
      // Only what is built can be chosen; the endpoint transport says why not.
      const previousTransport = transport.value;
      transport.replaceChildren(...(choice?.transports || []).map(item => {
        const option = el("option", item.display_name + (item.available ? "" : " · not built: " + words(item.reason)));
        option.value = item.id; option.disabled = !item.available; return option;
      }));
      if ([...transport.options].some(option => option.value === previousTransport && !option.disabled)) transport.value = previousTransport;
      describeTransport();
      describeMissing();
    };
    // The cards: this machine, then each setup the wiring guide covers.
    const local = offered.compute.filter(c => !c.needs_remote);
    const cards = [
      ...local.map(c => ({id: c.id, title: "This machine", sub: c.needs_gpu_image ? "My GPU" : "CPU · the default", choice: c.id})),
      ...(remoteChoice ? guides.cards.map(g => ({id: g.id, title: g.display_name, sub: g.transport === "ssh-container" ? "Container · SSH" : "Machine with Docker · SSH", choice: remoteChoice.id, transport: g.transport, guide: g})) : []),
    ];
    const aboutRemote = (parent, choice) => details(parent, "About remote practice", ["Cost: " + choice.cost_basis, "Live check: " + choice.live_check, choice.note, "Wiring guide: " + choice.guide]);
    const showWhere = card => {
      wherePanel.replaceChildren(); commandCodes.length = 0;
      const choice = offered.compute.find(c => c.id === computeChoice.value);
      wherePanel.hidden = !card && !choice?.needs_remote;
      if (!card) {
        // The remote choice made under Advanced, with no card picked.
        if (choice?.needs_remote) {
          wherePanel.append(el("p", "Pick where your GPU runs above to see its steps."));
          wherePanel.append(link({label: "Open the full guide", href: "#guide"}));
          aboutRemote(wherePanel, choice);
        }
        return;
      }
      if (!card.guide) {
        wherePanel.append(el("h3", card.title + " · " + card.sub));
        wherePanel.append(el("p", choice.needs_gpu_image ? "Practice runs on your own GPU, for speed only." : "Practice runs in an isolated container on this machine. Nothing is rented."));
        details(wherePanel, "About this choice", ["Cost: " + choice.cost_basis, "Live check: " + choice.live_check, choice.note]);
        return;
      }
      const g = card.guide;
      const head = el("div", undefined, "card-head"); head.append(el("h3", g.display_name), pill(g.transport, "pill-dev"));
      wherePanel.append(head);
      wherePanel.append(el("p", "You start, stop and pay for it" + (g.id === "own-server" ? "" : " at " + g.display_name) + ". Carbon reaches it with your own SSH and never starts, stops or bills it."));
      wherePanel.append(el("p", "Your steps, from the guide", "eyebrow"));
      const steps = el("div", undefined, "guide-steps");
      if (g.steps.length) renderBlocks(steps, g.steps);
      else steps.append(el("p", "This checkout has no guide section for it.", "hint"));
      wherePanel.append(steps);
      wherePanel.append(el("p", "Commands you run", "eyebrow"));
      g.commands.forEach((command, index) => commandCodes.push([copyRow(wherePanel, command.label, fill(command), "setup-copy-" + g.id + "-" + index), command]));
      const full = link({label: "Open the full guide", href: "#guide/" + g.anchor}); full.id = "setup-guide-link";
      wherePanel.append(full);
      const notes = el("div", undefined, "hint"); renderBlocks(notes, guides.notes); wherePanel.append(notes);
      aboutRemote(wherePanel, choice);
    };
    const pick = (card, remember) => {
      for (const input of grid.querySelectorAll("input")) input.checked = Boolean(card) && input.value === card.id;
      if (card) {
        computeChoice.value = card.choice;
        describeCompute();
        if (card.transport) { transport.value = card.transport; describeTransport(); }
        if (remember) store(whereKey, {id: card.id});
      }
      showWhere(card);
    };
    for (const card of cards) {
      const label = el("label", undefined, "where-card");
      const input = el("input"); input.type = "radio"; input.name = "setup-where"; input.value = card.id; input.id = "setup-where-" + card.id;
      input.addEventListener("change", () => pick(card, true));
      const text = el("span"); text.append(el("strong", card.title), el("small", card.sub));
      label.append(input, text); grid.append(label);
    }
    // A choice made directly in Advanced keeps the cards in step.
    computeChoice.addEventListener("change", () => {
      describeCompute();
      const shown = cards.find(card => card.id === stored(whereKey, {}).id && card.choice === computeChoice.value) || cards.find(card => !card.guide && card.choice === computeChoice.value) || null;
      pick(shown, false);
    });
    const checkedMachine = steps.compute?.remote_machine;
    const remembered = cards.find(card => card.id === stored(whereKey, {}).id) || null;
    let initial = cards[0] || null;
    if (steps.compute?.checked && steps.compute.choice) {
      initial = steps.compute.choice === remoteChoice?.id
        ? (remembered?.guide && remembered.transport === checkedMachine?.transport ? remembered : null)
        : cards.find(card => card.choice === steps.compute.choice) || null;
      computeChoice.value = steps.compute.choice;
    } else if (remembered) initial = remembered;
    if (initial) pick(initial, false);
    else describeCompute();
    if (checkedMachine) {
      transport.value = checkedMachine.transport; destination.value = checkedMachine.destination;
      sshPort.value = checkedMachine.port ?? "";
      describeTransport(); updateCommands();
    }
    const action = el("div", undefined, "step-action"); action.append(computeButton); compute.append(action);
    compute.addEventListener("submit", async event => {
      event.preventDefault();
      const request = {choice: computeChoice.value, image_manifest: image.value.trim(), analysis_image_manifest: analysis.value.trim()};
      if (!gpuBox.hidden) {
        request.gpu_image_manifest = gpuImage.value.trim();
        if (gpuChallenge.value) request.challenge = JSON.parse(gpuChallenge.value);
      }
      if (!remoteBox.hidden) {
        request.remote = {transport: transport.value, destination: destination.value.trim()};
        if (sshPort.value.trim()) request.remote.port = Number(sshPort.value.trim());
      }
      await setupCall("compute", request);
    });

    // Send your worker: a machine with Docker that does not hold the pinned
    // GPU worker yet. Nothing is sent without consent to that destination and
    // that image, unticked by default; it streams over your own SSH.
    const remoteCheck = steps.compute?.check?.remote;
    if (checkedMachine && checkedMachine.transport === "ssh-docker" && remoteCheck?.worker_image === "missing") {
      const sendBox = el("section", undefined, "guide-panel"); computePanel.append(sendBox);
      sendBox.append(el("h3", "Send your worker"));
      const send = stepForm(sendBox, "send_worker");
      const workerImage = steps.compute.check.gpu_image;
      const target = checkedMachine.destination + (checkedMachine.port ? " (port " + checkedMachine.port + ")" : "");
      researchNote(send, "Your machine does not hold the pinned GPU worker. Carbon can stream it there over your own SSH (docker save | ssh docker load) and check its image ID. It can take minutes.", "hint");
      const sendAgree = document.createElement("input");
      sendAgree.type = "checkbox"; sendAgree.id = "setup-send-worker-consent"; sendAgree.checked = false;
      const sendLabel = el("label", "Send the pinned GPU worker " + workerImage + " to " + target + "."); sendLabel.htmlFor = sendAgree.id;
      const sendRow = el("div", undefined, "consent"); sendRow.append(sendAgree, sendLabel);
      send.append(sendRow);
      const sendButton = el("button", sendingWorker ? "Sending…" : "Send my worker", "primary"); sendButton.disabled = true;
      sendAgree.addEventListener("change", () => { sendButton.disabled = !sendAgree.checked || Boolean(sendingWorker); });
      send.append(sendButton);
      send.addEventListener("submit", async event => {
        event.preventDefault();
        if (!sendAgree.checked || sendingWorker) return;
        const consent = {destination: checkedMachine.destination, image: workerImage};
        if (checkedMachine.port) consent.port = checkedMachine.port;
        sendButton.disabled = true; sendButton.textContent = "Sending…";
        try { await sendWorker({consent: {send: consent}}, target); }
        finally {
          // A send that did not go through leaves this form drawn: its
          // button is ready again, as its consent box says.
          sendButton.textContent = "Send my worker";
          sendButton.disabled = !sendAgree.checked || Boolean(sendingWorker);
        }
      });
    }

    // 3. Who researches? Carbon's agent, or the miner's own agent over MCP
    // (OWNER-MINER-SETUP-AGENT-FIRST-01): any MCP client, or Hermes with its
    // ready-made profile.
    const agentPanel = stepPanel(body, "agent", steps.agent?.checked ? "Checked: " + checkedText("agent", steps) + ", and your signer answered." : null);
    const agent = stepForm(agentPanel, "agent");
    const agentChoice = setupSelect(agent, "choice", "Who researches", offered.agent.map(c => [c.id, c.display_name]));
    const agentCost = el("div"); agent.append(agentCost);
    // Your own agent: the one command, and each client's snippet to copy.
    const connectBox = el("div", undefined, "guide-panel"); connectBox.id = "setup-agent-connect"; agent.append(connectBox);
    const describeConnect = choice => {
      connectBox.replaceChildren();
      connectBox.hidden = !choice?.connect;
      if (!choice?.connect) return;
      const connect = choice.connect;
      connectBox.append(el("h3", "Connect your agent"), el("p", "Skips Inference: " + choice.skips.inference + ". " + connect.note, "hint"));
      copyRow(connectBox, "The one command, run from your Carbon checkout (" + connect.cwd + ")", connect.command, "setup-agent-command-copy");
      // One disclosure per client: its snippets, its source and what Carbon
      // has not verified.
      for (const client of connect.clients) {
        const body = details(connectBox, client.name, []).querySelector(".detail-body");
        body.append(el("p", "From " + client.source + ".", "hint"));
        client.snippets.forEach((snippet, index) => copyRow(body, snippet.label, snippet.text, "setup-agent-" + client.id + "-" + index));
        for (const note of client.unverified) {
          const line = el("p", undefined, "hint"); line.append(el("strong", "UNVERIFIED:", "unverified"), " " + note.replace(/^UNVERIFIED: /, "")); body.append(line);
        }
      }
      connectBox.append(el("p", "Then your agent loops on carbon_setup_status until launch; the carbon_setup_workflow_v1 prompt says how. You can finish here too: both doors share one setup.", "hint"));
    };
    researchNote(agent, "Carbon never asks for your hotkey or its password. Start carbon-miner-signer for your registered hotkey in your own terminal; this step asks it which hotkey it holds.", "hint");
    // Hermes (C-MLP-03 slice 5): nothing is written to the miner's Hermes
    // without their consent to the exact files, unticked by default.
    const hermesBox = el("div"); agent.append(hermesBox);
    const hermesAgree = document.createElement("input");
    hermesAgree.type = "checkbox"; hermesAgree.id = "setup-agent-hermes-consent"; hermesAgree.checked = false;
    const hermesLabel = el("label"); hermesLabel.htmlFor = hermesAgree.id;
    const hermesRow = el("div", undefined, "consent"); hermesRow.append(hermesAgree, hermesLabel);
    hermesBox.append(hermesRow);
    // Miners leave these empty: setup reads Carbon's testnet and its
    // publisher from the chain. Only an operator running Carbon's deployment
    // names a config.
    const agentMore = advanced(agent);
    const operator = setupField(agentMore, "operator_config", "Operator config (operators only; leave empty)");
    const socket = setupField(agentMore, "signer_socket", "Signer socket (optional; leave empty for the default)");
    const describeAgent = () => {
      const choice = offered.agent.find(c => c.id === agentChoice.value);
      agentCost.replaceChildren();
      const about = details(agentCost, "About this agent", []);
      costNote(about.querySelector(".detail-body"), choice);
      describeConnect(choice);
      hermesBox.hidden = !choice?.needs_consent_to_write;
      hermesAgree.checked = false;
      if (choice?.needs_consent_to_write) {
        hermesLabel.textContent = "Write my Hermes profile: " + (choice.writes || []).join(", ") + ". Then start it with: " + choice.start;
      }
    };
    agentChoice.addEventListener("change", describeAgent);
    if (steps.agent?.checked && steps.agent.choice) agentChoice.value = steps.agent.choice;
    describeAgent();
    const agentAction = el("div", undefined, "step-action"); agentAction.append(el("button", "Check my signer", "primary")); agent.append(agentAction);
    agent.addEventListener("submit", async event => {
      event.preventDefault();
      const request = {choice: agentChoice.value};
      if (operator.value.trim()) request.operator_config = operator.value.trim();
      if (socket.value.trim()) request.signer_socket = socket.value.trim();
      const choice = offered.agent.find(c => c.id === agentChoice.value);
      if (choice?.needs_consent_to_write) {
        if (!hermesAgree.checked) { $("setup-result").replaceChildren(setupLine("consent: tick to agree to the files your Hermes profile needs.")); return; }
        request.consent = {writes: choice.writes};
      }
      await setupCall("agent", request);
    });

    // 6. Review and launch.
    const written = Boolean(steps.review?.profile_written);
    const reviewPanel = stepPanel(body, "review", written ? "Your profile is written." : null);
    const review = stepForm(reviewPanel, "review");
    const summary = el("dl", undefined, "review-grid"); review.append(summary);
    for (const [name, label] of [["agent", "Who researches"], ["inference", "Inference"], ["compute", "Compute"]]) {
      const state = steps[name] || {};
      summary.append(el("dt", label), el("dd", state.checked ? checkedText(name, steps) : j.skipped[name] ? "Skipped: your agent uses its own model" : "Not checked yet"));
    }
    researchNote(review, "Writes your runner profile beside this controller and loads it. Nothing is launched and nothing is spent.", "hint");
    const evaluationBox = el("div"); review.append(evaluationBox);
    // A validator's intake, when a Challenge's validator runs elsewhere
    // (C-MLP-03 slice 6, per Challenge since C-MLP-04). Its public facts are
    // read and checked by that Challenge; nothing is signed.
    const reviewMore = advanced(review, "Advanced: a validator's intake");
    const intakeChallenges = offered.intake_challenges || [];
    const intakeChallenge = setupSelect(reviewMore, "intake_challenge", "Validator intake for", intakeChallenges.map(item => [item.id, item.title + " · v" + item.version]));
    const intake = setupField(reviewMore, "intake_url", "Validator intake URL (optional; https, or loopback)");
    intakeChallenge.disabled = intake.disabled = !intakeChallenges.length;
    evaluationSection(evaluationBox, steps.evaluation, (challengeId, url) => {
      // Review writes only the intakes it is given: this one, again.
      intakeChallenge.value = challengeId; intake.value = url;
      reviewMore.parentNode.open = true;
      $("setup-result").replaceChildren(setupLine("Your intake is named again below. Write your profile to keep it."));
    });
    const write = el("button", written ? "Write my profile again" : "Write my profile", written ? "" : "primary");
    write.disabled = !steps.review?.ready;
    const reviewAction = el("div", undefined, "step-action"); reviewAction.append(write);
    if (caps?.profile?.configured) {
      const go = link({label: "Choose a Challenge", href: "#challenges"}, "button primary"); go.id = "setup-choose-challenge";
      reviewAction.prepend(go);
    }
    review.append(reviewAction);
    if (!steps.review?.ready) researchNote(review, "Finish steps 3 to 5 first.", "hint");
    review.addEventListener("submit", async event => {
      event.preventDefault();
      const request = {confirm: true};
      if (intake.value.trim() && intakeChallenge.value) request.intakes = {[intakeChallenge.value]: intake.value.trim()};
      await setupCall("review", request);
    });
    applySetupStep();
  }

  $("onboarding-status").addEventListener("click", () => onboardingCall("status"));
  $("onboarding-prepare").addEventListener("click", () => onboardingCall("prepare"));
  $("onboarding-confirm").addEventListener("click", () => onboardingCall("confirm"));

  // ---- Capabilities: read on connect and on request, never assumed. ----
  async function readCapabilities() {
    const value = await api("/api/v1/control-center/capabilities", undefined, undefined, 20000);
    if (value.schema !== CAPS_SCHEMA) throw new Error("unsupported_controller_version");
    caps = value;
    capsVersion++;
    // A remembered choice is checked against what exists now.
    if (wizard.challenge && !challengeEntry(wizard.challenge)) wizard.challenge = null;
    // A choice no longer offered (the autonomous agent, once Graphite
    // replaces it) is no longer chosen.
    if (wizard.agentChoice && !offeredAgent(wizard.agentChoice)) { wizard.agentChoice = null; composition = {...composition, agent: null}; }
    if (wizard.agentChoice) composition = {...composition, agent: agentEntry(wizard.agentChoice).launch_agent};
    // The model chosen in setup is the launch's model unless the miner picks
    // another here (LP-PROD-F): prefilled, so the Model step passes with it.
    const setupModel = caps.model?.setup_choice;
    const listed = (provider, model) => (caps.model?.providers || []).some(row => row.id === provider && row.models.some(entry => entry.id === model));
    if (wizard.provider && !listed(wizard.provider, wizard.model)) { wizard.provider = null; wizard.model = null; }
    if (!wizard.provider && setupModel && listed(setupModel.provider_id, setupModel.model_id)) {
      wizard.provider = setupModel.provider_id; wizard.model = setupModel.model_id;
    }
  }
  function challengeEntry(selection) {
    if (!caps || !selection) return null;
    return caps.challenges.find(entry => entry.challenge_id === selection.id && entry.version === selection.version) || null;
  }
  function agentEntry(id) { return caps?.agents.choices.find(choice => choice.id === id) || null; }
  function selectedProvider() {
    const providers = caps?.model.providers || [];
    return providers.find(provider => provider.id === wizard.provider) || null;
  }
  // The provider and model a launch names, or null: a model this page lists,
  // at an available provider, for an agent that calls one.
  function launchModel() {
    if (!caps?.model?.launch_field || !agentEntry(wizard.agentChoice)?.uses_model) return null;
    const provider = selectedProvider();
    if (provider?.availability !== "available" || !wizard.model || !provider.models.some(model => model.id === wizard.model)) return null;
    return {provider, model: wizard.model};
  }
  // The launch's optional output cap, model_settings.max_output_tokens
  // (LAUNCHPAD-PAGE-USABILITY-01): offered only when the launch names its
  // provider and model, since the runner refuses settings without them. The
  // bounds and each model's default are the controller's; this check only
  // mirrors the runner's, which validates the launch and has the last word.
  function outputCap() {
    const cap = caps?.model?.output_cap;
    const chosen = launchModel();
    if (!cap || !Array.isArray(cap.bounds) || cap.bounds.length !== 2 || !chosen) return null;
    const [low, high] = cap.bounds;
    const fallback = cap.defaults?.[chosen.provider.id]?.[chosen.model] || null;
    const text = String(wizard.maxOutput ?? "").trim();
    let value = null, problem = null;
    if (text) {
      value = /^\d+$/.test(text) ? Number(text) : NaN;
      if (!Number.isSafeInteger(value) || value < low || value > high) {
        problem = "max output tokens must be a whole number from " + low.toLocaleString("en-US") + " to " + high.toLocaleString("en-US");
        value = null;
      }
    }
    return {low, high, fallback, value, problem, basis: cap.basis};
  }
  const OUTPUT_BASIS = {model_documented_maximum: "this model's documented maximum", provider_documented_maximum: "the provider's documented maximum", no_documented_maximum: "Carbon records no maximum for this model, so the conservative cap"};
  function outputDefault(cap) {
    if (!cap?.fallback) return "the runner's default";
    return cap.fallback.max_output_tokens.toLocaleString("en-US") + " tokens (" + (OUTPUT_BASIS[cap.fallback.basis] || "the runner's default") + ")";
  }
  // The provider and model the runner profile's setup chose, or null.
  function setupModel() {
    const value = caps?.model?.setup_choice;
    return value && typeof value.provider_id === "string" && typeof value.model_id === "string" ? value : null;
  }
  function computeChoice() { return caps?.compute.choices[0] || null; }

  async function refresh() {
    if (!token || polling) return;
    polling = true;
    try {
      runs = (await api("/api/v1/runs")).runs;
      developmentSources = (await api("/api/v1/development")).sources;
      research = await api("/api/v1/research");
      if (research.preflight.available && !launchOptions) {
        try { launchOptions = await api("/api/v1/operations/options", {}); }
        catch (_) { launchOptions = null; }
      }
      if (!launchShape) {
        try {
          const listed = (await api("/api/v1/operations")).operations;
          operationsListed = Array.isArray(listed) ? listed : null;
          launchShape = operationsListed?.find(op => op.operation === "launch") || null;
        } catch (_) { launchShape = null; }
      }
      connected = true;
      land();
      settleWatches();
      settleHeld();
      quietly(render);
      if (!setupRead) { setupRead = true; readSetup(); }
      else pollSetup();
      setText($("connection-state"), "Connected");
    } catch (error) {
      connected = false;
      quietly(render);
      setText($("connection-state"), "Connection interrupted");
      message("Controller connection interrupted. Runs may still be active. Reconnect before issuing another command.", true);
    } finally { polling = false; }
  }
  // A returning miner lands on their active campaign; otherwise where they were.
  function land() {
    if (landed) return;
    landed = true;
    if (location.hash) return;
    const active = research.runs.find(run => !TERMINAL.includes(run.state));
    if (active) { location.hash = campaignHref(active.id); return; }
    const last = stored(routeKey, null);
    if (last && typeof last.hash === "string" && last.hash.startsWith("#")) location.hash = last.hash;
  }
  $("connect-form").addEventListener("submit", event => {
    event.preventDefault();
    if (busy || polling) return;
    connect($("token").value.trim());
  });
  // The session link connects as a pasted token does. One read while a
  // refresh or an operation is under way waits for it, rather than being lost.
  function connectFromLink(value) {
    if (!value) {
      message("This address held a session link this page cannot read. Open the link the Control Center printed again, or paste its local session token.", true);
      return;
    }
    if (busy || polling) { setTimeout(() => connectFromLink(value), 250); return; }
    connect(value);
  }
  async function connect(value) {
    connected = false;
    render();
    token = value;
    try {
      await readCapabilities();
      const catalog = await api("/api/v1/capabilities");
      if (catalog.schema !== "carbon.launchpad.rehearsal.v1" || catalog.mode !== "REHEARSAL") {
        throw new Error("unsupported_controller_version");
      }
      $("token").value = "";
      $("integrations").replaceChildren();
      for (const item of catalog.unavailable) {
        const box = document.createElement("div"); box.className = "integration";
        const title = document.createElement("strong"); title.textContent = item.id;
        const reason = document.createElement("p"); reason.textContent = item.reason.replaceAll("_", " ");
        box.append(title, reason); $("integrations").append(box);
      }
      // Order matters: renderExamEnvironment clears the panel before filling
      // it, so the compute choices are appended after it rather than before.
      await renderExamEnvironment();
      renderComputeChoices(caps.compute.destinations || []);
      await onboardingRequirements();
      message("Connected. Records persist on this machine.");
      await refresh();
      if (storageError) message("Browser retry storage is unavailable. Launch is disabled to preserve duplicate protection.", true);
    } catch (error) {
      token = "";
      connected = false;
      $("connection-state").textContent = "Disconnected";
      render();
      message("Could not connect: " + error.message, true);
    }
  }
  $("settings-recheck").addEventListener("click", async () => {
    if (busy || !connected) return;
    busy = true; render();
    try { await readCapabilities(); launchOptions = null; launchShape = null; message("Capabilities re-read from the controller."); }
    catch (error) { message("Capabilities not re-read: " + error.message, true); }
    finally { busy = false; await refresh(); render(); }
  });
  $("settings-clear").addEventListener("click", () => {
    for (const key of [wizardKey, draftKey, routeKey]) { try { localStorage.removeItem(key); } catch (_) { /* nothing stored */ } }
    for (const key of Object.keys(journeyDrafts)) delete journeyDrafts[key];
    wizard = {step: "challenge", challenge: null, agentChoice: null, provider: null, model: null};
    composition = {agent: null, budget: {}};
    $("settings-note").textContent = "Saved choices and drafts forgotten. Templates are kept; delete them in the launch wizard.";
    render();
  });
  $("launch-form").addEventListener("submit", async event => {
    event.preventDefault();
    if (busy || !connected || storageError) return;
    if (!pending) {
      pending = {key: crypto.randomUUID(), spec: {
        mode: "REHEARSAL", challenge: "controller-rehearsal-v1", agent: "fixture",
        reasoning: "none", compute: "local", max_steps: Number($("steps").value),
        max_seconds: Number($("seconds").value)
      }};
      try { sessionStorage.setItem(pendingKey, JSON.stringify(pending)); }
      catch (_) {
        storageError = true; render();
        message("Could not preserve the retry request. Nothing was dispatched.", true);
        return;
      }
    }
    // In flight, the outcome is unknown until answered: a reload keeps it so.
    const earlier = pending.unknown === true;
    pending.unknown = true;
    try { sessionStorage.setItem(pendingKey, JSON.stringify(pending)); } catch (_) { /* the key still covers this request */ }
    busy = true; $("launch-button").disabled = true;
    try {
      const run = await api("/api/v1/runs", pending.spec, pending.key);
      selected = run.id;
      sessionStorage.removeItem(pendingKey); pending = null;
      message("Rehearsal started. These fixture steps produce no physics or mining evidence.");
      await refresh();
    } catch (error) {
      if (refused(error) && !earlier) {
        // Refused: nothing started, and no earlier attempt is outstanding.
        forgetRehearsal();
        message("Launch refused: " + said(error) + ". Nothing was started; change the request and launch again. Free an active slot if required.", true);
      } else {
        message("Launch not confirmed: " + said(error) + ". Retry sends this same request, including after reconnect: if it was recorded it is replayed, never duplicated. Or discard it.", true);
      }
    } finally { busy = false; $("launch-button").disabled = false; render(); }
  });
  function forgetRehearsal() {
    try { sessionStorage.removeItem(pendingKey); } catch (_) { /* nothing held */ }
    pending = null;
  }
  $("launch-discard").addEventListener("click", () => {
    if (busy || !pending) return;
    forgetRehearsal();
    message("Discarded. If the earlier launch was recorded, it is listed under Rehearsal activity.");
    render();
  });
  for (const action of ["pause", "resume", "stop"]) {
    $(action).addEventListener("click", async () => {
      if (busy || !connected || !selected) return;
      busy = true; render();
      try {
        await api("/api/v1/runs/" + selected + "/" + action, {});
        message("Controller acknowledged: " + action + ".");
        await refresh();
      } catch (error) { message("Command not confirmed: " + error.message + ". Check the run state before retrying.", true); }
      finally { busy = false; render(); }
    });
  }
  $("run-picker").addEventListener("change", () => { selected = $("run-picker").value; render(); });
  $("export").addEventListener("click", async () => {
    if (busy || !connected || !selected) return;
    busy = true; render();
    try {
      const run = await api("/api/v1/runs/" + selected);
      download(run, "carbon-rehearsal-" + run.id + ".json");
    } catch (error) { message("Export not confirmed: " + error.message, true); }
    finally { busy = false; render(); }
  });
  function renderComputeChoices(choices) {
    // Where the miner may run their own research, and what each route needs,
    // beside the exam environment on purpose: they choose the first and are
    // told the second. Kept behind Details: the route cards above lead.
    const panel = $("exam-environment");
    if (!choices.length) return;
    const box = details(panel, "What each research route needs", []);
    const body = box.querySelector(".detail-body");
    body.append(el("h3", "Your research compute"));
    for (const choice of choices.filter(entry => entry.selectable !== false)) {
      const item = el("div", undefined, "integration");
      item.append(el("strong", choice.id.replaceAll("-", " ")), el("p", choice.summary));
      if (choice.requires?.length) researchNote(item, "Needs: " + choice.requires.map(value => value.replaceAll("_", " ").toLowerCase()).join("; "));
      if (choice.not_required?.length) researchNote(item, "Not needed: " + choice.not_required.map(value => value.replaceAll("_", " ").toLowerCase()).join("; "));
      body.append(item);
    }
  }

  async function renderExamEnvironment() {
    const panel = $("exam-environment");
    panel.replaceChildren();
    let contract;
    try {
      contract = await api("/api/v1/exam-environment");
    } catch (error) {
      researchNote(panel, "The published exam environment could not be read. It is a disclosure, not a launch requirement; research and submission are unaffected.");
      return;
    }
    // The plain reading first; the validator's internals behind Details.
    // Declared is not qualified, and the page says which this is.
    researchNote(panel, "Declared, not qualified: published so you can read it before you submit.", "status-line");
    researchNote(panel, "You submit: " + contract.submission.accepted.replaceAll("_", " ").toLowerCase() + ". Not accepted: " + contract.submission.not_accepted.map(value => value.replaceAll("_", " ").toLowerCase()).join("; ") + ".", "hint");
    researchNote(panel, "Your research hardware is not constrained by this contract and does not have to match it. No provider is prescribed, for you or for a validator.", "hint");
    const inside = details(panel, "Exam environment details", []);
    const body = inside.querySelector(".detail-body");
    researchNote(body, "Backend profile: " + contract.backend_profile.profile_id + " · " + contract.backend_profile.backend + " · " + contract.backend_profile.scope);
    researchNote(body, "Qualification: declared, not qualified · Backend support " + contract.qualification.backend_support + " · " + contract.qualification.basis);
    for (const limitation of contract.known_limitations || []) {
      researchNote(body, "Disclosed limitation · " + limitation.statement + " " + limitation.consequence);
    }
    const full = el("details"); full.append(el("summary", "Pinned versions, resource envelope and containment"));
    const data = el("pre"); data.textContent = JSON.stringify(contract, null, 2);
    full.append(data); body.append(full);
  }

  // ---- Overview. ----
  // Get started: the six steps, each done only when the controller confirmed
  // it, the current one highlighted, and one primary action that goes to it.
  function renderGettingStarted() {
    const list = $("getting-started-steps");
    const primary = $("overview-primary");
    const goTo = (text, href) => { setText(primary, text); if (primary.getAttribute("href") !== href) primary.href = href; };
    if (!connected) {
      rebuild(list, "disconnected", target => target.append(el("li", "Connect this browser to see your next step.", "hint")));
      goTo("Get started", "#setup");
      setText($("getting-started-progress"), "");
      return;
    }
    const j = journey();
    const key = JSON.stringify([j.state, j.profile, research.runs.length, setupState?.registered_hotkey ?? null, setupVersion]);
    goTo(j.current ? "Next: " + stepTitle(j.current, j) : "New campaign", j.current ? stepHref(j.current, j) : "#launch");
    setText($("overview-lede"), j.current ? "Step " + (SETUP_IDS.indexOf(j.current) + 1) + " of 6 is next. Each step is checked before it counts." : "You are set up. Choose a Challenge and launch.");
    rebuild(list, key, target => drawGettingStarted(target, j));
    setText($("getting-started-progress"), Object.values(j.state).filter(state => state === "done").length + " of 6 done");
  }
  function drawGettingStarted(list, j) {
    SETUP_IDS.forEach((id, index) => {
      const state = j.state[id];
      const item = el("li", undefined, "gs-step is-" + state + (id === j.current ? " is-current" : ""));
      item.dataset.step = id;
      if (id === j.current) item.setAttribute("aria-current", "step");
      const body = el("div", undefined, "gs-body");
      const title = el("h3"); const go = el("a", stepTitle(id, j)); go.href = stepHref(id, j); title.append(go);
      body.append(title, el("p", stepSentence(id, j)));
      item.append(el("span", String(index + 1).padStart(2, "0"), "gs-num"), body, pill(STATE_LABEL[state], "gs-state pill-" + ({done: "done", next: "next", open: "open"}[state] || "wait")));
      list.append(item);
    });
  }
  function prerequisites() {
    // What a launch needs, each read from the controller - never assumed met.
    if (!caps) return [];
    const items = [];
    items.push(caps.profile.configured
      ? {ok: true, text: "Your runner profile is loaded.", detail: ["Profile: " + caps.profile.profile_id]}
      : {ok: false, area: "Runner profile", item: caps.profile});
    items.push({ok: null, text: "Your subnet registration is read at launch, before anything is recorded.", fix: {label: "Check it", href: "#wallet"}});
    const selectable = caps.challenges.filter(entry => entry.selectable);
    items.push(selectable.length
      ? {ok: true, text: "You can launch: " + selectable.map(entry => entry.title).join(", ") + "."}
      : {ok: false, area: "Challenges", item: caps.challenges.find(entry => entry.implemented) || caps.challenges[0]});
    const agents = agentChoices().filter(choice => choice.availability === "available");
    items.push(agents.length
      ? {ok: true, text: "Agents ready: " + agents.map(choice => choice.label).join(", ") + "."}
      : {ok: false, area: "Agents", item: agentChoices()[0]});
    const provider = caps.model.providers.find(item => item.availability === "available");
    items.push(provider
      ? {ok: true, text: "Model key set for " + provider.provider + "."}
      : {ok: false, area: "Model key (only Carbon's own agent needs one)", item: caps.model.providers[0]});
    const compute = computeChoice();
    items.push(compute && compute.availability === "available"
      ? {ok: true, text: "Compute: " + compute.label + "."}
      : {ok: false, area: "Compute", item: compute});
    return items;
  }
  // One line per need: the same missing cause is said once, with the parts
  // waiting on it, one fix, and each code behind Details.
  function renderReadiness(list, items) {
    list.replaceChildren();
    const groups = new Map();
    for (const item of items) {
      if (item.ok !== false) {
        const entry = el("li", undefined, item.ok ? "ok" : "pending");
        entry.append(pill(item.ok ? "Ready" : "At launch", item.ok ? "pill-done" : "pill-wait"), el("span", item.text));
        if (item.fix) entry.append(link(item.fix));
        if (item.detail) details(entry, "Details", item.detail);
        list.append(entry);
        continue;
      }
      const source = item.item || {};
      const plain = source.plain || {sentence: "Unavailable: " + words(source.reason) + ".", next: null};
      const key = plain.sentence + "|" + (plain.next?.href || "");
      if (!groups.has(key)) {
        const entry = el("li", undefined, "missing");
        const group = {entry, plain, areas: [], lines: []};
        groups.set(key, group);
        list.append(entry);
      }
      const group = groups.get(key);
      group.areas.push(item.area);
      group.lines.push(item.area + ": " + (source.reason || "unknown") + (source.next_action ? " · " + source.next_action : ""));
    }
    for (const group of groups.values()) {
      group.entry.append(pill("Needed", "pill-need"), el("span", group.plain.sentence));
      if (group.areas.length > 1) group.entry.append(el("span", "Waiting on it: " + group.areas.join(", ") + ".", "next"));
      else group.entry.append(el("span", group.areas[0] + ".", "next"));
      if (group.plain.next) group.entry.append(link(group.plain.next, "button fix"));
      details(group.entry, "Details", group.lines);
    }
  }
  function renderChecklist(list, items) {
    list.replaceChildren();
    for (const item of items) {
      const entry = el("li", undefined, item.ok === true ? "ok" : item.ok === false ? "missing" : "pending");
      entry.append(pill(item.ok === true ? "Ready" : item.ok === false ? "Needed" : "At launch", item.ok === true ? "pill-done" : item.ok === false ? "pill-need" : "pill-wait"), el("span", item.text));
      if (item.next) entry.append(el("span", "Next: " + item.next, "next"));
      if (item.href) { const open = el("a", "Open", "inline-link"); open.href = item.href; entry.append(open); }
      list.append(entry);
    }
  }
  function renderOverview() {
    renderGettingStarted();
    const list = $("overview-prerequisites");
    if (!connected || !caps) rebuild(list, "disconnected", target => target.append(el("li", "Connect to read what this controller can do.", "hint")));
    else rebuild(list, "caps:" + capsVersion, target => renderReadiness(target, prerequisites()));
    const live = research.runs.filter(run => !TERMINAL.includes(run.state));
    const shown = connected ? (live.length ? live : research.runs.slice(0, 3)) : [];
    rebuild($("overview-active"), JSON.stringify([connected, research.runs.length, shown.map(cardKey), capsVersion]), active => {
      if (!connected) { researchNote(active, "Connect to see your campaigns.", "hint"); return; }
      if (!research.runs.length) {
        researchNote(active, "No campaigns yet. They appear here once you launch.", "hint");
        return;
      }
      for (const run of shown) campaignCard(active, run);
    });
  }
  // What a campaign card shows, as one key: it is redrawn only when this moves.
  function cardKey(run) {
    return [run.id, run.state, run.challenge ?? null, run.selects ?? null, run.attempted_experiments ?? 0, run.completed_experiments ?? 0, lastRefusal(run), graphiteLine(run)];
  }
  // A Graphite campaign's mode and stage, as its record states them.
  function graphiteLine(run) {
    const g = run?.graphite;
    if (!g || typeof g !== "object") return null;
    return "Graphite · " + graphiteMode(g.mode) + " mode · " + graphiteNow(g.stage, run.state);
  }
  // The campaign's last refusal (slice C's `last_refusal`): {code,
  // next_action, at, and, when given, the operation it was for and its kind
  // (refused, interrupted or paused)}, shown when present and well formed,
  // ignored otherwise.
  const REFUSAL_KINDS = {refused: "Refused", interrupted: "Interrupted", paused: "Paused"};
  function lastRefusal(...sources) {
    for (const source of sources) {
      const value = source?.last_refusal ?? source?.campaign?.last_refusal;
      if (value && typeof value === "object" && typeof value.code === "string" && value.code) {
        return {
          code: value.code.slice(0, 128),
          next_action: typeof value.next_action === "string" ? value.next_action.slice(0, 2000) : null,
          at: typeof value.at === "number" || typeof value.at === "string" ? value.at : null,
          operation: typeof value.operation === "string" && value.operation ? value.operation.slice(0, 32) : null,
          kind: typeof value.kind === "string" && Object.hasOwn(REFUSAL_KINDS, value.kind) ? value.kind : "refused",
        };
      }
    }
    return null;
  }
  function when(at) {
    if (typeof at === "number" && Number.isFinite(at)) return new Date((at > 1e12 ? at : at * 1000)).toLocaleString();
    if (typeof at === "string" && !Number.isNaN(Date.parse(at))) return new Date(at).toLocaleString();
    return null;
  }
  // Where a refusal's correction is taken, when this page has the place.
  function refusalFix(code) {
    if (/^signer_/.test(code)) return {label: "Check your signer", href: "#setup/signer"};
    if (/^registration_/.test(code)) return {label: "Check your registration", href: "#setup/register"};
    if (/^model_provider_|^model_selection_/.test(code)) return {label: "Set up inference", href: "#setup/inference"};
    if (/^research_profile_|^runner_profile_/.test(code)) return {label: "Continue setup", href: "#setup/review"};
    if (code === "evaluation_unavailable") return {label: "Review evaluation in setup", href: "#setup/review"};
    // Graphite's own (OWNER-GRAPHITE-MINER-01): where each is put right.
    if (code === "autonomous_agent_replaced") return {label: "Choose Graphite", href: "#launch"};
    if (code === "graphite_not_offered_for_challenge") return {label: "Choose a Challenge", href: "#challenges"};
    if (/^plan_(not_found|invalid)$/.test(code)) return {label: "Open your plans", href: "#library/plans"};
    if (/^card_(not_found|banned)$|^import_invalid$/.test(code)) return {label: "Open the Library", href: "#library"};
    if (code === "hunt_query_invalid") return {label: "Change the hunt", href: "#launch"};
    return null;
  }
  // The refusal as a person reads it: what was refused, when, and what to do.
  function refusalNote(parent, refusal, compact = false) {
    if (!refusal) return null;
    const box = el("div", undefined, "refusal-note");
    box.setAttribute("role", "status");
    const at = when(refusal.at);
    box.append(el("p", (REFUSAL_KINDS[refusal.kind] || "Refused") + ": " + words(refusal.code) + (refusal.operation ? " (" + words(refusal.operation) + ")" : "") + (at ? " · " + at : ""), "status-line"));
    if (refusal.next_action) box.append(el("p", (compact ? "" : "What to do: ") + refusal.next_action, compact ? "hint" : "refusal-next"));
    const fix = refusalFix(refusal.code);
    if (fix && !compact) box.append(link(fix, "button fix"));
    parent.append(box);
    return box;
  }
  function challengeLabel(run) {
    if (run.challenge) {
      const entry = challengeEntry({id: run.challenge.id, version: run.challenge.version});
      return (entry ? entry.title : run.challenge.id) + " · v" + run.challenge.version;
    }
    return run.selects ? "Recorded without a Challenge (historical DEVELOPMENT campaign)" : "Challenge not yet recorded";
  }
  function campaignCard(parent, run) {
    const box = el("a", undefined, "integration card campaign-card");
    box.href = campaignHref(run.id);
    box.dataset.campaign = run.id;
    const head = el("div", undefined, "card-head");
    head.append(el("h3", run.id.slice(0, 10)), el("span", run.state, "badge state-" + String(run.state).toLowerCase()));
    box.append(head);
    researchNote(box, challengeLabel(run));
    researchNote(box, (run.selects === "miner" ? "You select and submit" : run.selects === "agent" ? "Carbon's agent selects" : "Awaiting runtime") + " · Attempts: " + (run.attempted_experiments ?? 0) + " · Completed practice: " + (run.completed_experiments ?? 0), "hint");
    const graphite = graphiteLine(run);
    if (graphite) researchNote(box, graphite, "status-line graphite-line");
    refusalNote(box, lastRefusal(run), true);
    parent.append(box);
  }

  // ---- Catalog views: Challenges, Agents, Compute, Connections, Wallet. ----
  // Rebuilt only when what they show changes, so an open Details stays open.
  function renderCatalogs() {
    const views = ["challenge-catalog", "agent-catalog", "compute-catalog", "connection-catalog", "wallet-profile"];
    if (!connected || !caps) {
      for (const id of views) rebuild($(id), "disconnected", target => target.append(el("p", id === "wallet-profile" ? "" : "Connect to read this controller's capabilities.", "hint")));
      return;
    }
    const key = capsVersion + ":" + setupVersion;
    rebuild($("challenge-catalog"), key, renderChallengeCatalog);
    rebuild($("agent-catalog"), key, renderAgentCatalog);
    rebuild($("compute-catalog"), key, renderComputeCatalog);
    rebuild($("connection-catalog"), key, renderConnections);
    rebuild($("wallet-profile"), key, renderWallet);
  }
  function challengeStatus(entry) {
    return entry.status + (entry.selectable ? " · launchable" : "");
  }
  // The card's state in a word: ready, set up first, or why it never is here.
  function challengePill(entry) {
    if (entry.selectable) return ["Ready", "pill-done"];
    if (entry.implemented) return ["Set up first", "pill-need"];
    return [{RESERVED: "Reserved", DEFERRED: "Deferred", RETIRED: "Retired"}[entry.status] || words(entry.status), "pill-wait"];
  }
  function renderChallengeCatalog(target) {
    for (const entry of caps.challenges) {
      const [tag, kind] = challengePill(entry);
      const box = card(target, entry.title, tag, kind);
      box.dataset.challenge = entry.challenge_id;
      if (entry.selectable) {
        box.append(el("p", "Ready to launch.", "status-line"));
        const choose = el("button", "Use for a new campaign", "primary"); choose.type = "button";
        choose.addEventListener("click", () => { selectChallenge(entry); location.hash = "#launch"; });
        box.append(choose);
      } else {
        box.append(el("p", entry.plain?.sentence || "Unavailable: " + words(entry.reason) + ".", "status-line"));
        if (entry.plain?.next) box.append(link(entry.plain.next, "button fix"));
      }
      if (entry.implemented) {
        const description = details(box, "Description", []);
        renderDescription(description.querySelector(".detail-body"), entry);
      }
      details(box, "Details", [
        entry.challenge_id + (entry.version ? " · version " + entry.version : "") + " · " + words(entry.portfolio) + (entry.tracking ? " · " + entry.tracking : ""),
        "Status: " + challengeStatus(entry),
        entry.implemented ? "This host: " + (entry.usable_here ? "shows every requirement of " + entry.profile : "has not shown " + entry.missing_here.map(words).join(", ") + " (the launch still reads your profile's runtime)") : null,
        entry.reason ? "Code: " + entry.reason : null,
        entry.next_action ? "Next: " + entry.next_action : null,
      ]);
    }
  }
  function renderDescription(parent, entry) {
    // Straight from the Challenge's own registered description.
    const d = entry.description || {};
    const grid = el("dl", undefined, "review-grid");
    const row = (label, value) => { if (value === undefined || value === null || value === "") return; grid.append(el("dt", label), el("dd", value)); };
    row("Objective", d.task);
    row("Intended use", d.intended_use);
    const inputs = d.interface?.inputs || {};
    row("Inputs", Object.entries(inputs).map(([name, spec]) => name + " [" + (spec.bounds || []).join(", ") + "] " + (spec.unit || "")).join(" · "));
    const outputs = d.interface?.outputs || {};
    row("Outputs", Object.entries(outputs).map(([name, spec]) => name + " " + JSON.stringify(spec.shape ?? []) + " " + (spec.unit || "") + (spec.grid ? " (" + spec.grid + ")" : "") + (spec.meaning ? " (" + spec.meaning + ")" : "")).join(" · "));
    const material = d.public_material || {};
    row("Public data", [(material.names || []).join(", "), material.train ? "TRAIN " + material.train.version + ": " + material.train.cases + " cases" : "", material.practice ? "PRACTICE: " + material.practice.cases + " cases" : ""].filter(Boolean).join(" · "));
    row("Never disclosed", (material.never_disclosed || []).join("; "));
    row("Tools", Object.entries(entry.tools?.workflow || {}).map(([name, detail]) => name + ": " + detail).join(" · "));
    row("Rebuildable models", (entry.tools?.rebuildable_models || []).join(", "));
    row("Practice metrics", [d.feedback?.practice, d.exam?.components ? "components: " + d.exam.components.join(", ") : ""].filter(Boolean).join(" · "));
    row("Exam gates", (d.exam?.gates || []).join(", "));
    row("Submission", [d.prediction_contract?.produced_by, d.workflow?.freeze, d.workflow?.submit].filter(Boolean).join(" · "));
    row("Reconstruction", d.exclusion_scope?.submission);
    row("Exam version", "version " + entry.version + (d.contract_digest ? " · contract " + d.contract_digest : "") + (d.exam?.rule?.status ? " · " + words(d.exam.rule.status) : ""));
    row("Limits", Object.entries(entry.tools?.limits || {}).map(([name, detail]) => name + ": " + (typeof detail === "object" ? JSON.stringify(detail) : detail)).join(" · "));
    row("Authority", d.authority);
    // What the Challenge gives a miner to research with, and what setup can
    // prepare for it (C-MLP-04): every Challenge reports the same way.
    if (entry.provisions && !entry.provisions.retired) {
      row("Research environment", Object.entries(entry.provisions).map(([name, state]) => name + (state.status === "gap" ? ": gap (" + state.reason + ")" : ": provided")).join(" · "));
    }
    const offers = entry.setup_offers || {};
    row("Setup offers", [offers.gpu ? "GPU practice on your machine" : "", offers.remote_gpu ? "GPU practice on your own remote machine or container" : "", offers.intake ? "submission to a remote validator's intake" : "", offers.feedback_modes?.length ? "feedback modes: " + offers.feedback_modes.join(", ") : ""].filter(Boolean).join(" · "));
    parent.append(grid);
  }
  const readiness = item => item.availability === "available" ? ["Ready", "pill-done"] : ["Needs setup", "pill-need"];
  function renderAgentCatalog(target) {
    for (const choice of agentChoices()) {
      const box = card(target, choice.label, ...readiness(choice));
      box.dataset.agent = choice.id;
      box.append(el("p", choice.summary, "hint"));
      if (choice.command && choice.availability === "available") copyRow(box, "Connect your client with:", choice.command);
      if (choice.launch_agent === GRAPHITE) {
        box.append(el("p", "Modes: Research, Build or Full. It reads the shared card pack and your own Library, and can hunt arXiv for more, on your model and budget.", "hint"));
        box.append(link({label: "Open the Library", href: "#library"}));
      }
      if (choice.availability !== "available") unavailableNote(box, choice);
    }
    // The autonomous agent, once Graphite replaced it: said, never offered,
    // whether or not the controller still lists it.
    if (autonomousReplaced()) {
      const box = card(target, "Carbon's autonomous research agent", "Replaced", "pill-wait");
      box.dataset.agent = "replaced";
      box.append(el("p", "Replaced by Graphite for new campaigns (autonomous agent replaced). Campaigns launched with it keep running, and their records replay unchanged.", "status-line"));
    }
    // Model providers in one card: a row each, the fix beside the ones that
    // need it, every credential and code behind Details.
    const providers = card(target, "Model providers", "Used by Carbon's agent");
    const rows = el("ul", undefined, "checklist");
    for (const provider of caps.model.providers) {
      const entry = el("li", undefined, provider.availability === "available" ? "ok" : "missing");
      entry.append(pill(...readiness(provider)), el("span", provider.provider));
      if (provider.availability !== "available") {
        entry.append(el("span", provider.plain?.sentence || words(provider.reason) + ".", "next"));
        if (provider.plain?.next) entry.append(link(provider.plain.next));
      }
      details(entry, "Details", [
        "Models: " + provider.models.map(model => model.id).join(", ") + " · used by Carbon's own agent only",
        "Credential: " + provider.credential.reference + " · " + (provider.credential.configured === null ? provider.credential.basis : provider.credential.configured ? "configured" : "not configured") + " · held by " + provider.credential.held_by,
        provider.reason ? "Code: " + provider.reason : null,
        provider.next_action ? "Next: " + provider.next_action : null,
      ]);
      rows.append(entry);
    }
    providers.append(rows);
    for (const item of [...caps.agents.unavailable, ...caps.model.unavailable]) unavailableNote(card(target, words(item.id), "Not offered", "pill-wait"), item);
  }
  // Where research runs, side by side (LINKONLY-D10): this machine, and a GPU
  // the miner runs elsewhere, each with its state and the place to set it.
  function renderComputeCatalog(target) {
    const routes = caps.compute.routes || [];
    const choice = computeChoice();
    const checked = setupState?.steps?.compute;
    for (const route of routes) {
      if (route.id === "this-machine") {
        const [tag, kind] = route.availability === "available" ? [route.in_use ? "In use" : "Ready", "pill-done"] : ["Needs setup", "pill-need"];
        const box = card(target, route.label, tag, kind);
        const facts = choice ? [
          "Lanes: " + Object.entries(choice.lanes).map(([lane, state]) => lane + " " + state.availability + (state.reason ? " (" + words(state.reason) + ")" : "")).join(" · "),
          caps.compute.selection,
          "Host facts: " + (choice.host_facts || []).join(", "),
        ] : [];
        if (route.availability === "available") {
          box.append(el("p", "Practice runs in an isolated container here, on the " + route.lane.toUpperCase() + ".", "status-line"));
          details(box, "Details", facts);
        } else unavailableNote(box, route, facts);
        continue;
      }
      const set = route.availability === "configured";
      const box = card(target, route.label, set ? "In use" : "Not set up", set ? "pill-done" : "pill-wait");
      if (set) box.append(el("p", "In your profile: " + route.transport + ", over your own SSH.", "status-line"));
      else if (checked?.checked && checked.remote_machine) box.append(el("p", "Checked over your SSH: " + checked.remote_machine.destination + " (" + checked.remote_machine.transport + "). Write your profile to use it.", "status-line"));
      else box.append(el("p", "Use a GPU you run anywhere: RunPod, Lium, Targon, Vast.ai, Lambda or your own server, reached with your own SSH.", "status-line"));
      box.append(el("p", "You start, stop and pay for it. Carbon never does.", "hint"));
      const go = checked?.checked && checked.remote_machine && !set ? {label: "Write your profile", href: "#setup/review"} : route.plain.next;
      box.append(link(go, set ? "button fix" : "button primary"));
      details(box, "Details", ["Started, stopped and billed by: " + route.started_stopped_and_billed_by, set ? "Transport: " + route.transport : null]);
    }
    for (const item of caps.compute.unavailable) unavailableNote(card(target, words(item.id), "Not offered", "pill-wait"), item);
  }
  function renderConnections(target) {
    const mcp = agentEntry("external_mcp");
    if (mcp) {
      const box = card(target, "Your own MCP client · stdio", ...readiness(mcp));
      box.append(el("p", "Run on this machine with your runner profile. Every operation - launch, observe, practice, freeze, submit, halt, resume - is the same one this page calls, over the same records. Nothing is issued by Carbon.", "hint"));
      copyRow(box, "Connect your client with:", mcp.command, "connection-mcp-copy");
      // The command names this controller's own runner profile when it has
      // one (LP-PROD-F); otherwise it says where that path comes from.
      if (mcp.profile_path) researchNote(box, "Your runner profile: " + mcp.profile_path + ". The command above names it; your client starts the server with it.", "hint");
      else researchNote(box, "Replace <your runner profile> with your runner profile's path: Set up writes it, and this page shows it here once a profile is loaded.", "hint");
      if (mcp.client_configuration) details(box, "Client configuration (JSON)", [el("pre", JSON.stringify(mcp.client_configuration, null, 2))]);
      if (mcp.availability !== "available") unavailableNote(box, mcp);
    }
    for (const item of caps.connections) unavailableNote(card(target, words(item.id), "Not offered", "pill-wait"), item);
  }
  function renderWallet(target) {
    const box = card(target, "Research identity", ...(caps.profile.configured ? ["Ready", "pill-done"] : ["Needs setup", "pill-need"]));
    if (caps.profile.configured) {
      box.append(el("p", "Your runner profile is loaded. Your registered miner is read from it at launch; signing stays in your own wallet.", "status-line"));
      details(box, "Details", ["Runner profile " + caps.profile.profile_id]);
    } else unavailableNote(box, caps.profile);
    // Registration is the miner's own transaction: said here, with no link
    // back to this same page.
    for (const item of caps.wallet) {
      const entry = card(target, "Registration", "Your wallet", "pill-dev");
      entry.append(el("p", item.plain?.sentence || words(item.reason) + ".", "status-line"));
      details(entry, "Details", ["Code: " + item.reason, "Next: " + item.next_action]);
    }
  }

  // ---- Campaigns: list, deep-linked detail and tabs. ----
  function renderCampaigns() {
    const list = $("research-runs");
    const current = route();
    const detail = $("campaign-detail");
    // Read what is open now, before anything is rebuilt. The toggle event is
    // asynchronous, so a miner's click that lands just before a live refresh
    // would otherwise fire on a replaced element and be lost.
    for (const node of detail.querySelectorAll("details[data-research-run]")) {
      if (node.open) expandedResearch.add(node.dataset.researchRun); else expandedResearch.delete(node.dataset.researchRun);
    }
    const run = current.view === "campaigns" && current.id ? research.runs.find(r => r.id === current.id) : null;
    list.hidden = Boolean(run);
    detail.hidden = !run && !(current.view === "campaigns" && current.id);
    rebuild(list, JSON.stringify([connected, research.runs.map(cardKey), capsVersion]), target => {
      if (!connected) researchNote(target, "Reconnect to reconcile research state. Controls are disabled.", "hint");
      else if (!research.runs.length) {
        const empty = el("div", undefined, "empty");
        empty.append(el("h3", "No campaign yet."), el("p", "New campaign walks you through Challenge, agent, model, compute, tools and limits."));
        target.append(empty);
      }
      for (const item of research.runs) campaignCard(target, item);
    });
    if (current.view === "campaigns" && current.id && !run) {
      rebuild(detail, "missing|" + current.id + "|" + connected, target => {
        // The research surface's campaign frame is gone with it.
        delete target.dataset.frame;
        target.append(el("p", connected ? "No campaign " + current.id + " on this controller." : "Reconnect to open this campaign.", "hint"));
      });
      return;
    }
    if (!run) return;
    // The research surface draws the campaign from its campaign view, the
    // document an MCP client reads too (OWNER-MINER-RESEARCH-SURFACE-01).
    if (window.CarbonResearch) { window.CarbonResearch.detail(detail, run); return; }
    // Never rebuild under a person's cursor: the journey is typed into.
    const active = document.activeElement;
    if (active && detail.contains(active) && ["INPUT", "TEXTAREA", "SELECT"].includes(active.tagName) && detail.dataset.run === run.id) return;
    detail.dataset.run = run.id;
    detail.replaceChildren();
    const back = el("a", "← All campaigns", "inline-link"); back.href = "#campaigns";
    const head = el("div", undefined, "run-top");
    const title = el("div");
    title.append(el("p", "CAMPAIGN · " + challengeLabel(run), "eyebrow"), el("code", run.id));
    head.append(title, el("span", run.state, "badge state-" + String(run.state).toLowerCase()));
    const controls = document.createElement("div"); controls.className = "controls sticky-controls";
    for (const action of ["pause", "resume", "stop", "reconcile", "export"]) {
      const button = document.createElement("button"); button.type = "button"; button.textContent = action; button.dataset.action = action;
      // A disabled control says why, rather than leaving the miner to guess.
      const reason = !connected ? "Reconnect this browser first."
        : busy ? "Another request is in progress."
        : action === "resume" && !research.preflight.available ? "Resume needs a configured runner profile."
        : action !== "export" && ["COMPLETED", "STOPPED", "READBACK_UNAVAILABLE"].includes(run.state) ? "This campaign is " + run.state + "; there is nothing left to " + action + ". Export still gives its full record."
        : "";
      button.disabled = Boolean(reason);
      if (reason) button.title = reason;
      button.addEventListener("click", () => researchAction(run.id, action)); controls.append(button);
    }
    const tabs = el("nav", undefined, "tabs"); tabs.setAttribute("aria-label", "Campaign sections");
    for (const [name, label] of TABS) {
      const link = el("a", label); link.href = "#campaigns/" + encodeURIComponent(run.id) + "/" + name;
      if (name === current.tab) link.setAttribute("aria-current", "page");
      tabs.append(link);
    }
    detail.append(back, head, controls, tabs);
    const panels = {};
    for (const [name] of TABS) { panels[name] = el("section", undefined, "tab-panel"); panels[name].dataset.tab = name; panels[name].hidden = name !== current.tab; detail.append(panels[name]); }
    tabOverview(panels.overview, run);
    tabExperiments(panels.experiments, run);
    tabMetrics(panels.metrics, run);
    tabJournal(panels.journal, run);
    tabArtifacts(panels.artifacts, run);
    tabSubmission(panels.submission, run);
    tabLogs(panels.logs, run);
    tabSettings(panels.settings, run);
  }
  function missing(parent, text) { researchNote(parent, "Not yet available: " + text, "empty-state"); }
  function tabOverview(panel, run) {
    researchNote(panel, (run.agent || "Awaiting runtime") + " / " + (run.reasoning || "unavailable") + " / " + (run.compute || "unavailable") + " · Attempts: " + (run.attempted_experiments ?? 0) + " · Completed practice: " + (run.completed_experiments ?? 0));
    if (run.execution_label) researchNote(panel, run.execution_label, "hint");
    if (run.deadline_unix) researchNote(panel, "Deadline from your elapsed limit: " + new Date(run.deadline_unix * 1000).toLocaleString());
    else researchNote(panel, "No deadline: you set no elapsed limit.", "hint");
    if (run.research_guidance) {
      const task = document.createElement("p"); task.className = "frozen-guidance";
      task.textContent = "Frozen research task: " + run.research_guidance.text;
      panel.append(task);
      researchNote(panel, "Task identity: " + run.research_guidance.digest);
    }
    if (run.current_hypothesis) researchNote(panel, "Research hypothesis: " + (run.current_hypothesis.hypothesis || "unavailable"));
    const current = (run.operations || []).filter(op => op.state === "RESERVED");
    researchNote(panel, current.length ? "Active reserved operations: " + current.map(op => op.phase + " / " + op.id).join(", ") : "No active reserved operation reported.");
    if (run.usage) {
      const usage = document.createElement("div"); usage.className = "research-usage";
      for (const kind of ["available", "reserved", "reported", "uncertain"]) {
        const amount = run.usage[kind]?.provider_nanodollars;
        researchNote(usage, kind + ": " + (Number.isFinite(amount) ? "$" + (amount / 1e9).toFixed(8) : "unavailable"));
      }
      panel.append(usage);
      researchNote(panel, run.usage.cost_basis || "Cost basis unavailable.");
    } else missing(panel, "usage appears once the campaign ledger exists.");
    const results = run.final_results || [];
    researchNote(panel, results.length ? "Independent DEVELOPMENT results: " + results.length + " (see Submission)" : "No independent DEVELOPMENT result yet.", "development-summary");
  }
  function tabExperiments(panel, run) {
    if (run.selects === "miner") renderJourneyPractice(panel, run);
    const experiments = run.experiments || [];
    experiments.forEach((experiment, index) => renderPractice(panel, experiment, index));
    if (!experiments.length) missing(panel, "no practice experiment has completed in this campaign.");
  }
  // A campaign's ledger usage, every column in the unit its limit is set in
  // (USD, minutes, MB; counts as counts), so spend reads beside its limit
  // (LP-PROD-F). Shared by this page and the research surface's Logs tab.
  function usageTable(parent, usage) {
    const table = el("table", undefined, "metrics-table");
    const header = el("tr"); for (const name of ["Resource", "Your limit", "Reported", "Reserved", "Uncertain"]) header.append(el("th", name));
    table.append(header);
    const budget = usage.budget || {};
    const amount = (name, value) => typeof value === "number" ? resourceValue(name, value) : "–";
    for (const name of Object.keys(usage.reported || {})) {
      const row = el("tr");
      const cap = budget.ceilings ? budget.ceilings[name] : budget[name];
      row.append(el("td", resourceName(name)), el("td", cap === undefined || cap === null ? "No limit" : resourceValue(name, cap)), el("td", amount(name, usage.reported[name])), el("td", amount(name, usage.reserved?.[name])), el("td", amount(name, usage.uncertain?.[name])));
      table.append(row);
    }
    const wrap = el("div", undefined, "table-wrap"); wrap.append(table); parent.append(wrap);
    researchNote(parent, "Shown in USD, minutes and MB; the ledger counts whole nanodollars, milliseconds and bytes.", "hint");
  }
  function tabMetrics(panel, run) {
    if (!run.usage) { missing(panel, "resource metrics appear once the campaign ledger exists."); return; }
    usageTable(panel, run.usage);
    const scores = (run.experiments || []).map((experiment, index) => "#" + (index + 1) + ": " + (experiment.diagnostics?.descriptive_score ?? experiment.summary?.score ?? "unavailable"));
    researchNote(panel, scores.length ? "Descriptive practice scores (not accepted improvements): " + scores.join(" · ") : "No practice score yet.");
  }
  function tabJournal(panel, run) {
    const hypotheses = run.hypotheses || [];
    const decisions = run.decisions || [];
    for (const item of hypotheses) researchNote(panel, "Hypothesis " + (item.sequence ?? "") + ": " + (item.hypothesis || JSON.stringify(item)));
    for (const item of decisions) researchNote(panel, "Decision " + (item.sequence ?? "") + ": " + JSON.stringify(item));
    for (const item of run.capability_requests || []) researchNote(panel, "Capability request (grants nothing): " + JSON.stringify(item));
    for (const item of run.refusals || []) researchNote(panel, "Refused request (nothing ran): " + JSON.stringify(item));
    for (const outcome of run.epoch_outcomes || []) researchNote(panel, (outcome.selected_by === "miner" ? "Your" : "Agent") + " epoch " + outcome.epoch + ": " + outcome.status + " · " + (outcome.reason || "No reason reported") + " · " + (outcome.selected_by === "miner" ? "Your" : "Agent-reported") + " decision, not independent science.");
    if (!hypotheses.length && !decisions.length && !(run.epoch_outcomes || []).length) missing(panel, "the journal fills as hypotheses, decisions and epoch outcomes are recorded.");
  }
  function tabArtifacts(panel, run) {
    const freezes = run.candidate_freezes || [];
    for (const item of freezes) researchNote(panel, "Frozen candidate: " + JSON.stringify(item));
    const recipes = (run.experiments || []).filter(experiment => experiment.recipe).map(experiment => JSON.stringify(experiment.recipe));
    for (const text of [...new Set(recipes)]) researchNote(panel, "Practiced recipe: " + text, "code");
    if (!freezes.length && !recipes.length) missing(panel, "the controller does not expose trained weights or files; recipes and frozen candidates appear here once recorded.");
    researchNote(panel, "Export gives the full public record of this campaign as JSON.", "hint");
  }
  function renderValidatorOutcome(panel, result) {
    const o = result.result;
    const s = o.screening;
    const cases = s && s.cases && typeof s.cases === "object" ? Object.entries(s.cases).map(([k, v]) => words(k) + " " + v).join(", ") : "unavailable";
    const lines = [
      "Validator outcome, epoch " + result.epoch + ": " + o.state + (o.waiting ? " · waiting: " + o.waiting : ""),
      "Submission: " + (o.submission_id || "unavailable"),
      s ? "Screening on pool version " + (s.pool_version ?? "?") + ": " + (s.eligible === true ? "eligible" : s.eligible === false ? "not eligible" : "eligibility unavailable") + " · gates failed: " + ((s.gates_failed || []).join(", ") || "none") + " · cases: " + cases : "Screening: not shown in this feedback mode.",
      s && typeof s.score === "number" ? "Score: " + s.score + (typeof s.important_score === "number" ? " · important region: " + s.important_score : "") : "Score: not shown in this feedback mode.",
      "Nominated for a final: " + (o.nominated === true ? "yes" : o.nominated === false ? "no" : "unavailable") + ((o.finals || []).length ? " · finals: " + o.finals.map(f => f.state + (f.promoted ? " (promoted)" : "")).join(", ") : ""),
      (o.evidence || "DEVELOPMENT") + ": no qualification, no reward, no chain write.",
    ];
    for (const line of lines) researchNote(panel, line, "development-result");
  }
  function tabSubmission(panel, run) {
    if (run.selects === "miner") renderJourneySubmission(panel, run);
    else if (run.selects === "agent") researchNote(panel, "Carbon's agent freezes and submits in this campaign.", "hint");
    for (const result of run.final_results || []) {
      if (result.status === "VALIDATOR_OUTCOME" && result.result) { renderValidatorOutcome(panel, result); continue; }
      const verified = result.status === "VERIFIED_SOURCE" && result.result;
      researchNote(panel, "DEVELOPMENT evaluation: " + (verified ? (result.result.disposition || "disposition unavailable") + " · Accepted DEVELOPMENT improvement: " + (typeof result.result.accepted_development_improvement === "boolean" ? String(result.result.accepted_development_improvement) : "unavailable") : "Readback unavailable; no disposition inferred."), "development-result");
    }
    if (!(run.final_results || []).length) researchNote(panel, "DEVELOPMENT evaluation: no independent result available.", "development-result");
  }
  function tabLogs(panel, run) {
    const operations = run.operations || [];
    for (const op of operations) researchNote(panel, op.phase + " · " + op.state + " · " + op.id, "code");
    const held = operations.filter(op => op.state === "HELD");
    if (held.length) researchNote(panel, "Held capacity, never dispatched: " + held.map(op => op.phase + " / " + op.id).join(", "));
    if (!operations.length) missing(panel, "no operation has been recorded.");
    researchNote(panel, "Provider payloads, worker output and errors stay private to the campaign; the controller exposes operation states only.", "hint");
  }
  function tabSettings(panel, run) {
    const grid = el("dl", undefined, "review-grid");
    const row = (label, value) => grid.append(el("dt", label), el("dd", value));
    row("Challenge", challengeLabel(run));
    row("Profile", run.profile || "unavailable");
    row("Runtime revision", run.runtime_revision || "unavailable");
    row("Your budget", run.usage ? (Object.keys(run.usage.budget || {}).length ? JSON.stringify(run.usage.budget) : "none: no limit") : "unavailable");
    row("Admission", words(run.admission || "unavailable"));
    panel.append(grid);
    const details = document.createElement("details"); const summary = document.createElement("summary"); summary.textContent = "Research, usage, candidate and independent result";
    details.dataset.researchRun = run.id;
    details.open = expandedResearch.has(run.id);
    details.addEventListener("toggle", () => { if (details.isConnected) { if (details.open) expandedResearch.add(run.id); else expandedResearch.delete(run.id); } });
    const record = document.createElement("pre"); record.style.whiteSpace = "pre-wrap"; record.style.overflowWrap = "anywhere";
    record.textContent = JSON.stringify({challenge: run.challenge, runtime_revision: run.runtime_revision, agent_policy: run.agent_policy, research_guidance: run.research_guidance, effective_research_inputs: run.effective_research_inputs, hypothesis: run.current_hypothesis, hypotheses: run.hypotheses, decisions: run.decisions, outcomes: run.epoch_outcomes, usage: run.usage, experiments: run.experiments, operations: run.operations, freezes: run.candidate_freezes, development: run.final_results, capability_requests: run.capability_requests, refusals: run.refusals}, null, 2);
    details.append(summary, record); panel.append(details);
  }
  // A Challenge's own practice feedback (battery's summary, fit and backend),
  // as recorded; a field it does not report is shown as unavailable.
  // One Challenge's own model families (its construction contract), or the
  // historical list when the controller predates the per-Challenge field.
  function familiesFor(challengeId) {
    const by = launchOptions && launchOptions.families_by_challenge;
    return (by && challengeId && by[challengeId]) || (launchOptions ? launchOptions.families : []);
  }
  function renderChallengePractice(section, experiment) {
    const s = experiment.summary, fit = experiment.fit || {}, backend = experiment.backend || {};
    const num = v => typeof v === "number" && Number.isFinite(v) ? String(v) : "unavailable";
    researchNote(section, "Recipe: " + (experiment.backbone || experiment.recipe?.backbone || "unavailable") + (experiment.recipe?.parameters ? " · " + JSON.stringify(experiment.recipe.parameters) : ""), "code");
    researchNote(section, "Descriptive practice score: " + num(s.score) + " · important region: " + num(s.important_score) + " · lower is better · Not an accepted improvement.");
    const failures = s.gate_failures && typeof s.gate_failures === "object" ? Object.entries(s.gate_failures).filter(([, v]) => v).map(([k, v]) => k + " " + v) : [];
    researchNote(section, "Practice gates: " + (s.eligible === true ? "all passed" : s.eligible === false ? "failed · " + (failures.join(", ") || "gate counts unavailable") : "unavailable") + " · final admissibility is separate.");
    researchNote(section, "Cases: " + num(s.n_scored) + " scored of " + num(s.n_cases) + " · " + num(s.n_reference_invalid) + " reference invalid · " + num(s.n_failed_infra) + " infrastructure failed");
    researchNote(section, "Training: final loss " + num(fit.final_loss) + " · " + num(fit.n_params) + " parameters · " + num(fit.train_s) + " s training · backend " + (backend.kind || "unavailable"));
  }
  function renderPractice(parent, experiment, index) {
    const section = document.createElement("section"); section.className = "practice-result";
    const heading = document.createElement("h4"); heading.textContent = "Practice experiment " + (index + 1); section.append(heading);
    if (experiment.summary && typeof experiment.summary === "object") { renderChallengePractice(section, experiment); parent.append(section); return; }
    researchNote(section, "Completed updates: " + experiment.completed_steps + " · Worker seconds: " + experiment.worker_seconds);
    const diagnostics = experiment.diagnostics || {};
    researchNote(section, "Descriptive practice score: " + (diagnostics.descriptive_score ?? "unavailable") + " · Not an accepted improvement.");
    const failures = diagnostics.sampled_gate_failures;
    researchNote(section, Array.isArray(failures) ? "Sampled gate failures: " + (failures.length ? failures.join(", ") : "none reported; final admissibility is separate") : "Sampled gate failures unavailable.");
    const points = experiment.inline_curve;
    if (Array.isArray(points) && points.length >= 2 && points.length <= 8 && points.every((p, i) => p && Number.isFinite(p.step) && Number.isFinite(p.data_loss) && p.data_loss >= 0 && (!i || p.step > points[i - 1].step))) {
      const first = points[0], last = points[points.length - 1];
      const maximum = Math.max(...points.map(p => p.data_loss)) || 1;
      const ns = "http://www.w3.org/2000/svg";
      const svg = document.createElementNS(ns, "svg");
      svg.setAttribute("viewBox", "0 0 480 190"); svg.setAttribute("role", "img");
      svg.setAttribute("aria-label", "Sampled training data loss by optimizer update, not a physical field or final evaluation");
      const add = (name, attributes, text) => {
        const node = document.createElementNS(ns, name);
        for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
        if (text !== undefined) node.textContent = text;
        svg.append(node);
      };
      const x = p => 65 + 395 * (p.step - first.step) / (last.step - first.step);
      const y = p => 145 - 125 * p.data_loss / maximum;
      for (const fraction of [0, 0.5, 1]) {
        const at = 145 - fraction * 125;
        add("line", {x1: 65, y1: at, x2: 460, y2: at, class: "curve-grid"});
        add("text", {x: 58, y: at + 4, "text-anchor": "end"}, (maximum * fraction).toPrecision(3));
      }
      add("polyline", {points: points.map(p => x(p) + "," + y(p)).join(" "), class: "curve-line"});
      for (const p of points) add("circle", {cx: x(p), cy: y(p), r: 3, class: "curve-point"});
      add("text", {x: 65, y: 164}, String(first.step));
      add("text", {x: 460, y: 164, "text-anchor": "end"}, String(last.step));
      add("text", {x: 265, y: 184, "text-anchor": "middle"}, "Optimizer update");
      section.append(svg);
      researchNote(section, "Training data loss · " + points.length + " recorded samples, joined for readability. First: " + first.data_loss + "; last: " + last.data_loss + ". Full projected samples remain in the record under Settings.");
    } else researchNote(section, "Training curve unavailable; no measurements inferred.");
    parent.append(section);
  }
  function draft(id, field, fallback) {
    const key = id + ":" + field;
    return key in journeyDrafts ? journeyDrafts[key] : fallback;
  }
  function journeyField(parent, id, field, labelText, element, fallback) {
    const label = document.createElement("label"); label.textContent = labelText;
    element.id = "journey-" + field + "-" + id; label.htmlFor = element.id;
    element.value = draft(id, field, fallback);
    // Kept as a draft across reloads and redraws, so it never holds its region.
    element.dataset.draft = "1";
    element.addEventListener("input", () => { journeyDrafts[id + ":" + field] = element.value; store(draftKey, journeyDrafts); });
    parent.append(label, element);
    return element;
  }
  // The example recipe for a campaign's own Challenge, from its registered
  // description (validated by the same admission a submission meets). A
  // campaign recorded without a Challenge is the historical DEVELOPMENT one.
  function exampleRecipe(run) {
    const entry = run.challenge
      ? challengeEntry({id: run.challenge.id, version: run.challenge.version})
      : caps?.challenges.find(item => item.portfolio === "historical_development");
    return entry?.example_strategy ? JSON.stringify(entry.example_strategy, null, 2) : "";
  }
  function journeyState(run) {
    const journey = run.journey || {};
    return {journey, frozen: journey.frozen_awaiting_submission === true, exhausted: journey.final_exams_remaining === 0, ready: run.state === "READY"};
  }
  function practicedRecipes(run) {
    const practiced = [];
    for (const experiment of run.experiments || []) {
      if (!experiment.recipe) continue;
      const text = JSON.stringify(experiment.recipe);
      if (!practiced.includes(text)) practiced.push(text);
    }
    return practiced;
  }
  function renderJourneyPractice(parent, run) {
    // A person's own journey, with no Carbon agent: practice, freeze, submit.
    // Each step is an operation from the same table the agent and MCP use.
    const box = document.createElement("div"); box.className = "journey"; box.id = "journey-" + run.id;
    box.append(el("h4", "Your research · no Carbon agent"));
    researchNote(box, "1 · Practice a recipe here. 2 · Freeze one you practiced and 3 · submit it under Submission. Nothing reaches the chain.");
    const {journey, exhausted, ready} = journeyState(run);
    const example = exampleRecipe(run);
    const recipe = journeyField(box, run.id, "recipe", "Recipe to practice (JSON)", document.createElement("textarea"), example);
    recipe.rows = 8; recipe.className = "research-guidance";
    if (example) researchNote(box, "Prefilled with this Challenge's registered example, which passes admission. Edit it freely.", "hint");
    else researchNote(box, "No registered example for this campaign's Challenge; write a recipe.", "hint");
    const hypothesis = journeyField(box, run.id, "hypothesis", "What this trial tests", document.createElement("input"), "");
    if (!ready) researchNote(box, "Working: " + String(run.state).replaceAll("_", " ").toLowerCase() + ". The next step opens when the campaign is ready.");
    researchNote(box, "Final exams remaining: " + (journey.final_exams_remaining ?? "unavailable"));
    const buttons = document.createElement("div"); buttons.className = "controls";
    const practice = document.createElement("button"); practice.type = "button"; practice.id = "journey-practice-" + run.id; practice.textContent = "Run practice trial";
    practice.disabled = !connected || busy || !ready || exhausted;
    practice.addEventListener("click", () => {
      let strategy;
      try { strategy = JSON.parse(recipe.value); } catch (_) { message("The recipe is not valid JSON.", true); return; }
      operate("practice", {campaign: run.id, strategy, hypothesis: hypothesis.value || "practice"}, "Practice trial started. Its result appears under Experiments when training finishes.");
    });
    buttons.append(practice); box.append(buttons);
    operationLine(box, run, ["practice"]);
    if (launchOptions) {
      // Each family's true availability now, by its registry verdict.
      const byVerdict = {};
      for (const family of familiesFor(run.challenge && run.challenge.id)) (byVerdict[family.verdict] ||= []).push(family.selector || family.id.split(".")[1]);
      const labels = {supported: "Families you can freeze and submit now", not_yet_rebuildable: "Not yet rebuildable (research only)", needs_owner_decision: "Waiting on an owner decision", excluded: "Excluded"};
      for (const [verdict, label] of Object.entries(labels)) if (byVerdict[verdict]) researchNote(box, label + ": " + byVerdict[verdict].join(", "));
    }
    parent.append(box);
  }
  function renderJourneySubmission(parent, run) {
    const box = document.createElement("div"); box.className = "journey-submit";
    box.append(el("h4", "Freeze and submit"));
    const {journey, frozen, exhausted, ready} = journeyState(run);
    const practiced = practicedRecipes(run);
    researchNote(box, "Final exams remaining: " + (journey.final_exams_remaining ?? "unavailable") + " · Submitted epochs: " + ((journey.submitted_epochs || []).join(", ") || "none") + (frozen ? " · A frozen candidate is waiting for submission." : ""));
    const choose = document.createElement("select");
    for (const text of practiced) { const option = document.createElement("option"); option.value = text; option.textContent = text; choose.append(option); }
    journeyField(box, run.id, "candidate", "Practiced recipe to freeze", choose, practiced[0] || "");
    const reason = journeyField(box, run.id, "reason", "Why this candidate", document.createElement("input"), "");
    if (!practiced.length) researchNote(box, "No practiced recipe yet: a candidate must have a practice result before it can be frozen. Practice under Experiments.", "reason");
    const second = document.createElement("div"); second.className = "controls";
    const freeze = document.createElement("button"); freeze.type = "button"; freeze.id = "journey-freeze-" + run.id; freeze.textContent = "Freeze candidate";
    freeze.disabled = !connected || busy || !ready || !practiced.length || frozen || exhausted;
    // Said as started, not as done: the record says when it is done.
    freeze.addEventListener("click", () => operate("freeze_candidate", {campaign: run.id, strategy: JSON.parse(choose.value), reason: reason.value || "practiced"}, "Freezing your candidate. It shows here once the campaign records it."));
    const submit = document.createElement("button"); submit.type = "button"; submit.id = "journey-submit-" + run.id; submit.textContent = "Submit frozen candidate";
    submit.disabled = !connected || busy || !ready || !frozen;
    submit.addEventListener("click", () => operate("submit", {campaign: run.id}, "Submit started: your registration is read, then your frozen candidate is sent for the DEVELOPMENT comparison. Whether it was admitted shows here."));
    second.append(freeze, submit); box.append(second);
    evaluationNote(box, run);
    operationLine(box, run, ["freeze_candidate", "submit"]);
    parent.append(box);
  }
  // Whether this campaign's frozen candidate can be evaluated today, from the
  // prelaunch review's evaluation_endpoints (LP-PROD-E): configuration only,
  // stated before a submit rather than learnt from its refusal. Said plainly,
  // with what still works and the next step (LAUNCHPAD-PAGE-USABILITY-01).
  function evaluationOf(id) {
    const items = research.preflight?.review?.evaluation_endpoints?.challenges;
    if (!Array.isArray(items) || typeof id !== "string") return null;
    return items.find(item => item && item.challenge_id === id) || null;
  }
  function evaluationFor(run) { return evaluationOf(run?.challenge?.id); }
  function evaluationNote(parent, run) {
    const item = evaluationFor(run);
    if (!item || EVALUABLE.includes(item.status)) return;
    const note = el("div", undefined, "evaluation-unavailable"); note.dataset.evaluation = item.status;
    note.append(el("p", "Evaluation is unavailable for this Challenge today: no validator intake is configured in your runner profile" + (item.status === "NONE_PUBLISHED" ? ", and none is published for it yet" : "") + ". Submit is refused as evaluation unavailable, and a frozen candidate is kept.", "reason"));
    note.append(el("p", "What you can do now: practise, observe, freeze a candidate, and stop or pause this campaign.", "hint"));
    if (typeof item.next_step === "string" && item.next_step) note.append(el("p", "Next: " + item.next_step, "hint"));
    const link = el("a", "Review evaluation in setup"); link.href = "#setup/review";
    note.append(link);
    parent.append(note);
  }
  // The line under a journey's buttons: what the last operation is doing, or
  // how it ended, from the campaign's own record.
  function operationLine(parent, run, names) {
    const entry = watches.get(run.id);
    const status = entry && names.includes(entry.name) ? watchStatus(run) : null;
    if (status) {
      const line = el("p", status.text, status.kind === "refused" ? "reason" : "status-line");
      line.dataset.operation = status.kind;
      line.setAttribute("role", "status");
      parent.append(line);
    }
    // A request whose answer was lost is held under its key until the record
    // shows how it ended; the miner can let it go (LP-PROD-F).
    const held = heldOperation(run.id, names);
    if (!held) return;
    const box = el("div", undefined, "held-operation");
    box.dataset.held = held.name;
    box.append(el("p", "Your last " + OPERATION_NAMES[held.name] + " request was not confirmed. Trying again with the same values replays it under its key, never runs it twice; the page lets it go once the campaign's record shows how it ended.", "hint"));
    const discard = el("button", "Discard the unconfirmed " + OPERATION_NAMES[held.name], undefined);
    discard.type = "button"; discard.id = "journey-discard-" + held.name + "-" + run.id;
    discard.disabled = busy;
    discard.addEventListener("click", () => { discardOperation(run.id, [held.name]); message("Discarded. The next " + OPERATION_NAMES[held.name] + " is a new request, under a new key."); });
    box.append(discard);
    parent.append(box);
  }

  // ---- Graphite, Carbon's research agent (OWNER-GRAPHITE-MINER-01,
  // GRAPHITE-MINER-S5). It replaces the autonomous agent for new launches;
  // its mode, research share, plan, hunt and per-epoch limits are chosen
  // here and frozen at launch. Every value is the miner's: on their model,
  // key and budget. Carbon sets no default spend.
  const GRAPHITE = "graphite";
  const GRAPHITE_MODES = [
    ["FULL", "Full", "Research first, then build. Graphite reads the literature and writes a plan within the share of your model budget you set here, then constructs, practises, selects and submits."],
    ["RESEARCH", "Research", "Graphite reads the literature (and, if you choose, hunts arXiv for more), then writes a ranked plan you can read and edit in the Library. No practice submission: it spends model tokens, and practice trials only if it runs code."],
    ["BUILD", "Build", "Graphite builds from a plan: one you edited, one from an earlier Research run, or none (its Planner writes one first, from the shared pack and your Library as they are). Then it constructs, practises, selects and submits."],
  ];
  const GRAPHITE_MODE_LABEL = Object.fromEntries(GRAPHITE_MODES.map(([mode, label]) => [mode, label]));
  // The launch fields Graphite's choices travel in (S4's launch operation).
  const GRAPHITE_FIELDS = ["graphite_mode", "research_share", "plan", "hunt", "limits"];
  // Optional per-epoch counts: blank leaves only the campaign's own limits.
  const GRAPHITE_LIMITS = [["calls_per_epoch", "Model calls per epoch"], ["trials_per_epoch", "Practice trials per epoch"], ["planner_calls", "Planner model calls"]];
  // A hunt's closed query grammar (the design's): at most 8 queries of at
  // most 6 terms, each letters, digits and hyphens. Raw arXiv syntax is
  // never accepted. The counts and the record bounds are the controller's
  // own when its options state them (options.graphite.hunt); a term's and a
  // query's length are the launch rule's. The controller checks again
  // (hunt_query_invalid): these are hints before anything is sent.
  // The fallbacks are the launch rule's own (S2's hunt.MAX_RECORDS 5000 and
  // S3's edition.max_limit() 100000), used only when the options state none.
  const HUNT = {records: 200, maxRecords: 5000, queries: 8, terms: 6, termChars: 40, queryChars: 128, query: /^[A-Za-z0-9 -]+$/};
  // The largest per-epoch limit the launch takes, unless its options say.
  const LIMIT_MAX = 100000;
  const GRAPHITE_STAGES = {hunt: "Hunting arXiv", hunting: "Hunting arXiv", read: "Reading papers", reader: "Reading papers", reading: "Reading papers", triage: "Reading papers", plan: "Writing the plan", planner: "Writing the plan", planning: "Writing the plan", research: "Researching", build: "Building", constructor: "Building", construct: "Building", building: "Building", submit: "Submitting", done: "Done", complete: "Done", completed: "Done"};
  function graphiteMode(mode) { return GRAPHITE_MODE_LABEL[mode] || words(mode || "unknown"); }
  function graphiteStage(stage) {
    if (stage === undefined || stage === null || stage === "") return "Not started";
    return GRAPHITE_STAGES[String(stage).toLowerCase()] || words(stage);
  }
  // Where a campaign is now: its stage while it runs. The stage is the
  // newest call's, so an ended campaign says it ended, with the stage it
  // ended in, never that it is still writing its plan.
  const ENDED = {COMPLETED: "Done", STOPPED: "Stopped", EXPIRED: "Expired", READBACK_UNAVAILABLE: "Record unavailable"};
  function graphiteNow(stage, state) {
    if (!ENDED[state]) return graphiteStage(stage);
    const known = stage !== undefined && stage !== null && stage !== "" && graphiteStage(stage) !== "Done";
    return ENDED[state] + (known ? " (last stage: " + graphiteStage(stage).toLowerCase() + ")" : "");
  }
  // Dollars from the ledger's nanodollars, with enough places to say a small
  // amount ($0.00045), never rounded to $0.00 unless it is 0.
  function usd(nano) {
    if (typeof nano !== "number" || !Number.isFinite(nano)) return "unavailable";
    const dollars = nano / 1e9;
    if (dollars >= 1) return "$" + dollars.toFixed(2);
    if (dollars === 0) return "$0.00";
    if (dollars < 0.000001) return "under $0.000001";
    return "$" + String(Number(dollars.toPrecision(2)));
  }
  // A share as the percentage a person types, and back, exactly: "12.5" is
  // 0.125, at most two places.
  function percentText(share) { return String(Math.round(share * 10000) / 100); }
  function shareOf(text) {
    const typed = String(text ?? "").trim();
    if (!/^\d{1,3}(\.\d{1,2})?$/.test(typed)) return NaN;
    const percent = Number(typed);
    return percent <= 100 ? Math.round(percent * 100) / 10000 : NaN;
  }
  function wholeNumber(text) { const typed = String(text ?? "").trim(); return /^\d{1,15}$/.test(typed) ? Number(typed) : NaN; }
  function huntQueries(text) { return String(text ?? "").split("\n").map(line => line.trim().replace(/\s+/g, " ")).filter(Boolean); }
  // What the controller says a Graphite launch may choose: the shared
  // options operation's `graphite` block (the capability document repeats
  // it), or nothing from a controller that states none.
  function graphiteOffer() {
    const value = launchOptions?.graphite ?? caps?.graphite;
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  }
  const bound = (value, fallback) => Number.isSafeInteger(value) && value >= 1 ? value : fallback;
  // The hunt's bounds: the controller's when stated, the design's otherwise.
  function huntBounds() {
    const hunt = graphiteOffer().hunt || {};
    return {maxRecords: bound(hunt.max_records, HUNT.maxRecords), queries: bound(hunt.max_queries, HUNT.queries), terms: bound(hunt.max_terms, HUNT.terms)};
  }
  function limitMax() { return bound(graphiteOffer().limits?.maximum, LIMIT_MAX); }
  function queryProblem(queries) {
    const bounds = huntBounds();
    if (queries.length > bounds.queries) return "at most " + bounds.queries + " queries, one per line";
    for (const query of queries) {
      if (!HUNT.query.test(query)) return "“" + query + "” uses characters other than letters, digits, spaces and hyphens";
      const terms = query.split(" ");
      if (terms.length > bounds.terms) return "“" + query + "” has more than " + bounds.terms + " terms";
      if (terms.some(term => term.length > HUNT.termChars)) return "“" + query + "” has a term longer than " + HUNT.termChars + " characters";
      if (query.length > HUNT.queryChars) return "“" + query.slice(0, 40) + "…” is longer than " + HUNT.queryChars + " characters";
    }
    return null;
  }
  // The controller's own Graphite defaults when its options state them
  // (the default mode, the research share's default, the records a hunt
  // reads by default); the design's otherwise (Full, a 10% research share,
  // 200 papers a hunt). The hunt is off until the miner turns it on: it
  // spends their money, and the launch takes none unless asked.
  function graphiteDefaults() {
    const offered = graphiteOffer();
    const modes = Array.isArray(offered.modes) ? offered.modes : [];
    const mode = modes.find(item => item && item.default === true)?.id;
    const share = offered.research_share?.default;
    const hunt = offered.hunt || {};
    const records = hunt.default_records ?? hunt.max_records_default;
    return {
      mode: GRAPHITE_MODE_LABEL[mode] ? mode : "FULL",
      share: percentText(typeof share === "number" && share >= 0 && share <= 1 ? share : 0.10),
      plan: "", hunt: false,
      records: String(Number.isSafeInteger(records) && records >= 1 && records <= huntBounds().maxRecords ? records : Math.min(HUNT.records, huntBounds().maxRecords)),
      queries: "", limits: {},
    };
  }
  // The modes a hunt runs in, as the controller states them (a hunt runs
  // before Research's and Full's Planner; Build runs none), else not Build.
  function huntApplies(g) {
    const modes = graphiteOffer().hunt?.modes;
    return Array.isArray(modes) ? modes.includes(g.mode) : g.mode !== "BUILD";
  }
  // The miner's model ceilings for this launch: the share narrows only these.
  function shareCapped() {
    const ceilings = composition.budget?.ceilings || {};
    return Number.isSafeInteger(ceilings.provider_nanodollars) || Number.isSafeInteger(ceilings.provider_attempts);
  }
  // What the miner chose, over the defaults: typed text, as typed.
  function graphiteChoices() {
    const kept = wizard.graphite && typeof wizard.graphite === "object" ? wizard.graphite : {};
    return {...graphiteDefaults(), ...kept, limits: {...(kept.limits && typeof kept.limits === "object" ? kept.limits : {})}};
  }
  function setGraphite(patch) {
    wizard.graphite = {...(wizard.graphite && typeof wizard.graphite === "object" ? wizard.graphite : {}), ...patch};
    saveWizard(); render();
  }
  // Why the mode, share or hunt cannot launch, or null.
  function graphiteChoiceProblem(g = graphiteChoices()) {
    if (!GRAPHITE_MODE_LABEL[g.mode]) return "choose a mode";
    if (g.mode === "FULL" && Number.isNaN(shareOf(g.share))) return "the research share is a percentage from 0 to 100, at most two decimal places";
    if (huntApplies(g) && g.hunt) {
      const records = wholeNumber(g.records);
      const most = huntBounds().maxRecords;
      if (!(Number.isSafeInteger(records) && records >= 1 && records <= most)) return "the papers a hunt reads is a whole number from 1 to " + most;
      const problem = queryProblem(huntQueries(g.queries));
      if (problem) return "hunt query invalid: " + problem;
    }
    return null;
  }
  function graphiteLimitsProblem(g = graphiteChoices()) {
    const most = limitMax();
    for (const [key, label] of GRAPHITE_LIMITS) {
      const text = String(g.limits[key] ?? "").trim();
      if (text === "") continue;
      const value = wholeNumber(text);
      if (!(Number.isSafeInteger(value) && value >= 1 && value <= most)) return label.toLowerCase() + " is a whole number from 1 to " + most + ", or blank for no such limit";
    }
    return null;
  }
  // The launch fields for these choices: each only where its mode uses it.
  function graphiteFields(g = graphiteChoices()) {
    const fields = {graphite_mode: g.mode};
    if (g.mode === "FULL") fields.research_share = shareOf(g.share);
    if (g.mode === "BUILD" && g.plan) fields.plan = g.plan;
    if (huntApplies(g) && g.hunt) {
      const queries = huntQueries(g.queries);
      fields.hunt = {max_records: wholeNumber(g.records), ...(queries.length ? {queries} : {})};
    }
    const limits = {};
    for (const [key] of GRAPHITE_LIMITS) { const text = String(g.limits[key] ?? "").trim(); if (text !== "") limits[key] = wholeNumber(text); }
    if (Object.keys(limits).length) fields.limits = limits;
    return fields;
  }
  // The launch operation's declared fields, or null before its listing is
  // read (then everything is sent, and the controller refuses by name).
  function launchDeclared() { return launchShape ? new Set([...(launchShape.required || []), ...(launchShape.optional || [])]) : null; }
  function launchFields(fields) {
    const declared = launchDeclared();
    return Object.fromEntries(Object.entries(fields).filter(([key]) => !declared || declared.has(key)));
  }
  // A Graphite choice the controller's launch does not take: never dropped
  // silently (a Research launch sent without its mode would run as Full),
  // so the launch waits, and says why.
  function graphiteUndeclared(g = graphiteChoices()) {
    const declared = launchDeclared();
    if (!declared) return null;
    const missing = Object.keys(graphiteFields(g)).filter(key => !declared.has(key));
    return missing.length ? "this controller's launch does not take " + missing.join(", ") + ", so these choices cannot be sent. Next: update Carbon (install --update) and reconnect, or choose another agent" : null;
  }
  // The same choices from a template's fields.
  function graphiteFromFields(value) {
    const defaults = graphiteDefaults();
    const hunt = value.hunt && typeof value.hunt === "object" ? value.hunt : null;
    return {
      mode: GRAPHITE_MODE_LABEL[value.graphite_mode] ? value.graphite_mode : defaults.mode,
      share: typeof value.research_share === "number" ? percentText(value.research_share) : defaults.share,
      plan: typeof value.plan === "string" ? value.plan : "",
      hunt: Boolean(hunt),
      records: hunt && Number.isSafeInteger(hunt.max_records) ? String(hunt.max_records) : defaults.records,
      queries: hunt && Array.isArray(hunt.queries) ? hunt.queries.join("\n") : "",
      limits: Object.fromEntries(GRAPHITE_LIMITS.filter(([key]) => Number.isSafeInteger(value.limits?.[key])).map(([key]) => [key, String(value.limits[key])])),
    };
  }
  // These choices in one line, as the review and the Launchpad say them.
  function graphiteSummary(g = graphiteChoices()) {
    const problem = graphiteChoiceProblem(g);
    if (problem) return graphiteMode(g.mode) + " mode · " + problem;
    const fields = graphiteFields(g);
    const parts = [graphiteMode(g.mode) + " mode"];
    if (g.mode === "FULL") parts.push("research share " + percentText(fields.research_share) + "%" + (shareCapped() ? "" : " (binds only once you set a model-spend or model-call ceiling)"));
    if (g.mode === "BUILD") parts.push(fields.plan ? "plan " + fields.plan.slice(0, 12) + (fields.plan.length > 12 ? "…" : "") : "no plan: its Planner writes one first");
    if (huntApplies(g)) parts.push(fields.hunt ? "hunt up to " + fields.hunt.max_records + " papers" + (fields.hunt.queries ? " with " + fields.hunt.queries.length + " of your queries" : "") : "no hunt: the shared pack and your library");
    return parts.join(" · ");
  }
  // Graphite replaces the autonomous agent for new launches: once a
  // controller offers Graphite, or says the autonomous choice was replaced,
  // that choice is not offered here, and a template naming it is refused
  // with the reason, whether or not the controller still lists it. A
  // controller that predates Graphite offers what it offers. Campaigns
  // launched with the autonomous agent keep running, and their records
  // replay unchanged.
  function autonomousReplaced() {
    return Boolean(caps?.agents?.choices?.some(choice => choice.launch_agent === GRAPHITE || choice.reason === "autonomous_agent_replaced"));
  }
  function replacedChoice(choice) {
    if (choice.reason === "autonomous_agent_replaced") return true;
    return choice.launch_agent === "autonomous" && autonomousReplaced();
  }
  function agentChoices() { return caps ? caps.agents.choices.filter(choice => !replacedChoice(choice)) : []; }
  function offeredAgent(id) { return agentChoices().find(choice => choice.id === id) || null; }
  // Graphite runs on a Challenge with a registered campaign. The controller
  // says where: each Challenge's setup_offers.graphite, and the options'
  // graphite.offered_for ({id, version}). With neither stated, the launch's
  // own refusal (graphite_not_offered_for_challenge) says so.
  function graphiteOffered(choice, entry) {
    if (!choice || choice.launch_agent !== GRAPHITE || !entry) return true;
    if (typeof entry.setup_offers?.graphite === "boolean") return entry.setup_offers.graphite;
    const listed = graphiteOffer().offered_for;
    if (Array.isArray(listed)) return listed.some(item => item && item.id === entry.challenge_id && (item.version === undefined || item.version === entry.version));
    return true;
  }
  // The model a launch runs with: the one chosen here, else setup's.
  function selectedModel() {
    const setup = setupModel();
    const provider = wizard.provider || setup?.provider_id;
    const model = wizard.provider ? wizard.model : setup?.model_id;
    return provider && model ? {provider, model} : null;
  }
  // The selected model's listed price in nanodollars per token: from the
  // capability document when it carries one, else setup's own listing or the
  // price setup checked for this model. Null when none is listed here.
  function selectedPrice() {
    const chosen = selectedModel();
    if (!chosen) return null;
    const {provider, model} = chosen;
    const read = pricing => {
      if (!pricing || typeof pricing !== "object") return null;
      const input = pricing.input ?? pricing.input_nano;
      const output = pricing.output_including_reasoning ?? pricing.output ?? pricing.output_nano;
      return typeof input === "number" && typeof output === "number" && input >= 0 && output >= 0 ? {input, output, provider, model} : null;
    };
    const row = (caps?.model?.providers || []).find(item => item.id === provider)?.models?.find(item => item.id === model);
    const offeredHere = (setupState?.choices?.inference || []).find(item => item.id === provider)?.models?.find(item => item.model_id === model);
    const checked = setupState?.steps?.inference;
    const same = checked && checked.provider_id === provider && checked.model_id === model ? checked : null;
    return read(row?.pricing) || read(offeredHere?.pricing) || read(same?.published_pricing) || read(same?.declared_pricing);
  }
  // A hunt's cost, before launch: the controller's own per-paper estimate
  // when it is for the model chosen, else its Reader tokens per paper at the
  // chosen model's listed price. No figure is made up: with neither, none.
  function huntEstimate(g = graphiteChoices()) {
    const records = wholeNumber(g.records);
    if (!(Number.isSafeInteger(records) && records >= 1)) return "";
    const stated = graphiteOffer().hunt?.estimate;
    const estimate = stated && typeof stated === "object" ? stated : {};
    const chosen = selectedModel();
    const tokens = estimate.reader_tokens_per_abstract;
    const price = selectedPrice();
    let each = null, basis = "";
    if (chosen && estimate.model === chosen.provider + ":" + chosen.model && typeof estimate.nanodollars_per_abstract === "number" && estimate.nanodollars_per_abstract >= 0) {
      each = estimate.nanodollars_per_abstract; basis = "Carbon's estimate for " + chosen.model;
    } else if (price && tokens && typeof tokens.input === "number" && typeof tokens.output === "number") {
      each = tokens.input * price.input + tokens.output * price.output; basis = price.model + "'s listed price, about " + tokens.input + " input and " + tokens.output + " output tokens a paper";
    }
    if (each === null) return "No price " + (price ? "estimate is stated here" : "is listed here for this model") + ", so there is no estimate. Your model-spend ceiling, if you set one, binds the hunt.";
    return "Hunt estimate: about " + usd(each * records) + " for up to " + records + " papers (" + usd(each) + " each, at " + basis + "). A paper already in the shared pack or your library is skipped before any model call, so a hunt usually costs less. Your ledger meters the real cost, and your model-spend ceiling, if you set one, binds.";
  }
  function shareNote(g = graphiteChoices()) {
    const share = shareOf(g.share);
    if (Number.isNaN(share)) return "Type a percentage from 0 to 100, at most two decimal places.";
    const ceilings = composition.budget?.ceilings || {};
    const parts = [];
    if (Number.isSafeInteger(ceilings.provider_nanodollars)) parts.push(usd(Math.floor(ceilings.provider_nanodollars * share)) + " of your " + resourceValue("provider_nanodollars", ceilings.provider_nanodollars) + " model spend");
    if (Number.isSafeInteger(ceilings.provider_attempts)) parts.push(Math.floor(ceilings.provider_attempts * share) + " of your " + ceilings.provider_attempts + " model calls");
    // The share narrows only the model ceilings the miner set: with none,
    // it limits nothing, and that is said plainly.
    if (!parts.length) return "Research may use " + percentText(share) + "% of your model budget, but you have set no model-spend or model-call ceiling, so this share does not limit research yet. Set one under Tools & limits, Advanced: research then stops at its share (research share reached) and the build goes on.";
    return "Research may use " + percentText(share) + "% of your model budget: " + parts.join(" and ") + ". When that is used, research stops (research share reached) and the build goes on.";
  }

  // ---- Launch wizard. ----
  function selectChallenge(entry) {
    wizard = {...wizard, challenge: {id: entry.challenge_id, version: entry.version}};
    saveWizard(); render();
  }
  // A budget in the units a person reads: dollars, minutes, megabytes.
  function budgetParts(budget = {}) {
    const parts = [];
    if ("elapsed_seconds" in budget) parts.push(budget.elapsed_seconds + " s elapsed" + longer(budget.elapsed_seconds));
    if (budget.final_reserve) parts.push("final phase held back");
    for (const [name, cap] of Object.entries(budget.ceilings || {})) parts.push(resourceShort(name) + " ≤ " + resourceValue(name, cap));
    return parts;
  }
  function describeComposition(value) {
    const parts = budgetParts(value.budget || {});
    const agent = agentEntry(wizard.agentChoice);
    return "Launches with " + (value.agent ? (agent ? agent.label : value.agent) : "no choice yet") + (value.agent === GRAPHITE ? " (" + graphiteSummary() + ")" : "") + " · budget: " + (parts.length ? parts.join(", ") : "none, no cap");
  }
  // Why this composition cannot launch right now, or null. Availability is
  // the options operation's, read from the host - never assumed.
  function compositionProblem(value) {
    if (!launchOptions) return "launch options have not been read yet";
    // Refused at launch as autonomous_agent_replaced: said here first.
    if (value.agent === "autonomous" && autonomousReplaced()) return "Carbon's autonomous agent was replaced by Graphite for new campaigns (autonomous agent replaced): choose Graphite";
    const agent = launchOptions.agents.find(option => option.value === value.agent);
    if (!agent) return "choose who selects and submits";
    if (agent.availability !== "available") return "the " + value.agent + " agent is unavailable: " + words(agent.reason);
    return budgetProblem(value.budget);
  }
  function budgetProblem(budget = {}) {
    const vocabulary = caps?.budget || launchOptions?.budget || {keys: [], ceilings: []};
    for (const key of Object.keys(budget)) if (!vocabulary.keys.includes(key)) return "a budget cannot set " + key;
    if ("elapsed_seconds" in budget && !(Number.isInteger(budget.elapsed_seconds) && budget.elapsed_seconds >= 1)) return "the elapsed limit must be a whole number of seconds, at least 1";
    if ("final_reserve" in budget && typeof budget.final_reserve !== "boolean") return "the final reserve is on or off";
    for (const [name, cap] of Object.entries(budget.ceilings || {})) {
      if (!vocabulary.ceilings.includes(name)) return "no resource is called " + name;
      if (cap === Infinity) return "the " + resourceShort(name) + " ceiling is too large to count exactly";
      if (!(Number.isInteger(cap) && cap >= 0)) return "the " + resourceShort(name) + " ceiling must be " + (UNITS[name] ? "an amount in " + UNITS[name].unit : "a whole number") + ", 0 or more";
    }
    return null;
  }
  // Why a step cannot be passed yet, with what to do; null when it can.
  function stepProblem(step) {
    if (!connected || !caps) return "Connect this browser first.";
    if (step === "challenge") {
      const entry = challengeEntry(wizard.challenge);
      if (!entry) return "Choose a Challenge.";
      if (!entry.selectable) return entry.title + " cannot launch: " + words(entry.reason) + ". Next: " + entry.next_action;
    }
    if (step === "agent") {
      const agent = offeredAgent(wizard.agentChoice);
      if (!agent) return "Choose who selects and submits.";
      if (agent.availability !== "available") return agent.label + " is unavailable: " + words(agent.reason) + ". Next: " + agent.next_action;
      const entry = challengeEntry(wizard.challenge);
      if (!graphiteOffered(agent, entry)) return agent.label + " is not offered for " + entry.title + " (graphite not offered for challenge). Next: choose a Challenge it is offered for, or another agent.";
      if (agent.launch_agent === GRAPHITE) {
        const problem = graphiteChoiceProblem() || graphiteUndeclared();
        if (problem) return "Graphite: " + problem + ".";
      }
    }
    if (step === "model") {
      const agent = offeredAgent(wizard.agentChoice);
      if (agent?.uses_model) {
        const provider = selectedProvider();
        // With nothing chosen here, a launch runs with the model chosen in
        // setup: the controller falls back to the profile's model_selection.
        if (!provider) {
          const setup = setupModel();
          if (!setup) return "Choose a model provider.";
          const row = caps.model.providers.find(item => item.id === setup.provider_id);
          if (row && row.availability !== "available") return row.provider + " (your setup's choice) is unavailable: " + words(row.reason) + ". Next: " + row.next_action;
          return null;
        }
        if (provider.availability !== "available") return provider.provider + " is unavailable: " + words(provider.reason) + ". Next: " + provider.next_action;
        if (!provider.models.some(model => model.id === wizard.model)) {
          return provider.models.length ? "Choose a model." : provider.provider + " lists no models here. Choose it with your model under Set up, Inference: that model is then offered here.";
        }
        const cap = outputCap();
        if (cap?.problem) return "Fix the output cap: " + cap.problem + ", or leave it blank for " + outputDefault(cap) + ".";
      }
    }
    if (step === "compute") {
      const compute = computeChoice();
      if (!compute || compute.availability !== "available") return "Compute unavailable: " + words(compute?.reason) + ". Next: " + (compute?.next_action || "Re-read capabilities.");
    }
    if (step === "limits") {
      const problem = budgetProblem(composition.budget);
      if (problem) return "Fix your limits: " + problem + ".";
      if (offeredAgent(wizard.agentChoice)?.launch_agent === GRAPHITE) {
        const limits = graphiteLimitsProblem();
        if (limits) return "Fix Graphite's per-epoch limits: " + limits + ".";
      }
    }
    if (step === "review") {
      for (const [name] of STEPS.slice(0, 5)) { const problem = stepProblem(name); if (problem) return problem; }
      if (!research.preflight.available) return "Research launch is unavailable: " + words(research.preflight.reason || research.preflight.status) + ".";
      const problem = compositionProblem(composition);
      if (problem) return "Cannot launch: " + problem + ".";
    }
    return null;
  }
  function renderWizard() {
    const index = Math.max(0, STEPS.findIndex(([name]) => name === wizard.step));
    const list = $("wizard-steps");
    // Built once; each step button is patched in place, so it is the same
    // element from one refresh to the next and a click on it always lands.
    if (list.children.length !== STEPS.length) {
      list.replaceChildren();
      STEPS.forEach(([name, label], position) => {
        const item = el("li");
        const button = el("button", (position + 1) + " · " + label); button.type = "button"; button.dataset.wizardStep = name;
        button.addEventListener("click", () => { wizard.step = name; saveWizard(); render(); });
        item.append(button); list.append(item);
      });
    }
    STEPS.forEach((_, position) => {
      const button = list.children[position].firstChild;
      if (position === index) button.setAttribute("aria-current", "step"); else button.removeAttribute("aria-current");
      // A later step opens only once every step before it can be passed.
      button.disabled = position > index && STEPS.slice(0, position).some(([earlier]) => stepProblem(earlier));
    });
    for (const section of document.querySelectorAll("#launch .step")) section.hidden = section.dataset.step !== STEPS[index][0];
    const problem = stepProblem(STEPS[index][0]);
    $("wizard-back").disabled = index === 0;
    $("wizard-next").hidden = index === STEPS.length - 1;
    $("wizard-next").disabled = Boolean(problem);
    setText($("wizard-next-reason"), problem && index < STEPS.length - 1 ? problem : "");
    renderWizardChallenges();
    renderWizardAgents();
    renderWizardGraphite();
    renderWizardModel();
    renderWizardCompute();
    renderWizardTools();
    renderLaunchComposition();
    renderWizardReview();
    renderResearchPreflight();
    const blocked = stepProblem("review");
    $("research-launch").disabled = !connected || busy || storageError || !research.preflight.available || Boolean(blocked);
    setText($("research-launch"), pendingResearch ? "Retry the launch with these choices" : "Launch research");
    const chosen = challengeEntry(wizard.challenge);
    setText($("wizard-launch-summary"), chosen ? chosen.title + " \u00b7 version " + chosen.version + " \u00b7 " + describeComposition(composition) : "");
    setText($("wizard-launch-reason"), blocked ? blocked : storageError ? "Browser retry storage is unavailable; launch is disabled to preserve duplicate protection." : "");
    renderPendingLaunch();
  }
  // A launch sent and not answered (LP-PROD-F): said once, with its retry and
  // a way to let it go. Its key is kept, so a retry is replayed if the first
  // was recorded, never run twice; the retry carries the current choices.
  function renderPendingLaunch() {
    const note = $("research-pending");
    const text = pendingResearch ? "Your last launch was not confirmed: the controller did not answer, or answered with an error that does not say whether it was recorded. Retry sends your current choices under the same request key: if the first was recorded, it is replayed or refused as a conflict, never launched twice. If it was recorded, it is listed under My Campaigns." : "";
    setText(note, text);
    note.hidden = !pendingResearch;
    $("research-discard").hidden = !pendingResearch;
    $("research-discard").disabled = busy;
  }
  function discardLaunch() {
    if (busy || !pendingResearch) return;
    try { sessionStorage.removeItem(researchKey); } catch (_) { /* nothing held */ }
    pendingResearch = null;
    message("Discarded. Check My Campaigns: if the earlier launch was recorded, it is there. A new launch now gets a new key.");
    render();
  }
  $("research-discard").addEventListener("click", discardLaunch);
  $("wizard-back").addEventListener("click", () => { const index = STEPS.findIndex(([name]) => name === wizard.step); if (index > 0) { wizard.step = STEPS[index - 1][0]; saveWizard(); render(); } });
  $("wizard-next").addEventListener("click", () => { const index = STEPS.findIndex(([name]) => name === wizard.step); if (index < STEPS.length - 1 && !stepProblem(wizard.step)) { wizard.step = STEPS[index + 1][0]; saveWizard(); render(); } });
  function renderWizardChallenges() {
    const target = $("wizard-challenges");
    if (!caps) { rebuild(target, "none", node => node.append(el("p", "Connect to read the Challenge registry.", "hint"))); $("wizard-challenge-description").replaceChildren(); $("wizard-challenge-description").dataset.key = ""; return; }
    rebuild(target, JSON.stringify([capsVersion, caps.challenges.map(entry => [entry.challenge_id, entry.version, entry.selectable]), connected]), node => {
      for (const entry of caps.challenges) {
        const label = el("label", undefined, "choice" + (entry.selectable ? "" : " unavailable"));
        const input = el("input"); input.type = "radio"; input.name = "wizard-challenge"; input.value = entry.challenge_id;
        input.dataset.version = entry.version || "";
        // Unimplemented Challenges are shown, never offered as working choices.
        input.disabled = !entry.implemented;
        input.addEventListener("change", () => selectChallenge(entry));
        const text = el("span");
        text.append(el("strong", entry.title), el("span", " " + challengeStatus(entry) + (entry.version ? " · v" + entry.version : ""), "small-tag"));
        if (!entry.selectable) text.append(el("span", "Unavailable: " + words(entry.reason) + " · Next: " + entry.next_action, "reason"));
        label.append(input, text); node.append(label);
      }
    });
    // The choice is patched in place: choosing never redraws the list.
    for (const input of target.querySelectorAll("input[name=wizard-challenge]")) {
      input.checked = Boolean(wizard.challenge && wizard.challenge.id === input.value && (wizard.challenge.version || "") === input.dataset.version);
    }
    const description = $("wizard-challenge-description");
    const entry = challengeEntry(wizard.challenge);
    if (description.dataset.key !== (entry ? entry.challenge_id + "@" + entry.version : "")) {
      description.replaceChildren();
      if (entry?.implemented) { description.append(el("h3", entry.title)); renderDescription(description, entry); }
      description.dataset.key = entry ? entry.challenge_id + "@" + entry.version : "";
    }
  }
  function renderWizardAgents() {
    const box = $("research-selects");
    const notes = $("wizard-agent-notes");
    const entry = challengeEntry(wizard.challenge);
    const choices = caps ? agentChoices().map(choice => [choice.id, choice.label, choice.availability, choice.reason ?? null, graphiteOffered(choice, entry)]) : null;
    rebuild(box, JSON.stringify([capsVersion, choices, entry ? entry.title : null]), node => {
      node.append(el("legend", "Who selects and submits"));
      if (!caps) return;
      for (const choice of agentChoices()) {
        const here = graphiteOffered(choice, entry);
        const label = el("label", undefined, "choice" + (choice.availability === "available" && here ? "" : " unavailable"));
        const input = el("input"); input.type = "radio"; input.name = "research-agent"; input.value = choice.id;
        input.disabled = choice.availability !== "available" || !here;
        input.addEventListener("change", () => { wizard.agentChoice = choice.id; composition = {...composition, agent: choice.launch_agent}; saveWizard(); render(); });
        const text = el("span");
        text.append(el("strong", choice.label), el("span", " " + choice.summary, "hint"));
        if (choice.availability !== "available") text.append(el("span", "Unavailable: " + words(choice.reason) + " · Next: " + choice.next_action, "reason"));
        else if (!here) text.append(el("span", "Not offered for " + entry.title + ": graphite not offered for challenge · Next: choose a Challenge with a registered Graphite campaign.", "reason"));
        label.append(input, text); node.append(label);
      }
    });
    for (const input of box.querySelectorAll("input[name=research-agent]")) input.checked = wizard.agentChoice === input.value;
    const external = agentEntry("external_mcp");
    rebuild(notes, JSON.stringify([capsVersion, Boolean(caps), wizard.agentChoice]), node => {
      if (!caps) return;
      if (wizard.agentChoice === "external_mcp" && external) researchNote(node, "After launch, connect your client with: " + external.command + ". It sees this campaign and calls the same practice, freeze and submit operations.", "code");
      for (const item of caps.agents.unavailable) researchNote(node, item.id + " · unavailable: " + words(item.reason) + " · Next: " + item.next_action, "reason");
    });
  }
  // Graphite's choices, under the Agent step once Graphite is chosen: built
  // once, then patched in place, so a field being typed into is never
  // replaced. Each field is backed by the wizard's own state.
  function renderWizardGraphite() {
    const box = $("wizard-graphite");
    const limits = $("graphite-limits");
    const agent = caps ? offeredAgent(wizard.agentChoice) : null;
    const on = Boolean(agent && agent.launch_agent === GRAPHITE);
    box.hidden = !on;
    limits.hidden = !on;
    if (!on) return;
    rebuild(box, "graphite:" + capsVersion, drawGraphiteOptions);
    buildGraphiteLimits();
    patchGraphiteOptions();
  }
  function graphiteInput(parent, id, labelText, type, onInput, attributes = {}) {
    const label = el("label", labelText); label.htmlFor = id;
    const input = el(type === "textarea" ? "textarea" : "input"); input.id = id;
    if (type !== "textarea") input.type = type;
    for (const [name, value] of Object.entries(attributes)) input[name] = value;
    input.autocomplete = "off"; input.spellcheck = false;
    // Backed by the wizard's state: restored on a rebuild, never held.
    input.dataset.draft = "1";
    input.addEventListener("input", () => onInput(input.value));
    parent.append(label, input);
    return input;
  }
  function drawGraphiteOptions(box) {
    box.append(el("h3", "Graphite"));
    box.append(el("p", "Graphite, Carbon's research agent, reads the literature, writes a plan, then builds, practises, selects and submits: on your model, with your key, within your own budget. Carbon spends nothing and caps nothing.", "hint"));
    const modes = el("fieldset", undefined, "selects"); modes.id = "wizard-graphite-modes";
    modes.append(el("legend", "Mode"));
    for (const [mode, label, text] of GRAPHITE_MODES) {
      const choice = el("label", undefined, "choice");
      const input = el("input"); input.type = "radio"; input.name = "wizard-graphite-mode"; input.value = mode; input.id = "wizard-graphite-mode-" + mode.toLowerCase();
      input.addEventListener("change", () => setGraphite({mode}));
      const span = el("span"); span.append(el("strong", label + (mode === "FULL" ? " · the default" : "")), el("span", text, "hint"));
      choice.append(input, span); modes.append(choice);
    }
    box.append(modes);
    // Full: how much of the budget research may use.
    const share = el("div", undefined, "graphite-field"); share.id = "wizard-graphite-share";
    graphiteInput(share, "wizard-research-share", "Research share · % of your model budget", "number", value => setGraphite({share: value}), {min: "0", max: "100", step: "0.01"});
    const shareLine = el("p", "", "hint"); shareLine.id = "wizard-research-share-note"; share.append(shareLine);
    box.append(share);
    // Build: the plan it builds from.
    const plan = el("div", undefined, "graphite-field"); plan.id = "wizard-graphite-plan-box";
    const planLabel = el("label", "Plan to build from"); planLabel.htmlFor = "wizard-graphite-plan";
    const select = el("select"); select.id = "wizard-graphite-plan";
    select.addEventListener("change", () => { setGraphite({plan: select.value}); sent(select); });
    const planLine = el("p", "", "hint"); planLine.id = "wizard-graphite-plan-note";
    const planActions = el("div", undefined, "controls");
    const reread = el("button", "Re-read your plans"); reread.type = "button"; reread.id = "wizard-graphite-plans-reread";
    reread.addEventListener("click", () => { window.CarbonLibrary?.plans(true); });
    planActions.append(reread, link({label: "Read and edit your plans in the Library", href: "#library/plans"}));
    plan.append(planLabel, select, planLine, planActions);
    box.append(plan);
    // Research and Full (where the controller runs a hunt): the hunt, off
    // until the miner turns it on.
    const hunt = el("div", undefined, "graphite-field"); hunt.id = "wizard-graphite-hunt";
    const toggle = el("label", undefined, "check");
    const check = el("input"); check.type = "checkbox"; check.id = "wizard-hunt";
    check.addEventListener("change", () => setGraphite({hunt: check.checked}));
    toggle.append(check, " Hunt arXiv for more papers before planning, on your model and budget (off unless you turn it on)");
    hunt.append(toggle);
    const options = el("div"); options.id = "wizard-hunt-options";
    graphiteInput(options, "wizard-hunt-records", "Papers a hunt reads, at most", "number", value => setGraphite({records: value}), {min: "1", step: "1"});
    graphiteInput(options, "wizard-hunt-queries", "Your own queries (optional, one per line)", "textarea", value => setGraphite({queries: value}), {rows: 3});
    const hint = el("p", "", "hint"); hint.id = "wizard-hunt-hint";
    options.append(hint);
    const estimate = el("p", "", "status-line"); estimate.id = "wizard-hunt-estimate";
    options.append(estimate);
    hunt.append(options);
    box.append(hunt);
    box.append(el("p", "Per-epoch limits are optional, under Tools & limits, Advanced: left blank, only your campaign's own limits bind, money and time.", "hint"));
  }
  function buildGraphiteLimits() {
    const box = $("graphite-limits");
    if (box.dataset.built) return;
    box.append(el("p", "Optional. Left blank, only your campaign's own limits bind: its money, calls, trials and time. Set one only to end an epoch sooner.", "hint"));
    for (const [key, label] of GRAPHITE_LIMITS) {
      const wrap = el("div");
      graphiteInput(wrap, "graphite-limit-" + key, label, "number", value => setGraphite({limits: {...graphiteChoices().limits, [key]: value}}), {min: "1", max: String(limitMax()), step: "1", placeholder: "No limit"});
      box.append(wrap);
    }
    box.dataset.built = "1";
  }
  // A field shows the wizard's value unless it is the one being typed into.
  function fill(input, value) {
    const text = String(value ?? "");
    if (input && document.activeElement !== input && input.value !== text) input.value = text;
  }
  function patchGraphiteOptions() {
    const g = graphiteChoices();
    for (const input of document.querySelectorAll("input[name=wizard-graphite-mode]")) input.checked = input.value === g.mode;
    $("wizard-graphite-share").hidden = g.mode !== "FULL";
    $("wizard-graphite-plan-box").hidden = g.mode !== "BUILD";
    $("wizard-graphite-hunt").hidden = !huntApplies(g);
    fill($("wizard-research-share"), g.share);
    setText($("wizard-research-share-note"), shareNote(g));
    $("wizard-hunt").checked = Boolean(g.hunt);
    $("wizard-hunt-options").hidden = !g.hunt;
    // The controller's own bounds, as hints: it checks them again.
    const bounds = huntBounds();
    const records = $("wizard-hunt-records");
    if (records.max !== String(bounds.maxRecords)) records.max = String(bounds.maxRecords);
    for (const [key] of GRAPHITE_LIMITS) { const input = $("graphite-limit-" + key); if (input.max !== String(limitMax())) input.max = String(limitMax()); }
    setText($("wizard-hunt-hint"), "Carbon composes queries from the Challenge's public description. Add up to " + bounds.queries + " of your own, each up to " + bounds.terms + " words of letters, digits and hyphens. A hunt reads at most " + bounds.maxRecords + " papers. At most one arXiv request every 3 s; cards found go to your private Library. A launch that hunts also reads the texts you imported in the Library.");
    fill(records, g.records);
    fill($("wizard-hunt-queries"), g.queries);
    setText($("wizard-hunt-estimate"), huntEstimate(g));
    for (const [key] of GRAPHITE_LIMITS) fill($("graphite-limit-" + key), g.limits[key]);
    patchPlanPicker(g);
  }
  // The Library's plans, for Build (library_view.js reads them).
  function patchPlanPicker(g) {
    const select = $("wizard-graphite-plan");
    const note = $("wizard-graphite-plan-note");
    const read = g.mode === "BUILD" && window.CarbonLibrary ? window.CarbonLibrary.plans() : null;
    const plans = read?.list || [];
    const options = [["", "None: Graphite's Planner writes one first"], ...plans.map(item => [item.digest, (item.created_by === "miner" ? "Your edit" : "Graphite's plan") + " · " + item.digest.slice(0, 12) + (item.created_at && when(item.created_at) ? " · " + when(item.created_at) : "")])];
    if (g.plan && !plans.some(item => item.digest === g.plan)) options.push([g.plan, g.plan.slice(0, 12) + " · not in your Library now"]);
    const key = JSON.stringify(options);
    if (select.dataset.options !== key && !held(select)) {
      select.replaceChildren(...options.map(([value, text]) => { const option = el("option", text); option.value = value; return option; }));
      select.dataset.options = key;
    }
    if (select.value !== g.plan && document.activeElement !== select) select.value = g.plan;
    setText(note, !read ? "" : !read.offered ? "This controller does not list plans: Build starts with Graphite's Planner." : read.error ? "Your plans could not be read: " + words(read.error) + "." : !read.list ? "Reading your plans…" : !plans.length ? "No plan yet: a Research campaign writes one, or write your own in the Library." : plans.length + " plan" + (plans.length === 1 ? "" : "s") + " in your Library. The one chosen is frozen at launch by its digest.");
  }
  function renderWizardModel() {
    const target = $("wizard-model");
    const agent = agentEntry(wizard.agentChoice);
    const usesModel = !(agent && !agent.uses_model);
    rebuild(target, JSON.stringify([capsVersion, Boolean(caps), usesModel, agent?.label ?? null]), node => {
      if (!caps) return;
      if (!usesModel) {
        researchNote(node, agent.label + " calls no model: nothing to choose here, and no credential is needed.");
        return;
      }
      researchNote(node, "You choose the provider and model and supply your own credential. " + caps.model.selection, "hint");
      const setup = setupModel();
      if (setup) researchNote(node, "Your setup chose " + setup.model_id + " (" + ((caps.model.providers.find(row => row.id === setup.provider_id) || {}).provider || setup.provider_id) + "). It is selected below; a launch with nothing chosen here runs with it too.", "status-line");
      for (const provider of caps.model.providers) {
        const group = el("fieldset", undefined, "selects");
        group.append(el("legend", provider.provider));
        for (const model of provider.models) {
          const label = el("label", undefined, "choice" + (provider.availability === "available" ? "" : " unavailable"));
          const input = el("input"); input.type = "radio"; input.name = "wizard-model"; input.value = provider.id + "/" + model.id;
          input.disabled = provider.availability !== "available";
          input.addEventListener("change", () => { wizard.provider = provider.id; wizard.model = model.id; saveWizard(); render(); });
          label.append(input, el("span", model.id + (model.from_setup ? " · your setup choice" : "")));
          group.append(label);
        }
        // A provider whose adapter lists no models is chosen with its model
        // in setup; a launch never names a model this page has not listed.
        if (!provider.models.length) researchNote(group, "No model is listed for this provider here. Choose it with your model under Set up, Inference, and that model is offered here.", "hint");
        researchNote(group, "Credential: " + provider.credential.reference + " · " + (provider.credential.configured === null ? provider.credential.basis : provider.credential.configured ? "configured" : "not configured"), "hint");
        if (provider.availability !== "available") unavailableNote(group, provider);
        node.append(group);
      }
      for (const item of caps.model.unavailable) researchNote(node, item.id + " · unavailable: " + words(item.reason) + " · Next: " + item.next_action, "reason");
    });
    for (const input of target.querySelectorAll("input[name=wizard-model]")) input.checked = input.value === wizard.provider + "/" + wizard.model;
    // The optional output cap, patched in place so typing is never redrawn.
    const cap = outputCap();
    const box = $("wizard-output");
    if (box.hidden !== !cap) box.hidden = !cap;
    if (!cap) return;
    const input = $("wizard-max-output");
    if (input.min !== String(cap.low)) input.min = String(cap.low);
    if (input.max !== String(cap.high)) input.max = String(cap.high);
    const placeholder = cap.fallback ? "Default: " + cap.fallback.max_output_tokens : "Default";
    if (input.placeholder !== placeholder) input.placeholder = placeholder;
    fill(input, wizard.maxOutput ?? "");
    input.setAttribute("aria-invalid", cap.problem ? "true" : "false");
    let note = "Default for " + wizard.model + ": " + outputDefault(cap) + ". Leave it blank to use that, or enter a whole number from " + cap.low.toLocaleString("en-US") + " to " + cap.high.toLocaleString("en-US") + " to cap each reply; each call is reserved at the cap. The Control Center checks it again at launch.";
    if (cap.problem) note = "Not valid: " + cap.problem + ". " + note;
    else if (cap.value !== null && cap.fallback && cap.fallback.basis !== "no_documented_maximum" && cap.value > cap.fallback.max_output_tokens) note = "Above " + outputDefault(cap) + ": the provider may refuse the call. " + note;
    setText($("wizard-output-note"), note);
    const kind = cap.problem ? "reason" : "hint";
    if ($("wizard-output-note").className !== kind) $("wizard-output-note").className = kind;
  }
  function renderWizardCompute() {
    rebuild($("wizard-compute"), JSON.stringify([capsVersion, Boolean(caps)]), target => {
      if (!caps) return;
      researchNote(target, caps.compute.selection, "hint");
      for (const choice of caps.compute.choices) {
        const box = card(target, choice.label, ...readiness(choice));
        researchNote(box, "Lane: " + choice.lane + " · " + Object.entries(choice.lanes).map(([lane, state]) => lane + " " + state.availability + (state.reason ? " (" + words(state.reason) + ")" : "")).join(" · "));
        if (choice.availability !== "available") unavailableNote(box, choice);
      }
      for (const item of caps.compute.unavailable) researchNote(target, item.id + " · unavailable: " + words(item.reason) + " · Next: " + item.next_action, "reason");
    });
  }
  function renderWizardTools() {
    const target = $("wizard-tools");
    const entry = challengeEntry(wizard.challenge);
    const key = entry ? entry.challenge_id + "@" + entry.version : "";
    if (target.dataset.key === key) return;
    target.replaceChildren();
    target.dataset.key = key;
    if (!entry) { researchNote(target, "Choose a Challenge first: its tools come from its description.", "hint"); return; }
    target.append(el("h3", "Tools for " + entry.title));
    const grid = el("dl", undefined, "review-grid");
    for (const [name, detail] of Object.entries(entry.tools?.workflow || {})) grid.append(el("dt", name), el("dd", detail));
    if (entry.tools?.public_material?.length) grid.append(el("dt", "public material"), el("dd", entry.tools.public_material.join(", ")));
    if (entry.tools?.rebuildable_models?.length) grid.append(el("dt", "rebuildable models"), el("dd", entry.tools.rebuildable_models.join(", ")));
    target.append(grid);
    // The Challenge's own feedback modes; FULL is every Challenge's default.
    const modes = entry.setup_offers?.feedback_modes || [];
    if (modes.length > 1) {
      const id = "wizard-feedback-mode";
      const label = el("label", "Practice feedback"); label.htmlFor = id;
      const select = document.createElement("select"); select.id = id;
      for (const mode of modes) { const option = el("option", words(mode)); option.value = mode; select.append(option); }
      select.value = modes.includes(wizard.feedbackMode) ? wizard.feedbackMode : "FULL";
      select.addEventListener("change", () => { wizard.feedbackMode = select.value; saveWizard(); });
      target.append(label, select);
    }
    if (entry.tools?.how_to_request_unsupported) researchNote(target, entry.tools.how_to_request_unsupported, "hint");
  }
  function renderResearchPreflight() {
    const guidance = research.preflight.research_guidance;
    $("research-guidance-review").hidden = !connected || !guidance;
    const task = connected && guidance ? guidance.text : "";
    if ($("research-guidance").value !== task) $("research-guidance").value = task;
    setText($("research-runtime"), connected && guidance ? "Configured runtime: " + research.preflight.runtime_revision + " · Task identity (frozen on launch): " + guidance.digest : "");
    setText($("research-preflight"), connected ? research.preflight.status.replaceAll("_", " ") + (research.preflight.reason ? " · " + research.preflight.reason : "") + (research.preflight.available ? " · Admission: your subnet registration, read at launch · Budget: yours to set, or none" : "") : "Reconnect to reconcile research state. Controls are disabled.");
    const review = connected && research.preflight.review;
    rebuild($("research-review"), JSON.stringify(review || null), reviewPanel => { if (review) drawReview(reviewPanel, review); });
  }
  function drawReview(reviewPanel, review) {
    researchNote(reviewPanel, "Experiment pause: " + review.experiment_pause);
    if (review.blockers?.length) researchNote(reviewPanel, "Launch unavailable: " + review.blockers.map(value => value.replaceAll("_", " ")).join("; "));
    researchNote(reviewPanel, "Your research runs on: " + review.execution.profile + " · Backend: " + review.execution.backend + " · Lane: " + review.execution.lane + " · " + review.execution.basis);
    // Stated before launch rather than discovered afterwards. Choosing a GPU
    // to research with never selects or rewrites the evaluator.
    if (review.final_evaluation) {
      researchNote(reviewPanel, "Independent DEVELOPMENT comparison runs on: " + review.final_evaluation.profile + " · Backend: " + review.final_evaluation.backend + " · " + review.final_evaluation.basis);
    }
    if (review.execution.assurance) {
      researchNote(reviewPanel, "This research lane establishes: " + review.execution.assurance.established.map(value => value.replaceAll("_", " ").toLowerCase()).join("; ") + ". It does not establish: " + review.execution.assurance.not_established.map(value => value.replaceAll("_", " ").toLowerCase()).join("; ") + ".");
    }
    if (review.readiness) {
      // Distinct states, never one green badge.
      const states = Object.entries(review.readiness).filter(([name]) => name !== "basis");
      researchNote(reviewPanel, "Readiness · " + states.map(([name, value]) => name.replaceAll("_", " ") + ": " + value).join(" · "));
      researchNote(reviewPanel, review.readiness.basis);
    }
    researchNote(reviewPanel, "Dependencies installed: " + review.execution.installed_dependencies + " · Device visibility: " + review.execution.device_visibility + " · Retained execution evidence: " + review.execution.runtime_evidence + " · Admission: " + review.execution.admission_readiness);
    researchNote(reviewPanel, "Admission: " + review.admission.gate.replaceAll("_", " ").toLowerCase() + " · " + review.admission.basis);
    researchNote(reviewPanel, review.resources.basis);
    const details = document.createElement("details");
    const label = document.createElement("summary"); label.textContent = "Exact configured identities, capabilities and resource limits";
    const data = document.createElement("pre"); data.textContent = JSON.stringify(review, null, 2);
    data.style.whiteSpace = "pre-wrap"; data.style.overflowWrap = "anywhere";
    details.append(label, data); reviewPanel.append(details);
  }
  function renderWizardReview() {
    const rows = [];
    const problems = [];
    if (caps) {
      const row = (label, value) => rows.push([label, value]);
      const entry = challengeEntry(wizard.challenge);
      const agent = agentEntry(wizard.agentChoice);
      const provider = selectedProvider();
      const compute = computeChoice();
      const budget = composition.budget || {};
      const setup = setupModel();
      row("Identity", caps.profile.configured ? "Runner profile " + caps.profile.profile_id + " · registered hotkey read from it at launch" : "No runner profile");
      row("Network", research.preflight.review?.admission?.gate ? words(research.preflight.review.admission.gate).toLowerCase() + " · see Wallet & Identity for the network and netuid" : "Subnet registration, read at launch · see Wallet & Identity");
      row("Challenge", entry ? entry.title + " · " + entry.challenge_id + " · version " + entry.version + (entry.description?.contract_digest ? " · contract " + entry.description.contract_digest : "") : "Not chosen");
      row("Agent", agent ? agent.label + " (launch agent: " + agent.launch_agent + ")" : "Not chosen");
      if (agent?.launch_agent === GRAPHITE) {
        const g = graphiteChoices();
        row("Graphite", graphiteSummary(g));
        if (huntApplies(g) && g.hunt && !graphiteChoiceProblem(g)) row("Hunt cost", huntEstimate(g));
        const limits = graphiteLimitsProblem(g) ? {} : graphiteFields(g).limits || {};
        row("Graphite's limits", GRAPHITE_LIMITS.map(([key, label]) => label + ": " + (key in limits ? limits[key] : "no limit")).join(" · ") + ". Unset, only your campaign's own limits bind.");
      }
      row("Model", agent && !agent.uses_model ? "None: this agent calls no model"
        : provider && wizard.model ? provider.provider + " · " + wizard.model + " · credential " + (provider.credential.configured ? "configured" : "not configured") + ". " + caps.model.selection
        : setup ? "Your setup's choice: " + setup.model_id + " (" + setup.provider_id + ")" : "Not chosen");
      const cap = outputCap();
      if (cap && !cap.problem) row("Max output", cap.value !== null ? cap.value.toLocaleString("en-US") + " tokens per reply, your cap" : "Not set: " + outputDefault(cap));
      row("Compute", compute ? compute.label + " · " + compute.lane + " lane · " + compute.availability : "Unavailable");
      row("Tools", entry ? Object.keys(entry.tools?.workflow || {}).join(", ") || "none listed" : "Choose a Challenge");
      // Stated before launch, not learnt at submit (LAUNCHPAD-PAGE-USABILITY-01).
      const evaluation = entry ? evaluationOf(entry.challenge_id) : null;
      if (evaluation) row("Evaluation", EVALUABLE.includes(evaluation.status) ? "A validator is configured for this Challenge in your profile; whether it answers is seen at submit." : "Unavailable today: no validator intake is configured in your profile" + (evaluation.status === "NONE_PUBLISHED" ? " and none is published for this Challenge yet" : "") + ". You can launch, practise, observe, freeze, and stop or pause; a submit is refused and the frozen candidate kept until one is configured.");
      const limits = [];
      limits.push("elapsed: " + ("elapsed_seconds" in budget ? budget.elapsed_seconds + " s" + longer(budget.elapsed_seconds) : "no limit"));
      limits.push("final reserve: " + (budget.final_reserve ? "on" : "off"));
      for (const name of caps.budget.ceilings) limits.push(resourceShort(name) + ": " + resourceValue(name, budget.ceilings && name in budget.ceilings ? budget.ceilings[name] : null));
      row("Your limits", limits.join(" · "));
      row("Unset limits", "An unset limit means no limit. Carbon sets none for you.");
      for (const [name, label] of STEPS.slice(0, 5)) { const problem = stepProblem(name); if (problem) problems.push({ok: false, text: label + ": " + problem}); }
      if (!research.preflight.available) problems.push({ok: false, text: "Research launch: " + words(research.preflight.reason || research.preflight.status)});
      problems.push({ok: null, text: "Subnet registration is read at launch, before anything is recorded.", href: "#wallet"});
    }
    rebuild($("wizard-review"), JSON.stringify(rows), grid => { for (const [label, value] of rows) grid.append(el("dt", label), el("dd", value)); });
    rebuild($("wizard-missing"), JSON.stringify(problems), list => renderChecklist(list, problems));
  }
  function buildCeilings() {
    const box = $("budget-ceilings");
    const vocabulary = caps?.budget || launchOptions?.budget;
    if (!vocabulary || box.dataset.built) return;
    // Each ceiling is typed in the unit a person thinks in (dollars, minutes,
    // megabytes) and sent as the ledger's whole number (LP-PROD-F).
    for (const name of vocabulary.ceilings) {
      const wrap = document.createElement("div");
      const label = document.createElement("label"); label.htmlFor = "ceiling-" + name; label.textContent = resourceName(name);
      const input = document.createElement("input"); input.id = "ceiling-" + name; input.type = "number"; input.min = "0"; input.step = UNITS[name]?.step || "1"; input.placeholder = "No limit"; input.dataset.ceiling = name;
      input.dataset.draft = "1";
      if (UNITS[name]) input.dataset.unit = UNITS[name].unit;
      input.addEventListener("input", readAdvanced);
      wrap.append(label, input); box.append(wrap);
    }
    box.dataset.built = "1";
    writeAdvanced();
  }
  // What each ceiling field was last filled with, and the ledger whole number
  // it stands for: a field not typed into since keeps that exact number, so
  // editing one limit never rewrites another (LP-PROD-F).
  const ceilingsWritten = new Map();
  // Advanced inputs write into the composition; a blank field removes its key.
  function readAdvanced() {
    const budget = {};
    const whole = text => (text.trim() === "" ? undefined : Number(text));
    const elapsed = whole($("budget-elapsed").value);
    if (elapsed !== undefined) budget.elapsed_seconds = elapsed;
    if ($("budget-final-reserve").checked) budget.final_reserve = true;
    const ceilings = {};
    for (const input of document.querySelectorAll("[data-ceiling]")) {
      const name = input.dataset.ceiling;
      const written = ceilingsWritten.get(name);
      const kept = written && written.text === input.value && Number.isSafeInteger(written.ledger) && written.ledger >= 0;
      const cap = kept ? written.ledger : toLedger(name, input.value);
      if (cap !== undefined) ceilings[name] = cap;
    }
    if (Object.keys(ceilings).length) budget.ceilings = ceilings;
    composition = {...composition, budget};
    saveWizard();
    render();
  }
  function writeAdvanced() {
    const budget = composition.budget || {};
    $("budget-elapsed").value = budget.elapsed_seconds ?? "";
    $("budget-final-reserve").checked = budget.final_reserve === true;
    for (const input of document.querySelectorAll("[data-ceiling]")) {
      const name = input.dataset.ceiling;
      const ledger = budget.ceilings?.[name];
      input.value = fromLedger(name, ledger);
      ceilingsWritten.set(name, {text: input.value, ledger});
    }
  }
  function renderLaunchComposition() {
    buildCeilings();
    $("path-quick").setAttribute("aria-pressed", String(launchPath === "quick"));
    $("path-advanced").setAttribute("aria-pressed", String(launchPath === "advanced"));
    $("launch-advanced").hidden = launchPath !== "advanced";
    const availability = $("launch-availability");
    const chosen = wizard.challenge ? wizard.challenge.id : "";
    if (launchOptions && availability.dataset.built !== chosen) {
      availability.replaceChildren();
      const families = {};
      for (const family of familiesFor(chosen)) (families[family.verdict] ||= []).push(family.selector || family.id.split(".")[1]);
      for (const [verdict, names] of Object.entries(families)) researchNote(availability, "Model families · " + words(verdict) + ": " + names.join(", "));
      for (const [lane, state] of Object.entries(launchOptions.research_lanes)) researchNote(availability, "Research lane " + lane + " · " + state.availability + (state.reason ? ": " + words(state.reason) : ""));
      availability.dataset.built = chosen;
    }
    const problem = compositionProblem(composition);
    setText($("composition-summary"), describeComposition(composition) + (problem ? " · cannot launch: " + problem : ""));
    renderTemplates();
    return problem;
  }
  function readTemplates() {
    try { const value = JSON.parse(localStorage.getItem(templateKey) || "{}"); return value && typeof value === "object" && !Array.isArray(value) ? value : {}; }
    catch (_) { return null; }
  }
  function renderTemplates() {
    const templates = readTemplates();
    const pick = $("template-pick");
    const disabled = templates === null || !connected;
    const names = templates === null ? [] : Object.keys(templates).sort();
    // Each control set once per render, to its final state: no flicker.
    for (const id of ["template-name", "template-save", "template-pick"]) $(id).disabled = disabled;
    for (const id of ["template-load", "template-delete"]) $(id).disabled = disabled || !names.length;
    if (templates === null) { setText($("template-note"), "Templates are unavailable: this browser refused its storage."); return; }
    if (pick.dataset.names !== names.join("\n") && !held(pick)) {
      pick.replaceChildren(...names.map(name => { const option = document.createElement("option"); option.value = name; option.textContent = name; return option; }));
      pick.dataset.names = names.join("\n");
    }
  }
  // A template is a launch composition and nothing else: closed against the
  // launch operation's own fields, and checked against what is available now,
  // not when it was saved.
  function templateProblem(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return "it is not a launch composition";
    const fields = new Set([...(launchShape?.required || []), ...(launchShape?.optional || [])]);
    // Graphite's choices travel with a Graphite template, as launch fields.
    const carried = value.agent === GRAPHITE ? ["agent", "budget", ...GRAPHITE_FIELDS] : ["agent", "budget"];
    for (const key of Object.keys(value)) if (!carried.includes(key) || !fields.has(key)) return "it sets " + key + ", which a template cannot carry";
    const problem = compositionProblem({agent: value.agent, budget: value.budget || {}});
    if (problem || value.agent !== GRAPHITE) return problem;
    const g = graphiteFromFields(value);
    const graphite = graphiteChoiceProblem(g) || graphiteLimitsProblem(g);
    return graphite ? "Graphite: " + graphite : null;
  }
  $("path-quick").addEventListener("click", () => { launchPath = "quick"; saveWizard(); render(); });
  $("path-advanced").addEventListener("click", () => { launchPath = "advanced"; writeAdvanced(); saveWizard(); render(); });
  $("budget-elapsed").addEventListener("input", readAdvanced);
  $("wizard-max-output").addEventListener("input", () => { wizard.maxOutput = $("wizard-max-output").value; saveWizard(); render(); });
  $("budget-final-reserve").addEventListener("change", readAdvanced);
  $("template-save").addEventListener("click", () => {
    const name = $("template-name").value.trim();
    if (!name) { message("Name the template first.", true); return; }
    const graphite = composition.agent === GRAPHITE;
    const problem = compositionProblem(composition) || (graphite ? graphiteChoiceProblem() || graphiteLimitsProblem() : null);
    if (problem) { message("Not saved: " + problem + ".", true); return; }
    const templates = readTemplates();
    if (templates === null) { message("Not saved: this browser refused its storage.", true); return; }
    templates[name] = {agent: composition.agent, ...(Object.keys(composition.budget).length ? {budget: composition.budget} : {}), ...(graphite ? launchFields(graphiteFields()) : {})};
    try { localStorage.setItem(templateKey, JSON.stringify(templates)); }
    catch (_) { message("Not saved: this browser refused its storage.", true); return; }
    $("template-name").value = "";
    message("Template “" + name + "” saved.");
    render();
  });
  $("template-load").addEventListener("click", async () => {
    const name = $("template-pick").value;
    const value = (readTemplates() || {})[name];
    // Availability is read again now: the moment of choosing is this one.
    try { launchOptions = await api("/api/v1/operations/options", {}); } catch (_) { /* keep the last read */ }
    const problem = templateProblem(value);
    if (problem) { message("Template “" + name + "” not loaded: " + problem + ".", true); render(); return; }
    composition = {agent: value.agent, budget: value.budget || {}};
    // A template carries the launch agent: the choice offered for it ("none"
    // is the manual choice), with Graphite's own choices when it has them.
    const offeredNow = agentChoices();
    wizard.agentChoice = (offeredNow.find(choice => choice.launch_agent === value.agent && (value.agent !== "none" || choice.id === "manual")) || offeredNow.find(choice => choice.launch_agent === value.agent))?.id || null;
    if (value.agent === GRAPHITE) wizard.graphite = graphiteFromFields(value);
    launchPath = Object.keys(composition.budget).length ? "advanced" : "quick";
    writeAdvanced(); saveWizard();
    message("Template “" + name + "” loaded. " + describeComposition(composition) + ".");
    render();
  });
  $("template-delete").addEventListener("click", () => {
    const name = $("template-pick").value;
    const templates = readTemplates();
    if (!templates || !(name in templates)) return;
    delete templates[name];
    try { localStorage.setItem(templateKey, JSON.stringify(templates)); } catch (_) { message("Not deleted: this browser refused its storage.", true); return; }
    message("Template “" + name + "” deleted.");
    render();
  });
  // ---- Keyed operations (LP-PROD-F): practice, freeze and submit. One
  // idempotency key per request, held until its outcome is known: a retry
  // after a lost answer or a reload replays the request rather than starting
  // it twice (or meeting campaign_busy from its own first attempt). Both the
  // journey and the Tools tab send through here.
  //
  // A held key is released when the controller answers it; on a refusal
  // with no earlier attempt under it outstanding; on
  // operation_replay_conflict (the key is spent); by Discard; and when the
  // campaign's record shows how the request ended (its effect, a refusal
  // recorded since, an interruption, the campaign ending) or that it no
  // longer applies (a submit with its frozen candidate gone). A held key is
  // never carried into the next epoch's request: a submit whose answer was
  // lost but which ran is released by its submitted epoch, so the next
  // candidate's submit is a new request, not a replay of the old one.
  const operationKey = "carbon.launchpad.pending-operation.v1";
  // Slots whose request is in flight from this page: only its answer
  // releases those.
  const inFlight = new Set();
  function heldOperations() {
    let value = null;
    try { value = JSON.parse(sessionStorage.getItem(operationKey) || "null"); } catch (_) { value = null; }
    if (!value || typeof value !== "object" || Array.isArray(value)) return {};
    // The page before LP-PROD-F held one request, not one per campaign.
    if (typeof value.name === "string") return {[value.name + ":" + (value.body?.campaign || "")]: {...value, unknown: true}};
    return value;
  }
  function writeHeld(all) {
    try { sessionStorage.setItem(operationKey, JSON.stringify(all)); } catch (_) { /* the key still covers this request */ }
  }
  function holdOperation(slot, action) {
    const all = heldOperations();
    if (action) all[slot] = action; else delete all[slot];
    writeHeld(all);
  }
  // What the campaign's record showed when a request was first sent: the
  // mark its outcome is read against, on a retry as on the first answer.
  function recordMark(campaign) {
    const run = research.runs.find(item => item.id === campaign) || {};
    return {
      state: run.state || null,
      submitted: (run.journey?.submitted_epochs || []).length,
      frozen: run.journey?.frozen_awaiting_submission === true,
      experiments: (run.experiments || []).length,
      refusals: (run.refusals || []).length,
      refusal: JSON.stringify(lastRefusal(run)),
    };
  }
  // A refusal that may be this operation's: slice C names the operation a
  // refusal was for; one naming another operation is not this one's.
  function refusalOf(name, refusal) { return Boolean(refusal) && (!refusal.operation || refusal.operation === name); }
  // Whether the record shows how a held request ended, or that it no longer
  // applies, since its mark.
  // A record that could not be read (READBACK_UNAVAILABLE, or one without
  // its journey) shows nothing either way, and releases nothing.
  function heldSettled(name, mark, run) {
    if (["COMPLETED", "STOPPED", "EXPIRED"].includes(run.state)) return true;
    if (["INTERRUPTED", "RECONCILIATION_REQUIRED"].includes(run.state) && run.state !== mark.state) return true;
    const refusal = lastRefusal(run);
    if (refusal && JSON.stringify(refusal) !== mark.refusal && refusalOf(name, refusal)) return true;
    if ((run.refusals || []).length > mark.refusals) return true;
    if (name === "practice") return (run.experiments || []).length > mark.experiments;
    const journey = run.journey;
    if (!journey || typeof journey !== "object") return false;
    const submitted = (journey.submitted_epochs || []).length > mark.submitted;
    const frozen = journey.frozen_awaiting_submission === true;
    if (name === "submit") return submitted || (mark.frozen && !frozen);
    if (name === "freeze_candidate") return submitted || (!mark.frozen && frozen);
    return false;
  }
  // Each refresh: a held request the record shows ended lets its key go.
  function settleHeld() {
    const all = heldOperations();
    let changed = false;
    for (const [slot, action] of Object.entries(all)) {
      if (inFlight.has(slot) || !action || typeof action !== "object" || !action.mark) continue;
      const run = research.runs.find(item => item.id === action.body?.campaign);
      if (run && heldSettled(action.name, action.mark, run)) { delete all[slot]; changed = true; }
    }
    if (changed) writeHeld(all);
  }
  // A held request that is not a campaign's (the Library's pin, unpin, ban
  // and unban): released when the caller's own record shows it ended
  // (`ended(slot, action)`), as settleHeld does for a campaign's. Never while
  // in flight from this page.
  function releaseHeld(ended) {
    const all = heldOperations();
    let changed = false;
    for (const [slot, action] of Object.entries(all)) {
      if (inFlight.has(slot) || !action || typeof action !== "object") continue;
      if (ended(slot, action)) { delete all[slot]; changed = true; }
    }
    if (changed) writeHeld(all);
  }
  // The held request among `names` for a campaign, when one is waiting on a
  // retry or a discard (not while it is in flight), or null.
  function heldOperation(campaign, names) {
    const all = heldOperations();
    for (const name of names) {
      const slot = name + ":" + campaign;
      if (all[slot] && all[slot].unknown === true && !inFlight.has(slot)) return {name, key: all[slot].key};
    }
    return null;
  }
  function discardOperation(campaign, names) {
    const all = heldOperations();
    for (const name of names) if (!inFlight.has(name + ":" + campaign)) delete all[name + ":" + campaign];
    writeHeld(all);
    render();
  }
  // `options.send` posts the keyed body another way (the Library's own
  // routes) and `options.slot` names what the key is held for (a card, an
  // import, a plan), when it is not a campaign.
  async function keyedOperation(name, body, timeout = 20000, options = {}) {
    const slot = options.slot || name + ":" + (body.campaign || "");
    let kept = heldOperations()[slot];
    if (!kept || typeof kept !== "object" || typeof kept.key !== "string") kept = null;
    // Held, but the record shows it ended: its key is spent, and this is a
    // new request.
    const run = research.runs.find(item => item.id === body.campaign);
    if (kept && kept.mark && run && heldSettled(name, kept.mark, run)) kept = null;
    const same = Boolean(kept) && JSON.stringify(kept.body) === JSON.stringify(body);
    // A different request while an earlier one is unknown: sent as a new
    // request under a new key, and said so; the earlier one's key is let go.
    const replaced = Boolean(kept) && kept.unknown === true && !same;
    const action = same ? {...kept, mark: kept.mark || recordMark(body.campaign)} : {name, body, key: crypto.randomUUID(), unknown: false, mark: recordMark(body.campaign)};
    const earlier = action.unknown === true;
    holdOperation(slot, {...action, unknown: true});
    inFlight.add(slot);
    try {
      const keyed = {...body, idempotency_key: action.key};
      const value = options.send ? await options.send(keyed) : await api("/api/v1/operations/" + name, keyed, undefined, timeout);
      holdOperation(slot, null);
      // A retry answered: its outcome is read against the record when it was
      // first sent, which a replay of finished work already includes.
      return {ok: true, value, mark: earlier ? action.mark : null, replaced};
    } catch (error) {
      // The key already named another request: it is spent, nothing new ran.
      const spent = error.code === "operation_replay_conflict";
      const release = spent || (refused(error) && !earlier);
      if (release) holdOperation(slot, null);
      return {ok: false, error, refused: refused(error), kept: !release, spent, replaced};
    } finally { inFlight.delete(slot); }
  }
  const REPLACED = "This differs from your earlier request, whose outcome is unknown, so it went as a new request under a new key; if the earlier one started, it ran too.";
  // Why an operation is not done, as a person reads it. `text` is the
  // caller's wording of the error, when it has its own.
  function notDone(outcome, text = said(outcome.error)) {
    if (outcome.spent) return "Not sent again: an earlier request under this key was recorded with other values, so nothing new started. See the campaign's record.";
    const head = (outcome.refused ? "Refused: " : "Not confirmed: ") + text.replace(/\.$/, "");
    return head + (outcome.kept ? ". Trying again with the same values sends it under the same key: if it started, it is replayed, never run twice. Or discard it." : ".") + (outcome.replaced ? " " + REPLACED : "");
  }
  async function operate(name, body, started) {
    if (!connected || busy) return;
    busy = true; render();
    try {
      const outcome = await keyedOperation(name, body);
      if (outcome.ok) { watch(name, body.campaign, outcome.value, outcome); message(started + (outcome.replaced ? " " + REPLACED : "")); }
      // A refusal with the controller's next step, not just its code
      // (LAUNCHPAD-PAGE-USABILITY-01: a submit with no intake said only
      // "evaluation unavailable").
      else message(notDone(outcome) + (outcome.refused && outcome.error?.nextStep && !SIGNER_HELP[outcome.error.code] ?" Next: " + String(outcome.error.nextStep).replace(/\.$/, "") + "." : ""), true);
    } finally { busy = false; await refresh(); render(); }
  }
  // ---- What a started operation shows (LP-PROD-F). The controller answers
  // practice, freeze and submit once the work has started, not once it was
  // admitted or finished. The page says it started, and says it was done
  // only when the campaign's own record shows it; a refusal recorded since
  // is shown with what to do.
  const WORKING = {PRACTICING: "practice", FREEZING: "freeze_candidate", SUBMITTING: "submit"};
  const watches = new Map();
  // `sent` is keyedOperation's outcome: on a retry, the mark from its first
  // send is the baseline, so a replay of work that already finished reads as
  // done, not as "ended without the change it was for".
  function watch(name, campaign, answered, sent = {}) {
    if (!campaign) return;
    const before = research.runs.find(run => run.id === campaign) || {};
    const mark = sent.mark;
    watches.set(campaign, {
      name, since: Date.now(), settled: null, replaced: Boolean(sent.replaced),
      submitted: mark ? mark.submitted : (before.journey?.submitted_epochs || []).length,
      experiments: mark ? mark.experiments : (before.experiments || []).length,
      refusals: mark ? mark.refusals : (before.refusals || []).length,
      refusal: mark ? mark.refusal : JSON.stringify(lastRefusal(answered, before)),
    });
  }
  // Back to READY with no change of record: the projection can lag the
  // operation's thread by a refresh, so this waits before saying so.
  const SETTLE_MS = 60000;
  function watchStatus(run) {
    const entry = run && watches.get(run.id);
    if (!entry) return null;
    if (entry.settled) return entry.settled;
    // A start time, not a running clock: the line changes only when the
    // operation's state does, so it never redraws its form.
    const elapsed = "started " + new Date(entry.since).toLocaleTimeString();
    if (WORKING[run.state]) {
      const doing = {practice: "Practice trial running", freeze_candidate: "Freezing your candidate", submit: "Submitting your frozen candidate: your registration is read, then it is sent for the DEVELOPMENT comparison"}[entry.name];
      return {kind: "working", text: doing + " · " + elapsed + "." + (entry.replaced ? " " + REPLACED : "")};
    }
    const refusal = lastRefusal(run);
    if (refusal && JSON.stringify(refusal) !== entry.refusal && refusalOf(entry.name, refusal)) {
      return {kind: "refused", text: "Not done: " + words(refusal.code) + "." + (refusal.next_action ? " " + refusal.next_action : ""), refusal};
    }
    const recorded = run.refusals || [];
    if (recorded.length > entry.refusals) {
      const last = recorded[recorded.length - 1] || {};
      return {kind: "refused", text: "Not done: " + words(last.reason || last.status || "refused") + "." + (last.detail ? " " + last.detail : "")};
    }
    if (entry.name === "submit" && (run.journey?.submitted_epochs || []).length > entry.submitted) {
      return {kind: "done", text: "Submitted for the DEVELOPMENT comparison. The independent result appears below."};
    }
    if (entry.name === "freeze_candidate" && run.journey?.frozen_awaiting_submission === true) {
      return {kind: "done", text: "Candidate frozen for this epoch. Submit it under Submission."};
    }
    if (entry.name === "practice" && (run.experiments || []).length > entry.experiments) {
      return {kind: "done", text: "Practice trial finished. Its result is under Experiments."};
    }
    if (["INTERRUPTED", "RECONCILIATION_REQUIRED"].includes(run.state)) {
      return {kind: "refused", text: "Interrupted before it finished (" + words(run.state).toLowerCase() + "). Reconcile the campaign, then try again."};
    }
    if (Date.now() - entry.since < SETTLE_MS) return {kind: "working", text: "Finishing: waiting for the campaign's record · " + elapsed + "."};
    return {kind: "unclear", text: "It ended without the change it was for (" + words(run.state).toLowerCase() + "). Any reason is in the campaign's Logs and journal."};
  }
  // Each refresh: an operation that ended says so once, in the page's message.
  function settleWatches() {
    for (const [id, entry] of watches) {
      if (entry.settled) continue;
      const run = research.runs.find(item => item.id === id);
      if (!run) continue;
      const status = watchStatus(run);
      if (status && status.kind !== "working") {
        entry.settled = status;
        message(status.text, status.kind === "refused");
      } else if (Date.now() - entry.since > 2 * 3600 * 1000) {
        entry.settled = {kind: "unclear", text: "No change of record two hours after it started: see the campaign's Logs."};
      }
    }
  }
  async function researchAction(id, action) {
    if (!connected || busy) return;
    busy = true; render();
    try {
      if (action === "export") download(await api("/api/v1/research/" + id), "carbon-research-" + id + ".json");
      else await api("/api/v1/research/" + id + "/" + action, {});
      message("Research request acknowledged. Check observed state and cleanup in the campaign.");
    } catch (error) {
      // The controller's next step when it gives one: for a Reconcile, A's
      // step for a model call it would not settle (LP-PROD-W2).
      message("Research request unresolved: " + error.message + (error.nextStep ? ". Next: " + error.nextStep.replace(/\.$/, "") + "." : ""), true);
    }
    finally { busy = false; await refresh(); render(); }
  }
  $("research-launch").addEventListener("click", () => launchResearch());
  // The one launch: the wizard's button and the Launchpad's both call it.
  async function launchResearch() {
    if (!connected || busy || storageError || !research.preflight.available) return;
    const problem = stepProblem("review");
    if (problem) { message("Not launched: " + problem, true); return; }
    const entry = challengeEntry(wizard.challenge);
    // The body is always the wizard's current choices, with the review the
    // controller states now. The key is kept from an attempt whose outcome is
    // unknown, so the controller replays (or refuses as a conflict) a launch
    // it already recorded instead of starting a second one (LP-PROD-F).
    const earlier = Boolean(pendingResearch?.unknown);
    // The Challenge is always sent, exactly: there is no default Challenge.
    pendingResearch = {key: pendingResearch?.key || crypto.randomUUID(), unknown: true, body: {profile: research.preflight.profile, agent: composition.agent, challenge: entry.challenge_id, challenge_version: entry.version}};
    if (Object.keys(composition.budget).length) pendingResearch.body.budget = composition.budget;
    // A feedback mode only when the Challenge offers it and it is not FULL.
    if (wizard.feedbackMode && wizard.feedbackMode !== "FULL" && (entry.setup_offers?.feedback_modes || []).includes(wizard.feedbackMode)) pendingResearch.body.feedback_mode = wizard.feedbackMode;
    // The chosen provider and model, when the agent calls one and the launch
    // carries them; the key file stays in the runner profile. With none
    // chosen here, the controller runs the model chosen in setup.
    const provider = launchModel()?.provider;
    if (provider) {
      pendingResearch.body.model_provider = provider.id;
      pendingResearch.body.model = wizard.model;
      // The output cap only when the miner set one: blank is the default.
      const cap = outputCap();
      if (cap && cap.value !== null) pendingResearch.body.model_settings = {max_output_tokens: cap.value};
    }
    // Graphite's mode, research share, plan, hunt and limits: each where its
    // mode uses it, and only as the launch operation declares it.
    if (composition.agent === GRAPHITE) Object.assign(pendingResearch.body, launchFields(graphiteFields()));
    if (research.preflight.review_digest) pendingResearch.body.review_digest = research.preflight.review_digest;
    // Held before it is sent: in flight, its outcome is unknown until answered.
    try { sessionStorage.setItem(researchKey, JSON.stringify(pendingResearch)); }
    catch (_) { storageError = true; pendingResearch = null; render(); return; }
    busy = true; render();
    try {
      const run = await api("/api/v1/research", pendingResearch.body, pendingResearch.key);
      forgetLaunch();
      message("Research launch recorded. Runtime preflight and actual outcome appear in the campaign.");
      wizard.step = "challenge"; saveWizard();
      if (run && run.id) location.hash = campaignHref(run.id);
    } catch (error) {
      if (error.code === "research_launch_replay_conflict") {
        // The key already started a campaign, with other choices: that one
        // stands, and is listed. The key is spent.
        forgetLaunch();
        message("Your earlier launch was recorded, with the choices it had then: it is listed under My Campaigns. Nothing new was launched.", true);
      } else if (refused(error) && !earlier) {
        // Refused: nothing was recorded, and no earlier attempt is outstanding.
        forgetLaunch();
        message("Research launch refused: " + said(error) + ". Nothing was recorded. Fix it and launch again.", true);
      } else {
        message((refused(error) ? "Research launch refused: " + said(error) + ". An earlier attempt may still have been recorded, so its key is kept" : "Research launch not confirmed: " + said(error) + ". It may have been recorded, so its key is kept") + ": retry sends your current choices under it, never a second campaign. Or discard it.", true);
      }
    }
    finally { busy = false; await refresh(); render(); }
  }
  function forgetLaunch() {
    try { sessionStorage.removeItem(researchKey); } catch (_) { /* nothing held */ }
    pendingResearch = null;
  }
  // The research surface (research_view.js) reads this page's state and
  // calls its operations through this one bridge; it holds none of its own.
  window.CarbonControlCenter = {
    api, el, pill, details, link, message, when,
    state: () => ({connected, busy, caps, research, setupState, wizard, composition, launchOptions, pendingResearch, operations: operationsListed}),
    // A redraw the page did not ask for (a read that finished): drawn under
    // the live-region rules, so nothing under a person's hand is replaced.
    redraw: () => quietly(render),
    // Graphite's words and choices, shared with the research surface.
    graphite: {modeLabel: graphiteMode, stageLabel: graphiteStage, now: graphiteNow, summary: graphiteSummary, usd, agentChoices},
    challengeEntry, agentEntry, selectedProvider, describeComposition, journey,
    launch: launchResearch, discardLaunch,
    launchProblem: () => !connected ? "Connect this browser first." : storageError ? "Browser retry storage is unavailable; launch is disabled to preserve duplicate protection." : stepProblem("review"),
    goWizard(step) { if (STEPS.some(([name]) => name === step)) { wizard.step = step; saveWizard(); } location.hash = "#launch"; render(); },
    researchAction, renderCampaigns, renderJourneyPractice, renderJourneySubmission,
    evaluationFor, evaluationNote,
    // Live regions, refusals and keyed operations (LP-PROD-F), shared with
    // the research surface and its Tools tab so all three behave alike.
    held, rebuild, quietly, setText, sent, refused,
    keyedOperation, heldOperation, discardOperation, releaseHeld, watch, watchStatus, notDone,
    lastRefusal, refusalNote, campaignHref, budgetParts, resourceShort, resourceValue, usageTable,
    onRender(hook) { renderHooks.push(hook); },
  };
  buildNavigation();
  show();
  setInterval(refresh, 1500);
  if (linkToken !== null) connectFromLink(linkToken);
})();
