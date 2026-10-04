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
// when the controller has no such route. Each request carries only the
// fields the controller's operation listing declares. A write is sent under
// an idempotency key kept until the controller answers it, so a retry after a
// lost answer replays it rather than repeating it.
//
// Every piece of text from the controller is set as text, never parsed as
// HTML. Nothing loads from the internet.
(() => {
  const CC = window.CarbonControlCenter;
  if (!CC) return;
  const {el} = CC;
  const $ = id => document.getElementById(id);
  const PLAN_SCHEMA = "carbon.graphite.miner-plan.v1";
  // The longest text an import carries (library_import, the design's bound).
  const IMPORT_MAX = 20000;
  // The Library is read again this often while it (or the Build plan
  // picker) is on screen: a hunt in a running campaign adds cards.
  const POLL_MS = 10000;
  // The results a search asks for, when the operation takes a limit.
  const SEARCH_LIMIT = 20;
  // ---- The operations, as the controller names them. `fields` are sent
  // always, under the first name the operation declares (or the first named
  // here when the listing has not been read); `extra` and `context` only
  // when the operation declares them.
  const CARD = ["card_id", "card"];
  const OPS = {
    library_search: {route: "/api/v1/library/search", fields: {query: ["query", "q"]}, context: ["challenge", "challenge_version", "limit"]},
    library_card: {route: "/api/v1/library/card", fields: {card: CARD}},
    library_list: {route: "/api/v1/library/list", fields: {}, context: ["challenge", "challenge_version"]},
    plan_list: {route: "/api/v1/plans/list", fields: {}},
    plan_get: {route: "/api/v1/plans/get", fields: {plan: ["plan", "digest", "plan_digest"]}},
    library_pin: {route: "/api/v1/library/pin", write: true, fields: {card: CARD}},
    library_unpin: {route: "/api/v1/library/unpin", write: true, fields: {card: CARD}},
    library_ban: {route: "/api/v1/library/ban", write: true, fields: {card: CARD}},
    library_unban: {route: "/api/v1/library/unban", write: true, fields: {card: CARD}},
    library_import: {route: "/api/v1/library/import", write: true, fields: {title: ["title"], text: ["text"]}},
    plan_edit: {route: "/api/v1/plans/edit", write: true, fields: {plan: ["plan", "plan_document", "document"]}, extra: {parent: ["parent", "parent_digest"]}},
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
    draft: null, draftFor: null, draftVersion: 0, draftResult: null,
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
    if (item && typeof item === "object") return String(item.card_id ?? item.id ?? "");
    return "";
  }
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
    const pick = names => (known && names.find(n => known.has(n))) || null;
    for (const [role, names] of Object.entries(op.fields)) {
      if (values[role] === undefined) continue;
      body[pick(names) || names[0]] = values[role];
    }
    for (const [role, names] of Object.entries(op.extra || {})) {
      const field = pick(names);
      if (field && values[role] !== undefined && values[role] !== null) body[field] = values[role];
    }
    if (known) for (const field of op.context || []) {
      if (!known.has(field)) continue;
      if (field === "challenge" && lib.challenge) body.challenge = lib.challenge.id;
      if (field === "challenge_version" && lib.challenge?.version) body.challenge_version = lib.challenge.version;
      if (field === "limit") body.limit = SEARCH_LIMIT;
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
    let card = item;
    if (item.card && typeof item.card === "object") {
      card = {...item.card};
      for (const key of ["score", "reasons", "origin", "check_status"]) if (item[key] !== undefined) card[key] = item[key];
    }
    return typeof card.card_id === "string" && card.card_id ? card : null;
  }
  function curationOf(value) {
    const c = value?.curation && typeof value.curation === "object" ? value.curation : value;
    if (!c || typeof c !== "object" || !(Array.isArray(c.pins) || Array.isArray(c.bans))) return null;
    return {pins: listOf(c.pins).map(idOf).filter(Boolean), bans: listOf(c.bans).map(idOf).filter(Boolean), digest: typeof c.digest === "string" ? c.digest : null};
  }
  function remember(cards) { for (const card of cards) if (card) lib.cards.set(card.card_id, {...(lib.cards.get(card.card_id) || {}), ...card}); }
  function listFrom(value) {
    const cards = listOf(value, "cards", "private", "items").map(cardOf).filter(Boolean);
    const pending = listOf(value?.pending_imports ?? value?.imports).filter(item => item && typeof item === "object");
    const shared = value?.shared && typeof value.shared === "object" ? value.shared : value?.pack && typeof value.pack === "object" ? value.pack : null;
    return {cards, pending, shared};
  }
  function planOf(value) {
    const doc = value?.plan && typeof value.plan === "object" && !Array.isArray(value.plan) ? value.plan : value;
    return doc && typeof doc === "object" ? doc : null;
  }
  function digestOf(value) {
    for (const candidate of [value?.digest, value?.plan_digest, typeof value?.plan === "string" ? value.plan : null]) if (typeof candidate === "string" && candidate) return candidate;
    return null;
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
      remember(lib.list.cards);
      const curation = curationOf(value);
      if (curation) lib.curation = curation;
    } catch (error) { lib.listError = error.message; }
    finally { lib.listLoading = false; lib.listAt = Date.now(); CC.redraw(); }
  }
  async function loadPlans(force = false) {
    if (lib.plansLoading || !CC.state().connected || !offered("plan_list") || !due(lib.plansAt, force)) return;
    lib.plansLoading = true;
    try {
      lib.plans = listOf(await read("plan_list", {}), "plans", "items").filter(item => item && typeof item.digest === "string");
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
      const results = listOf(value, "results", "cards", "items").map(cardOf).filter(Boolean);
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
    const outcome = await write(name, {card: id}, id);
    if (!outcome) return;
    if (outcome.ok) {
      const curation = curationOf(outcome.value);
      if (curation) lib.curation = curation;
      else {
        const list = action === "pin" ? "pins" : "bans";
        lib.curation = {...lib.curation, [list]: on ? lib.curation[list].filter(item => item !== id) : [...lib.curation[list], id]};
      }
      const title = lib.cards.get(id)?.title || id;
      lib.note = {kind: "done", text: {library_pin: "Pinned: Graphite's Planner must consider " + title + ".", library_unpin: "Unpinned " + title + ".", library_ban: "Banned: " + title + " is no longer served to Graphite or offered here.", library_unban: "Unbanned " + title + "."}[name]};
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
      const select = el("select"); select.id = "library-challenge";
      for (const entry of challenges) { const option = el("option", entry.title + " · v" + entry.version); option.value = JSON.stringify({id: entry.challenge_id, version: entry.version}); select.append(option); }
      if (lib.challenge) select.value = JSON.stringify(lib.challenge);
      select.addEventListener("change", () => {
        try { lib.challenge = JSON.parse(select.value); } catch (_) { lib.challenge = null; }
        CC.sent(select); select.blur();
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
      if (!lib.search) { para(box, "Search to see ranked cards. Every card is UNCHECKED: Carbon has not checked its claims.", "hint"); return; }
      if (lib.search.error) { para(box, lib.search.error + (lib.search.next ? ". Next: " + lib.search.next : ""), "reason"); return; }
      const challenge = (CC.state().caps?.challenges || []).find(entry => entry.challenge_id === lib.search.challenge?.id);
      para(box, shown.length + " card" + (shown.length === 1 ? "" : "s") + " for “" + lib.search.query + "”" + (challenge ? ", ranked for " + challenge.title : "") + ".", "status-line");
      for (const card of shown) cardItem(box, card);
    }, "lib-results");
    patchCuration(results);
    const curation = part(panel, "curation", JSON.stringify([lib.curation, [...lib.curation.pins, ...lib.curation.bans].map(id => [id, lib.cards.get(id)?.title || null, lib.cards.get(id)?.origin || null])]), box => drawCuration(box), "lib-curation panel");
    patchCuration(curation);
    const mine = part(panel, "mine", JSON.stringify([lib.list, lib.listError]), box => drawMine(box), "lib-mine panel");
    patchCuration(mine);
  }
  function readCard(id) {
    if (lib.cards.get(id)?.title || lib.cardReads.has(id) || !offered("library_card")) return;
    lib.cardReads.add(id);
    read("library_card", {card: id}).then(value => {
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
    para(box, "Graphite's Planner must consider every card you pin; a plan that ignores one is refused. A card you ban is never served to Graphite, offered here or cited by a plan.", "hint");
    for (const [action, title, ids] of [["pin", "Pinned", lib.curation.pins], ["ban", "Banned", lib.curation.bans]]) {
      box.append(el("h3", title + " · " + ids.length));
      if (!ids.length) { para(box, action === "pin" ? "Nothing pinned." : "Nothing banned.", "hint"); continue; }
      const list = el("ul", undefined, "lib-curated"); list.dataset.list = action;
      for (const id of ids) curationRow(list, id, action);
      box.append(list);
    }
  }
  function drawMine(box) {
    box.append(el("h2", "Your library"));
    if (lib.listError) { para(box, "Your library could not be read: " + words(lib.listError) + ". It is read again shortly.", "reason"); return; }
    if (!lib.list) { para(box, "Reading your library…", "hint"); return; }
    const shared = lib.list.shared;
    if (shared) {
      const count = typeof shared.cards === "number" ? shared.cards : Array.isArray(shared.cards) ? shared.cards.length : null;
      para(box, "Shared pack" + (count !== null ? ": " + count + " cards" : "") + ", frozen, shipped with Carbon" + (typeof shared.digest === "string" ? " (" + short(shared.digest) + ")" : "") + ". arXiv titles and abstracts are CC0 descriptive metadata; the other fields are Carbon's.", "hint");
    }
    para(box, "Cards your hunts found and texts you imported live here, on this machine, owner-only. " + lib.list.cards.length + " so far.", "hint");
    for (const card of lib.list.cards) cardItem(box, card);
  }

  // ---- Import. ----
  function drawImport(panel) {
    part(panel, "form", "form", box => {
      box.append(el("h2", "Import your own text"));
      para(box, "Paste a paper's text, or your own notes. The next Reader stage of a Research or Full campaign extracts it into a card, on your model and budget, and it joins your private library marked as your import. PDF import is not offered yet: paste the text.", "hint");
      const form = el("form", undefined, "lib-import");
      const titleLabel = el("label", "Title"); titleLabel.htmlFor = "library-import-title";
      const title = el("input"); title.id = "library-import-title"; title.type = "text"; title.maxLength = 300; title.autocomplete = "off";
      const textLabel = el("label", "Text"); textLabel.htmlFor = "library-import-text";
      const text = el("textarea"); text.id = "library-import-text"; text.rows = 10; text.maxLength = IMPORT_MAX;
      const count = el("p", "0 / " + IMPORT_MAX.toLocaleString("en-US") + " characters", "hint"); count.id = "library-import-count";
      text.addEventListener("input", () => CC.setText(count, text.value.length.toLocaleString("en-US") + " / " + IMPORT_MAX.toLocaleString("en-US") + " characters"));
      const go = el("button", "Import for the next Reader stage", "primary"); go.type = "submit"; go.id = "library-import-go";
      const result = el("p", "", "hint"); result.id = "library-import-result"; result.setAttribute("role", "status");
      form.append(titleLabel, title, textLabel, text, count, go, result);
      form.addEventListener("submit", async event => {
        event.preventDefault();
        const titleText = title.value.trim(), body = text.value;
        if (!titleText || !body.trim()) { lib.importNote = {kind: "refused", text: "Write a title and the text to import."}; CC.redraw(); return; }
        if (body.length > IMPORT_MAX) { lib.importNote = {kind: "refused", text: "An import is at most " + IMPORT_MAX.toLocaleString("en-US") + " characters; this is " + body.length.toLocaleString("en-US") + ". Split it, or import its abstract and key sections."}; CC.redraw(); return; }
        const outcome = await write("library_import", {title: titleText, text: body}, titleText);
        if (!outcome) return;
        if (outcome.ok) {
          const id = outcome.value?.import_id ?? outcome.value?.id;
          lib.importNote = {kind: "done", text: "Queued" + (id ? " as " + id : "") + ": “" + titleText + "”. The next Reader stage extracts it; then it is a card in your library."};
          title.value = ""; text.value = ""; CC.sent(title, text);
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
      box.append(el("h2", "Waiting for the next Reader stage"));
      const pending = lib.list?.pending || [];
      if (!pending.length) { para(box, lib.list ? "Nothing waiting." : "Reading your library…", "hint"); return; }
      const list = el("ul", undefined, "lib-pending");
      for (const item of pending) list.append(el("li", (item.title || item.import_id || "Untitled") + (item.import_id ? " · " + item.import_id : "")));
      box.append(list);
    }, "panel lib-pending-part");
  }

  // ---- Plans. ----
  function writer(createdBy) { return createdBy === "miner" ? "Your edit" : createdBy === "planner" ? "Graphite's Planner" : words(createdBy || "unknown"); }
  function planLabel(item) {
    return writer(item.created_by) + " · " + short(item.digest) + (item.parent ? " · from " + short(item.parent) : "") + (CC.when(item.created_at) ? " · " + CC.when(item.created_at) : "");
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
    part(panel, "list", JSON.stringify([lib.plans, lib.plansError, r.plan]), box => {
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
        row.append(cell, el("td", writer(item.created_by)), el("td", item.parent ? short(item.parent) : "–"), el("td", CC.when(item.created_at) || "–"));
        table.append(row);
      }
      wrap.append(table); box.append(wrap);
    }, "panel lib-plans-part");
    const editing = lib.draft && lib.draftFor === (r.plan || "");
    if (r.plan === "new" && (!lib.draft || lib.draftFor !== "new")) startDraft(null, null, "new");
    const entry = r.plan && r.plan !== "new" ? planState(r.plan) : null;
    titles([...lib.curation.pins, ...lib.curation.bans, ...listOf(entry?.doc?.hypotheses).flatMap(h => listOf(h?.cites).map(idOf))]);
    part(panel, "plan", JSON.stringify([r.plan, entry && [entry.doc, entry.error], editing || r.plan === "new", entry?.doc ? listOf(entry.doc.hypotheses).flatMap(h => listOf(h?.cites).map(c => lib.cards.get(idOf(c))?.title || null)) : null]), box => {
      if (!r.plan) { para(box, "Choose a plan to read it.", "hint"); return; }
      if (r.plan === "new") { box.append(el("h2", "A new plan")); para(box, "Written by you, from no earlier plan.", "hint"); return; }
      box.append(el("h2", "Plan " + short(r.plan)));
      if (entry.error) { para(box, "This plan could not be read: " + words(entry.error) + ".", "reason"); return; }
      if (!entry.doc) { para(box, "Reading the plan…", "hint"); return; }
      const doc = entry.doc;
      const facts = el("dl", undefined, "review-grid");
      facts.append(el("dt", "Written by"), el("dd", writer(doc.created_by)), el("dt", "From"), el("dd", doc.parent ? short(doc.parent) : "no earlier plan"), el("dt", "Digest"), el("dd", r.plan));
      const considered = listOf(doc.pins_considered).map(idOf).filter(Boolean);
      facts.append(el("dt", "Pins considered"), el("dd", considered.length ? considered.map(id => lib.cards.get(id)?.title || id).join(", ") : "none"));
      box.append(facts);
      para(box, "Guidance for Graphite's Constructor, read as data: it never changes your limits, the Challenge or how candidates are evaluated. Cited cards are UNCHECKED.", "hint");
      drawPlan(box, doc);
      if (!editing) {
        const edit = button("Edit as a new version", "primary", () => { startDraft(doc, r.plan, r.plan); CC.redraw(); });
        edit.id = "library-plan-edit";
        box.append(edit);
      }
    }, "panel lib-plan-part");
    const editor = part(panel, "editor", editing || r.plan === "new" ? "draft:" + lib.draftVersion : "", box => { if (lib.draft && lib.draftFor === (r.plan || "")) drawEditor(box); }, "panel lib-editor-part");
    editor.hidden = !(lib.draft && lib.draftFor === (r.plan || ""));
    const result = $("library-plan-result");
    if (result) {
      CC.setText(result, lib.draftResult ? lib.draftResult.text : "");
      const kind = lib.draftResult?.kind === "refused" ? "reason" : "hint";
      if (result.className !== kind) result.className = kind;
    }
    const save = $("library-plan-save");
    if (save) save.disabled = !CC.state().connected || lib.writing;
  }

  // ---- The plan editor. It edits a draft held here; typing never redraws
  // it, and adding, moving or removing a hypothesis redraws it from the
  // draft, so nothing typed is lost.
  function text(value) { return value === undefined || value === null ? "" : String(value); }
  function rowFrom(h) {
    const {hypothesis, expected_effect: effect, stopping_rule: rule, recipe, cites: cited, ...extra} = h && typeof h === "object" ? h : {};
    const origins = {};
    for (const cite of listOf(cited)) if (cite && typeof cite === "object" && idOf(cite)) origins[idOf(cite)] = cite.origin;
    return {
      hypothesis: text(hypothesis), expected_effect: text(effect), stopping_rule: text(rule),
      recipe: recipe === undefined || recipe === null ? "" : JSON.stringify(recipe, null, 2),
      cites: listOf(cited).map(idOf).filter(Boolean).join("\n"), origins, extra,
    };
  }
  function startDraft(doc, parent, key) {
    const rows = listOf(doc?.hypotheses).map(rowFrom);
    if (!rows.length) rows.push(rowFrom(null));
    lib.draft = {parent: parent || null, base: doc || null, rows, considered: new Set(listOf(doc?.pins_considered).map(idOf).filter(Boolean))};
    lib.draftFor = key; lib.draftVersion++; lib.draftResult = null;
  }
  function citesOf(row) { return [...new Set(row.cites.split(/[\s,]+/).map(item => item.trim()).filter(Boolean))]; }
  function drawEditor(box) {
    const draft = lib.draft;
    box.append(el("h2", draft.parent ? "Edit as a new version of " + short(draft.parent) : "Write a plan"));
    para(box, "Ranked: the first hypothesis is the one Graphite tries first. Saving checks the plan here, then the controller checks it again and stores it as a new version; the plan it came from is kept.", "hint");
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
      set.append(...field(row, index, "cites", "Cited cards: one card id per line", 2, "code"));
      const moves = el("div", undefined, "controls");
      const move = (label, to) => { const b = button(label, "", () => { const [taken] = draft.rows.splice(index, 1); draft.rows.splice(to, 0, taken); lib.draftVersion++; CC.redraw(); }); b.dataset.move = label; return b; };
      if (index > 0) moves.append(move("Move up", index - 1));
      if (index < draft.rows.length - 1) moves.append(move("Move down", index + 1));
      if (draft.rows.length > 1) moves.append(button("Remove", "", () => { draft.rows.splice(index, 1); lib.draftVersion++; CC.redraw(); }));
      set.append(moves);
      box.append(set);
    });
    const add = button("Add a hypothesis", "", () => { draft.rows.push(rowFrom(null)); lib.draftVersion++; CC.redraw(); });
    add.id = "library-plan-add";
    box.append(add);
    const pins = lib.curation.pins;
    const considered = el("fieldset", undefined, "lib-considered");
    considered.append(el("legend", "Pinned cards this plan considered"));
    if (!pins.length) para(considered, "Nothing is pinned.", "hint");
    pins.forEach((id, index) => {
      const row = el("label", undefined, "check");
      const tick = el("input"); tick.type = "checkbox"; tick.id = "library-plan-pin-" + index; tick.dataset.pin = id; tick.checked = draft.considered.has(id);
      tick.addEventListener("change", () => { if (tick.checked) draft.considered.add(id); else draft.considered.delete(id); });
      row.append(tick, " " + (lib.cards.get(id)?.title || id));
      considered.append(row);
    });
    para(considered, "Every pinned card must be considered: tick each once your plan accounts for it.", "hint");
    box.append(considered);
    const actions = el("div", undefined, "controls");
    const save = button("Check and save a new version", "primary", () => saveDraft()); save.id = "library-plan-save";
    const cancel = button("Cancel", "", () => { lib.draft = null; lib.draftFor = null; lib.draftResult = null; CC.redraw(); });
    actions.append(save, cancel);
    box.append(actions);
    const result = el("p", "", "hint"); result.id = "library-plan-result"; result.setAttribute("role", "status");
    box.append(result);
  }
  // What keeps the draft from being a plan, before anything is sent.
  function draftProblems(draft) {
    const problems = [];
    if (!draft.rows.length) problems.push("a plan needs at least one hypothesis");
    draft.rows.forEach((row, index) => {
      const n = "hypothesis " + (index + 1);
      for (const [key, label] of [["hypothesis", "the hypothesis"], ["expected_effect", "its expected effect"], ["stopping_rule", "its stopping rule"]]) if (!row[key].trim()) problems.push(n + ": write " + label);
      if (row.recipe.trim()) {
        let value = null;
        try { value = JSON.parse(row.recipe); } catch (_) { problems.push(n + ": the recipe is not valid JSON"); value = undefined; }
        if (value !== undefined && (!value || typeof value !== "object" || Array.isArray(value))) problems.push(n + ": the recipe is a JSON object");
      }
      for (const id of citesOf(row)) if (lib.curation.bans.includes(id)) problems.push(n + " cites " + (lib.cards.get(id)?.title || id) + ", which you banned (card banned)");
    });
    const ignored = lib.curation.pins.filter(id => !draft.considered.has(id));
    if (ignored.length) problems.push("consider every pinned card: " + ignored.map(id => lib.cards.get(id)?.title || id).join(", ") + " (plan invalid)");
    return problems;
  }
  async function saveDraft() {
    const draft = lib.draft;
    if (!draft || lib.writing) return;
    const refuse = problems => { lib.draftResult = {kind: "refused", text: "Not saved: " + problems.join("; ") + "."}; CC.redraw(); };
    const problems = draftProblems(draft);
    if (problems.length) { refuse(problems); return; }
    // Each cited card with where it came from; a card not read yet is read
    // first, and one in neither the shared pack nor this library is refused.
    const origins = {};
    for (const row of draft.rows) for (const id of citesOf(row)) origins[id] = row.origins[id] || lib.cards.get(id)?.origin || null;
    for (const id of Object.keys(origins).filter(item => !origins[item])) {
      try {
        const card = cardOf(await read("library_card", {card: id}));
        if (card) { remember([card]); origins[id] = card.origin || null; }
        else problems.push(id + " could not be read");
      } catch (error) {
        problems.push(error.code === "card_not_found" ? "cites " + id + ", which is in neither the shared pack nor your library (card not found)" : "cites " + id + ", which could not be read: " + words(error.message));
      }
    }
    if (problems.length) { refuse(problems); return; }
    const base = {...(draft.base || {})};
    for (const key of ["digest", "created_at"]) delete base[key];
    const plan = {
      ...base,
      schema: typeof base.schema === "string" ? base.schema : PLAN_SCHEMA,
      hypotheses: draft.rows.map(row => ({
        ...row.extra,
        hypothesis: row.hypothesis.trim(), expected_effect: row.expected_effect.trim(), stopping_rule: row.stopping_rule.trim(),
        ...(row.recipe.trim() ? {recipe: JSON.parse(row.recipe)} : {}),
        cites: citesOf(row).map(id => ({card_id: id, origin: origins[id]})),
      })),
      pins_considered: [...draft.considered],
      parent: draft.parent,
      created_by: "miner",
    };
    const outcome = await write("plan_edit", {plan, parent: draft.parent}, draft.parent || "new");
    if (!outcome) return;
    if (!outcome.ok) { lib.draftResult = {kind: "refused", text: failed(outcome)}; CC.redraw(); return; }
    // The new version is read back as the controller stored it.
    const digest = digestOf(outcome.value);
    lib.draft = null; lib.draftFor = null; lib.draftResult = null;
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
})();
