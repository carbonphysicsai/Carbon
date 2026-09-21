import { createHash } from "node:crypto";
import { lstat, mkdir, mkdtemp, opendir, readFile, rename, rm, writeFile } from "node:fs/promises";
import { basename, dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const KNOWN_LIVE_SHA256 = "5ebb43e859e9837f74bbc93b5748b2db95a6700821afbfcecb407e75702e2020";
const OWNER_UPLOADED_SHA256 = "546fb89d7df7de98f191ae9585d9952db773eedff4bf33c069f9c6b29f6efb7b";
const OWNER_UPLOAD_RECONCILIATION = "owner-upload-2026-09-18-plus-workbench-navigation-v1";
const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "..");
const PILOT_DESIGNER = resolve(ROOT, "../../Business/Carbon_Fit/workbench/Carbon_Client_Pilot_Designer_Preview.html");
const DEFAULT_BASELINE_MANIFEST = resolve(ROOT, "production-baseline.manifest.json");

// The homepage the bundle publishes is the integrated document, not the
// baseline copy of the currently deployed homepage.
const REPLACED_BY_INTEGRATION = "index.html";

const sha256 = (buffer) => createHash("sha256").update(buffer).digest("hex");

export const loadBaselineManifest = async (path = DEFAULT_BASELINE_MANIFEST) => {
  const manifest = JSON.parse(await readFile(path, "utf8"));
  if (!Array.isArray(manifest.assets) || manifest.assets.length === 0) {
    throw new Error(`Baseline manifest ${path} lists no assets.`);
  }
  const seen = new Set();
  for (const asset of manifest.assets) {
    if (typeof asset.path !== "string" || !asset.path) throw new Error(`Baseline manifest ${path} has an asset without a path.`);
    if (asset.path.startsWith("/") || asset.path.split("/").some((part) => !part || part === "." || part === "..")) {
      throw new Error(`Baseline manifest ${path} has an unbounded asset path: ${asset.path}`);
    }
    if (!/^[0-9a-f]{64}$/.test(asset.sha256 ?? "")) throw new Error(`Baseline manifest ${path} has no SHA-256 for ${asset.path}.`);
    if (!Number.isInteger(asset.bytes) || asset.bytes <= 0) throw new Error(`Baseline manifest ${path} has no positive byte size for ${asset.path}.`);
    if (seen.has(asset.path)) throw new Error(`Baseline manifest ${path} lists ${asset.path} twice.`);
    seen.add(asset.path);
  }
  return manifest;
};

// Retained as regression coverage of the paths observed live on 2026-09-19/20.
// This list is a floor, never a proof of a complete inventory: completeness is
// asserted only by `manifest.inventory_complete`.
export const REQUIRED_PRODUCTION_PATHS = Object.freeze([
  "index.html",
  "assets/carbon-66e3549179d4.png",
  "assets/carbon-f7ea9506b7b9.png",
  "workbench/index.html",
  "workbench/app.js",
  "workbench/assist-contract.js",
  "workbench/assist-ui.js",
  "workbench/atlas.js",
  "workbench/atlas-source.json",
  "workbench/cooling-v02.js",
  "workbench/engine.js",
  "workbench/styles.css",
]);

/**
 * Verify real regular-file contents against trusted digests.
 *
 * `fs.access` was insufficient: it accepts empty files, wrong content,
 * directories standing in for files, and symlinks. Every expectation here is
 * checked against the bytes actually on disk.
 *
 * @returns {Promise<Array<{path:string,problem:string,expected?:string,actual?:string}>>}
 */
export const verifyAssetContents = async (directory, expectations) => {
  const problems = [];
  for (const expected of expectations) {
    const absolute = join(directory, expected.path);
    let stats;
    try {
      stats = await lstat(absolute);
    } catch {
      problems.push({ path: expected.path, problem: "missing" });
      continue;
    }
    if (stats.isSymbolicLink()) {
      problems.push({ path: expected.path, problem: "unsupported_symlink" });
      continue;
    }
    if (stats.isDirectory()) {
      problems.push({ path: expected.path, problem: "directory_at_file_path" });
      continue;
    }
    if (!stats.isFile()) {
      problems.push({ path: expected.path, problem: "not_a_regular_file" });
      continue;
    }
    if (stats.size !== expected.bytes) {
      problems.push({ path: expected.path, problem: "size_mismatch", expected: String(expected.bytes), actual: String(stats.size) });
      continue;
    }
    const actual = sha256(await readFile(absolute));
    if (actual !== expected.sha256) {
      problems.push({ path: expected.path, problem: "digest_mismatch", expected: expected.sha256, actual });
    }
  }
  return problems;
};

export const describeProblems = (problems) => problems
  .map((problem) => {
    const detail = problem.expected ? ` (expected ${problem.expected}, found ${problem.actual})` : "";
    return `${problem.path}: ${problem.problem}${detail}`;
  })
  .join("; ");

/**
 * Copy a tree into a fresh destination, refusing anything we cannot vouch for.
 *
 * `fs.cp` with `force: false, errorOnExist: false` silently preserved stale
 * destination files. This copy targets an empty staging directory and treats
 * any pre-existing destination entry as a hard conflict.
 */
