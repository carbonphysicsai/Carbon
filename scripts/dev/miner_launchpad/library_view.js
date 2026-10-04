"use strict";
// Carbon's Library (OWNER-GRAPHITE-MINER-01, GRAPHITE-MINER-S5).
//
// The literature Graphite reads and the plans it builds from: the shared card
// pack that ships with Carbon, and the miner's own private library (cards
// hunted from arXiv or imported as text, the plans, and the pins and bans that
// steer the ranking). Every card shows where it came from and that it is
// UNCHECKED: Carbon has not checked its claims. Search ranks cards for one
// Challenge as the agent's own search does, with its reasons.
//
// Reads and writes are the controller's own operations, the ones an MCP
// client calls as carbon_library_* and carbon_plan_*: sent to
// /api/v1/library/<verb> and /api/v1/plans/<verb>, or to the operations door
// when the controller has no such route, with the fields the operations
// declare (slice S4). A write is sent under an idempotency key kept until the
// controller answers it, or until the library shows its effect, so a retry
// after a lost answer replays it rather than repeating it. A plan is saved in
// Graphite's plan schema (carbon.graphite.miner-plan.v1, slice S3's rule).
//
// Every piece of text from the controller is set as text, never parsed as
// HTML. Nothing loads from the internet.
(() => {
  const CC = window.CarbonControlCenter;
  if (!CC) return;
  const {el} = CC;
  const $ = id => document.getElementById(id);
  const PLAN_SCHEMA = "carbon.graphite.miner-plan.v1";
  // The plan rule's shape bounds (S3's plan.py), checked here first so a
  // plan that cannot be saved says why before anything is sent. The
  // controller checks again and is the authority.
  const PLAN = {hypotheses: 8, cites: 12, pins: 64, text: 2000, recipeBytes: 16384, cardId: /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/};
  // The longest text an import carries (library_import).
  const IMPORT_MAX = 20000;
  // The Library is read again this often while it (or the Build plan
  // picker) is on screen: a hunt in a running campaign adds cards.
  const POLL_MS = 10000;
  // The cards a search asks for (library_search's card_limit, 1 to 50).
  const SEARCH_LIMIT = 20;
  // ---- The operations, with the fields each takes (S4's operations
  // table). `fields` are sent when given; `context` only when the
  // operation's listing declares it.
  const OPS = {
    library_search: {route: "/api/v1/library/search", fields: ["query"], context: ["challenge", "challenge_version", "card_limit"]},
    library_card: {route: "/api/v1/library/card", fields: ["card_id"]},
    library_list: {route: "/api/v1/library/list", fields: []},
    plan_list: {route: "/api/v1/plans/list", fields: []},
    plan_get: {route: "/api/v1/plans/get", fields: ["plan"]},
    library_pin: {route: "/api/v1/library/pin", fields: ["card_id"]},
    library_unpin: {route: "/api/v1/library/unpin", fields: ["card_id"]},
    library_ban: {route: "/api/v1/library/ban", fields: ["card_id"]},
    library_unban: {route: "/api/v1/library/unban", fields: ["card_id"]},
    library_import: {route: "/api/v1/library/import", fields: ["title", "text"]},
    plan_edit: {route: "/api/v1/plans/edit", fields: ["plan_document"]},
  };
  // What each curation write leaves in the library's curation, once done.
  const EFFECT = {
    library_pin: (curation, id) => curation.pins.includes(id),
    library_unpin: (curation, id) => !curation.pins.includes(id),
    library_ban: (curation, id) => curation.bans.includes(id),
    library_unban: (curation, id) => !curation.bans.includes(id),
  };
  const ORIGINS = {shared: ["Shared pack", "pill-dev"], miner_hunt: ["Your hunt", "pill-open"], miner_import: ["Your import", "pill-open"]};
  const TABS = [["cards", "Cards", "#library"], ["import", "Import", "#library/import"], ["plans", "Plans", "#library/plans"]];

  // The Library's own state. Never a token or key; nothing is stored.
  const lib = {
    challenge: null,
    search: null, searching: false,
    list: null, listError: null, listAt: 0, listLoading: false,
    plans: null, plansError: null, plansAt: 0, plansLoading: false,
    docs: new Map(),
    // Every card read so far, by id: titles and origins for pins, bans and
    // cites; and the cards read one by one, with any error.
    cards: new Map(), cardReads: new Set(), cardErrors: {},
    curation: {pins: [], bans: [], digest: null},
    // The plan editor's drafts, one per plan being edited (by its digest)
    // and one for a new plan ("new"): opening another keeps each.
    drafts: new Map(), draftVersion: 0,
    note: null, importNote: null, writing: false,
  };

  // ---- Small helpers, all text. ----
  function words(value) { return String(value ?? "").replaceAll("_", " "); }
  function para(parent, text, className) { const p = el("p", text, className); parent.append(p); return p; }
  function button(label, className, onClick) {
    const b = el("button", label, className); b.type = "button";
    if (onClick) b.addEventListener("click", onClick);
    return b;
  }
  function anchor(label, href, className = "link") { const a = el("a", label, className); a.href = href; return a; }
  function short(digest) { const text = String(digest || ""); return text.length > 14 ? text.slice(0, 12) + "…" : text; }
  function listOf(value, ...names) {
    if (Array.isArray(value)) return value;
    for (const name of names) if (Array.isArray(value?.[name])) return value[name];
    return [];
  }
  function idOf(item) {
    if (typeof item === "string") return item;
    if (item && typeof item === "object") return String(item.card_id ?? "");
    return "";
  }
  function title(id) { return lib.cards.get(id)?.title || id; }
  // One part of a region, redrawn alone when what it shows changed and
  // nothing holds it (app.js's live-region rules).
  function part(parent, name, key, build, className = "", tag = "div") {
    let node = null;
    for (const child of parent.children) if (child.dataset.part === name) { node = child; break; }
    if (!node) { node = el(tag, undefined, className); node.dataset.part = name; parent.append(node); }
    CC.rebuild(node, key, build);
    return node;
  }

  // ---- The controller's operations. ----
  // The operation's listing: null before the controller's operations are
  // read, false when the controller lists them and this is not one.
  function shape(name) {
    const listed = CC.state().operations;
    if (!Array.isArray(listed)) return null;
    return listed.find(op => op.operation === name) || false;
  }
  function offered(name) { return shape(name) !== false; }
  function declared(name) {
    const op = shape(name);
    return op ? new Set([...(op.required || []), ...(op.optional || [])]) : null;
  }
  function request(name, values) {
    const op = OPS[name];
    const known = declared(name);
    const body = {};
    for (const field of op.fields) if (values[field] !== undefined) body[field] = values[field];
    if (known) for (const field of op.context || []) {
      if (!known.has(field)) continue;
      if (field === "challenge" && lib.challenge) body.challenge = lib.challenge.id;
      if (field === "challenge_version" && lib.challenge?.version) body.challenge_version = lib.challenge.version;
      if (field === "card_limit") body.card_limit = SEARCH_LIMIT;
    }
    return body;
  }
  // The operation's own route, or the operations door when the controller
  // has no such route: a route it does not have ran nothing.
  async function post(name, body, timeout = 15000) {
    try { return await CC.api(OPS[name].route, body, undefined, timeout); }
    catch (error) {
      if (error.status === 404 && error.code === "route_not_found") return CC.api("/api/v1/operations/" + name, body, undefined, timeout);
      throw error;
    }
  }
  function read(name, values, timeout) { return post(name, request(name, values), timeout); }
  // What to do next, from the controller's own refusal, when it names it.
  function nextOf(error) { return error?.nextStep ? " Next: " + String(error.nextStep).replace(/\.$/, "") + "." : ""; }
  // A write, under its idempotency key when the operation takes one.
  async function write(name, values, slot) {
    if (lib.writing || !CC.state().connected) return null;
    lib.writing = true; CC.redraw();
    try {
      const body = request(name, values);
      if (declared(name)?.has("idempotency_key")) {
        return await CC.keyedOperation(name, body, 20000, {send: value => post(name, value, 20000), slot: name + ":" + slot});
      }
      try { return {ok: true, value: await post(name, body, 20000)}; }
      catch (error) { return {ok: false, error, refused: CC.refused(error), kept: false}; }
    } finally { lib.writing = false; CC.redraw(); }
  }
  function failed(outcome) { return CC.notDone(outcome) + nextOf(outcome.error); }

  // ---- Reading the controller's answers. ----
  function cardOf(item) {
    if (!item || typeof item !== "object") return null;
    const card = item.card && typeof item.card === "object" ? item.card : item;
    return typeof card.card_id === "string" && card.card_id ? card : null;
  }
  function curationOf(value) {
    const c = value?.curation;
    if (!c || typeof c !== "object" || !Array.isArray(c.pins) || !Array.isArray(c.bans)) return null;
    return {pins: c.pins.map(idOf).filter(Boolean), bans: c.bans.map(idOf).filter(Boolean), digest: typeof c.digest === "string" ? c.digest : null};
  }
  function remember(cards) { for (const card of cards) if (card) lib.cards.set(card.card_id, {...(lib.cards.get(card.card_id) || {}), ...card}); }
  // library_list: the shared pack's state, the private library's snapshot,
  // the imports waiting for the Reader and how many plans. It lists no
  // private card: a search finds those beside the shared pack.
  function listFrom(value) {
    return {
      shared: value?.shared_pack && typeof value.shared_pack === "object" ? value.shared_pack : null,
      snapshot: typeof value?.private_snapshot === "string" ? value.private_snapshot : null,
      pending: listOf(value?.pending_imports).filter(item => item && typeof item === "object"),
      plans: Array.isArray(value?.plans) ? value.plans.length : null,
    };
  }
  function planOf(value) {
    const doc = value?.plan;
    return doc && typeof doc === "object" && !Array.isArray(doc) ? doc : null;
  }
  // The curation, as the library states it now; and a held pin, unpin, ban
  // or unban whose effect it shows is let go: that request ended, so a later
  // one is a new request under a new key, never a replay of the old answer.
  function setCuration(curation) {
    lib.curation = curation;
    CC.releaseHeld?.((slot, action) => {
      const test = EFFECT[action.name];
      const id = action.body?.card_id;
      return Boolean(test) && slot === action.name + ":" + id && typeof id === "string" && test(curation, id);
    });
  }

  // ---- Loading. Reads run in the background and redraw under the
  // live-region rules: a refresh never replaces what a person is typing.
  const due = (at, force) => force || Date.now() - at >= POLL_MS;
  async function loadList(force = false) {
    if (lib.listLoading || !CC.state().connected || !offered("library_list") || !due(lib.listAt, force)) return;
    lib.listLoading = true;
    try {
      const value = await read("library_list", {});
      lib.list = listFrom(value); lib.listError = null;
      const curation = curationOf(value);
      if (curation) setCuration(curation);
    } catch (error) { lib.listError = error.message; }
    finally { lib.listLoading = false; lib.listAt = Date.now(); CC.redraw(); }
  }
  async function loadPlans(force = false) {
    if (lib.plansLoading || !CC.state().connected || !offered("plan_list") || !due(lib.plansAt, force)) return;
    lib.plansLoading = true;
    try {
      lib.plans = listOf(await read("plan_list", {}), "plans").filter(item => item && typeof item.digest === "string");
      lib.plansError = null;
    } catch (error) { lib.plansError = error.message; }
    finally { lib.plansLoading = false; lib.plansAt = Date.now(); CC.redraw(); }
  }
  // A plan is stored by its digest, so it never changes: read once.
  function planState(digest) {
    if (!digest) return {doc: null, error: null};
    if (shape("plan_get") === false) return {doc: null, error: "plan_get_not_offered_by_this_controller"};
    let entry = lib.docs.get(digest);
    if (!entry) { entry = {doc: null, error: null, at: 0, loading: false}; lib.docs.set(digest, entry); }
    if (!entry.doc && !entry.loading && CC.state().connected && offered("plan_get") && due(entry.at, !entry.at)) {
      entry.loading = true;
      read("plan_get", {plan: digest}).then(value => {
        entry.doc = planOf(value); entry.error = entry.doc ? null : "plan_unreadable";
        for (const h of listOf(entry.doc?.hypotheses)) for (const cite of listOf(h?.cites)) if (cite && typeof cite === "object" && idOf(cite) && !lib.cards.has(idOf(cite))) lib.cards.set(idOf(cite), {card_id: idOf(cite), origin: cite.origin});
      }, error => { entry.error = error.message; }).finally(() => { entry.loading = false; entry.at = Date.now(); CC.redraw(); });
    }
    return entry;
  }
  async function search(query) {
    if (lib.searching || !CC.state().connected) return;
    lib.searching = true; CC.redraw();
    const challenge = lib.challenge;
    try {
      const value = await read("library_search", {query}, 20000);
      const results = listOf(value, "cards").map(cardOf).filter(Boolean);
      remember(results);
      lib.search = {query, challenge, results, error: null, next: null};
    } catch (error) {
      lib.search = {query, challenge, results: [], error: CC.refused(error) ? "Refused: " + words(error.message) : "Not answered: " + words(error.message), next: error.nextStep || null};
    } finally { lib.searching = false; CC.redraw(); }
  }

  // ---- Routing: #library, #library/import, #library/plans[/<digest>|/new],
  // #library/card/<id>. Read after app.js has taken any session link from
  // the address, and never stored here.
  function route() {
    const parts = location.hash.replace(/^#\/?/, "").split("/").map(item => { try { return decodeURIComponent(item); } catch (_) { return item; } });
    if (parts[0] !== "library") return null;
    if (parts[1] === "card" && parts[2]) return {tab: "cards", card: parts[2], plan: ""};
    const tab = ["cards", "import", "plans"].includes(parts[1]) ? parts[1] : "cards";
    return {tab, card: "", plan: tab === "plans" ? parts[2] || "" : ""};
  }
  // The Challenges a search ranks for and a new plan is for: the
  // implemented ones, the wizard's choice first.
  function chooseChallenge() {
    const s = CC.state();
    const offeredHere = (s.caps?.challenges || []).filter(entry => entry.implemented);
    const known = item => item && offeredHere.some(entry => entry.challenge_id === item.id && entry.version === item.version);
    if (known(lib.challenge)) return offeredHere;
    const wanted = s.wizard?.challenge;
    const first = known(wanted) ? wanted : offeredHere.find(entry => entry.selectable) || offeredHere[0];
    lib.challenge = first ? {id: first.challenge_id ?? first.id, version: first.version} : null;
    return offeredHere;
  }
  function challengeSelect(id, challenges, value, onChange) {
    const select = el("select"); select.id = id;
    for (const entry of challenges) { const option = el("option", entry.title + " · v" + entry.version); option.value = JSON.stringify({id: entry.challenge_id, version: entry.version}); select.append(option); }
    if (value) select.value = JSON.stringify({id: value.id, version: value.version});
    select.addEventListener("change", () => {
      let chosen = null;
      try { chosen = JSON.parse(select.value); } catch (_) { chosen = null; }
      CC.sent(select); select.blur();
      onChange(chosen);
    });
    return select;
  }

  // ---- Cards. ----
  function originPill(card) {
    const [label, kind] = ORIGINS[card.origin] || [card.origin ? words(card.origin) : "Origin not stated", "pill-need"];
    const p = CC.pill(label, kind); p.dataset.origin = card.origin || "";
    return p;
  }
  // Served UNCHECKED: a card says what a paper claims, not that it holds.
  function checkPill(card) {
    const status = typeof card.check_status === "string" && card.check_status ? card.check_status : "UNCHECKED";
    const p = CC.pill(words(status), "pill-wait"); p.dataset.check = status;
    p.title = "Carbon has not checked this card's claims.";
    return p;
  }
  function scoreText(score) {
    if (typeof score !== "number" || !Number.isFinite(score)) return null;
    return Number.isInteger(score) && score >= 0 && score <= 3 ? "Relevance " + score + " of 3" : "Score " + String(Math.round(score * 1000) / 1000);
  }
  function provenance(value) {
    if (value === undefined || value === null || value === "") return null;
    if (typeof value === "string") return value;
    if (typeof value === "object") return Object.entries(value).filter(([, v]) => v !== null && v !== undefined && v !== "" && typeof v !== "object").map(([k, v]) => words(k) + " " + v).join(" · ");
    return String(value);
  }
  function cardItem(parent, card, curate = true) {
    const item = el("article", undefined, "lib-card"); item.dataset.card = card.card_id;
    const top = el("div", undefined, "lib-card-head");
    top.append(el("h3", card.title || card.card_id));
    const pills = el("div", undefined, "lib-pills");
    pills.append(originPill(card), checkPill(card));
    const score = scoreText(card.score);
    if (score) pills.append(CC.pill(score, "pill-next"));
    // Buildable under the Challenge's contract (a plan input), or a
    // capability request candidate instead, as the ranking flags it.
    if (card.capability_request_candidate === true) { const p = CC.pill("Not buildable here: a capability request candidate", "pill-need"); p.dataset.buildable = "no"; pills.append(p); }
    else if (card.plan_input === true) { const p = CC.pill("Buildable under the contract", "pill-done"); p.dataset.buildable = "yes"; pills.append(p); }
    top.append(pills);
    item.append(top);
    const grid = el("dl", undefined, "lib-facts");
    const fact = (label, value) => { if (value === undefined || value === null || value === "") return; grid.append(el("dt", label), el("dd", typeof value === "string" ? value : JSON.stringify(value))); };
    fact("Technique", card.technique);
    fact("Claimed effect", card.claimed_effect);
    fact("Data regime", card.data_regime);
    fact("Cost", card.cost);
    fact("Code", card.code_available === true ? "available" : card.code_available === false ? "not available" : card.code_available);
    fact("Applicability", card.applicability);
    fact("Source", provenance(card.provenance));
    if (grid.children.length) item.append(grid);
    const reasons = listOf(card.reasons).filter(reason => typeof reason === "string" && reason);
    if (reasons.length) {
      const why = el("ul", undefined, "lib-reasons"); why.setAttribute("aria-label", "Why it ranks here");
      for (const reason of reasons) why.append(el("li", reason));
      item.append(el("p", "Why it ranks here", "eyebrow"), why);
    }
    if (card.abstract) {
      const box = el("details"); box.append(el("summary", "Abstract"), el("p", card.abstract, "lib-abstract"));
      item.append(box);
    }
    const foot = el("div", undefined, "lib-card-foot");
    foot.append(el("code", card.card_id, "lib-id"));
    if (curate) for (const action of ["pin", "ban"]) {
      const b = button(action === "pin" ? "Pin" : "Ban", "", () => curate_(action, card.card_id));
      b.dataset.curate = action; b.dataset.card = card.card_id;
      foot.append(b);
    }
    item.append(foot);
    parent.append(item);
    return item;
  }
  // Pin and Ban, patched in place on every draw: their state follows the
  // curation without redrawing the card under a person's hand.
  function patchCuration(root) {
    const s = CC.state();
    for (const b of root.querySelectorAll("button[data-curate]")) {
      b.disabled = !s.connected || lib.writing;
      // A pinned or banned list's own button says Unpin or Unban, always.
      if (b.dataset.listed) continue;
      const id = b.dataset.card;
      const on = (b.dataset.curate === "pin" ? lib.curation.pins : lib.curation.bans).includes(id);
      const text = b.dataset.curate === "pin" ? (on ? "Pinned · unpin" : "Pin") : (on ? "Banned · unban" : "Ban");
      CC.setText(b, text);
      b.setAttribute("aria-pressed", String(on));
    }
  }
  async function curate_(action, id) {
    const on = (action === "pin" ? lib.curation.pins : lib.curation.bans).includes(id);
    const name = "library_" + (on ? "un" : "") + action;
    const outcome = await write(name, {card_id: id}, id);
    if (!outcome) return;
    if (outcome.ok) {
      const curation = curationOf(outcome.value);
      if (curation) setCuration(curation);
      else {
        const list = action === "pin" ? "pins" : "bans";
        setCuration({...lib.curation, [list]: on ? lib.curation[list].filter(item => item !== id) : [...lib.curation[list], id]});
      }
      lib.note = {kind: "done", text: {library_pin: "Pinned: Graphite's Planner must consider " + title(id) + ".", library_unpin: "Unpinned " + title(id) + ".", library_ban: "Banned: " + title(id) + " is no longer served to Graphite or offered here.", library_unban: "Unbanned " + title(id) + "."}[name]};
      CC.message(lib.note.text);
      // The search and the library, as they stand now.
      if (lib.search) search(lib.search.query);
      loadList(true);
    } else {
      lib.note = {kind: "refused", text: failed(outcome)};
      CC.message(lib.note.text, true);
    }
  }
  function drawCards(panel, r, s) {
    const challenges = chooseChallenge();
    titles([...lib.curation.pins, ...lib.curation.bans]);
    part(panel, "context", JSON.stringify([challenges.map(entry => [entry.challenge_id, entry.version, entry.title]), lib.challenge]), box => {
      const label = el("label", "Rank for this Challenge"); label.htmlFor = "library-challenge";
      const select = challengeSelect("library-challenge", challenges, lib.challenge, chosen => {
        lib.challenge = chosen;
        if (lib.search) search(lib.search.query); else CC.redraw();
      });
      box.append(label, select);
      para(box, "Ranks each card for this Challenge's public contract: what it is about, and whether it can be built under the contract, as Graphite's own search does. Your pins and bans steer it; only public material and your own practice results ever inform it.", "hint");
    }, "lib-context panel");
    // The search box is drawn once and never redrawn: what is typed stays.
    part(panel, "search", "form", box => {
      const form = el("form", undefined, "lib-search"); form.setAttribute("role", "search");
      const label = el("label", "Search the shared pack and your library"); label.htmlFor = "library-query";
      const input = el("input"); input.id = "library-query"; input.type = "search"; input.autocomplete = "off"; input.spellcheck = false; input.maxLength = 200;
      input.placeholder = "A technique, an effect, a data regime…";
      const go = el("button", "Search", "primary"); go.type = "submit"; go.id = "library-search-go";
      const row = el("div", undefined, "inline"); row.append(input, go);
      form.append(label, row);
      form.addEventListener("submit", event => {
        event.preventDefault();
        const query = input.value.trim();
        CC.sent(input);
        if (!query) { lib.search = {query: "", challenge: lib.challenge, results: [], error: "Type what to search for.", next: null}; CC.redraw(); return; }
        search(query);
      });
      box.append(form);
    }, "lib-search-part");
    // One card, opened from a plan's citation: read once when not known yet.
    if (r.card) readCard(r.card);
    const one = part(panel, "card", r.card ? JSON.stringify([r.card, lib.cards.get(r.card) || null, lib.cardErrors[r.card] || null]) : "", box => { if (r.card) drawOneCard(box, r.card); }, "lib-one panel");
    one.hidden = !r.card;
    patchCuration(one);
    // Banned cards are never served: one shown by mistake is not shown here.
    const shown = lib.search ? lib.search.results.filter(card => !lib.curation.bans.includes(card.card_id)) : [];
    const results = part(panel, "results", JSON.stringify([lib.search && [lib.search.query, lib.search.challenge, lib.search.error, lib.search.next], shown, lib.searching]), box => {
      if (lib.searching) { para(box, "Searching…", "hint"); return; }
      if (!lib.search) { para(box, "Search to see ranked cards, from the shared pack and your own hunts and imports. Every card is UNCHECKED: Carbon has not checked its claims.", "hint"); return; }
      if (lib.search.error) { para(box, lib.search.error + (lib.search.next ? ". Next: " + lib.search.next : ""), "reason"); return; }
      const challenge = (CC.state().caps?.challenges || []).find(entry => entry.challenge_id === lib.search.challenge?.id);
      para(box, shown.length + " card" + (shown.length === 1 ? "" : "s") + " for “" + lib.search.query + "”" + (challenge ? ", ranked for " + challenge.title : "") + ".", "status-line");
      for (const card of shown) cardItem(box, card);
    }, "lib-results");
    patchCuration(results);
    const curation = part(panel, "curation", JSON.stringify([lib.curation, [...lib.curation.pins, ...lib.curation.bans].map(id => [id, lib.cards.get(id)?.title || null, lib.cards.get(id)?.origin || null])]), box => drawCuration(box), "lib-curation panel");
    patchCuration(curation);
    part(panel, "mine", JSON.stringify([lib.list, lib.listError]), box => drawMine(box), "lib-mine panel");
  }
  // A banned card is never served (card_banned): it is named by its id, or
  // by the title a search showed before it was banned.
  function readCard(id) {
    if (lib.cards.get(id)?.title || lib.cardReads.has(id) || lib.curation.bans.includes(id) || !offered("library_card")) return;
    lib.cardReads.add(id);
    read("library_card", {card_id: id}).then(value => {
      const found = cardOf(value);
      if (found) remember([found]); else lib.cardErrors[id] = "card_unreadable";
    }, error => { lib.cardErrors[id] = error.message; }).finally(() => CC.redraw());
  }
  // Titles for the pinned, banned and cited cards this view names, read once.
  function titles(ids) { for (const id of ids) if (id) readCard(id); }
  function drawOneCard(box, id) {
    const card = lib.cards.get(id);
    if (card && card.title) { cardItem(box, card); return; }
    const error = lib.cardErrors[id];
    para(box, error ? "Card " + id + " could not be read: " + words(error) + "." : "Reading card " + id + "…", error ? "reason" : "hint");
  }
  function curationRow(list, id, action) {
    const known = lib.cards.get(id);
    const item = el("li");
    item.append(el("span", known?.title || id));
    if (known?.origin) item.append(originPill(known));
    const b = button(action === "pin" ? "Unpin" : "Unban", "", () => curate_(action, id));
    b.dataset.curate = action; b.dataset.card = id; b.dataset.listed = "1";
    item.append(b);
    list.append(item);
  }
  function drawCuration(box) {
    box.append(el("h2", "Your pins and bans"));
    para(box, "Graphite's Planner must consider every card you pin; a plan that leaves one out is refused. A card you ban is never served to Graphite, offered here or cited by a plan.", "hint");
    for (const [action, heading, ids] of [["pin", "Pinned", lib.curation.pins], ["ban", "Banned", lib.curation.bans]]) {
      box.append(el("h3", heading + " · " + ids.length));
      if (!ids.length) { para(box, action === "pin" ? "Nothing pinned." : "Nothing banned.", "hint"); continue; }
      const list = el("ul", undefined, "lib-curated"); list.dataset.list = action;
      for (const id of ids) curationRow(list, id, action);
      box.append(list);
    }
  }
  // What the library holds, as library_list states it: the shared pack, the
  // private library's snapshot, imports waiting and plans. Its own cards are
  // found by search; no count is shown that the controller did not give.
  function drawMine(box) {
    box.append(el("h2", "Your library"));
    if (lib.listError) { para(box, "Your library could not be read: " + words(lib.listError) + ". It is read again shortly.", "reason"); return; }
    if (!lib.list) { para(box, "Reading your library…", "hint"); return; }
    const shared = lib.list.shared;
    if (shared && shared.available === false) {
      para(box, "The shared card pack is missing or differs from its pinned digest (" + words(shared.code || "literature_pack_missing") + "). Next: re-run the installer with --update, then reconnect.", "reason");
    } else if (shared) {
      const count = typeof shared.cards === "number" ? shared.cards : null;
      para(box, "Shared pack" + (count !== null ? ": " + count + " cards" : "") + ", frozen, shipped with Carbon" + (typeof shared.digest === "string" ? " (" + short(shared.digest) + ")" : "") + ". arXiv titles and abstracts are CC0 descriptive metadata; the other fields are Carbon's extraction.", "hint");
    }
    para(box, "Your own cards, found by your hunts or extracted from text you imported, live on this machine, owner-only, and are never uploaded. Search above finds them beside the shared pack, labelled Your hunt or Your import." + (lib.list.snapshot ? " Private library snapshot " + short(lib.list.snapshot) + "." : ""), "hint");
    const waiting = lib.list.pending.length;
    const imports = para(box, (waiting ? waiting + " import" + (waiting === 1 ? "" : "s") + " waiting for a launch that hunts. " : "No import waiting. "), "hint");
    imports.append(anchor("Import text", "#library/import"));
    if (lib.list.plans !== null) {
      const plans = para(box, lib.list.plans + " plan" + (lib.list.plans === 1 ? "" : "s") + " in your library. ", "hint");
      plans.append(anchor("Your plans", "#library/plans"));
    }
  }

  // ---- Import. ----
  function drawImport(panel) {
    part(panel, "form", "form", box => {
      box.append(el("h2", "Import your own text"));
      para(box, "Paste a paper's text, or your own notes. The next Research or Full launch with the hunt turned on reads it: its Reader extracts it into a card, on your model and budget, and it joins your private library marked as your import. Until then it waits here. PDF import is not offered yet: paste the text.", "hint");
      const form = el("form", undefined, "lib-import");
      const titleLabel = el("label", "Title"); titleLabel.htmlFor = "library-import-title";
      const titleInput = el("input"); titleInput.id = "library-import-title"; titleInput.type = "text"; titleInput.maxLength = 300; titleInput.autocomplete = "off";
      const textLabel = el("label", "Text"); textLabel.htmlFor = "library-import-text";
      const text = el("textarea"); text.id = "library-import-text"; text.rows = 10; text.maxLength = IMPORT_MAX;
      const count = el("p", "0 / " + IMPORT_MAX.toLocaleString("en-US") + " characters", "hint"); count.id = "library-import-count";
      text.addEventListener("input", () => CC.setText(count, text.value.length.toLocaleString("en-US") + " / " + IMPORT_MAX.toLocaleString("en-US") + " characters"));
      const go = el("button", "Import for the next launch that hunts", "primary"); go.type = "submit"; go.id = "library-import-go";
      const result = el("p", "", "hint"); result.id = "library-import-result"; result.setAttribute("role", "status");
      form.append(titleLabel, titleInput, textLabel, text, count, go, result);
      form.addEventListener("submit", async event => {
        event.preventDefault();
        const titleText = titleInput.value.trim(), body = text.value;
        if (!titleText || !body.trim()) { lib.importNote = {kind: "refused", text: "Write a title and the text to import."}; CC.redraw(); return; }
        if (body.length > IMPORT_MAX) { lib.importNote = {kind: "refused", text: "An import is at most " + IMPORT_MAX.toLocaleString("en-US") + " characters; this is " + body.length.toLocaleString("en-US") + ". Split it, or import its abstract and key sections."}; CC.redraw(); return; }
        const outcome = await write("library_import", {title: titleText, text: body}, titleText);
        if (!outcome) return;
        if (outcome.ok) {
          const id = outcome.value?.import_id;
          lib.importNote = {kind: "done", text: "Queued" + (id ? " as " + id : "") + ": “" + titleText + "”. The next Research or Full launch that hunts extracts it; then it is a card in your library."};
          titleInput.value = ""; text.value = ""; CC.sent(titleInput, text);
          CC.setText(count, "0 / " + IMPORT_MAX.toLocaleString("en-US") + " characters");
          loadList(true);
        } else lib.importNote = {kind: "refused", text: failed(outcome)};
        CC.redraw();
      });
      box.append(form);
    }, "panel lib-import-part");
    const result = $("library-import-result");
    if (result) {
      CC.setText(result, lib.importNote ? lib.importNote.text : "");
      const kind = lib.importNote?.kind === "refused" ? "reason" : "hint";
      if (result.className !== kind) result.className = kind;
    }
    const go = $("library-import-go");
    if (go) go.disabled = !CC.state().connected || lib.writing;
    part(panel, "pending", JSON.stringify([lib.list?.pending || null, lib.listError]), box => {
      box.append(el("h2", "Waiting for a launch that hunts"));
      const pending = lib.list?.pending || [];
      if (!pending.length) { para(box, lib.list ? "Nothing waiting." : "Reading your library…", "hint"); return; }
      const list = el("ul", undefined, "lib-pending");
      for (const item of pending) list.append(el("li", (item.title || item.import_id || "Untitled") + (item.import_id ? " · " + item.import_id : "") + (typeof item.characters === "number" ? " · " + item.characters.toLocaleString("en-US") + " characters" : "")));
      box.append(list);
    }, "panel lib-pending-part");
  }

  // ---- Plans. ----
  function writer(createdBy) { return createdBy === "miner" ? "Your edit" : createdBy === "planner" ? "Graphite's Planner" : words(createdBy || "unknown"); }
  function challengeName(challenge) {
    if (!challenge || typeof challenge !== "object") return "no Challenge named";
    const entry = (CC.state().caps?.challenges || []).find(item => item.challenge_id === challenge.id && item.version === challenge.version);
    return (entry ? entry.title : String(challenge.id)) + " · v" + challenge.version;
  }
  function cites(parent, list) {
    const items = listOf(list).filter(Boolean);
    if (!items.length) return;
    const ul = el("ul", undefined, "lib-cites"); ul.setAttribute("aria-label", "Cited cards");
    for (const cite of items) {
      const id = idOf(cite);
      const known = lib.cards.get(id);
      const li = el("li");
      li.append(anchor(known?.title || id, "#library/card/" + encodeURIComponent(id), "link"));
      li.append(originPill({origin: typeof cite === "object" ? cite.origin : known?.origin}));
      ul.append(li);
    }
    parent.append(ul);
  }
  // A plan, as text: ranked hypotheses, each with its expected effect, its
  // stopping rule, any recipe and the cards it cites.
  function drawPlan(parent, doc, limit = 0) {
    const hypotheses = listOf(doc?.hypotheses);
    if (!hypotheses.length) { para(parent, "This plan holds no hypothesis.", "hint"); return; }
    const list = el("ol", undefined, "lib-plan");
    for (const h of limit ? hypotheses.slice(0, limit) : hypotheses) {
      const item = el("li");
      item.append(el("strong", String(h?.hypothesis ?? "")));
      if (h?.expected_effect) item.append(el("p", "Expected effect: " + h.expected_effect, "hint"));
      if (!limit && h?.stopping_rule) item.append(el("p", "Stops when: " + h.stopping_rule, "hint"));
      if (!limit && h?.recipe !== undefined && h?.recipe !== null) item.append(el("pre", typeof h.recipe === "string" ? h.recipe : JSON.stringify(h.recipe, null, 2), "rs-pre"));
      if (!limit) cites(item, h?.cites);
      list.append(item);
    }
    parent.append(list);
    if (limit && hypotheses.length > limit) para(parent, (hypotheses.length - limit) + " more in the Library.", "hint");
  }
  function drawPlans(panel, r) {
    chooseChallenge();
    part(panel, "list", JSON.stringify([lib.plans, lib.plansError, r.plan, [...lib.drafts.keys()]]), box => {
      const top = el("div", undefined, "panel-heading");
      top.append(el("h2", "Your plans"));
      const fresh = anchor("Write a new plan", "#library/plans/new", "button"); fresh.id = "library-plan-new";
      top.append(fresh);
      box.append(top);
      para(box, "A plan is stored by its digest and never changes: an edit is a new version, with the plan it came from as its parent. Graphite builds from the plan a Build or Full campaign froze at launch.", "hint");
      if (lib.plansError) { para(box, "Your plans could not be read: " + words(lib.plansError) + ".", "reason"); return; }
      if (!lib.plans) { para(box, "Reading your plans…", "hint"); return; }
      if (!lib.plans.length) { para(box, "No plan yet. A Research campaign writes one; or write your own.", "hint"); return; }
      const wrap = el("div", undefined, "table-wrap"); const table = el("table", undefined, "metrics-table lib-plans");
      const head = el("tr"); for (const name of ["Plan", "Written by", "From", "When"]) head.append(el("th", name)); table.append(head);
      for (const item of lib.plans) {
        const row = el("tr"); row.dataset.plan = item.digest;
        if (item.digest === r.plan) row.setAttribute("aria-current", "true");
        const cell = el("td"); cell.append(anchor(short(item.digest), "#library/plans/" + encodeURIComponent(item.digest), "link"));
        if (lib.drafts.has(item.digest)) cell.append(el("span", " · editing", "small-tag"));
        row.append(cell, el("td", writer(item.created_by)), el("td", item.parent ? short(item.parent) : "–"), el("td", CC.when(item.created_at) || "–"));
        table.append(row);
      }
      wrap.append(table); box.append(wrap);
    }, "panel lib-plans-part");
    // Opening a new plan never discards another plan's draft: each is kept
    // under its own key until saved or cancelled.
    if (r.plan === "new" && !lib.drafts.has("new")) startDraft(null, null, "new");
    const draft = r.plan ? lib.drafts.get(r.plan) || null : null;
    const entry = r.plan && r.plan !== "new" ? planState(r.plan) : null;
    titles([...lib.curation.pins, ...lib.curation.bans, ...listOf(entry?.doc?.hypotheses).flatMap(h => listOf(h?.cites).map(idOf))]);
    part(panel, "plan", JSON.stringify([r.plan, entry && [entry.doc, entry.error], Boolean(draft), entry?.doc ? listOf(entry.doc.hypotheses).flatMap(h => listOf(h?.cites).map(c => lib.cards.get(idOf(c))?.title || null)) : null]), box => {
      if (!r.plan) { para(box, "Choose a plan to read it.", "hint"); return; }
      if (r.plan === "new") { box.append(el("h2", "A new plan")); para(box, "Written by you, from no earlier plan.", "hint"); return; }
      box.append(el("h2", "Plan " + short(r.plan)));
      if (entry.error) { para(box, "This plan could not be read: " + words(entry.error) + ".", "reason"); return; }
      if (!entry.doc) { para(box, "Reading the plan…", "hint"); return; }
      const doc = entry.doc;
      const facts = el("dl", undefined, "review-grid");
      facts.append(el("dt", "Written by"), el("dd", writer(doc.created_by)), el("dt", "For"), el("dd", challengeName(doc.challenge)), el("dt", "From"), el("dd", doc.parent ? short(doc.parent) : "no earlier plan"), el("dt", "Digest"), el("dd", r.plan));
      const considered = listOf(doc.pins_considered).filter(item => idOf(item));
      facts.append(el("dt", "Pins considered"), el("dd", considered.length ? considered.map(item => title(idOf(item)) + (typeof item?.consideration === "string" && item.consideration ? ": " + item.consideration : "")).join(" · ") : "none"));
      box.append(facts);
      para(box, "Guidance for Graphite's Constructor, read as data: it never changes your limits, the Challenge or how candidates are evaluated. Cited cards are UNCHECKED.", "hint");
      drawPlan(box, doc);
      if (!draft) {
        const edit = button("Edit as a new version", "primary", () => { startDraft(doc, r.plan, r.plan); CC.redraw(); });
        edit.id = "library-plan-edit";
        box.append(edit);
      }
    }, "panel lib-plan-part");
    // The editor's hypotheses are redrawn from the draft only when its rows
    // move; the pins it considered are their own part, redrawn when the pins
    // change (a pin made meanwhile gets its own box); its actions are drawn
    // once per draft. Typing never redraws any of them.
    const considered = draft ? consideredIds(draft) : [];
    const parts = [
      part(panel, "editor", draft ? JSON.stringify([draft.key, lib.draftVersion]) : "", box => { if (draft) drawEditorRows(box, draft); }, "panel lib-editor-part"),
      part(panel, "considered", draft ? JSON.stringify([draft.key, lib.draftVersion, lib.curation.pins, considered.map(id => lib.cards.get(id)?.title || null)]) : "", box => { if (draft) drawConsidered(box, draft); }, "panel lib-considered-part"),
      part(panel, "editor-actions", draft ? JSON.stringify([draft.key, lib.draftVersion]) : "", box => { if (draft) drawEditorActions(box, draft); }, "lib-editor-actions"),
    ];
    for (const node of parts) node.hidden = !draft;
    const result = $("library-plan-result");
    if (result) {
      CC.setText(result, draft?.result ? draft.result.text : "");
      const kind = draft?.result?.kind === "refused" ? "reason" : "hint";
      if (result.className !== kind) result.className = kind;
    }
    const save = $("library-plan-save");
    if (save) save.disabled = !CC.state().connected || lib.writing;
    const add = $("library-plan-add");
    if (add && draft) add.disabled = draft.rows.length >= PLAN.hypotheses;
  }

  // ---- The plan editor. It edits a draft held here; typing never redraws
  // it, and adding, moving or removing a hypothesis redraws it from the
  // draft, so nothing typed is lost. Saved in Graphite's plan schema: the
  // rank is the row's place, the Challenge is named, and each pinned card
  // says how the plan considers it.
  function text(value) { return value === undefined || value === null ? "" : String(value); }
  function rowFrom(h) {
    const item = h && typeof h === "object" ? h : {};
    const origins = {};
    for (const cite of listOf(item.cites)) if (cite && typeof cite === "object" && idOf(cite)) origins[idOf(cite)] = cite.origin;
    return {
      hypothesis: text(item.hypothesis), expected_effect: text(item.expected_effect), stopping_rule: text(item.stopping_rule),
      recipe: item.recipe === undefined || item.recipe === null ? "" : JSON.stringify(item.recipe, null, 2),
      cites: listOf(item.cites).map(idOf).filter(Boolean).join("\n"), origins,
    };
  }
  function startDraft(doc, parent, key) {
    const rows = listOf(doc?.hypotheses).map(rowFrom);
    if (!rows.length) rows.push(rowFrom(null));
    // How the plan considered each pin, kept as written; a planner's plan
    // carries one line per pinned card.
    const considerations = new Map();
    for (const item of listOf(doc?.pins_considered)) {
      const id = idOf(item);
      if (id) considerations.set(id, typeof item?.consideration === "string" ? item.consideration : "");
    }
    const named = doc?.challenge && typeof doc.challenge === "object" && typeof doc.challenge.id === "string" ? {id: doc.challenge.id, version: doc.challenge.version} : null;
    lib.drafts.set(key, {key, parent: parent || null, challenge: named || (lib.challenge ? {...lib.challenge} : null), fixedChallenge: Boolean(named), rows, considerations, result: null});
    lib.draftVersion++;
  }
  function citesOf(row) { return [...new Set(row.cites.split(/[\s,]+/).map(item => item.trim()).filter(Boolean))]; }
  // The cards whose consideration the editor asks for: every pinned card,
  // and any the plan considered that is no longer pinned.
  function consideredIds(draft) { return [...new Set([...lib.curation.pins, ...draft.considerations.keys()])]; }
  function drawEditorRows(box, draft) {
    box.append(el("h2", draft.parent ? "Edit as a new version of " + short(draft.parent) : "Write a plan"));
    para(box, "Ranked: the first hypothesis is the one Graphite tries first. Saving checks the plan here, then the controller checks it again and stores it as a new version; the plan it came from is kept.", "hint");
    if (draft.fixedChallenge) para(box, "For " + challengeName(draft.challenge) + ", as the plan it edits.", "hint");
    else {
      const label = el("label", "The Challenge this plan is for"); label.htmlFor = "library-plan-challenge";
      const challenges = chooseChallenge();
      const select = challengeSelect("library-plan-challenge", challenges, draft.challenge, chosen => { draft.challenge = chosen; });
      box.append(label, select);
    }
    const field = (row, index, key, label, rows, className) => {
      const id = "library-plan-" + key + "-" + index;
      const l = el("label", label); l.htmlFor = id;
      const area = el("textarea"); area.id = id; area.rows = rows; area.value = row[key]; area.dataset.draft = "1";
      if (className) area.className = className;
      area.addEventListener("input", () => { row[key] = area.value; });
      return [l, area];
    };
    draft.rows.forEach((row, index) => {
      const set = el("fieldset", undefined, "lib-plan-row"); set.dataset.row = String(index);
      set.append(el("legend", "Hypothesis " + (index + 1)));
      set.append(...field(row, index, "hypothesis", "Hypothesis", 2));
      set.append(...field(row, index, "expected_effect", "Expected effect", 2));
      set.append(...field(row, index, "stopping_rule", "Stopping rule: when to give it up", 2));
      set.append(...field(row, index, "recipe", "Recipe (optional, a JSON object as practice takes it)", 4, "code"));
      set.append(...field(row, index, "cites", "Cited cards: one card id per line, at most " + PLAN.cites, 2, "code"));
      const moves = el("div", undefined, "controls");
      const move = (label, to) => { const b = button(label, "", () => { const [taken] = draft.rows.splice(index, 1); draft.rows.splice(to, 0, taken); lib.draftVersion++; CC.redraw(); }); b.dataset.move = label; return b; };
      if (index > 0) moves.append(move("Move up", index - 1));
      if (index < draft.rows.length - 1) moves.append(move("Move down", index + 1));
      if (draft.rows.length > 1) moves.append(button("Remove", "", () => { draft.rows.splice(index, 1); lib.draftVersion++; CC.redraw(); }));
      set.append(moves);
      box.append(set);
    });
    const add = button("Add a hypothesis", "", () => { if (draft.rows.length >= PLAN.hypotheses) return; draft.rows.push(rowFrom(null)); lib.draftVersion++; CC.redraw(); });
    add.id = "library-plan-add";
    box.append(add);
    para(box, "A plan ranks 1 to " + PLAN.hypotheses + " hypotheses.", "hint");
  }
  // How the plan considers each pinned card: one line each, from the draft.
  function drawConsidered(box, draft) {
    const ids = consideredIds(draft);
    const considered = el("fieldset", undefined, "lib-considered");
    considered.append(el("legend", "How this plan considers each pinned card"));
    if (!ids.length) para(considered, "Nothing is pinned.", "hint");
    ids.forEach((id, index) => {
      const pinned = lib.curation.pins.includes(id);
      const areaId = "library-plan-consider-" + index;
      const label = el("label", title(id) + (pinned ? " · pinned" : " · no longer pinned")); label.htmlFor = areaId;
      const area = el("textarea"); area.id = areaId; area.rows = 2; area.dataset.pin = id; area.dataset.draft = "1";
      area.value = draft.considerations.get(id) || "";
      area.addEventListener("input", () => { draft.considerations.set(id, area.value); });
      considered.append(label, area);
    });
    para(considered, "Every pinned card needs a line saying how this plan considers it: Graphite's plan rule refuses a plan that leaves one out. A card no longer pinned is dropped when its line is blank.", "hint");
    box.append(considered);
  }
  function drawEditorActions(box, draft) {
    const actions = el("div", undefined, "controls");
    const save = button("Check and save a new version", "primary", () => saveDraft(draft)); save.id = "library-plan-save";
    const cancel = button("Cancel", "", () => {
      lib.drafts.delete(draft.key); lib.draftVersion++;
      // A new plan let go of leaves its page; an edit goes back to its plan.
      if (draft.key === "new") location.hash = "#library/plans"; else CC.redraw();
    });
    cancel.id = "library-plan-cancel";
    actions.append(save, cancel);
    box.append(actions);
    const result = el("p", "", "hint"); result.id = "library-plan-result"; result.setAttribute("role", "status");
    box.append(result);
  }
  function bounded(value, label, problems, n) {
    const trimmed = value.trim();
    if (!trimmed) problems.push(n + ": write " + label);
    else if (trimmed.length > PLAN.text) problems.push(n + ": " + label + " is at most " + PLAN.text + " characters");
  }
  // What keeps the draft from being a plan Graphite's rule takes, before
  // anything is sent.
  function draftProblems(draft) {
    const problems = [];
    if (!draft.challenge || typeof draft.challenge.id !== "string" || !draft.challenge.id) problems.push("choose the Challenge this plan is for");
    if (!draft.rows.length) problems.push("a plan needs at least one hypothesis");
    if (draft.rows.length > PLAN.hypotheses) problems.push("a plan ranks at most " + PLAN.hypotheses + " hypotheses");
    draft.rows.forEach((row, index) => {
      const n = "hypothesis " + (index + 1);
      for (const [key, label] of [["hypothesis", "the hypothesis"], ["expected_effect", "its expected effect"], ["stopping_rule", "its stopping rule"]]) bounded(row[key], label, problems, n);
      if (row.recipe.trim()) {
        let value = null;
        try { value = JSON.parse(row.recipe); } catch (_) { problems.push(n + ": the recipe is not valid JSON"); value = undefined; }
        if (value !== undefined && (!value || typeof value !== "object" || Array.isArray(value))) problems.push(n + ": the recipe is a JSON object");
        else if (value && JSON.stringify(value).length > PLAN.recipeBytes) problems.push(n + ": the recipe is at most " + PLAN.recipeBytes + " bytes");
      }
      const cited = citesOf(row);
      if (cited.length > PLAN.cites) problems.push(n + " cites " + cited.length + " cards; at most " + PLAN.cites);
      for (const id of cited) {
        if (!PLAN.cardId.test(id)) problems.push(n + ": “" + id + "” is not a card id");
        else if (lib.curation.bans.includes(id)) problems.push(n + " cites " + title(id) + ", which you banned (card banned)");
      }
    });
    const ignored = lib.curation.pins.filter(id => !text(draft.considerations.get(id)).trim());
    if (ignored.length) problems.push("say how the plan considers every pinned card: " + ignored.map(title).join(", ") + " (plan invalid)");
    const lines = [...draft.considerations.values()].map(value => text(value).trim()).filter(Boolean);
    if (lines.some(line => line.length > PLAN.text)) problems.push("a consideration is at most " + PLAN.text + " characters");
    if (lines.length > PLAN.pins) problems.push("a plan considers at most " + PLAN.pins + " pinned cards");
    return problems;
  }
  async function saveDraft(draft) {
    if (!draft || lib.writing || lib.drafts.get(draft.key) !== draft) return;
    const refuse = problems => { draft.result = {kind: "refused", text: "Not saved: " + problems.join("; ") + "."}; CC.redraw(); };
    const problems = draftProblems(draft);
    if (problems.length) { refuse(problems); return; }
    // Each cited card with where it came from; a card not read yet is read
    // first, and one in neither the shared pack nor this library is refused.
    const origins = {};
    for (const row of draft.rows) for (const id of citesOf(row)) origins[id] = row.origins[id] || lib.cards.get(id)?.origin || null;
    for (const id of Object.keys(origins).filter(item => !origins[item])) {
      try {
        const card = cardOf(await read("library_card", {card_id: id}));
        if (card) { remember([card]); origins[id] = card.origin || null; }
        else problems.push(id + " could not be read");
      } catch (error) {
        problems.push(error.code === "card_not_found" ? "cites " + id + ", which is in neither the shared pack nor your library (card not found)" : "cites " + id + ", which could not be read: " + words(error.message));
      }
    }
    if (problems.length) { refuse(problems); return; }
    // Graphite's plan, in its closed shape: exactly these fields.
    const plan = {
      schema: PLAN_SCHEMA,
      challenge: {id: draft.challenge.id, version: draft.challenge.version},
      hypotheses: draft.rows.map((row, index) => ({
        rank: index + 1,
        hypothesis: row.hypothesis.trim(), expected_effect: row.expected_effect.trim(), stopping_rule: row.stopping_rule.trim(),
        cites: citesOf(row).map(id => ({card_id: id, origin: origins[id]})),
        ...(row.recipe.trim() ? {recipe: JSON.parse(row.recipe)} : {}),
      })),
      pins_considered: consideredIds(draft).map(id => [id, text(draft.considerations.get(id)).trim()]).filter(([, line]) => line).map(([id, line]) => ({card_id: id, consideration: line})),
      parent: draft.parent,
      created_by: "miner",
    };
    const outcome = await write("plan_edit", {plan_document: plan}, draft.parent || "new");
    if (!outcome) return;
    if (!outcome.ok) { draft.result = {kind: "refused", text: failed(outcome)}; CC.redraw(); return; }
    // The new version is read back as the controller stored it.
    const digest = typeof outcome.value?.digest === "string" && outcome.value.digest ? outcome.value.digest : null;
    lib.drafts.delete(draft.key); lib.draftVersion++;
    lib.note = {kind: "done", text: "Saved as a new version" + (digest ? " " + short(digest) : "") + ". The plan it came from is kept."};
    CC.message(lib.note.text);
    loadPlans(true);
    if (digest) location.hash = "#library/plans/" + encodeURIComponent(digest);
    else CC.redraw();
  }

  // ---- The view. ----
  function statusText(s) {
    if (!s.connected) return "Connect this browser to read your library.";
    if (!Array.isArray(s.operations)) return "Reading what this controller offers…";
    if (!offered("library_search") && !offered("library_list")) return "This controller does not offer the Library: it predates Graphite's miner edition. Update Carbon (install --update), then reconnect.";
    return "";
  }
  function drawTabs(r) {
    const nav = $("library-tabs");
    if (!nav) return;
    if (nav.children.length !== TABS.length) {
      nav.replaceChildren();
      for (const [name, label, href] of TABS) { const a = anchor(label, href, ""); a.dataset.tab = name; nav.append(a); }
    }
    for (const a of nav.children) { if (a.dataset.tab === r.tab) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); }
  }
  const DRAW = {cards: drawCards, import: drawImport, plans: drawPlans};
  function render() {
    const r = route();
    if (!r) return;
    const s = CC.state();
    drawTabs(r);
    const note = $("library-note");
    if (note) {
      CC.setText(note, lib.note ? lib.note.text : "");
      const kind = lib.note?.kind === "refused" ? "reason" : "hint";
      if (note.className !== kind) note.className = kind;
    }
    const body = $("library-body");
    const status = statusText(s);
    part(body, "status", status, box => { if (status) para(box, status, s.connected ? "reason" : "hint"); }, "lib-status");
    for (const child of body.children) if (child.dataset.tab) child.hidden = Boolean(status) || child.dataset.tab !== r.tab;
    if (status) return;
    loadList();
    if (r.tab === "plans") loadPlans();
    let panel = null;
    for (const child of body.children) if (child.dataset.tab === r.tab) panel = child;
    if (!panel) { panel = el("div", undefined, "lib-panel"); panel.dataset.tab = r.tab; body.append(panel); }
    DRAW[r.tab](panel, r, s);
  }

  // ---- What the rest of the page reads: the plans for Build's picker, and
  // a plan's state for a campaign's Graphite panel.
  window.CarbonLibrary = {
    plans(force = false) {
      const s = CC.state();
      if (!s.connected) return {offered: true, list: null, error: null};
      if (!offered("plan_list")) return {offered: false, list: null, error: null};
      loadPlans(force);
      return {offered: true, list: lib.plans, error: lib.plansError};
    },
    plan(digest) { const entry = planState(digest); return {doc: entry.doc, error: entry.error}; },
    planKey(digest) { const entry = planState(digest); return JSON.stringify([digest, entry.doc, entry.error]); },
    drawPlan, short,
  };
  CC.onRender(() => { try { render(); } catch (error) { console.error(error); } });
  // The page drew once before this script ran: a Library address opened
  // before connecting says so now, not at the next redraw.
  try { render(); } catch (error) { console.error(error); }
})();
