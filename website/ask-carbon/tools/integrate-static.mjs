import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const KNOWN_LIVE_SHA256 = "5ebb43e859e9837f74bbc93b5748b2db95a6700821afbfcecb407e75702e2020";
const OWNER_UPLOADED_SHA256 = "546fb89d7df7de98f191ae9585d9952db773eedff4bf33c069f9c6b29f6efb7b";
const OWNER_UPLOAD_RECONCILIATION = "owner-upload-2026-09-18-plus-workbench-navigation-v1";
const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "..");
const PILOT_DESIGNER = resolve(ROOT, "../../Business/Carbon_Fit/workbench/Carbon_Client_Pilot_Designer_Preview.html");

const parseArgs = (argv) => {
  const result = { "asset-prefix": "./ask-carbon", "expected-sha256": KNOWN_LIVE_SHA256 };
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === "--allow-changed-source") {
      result["allow-changed-source"] = true;
      continue;
    }
    if (argument === "--staging-preview") {
      result["staging-preview"] = true;
      continue;
    }
    if (argument === "--reconcile-owner-upload") {
      result["reconcile-owner-upload"] = true;
      continue;
    }
    if (!argument.startsWith("--") || !argv[index + 1]) throw new Error(`Invalid argument: ${argument}`);
    result[argument.slice(2)] = argv[index + 1];
    index += 1;
  }
  if (!result.input || !result.output) throw new Error("Usage: integrate-static.mjs --input PATH --output PATH [--asset-prefix PREFIX] [--reconcile-owner-upload]");
  return result;
};

const replaceExactlyOnce = (value, marker, replacement, label) => {
  const first = value.indexOf(marker);
  if (first < 0 || value.indexOf(marker, first + marker.length) >= 0) {
    throw new Error(`Owner-upload reconciliation expected exactly one ${label} marker.`);
  }
  return `${value.slice(0, first)}${replacement}${value.slice(first + marker.length)}`;
};

export const reconcileOwnerUploadedHomepage = (html) => {
  let reconciled = replaceExactlyOnce(
    html,
    ".network-flow-art img{height:auto;object-fit:contain;object-position:center}\n</style>",
    ".network-flow-art img{height:auto;object-fit:contain;object-position:center}\n\n/* Workbench navigation: allow the existing links to wrap on tablets. */\n@media(min-width:651px) and (max-width:1100px){header nav{flex-wrap:wrap;justify-content:flex-end;row-gap:8px}}\n</style>",
    "responsive-style",
  );
  reconciled = replaceExactlyOnce(
    reconciled,
    '<a href="#company">Company</a></nav>',
    '<a href="#company">Company</a><a href="/workbench/">Workbench</a></nav>',
    "main-navigation",
  );
  return replaceExactlyOnce(
    reconciled,
    '<a href="#faq">FAQ</a></nav>',
    '<a href="#faq">FAQ</a><a href="/workbench/">Workbench</a></nav>',
    "footer-navigation",
  );
};

