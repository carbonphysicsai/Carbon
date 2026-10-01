// The Pilot Designer's system builder (GOAL-WORKBENCH-16 slice 1).
//
// The live /workbench/ page's problem builder, moved into the Pilot Designer so
// that one page drafts one brief. The problem model is the live page's own
// engine (src/problem/engine.js, byte-for-byte), and the editors and renderers
// here are adapted from that page's app.js. Nothing here reaches the network:
// the structure stays in the browser, is not sent to the optional AI guidance,
// and leaves only inside the reviewed package the client downloads.
//
// The words of the problem (its title, description, decision and baseline)
// belong to the brief. The builder reads them for the evidence plan and hands
// words from an example or an imported draft back to the brief, but the system
// it returns carries structure only.
(function (root) {
  "use strict";

  const LIMITS = { components: 12, couplings: 24, inputs: 24, outputs: 24, requirements: 24, sources: 12 };
  const STEPS = ["system", "contract", "evidence", "success", "constraints", "economics"];
  const COST_LABELS = {
    queries: "Predictions per month",
    baselineSeconds: "Current end-to-end time (s)",
    targetSeconds: "Target end-to-end time (s)",
    baselineCost: "Current cost / prediction (USD)",
    targetCost: "Target cost / prediction (USD)",
    setupCost: "One-time setup cost (USD)",
    monthlyCost: "Additional monthly cost (USD)",
    hardware: "Timing context / hardware",
  };
  const ROW_LABEL = { components: "Component", couplings: "Coupling", inputs: "Input", outputs: "Output", requirements: "Criterion", sources: "Source" };
  const esc = (value) =>
    String(value).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const newId = (prefix) => prefix + "_" + root.crypto.randomUUID().replaceAll("-", "").slice(0, 20);

  // Words carried by an example or a saved /workbench/ draft, in the brief's
  // own field names. Only these three brief fields receive them.
  function wordsFrom(problem) {
    const result = [problem.title, problem.description].filter((x) => x && x.trim()).join(" — ");
    return {
      intended_decision: problem.decision || "",
      requested_result: result,
      current_baseline: problem.baseline || "",
    };
  }

  // Reads any saved draft the live /workbench/ page produced: its editable
  // draft (carbon.workbench.problem.v0.3, including an older rules version),
  // a cooling v0.2 draft, or the unsent submission preview
  // (carbon.client-intake/1). Returns the problem and the contact email the
  // preview carried, if any.
  function readWorkbenchDraft(E, text) {
    let parsed;
    try { parsed = JSON.parse(text); } catch { throw Error("Choose a valid Carbon draft file."); }
    let jobText = text;
    let email = "";
    if (parsed && parsed.schema === "carbon.client-intake/1") {
      if (!parsed.job || typeof parsed.job !== "object") throw Error("This Workbench file has no draft inside it.");
      jobText = JSON.stringify(parsed.job);
      email = typeof parsed.contact?.email === "string" ? parsed.contact.email.slice(0, 320) : "";
    }
    const item = E.importJob(jobText);
    const job = item.kind === "legacy" ? E.migrateLegacy(item.originalText) : item.job;
    return { problem: E.copy(job.problem), email, kind: item.kind };
  }

  function create(options) {
    const E = options.engine;
    const atlas = options.atlas;
    const $ = (id) => document.getElementById(id);
    const $$ = (selector) => Array.from(options.root.querySelectorAll(selector));
    let problem = E.blankProblem();
    let invalid = false;
    let activeStep = "system";
    let atlasLimit = 6;

    const money = (n) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: Math.abs(n) < 1 ? 4 : 0, notation: Math.abs(n) > 1e7 ? "compact" : "standard" }).format(n);
    const num = (n) => new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(n);
    const choices = (values, value, empty) =>
      (empty !== undefined ? '<option value="">' + esc(empty) + "</option>" : "") +
      Object.entries(values).map(([v, label]) => `<option value="${esc(v)}"${v === value ? " selected" : ""}>${esc(label)}</option>`).join("");
    const componentNames = () => Object.fromEntries(problem.components.map((c) => [c.id, c.name || E.PHYSICS[c.physics]]));
    const outputNames = () => Object.fromEntries(problem.outputs.map((o) => [o.id, o.name || "Unnamed output"]));

    function field(type, row, key, label, kind = "text", values) {
      const domId = "sb_" + row.id + "_" + key;
      const attr = `id="${esc(domId)}" data-list="${type}" data-row="${esc(row.id)}" data-field="${key}"`;
      const value = row[key];
      if (kind === "select")
        return `<label for="${domId}">${label}<select ${attr}>${choices(values, value, ["from", "to", "output"].includes(key) ? "Select / unknown" : undefined)}</select></label>`;
      if (kind === "textarea")
        return `<label for="${domId}">${label}<textarea ${attr} rows="2" maxlength="${["coverage", "uncertainty", "definition"].includes(key) ? 1200 : 600}">${esc(value)}</textarea></label>`;
      const numeric = kind === "number";
      const max = key === "unit" ? 80 : key === "purpose" ? 700 : key === "quantity" ? 300 : type === "components" && key === "name" ? 140 : 160;
      return `<label for="${domId}">${label}<input ${attr} type="${numeric ? "number" : "text"}" ${numeric ? 'step="' + (key === "count" ? "1" : "any") + '" max="1000000000000"' + (key === "count" ? ' min="0"' : "") : 'maxlength="' + max + '"'} value="${esc(value === null ? "" : value)}" placeholder="${numeric ? "Unknown" : "To define"}"></label>`;
    }

    function rowHTML(type, row, index) {
      const f = (key, label, kind, values) => field(type, row, key, label, kind, values);
      let body = "";
      if (type === "components")
        body = f("name", "Component / subsystem name") + f("physics", "Physical process", "select", E.PHYSICS) + f("regime", "Regime, boundaries or assumptions", "textarea");
      if (type === "couplings")
        body = `<div class="pair">${f("from", "From", "select", componentNames())}${f("to", "To", "select", componentNames())}</div>` + f("quantity", "Exchanged quantity or influence") + f("direction", "Interaction", "select", E.OPTIONS.coupling);
      if (type === "inputs")
        body = f("name", "Input / varying condition") + `<div class="pair">${f("unit", "Unit or representation")}${f("variation", "How it varies", "select", E.OPTIONS.variation)}</div><div class="pair">${f("min", "Lower bound", "number")}${f("max", "Upper bound", "number")}</div><p class="field-note">Leave both bounds blank for categorical, geometry, history or unknown ranges.</p>` + f("definition", "Domain details, categories, geometry or histories", "textarea");
      if (type === "outputs")
        body = f("name", "Output / quantity you need") + `<div class="pair">${f("unit", "Unit or representation")}${f("priority", "Importance", "select", E.OPTIONS.priority)}</div>` + f("purpose", "Decision this output supports");
      if (type === "requirements")
        body = f("output", "Output being assessed", "select", outputNames()) + f("kind", "Requirement type", "select", E.OPTIONS.criterion) + f("measure", "Measurement or interpretation", "textarea") + f("operator", "How to interpret the target", "select", E.OPTIONS.operator) + `<div class="pair">${f("target", "Proposed target", "number")}${f("unit", "Target unit")}</div>`;
      if (type === "sources")
        body = f("name", "Source description") + `<div class="pair">${f("type", "Source type", "select", E.OPTIONS.dataType)}${f("role", "Possible role", "select", E.OPTIONS.dataRole)}</div><div class="pair">${f("access", "Permission / access", "select", E.OPTIONS.access)}${f("independence", "Independence", "select", E.OPTIONS.independence)}</div><div class="pair">${f("count", "Available count", "number")}${f("countUnit", "What are you counting?", "select", E.OPTIONS.countUnit)}</div>` + f("coverage", "Outputs and conditions covered", "textarea") + f("uncertainty", "Known uncertainty / quality limits", "textarea");
      return `<article class="collection-row" id="sb_card_${esc(row.id)}"><div class="row-heading"><strong>${ROW_LABEL[type]} ${index + 1}</strong><button type="button" class="quiet small" data-remove="${type}" data-id="${esc(row.id)}">Remove</button></div>${body}</article>`;
    }

    function renderEditors() {
      $$("[data-scalar]").forEach((node) => {
        const key = node.dataset.scalar;
        if (node.tagName === "SELECT") node.innerHTML = choices(key === "goal" ? E.GOALS : E.OPTIONS[key], problem[key]);
        else node.value = problem[key];
      });
      for (const type of Object.keys(LIMITS)) {
        $("sb-" + type + "-rows").innerHTML = problem[type].length
          ? problem[type].map((row, index) => rowHTML(type, row, index)).join("")
          : `<p class="field-note">No ${type} defined yet.</p>`;
        options.root.querySelector(`[data-add="${type}"]`).disabled = problem[type].length >= LIMITS[type];
      }
      $("sb-economics-fields").innerHTML =
        E.econKeys.filter((k) => k !== "matchedTiming").map((k) =>
          `<label for="sb_cost_${k}">${COST_LABELS[k]}<input id="sb_cost_${k}" data-cost="${k}" ${k === "hardware" ? 'type="text" maxlength="300"' : 'type="number" min="0" max="1000000000" step="' + (k === "queries" ? "1" : "any") + '"'} value="${esc(problem.economics[k] === null ? "" : problem.economics[k])}" placeholder="${k === "hardware" ? "Comparable workload, batching and boundaries" : "Unknown / your assumption"}"></label>`,
        ).join("") +
        `<label class="check"><input id="sb_cost_matchedTiming" data-cost="matchedTiming" type="checkbox"${problem.economics.matchedTiming ? " checked" : ""}> I intend to compare matching workloads and timing boundaries.</label>`;
      wireRows();
      showStep(activeStep, false);
    }

    function collect() {
      const next = E.copy(problem);
      for (const node of $$("[data-scalar],[data-list][data-field],[data-cost]")) {
        if (!node.validity.valid)
          throw Error("Correct " + (node.closest("label")?.firstChild?.textContent?.trim() || "the field") + " before the plan can update.");
        const value = node.type === "checkbox" ? node.checked : node.type === "number" ? (node.value === "" ? null : Number(node.value)) : node.value;
        if (node.dataset.scalar) next[node.dataset.scalar] = value;
        else if (node.dataset.cost) next.economics[node.dataset.cost] = value;
        else {
          const target = next[node.dataset.list].find((r) => r.id === node.dataset.row);
          if (!target) throw Error("Missing row.");
          target[node.dataset.field] = value;
        }
      }
      E.validateProblem(next);
      return next;
    }

    function referenceChoices() {
      $$('[data-list="couplings"][data-field="from"], [data-list="couplings"][data-field="to"]').forEach((node) => {
        const value = node.value; node.innerHTML = choices(componentNames(), value, "Select / unknown");
      });
      $$('[data-list="requirements"][data-field="output"]').forEach((node) => {
        const value = node.value; node.innerHTML = choices(outputNames(), value, "Select / unknown");
      });
    }

    function edited() {
      try {
        problem = collect();
        invalid = false;
        $("sb-error").hidden = true;
        referenceChoices();
        renderResults();
      } catch (error) {
        invalid = true;
        $("sb-error").hidden = false;
        $("sb-error").textContent = error.message + " The plan keeps the last valid entry, and downloads are blocked until this is corrected.";
      }
      options.onChange();
    }

    function commit(next) {
      E.validateProblem(next);
      problem = next;
      invalid = false;
      $("sb-error").hidden = true;
      renderEditors();
      renderResults();
      options.onChange();
    }

    function wireRows() {
      $$("[data-remove]").forEach((button) => button.addEventListener("click", () => {
        if (invalid) { options.status("Correct the invalid field before removing a row."); return; }
        const type = button.dataset.remove, rowId = button.dataset.id;
        const linked = type === "components"
          ? problem.couplings.filter((r) => r.from === rowId || r.to === rowId).length
          : type === "outputs" ? problem.requirements.filter((r) => r.output === rowId).length : 0;
        if (linked && !root.confirm(type === "components"
          ? `Remove this component and its ${linked} coupling(s)?`
          : `Remove this output? ${linked} criterion link(s) will become unknown; the criteria remain.`)) return;
        commit(E.removeRow(problem, type, rowId));
      }));
    }

    // The evidence plan reads the brief's words, so it reflects one draft.
    function withWords() {
      const words = options.words();
      const p = E.copy(problem);
      p.title = (words.requested_result || "").slice(0, 300);
      p.description = (words.requested_result || "").slice(0, 3000);
      p.decision = (words.intended_decision || "").slice(0, 3000);
      p.baseline = (words.current_baseline || "").slice(0, 300);
      return p;
    }

    function systemMap(p) {
      const count = p.components.length;
      if (!count) return '<p class="field-note">Add a component to draw your system. You can name a custom process or choose “Not sure yet”.</p>';
      const height = 90 + count * 65, top = 40;
      const pos = Object.fromEntries(p.components.map((c, i) => [c.id, top + i * 65]));
      const trim = (s, n) => (s.length > n ? s.slice(0, n - 1) + "…" : s);
      const links = p.couplings.filter((c) => c.from && c.to && c.from !== c.to).map((link, i) => {
        const x = 283 + (i % 7) * 6, y1 = pos[link.from] + 20, y2 = pos[link.to] + 20;
        return `<path class="link" d="M272 ${y1}H${x}V${y2}H272" marker-end="url(#sb-arrow)"${link.direction === "twoway" ? ' marker-start="url(#sb-arrow-back)"' : ""}><title>${esc(link.quantity || "Quantity to define")}</title></path>`;
      }).join("");
      const nodes = p.components.map((c) =>
        `<g><rect class="box" x="12" y="${pos[c.id]}" width="260" height="46"/><text x="23" y="${pos[c.id] + 18}">${esc(trim(c.name || "Unnamed component", 35))}</text><text class="small" x="23" y="${pos[c.id] + 34}">${esc(E.PHYSICS[c.physics])}</text><title>${esc(c.name)}: ${esc(c.regime || "Regime to define")}</title></g>`,
      ).join("");
      const names = componentNames();
      return `<svg class="system-svg" viewBox="0 0 340 ${height}" role="img" aria-labelledby="sb-map-title sb-map-desc"><title id="sb-map-title">Your proposed physical system</title><desc id="sb-map-desc">${count} components and ${p.couplings.length} proposed couplings. See the list below for connections.</desc><defs><marker id="sb-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0 10 5 0 10Z"/></marker><marker id="sb-arrow-back" viewBox="0 0 10 10" refX="1" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M10 0 0 5 10 10Z"/></marker></defs><text class="small" x="12" y="22">${p.inputs.length} inputs / proposed connections</text>${links}${nodes}<text class="small" x="12" y="${height - 12}">${p.outputs.length} outputs / ${p.requirements.length} criteria to review</text></svg>` +
        (p.couplings.length ? `<ul class="map-links">${p.couplings.map((c) => `<li>${esc(names[c.from] || "Unknown")} ${c.direction === "twoway" ? "↔" : "→"} ${esc(names[c.to] || "Unknown")}: ${esc(c.quantity || "quantity to define")}</li>`).join("")}</ul>` : '<p class="field-note">No coupling defined.</p>');
    }

    function costChart(e) {
      const points = e.curve, xmax = Math.max(1, ...points.map((x) => x.queries));
      let lo = Math.min(0, ...points.map((x) => x.value)), hi = Math.max(0, ...points.map((x) => x.value));
      if (lo === hi) { lo--; hi++; }
      const sx = (x) => 65 + (x / xmax) * 395, sy = (y) => 175 - ((y - lo) / (hi - lo)) * 140;
      const d = points.map((p, i) => (i ? "L" : "M") + sx(p.queries).toFixed(2) + "," + sy(p.value).toFixed(2)).join(" ");
      return `<figure class="chart"><figcaption class="field-note">Twelve-month net / scenario</figcaption><svg viewBox="0 0 485 225" role="img" aria-label="Scenario net value as monthly prediction volume varies"><line x1="65" x2="65" y1="35" y2="175"/><line x1="65" x2="460" y1="175" y2="175"/><line class="zero" x1="65" x2="460" y1="${sy(0)}" y2="${sy(0)}"/><path d="${d}"/><text x="60" y="38" text-anchor="end">${esc(money(hi))}</text><text x="60" y="177" text-anchor="end">${esc(money(lo))}</text><text x="65" y="196">0</text><text x="460" y="196" text-anchor="end">${num(xmax)}</text><text x="260" y="220" text-anchor="middle">Predictions per month</text></svg></figure>`;
    }

    function costResult(e) {
      const timing = e.timingKnown ? `<p class="field-note">Timing assumptions imply ${num(Math.abs(e.secondsSaved) / 3600)} aggregate execution hours ${e.secondsSaved < 0 ? "added" : "saved"} per month. This is not measured speedup or calendar time.</p>` : "";
      if (e.kind === "unknown") return `<div class="empty-note"><strong>Cost inputs remain unknown.</strong><p class="field-note">Needed: ${e.missing.map((k) => esc(COST_LABELS[k])).join(", ")}.</p>${timing}</div>`;
      return `<div class="metric-row"><div><span>Monthly net</span><strong>${money(e.monthlyNet)}</strong></div><div><span>Setup break-even</span><strong>${e.months === null ? "Not reached" : num(e.months) + " mo"}</strong></div><div><span>Twelve-month net</span><strong>${money(e.annualNet)}</strong></div></div>${costChart(e)}${timing}<p class="field-note">${e.maxTargetCost12 === null ? "Enter positive volume to inspect a cost boundary." : e.maxTargetCost12 < 0 ? "These assumptions do not recover setup within twelve months even with zero target cost per prediction." : "The target cost would need to stay at or below " + money(e.maxTargetCost12) + " per prediction to recover setup within twelve months. This does not establish achievability."}</p>`;
    }

    function plan(d, p) {
      return `<div class="plan-route"><p class="eyebrow">Proposed entry point</p><h4>${esc(d.route)}</h4><p>${esc(d.method.claim)}</p></div>` +
        `<h4>The next useful step</h4><p>${esc(d.next)}</p>` +
        (d.contradictions.length ? `<div class="boundary"><strong>Unresolved contradictions.</strong> ${esc(d.contradictions.join(" "))} Downloads keep them visible; this is not an executable challenge.</div>` : "") +
        `<h4>Review items (${d.gaps.length})</h4><ul class="gap-list">${d.gaps.slice(0, 6).map((g) => `<li><strong>${esc(g.topic)}.</strong> ${esc(g.text)}</li>`).join("")}</ul><p class="field-note">A work list, not a feasibility score.</p>` +
        `<h4>Evidence plan</h4><p>${esc(d.method.measure)}</p><ol class="stage-list">${d.evidenceStages.map((s) => `<li><strong>${esc(s.name)}.</strong> ${esc(s.text)}</li>`).join("")}</ol><p class="field-note">${esc(d.referenceBoundary)}</p>` +
        (d.guidance.length ? `<h4>Method and regime review</h4>${d.guidance.map((g) => `<details class="method"><summary>${esc(g.name)} / proposed checklist</summary><p>${esc(g.review)}</p><p><strong>Reference:</strong> ${esc(g.reference)}</p><p><strong>Measurements:</strong> ${esc(g.measure)}</p><p class="field-note">${esc(g.status)}</p></details>`).join("")}` : "") +
        `<div class="boundary"><strong>System and time behavior.</strong> ${esc(d.coupling)} ${esc(d.time)}</div>` +
        `<h4>What you could receive</h4><ul>${d.deliverables.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` +
        `<h4>Compare sensible paths</h4><ul>${d.alternatives.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` +
        `<details class="method"><summary>Scientific interpretation and scoring boundaries</summary><p>Define the target population, evaluation sampling and score weighting as separate choices. A specialist must review reference uncertainty, dependence and the resolution needed to distinguish candidates before selecting a sample count.</p><p>Freeze confirmatory criteria before observing outcomes. Preserve reference and infrastructure failures separately from model failures. No favorable economics can compensate for a failed mandatory physical requirement.</p><p>A customer’s target does not create an official score, approved threshold or scientific result.</p></details>` +
        `<p class="field-note">${p.outputs.length} outputs, ${p.sources.length} reported sources, ${p.requirements.length} requested criteria. Descriptions and planning rules only: no solver or scientific assessment has run.</p>`;
    }

    function renderResults() {
      const p = withWords();
      const derived = E.derive(p);
      $("sb-map").innerHTML = systemMap(p);
      $("sb-plan").innerHTML = plan(derived, p);
      $("sb-economics-result").innerHTML = costResult(derived.economics);
    }

    function showStep(name, focus) {
      activeStep = name;
      $$("[data-step]").forEach((button) => {
        const yes = button.dataset.step === name;
        button.setAttribute("aria-selected", String(yes));
        button.tabIndex = yes ? 0 : -1;
        $("sb-editor-" + button.dataset.step).hidden = !yes;
        if (yes && focus) button.focus();
      });
      $("sb-previous").disabled = STEPS.indexOf(name) === 0;
      $("sb-next").disabled = STEPS.indexOf(name) === STEPS.length - 1;
    }

    function renderAtlas() {
      const query = $("sb-atlas-search").value.trim().toLowerCase();
      const matches = atlas.opportunities.filter((o) => (o.title + " " + o.engineering_jobs_source).toLowerCase().includes(query));
      $("sb-atlas").innerHTML = `<p class="field-note">${matches.length} research leads</p>` +
        (matches.length
          ? `<div class="atlas-grid">${matches.slice(0, atlasLimit).map((o) => `<article class="atlas-card"><span class="field-note">${esc(o.id)} / Research lead</span><h4>${esc(o.title)}</h4><p>${esc(o.engineering_jobs_source)}</p><details><summary>Inspect the source strategy</summary><p>${esc(o.reference_path_source)}</p><p>${esc(o.path_and_risk_source)}</p><p class="field-note">Historical recommendation. Applicability and implementation remain to review.</p></details><button type="button" class="quiet small" data-use-lead="${esc(o.id)}">Add to my system +</button></article>`).join("")}</div>`
          : '<p class="field-note">No matching research lead. Describe this physics with a custom component; your problem does not have to match the catalogue.</p>') +
        (matches.length > atlasLimit ? '<button type="button" class="quiet small" id="sb-atlas-more">Show more research leads</button>' : "");
      $("sb-atlas-more")?.addEventListener("click", () => { atlasLimit += 12; renderAtlas(); });
      $$("[data-use-lead]").forEach((button) => button.addEventListener("click", () => {
        if (invalid) { options.status("Correct the invalid field first."); return; }
        const lead = atlas.opportunities.find((x) => x.id === button.dataset.useLead);
        const next = E.copy(problem);
        if (next.components.length >= LIMITS.components || next.sourceRefs.length >= 20) { options.status("The draft has reached its component or research-lead limit."); return; }
        if (next.sourceRefs.includes(lead.id)) { options.status("This research lead is already linked."); return; }
        next.components.push({ ...E.row("components", newId("component")), name: lead.title, physics: "unknown", regime: "Research lead " + lead.id + ". Select applicable physics and define the scope." });
        next.sourceRefs.push(lead.id);
        commit(next);
        showStep("system", false);
        options.status("Research lead added. Choose its physical process and define the component’s role.");
      }));
    }

    options.root.querySelector("#sb-form").addEventListener("input", edited);
    options.root.querySelector("#sb-form").addEventListener("submit", (event) => event.preventDefault());
    $$("[data-add]").forEach((button) => button.addEventListener("click", () => {
      if (invalid) { options.status("Correct the invalid field first."); return; }
      const type = button.dataset.add, next = E.copy(problem);
      if (next[type].length >= LIMITS[type]) return;
      const row = E.row(type, newId(type.slice(0, 3)));
      if (type === "couplings" && next.components.length >= 2) { row.from = next.components[0].id; row.to = next.components[1].id; }
      if (type === "requirements" && next.outputs.length) row.output = next.outputs[0].id;
      next[type].push(row);
      commit(next);
      options.root.querySelector(`#sb_card_${row.id} input, #sb_card_${row.id} select`)?.focus();
    }));
    $$("[data-step]").forEach((button) => button.addEventListener("click", () => showStep(button.dataset.step, false)));
    $("sb-previous").addEventListener("click", () => showStep(STEPS[Math.max(0, STEPS.indexOf(activeStep) - 1)], true));
    $("sb-next").addEventListener("click", () => showStep(STEPS[Math.min(STEPS.length - 1, STEPS.indexOf(activeStep) + 1)], true));
    $("sb-illustration").addEventListener("click", () => {
      if (invalid) { options.status("Correct the invalid field first."); return; }
      if (Object.values(problem.economics).some((x) => x !== null && x !== "" && x !== false) && !root.confirm("Replace the cost fields with illustrative assumptions?")) return;
      const next = E.copy(problem);
      Object.assign(next.economics, { queries: 10000, baselineCost: 0.5, targetCost: 0.02, setupCost: 5000, monthlyCost: 500, baselineSeconds: 60, targetSeconds: 0.5, hardware: "Illustration: comparable workload and boundaries", matchedTiming: true });
      commit(next);
      options.status("Illustrative cost assumptions loaded. No measured result or price quote.");
    });
    $("sb-atlas-search").addEventListener("input", () => { atlasLimit = 6; renderAtlas(); });

    // Loads a problem, keeping its structure here and returning its words.
    function load(next) {
      E.validateProblem(next);
      const unknownLead = next.sourceRefs.find((x) => !atlas.opportunities.some((o) => o.id === x));
      if (unknownLead) throw Error("The draft refers to an unknown research lead: " + unknownLead);
      const words = wordsFrom(next);
      const structure = E.copy(next);
      for (const key of ["title", "description", "decision", "baseline"]) structure[key] = "";
      problem = structure;
      invalid = false;
      $("sb-error").hidden = true;
      activeStep = "system";
      renderEditors();
      renderResults();
      options.onChange();
      return words;
    }

    renderEditors();
    renderResults();
    renderAtlas();

    return Object.freeze({
      // The validated structure, words empty, as a v2 brief carries it.
      system() {
        if (invalid) throw Error("Correct the highlighted system field before downloading.");
        const out = E.copy(problem);
        for (const key of ["title", "description", "decision", "baseline"]) out[key] = "";
        return E.validateProblem(out);
      },
      load,
      example(key) { return load(E.template(key, newId("job")).problem); },
      reset() { load(E.blankProblem()); },
      refresh() { if (!invalid) renderResults(); },
      valid: () => !invalid,
      isBlank: () => JSON.stringify(problem) === JSON.stringify(E.blankProblem()),
    });
  }

  const api = { create, readWorkbenchDraft, wordsFrom };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.CarbonSystemBuilder = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
