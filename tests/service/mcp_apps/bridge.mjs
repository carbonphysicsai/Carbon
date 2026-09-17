import { AppBridge, PostMessageTransport } from "../../../carbon/miner_mcp/apps_ui/node_modules/@modelcontextprotocol/ext-apps/dist/src/app-bridge.js";

const iframe = document.getElementById("view");
const bridge = new AppBridge(null, { name: "Carbon deterministic AppBridge fixture", version: "1.0.0" }, { serverTools: {} });
globalThis.calls = [];
bridge.onsizechange = ({ height }) => { if (Number.isFinite(height)) iframe.style.height = Math.min(height + 8, 2400) + "px"; };
bridge.oncalltool = async (params) => {
  if (params.name !== "carbon_workbench_study_v1" || !["start", "status", "result", "cancel"].includes(params.arguments.action) || JSON.stringify(params.arguments.request) !== JSON.stringify(globalThis.fixture.request)) throw Error("Fixture exact binding required");
  globalThis.calls.push(params.arguments.action);
  const payload = { ...globalThis.fixture.structured, action: params.arguments.action };
  if (params.arguments.action === "start" && globalThis.delayStart) {
    globalThis.startWaiting = true;
    await new Promise((resolve) => { globalThis.releaseStart = resolve; });
    globalThis.startWaiting = false;
  }
  if (params.arguments.action === "cancel" && globalThis.startWaiting) payload.response = { ...payload.response, status: "CANCEL_REQUESTED", result: null };
  return { content: [{ type: "text", text: JSON.stringify(payload) }], structuredContent: payload, isError: false };
};
bridge.oninitialized = async () => {
  await bridge.sendToolInput({ arguments: { action: "start", request: globalThis.fixture.request } });
  await bridge.sendToolResult(globalThis.fixture.result);
  globalThis.bridgeReady = true;
};
globalThis.sendRejectedResult = async () => {
  const result = structuredClone(globalThis.fixture.result);
  result.structuredContent.response.qualification = "QUALIFIED";
  await bridge.sendToolResult(result);
};
await bridge.connect(new PostMessageTransport(iframe.contentWindow, iframe.contentWindow));
iframe.srcdoc = globalThis.appHtml;