export const copyTreeStrict = async (source, destination, { skip = () => false, base = source } = {}) => {
  await mkdir(destination, { recursive: true });
  const directory = await opendir(source);
  for await (const entry of directory) {
    const from = join(source, entry.name);
    const to = join(destination, entry.name);
    const relativePath = relative(base, from).split(sep).join("/");
    if (skip(relativePath)) continue;
    if (entry.isSymbolicLink()) throw new Error(`Refusing to copy unsupported symlink ${relativePath} from ${base}.`);
    if (entry.isDirectory()) {
      await copyTreeStrict(from, to, { skip, base });
      continue;
    }
    if (!entry.isFile()) throw new Error(`Refusing to copy ${relativePath}: not a regular file.`);
    let conflict = null;
    try {
      conflict = await lstat(to);
    } catch {
      conflict = null;
    }
    if (conflict) throw new Error(`Destination conflict: ${relativePath} already exists in the staging tree.`);
    await writeFile(to, await readFile(from), { flag: "wx" });
  }
};

/** Enumerate the staged bytes so the bundle has one verifiable identity. */
export const inventoryDirectory = async (directory, base = directory) => {
  const entries = [];
  const handle = await opendir(directory);
  for await (const entry of handle) {
    const absolute = join(directory, entry.name);
    const relativePath = relative(base, absolute).split(sep).join("/");
    if (entry.isSymbolicLink()) throw new Error(`Staged bundle contains an unsupported symlink: ${relativePath}`);
    if (entry.isDirectory()) {
      entries.push(...await inventoryDirectory(absolute, base));
      continue;
    }
    if (!entry.isFile()) throw new Error(`Staged bundle contains a non-regular file: ${relativePath}`);
    const bytes = await readFile(absolute);
    entries.push({ path: relativePath, sha256: sha256(bytes), bytes: bytes.length });
  }
  return entries.sort((left, right) => (left.path < right.path ? -1 : left.path > right.path ? 1 : 0));
};

export const bundleIdentity = (inventory) => sha256(Buffer.from(inventory.map((entry) => `${entry.sha256}  ${entry.bytes}  ${entry.path}\n`).join("")));

const isEmptyOrAbsent = async (directory) => {
  let stats;
  try {
    stats = await lstat(directory);
  } catch {
    return true;
  }
  if (!stats.isDirectory()) throw new Error(`Output bundle root ${directory} exists and is not a directory.`);
  const handle = await opendir(directory);
  try {
    return (await handle.read()) === null;
  } finally {
    await handle.close().catch(() => {});
  }
};

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
    if (argument === "--require-complete-bundle") {
      result["require-complete-bundle"] = true;
      continue;
    }
    if (!argument.startsWith("--") || !argv[index + 1]) throw new Error(`Invalid argument: ${argument}`);
    result[argument.slice(2)] = argv[index + 1];
    index += 1;
  }
  if (!result.input || !result.output) throw new Error("Usage: integrate-static.mjs --input PATH --output PATH [--asset-prefix PREFIX] [--reconcile-owner-upload] [--existing-site DIR] [--baseline-manifest PATH] [--require-complete-bundle]");
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

const escapeAttribute = (value) => String(value)
  .replaceAll("&", "&amp;")
  .replaceAll('"', "&quot;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;");

