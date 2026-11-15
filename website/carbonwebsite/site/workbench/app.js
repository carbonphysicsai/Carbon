(function () {
  "use strict";
  const E = window.CarbonWorkbench,
    $ = (s) => document.querySelector(s),
    $$ = (s) => Array.from(document.querySelectorAll(s));
  const esc = (s) =>
    String(s).replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
  const newId = (prefix) =>
    prefix +
    "_" +
    (window.crypto && crypto.randomUUID
      ? crypto.randomUUID()
      : Date.now().toString(36) + "_" + Math.random().toString(36).slice(2));
  const steps = [
    "goal",
    "system",
    "contract",
    "evidence",
    "success",
    "constraints",
    "economics",
  ];
  const limits = {
    components: 12,
    couplings: 24,
    inputs: 24,
    outputs: 24,
    requirements: 24,
    sources: 12,
  };
  let job = E.newJob(newId("job")),
    dirty = false,
    invalid = false,
    activeStep = "goal",
    activeView = "client",
    atlasLimit = 6,
    timer;
  const money = (n) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: Math.abs(n) < 1 ? 4 : 0,
      notation: Math.abs(n) > 1e7 ? "compact" : "standard",
    }).format(n);
  const num = (n) =>
    new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(n);
  const toast = (s) => {
    $("#status-message").textContent = s;
    clearTimeout(timer);
    timer = setTimeout(() => {
      $("#status-message").textContent = "";
    }, 8000);
  };
  const options = (values, value, empty) =>
    `${empty !== undefined ? '<option value="">' + esc(empty) + "</option>" : ""}` +
    Object.entries(values)
      .map(
        ([v, label]) =>
          `<option value="${esc(v)}"${v === value ? " selected" : ""}>${esc(label)}</option>`,
      )
      .join("");
  const costLabels = {
    queries: "Predictions per month",
    baselineSeconds: "Current end-to-end time (s)",
    targetSeconds: "Target end-to-end time (s)",
    baselineCost: "Current cost / prediction (USD)",
    targetCost: "Target cost / prediction (USD)",
    setupCost: "One-time setup cost (USD)",
    monthlyCost: "Additional monthly cost (USD)",
    hardware: "Timing context / hardware",
  };
  function field(type, r, key, label, kind = "text", opts) {
    const domId = r.id + "_" + key,
      attr = `id="${esc(domId)}" data-list="${type}" data-row="${esc(r.id)}" data-field="${key}"`,
      v = r[key];
    if (kind === "select")
      return `<div><label for="${domId}">${label}</label><select ${attr}>${options(opts, v, ["from", "to", "output"].includes(key) ? "Select / unknown" : undefined)}</select></div>`;
    if (kind === "textarea")
      return `<div><label for="${domId}">${label}</label><textarea ${attr} rows="2" maxlength="${["coverage", "uncertainty", "definition"].includes(key) ? 1200 : 600}">${esc(v)}</textarea></div>`;
    const numeric = kind === "number";
    return `<div><label for="${domId}">${label}</label><input ${attr} type="${numeric ? "number" : "text"}" ${numeric ? 'step="' + (key === "count" ? "1" : "any") + '" max="1000000000000"' + (key === "count" ? ' min="0"' : "") : 'maxlength="' + (["unit"].includes(key) ? 80 : key === "purpose" ? 700 : key === "quantity" ? 300 : type === "components" && key === "name" ? 140 : 160) + '"'} value="${esc(v === null ? "" : v)}" placeholder="${numeric ? "Unknown" : "To define"}"></div>`;
  }
  function rowHTML(type, r, i) {
    let body = "";
    const f = (key, label, kind = "text", opts) =>
      field(type, r, key, label, kind, opts);
    if (type === "components")
      body =
        f("name", "Component / subsystem name") +
        f("physics", "Physical process", "select", E.PHYSICS) +
        f("regime", "Regime, boundaries or assumptions", "textarea");
    if (type === "couplings")
      body =
        `<div class="input-pair">${f("from", "From", "select", Object.fromEntries(job.problem.components.map((c) => [c.id, c.name || E.PHYSICS[c.physics]])))}${f("to", "To", "select", Object.fromEntries(job.problem.components.map((c) => [c.id, c.name || E.PHYSICS[c.physics]])))}</div>` +
        f("quantity", "Exchanged quantity or influence") +
        f("direction", "Interaction", "select", E.OPTIONS.coupling);
    if (type === "inputs")
      body =
        f("name", "Input / varying condition") +
        `<div class="input-pair">${f("unit", "Unit or representation")}${f("variation", "How it varies", "select", E.OPTIONS.variation)}</div><div class="input-pair">${f("min", "Lower bound", "number")}${f("max", "Upper bound", "number")}</div><p class="unit-note">Leave both bounds blank for categorical, geometry, history or unknown ranges.</p>` +
        f(
          "definition",
          "Domain details, categories, geometry or histories",
          "textarea",
        );
    if (type === "outputs")
      body =
        f("name", "Output / quantity you need") +
        `<div class="input-pair">${f("unit", "Unit or representation")}${f("priority", "Importance", "select", E.OPTIONS.priority)}</div>` +
        f("purpose", "Decision this output supports");
    if (type === "requirements")
      body =
        f(
          "output",
          "Output being assessed",
          "select",
          Object.fromEntries(
            job.problem.outputs.map((o) => [o.id, o.name || "Unnamed output"]),
          ),
        ) +
        f("kind", "Requirement type", "select", E.OPTIONS.criterion) +
        f("measure", "Measurement or interpretation", "textarea") +
        f(
          "operator",
          "How to interpret the target",
          "select",
          E.OPTIONS.operator,
        ) +
        `<div class="input-pair">${f("target", "Proposed target", "number")}${f("unit", "Target unit")}</div>`;
    if (type === "sources")
      body =
        f("name", "Source description") +
        `<div class="input-pair">${f("type", "Source type", "select", E.OPTIONS.dataType)}${f("role", "Possible role", "select", E.OPTIONS.dataRole)}</div><div class="input-pair">${f("access", "Permission / access", "select", E.OPTIONS.access)}${f("independence", "Independence", "select", E.OPTIONS.independence)}</div><div class="input-pair">${f("count", "Available count", "number")}${f("countUnit", "What are you counting?", "select", E.OPTIONS.countUnit)}</div>` +
        f("coverage", "Outputs and conditions covered", "textarea") +
        f("uncertainty", "Known uncertainty / quality limits", "textarea");
    return `<article class="collection-row" id="card_${esc(r.id)}"><div class="row-heading"><strong>${type === "requirements" ? "Criterion" : type === "sources" ? "Source" : type === "couplings" ? "Coupling" : type === "components" ? "Component" : type === "inputs" ? "Input" : "Output"} ${i + 1}</strong><button type="button" class="text-button remove-row" data-remove="${type}" data-id="${esc(r.id)}">Remove</button></div>${body}</article>`;
  }
  function renderEditors() {
    $$("[data-scalar]").forEach((el) => {
      const k = el.dataset.scalar;
      if (el.tagName === "SELECT")
        el.innerHTML = options(
          k === "goal" ? E.GOALS : E.OPTIONS[k],
          job.problem[k],
        );
      else el.value = job.problem[k];
    });
    for (const type of Object.keys(limits)) {
      $("#" + type + "-rows").innerHTML = job.problem[type].length
        ? job.problem[type].map((r, i) => rowHTML(type, r, i)).join("")
        : '<p class="collection-empty">No ' + type + " defined yet.</p>";
      const b = $(`[data-add="${type}"]`);
      b.disabled = job.problem[type].length >= limits[type];
    }
    $("#economics-fields").innerHTML =
      E.econKeys
        .filter((k) => k !== "matchedTiming")
        .map(
          (k) =>
            `<div><label for="cost_${k}">${costLabels[k]}</label><input id="cost_${k}" data-cost="${k}" ${k === "hardware" ? 'type="text" maxlength="300"' : 'type="number" min="0" max="1000000000" step="' + (k === "queries" ? "1" : "any") + '"'} value="${esc(job.problem.economics[k] === null ? "" : job.problem.economics[k])}" placeholder="${k === "hardware" ? "Comparable workload, batching and boundaries" : "Unknown / your assumption"}"></div>`,
        )
        .join("") +
      `<label class="check-label"><input id="cost_matchedTiming" data-cost="matchedTiming" type="checkbox"${job.problem.economics.matchedTiming ? " checked" : ""}>I intend to compare matching workloads and timing boundaries.</label>`;
    showStep(activeStep, false);
    wireRows();
  }
  function referenceOptions() {
    $$(
      '[data-list="couplings"][data-field="from"], [data-list="couplings"][data-field="to"]',
    ).forEach((el) => {
      const v = el.value;
      el.innerHTML = options(
        Object.fromEntries(
          job.problem.components.map((c) => [
            c.id,
            c.name || E.PHYSICS[c.physics],
          ]),
        ),
        v,
        "Select / unknown",
      );
    });
    $$('[data-list="requirements"][data-field="output"]').forEach((el) => {
      const v = el.value;
      el.innerHTML = options(
        Object.fromEntries(
          job.problem.outputs.map((o) => [o.id, o.name || "Unnamed output"]),
        ),
        v,
        "Select / unknown",
      );
    });
  }
  function collect() {
    const p = E.copy(job.problem);
    for (const el of $$("[data-scalar],[data-list][data-field],[data-cost]")) {
      if (!el.validity.valid)
        throw Error(
          "Correct " +
            (document.querySelector(`label[for="${el.id}"]`)?.textContent ||
              "the field") +
            " before using the updated preview.",
        );
      const value =
        el.type === "checkbox"
          ? el.checked
          : el.type === "number"
            ? el.value === ""
              ? null
              : Number(el.value)
            : el.value;
      if (el.dataset.scalar) p[el.dataset.scalar] = value;
      else if (el.dataset.cost) p.economics[el.dataset.cost] = value;
      else {
        const target = p[el.dataset.list].find((r) => r.id === el.dataset.row);
        if (!target) throw Error("Missing row.");
        target[el.dataset.field] = value;
      }
    }
    E.validateProblem(p);
    return p;
  }
  function disabled(value) {
    for (const id of [
      "download-brief",
      "download-draft",
      "save-top",
      "checkpoint",
      "fork",
      "print-brief",
    ])
      $("#" + id).disabled = value;
  }
  function edited() {
    dirty = true;
    try {
      job.problem = collect();
      dirty = true;
      invalid = false;
      renderResults();
      referenceOptions();
    } catch (e) {
      invalid = true;
      disabled(true);
      $("#input-error").hidden = false;
      $("#input-error").textContent =
        e.message +
        " The preview retains the last valid record. Exports are disabled until correction.";
      $("#draft-label").textContent = "Correct inputs to update";
    }
  }
  $("#problem-form").addEventListener("input", edited);
  $("#problem-form").addEventListener("submit", (e) => e.preventDefault());
  function commitProblem(p) {
    E.validateProblem(p);
    job.problem = p;
    dirty = true;
    invalid = false;
    renderEditors();
    renderResults();
  }
  function wireRows() {
    $$("[data-remove]").forEach((b) =>
      b.addEventListener("click", () => {
        if (invalid) {
          toast(
            "Correct invalid inputs before removing a row so other edits remain intact.",
          );
          return;
        }
        const type = b.dataset.remove,
          rowId = b.dataset.id;
        const linked =
          type === "components"
            ? job.problem.couplings.filter(
                (r) => r.from === rowId || r.to === rowId,
              ).length
            : type === "outputs"
              ? job.problem.requirements.filter((r) => r.output === rowId)
                  .length
              : 0;
        if (
          linked &&
          !window.confirm(
            type === "components"
              ? `Remove this component and its ${linked} coupling(s)?`
              : `Remove this output? ${linked} criterion link(s) will become unknown; the criteria remain.`,
          )
        )
          return;
        commitProblem(E.removeRow(job.problem, type, rowId));
        toast("Row removed. Review the updated scope and evidence plan.");
      }),
    );
  }
  $$("[data-add]").forEach((b) =>
    b.addEventListener("click", () => {
      if (invalid) {
        toast("Correct the invalid input first.");
        return;
      }
      const type = b.dataset.add,
        p = E.copy(job.problem);
      if (p[type].length >= limits[type]) return;
      const r = E.row(type, newId(type.slice(0, 3)));
      if (type === "couplings" && p.components.length >= 2) {
        r.from = p.components[0].id;
        r.to = p.components[1].id;
      }
      if (type === "requirements" && p.outputs.length)
        r.output = p.outputs[0].id;
      p[type].push(r);
      commitProblem(p);
      document
        .querySelector(`#card_${r.id} input, #card_${r.id} select`)
        ?.focus();
    }),
  );
  function systemMap(p) {
    const count = p.components.length;
    if (!count)
      return '<div class="collection-empty">Add a component to draw your system. You can name a custom process or choose “Not sure yet”.</div>';
    const h = 90 + count * 65,
      w = 340,
      top = 40,
      pos = Object.fromEntries(
        p.components.map((c, i) => [c.id, top + i * 65]),
      );
    const trim = (s, n) => (s.length > n ? s.slice(0, n - 1) + "…" : s);
    const links = p.couplings
      .filter((c) => c.from && c.to && c.from !== c.to)
      .map((l, i) => {
        const x = 283 + (i % 7) * 6,
          y1 = pos[l.from] + 20,
          y2 = pos[l.to] + 20;
        return `<path class="link" d="M272 ${y1}H${x}V${y2}H272" marker-end="url(#arrow)"${l.direction === "twoway" ? ' marker-start="url(#arrowBack)"' : ""}><title>${esc(l.quantity || "Quantity to define")}</title></path>`;
      })
      .join("");
    const nodes = p.components
      .map(
        (c) =>
          `<g><rect class="box" x="12" y="${pos[c.id]}" width="260" height="46"/><text x="23" y="${pos[c.id] + 18}">${esc(trim(c.name || "Unnamed component", 35))}</text><text class="small" x="23" y="${pos[c.id] + 34}">${esc(E.PHYSICS[c.physics])}</text><title>${esc(c.name)}: ${esc(c.regime || "Regime to define")}</title></g>`,
      )
      .join("");
    const names = Object.fromEntries(
      p.components.map((c) => [c.id, c.name || E.PHYSICS[c.physics]]),
    );
    return (
      `<svg class="system-svg" viewBox="0 0 ${w} ${h}" role="img" aria-labelledby="system-title system-desc"><title id="system-title">Your proposed physical system</title><desc id="system-desc">${count} components and ${p.couplings.length} proposed couplings. See the text list for connections.</desc><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0 10 5 0 10Z" fill="#ce3f29"/></marker><marker id="arrowBack" viewBox="0 0 10 10" refX="1" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M10 0 0 5 10 10Z" fill="#ce3f29"/></marker></defs><text class="small" x="12" y="22">${p.inputs.length} inputs / proposed connections</text>${links}${nodes}<text class="small" x="12" y="${h - 12}">${p.outputs.length} outputs / ${p.requirements.length} criteria to review</text></svg>` +
      (p.couplings.length
        ? `<ul class="map-links">${p.couplings.map((c) => `<li>${esc(names[c.from] || "Unknown")} ${c.direction === "twoway" ? "↔" : "→"} ${esc(names[c.to] || "Unknown")}: ${esc(c.quantity || "quantity to define")}</li>`).join("")}</ul>`
        : '<p class="micro">No coupling defined.</p>')
    );
  }
  function table(heads, rows, cls = "") {
    return `<div class="table-wrap"><table class="review-table ${cls}"><thead><tr>${heads.map((h) => `<th scope="col">${h}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${row.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
  }
  function client(p) {
    const x = job.problem;
    return `<p class="micro">Draft ${esc(job.id)} / revision ${job.revision} / ${esc(E.RULES)} / ${esc(job.origin)}</p><div class="result-grid"><div><p class="eyebrow">Client challenge preview</p><h3>${esc(x.title || "Your engineering problem")}</h3><p>${esc(x.description || "Describe the system to begin your proposed study.")}</p><div class="claim-box"><p>${esc(x.decision || p.method.claim)}</p><span class="note">Your intended decision. Performance remains unmeasured.</span></div><article class="route"><span class="micro">Proposed entry point</span><h3>${esc(p.route)}</h3><p>${esc(p.method.claim)}</p></article></div><div><h3>What you could receive</h3>${p.deliverables.map((d, i) => `<article class="method-card"><p class="micro">0${i + 1} / Proposed deliverable</p><p>${esc(d)}</p></article>`).join("")}</div></div>
 <h3>The model’s proposed contract</h3>${table(["Model receives", "Model returns"], [[x.inputs.length ? x.inputs.map((i) => esc(i.name || "Unnamed input") + ' <span class="micro">' + esc(i.unit || "unit / representation unknown") + "</span>").join("<br>") : "Inputs to define", x.outputs.length ? x.outputs.map((o) => esc(o.name || "Unnamed output") + ' <span class="micro">' + esc(o.unit || "unit / representation unknown") + "</span>").join("<br>") : "Outputs to define"]])}
 <h3 class="subheading">Proposed success criteria</h3>${
   x.requirements.length
     ? table(
         ["Output / requirement", "Measurement", "Proposed criterion"],
         x.requirements.map((r) => [
           esc(
             x.outputs.find((o) => o.id === r.output)?.name ||
               "Output to define",
           ) +
             '<br><span class="micro">' +
             esc(E.OPTIONS.criterion[r.kind]) +
             "</span>",
           esc(r.measure || "Measurement to define"),
           esc(E.OPTIONS.operator[r.operator]) +
             (r.target === null
               ? " / target to agree"
               : " " + esc(r.target) + " " + esc(r.unit || "unit to define")),
         ]),
       )
     : '<p class="note">Add criteria to show what a successful result would need to demonstrate.</p>'
 }<p class="note">These are requested targets. They are not measured performance or a promise of delivery.</p>
 <div class="notice"><strong>Evidence limit</strong><p>${esc(p.referenceBoundary)}</p></div><h3 class="subheading">Compare sensible paths</h3><ul>${p.alternatives.map((a) => `<li>${esc(a)}</li>`).join("")}</ul><div class="next-card"><div><p class="eyebrow">The next useful step</p><h3>${esc(p.next)}</h3></div></div>`;
  }
  function evidence(p) {
    const x = job.problem;
    const scopeRows = x.outputs.map((o) => [
      esc(o.name || "Unnamed output"),
      esc(o.purpose || "Decision to define"),
      x.sources.length
        ? "Source-to-output coverage needs review"
        : "No source listed",
      "Not measured",
    ]);
    return `<div class="result-grid"><div><p class="eyebrow">Evidence plan</p><h3>Match the evidence to the claim.</h3><p>${esc(p.method.measure)}</p><p class="note">${esc(p.referenceBoundary)}</p>${p.evidenceStages.map((s, i) => `<article class="method-card"><p class="micro">0${i + 1}</p><h4>${s.name}</h4><p>${esc(s.text)}</p></article>`).join("")}</div><div><h3>Method and regime review</h3>${p.guidance.length ? p.guidance.map((g) => `<details class="method-details"><summary>${esc(g.name)} / proposed checklist</summary><p>${esc(g.review)}</p><p><strong>Reference:</strong> ${esc(g.reference)}</p><p><strong>Measurements:</strong> ${esc(g.measure)}</p><p class="micro">${esc(g.status)}</p></details>`).join("") : '<p class="note">Add physics to inspect relevant scoping checklists.</p>'}<div class="notice"><strong>System and time behavior</strong><p>${esc(p.coupling)}</p><p>${esc(p.time)}</p></div></div></div>
 <h3 class="subheading">Coverage you would need to establish</h3>${scopeRows.length ? table(["Requested output", "Engineering purpose", "Reference coverage", "Result"], scopeRows) : '<p class="note">Add outputs to assemble a coverage review.</p>'}
 <h3 class="subheading">Reported evidence sources</h3>${
   x.sources.length
     ? table(
         [
           "Source / use",
           "Access / dependence",
           "Reported count",
           "Coverage / uncertainty",
         ],
         x.sources.map((s) => [
           esc(s.name || "Unnamed source") +
             "<br>" +
             esc(E.OPTIONS.dataType[s.type]) +
             "<br>" +
             esc(E.OPTIONS.dataRole[s.role]),
           esc(E.OPTIONS.access[s.access]) +
             "<br>" +
             esc(E.OPTIONS.independence[s.independence]),
           s.count === null
             ? "Unknown"
             : esc(s.count) + " " + esc(E.OPTIONS.countUnit[s.countUnit]),
           esc(s.coverage || "Coverage to review") +
             "<br><br>" +
             esc(s.uncertainty || "Uncertainty to review"),
         ]),
       )
     : '<p class="note">No sources recorded. Start by identifying the reference a useful comparison would require.</p>'
 }
 <details class="method-details"><summary>Scientific interpretation and scoring boundaries</summary><p>Define the target population, evaluation sampling and score weighting as separate choices. A specialist must review reference uncertainty, dependence and the resolution needed to distinguish candidates before selecting a sample count.</p><p>Freeze confirmatory criteria before observing outcomes. Preserve reference and infrastructure failures separately from model failures. No favorable economics can compensate for a failed mandatory physical requirement.</p><p>Do not compare scalar challenge scores across unrelated problems without a justified mapping. A customer’s target does not create an official score, approved threshold or scientific result.</p></details>`;
  }
  function record() {
    const p = job.problem;
    return `<p class="eyebrow">Complete review record</p><p class="micro">${esc(job.id)} / working revision ${job.revision} / ${esc(E.RULES)}</p><p>Origin: ${esc(job.origin)}. Values are working descriptions and assumptions, not authenticated facts or measured outcomes.</p>${job.migration ? `<div class="notice"><strong>Legacy migration retained</strong><p>${esc(job.migration.note)}</p><p>Original draft text and checkpoints remain inside the editable export.</p></div>` : ""}<pre>${esc(JSON.stringify(p, null, 2))}</pre><details class="method-details"><summary>Local checkpoint history (${job.checkpoints.length})</summary>${job.checkpoints.length ? job.checkpoints.map((c) => `<details><summary>v${c.revision} / ${esc(c.label)}</summary><pre>${esc(JSON.stringify(c.problem, null, 2))}</pre></details>`).join("") : "<p>No checkpoints retained.</p>"}</details>`;
  }
  function costChart(e) {
    const points = e.curve,
      xmax = Math.max(1, ...points.map((x) => x.queries));
    let lo = Math.min(0, ...points.map((x) => x.value)),
      hi = Math.max(0, ...points.map((x) => x.value));
    if (lo === hi) {
      lo--;
      hi++;
    }
    const sx = (x) => 65 + (x / xmax) * 395,
      sy = (y) => 175 - ((y - lo) / (hi - lo)) * 140,
      d = points
        .map(
          (p, i) =>
            (i ? "L" : "M") +
            sx(p.queries).toFixed(2) +
            "," +
            sy(p.value).toFixed(2),
        )
        .join(" ");
    return `<figure class="chart"><figcaption class="micro">Twelve-month net / scenario</figcaption><svg viewBox="0 0 485 225" role="img" aria-label="Scenario net value as monthly prediction volume varies"><line x1="65" x2="65" y1="35" y2="175"/><line x1="65" x2="460" y1="175" y2="175"/><line class="zero" x1="65" x2="460" y1="${sy(0)}" y2="${sy(0)}"/><path d="${d}"/><text x="60" y="38" text-anchor="end">${esc(money(hi))}</text><text x="60" y="177" text-anchor="end">${esc(money(lo))}</text><text x="65" y="196">0</text><text x="460" y="196" text-anchor="end">${num(xmax)}</text><text x="260" y="220" text-anchor="middle">Predictions per month</text></svg></figure>`;
  }
  function costResult(e) {
    const timing = e.timingKnown
      ? `<p class="note">Timing assumptions imply ${num(Math.abs(e.secondsSaved) / 3600)} aggregate execution hours ${e.secondsSaved < 0 ? "added" : "saved"} per month. This is not measured speedup or calendar time.</p>`
      : "";
    if (e.kind === "unknown")
      return `<div class="empty-chart"><h4>Cost inputs remain unknown.</h4><p class="note">Needed: ${e.missing.map((k) => esc(costLabels[k])).join(", ")}.</p>${timing}</div>`;
    return `<div class="metric-row"><div><span>Monthly net</span><strong>${money(e.monthlyNet)}</strong></div><div><span>Setup break-even</span><strong>${e.months === null ? "Not reached" : num(e.months) + " mo"}</strong></div><div><span>Twelve-month net</span><strong>${money(e.annualNet)}</strong></div></div>${costChart(e)}${timing}<p class="note">${e.maxTargetCost12 === null ? "Enter positive volume to inspect a cost boundary." : e.maxTargetCost12 < 0 ? "These assumptions do not recover setup within twelve months even with zero target cost per prediction." : "The target cost would need to stay at or below " + money(e.maxTargetCost12) + " per prediction to recover setup within twelve months. This does not establish achievability."}</p>`;
  }
  function renderResults() {
    const p = E.derive(job.problem);
    invalid = false;
    disabled(false);
    $("#working-title").textContent =
      job.problem.title || "Untitled engineering problem";
    $("#draft-label").textContent = "Local draft · v" + job.revision;
    $("#input-error").hidden = !p.contradictions.length;
    $("#input-error").textContent =
      p.contradictions.join(" ") +
      " Draft exports retain these unresolved contradictions; this is not an executable challenge.";
    $("#system-map").innerHTML = systemMap(job.problem);
    $("#live-summary").innerHTML =
      `<div class="summary-counts"><span>${job.problem.components.length} components</span><span>${job.problem.inputs.length} inputs</span><span>${job.problem.outputs.length} outputs</span></div><h3>${esc(p.route)}</h3>${p.gaps
        .slice(0, 3)
        .map(
          (g) =>
            `<div class="gap-item"><strong>${esc(g.topic)}</strong><br>${esc(g.text)}</div>`,
        )
        .join(
          "",
        )}<p class="micro">${p.gaps.length} proposed review items. This is a work list, not a feasibility score.</p>`;
    $("#result-client").innerHTML = client(p);
    $("#result-evidence").innerHTML = evidence(p);
    $("#result-record").innerHTML = record();
    $("#economics-result").innerHTML = costResult(p.economics);
    const changed = E.changes(job);
    $("#revision-diff").innerHTML =
      `<strong>Changes since the last checkpoint</strong><p>${!job.checkpoints.length ? "Keep a local checkpoint before exploring alternatives. Save an editable draft to retain it after closing this page." : changed.length ? esc(changed.join(", ")) + ". Review affected claims, methods, data and costs. No prior scientific evidence carries over by default." : "The current problem matches the latest checkpoint."}</p>`;
    showView(activeView, false);
  }
  function showStep(name, focus) {
    activeStep = name;
    $$("[data-step]").forEach((b) => {
      const yes = b.dataset.step === name;
      b.setAttribute("aria-selected", String(yes));
      b.tabIndex = yes ? 0 : -1;
      $("#editor-" + b.dataset.step).hidden = !yes;
      if (yes && focus) b.focus();
    });
    $("#previous-step").disabled = steps.indexOf(name) === 0;
    $("#next-step-button").textContent =
      name === "economics" ? "Inspect your challenge →" : "Next section →";
  }
  function showView(name, focus) {
    activeView = name;
    $$("[data-view]").forEach((b) => {
      const yes = b.dataset.view === name;
      b.setAttribute("aria-selected", String(yes));
      b.tabIndex = yes ? 0 : -1;
      $("#result-" + b.dataset.view).hidden = !yes;
      if (yes && focus) b.focus();
    });
  }
  function keyboardTabs(buttons, attr, show, vertical) {
    buttons.forEach((b, i) => {
      b.addEventListener("click", () => show(b.dataset[attr], false));
      b.addEventListener("keydown", (e) => {
        let n;
        if (e.key === (vertical ? "ArrowDown" : "ArrowRight"))
          n = (i + 1) % buttons.length;
        if (e.key === (vertical ? "ArrowUp" : "ArrowLeft"))
          n = (i + buttons.length - 1) % buttons.length;
        if (e.key === "Home") n = 0;
        if (e.key === "End") n = buttons.length - 1;
        if (n !== undefined) {
          e.preventDefault();
          show(buttons[n].dataset[attr], true);
        }
      });
    });
  }
  keyboardTabs($$("[data-step]"), "step", showStep, true);
  keyboardTabs($$("[data-view]"), "view", showView, false);
  $("#previous-step").addEventListener("click", () =>
    showStep(steps[Math.max(0, steps.indexOf(activeStep) - 1)], true),
  );
  $("#next-step-button").addEventListener("click", () => {
    if (activeStep === "economics") {
      $("#assessment").scrollIntoView();
      $("#view-client").focus();
      showView("client", false);
    } else showStep(steps[steps.indexOf(activeStep) + 1], true);
  });
  function loadJob(next) {
    job = next;
    invalid = false;
    dirty = false;
    renderEditors();
    renderResults();
    showStep("goal", false);
    showView("client", false);
    $("#composer").scrollIntoView();
  }
  function mayReplace() {
    return (
      !dirty ||
      window.confirm(
        "Replace this unsaved problem? Export an editable draft first if you want to retain it.",
      )
    );
  }
  $$("[data-example]").forEach((b) =>
    b.addEventListener("click", () => {
      if (mayReplace()) {
        loadJob(E.template(b.dataset.example, newId("job")));
        toast(
          "Example loaded. Review and edit the starting assumptions for your own problem.",
        );
      }
    }),
  );
  function blank() {
    if (mayReplace()) {
      loadJob(E.newJob(newId("job")));
      toast("Blank problem started. Downloaded files remain on your device.");
    }
  }
  $("#blank-button").addEventListener("click", blank);
  $("#reset-button").addEventListener("click", blank);
  function download(content, name, type) {
    const url = URL.createObjectURL(new Blob([content], { type })),
      a = document.createElement("a");
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function save() {
    try {
      if (invalid) return;
      download(
        E.exportJob(job),
        job.id + "-v" + job.revision + ".json",
        "application/json",
      );
      dirty = false;
      toast(
        "Editable draft exported. Reopen it with Continue a draft. No inquiry was sent.",
      );
    } catch (e) {
      toast(e.message);
    }
  }
  $("#save-top").addEventListener("click", save);
  $("#download-draft").addEventListener("click", save);
  $("#download-brief").addEventListener("click", () => {
    if (invalid) return;
    download(E.brief(job), job.id + "-brief.txt", "text/plain");
    toast(
      "Readable brief exported. Save an editable draft to preserve all checkpoints.",
    );
  });
  $("#checkpoint").addEventListener("click", () => {
    try {
      if (invalid) return;
      job = E.checkpoint(job, "Working assumptions");
      dirty = true;
      renderResults();
      toast(
        "Local checkpoint kept. Export the draft to preserve it after closing.",
      );
    } catch (e) {
      toast(e.message);
    }
  });
  $("#fork").addEventListener("click", () => {
    if (invalid) return;
    if (
      !window.confirm(
        "Fork the current problem into a new job identity? Export the current draft first to keep its checkpoint history.",
      )
    )
      return;
    job = E.fork(job, newId("job"));
    dirty = true;
    renderResults();
    toast(
      "New job identity created. The working problem and migration record remain; checkpoint history starts empty.",
    );
  });
  $("#print-brief").addEventListener("click", () => {
    if (invalid) return;
    showView("client", false);
    window.print();
  });
  $("#illustration").addEventListener("click", () => {
    if (invalid) {
      toast("Correct invalid inputs first.");
      return;
    }
    if (
      Object.values(job.problem.economics).some(
        (x) => x !== null && x !== "" && x !== false,
      ) &&
      !window.confirm(
        "Replace the economics fields with illustrative assumptions?",
      )
    )
      return;
    const p = E.copy(job.problem);
    Object.assign(p.economics, {
      queries: 10000,
      baselineCost: 0.5,
      targetCost: 0.02,
      setupCost: 5000,
      monthlyCost: 500,
      baselineSeconds: 60,
      targetSeconds: 0.5,
      hardware: "Illustration: comparable workload and boundaries",
      matchedTiming: true,
    });
    commitProblem(p);
    toast(
      "Illustrative assumptions loaded. No measured result or price quote.",
    );
  });
  for (const id of ["import-button", "resume-top"])
    $("#" + id).addEventListener("click", () => $("#import-file").click());
  $("#import-file").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    try {
      if (file.size > E.MAX_BYTES) throw Error("Draft exceeds 2 MB.");
      const item = E.importJob(await file.text());
      if (!mayReplace()) return;
      if (item.kind === "rules_update" && !window.confirm("Update planning rules? Your original draft will be retained. Review the additional evidence questions.")) return;
      if (item.kind === "legacy") {
        if (
          !window.confirm(
            "This is a cooling v0.2 draft. Migrate it into a general problem? The export will retain the original text, origins and historical checkpoints. Review the mapped fields before use.",
          )
        )
          return;
        loadJob(E.migrateLegacy(item.originalText));
        dirty = true;
        toast(
          "Legacy cooling draft migrated. Inspect Full record for mapping limits and the retained original.",
        );
      } else {
        const atlasIds = new Set(
          window.CARBON_ATLAS.opportunities.map((o) => o.id),
        );
        if (item.job.problem.sourceRefs.some((x) => !atlasIds.has(x)))
          throw Error("Draft refers to an unknown atlas lead.");
        loadJob(item.job);
        toast(
          "General problem imported. No approval or measured evidence was imported.",
        );
      }
    } catch (err) {
      toast(err.message);
    } finally {
      e.target.value = "";
    }
  });
  window.addEventListener("beforeunload", (e) => {
    if (dirty) {
      e.preventDefault();
      e.returnValue = "";
    }
  });
  function atlas() {
    const q = $("#atlas-search").value.trim().toLowerCase(),
      matches = window.CARBON_ATLAS.opportunities.filter((o) =>
        (o.title + " " + o.engineering_jobs_source).toLowerCase().includes(q),
      );
    $("#atlas-content").innerHTML =
      `<p class="micro">${matches.length} research leads</p>` +
      (matches.length
        ? `<div class="atlas-grid">${matches
            .slice(0, atlasLimit)
            .map(
              (o) =>
                `<article class="atlas-card"><span class="micro">${esc(o.id)} / Research lead</span><h3>${esc(o.title)}</h3><p>${esc(o.engineering_jobs_source)}</p><details><summary>Inspect the source strategy</summary><p>${esc(o.reference_path_source)}</p><p>${esc(o.path_and_risk_source)}</p><p class="micro">Historical recommendation. Applicability and implementation remain to review.</p></details><button class="text-button" data-use-lead="${esc(o.id)}">Add to my problem +</button></article>`,
            )
            .join("")}</div>`
        : '<div class="empty-chart"><h3>No matching research lead.</h3><p>You can describe this physics with a custom component. Your problem does not have to match the catalogue.</p><button id="custom-from-search" class="text-button">Add a custom component →</button></div>') +
      (matches.length > atlasLimit
        ? '<button id="show-more" class="text-button atlas-more">Show more research leads ↓</button>'
        : "");
    const more = $("#show-more");
    if (more)
      more.addEventListener("click", () => {
        atlasLimit += 12;
        atlas();
      });
    $$("[data-use-lead]").forEach((b) =>
      b.addEventListener("click", () => {
        if (invalid) {
          toast("Correct the invalid field first.");
          return;
        }
        const o = window.CARBON_ATLAS.opportunities.find(
            (x) => x.id === b.dataset.useLead,
          ),
          p = E.copy(job.problem);
        if (
          p.components.length >= limits.components ||
          p.sourceRefs.length >= 20
        ) {
          toast(
            "The local draft has reached its component/source limit. Save and fork a narrower study.",
          );
          return;
        }
        if (p.sourceRefs.includes(o.id)) {
          toast("This research lead is already linked to the problem.");
          return;
        }
        p.components.push({
          ...E.row("components", newId("component")),
          name: o.title,
          physics: "unknown",
          regime:
            "Research lead " +
            o.id +
            ". Select applicable physics and define the scope.",
        });
        p.sourceRefs.push(o.id);
        commitProblem(p);
        showStep("system", false);
        $("#composer").scrollIntoView();
        toast(
          "Research lead added. Choose its physical process and define the component’s role.",
        );
      }),
    );
    const custom = $("#custom-from-search");
    if (custom)
      custom.addEventListener("click", () => {
        showStep("system", false);
        $("#composer").scrollIntoView();
        $('[data-add="components"]').focus();
      });
  }
  $("#atlas-search").addEventListener("input", () => {
    atlasLimit = 6;
    atlas();
  });
  window.CarbonDraftUI = Object.freeze({
    get:()=>E.copy(job),
    applyReviewed:(next)=>{E.validateJob(next);loadJob(next);dirty=true;toast("Reviewed suggestions added. They remain your working assumptions.");},
    valid:()=>!invalid
  });
  renderEditors();
  renderResults();
  atlas();
})();
