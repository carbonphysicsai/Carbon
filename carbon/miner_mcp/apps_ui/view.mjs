import { App } from "@modelcontextprotocol/ext-apps";
import "../../../Business/Carbon_Fit/workbench/src/scientific_studies.js";
import "../../../Business/Carbon_Fit/workbench/src/scientific_studies_ui.js";

const S = globalThis.CarbonScientificStudies;
const app = new App({ name: "Carbon Workbench public study", version: "1.0.0" });
const find = (id) => document.getElementById(id);
const actions = ["start", "status", "result", "cancel"];
let request = null, response = null, busy = false, cancelBusy = false, connected = false;
const ordered = (value) => Array.isArray(value) ? value.map(ordered) : value && typeof value === "object" ? Object.fromEntries(Object.keys(value).sort().map((key) => [key, ordered(value[key])])) : value;
const same = (a, b) => JSON.stringify(ordered(a)) === JSON.stringify(ordered(b));
const copy = (value) => JSON.parse(JSON.stringify(value));

function message(text) { find("message").textContent = text; }
function draw() {
  for (const action of actions) find(action).disabled = !connected || !request || (action === "cancel" ? cancelBusy : busy || cancelBusy);
  find("inputs").textContent = request ? JSON.stringify(request, null, 2) : "No bound study request. Use the existing Workbench to prepare its exact registered draft request.";
  find("plot").replaceChildren();
  find("state").textContent = (response?.status || "No numerical response received.") + (busy ? " · Study request in flight; reconcile before retry." : "") + (cancelBusy ? " · Cancellation request in flight; release not established." : "");
  find("budget").textContent = response ? Object.entries(response.remaining_budget).map(([key, value]) => key.replaceAll("_", " ") + ": " + (value ?? "unknown")).join("; ") : "Remaining budget unknown.";
  find("metadata").textContent = response ? JSON.stringify({ method: response.method, environment: response.environment, binding: response.binding, diagnostics: response.result?.metadata || null }, null, 2) : "No method or environment observations received.";
  if (!response?.result) return;
  const children = response.result.children || [{ state: "SUCCEEDED", case_digest: "Registered public source", result: response.result }];
  for (const child of children) {
    const caption = document.createElement("p");
    caption.textContent = child.case_digest + " · " + child.state + (child.state === "HELD" ? " (capacity held; never dispatched)" : "");
    find("plot").append(caption);
    if (child.result) find("plot").append(globalThis.CarbonScientificStudyUI.plot(child.result.values, child.result.metadata.times || request.physical.requested_times));
  }
}
function acceptInput(args) {
  if (!args || !["capabilities", ...actions].includes(args.action) || Object.keys(args).sort().join() !== "action,request") throw Error("Invalid study tool input");
  const next = args.request === null ? null : S.request(args.request);
  if (request && !same(request, next)) throw Error("Study binding changed; reopen this view for the other operation");
  request = next; draw();
}
function acceptResult(result) {
  if (result.isError) throw Error("Study request unavailable; reconcile with the operator before retry");
  const value = result.structuredContent;
  if (!value || value.official_eligible !== false || !["capabilities", ...actions].includes(value.action) || Object.keys(value).sort().join() !== "action,official_eligible,request,response") throw Error("Invalid study result");
  if (value.action === "capabilities") {
    if (value.request !== null) throw Error("Unexpected capability binding");
    find("capabilities").textContent = JSON.stringify(S.capabilities(value.response), null, 2);
  } else {
    if (!request || !same(S.request(value.request), request)) throw Error("Result belongs to a different bound request");
    const checked = S.response(value.response, request);
    if (response && (checked.task_id !== response.task_id || checked.method !== response.method || checked.environment !== response.environment)) throw Error("Study identity changed");
    response = checked;
  }
  draw(); message("Received DEVELOPMENT data. No qualification follows.");
}
app.ontoolinput = ({ arguments: args }) => { try { acceptInput(args); } catch (error) { message(error.message); } };
app.ontoolresult = (result) => { try { acceptResult(result); } catch (error) { message(error.message); } };
app.ontoolcancelled = () => message("Host reported cancellation; worker release still requires controller observation.");
for (const action of actions) find(action).onclick = async () => {
  if (!request || !connected || (action === "cancel" ? cancelBusy : busy || cancelBusy)) return;
  if (action === "cancel") cancelBusy = true; else busy = true;
  draw(); message("Requesting " + action + " through the authorized host.");
  try {
    const result = await app.callServerTool({ name: "carbon_workbench_study_v1", arguments: { action, request: copy(request) } }, { timeout: 750000 });
    acceptResult(result);
  } catch (_) { message("Request outcome unavailable. Reconcile before retry; no automatic redispatch."); }
  finally { if (action === "cancel") cancelBusy = false; else busy = false; draw(); }
};
draw();
try { await app.connect(); connected = true; draw(); }
catch (_) { message("Compatible authorized MCP App host unavailable. Use the structured/text tool result."); }
