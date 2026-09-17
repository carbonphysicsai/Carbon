(function (root) {
  "use strict";
  const TEMPLATE = "periodic_viscous_burgers_1d_v1";
  const REQUEST = "carbon.workbench.scientific-study.request.v1";
  const RESPONSE = "carbon.workbench.scientific-study.response.v1";
  const CAPABILITIES = "carbon.workbench.scientific-study.capabilities.v1";
  const BUNDLE = "carbon.workbench.scientific-study.bundle.v1";
  const SCOPE = ["physics_family", "requested_goal", "inputs", "outputs", "units", "geometry", "conditions", "regime", "exclusions", "query_workload", "rights_scope"];
  const BUDGET = ["research_trials_remaining", "numerical_milliseconds_remaining", "reference_invocations_remaining"];
  const STATES = ["PENDING", "RUNNING", "COMPLETE", "FAILED", "CANCELLED", "CANCEL_REQUESTED", "REQUIRES_RECONCILIATION"];
  const clone = (v) => JSON.parse(JSON.stringify(v));
  function exact(v, keys, label) {
    if (!v || typeof v !== "object" || Array.isArray(v) || ![Object.prototype, null].includes(Object.getPrototypeOf(v)) || Object.keys(v).sort().join("|") !== [...keys].sort().join("|")) throw Error(label + ": closed fields required");
    return v;
  }
  function text(v, label, max = 8000) {
    if (typeof v !== "string" || !v.length || v.length > max) throw Error(label + ": bounded text required");
    return v;
  }
  function ident(v) { if (typeof v !== "string" || !/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(v)) throw Error("Invalid identity"); return v; }
  function finite(v) { if (typeof v !== "number" || !Number.isFinite(v)) throw Error("Finite numerical value required"); return v; }
  function plain(v, depth = 0) {
    if (depth > 12) throw Error("Study data nesting limit");
    if (v === null || typeof v === "boolean" || typeof v === "string") return;
    if (typeof v === "number") return finite(v);
    if (Array.isArray(v)) { if (v.length > 2048) throw Error("Study array limit"); v.forEach((x) => plain(x, depth + 1)); return; }
    if (v && [Object.prototype, null].includes(Object.getPrototypeOf(v))) {
      Object.entries(v).forEach(([k, x]) => { if (["__proto__", "constructor", "prototype"].includes(k)) throw Error("Unsafe study key"); plain(x, depth + 1); }); return;
    }
    throw Error("Plain JSON study data required");
  }
  function bounded(v) { plain(v); if (new TextEncoder().encode(JSON.stringify(v)).length > 131072) throw Error("Study byte limit"); return v; }
  function canonical(v) {
    if (Array.isArray(v)) return v.map(canonical);
    if (v && typeof v === "object") return Object.fromEntries(Object.keys(v).sort().map((k) => [k, canonical(v[k])]));
    return v;
  }
  function same(a, b) { return JSON.stringify(canonical(a)) === JSON.stringify(canonical(b)); }
  function digestValue(v) {
    if (typeof v === "number") {
      finite(v);
      const buffer = new ArrayBuffer(8); new DataView(buffer).setFloat64(0, v, false);
      return { $f64: Array.from(new Uint8Array(buffer), (n) => n.toString(16).padStart(2, "0")).join("") };
    }
    if (Array.isArray(v)) return v.map(digestValue);
    if (v && typeof v === "object") return Object.fromEntries(Object.keys(v).sort().map((k) => [k, digestValue(v[k])]));
    return v;
  }
  async function digest(v) {
    const bytes = new TextEncoder().encode(JSON.stringify(digestValue(v)));
    const hash = await root.crypto.subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(hash), (n) => n.toString(16).padStart(2, "0")).join("");
  }
  function physical(v) {
    exact(v, ["domain_length", "viscosity", "mean", "cosine_coefficients", "sine_coefficients", "requested_times", "output_points", "units"], "physical definition");
    if (finite(v.domain_length) <= 0 || finite(v.viscosity) <= 0) throw Error("Positive domain length and viscosity required");
    finite(v.mean);
    for (const k of ["cosine_coefficients", "sine_coefficients"]) {
      if (!Array.isArray(v[k]) || v[k].length !== 12) throw Error("Twelve Fourier coefficients required");
      v[k].forEach(finite);
    }
    if (!Array.isArray(v.requested_times) || v.requested_times.length !== 13) throw Error("Thirteen requested times required");
    v.requested_times.forEach((t) => { if (finite(t) < 0) throw Error("Nonnegative time required"); });
    if (v.output_points !== 64 || v.units !== "dimensionless") throw Error("Only source-owned 64 point dimensionless layout is supported");
    return clone(v);
  }
  function scope(d) {
    const result = Object.fromEntries(SCOPE.map((key) => [key, d.scope[key]]));
    result.reference_equation = d.reference_plan.equation;
    result.reference_method = d.reference_plan.method;
    Object.values(result).forEach((v) => { if (typeof v !== "string" || v.length > 8000) throw Error("Invalid draft scope"); });
    return result;
  }
  function check(d, p = null) {
    const issues = [];
    if (d.scope.physics_family !== TEMPLATE) issues.push("Only the public periodic Burgers source template is available.");
    if (d.scope.requested_goal !== "Dynamics") issues.push("The source template requires the Dynamics goal.");
    if (d.scope.rights_scope !== "SYNTHETIC_INTERNAL") issues.push("Private or unresolved rights are unavailable for this public-source study.");
    for (const key of ["inputs", "outputs", "units", "geometry", "conditions"]) if (!d.scope[key]) issues.push("Missing " + key + ".");
    if (/\b(SI|dimensional|metres|meters|seconds)\b/i.test(d.scope.units)) issues.push("The draft names dimensional units; the available source study uses dimensionless variables and cannot convert them.");
    if (/\b(dirichlet|neumann|nonperiodic|non-periodic|forced)\b/i.test(d.scope.conditions)) issues.push("The draft names a boundary or forcing condition outside the unforced periodic source template.");
    if (!d.reference_plan.equation) issues.push("Missing governing equation.");
    if (p !== null) { try { physical(p); } catch (error) { issues.push(error.message); } }
    else issues.push("Adopt the private service's exact public-source physical definition.");
    return { status: issues.length ? "INPUTS_UNRESOLVED" : "STRUCTURALLY_CHECKED", issues, qualification: "NOT_QUALIFIED", limitations: "Structural DEVELOPMENT checks only. Free text, units and boundary conditions need source-owner binding; the service must reject an unregistered or changed draft." };
  }
  function capabilities(v) {
    bounded(v);
    exact(v, ["schema", "template_id", "physical", "method", "environment", "available"], "capabilities");
    if (v.schema !== CAPABILITIES || v.template_id !== TEMPLATE || typeof v.available !== "boolean") throw Error("Unsupported study capability");
    physical(v.physical); text(v.method, "method", 300); text(v.environment, "environment", 300);
    return clone(v);
  }
  function binding(v) {
    exact(v, ["job_id", "design_id", "design_revision", "physical_sha256"], "study binding");
    ident(v.job_id); ident(v.design_id);
    if (!Number.isSafeInteger(v.design_revision) || v.design_revision < 1 || !/^[a-f0-9]{64}$/.test(v.physical_sha256)) throw Error("Invalid study binding");
  }
  function request(v) {
    bounded(v);
    exact(v, ["schema", "operation_id", "action", "binding", "template_id", "physical", "draft_scope", "rights_scope"], "study request");
    if (v.schema !== REQUEST || v.action !== "REFERENCE_FEASIBILITY" || v.template_id !== TEMPLATE || v.rights_scope !== "SYNTHETIC_INTERNAL") throw Error("Unsupported scientific study request");
    ident(v.operation_id); if (v.operation_id.length < 16 || v.operation_id.length > 114) throw Error("Invalid operation identity");
    binding(v.binding); physical(v.physical);
    exact(v.draft_scope, [...SCOPE, "reference_equation", "reference_method"], "draft scope");
    Object.values(v.draft_scope).forEach((s) => { if (typeof s !== "string" || s.length > 8000) throw Error("Invalid draft scope"); });
    return clone(v);
  }
  async function prepare(d, p) {
    const validated = physical(p), draftScope = scope(d), checked = check(d, p);
    if (checked.issues.length) throw Error(checked.issues.join(" "));
    const b = { job_id: ident(d.job_id), design_id: ident(d.design_id), design_revision: d.revision, physical_sha256: await digest({ template_id: TEMPLATE, physical: validated, draft_scope: draftScope }) };
    return request({ schema: REQUEST, operation_id: "study-" + await digest(b), action: "REFERENCE_FEASIBILITY", binding: b, template_id: TEMPLATE, physical: validated, draft_scope: draftScope, rights_scope: "SYNTHETIC_INTERNAL" });
  }
  function response(v, r) {
    bounded(v);
    exact(v, ["schema", "operation_id", "task_id", "status", "binding", "remaining_budget", "method", "environment", "result", "official_eligible", "qualification"], "study response");
    if (v.schema !== RESPONSE || v.operation_id !== r.operation_id || !same(v.binding, r.binding)) throw Error("Wrong study operation or draft binding");
    binding(v.binding); ident(v.task_id);
    if (!STATES.includes(v.status) || v.official_eligible !== false || v.qualification !== "NOT_QUALIFIED") throw Error("Study authority or status rejected");
    exact(v.remaining_budget, BUDGET, "remaining budget");
    Object.values(v.remaining_budget).forEach((n) => { if (n !== null && (!Number.isSafeInteger(n) || n < 0)) throw Error("Invalid remaining budget"); });
    text(v.method, "method", 300); text(v.environment, "environment", 300);
    if (v.result !== null) {
      exact(v.result, ["metadata", "values"], "study result");
      if (v.status !== "COMPLETE" || !v.result.metadata || Array.isArray(v.result.metadata) || typeof v.result.metadata !== "object") throw Error("Only completed studies carry numerical results");
      if (!Array.isArray(v.result.values) || v.result.values.length !== 13) throw Error("Study time shape mismatch");
      v.result.values.forEach((row) => { if (!Array.isArray(row) || row.length !== 64) throw Error("Study spatial shape mismatch"); row.forEach(finite); });
    }
    return clone(v);
  }
  function createAdapter(fetcher = root.fetch.bind(root)) {
    async function call(name, value) {
      const abort = new AbortController(), timer = setTimeout(() => abort.abort(), 30000);
      try {
      const result = await fetcher("/api/scientific-studies/" + name, { method: value === undefined ? "GET" : "POST", credentials: "same-origin", redirect: "error", signal: abort.signal, headers: value === undefined ? {} : { "Content-Type": "application/json" }, ...(value === undefined ? {} : { body: JSON.stringify(value) }) });
      if (!result.ok) throw Error("Private scientific service unavailable or request denied (" + result.status + ").");
      const raw = await result.text();
      if (new TextEncoder().encode(raw).length > 131072) throw Error("Study response byte limit");
      const parser = root.CarbonFit || (typeof require !== "undefined" ? require("./engine.js") : null);
      return parser.strictJsonParse(raw, { maxBytes: 131072, maxDepth: 12 });
      } finally { clearTimeout(timer); }
    }
    return Object.freeze({ capabilities: () => call("capabilities"), start: (r) => call("start", r), status: (r) => call("status", r), cancel: (r) => call("cancel", r), result: (r) => call("result", r) });
  }
  function createController(adapter, currentDesign) {
    let cap = null, adopted = null, run = null, busy = false;
    const snapshot = () => clone({ capabilities: cap, physical: adopted, run, busy });
    async function current(r) {
      const d = currentDesign();
      if (!d || !adopted) return false;
      try { return same((await prepare(d, adopted)).binding, r.binding); } catch { return false; }
    }
    async function accept(value, sent) {
      const received = response(value, sent);
      if (!run || !same(run.request, sent)) throw Error("Study selection changed while request was in flight");
      if (!cap || received.method !== cap.method || received.environment !== cap.environment) throw Error("Study method or environment changed");
      if (run.response && run.response.task_id !== received.task_id) throw Error("Study task identity changed");
      run.response = received;
      run.origin = "PRIVATE_SERVICE_RESPONSE";
      run.association = await current(sent) ? "CURRENT" : "STALE";
      if (run.association === "STALE") throw Error("Late result retained for its original draft; current physical definition changed");
      return snapshot();
    }
    async function execute(action) {
      if (busy) throw Error("Study request already in flight");
      if (!adapter || !cap?.available || !run) throw Error("Connect and adopt the public source before execution");
      if (!same(adopted, cap.physical)) throw Error("Saved inputs differ from the admitted public source definition");
      busy = true;
      const sent = clone(run.request);
      try {
        if (!(await current(sent)) && action !== "cancel") { run.association = "STALE"; throw Error("Study is stale for this draft"); }
        return await accept(await adapter[action](sent), sent);
      }
      finally { busy = false; }
    }
    return Object.freeze({
      snapshot,
      async connect() { if (busy) throw Error("Study request already in flight"); if (!adapter) throw Error("Offline Workbench: private scientific service unavailable"); busy = true; try { cap = capabilities(await adapter.capabilities()); return snapshot(); } finally { busy = false; } },
      async adopt() { if (busy) throw Error("Study request already in flight"); if (!cap?.available) throw Error("No available public source definition"); busy = true; try { const prepared = await prepare(currentDesign(), cap.physical); if (run && !same(run.request, prepared)) throw Error("Preserve the existing study and create a new design revision before adopting changed inputs"); adopted = clone(cap.physical); if (!run) run = { request: prepared, response: null, association: "CURRENT", origin: "NOT_EXECUTED" }; run.association = await current(prepared) ? "CURRENT" : "STALE"; return snapshot(); } finally { busy = false; } },
      async refresh() { if (run) run.association = await current(run.request) ? "CURRENT" : "STALE"; return snapshot(); },
      start: () => execute("start"), status: () => execute("status"), cancel: () => execute("cancel"), result: () => execute("result"),
      save() { if (!run) throw Error("No study to save"); return clone({ schema: BUNDLE, request: run.request, response: run.response }); },
      async reopen(value) {
        if (busy) throw Error("Study request already in flight"); bounded(value); exact(value, ["schema", "request", "response"], "study bundle"); if (value.schema !== BUNDLE) throw Error("Unsupported study bundle");
        const r = request(value.request), received = value.response === null ? null : response(value.response, r);
        const expected = await prepare(currentDesign(), r.physical);
        if (!same(expected, r)) throw Error("Saved study belongs to a different draft or physical definition");
        if (run && (!same(run.request, r) || (run.response !== null && !same(run.response, received)))) throw Error("Saved study conflicts with retained operation or response bytes");
        adopted = clone(r.physical); run = { request: r, response: received, association: "CURRENT", origin: "SAVED_UNVERIFIED" }; run.association = await current(r) ? "CURRENT" : "STALE"; return snapshot();
      },
    });
  }
  const api = Object.freeze({ TEMPLATE, REQUEST, RESPONSE, CAPABILITIES, BUNDLE, check, physical, scope, prepare, response, capabilities, digest, createAdapter, createController });
  root.CarbonScientificStudies = api;
  if (typeof module !== "undefined") module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
