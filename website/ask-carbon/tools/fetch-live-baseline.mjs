// Re-derive the `--existing-site` baseline from the live site, for an operator
// who has no copy of the owner-supplied site archive. Every path the baseline
// manifest lists is fetched from one hostname, the Cloudflare edge injections
// are removed from HTML, the integrated homepage is returned to its reviewed
// source, and each file must match the manifest by SHA-256 and size. One
// mismatch fails the whole run and writes nothing: it means live is no longer
// the baseline the candidate was built against, so stop and rebuild for a
// fresh decision rather than publish over an unknown state.
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, rename, rm, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { loadBaselineManifest } from "./integrate-static.mjs";

const sha256 = (buffer) => createHash("sha256").update(buffer).digest("hex");

// The edge adds a bot-challenge script and, on some responses, the Web
// Analytics beacon immediately before `</body>`. The beacon line carries its
// own trailing newline.
export const removeEdgeInjections = (html) => html
  .replace(/<script>\(function\(\)\{function c\(\)\{[\s\S]*?<\/script>/g, "")
  .replace(/<script[^>]*cloudflareinsights[^>]*><\/script>\n?/g, "");

// The exact inverse of integrateHtml(): the stylesheet line before `</head>`
// and the element plus module script before `</body>`.
export const removeAskCarbonIntegration = (html) => html
  .replace(/ {2}<link data-ask-carbon-integration [^\n]*\n/, "")
  .replace(/ {2}<ask-carbon data-ask-carbon-integration[^\n]*\n {2}<script type="module" src="[^"]*ask-carbon\.js"><\/script>\n/, "");

export const recoverBaselineBytes = (path, raw, expectedSha256) => {
  if (sha256(raw) === expectedSha256) return raw;
  if (!path.endsWith(".html")) return raw;
  let html = removeEdgeInjections(raw.toString("utf8"));
  if (path === "index.html") html = removeAskCarbonIntegration(html);
  return Buffer.from(html, "utf8");
};

const fetchBytes = async (url) => {
  const response = await fetch(url, { headers: { "user-agent": "carbon-ask-carbon-baseline/1" } });
  if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
  return Buffer.from(await response.arrayBuffer());
};

export const fetchBaseline = async ({ host, manifest, attempts = 4, fetcher = fetchBytes }) => {
  const files = [];
  const problems = [];
  for (const asset of manifest.assets) {
    let bytes = null;
    let lastProblem = null;
    // The edge varies its injection per response, so an HTML page that fails
    // to reduce is fetched again before it counts as a mismatch.
    for (let attempt = 0; attempt < attempts && bytes === null; attempt += 1) {
      try {
        const candidate = recoverBaselineBytes(asset.path, await fetcher(`https://${host}/${asset.path}`), asset.sha256);
        if (candidate.length === asset.bytes && sha256(candidate) === asset.sha256) bytes = candidate;
        else lastProblem = `digest ${sha256(candidate)} (${candidate.length} bytes), manifest ${asset.sha256} (${asset.bytes} bytes)`;
      } catch (error) {
        lastProblem = error.message;
      }
    }
    if (bytes === null) problems.push(`${asset.path}: ${lastProblem}`);
    else files.push({ path: asset.path, bytes });
  }
  return { files, problems };
};

const main = async () => {
  const args = process.argv.slice(2);
  const option = (name) => {
    const index = args.indexOf(name);
    return index >= 0 ? args[index + 1] : undefined;
  };
  const host = option("--host");
  const out = option("--out");
  if (!host || !out) throw new Error("usage: fetch-live-baseline.mjs --host carbonphysics.ai --out <empty directory> [--baseline-manifest <path>]");
  const manifest = await loadBaselineManifest(option("--baseline-manifest") ? resolve(option("--baseline-manifest")) : undefined);
  const { files, problems } = await fetchBaseline({ host, manifest });
  if (problems.length) {
    process.stderr.write(`${host}: ${files.length}/${manifest.assets.length} match the baseline manifest. Live is not the recorded baseline; do not build or deploy.\n${problems.map((line) => `  ${line}`).join("\n")}\n`);
    process.exitCode = 1;
    return;
  }
  const destination = resolve(out);
  await mkdir(dirname(destination), { recursive: true });
  const staging = await mkdtemp(join(dirname(destination), ".baseline-"));
  try {
    for (const file of files) {
      await mkdir(dirname(join(staging, file.path)), { recursive: true });
      await writeFile(join(staging, file.path), file.bytes, { flag: "wx" });
    }
    await rename(staging, destination);
  } catch (error) {
    await rm(staging, { recursive: true, force: true });
    throw error;
  }
  process.stdout.write(`${host}: ${files.length}/${manifest.assets.length} match the baseline manifest; written to ${destination}\n`);
};

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 1;
  });
}
