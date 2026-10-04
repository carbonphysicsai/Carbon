"use strict";
// Carbon research surface: the working toolbox (OWNER-MINER-RESEARCH-SURFACE-03).
//
// The Tools tab uses the research tools, not only lists them. The page is one
// more client of the tools an MCP agent gets (RSURF-D15): a session attaches
// to the campaign as carbon_attach_campaign does, under its ownership lock, and
// every panel calls those tools through /api/v1/tools/<campaign>. Each tool's
// generic form is built from that tool's own input schema. Results are shown as
// text, and run images as images: nothing is ever parsed as HTML.
(() => {
  const CC = window.CarbonControlCenter;
  if (!CC) return;
  const {el} = CC;
  const READ_CHUNK = 4096;
  // A workspace action's arguments are bounded at 16 KiB, and base64 makes a
  // file 4/3 its size: write_file takes about 11 KiB of file at a time.
  const EDIT_MAX = 11 * 1024;
  const SHOW_MAX = 200000;
  const POLL_MS = 2000;
  const IMAGE_TYPES = ["image/png", "image/jpeg", "image/gif", "image/webp"];
  const MATERIAL = ["objective", "capabilities", "training_data", "practice_data", "reference_method"];
  const REASONS = ["missing_adapter", "missing_data_support", "resource_ceiling", "host_limitation", "contract_incompatibility", "prohibited_authority_or_data"];
  const REQUEST_FIELDS = ["purpose", "operation", "hypothesis", "public_evidence", "expected_benefit", "estimated_cost", "minimal_safe_design", "verification"];
  const BUSY = {
    carbon_agent_or_operation: "Carbon's agent is researching in this campaign, or an operation (practice, freeze, submit, resume) is running. Pause Carbon's agent from Controls, or wait for the operation to finish, then open the tools again.",
    another_session: "Another session holds this campaign: most likely your own agent attached it with carbon_attach_campaign. Ask it to call carbon_detach_campaign, or let it run the tools for you; then open the tools here.",
  };
  const PYTHON = [
    "# Runs isolated, on the workspace files you pick: in the CPU analysis",
    "# image, or on your GPU if you choose it. Files you write to ../output",
    "# come back to your workspace, and images among them show below. The",
    "# last 64 KiB of stdout and of stderr are kept, even when it fails.",
    "from pathlib import Path",
    "",
    "out = Path(\"../output\")",
    "print(\"hello from the code cell\")",
    "",
  ].join("\n");
  const JULIA = "# Runs in the pinned Julia environment, research only.\nprintln(\"hello from Julia\")\n";
  const benches = new Map();

  // ---- Small helpers, all text. ----
  function words(value) { return String(value ?? "").replaceAll("_", " "); }
  function para(parent, text, className) { const p = el("p", text, className); parent.append(p); return p; }
  function button(label, className, onClick) {
    const b = el("button", label, className); b.type = "button";
    if (onClick) b.addEventListener("click", onClick);
    return b;
  }
  function input(type, value, label) {
    const node = el(type === "textarea" ? "textarea" : "input");
    if (type !== "textarea") node.type = type;
    if (value !== undefined && value !== null) node.value = String(value);
    if (label) node.setAttribute("aria-label", label);
    return node;
  }
  function select(options, value, label) {
    const node = el("select");
    for (const [optionValue, text] of options) { const o = el("option", text); o.value = optionValue; node.append(o); }
    if (value !== undefined) node.value = value;
    if (label) node.setAttribute("aria-label", label);
    return node;
  }
  function field(parent, label, control, hint) {
    const box = el("label", undefined, "rs-field");
    box.append(el("span", label, "rs-field-label"), control);
    if (hint) box.append(el("span", hint, "hint"));
    parent.append(box);
    return control;
  }
  function out(parent) { const node = el("pre", "", "rs-out"); node.hidden = true; parent.append(node); return node; }
  function show(node, value) {
    node.hidden = false;
    let text = typeof value === "string" ? value : readable(value);
    if (text.length > SHOW_MAX) text = text.slice(0, SHOW_MAX) + "\n… shortened here; the full result is the tool's.";
    node.textContent = text;
  }
  // A tool's answer as a person reads it (LP-PROD-F): one "name: value" line
  // per field, nested fields indented, lists as "- " items, text unquoted.
  // Still text: nothing in it is parsed or run.
  function readable(value, depth = 0) {
    const pad = "  ".repeat(depth);
    const scalar = item => item === null ? "none" : typeof item === "string" ? item : typeof item === "boolean" ? (item ? "yes" : "no") : String(item);
    const flat = item => item === null || typeof item !== "object" || (Array.isArray(item) ? !item.length : !Object.keys(item).length);
    if (flat(value)) return pad + (Array.isArray(value) ? "(none)" : value && typeof value === "object" ? "(empty)" : scalar(value));
    const lines = [];
    if (Array.isArray(value)) {
      for (const item of value) {
        if (flat(item)) lines.push(pad + "- " + (Array.isArray(item) ? "(none)" : item && typeof item === "object" ? "(empty)" : scalar(item)));
        else lines.push(pad + "-", readable(item, depth + 1));
      }
    } else {
      for (const [key, item] of Object.entries(value)) {
        const label = key.replaceAll("_", " ");
        if (flat(item)) lines.push(pad + label + ": " + (Array.isArray(item) ? "(none)" : item && typeof item === "object" ? "(empty)" : scalar(item)));
        else lines.push(pad + label + ":", readable(item, depth + 1));
      }
    }
    return lines.join("\n");
  }
  function opId() {
    const bytes = new Uint8Array(12); crypto.getRandomValues(bytes);
    return "page-" + [...bytes].map(b => b.toString(16).padStart(2, "0")).join("");
  }
  function decode(base64) {
    const binary = atob(base64); const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    return bytes;
  }
  function encode(bytes) {
    let binary = "";
    for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return btoa(binary);
  }
  // A read_file result's bytes. A campaign that froze the v2 research tools
  // rule (LP-PROD-D) returns them once: as content_utf8 when they are UTF-8
  // text, otherwise as content_base64, the other null. The historical rule
  // returns content_base64 alone. Either way, the same bytes.
  function readBytes(value) {
    if (typeof value?.content_utf8 === "string") return new TextEncoder().encode(value.content_utf8);
    if (typeof value?.content_base64 === "string") return decode(value.content_base64);
    throw new Error("read_file_result_unreadable");
  }
  function asText(bytes) { try { return new TextDecoder("utf-8", {fatal: true}).decode(bytes); } catch (_) { return null; } }
  function parseJSON(text) { try { return {value: JSON.parse(text)}; } catch (error) { return {error: "Not valid JSON: " + error.message}; } }
  function errorText(error) {
    const code = String(error?.message || error);
    for (const [hint, text] of Object.entries(BUSY)) if (code.includes("campaign_busy_" + hint)) return text;
    if (code.includes("tools_session_not_open")) return "The tools session is closed (it closes after idle minutes). Open it again.";
    if (code.includes("registration")) return "Your registration could not be confirmed (" + words(code) + "). Tools need the same registration practice does.";
    if (code.includes("tools_unavailable_for_campaign")) return "This campaign cannot open its tools now: it must be yours, unfinished, running (not paused or stopped) and have no unresolved work to reconcile.";
    return words(code);
  }

  // ---- Calls: every one goes through the page's tools route. ----
  function path(w, action) { return "/api/v1/tools/" + encodeURIComponent(w.id) + (action ? "/" + action : ""); }
  async function post(w, action, body) { return CC.api(path(w, action), body, undefined, 130000); }
  function toolName(w, operation) { return (w.state?.tools || []).find(t => t.operation === operation)?.name; }
  function unwrap(reply) {
    if (!reply.ok) return {error: reply.error};
    const payload = reply.result?.payload || {};
    if (payload.status === "REJECTED_BEFORE_DISPATCH" || payload.status === "UNAVAILABLE") return {error: words(payload.reason) + ": " + payload.detail, payload};
    return {payload, value: payload.public_result ? payload.public_result.result : payload.reply};
  }
  async function callTool(w, operation, args) {
    const name = toolName(w, operation);
    if (!name) return {error: "This session has no " + operation + " tool."};
    return unwrap(await post(w, "call", {tool: name, arguments: {operation_id: opId(), ...args}}));
  }
  async function workspace(w, action, args, why) {
    return callTool(w, "start_research_task", {kind: "workspace", strategy: null, action, arguments: args, hypothesis: why[0], expected_effect: why[1]});
  }
  async function guarded(node, work) {
    show(node, "Working…");
    try { const result = await work(); if (result !== undefined) show(node, result.error ? "Refused: " + result.error : result.value ?? result.payload ?? result); }
    catch (error) { show(node, "Failed: " + errorText(error)); }
  }

  // ---- The session: open, close, and who holds the campaign. ----
  function merge(w) {
    // The session lists its tasks newest first.
    for (const taskId of w.state?.tasks || []) if (!w.tasks.includes(taskId)) w.tasks.push(taskId);
  }
  async function refresh(w) {
    try { w.state = await CC.api(path(w)); w.error = null; merge(w); }
    catch (error) { w.error = errorText(error); }
    draw(w);
  }
  async function open(w) {
    w.busy = true; draw(w);
    try { w.state = await post(w, "open", {}); w.error = null; merge(w); }
    catch (error) { w.error = errorText(error); }
    w.busy = false; draw(w);
  }
  async function close(w) {
    w.busy = true; draw(w);
    try { await post(w, "close", {}); } catch (_) { /* a closed session stays closed */ }
    w.state = {open: false}; w.busy = false; draw(w);
  }

  // ---- Panels. ----
  function sessionBar(w, parent) {
    const bar = el("div", undefined, "rs-tools-bar");
    const s = w.state || {};
    if (s.open) {
      bar.append(el("strong", "Tools open"), el("span", "Closes after " + Math.round((s.idle_close_seconds || 600) / 60) + " idle minutes.", "hint"), button("Close the tools", "", () => close(w)));
      parent.append(bar);
      para(parent, s.holds || "", "hint");
    } else {
      const go = button(w.busy ? "Opening…" : "Open the tools", "primary", () => open(w)); go.disabled = Boolean(w.busy);
      bar.append(go, el("span", "Opening attaches this page to the campaign, as your agent's carbon_attach_campaign does. One holder at a time: while it is open, your agent's attach, practice, freeze and submit wait.", "hint"));
      parent.append(bar);
    }
    if (w.error) para(parent, w.error, "reason");
    if (w.doc.fixture) para(parent, "Synthetic fixture: the tools are the real ones, answering from made-up data. Nothing runs, and nothing reaches a campaign.", "hint");
  }

  function costLine(w, action, device) {
    const trials = w.doc.tiles?.trials;
    const used = trials ? trials.used + (trials.ceiling == null ? " (no ceiling set)" : " of your " + trials.ceiling) : "unknown";
    const limit = (w.doc.toolbox?.workspace || []).find(a => a.id === action)?.limits;
    const lane = w.state?.gpu_lane;
    const wall = device === "gpu" && lane?.kind === "remote_gpu" ? "required, " + lane.seconds[0] + " to " + lane.seconds[1] + " s on your remote GPU" : typeof limit === "number" ? "up to " + limit + " s" : limit ? String(limit) : "your allowance, or none";
    const image = action === "run_julia" ? "the campaign's Julia image (CUDA.jl on CUDA 13.0)" : "the campaign's pinned GPU worker image (its packages differ from the CPU sandbox)";
    const where = device === "gpu" && lane ? " Runs on " + lane.label + ", in " + image + ", on your machine and your bill. Isolation: " + (lane.isolation || "not stated, so assume none") + ". The validator stays on CPU." : " Runs on CPU, in the isolated analysis sandbox.";
    return "Costs 1 research trial of your own budget: used " + used + ". Wall time: " + wall + "." + where + " Research only, never part of a submission.";
  }

  function workspacePanel(w, body) {
    const box = el("details", undefined, "rs-tool"); box.open = true;
    box.append(el("summary", "Workspace: your files"));
    const actions = el("div", undefined, "rs-actions");
    const list = el("div", undefined, "table-wrap");
    const viewer = el("div", undefined, "rs-viewer");
    const result = out(box);
    actions.append(button("Refresh files", "", () => inventory(w, list, viewer, result)));
    const newName = input("text", "", "New file name"); newName.placeholder = "new-file.py";
    actions.append(newName, button("New file", "", () => { if (newName.value) editor(w, viewer, newName.value, new Uint8Array(), null); }));
    const material = select(MATERIAL.map(m => [m, words(m)]), MATERIAL[0], "Public material");
    actions.append(material, button("Fetch public material", "", () => guarded(result, () => workspace(w, "public_material", {name: material.value}, ["Read public material", "See the public " + material.value]))));
    box.append(actions, list, viewer);
    body.append(box);
    inventory(w, list, viewer, result);
  }
  async function inventory(w, list, viewer, result) {
    const answer = await workspace(w, "inventory", {}, ["List my workspace", "See the files and their digests"]).catch(error => ({error: errorText(error)}));
    if (answer.error) { show(result, "Refused: " + answer.error); return; }
    w.files = answer.value?.files || [];
    const table = el("table", undefined, "metrics-table rs-files");
    const head = el("tr"); for (const h of ["File", "Bytes", "Digest", ""]) head.append(el("th", h)); table.append(head);
    for (const file of w.files) {
      const row = el("tr");
      const act = el("td");
      act.append(button("View", "", () => view(w, viewer, file, 0)), button("Edit", "", () => loadForEdit(w, viewer, file)));
      row.append(el("td", file.name), el("td", String(file.bytes)), el("td", String(file.digest).slice(0, 19) + "…"), act);
      table.append(row);
    }
    list.replaceChildren(w.files.length ? table : el("p", "No files yet.", "hint"));
    w.onFiles?.();
  }
  async function readChunk(w, file, offset) {
    const answer = await workspace(w, "read_file", {name: file.name, offset, count: READ_CHUNK}, ["View " + file.name, "Read its bytes"]);
    if (answer.error) throw new Error(answer.error);
    return readBytes(answer.value);
  }
  async function view(w, viewer, file, offset, shown = "") {
    viewer.replaceChildren(el("h4", file.name), el("p", "Reading…", "hint"));
    try {
      const bytes = await readChunk(w, file, offset);
      const text = asText(bytes);
      viewer.replaceChildren(el("h4", file.name + " · " + file.bytes + " bytes"));
      if (/\.(png|jpe?g|gif|webp)$/i.test(file.name)) para(viewer, "An image: a run's images show with its output under Results.", "hint");
      if (text === null) {
        para(viewer, "Binary, or not UTF-8 text. First bytes (hex):", "hint");
        viewer.append(el("pre", [...bytes.subarray(0, 64)].map(b => b.toString(16).padStart(2, "0")).join(" "), "rs-out"));
        return;
      }
      const pre = el("pre", shown + text, "rs-out"); viewer.append(pre);
      const next = offset + bytes.length;
      if (next < file.bytes) viewer.append(button("Read the next 4 KiB", "", () => view(w, viewer, file, next, shown + text)));
    } catch (error) { viewer.replaceChildren(el("h4", file.name), el("p", errorText(error), "reason")); }
  }
  async function loadForEdit(w, viewer, file) {
    if (file.bytes > EDIT_MAX) { viewer.replaceChildren(el("p", file.name + " is " + file.bytes + " bytes: write_file takes at most " + EDIT_MAX + " bytes at a time (a workspace action's arguments are bounded at 16 KiB). View it instead.", "reason")); return; }
    viewer.replaceChildren(el("p", "Reading " + file.name + " in 4 KiB pieces…", "hint"));
    try {
      const parts = []; let offset = 0;
      while (offset < file.bytes) { const chunk = await readChunk(w, file, offset); if (!chunk.length) break; parts.push(chunk); offset += chunk.length; }
      const bytes = new Uint8Array(offset); let at = 0; for (const part of parts) { bytes.set(part, at); at += part.length; }
      editor(w, viewer, file.name, bytes, file.digest);
    } catch (error) { viewer.replaceChildren(el("p", errorText(error), "reason")); }
  }
  function editor(w, viewer, name, bytes, digest) {
    const text = asText(bytes);
    if (text === null) { viewer.replaceChildren(el("p", name + " is not UTF-8 text; it can be viewed, not edited here.", "reason")); return; }
    const area = input("textarea", text, "Edit " + name); area.className = "rs-code"; area.rows = 16;
    const result = el("p", "", "hint");
    const save = button("Save with write_file", "primary", async () => {
      const body = new TextEncoder().encode(area.value);
      if (body.length > EDIT_MAX) { result.textContent = "Too large for write_file here (" + body.length + " > " + EDIT_MAX + " bytes)."; return; }
      result.textContent = "Saving…";
      try {
        const answer = await workspace(w, "write_file", {name, content_base64: encode(body), expected_digest: digest}, ["Edit " + name, "Save my change"]);
        if (answer.error) { result.textContent = "Refused: " + answer.error + (answer.error.includes("compare-and-swap") ? " (the file changed since you opened it; open it again)" : ""); return; }
        digest = answer.value.digest; result.textContent = "Saved: " + digest;
      } catch (error) { result.textContent = errorText(error); }
    });
    viewer.replaceChildren(el("h4", "Edit " + name), area, save, result, el("p", "write_file is guarded by the file's digest: a change made elsewhere since you opened it is refused, never overwritten.", "hint"));
  }

  function codePanel(w, body) {
    const julia = Boolean(w.state.run_julia_available);
    const box = el("details", undefined, "rs-tool"); box.open = true;
    box.append(el("summary", "Code cell: run_python" + (julia ? " and run_julia" : "")));
    const language = select([["run_python", "Python"], ...(julia ? [["run_julia", "Julia"]] : [])], "run_python", "Language");
    field(box, "Language", language, julia ? null : "run_julia is not available on this host: " + (w.doc.toolbox?.julia?.run_julia?.reason || "not configured") + ".");
    const environment = select([["current", "current: newest SciML core"], ["pde", "pde: NeuralPDE, MethodOfLines, DataDrivenDiffEq"]], "current", "Julia environment");
    const envField = field(box, "Julia environment", environment); envField.parentElement.hidden = true;
    // CPU or GPU, per run, only when this campaign has a GPU lane (RSURF-D20).
    const lane = w.state.gpu_lane;
    const device = select([["cpu", "CPU (isolated analysis sandbox)"], ...(lane ? [["gpu", lane.label]] : [])], "cpu", "Device");
    // run_julia on the GPU only where this campaign has Julia, the lane runs
    // it, and the environment has CUDA (JULIA-GPU-01): the lane says which.
    const juliaGpuEnvironments = julia && lane && (lane.actions || []).includes("run_julia") ? (lane.julia_environments || []) : [];
    const gpuNote = !lane ? "CPU only: this campaign was launched without a GPU. Set one up in Set up, Compute, for your next campaign."
      : !julia ? "Choose per run."
      : juliaGpuEnvironments.length ? "Choose per run. run_julia runs on this GPU in its " + juliaGpuEnvironments.join(", ") + " environment (CUDA.jl on CUDA 13.0); its other environments run on CPU."
      : "Choose per run. run_julia runs on CPU: this GPU lane runs run_python only.";
    field(box, "Runs on", device, gpuNote);
    device.disabled = !lane;
    const source = input("textarea", PYTHON, "Source"); source.className = "rs-code"; source.rows = 12;
    field(box, "Source", source);
    const syncDevice = () => {
      const juliaOnCpuOnly = language.value === "run_julia" && !juliaGpuEnvironments.includes(environment.value);
      if (juliaOnCpuOnly) device.value = "cpu";
      device.disabled = !lane || juliaOnCpuOnly;
      cost.textContent = costLine(w, language.value, device.value);
    };
    language.addEventListener("change", () => {
      const isJulia = language.value === "run_julia";
      envField.parentElement.hidden = !isJulia;
      if (source.value === PYTHON || source.value === JULIA) source.value = isJulia ? JULIA : PYTHON;
      syncDevice();
    });
    environment.addEventListener("change", syncDevice);
    device.addEventListener("change", () => { cost.textContent = costLine(w, language.value, device.value); });
    const files = el("div", undefined, "rs-checks");
    field(box, "Files to stage", files, "Only the files you tick are copied in; refresh the workspace to see new ones.");
    const drawFiles = () => {
      const chosen = new Set([...files.querySelectorAll("input:checked")].map(i => i.value));
      files.replaceChildren();
      for (const file of w.files || []) {
        const label = el("label", undefined, "rs-check"); const box2 = input("checkbox"); box2.value = file.name; box2.checked = chosen.has(file.name);
        label.append(box2, el("span", file.name)); files.append(label);
      }
      if (!(w.files || []).length) files.append(el("span", "No workspace files yet.", "hint"));
    };
    w.onFiles = drawFiles; drawFiles();
    const seconds = input("number", "", "Wall seconds"); seconds.min = "1"; seconds.placeholder = "omit for none";
    field(box, "Wall seconds (optional)", seconds);
    const hypothesis = input("text", "Check the data before the next trial", "Hypothesis");
    const effect = input("text", "Learn what the next practice trial should change", "Expected effect");
    field(box, "Hypothesis", hypothesis); field(box, "Expected effect", effect);
    const cost = el("p", costLine(w, "run_python"), "rs-cost");
    box.append(cost);
    const result = el("div", undefined, "rs-run");
    box.append(button("Run", "primary", async () => {
      const args = {source: source.value, files: [...files.querySelectorAll("input:checked")].map(i => i.value), hypothesis: hypothesis.value, expected_effect: effect.value};
      if (seconds.value) args.seconds = Number(seconds.value);
      if (language.value === "run_julia") args.environment = environment.value;
      // Absent, a request runs on CPU exactly as before; only a GPU run says so.
      if (device.value === "gpu") args.device = "gpu";
      await startTask(w, result, {kind: "workspace", strategy: null, action: language.value, arguments: args, hypothesis: hypothesis.value, expected_effect: effect.value});
    }), result);
    body.append(box);
  }

  // ---- Tasks: start, progress, cancel, output (MCP Tasks' own projection). ----
  async function startTask(w, area, args) {
    area.replaceChildren(el("p", "Starting…", "hint"));
    try {
      const reply = await post(w, "start", {arguments: {operation_id: opId(), ...args}});
      if (!reply.ok) { area.replaceChildren(el("p", "Refused: " + reply.error, "reason")); return; }
      if (!reply.task) {
        const text = reply.result?.content?.[0]?.text || "";
        const parsed = parseJSON(text).value?.payload;
        area.replaceChildren(el("p", parsed?.status === "REJECTED_BEFORE_DISPATCH" ? "Refused before it started: " + words(parsed.reason) + ". " + parsed.detail : "Not started.", "reason"));
        return;
      }
      track(w, reply.task.taskId, area);
    } catch (error) { area.replaceChildren(el("p", errorText(error), "reason")); }
  }
  function track(w, taskId, area) {
    if (!w.tasks.includes(taskId)) w.tasks.unshift(taskId);
    drawResults(w);
    if (area) poll(w, taskId, area);
  }
  async function poll(w, taskId, area) {
    let reply;
    try { reply = await post(w, "observe", {task_id: taskId}); }
    catch (error) { area.replaceChildren(el("p", errorText(error), "reason")); return; }
    if (!reply.ok) { area.replaceChildren(el("p", reply.error, "reason")); return; }
    const task = reply.task;
    const head = el("div", undefined, "rs-actions");
    head.append(el("strong", words(task.statusMessage)), el("span", taskId.slice(0, 18) + "…", "hint"));
    if (task.status === "working") head.append(button("Cancel", "", async () => {
      try { const c = await post(w, "cancel", {task_id: taskId}); if (!c.ok) para(area, c.error, "reason"); } catch (error) { para(area, errorText(error), "reason"); }
    }));
    area.replaceChildren(head);
    if (task.status === "working") { setTimeout(() => poll(w, taskId, area), POLL_MS); return; }
    output(w, taskId, area);
  }
  async function output(w, taskId, area) {
    try {
      const doc = await CC.api("/api/v1/operations/run_output", {campaign: w.id, task: taskId}, undefined, 30000);
      runOutput(area, doc);
    } catch (error) {
      if (/not_a_workspace_run/.test(error.message)) para(area, "A practice trial: its result is under Experiments.", "hint");
      else para(area, "Output: " + errorText(error), "reason");
    }
  }
  function runOutput(area, doc) {
    para(area, doc.outcome === "SUCCEEDED" ? "Your program finished. Its output is self-reported." : "Your program failed (" + words(doc.failure_code) + "). The last of its output and errors is below.", doc.outcome === "SUCCEEDED" ? "hint" : "reason");
    if (doc.ran_on) para(area, "Ran on: " + doc.ran_on.label + (doc.ran_on.device_kind ? " · " + doc.ran_on.device_kind : "") + (doc.ran_on.transport ? " · " + doc.ran_on.transport : ""), "rs-runs-on");
    area.append(el("h4", "stdout" + (doc.stdout_truncated_to_last_bytes ? " (the last " + doc.stdout_truncated_to_last_bytes + " bytes)" : "")));
    area.append(el("pre", doc.stdout ?? "(none kept)", "rs-out"));
    area.append(el("h4", "stderr" + (doc.stderr_truncated_to_last_bytes ? " (the last " + doc.stderr_truncated_to_last_bytes + " bytes)" : "")));
    area.append(el("pre", doc.stderr ?? "(none kept: a run recorded before error output was kept)", "rs-out"));
    para(area, "Kept: " + doc.carrier.kept + ". Outputs: " + doc.carrier.outputs + ".", "hint");
    if (!doc.files.length) { para(area, "It wrote no files.", "hint"); return; }
    area.append(el("h4", "Files it wrote to your workspace"));
    const list = el("ul", undefined, "rs-out-files");
    for (const file of doc.files) {
      const item = el("li");
      item.append(el("span", file.name + " · " + (file.bytes ?? "?") + " bytes" + (file.media_type ? " · " + file.media_type : "")));
      if (file.image_base64 && IMAGE_TYPES.includes(file.media_type) && /^[A-Za-z0-9+/]*={0,2}$/.test(file.image_base64)) {
        // A blob of the checked raster bytes: the page's CSP allows blob:
        // images and nothing else beyond its own origin.
        const image = el("img", undefined, "rs-img");
        image.alt = "Image written by your program: " + file.name;
        const url = URL.createObjectURL(new Blob([decode(file.image_base64)], {type: file.media_type}));
        image.addEventListener("load", () => URL.revokeObjectURL(url), {once: true});
        image.src = url;
        item.append(image);
      } else if (file.not_inlined) item.append(el("span", " (" + file.not_inlined + ")", "hint"));
      list.append(item);
    }
    area.append(list);
  }
  function resultsPanel(w, body) {
    const box = el("details", undefined, "rs-tool"); box.open = true;
    box.append(el("summary", "Results: tasks and their output"));
    const look = input("text", "", "Task id"); look.placeholder = "rtsk_…";
    const actions = el("div", undefined, "rs-actions");
    actions.append(look, button("Show", "", () => { if (/^rtsk_[0-9a-f]{64}$/.test(look.value.trim())) track(w, look.value.trim()); }));
    w.resultList = el("div", undefined, "rs-results");
    box.append(el("p", "Long tasks start with start_research_task and report through get_research_result, as your agent's do. Cancel asks the task to stop; only observed cleanup proves it did.", "hint"), actions, w.resultList);
    body.append(box);
    drawResults(w);
  }
  function drawResults(w) {
    if (!w.resultList) return;
    w.resultList.replaceChildren();
    if (!w.tasks.length) { w.resultList.append(el("p", "No tasks yet in this session.", "hint")); return; }
    for (const taskId of w.tasks.slice(0, 20)) {
      const row = el("div", undefined, "rs-result");
      const area = el("div");
      row.append(el("code", taskId), button("Progress and output", "", () => poll(w, taskId, area)), area);
      w.resultList.append(row);
    }
  }

  function recipePanel(w, body) {
    const box = el("details", undefined, "rs-tool");
    box.append(el("summary", "Recipe: validate, compile, estimate, practice, freeze, submit"));
    const example = (w.doc.toolbox?.examples || [])[0];
    const recipe = input("textarea", example ? JSON.stringify(example, null, 2) : "{}", "Recipe JSON"); recipe.className = "rs-code"; recipe.rows = 10;
    field(box, "Recipe (JSON)", recipe, example ? "Prefilled with the Challenge's registered example." : "This Challenge registers no example recipe.");
    const result = out(box);
    const strategy = () => { const parsed = parseJSON(recipe.value); if (parsed.error) { show(result, parsed.error); return null; } return parsed.value; };
    const seconds = input("number", "60", "Forecast seconds"); seconds.min = "1"; seconds.max = "600";
    const actions = el("div", undefined, "rs-actions");
    for (const [operation, label] of [["dry_validate", "Dry-validate"], ["compile_strategy", "Compile"], ["inspect_resources", "Inspect resources"]]) {
      actions.append(button(label, "", () => { const s = strategy(); if (s) guarded(result, () => callTool(w, operation, {strategy: s})); }));
    }
    actions.append(seconds, button("Forecast resources", "", () => { const s = strategy(); if (s) guarded(result, () => callTool(w, "forecast_resources", {strategy: s, seconds: Number(seconds.value)})); }));
    box.insertBefore(actions, result);
    // Practice: the research tool's own practice task, inside this session.
    const hypothesis = input("text", "This recipe trains well on TRAIN data", "Practice hypothesis");
    const effect = input("text", "A lower practice score than the last run", "Practice expected effect");
    field(box, "Practice hypothesis", hypothesis); field(box, "Expected effect", effect);
    box.append(el("p", "Practice costs 1 research trial of your own budget: used " + (w.doc.tiles?.trials ? w.doc.tiles.trials.used + (w.doc.tiles.trials.ceiling == null ? "" : " of " + w.doc.tiles.trials.ceiling) : "unknown") + ". Forecast first to see its compute.", "rs-cost"));
    const practiceArea = el("div", undefined, "rs-run");
    box.append(button("Practice this recipe", "primary", () => { const s = strategy(); if (s) startTask(w, practiceArea, {kind: "practice", strategy: s, action: null, arguments: null, hypothesis: hypothesis.value, expected_effect: effect.value}); }), practiceArea);
    // Freeze and submit are the operations, with their own gates; they need
    // the campaign's lock, so the session closes first (RSURF-D16). Each is
    // sent under one idempotency key kept until it is answered (LP-PROD-F):
    // a retry after a timeout replays the request, never meets its own first
    // attempt as campaign_busy. What it did is read from the campaign's
    // record, as text, and followed until it is done or refused.
    const reason = input("text", "", "Why this candidate"); reason.placeholder = "What your practice showed";
    field(box, "Freeze: why this candidate", reason);
    const freeze = button("Close the tools and freeze this recipe", "", async () => {
      const s = strategy(); if (!s) return;
      if (!reason.value.trim()) { say(w, "Say why this candidate first.", "reason"); return; }
      if (!window.confirm("Close the tools and freeze this recipe as this epoch's candidate?")) return;
      await operation(w, freeze, "freeze_candidate", {campaign: w.id, strategy: s, reason: reason.value.trim()}, "Freezing");
    });
    const submit = button("Close the tools and submit the candidate", "", async () => {
      if (!window.confirm("Close the tools and submit your frozen candidate (DEVELOPMENT)?")) return;
      await operation(w, submit, "submit", {campaign: w.id}, "Submitting");
    });
    box.append(el("div", undefined, "rs-actions"));
    box.lastChild.append(freeze, submit);
    para(box, "What freeze or submit did shows above the tools, which close first.", "hint");
    body.append(box);
  }
  // The bench's own status line: kept across the tools closing and opening,
  // because freeze and submit close them first.
  function say(w, text, className = "hint") {
    CC.setText(w.opLine, text);
    if (w.opLine.className !== className) w.opLine.className = className;
    w.opLine.hidden = !text;
  }
  const KEYED = ["freeze_candidate", "submit"];
  async function operation(w, control, name, body, doing) {
    control.disabled = true;
    try {
      say(w, "Closing the tools…");
      await close(w);
      say(w, doing + ": sending…");
      const outcome = await CC.keyedOperation(name, body, 60000);
      if (outcome.ok) { CC.watch(name, w.id, outcome.value, outcome); w.following = name; follow(w); }
      else { w.following = null; say(w, CC.notDone(outcome, errorText(outcome.error)), "reason"); }
    } finally { control.disabled = false; follow(w); }
  }
  // The operation's progress and ending, from the campaign's own record; and
  // Discard while a freeze or submit is held under its key, its answer lost.
  function follow(w) {
    const held = CC.heldOperation(w.id, KEYED);
    if (w.opDiscard.hidden !== !held) w.opDiscard.hidden = !held;
    if (held) CC.setText(w.opDiscard, "Discard the unconfirmed " + (held.name === "submit" ? "submit" : "freeze"));
    if (!w.following) return;
    const run = (CC.state().research?.runs || []).find(item => item.id === w.id);
    const status = run ? CC.watchStatus(run) : null;
    if (status) say(w, status.text, status.kind === "refused" ? "reason" : status.kind === "done" ? "status-line" : "hint");
  }

  function designPanel(w, body) {
    const box = el("details", undefined, "rs-tool");
    box.append(el("summary", "Design checks and the roadmap"));
    const example = (w.doc.toolbox?.examples || [])[0] || {};
    const design = input("textarea", JSON.stringify({strategy: example, capabilities: []}, null, 2), "Design JSON"); design.className = "rs-code"; design.rows = 8;
    field(box, "Design (JSON: strategy, capabilities)", design, "A verdict per choice; charges nothing.");
    const result = out(box);
    const actions = el("div", undefined, "rs-actions");
    actions.append(
      button("Check design", "", () => { const parsed = parseJSON(design.value); if (parsed.error) { show(result, parsed.error); return; } guarded(result, () => workspace(w, "check_design", {design: parsed.value}, ["Check a design", "Know whether it can be submitted"])); }),
      button("Roadmap", "", () => guarded(result, () => workspace(w, "roadmap", {}, ["Read the roadmap", "See what blocks each capability"]))),
    );
    box.insertBefore(actions, result);
    body.append(box);
  }

  function capabilityPanel(w, body) {
    const box = el("details", undefined, "rs-tool");
    box.append(el("summary", "Ask for a capability (grants nothing)"));
    para(box, "A capability request grants nothing. It counts as demand on the roadmap.", "hint");
    const values = {};
    for (const name of REQUEST_FIELDS) values[name] = field(box, words(name), input("text", "", words(name)));
    const reason = field(box, "reason", select(REASONS.map(r => [r, words(r)]), REASONS[0], "reason"));
    const capability = field(box, "capability (optional registry id)", input("text", "", "capability"));
    const result = out(box);
    box.insertBefore(button("Send the request (grants nothing)", "", () => {
      const request = {reason: reason.value};
      for (const name of REQUEST_FIELDS) request[name] = values[name].value;
      if (capability.value.trim()) request.capability = capability.value.trim();
      guarded(result, () => workspace(w, "capability_request", {request}, ["Ask for a capability", "Record demand; it grants nothing"]));
    }), result);
    body.append(box);
  }

  function notebookPanel(w, body) {
    const box = el("details", undefined, "rs-tool");
    box.append(el("summary", "Notebook"));
    const kind = field(box, "Kind", select([["hypothesis", "hypothesis"], ["decision", "decision"], ["notebook", "note"]], "notebook", "Kind"));
    const text = field(box, "Entry", input("textarea", "", "Notebook entry"));
    const result = out(box);
    box.insertBefore(button("Save to the journal", "", () => guarded(result, () => workspace(w, "notebook", {kind: kind.value, body: {text: text.value}}, ["Keep a note", "Record it in the campaign journal"]))), result);
    body.append(box);
  }

  // Every tool, from its own input schema: the generic Use panel.
  function control(name, schema, required) {
    const options = schema.anyOf || [schema];
    const nullable = options.some(o => o.type === "null") || !required;
    const kinds = options.map(o => o.type).filter(t => t && t !== "null");
    const values = options.flatMap(o => o.enum || (o.const !== undefined ? [o.const] : []));
    if (values.length) return {node: select([...(nullable ? [["__null__", "null"]] : []), ...values.map(v => [String(v), String(v)])], String(values[0]), name), read: n => n.value === "__null__" ? null : n.value};
    if (kinds.length === 1 && kinds[0] === "integer") { const n = input("number", "", name); return {node: n, read: x => x.value === "" ? (nullable ? null : NaN) : Number(x.value)}; }
    if (kinds.length === 1 && kinds[0] === "string") {
      const n = input(["hypothesis", "expected_effect"].includes(name) ? "text" : "text", name === "operation_id" ? opId() : "", name);
      return {node: n, read: x => x.value};
    }
    const n = input("textarea", nullable ? "null" : "{}", name); n.className = "rs-code"; n.rows = 4;
    return {node: n, read: x => { const parsed = parseJSON(x.value); if (parsed.error) throw new Error(name + ": " + parsed.error); return parsed.value; }};
  }
  function allToolsPanel(w, body) {
    const box = el("details", undefined, "rs-tool");
    box.append(el("summary", "Every research tool (built from its own input schema)"));
    para(box, "These are the tools your agent gets after carbon_attach_campaign, with the same arguments and refusals.", "hint");
    for (const tool of w.state.tools || []) {
      const item = el("details", undefined, "rs-tool-generic");
      item.append(el("summary", tool.operation));
      para(item, tool.description, "hint");
      const props = tool.input_schema?.properties || {};
      const required = new Set(tool.input_schema?.required || []);
      const controls = {};
      for (const [name, schema] of Object.entries(props)) controls[name] = field(item, name + (required.has(name) ? "" : " (optional)"), (controls[name + "__c"] = control(name, schema, required.has(name))).node);
      const result = out(item);
      item.insertBefore(button("Use " + tool.operation, "", () => guarded(result, async () => {
        const args = {};
        for (const name of Object.keys(props)) args[name] = controls[name + "__c"].read(controls[name]);
        const reply = await post(w, "call", {tool: tool.name, arguments: args});
        // A new business id for the next use; reusing one replays it.
        if (controls.operation_id) controls.operation_id.value = opId();
        return reply.ok ? {value: reply.result} : {error: reply.error};
      })), result);
      box.append(item);
    }
    body.append(box);
  }

  // ---- The bench for one campaign, kept across re-renders. ----
  function draw(w) {
    w.node.replaceChildren(el("h3", "Use the tools"));
    sessionBar(w, w.node);
    w.node.append(w.opLine, w.opDiscard);
    if (!w.state?.open) return;
    w.resultList = null;
    const body = el("div", undefined, "rs-bench");
    workspacePanel(w, body);
    codePanel(w, body);
    resultsPanel(w, body);
    recipePanel(w, body);
    notebookPanel(w, body);
    designPanel(w, body);
    capabilityPanel(w, body);
    allToolsPanel(w, body);
    w.node.append(body);
  }
  function mount(panel, doc) {
    const id = doc.campaign?.id;
    if (!id) return;
    let w = benches.get(id);
    if (!w) {
      w = {id, doc, node: el("section", undefined, "rs-panel rs-workbench"), state: null, tasks: [], files: [], opLine: el("p", "", "hint")};
      w.opLine.setAttribute("role", "status"); w.opLine.hidden = true;
      // Lets go of a freeze or submit held under its key (LP-PROD-F).
      w.opDiscard = button("Discard the unconfirmed request", "", () => {
        CC.discardOperation(w.id, KEYED);
        w.following = null;
        say(w, "Discarded. The next freeze or submit is a new request, under a new key.");
        follow(w);
      });
      w.opDiscard.dataset.discard = "operation"; w.opDiscard.hidden = true;
      benches.set(id, w);
      w.doc = doc;
      draw(w);
      refresh(w);
    }
    w.doc = doc;
    // Moved in only when it is not already there: moving a node blurs what
    // is focused in it, and a refresh must never take focus from an editor.
    if (w.node.parentNode !== panel) panel.append(w.node);
  }
  window.CarbonTools = {mount, readable, readBytes};
  // Each page refresh moves a freeze or submit's line on, from the record.
  CC.onRender(() => { for (const w of benches.values()) follow(w); });
})();
