// After a publication, compare what both hostnames serve with the staged
// bundle that was uploaded, then read the Ask Carbon health endpoint. Exits 1
// on any difference, so "verified" always names the bytes it checked.
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { removeEdgeInjections } from "./fetch-live-baseline.mjs";

const sha256 = (buffer) => createHash("sha256").update(buffer).digest("hex");
export const HOSTS = ["carbonphysics.ai", "www.carbonphysics.ai"];

// URL path → staged file. `/`, `/workbench/`, `/miners/` and `/start-mining/`
// are served from their directory index.
export const DEFAULT_CHECKS = [
  ["/", "index.html"],
  ["/workbench/", "workbench/index.html"],
  ["/miners/", "miners/index.html"],
  ["/start-mining/", "start-mining/index.html"],
  ["/sitemap.xml", "sitemap.xml"],
  ["/assets/logo-boeing.png", "assets/logo-boeing.png"],
  ["/assets/logo-usaf.png", "assets/logo-usaf.png"],
  ["/assets/og-carbon.png", "assets/og-carbon.png"],
  ["/assets/x-logo.png", "assets/x-logo.png"],
  ["/workbench/atlas-source.json", "workbench/atlas-source.json"],
  ["/ask-carbon/pilot-designer.html", "ask-carbon/pilot-designer.html"],
];

export const EXPECTED_HEALTH = { active: true, reasons: [], model_config_id: "gemma-4-31b-turbo-tee:v1" };

export const healthProblems = (health) => {
  const problems = [];
  if (health?.active !== true) problems.push(`active is ${JSON.stringify(health?.active)}, expected true`);
  if (!Array.isArray(health?.reasons) || health.reasons.length) problems.push(`reasons is ${JSON.stringify(health?.reasons)}, expected []`);
  if (health?.model_config_id !== EXPECTED_HEALTH.model_config_id) problems.push(`model_config_id is ${JSON.stringify(health?.model_config_id)}, expected ${EXPECTED_HEALTH.model_config_id}`);
  return problems;
};

const get = async (url) => {
  const response = await fetch(url, { headers: { "user-agent": "carbon-ask-carbon-verify/1", "cache-control": "no-cache" } });
  return { status: response.status, bytes: Buffer.from(await response.arrayBuffer()) };
};

const main = async () => {
  const args = process.argv.slice(2);
  const bundleIndex = args.indexOf("--bundle");
  if (bundleIndex < 0) throw new Error("usage: verify-publication.mjs --bundle <staged bundle directory> [--static-only]");
  const bundle = resolve(args[bundleIndex + 1]);
  const failures = [];
  for (const host of HOSTS) {
    for (const [urlPath, file] of DEFAULT_CHECKS) {
      const expected = sha256(await readFile(join(bundle, file)));
      let actual = null;
      let status = null;
      // The edge varies its HTML injection per response; retry before failing.
      for (let attempt = 0; attempt < 4 && actual !== expected; attempt += 1) {
        const response = await get(`https://${host}${urlPath}`);
        status = response.status;
        actual = sha256(file.endsWith(".html") ? Buffer.from(removeEdgeInjections(response.bytes.toString("utf8")), "utf8") : response.bytes);
      }
      const ok = status === 200 && actual === expected;
      process.stdout.write(`${ok ? "ok  " : "FAIL"} ${host}${urlPath} HTTP ${status} ${actual.slice(0, 12)}…${ok ? "" : ` expected ${expected.slice(0, 12)}…`}\n`);
      if (!ok) failures.push(`${host}${urlPath}`);
    }
    if (!args.includes("--static-only")) {
      const response = await get(`https://${host}/api/ask-carbon/health`);
      let problems;
      try {
        problems = response.status === 200 ? healthProblems(JSON.parse(response.bytes.toString("utf8"))) : [`HTTP ${response.status}`];
      } catch {
        problems = ["unparseable health response"];
      }
      process.stdout.write(`${problems.length ? "FAIL" : "ok  "} ${host}/api/ask-carbon/health${problems.length ? ` ${problems.join("; ")}` : " active:true reasons:[] gemma-4-31b-turbo-tee:v1"}\n`);
      if (problems.length) failures.push(`${host}/api/ask-carbon/health`);
    }
  }
  if (failures.length) {
    process.stdout.write(`\nNOT VERIFIED: ${failures.length} check(s) failed. After a deployment, this means roll back.\n`);
    process.exitCode = 1;
  } else {
    process.stdout.write("\nVERIFIED: every check matched the staged bundle on both hostnames.\n");
  }
};

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 1;
  });
}
