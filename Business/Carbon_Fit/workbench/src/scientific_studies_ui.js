(function (root) {
  "use strict";
  const S = root.CarbonScientificStudies;
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  function plot(values, times) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 640 220"); svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "Public source field at requested times " + times[0] + " and " + times[12]);
    const rows = [values[0], values[12]], points = rows.flat(), low = Math.min(...points), high = Math.max(...points), scale = Math.max(Math.abs(low), Math.abs(high), 1), lower = low / scale, span = high / scale - lower || 1;
    rows.forEach((row, index) => {
      const line = document.createElementNS(svg.namespaceURI, "polyline");
      line.setAttribute("points", row.map((value, x) => `${20 + x * 600 / 63},${190 - (value / scale - lower) * 160 / span}`).join(" "));
      line.setAttribute("fill", "none"); line.setAttribute("stroke", index ? "#136f63" : "#a34413"); line.setAttribute("stroke-width", "2"); svg.append(line);
    });
    return svg;
  }
  function create({ getDesign, notify, download }) {
    const controllers = new Map();
    const enabled = document.documentElement.dataset.scientificService === "private" && ["http:", "https:"].includes(location.protocol);
    let panel = null, checked = null;
    // Held for this browser session only. Never stored, never rendered back
    // into the document, never written to a URL, export or saved study.
    let credential = null;
    function controller() {
      const d = getDesign();
      if (!d) return null;
      const key = d.job_id + ":" + d.design_id;
      if (!controllers.has(key)) controllers.set(key, S.createController(enabled ? S.createAdapter(undefined, () => credential) : null, getDesign));
      return controllers.get(key);
    }
    function draw() {
      if (!panel?.isConnected || !getDesign()) return;
      const c = controller(), state = c.snapshot(), r = state.run, response = r?.response, locked = state.busy ? "disabled" : "";
      panel.innerHTML = `<div class="eyebrow">Public source study · DEVELOPMENT</div><h3>Executable physical study</h3><p>Check the draft, then study the exact public Burgers source case through the private scientific service. This is not numerical validation of customer design text. Private customer inputs are unavailable. An explicitly granted envelope compares exactly two frozen public TRAIN cases; it does not establish population coverage.</p><p><strong>Scientific qualification: NOT_QUALIFIED.</strong> Draft assessment and rights remain unchanged. Source-owner registration and an existing service grant are required.</p><div class="actions"><button id="science-check" ${locked}>Check physical definitions</button>${enabled ? (credential ? `<span id="science-credential-state">Staff credential held for this browser session.</span><button id="science-credential-clear" ${locked}>Clear credential</button>` : `<label for="science-token">Staff access token</label><input id="science-token" type="password" autocomplete="off" spellcheck="false" placeholder="Issued to you by the operator">`) : ""}<button id="science-connect" ${!enabled ? "disabled" : locked}>Connect private service</button><button id="science-adopt" ${!state.capabilities?.available ? "disabled" : locked}>Adopt public source inputs</button><button id="science-envelope" ${!state.capabilities?.envelope || !enabled ? "disabled" : locked}>Explore operating envelope${state.capabilities?.envelope ? "" : " unavailable"}</button></div><p id="science-connection">${enabled ? state.capabilities ? "Source profile received; no study runs until requested." : credential ? "Private service build; connection requires your explicit action." : "Private service build. Enter your own staff access token, then connect. The token stays in this browser tab: it is not saved, exported or written into a study file." : "Offline build: numerical execution unavailable. Open this Workbench on its operator-configured private service to run a study."}</p><div id="science-check-result" role="status"></div><details><summary>Exact physical inputs and array layout</summary><pre id="science-inputs"></pre><p>Periodic unforced Burgers; Fourier coefficients use modes 1–12. Output rows follow the 13 requested times; columns are 64 periodic points from x=0, endpoint excluded, C order, zero-based indexing. Dimensionless variables; no implicit unit conversion.</p></details><div class="actions"><button id="science-run" ${!r || !enabled || r.association === "STALE" ? "disabled" : locked}>Assess reference feasibility</button><button id="science-status" ${!r || !enabled ? "disabled" : locked}>Status</button><button id="science-result" ${!r || !enabled ? "disabled" : locked}>Load results</button><button id="science-cancel" ${!r || !enabled ? "disabled" : locked}>Cancel study</button><button id="science-save" ${!r ? "disabled" : locked}>Save study</button><button id="science-reopen" ${locked}>Reopen saved study</button><input id="science-file" type="file" accept=".json,application/json" hidden></div><p id="science-state" role="status">${state.busy ? "Request in flight; execution state may require reconciliation." : r ? esc(r.request.action + " / " + r.association + " / " + r.origin + " / " + (response?.status || "NOT_EXECUTED")) : "No study adopted."}</p><p>Saved studies are separate versioned files bound to this job and exact draft revision. Reopened data is unverified until reread through the private service. Cancellation is a request; resource release must be observed by the controller.</p><div id="science-budget"></div><div id="science-plot"></div><details><summary>Resource observations, refinement evidence and method limitations</summary><pre id="science-metadata"></pre></details>`;
      const find = (id) => panel.querySelector("#" + id);
      find("science-inputs").textContent = state.physical ? JSON.stringify(r?.request.action === "OPERATING_ENVELOPE" ? state.capabilities?.envelope || state.physical : state.physical, null, 2) : "No source definition adopted.";
      if (checked) find("science-check-result").textContent = checked.status + ": " + checked.issues.join(" ") + " " + checked.limitations;
      if (response) {
        if (response.result?.children && r.association === "CURRENT") {
          for (const [index, child] of response.result.children.entries()) {
            const caption = document.createElement("p");
            caption.textContent = (index ? "Comparison public TRAIN case" : "Baseline public TRAIN case") + " · " + child.case_digest + " · " + child.state + (child.state === "HELD" ? " (capacity reserved; never dispatched)" : "") + ".";
            find("science-plot").append(caption);
            if (child.result) find("science-plot").append(plot(child.result.values, child.result.metadata.times));
          }
          const limit = document.createElement("p"); limit.textContent = "Each plot uses that case's requested time coordinates. Orange: first requested time; green: last. Two public DEVELOPMENT cases do not establish an operating population, qualification or customer-design validity."; find("science-plot").append(limit);
        }
        find("science-budget").textContent = "Remaining grant observations: " + Object.entries(response.remaining_budget).map(([key, value]) => key.replaceAll("_", " ") + ": " + (value ?? "unknown")).join("; ") + ". Method " + response.method + "; environment " + response.environment + ".";
        find("science-metadata").textContent = JSON.stringify(response.result?.metadata || { status: response.status, result: "No numerical result received" }, null, 2);
        if (response.result && !response.result.children && r.association === "CURRENT") {
          find("science-plot").append(plot(response.result.values, state.physical.requested_times));
          const caption = document.createElement("p"); caption.textContent = "Orange: first requested time " + state.physical.requested_times[0] + "; green: last requested time " + state.physical.requested_times[12] + ". Field values " + (r.origin === "SAVED_UNVERIFIED" ? "from an unverified saved file" : "returned by the private DEVELOPMENT service") + ". No reference qualification follows from agreement or solver success."; find("science-plot").append(caption);
        }
      }
      async function act(fn) { try { const pending = fn(); draw(); await pending; } catch (error) { notify(error.message); } finally { draw(); } }
      find("science-check").onclick = () => { checked = S.check(getDesign(), c.snapshot().physical); draw(); };
      find("science-connect").onclick = () => {
        const field = find("science-token");
        if (field) { credential = field.value.trim() || null; field.value = ""; }
        act(() => c.connect());
      };
      if (find("science-credential-clear")) find("science-credential-clear").onclick = () => { credential = null; draw(); };
      find("science-adopt").onclick = () => act(() => c.adopt());
      find("science-run").onclick = () => act(async () => { await c.adopt(); return c.start(); });
      find("science-envelope").onclick = () => act(async () => { await c.adopt("OPERATING_ENVELOPE"); return c.start(); });
      for (const [id, method] of [["science-status", "status"], ["science-result", "result"], ["science-cancel", "cancel"]]) find(id).onclick = () => act(() => c[method]());
      find("science-save").onclick = () => { try { download("public-scientific-study-" + getDesign().design_id + ".json", c.save()); } catch (error) { notify(error.message); } };
      find("science-reopen").onclick = () => find("science-file").click();
      find("science-file").onchange = async (event) => {
        const file = event.target.files[0]; if (!file) return;
        await act(async () => { if (file.size > 131072) throw Error("Study file exceeds byte limit"); const value = root.CarbonFit.strictJsonParse(await file.text(), { maxBytes: 131072, maxDepth: 12 }); await c.reopen(value); });
      };
    }
    function mount(container) {
      if (!getDesign() || !container) return;
      panel?.remove(); panel = document.createElement("section"); panel.className = "panel scientific-study-panel"; panel.id = "scientific-study-panel"; container.append(panel);
      checked = null;
      draw(); controller().refresh().then(draw).catch((error) => notify(error.message));
    }
    return Object.freeze({ mount });
  }
  root.CarbonScientificStudyUI = Object.freeze({ create, plot });
})(globalThis);