export const integrateHtml = (html, {
  assetPrefix = "./ask-carbon",
  knowledgeUrl,
  apiUrl = "/api/ask-carbon",
  pilotUrl,
  stagingPreview = false,
} = {}) => {
  if (!/<\/head\s*>/i.test(html) || !/<\/body\s*>/i.test(html)) throw new Error("Input is not a complete HTML document.");
  if (html.includes("data-ask-carbon-integration")) throw new Error("Ask Carbon is already integrated.");
  const prefix = assetPrefix.replace(/\/$/, "");
  const assetPath = prefix.replace(/^\.\//, "").replace(/^\//, "");
  if (!assetPath || assetPath.split("/").some((part) => !part || part === "." || part === "..")) {
    throw new Error("Asset prefix must be a bounded relative or root-relative path.");
  }
  const resolvedKnowledgeUrl = knowledgeUrl ?? `${prefix}/public-knowledge.v1.json`;
  const resolvedPilotUrl = pilotUrl ?? `${prefix}/pilot-designer.html`;
  const head = `  <link data-ask-carbon-integration rel="stylesheet" href="${escapeAttribute(prefix)}/ask-carbon.css">\n`;
  const body = [
    `  <ask-carbon data-ask-carbon-integration knowledge-url="${escapeAttribute(resolvedKnowledgeUrl)}" api-url="${escapeAttribute(apiUrl)}" pilot-url="${escapeAttribute(resolvedPilotUrl)}"${stagingPreview ? " staging-preview" : ""}></ask-carbon>`,
    `  <script type="module" src="${escapeAttribute(prefix)}/ask-carbon.js"></script>`,
    "",
  ].join("\n");
  return html.replace(/<\/head\s*>/i, `${head}</head>`).replace(/<\/body\s*>/i, `${body}</body>`);
};

const sha256 = (buffer) => createHash("sha256").update(buffer).digest("hex");

const escapeAttribute = (value) => String(value)
  .replaceAll("&", "&amp;")
  .replaceAll('"', "&quot;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;");

const main = async () => {
  const args = parseArgs(process.argv.slice(2));
  const inputPath = resolve(args.input);
  const outputPath = resolve(args.output);
  const suppliedInput = await readFile(inputPath);
  const suppliedInputSha256 = sha256(suppliedInput);
  let input = suppliedInput;
  let sourceReconciliation = null;
  if (args["reconcile-owner-upload"]) {
    if (suppliedInputSha256 !== OWNER_UPLOADED_SHA256) {
      throw new Error(`Owner-upload source SHA-256 ${suppliedInputSha256} does not match ${OWNER_UPLOADED_SHA256}.`);
    }
    input = Buffer.from(reconcileOwnerUploadedHomepage(suppliedInput.toString("utf8")));
    sourceReconciliation = OWNER_UPLOAD_RECONCILIATION;
  }
  const inputSha256 = sha256(input);
  if (!args["allow-changed-source"] && inputSha256 !== args["expected-sha256"]) {
    throw new Error(`Static source SHA-256 ${inputSha256} does not match reviewed source ${args["expected-sha256"]}. Review the changed homepage before integrating.`);
  }
  const integrated = integrateHtml(input.toString("utf8"), {
    assetPrefix: args["asset-prefix"],
    knowledgeUrl: args["knowledge-url"],
    apiUrl: args["api-url"] ?? "/api/ask-carbon",
    pilotUrl: args["pilot-url"],
    stagingPreview: args["staging-preview"] === true,
  });
  await mkdir(dirname(outputPath), { recursive: true });
  await writeFile(outputPath, integrated, { flag: "wx" });
  const assetDirectory = join(dirname(outputPath), args["asset-prefix"].replace(/^\.\//, "").replace(/^\//, ""));
  await mkdir(assetDirectory, { recursive: true });
  for (const [source, destination] of [
    [join(ROOT, "public", "ask-carbon.css"), "ask-carbon.css"],
    [join(ROOT, "public", "ask-carbon.js"), "ask-carbon.js"],
    [join(ROOT, "public", "release-contract.js"), "release-contract.js"],
    [join(ROOT, "knowledge", "public-knowledge.v1.json"), "public-knowledge.v1.json"],
    [PILOT_DESIGNER, "pilot-designer.html"],
  ]) {
    await writeFile(join(assetDirectory, destination), await readFile(source), { flag: "wx" });
  }
  process.stdout.write(`${JSON.stringify({
    input: inputPath,
    supplied_input_sha256: suppliedInputSha256,
    source_reconciliation: sourceReconciliation,
    integration_input_sha256: inputSha256,
    output: outputPath,
    output_sha256: sha256(Buffer.from(integrated)),
    asset_directory: assetDirectory,
  }, null, 2)}\n`);
};

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 1;
  });
}