const main = async () => {
  const args = parseArgs(process.argv.slice(2));
  const inputPath = resolve(args.input);
  const outputPath = resolve(args.output);
  const bundleRoot = dirname(outputPath);
  const outputName = basename(outputPath);
  const manifest = await loadBaselineManifest(args["baseline-manifest"] ? resolve(args["baseline-manifest"]) : undefined);

  // Preview and changed-source builds are inspection artifacts. They never
  // establish production authorization, so they may not claim deployability.
  const previewOnly = args["staging-preview"] === true || args["allow-changed-source"] === true;

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
  const integrated = Buffer.from(integrateHtml(input.toString("utf8"), {
    assetPrefix: args["asset-prefix"],
    knowledgeUrl: args["knowledge-url"],
    apiUrl: args["api-url"] ?? "/api/ask-carbon",
    pilotUrl: args["pilot-url"],
    stagingPreview: args["staging-preview"] === true,
  }));
  const integratedSha256 = sha256(integrated);

  // Fresh isolated output construction. We never write into a directory that
  // already holds content, and we never delete an existing user directory.
  if (!(await isEmptyOrAbsent(bundleRoot))) {
    throw new Error(`Refusing to build into a non-empty output directory: ${bundleRoot}. Stale files there can survive assembly and be published. Choose a fresh --output directory; remove the old one yourself if you no longer need it.`);
  }
  const parent = dirname(bundleRoot);
  await mkdir(parent, { recursive: true });
  const staging = await mkdtemp(join(parent, ".ask-carbon-staging-"));
  try {
    if (args["existing-site"]) {
      const existingSite = resolve(args["existing-site"]);
      const baselineProblems = await verifyAssetContents(existingSite, manifest.assets);
      if (baselineProblems.length) {
        throw new Error(`--existing-site ${existingSite} is not a verified copy of the current production asset set. ${describeProblems(baselineProblems)}. Obtain the authoritative current assets before building a production bundle; do not create placeholder files to satisfy this check.`);
      }
      // index.html is replaced by the integrated homepage written below.
      await copyTreeStrict(existingSite, staging, { skip: (path) => path === REPLACED_BY_INTEGRATION });
    }
    await writeFile(join(staging, outputName), integrated, { flag: "wx" });
    const assetRelative = args["asset-prefix"].replace(/^\.\//, "").replace(/^\//, "");
    const assetDirectory = join(staging, assetRelative);
    await mkdir(assetDirectory, { recursive: true });
    const askCarbonAssets = [];
    for (const [source, destination] of [
      [join(ROOT, "public", "ask-carbon.css"), "ask-carbon.css"],
      [join(ROOT, "public", "ask-carbon.js"), "ask-carbon.js"],
      [join(ROOT, "public", "release-contract.js"), "release-contract.js"],
      [join(ROOT, "knowledge", "public-knowledge.v1.json"), "public-knowledge.v1.json"],
      [PILOT_DESIGNER, "pilot-designer.html"],
    ]) {
      const bytes = await readFile(source);
      await writeFile(join(assetDirectory, destination), bytes, { flag: "wx" });
      askCarbonAssets.push({ path: `${assetRelative}/${destination}`, sha256: sha256(bytes), bytes: bytes.length });
    }

    // Verify the bytes that were actually staged, not the bytes we intended.
    const stagedExpectations = [
      ...manifest.assets.filter((asset) => asset.path !== REPLACED_BY_INTEGRATION),
      { path: outputName, sha256: integratedSha256, bytes: integrated.length },
      ...askCarbonAssets,
    ];
    const stagedProblems = args["existing-site"]
      ? await verifyAssetContents(staging, stagedExpectations)
      : await verifyAssetContents(staging, stagedExpectations.filter((asset) => !manifest.assets.some((baseline) => baseline.path === asset.path)));
    if (stagedProblems.length) {
      throw new Error(`Staged bundle verification failed after assembly: ${describeProblems(stagedProblems)}.`);
    }

    const inventory = await inventoryDirectory(staging);
    const identity = bundleIdentity(inventory);
    const baselinePreserved = args["existing-site"]
      ? manifest.assets.filter((asset) => asset.path !== REPLACED_BY_INTEGRATION).every((asset) => inventory.some((entry) => entry.path === asset.path && entry.sha256 === asset.sha256))
      : false;
    const inventoryComplete = manifest.inventory_complete === true;
    const deployable = baselinePreserved && inventoryComplete && !previewOnly;

    if (args["require-complete-bundle"] && !deployable) {
      const reasons = [];
      if (!args["existing-site"]) reasons.push("no --existing-site baseline was supplied, so no existing production asset is preserved");
      else if (!baselinePreserved) reasons.push("the staged bundle does not reproduce every verified baseline asset");
      if (!inventoryComplete) reasons.push(`the baseline manifest is "${manifest.inventory_status}": ${manifest.inventory_status_reason ?? "the deployed asset set has not been enumerated"}`);
      if (previewOnly) reasons.push("--staging-preview/--allow-changed-source builds are inspection artifacts and never carry production authorization");
      throw new Error(`Refusing to certify a deployable production bundle: ${reasons.join("; ")}. Deploying an incomplete asset set to carbonwebsite would withdraw the missing paths from production.`);
    }

    await rename(staging, bundleRoot);

    process.stdout.write(`${JSON.stringify({
      input: inputPath,
      supplied_input_sha256: suppliedInputSha256,
      source_reconciliation: sourceReconciliation,
      integration_input_sha256: inputSha256,
      output: outputPath,
      output_sha256: integratedSha256,
      asset_directory: join(bundleRoot, assetRelative),
      bundle_root: bundleRoot,
      bundle_identity_sha256: identity,
      staged_file_count: inventory.length,
      baseline_manifest_status: manifest.inventory_status,
      baseline_inventory_complete: inventoryComplete,
      baseline_assets_preserved: baselinePreserved,
      preview_only: previewOnly,
      deployable_to_carbonwebsite: deployable,
      release_authorized: false,
      release_authorization_note: "Asset preservation is not release authorization. Publication and public activation remain governed by the release decision packet and named-operator authority.",
      staged_inventory: inventory,
    }, null, 2)}\n`);

    if (!deployable) {
      const why = !inventoryComplete
        ? `the baseline manifest is "${manifest.inventory_status}" — the deployed asset set has not been enumerated under authenticated access`
        : !baselinePreserved
          ? "the staged bundle does not reproduce every verified baseline asset"
          : "this is a preview/changed-source build";
      process.stderr.write(`WARNING: ${bundleRoot} is NOT certified as a complete carbonwebsite asset set because ${why}. This output is a preview/inspection artifact only; deploying it could withdraw live paths from production.\n`);
    }
  } catch (error) {
    await rm(staging, { recursive: true, force: true }).catch(() => {});
    throw error;
  }
};

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 1;
  });
}
