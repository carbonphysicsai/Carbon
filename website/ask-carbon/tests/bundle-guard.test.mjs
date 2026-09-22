// Real-filesystem and real-child-process coverage for the production bundle
// guard. These tests deliberately avoid injected probes: the defects they pin
// (presence-only checks, stale destination survival, an incomplete hard-coded
// path list) were all invisible to in-memory fakes.
import test from "node:test";
import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  REQUIRED_PRODUCTION_PATHS,
  bundleIdentity,
  inventoryDirectory,
  loadBaselineManifest,
  verifyAssetContents,
} from "../tools/integrate-static.mjs";

const TOOL = fileURLToPath(new URL("../tools/integrate-static.mjs", import.meta.url));
const sha256 = (buffer) => createHash("sha256").update(buffer).digest("hex");

const workspaces = [];
const workspace = async () => {
  const directory = await mkdtemp(join(tmpdir(), "ask-carbon-guard-"));
  workspaces.push(directory);
  return directory;
};
test.after(async () => {
  for (const directory of workspaces) await rm(directory, { recursive: true, force: true });
});

/**
 * Run the CLI as a real child process and observe the real exit status.
 * `execFile` reports the process's own exit code, so a wrapper cannot mask a
 * failing exit the way a shell pipeline can.
 */
const runCli = (args) => new Promise((resolve) => {
  execFile(process.execPath, [TOOL, ...args], { encoding: "utf8" }, (error, stdout, stderr) => {
    resolve({ code: error ? (error.code ?? 1) : 0, stdout, stderr });
  });
});

const writeFixture = async (root, path, contents) => {
  const absolute = join(root, path);
  await mkdir(dirname(absolute), { recursive: true });
  await writeFile(absolute, contents);
  return absolute;
};

/**
 * A small self-consistent baseline: a stand-in production site plus the
 * manifest that describes it. `extra` lets a test add a legitimate asset that
 * is absent from the old hard-coded REQUIRED_PRODUCTION_PATHS list.
 */
const buildBaseline = async ({ complete = true, extra = null, rollback = "0f1e2d3c-4b5a-4978-8765-43210fedcba9" } = {}) => {
  const root = await workspace();
  const site = join(root, "current");
  const files = [
    ["index.html", "<html><head></head><body>live homepage</body></html>"],
    ["404.html", "<html><head></head><body>not found</body></html>"],
    ["site.css", "body{background:#f5f5f0}"],
    ["favicon.svg", "<svg xmlns='http://www.w3.org/2000/svg'/>"],
    ["robots.txt", "User-agent: *\nAllow: /\n"],
    ["sitemap.xml", "<urlset/>"],
    ["about/index.html", "<html><head></head><body>about</body></html>"],
    ["customers/index.html", "<html><head></head><body>customers</body></html>"],
    ["investors/index.html", "<html><head></head><body>investors</body></html>"],
    ["miners/index.html", "<html><head></head><body>miners</body></html>"],
    ["papers/index.html", "<html><head></head><body>papers</body></html>"],
    ["validators/index.html", "<html><head></head><body>validators</body></html>"],
    ["assets/brand-1.svg", "<svg xmlns='http://www.w3.org/2000/svg'><title>brand-1</title></svg>"],
    ["assets/brand-2.svg", "<svg xmlns='http://www.w3.org/2000/svg'><title>brand-2</title></svg>"],
    ["assets/neue-0.otf", "OTF-400-bytes"],
    ["assets/neue-1.otf", "OTF-600-bytes"],
    ["assets/og-carbon.png", "PNG-OG-bytes"],
    ["workbench/index.html", "<html><head></head><body>workbench</body></html>"],
    ["workbench/app.js", "export const app = 'real';"],
    ["workbench/assist-contract.js", "export const contract = 1;"],
    ["workbench/assist-ui.js", "export const ui = 1;"],
    ["workbench/atlas.js", "export const atlas = 1;"],
    ["workbench/atlas-source.json", '{"atlas":"source"}'],
    ["workbench/cooling-v02.js", "export const cooling = 1;"],
    ["workbench/engine.js", "export const engine = 1;"],
    ["workbench/styles.css", "body{color:#111}"],
  ];
  if (extra) files.push(extra);
  const assets = [];
  for (const [path, contents] of files) {
    await writeFixture(site, path, contents);
    assets.push({ path, sha256: sha256(Buffer.from(contents)), bytes: Buffer.byteLength(contents) });
  }
  const manifestPath = join(root, "baseline.manifest.json");
  await writeFile(manifestPath, JSON.stringify({
    manifest_version: 1,
    target: "carbonwebsite",
    inventory_status: complete ? "verified-complete" : "incomplete",
    inventory_complete: complete,
    inventory_status_reason: complete ? "fixture" : "fixture: deployed asset set not enumerated",
    deployment_target_observed: { worker: "carbonwebsite", live_version_id: rollback },
    assets,
  }, null, 2));
  const input = join(root, "input.html");
  const inputHtml = "<html><head><title>Carbon</title></head><body>new homepage</body></html>";
  await writeFile(input, inputHtml);
  return { root, site, manifestPath, input, inputSha256: sha256(Buffer.from(inputHtml)), assets };
};

const productionArgs = (fixture, output, extra = []) => [
  "--input", fixture.input,
  "--output", output,
  "--asset-prefix", "./ask-carbon",
  "--expected-sha256", fixture.inputSha256,
  "--existing-site", fixture.site,
  "--baseline-manifest", fixture.manifestPath,
  ...extra,
];

// --- A. content verification, not path presence -----------------------------

test("a missing required file is reported as missing, not accepted", async () => {
  const fixture = await buildBaseline();
  const manifest = JSON.parse(await readFile(fixture.manifestPath, "utf8"));
  await rm(join(fixture.site, "workbench/app.js"));
  const problems = await verifyAssetContents(fixture.site, manifest.assets);
  assert.deepEqual(problems, [{ path: "workbench/app.js", problem: "missing" }]);
});

test("an empty file at a required path is rejected although fs.access would accept it", async () => {
  const fixture = await buildBaseline();
  const manifest = JSON.parse(await readFile(fixture.manifestPath, "utf8"));
  await writeFile(join(fixture.site, "workbench/app.js"), "");
  const [problem] = await verifyAssetContents(fixture.site, manifest.assets);
  assert.equal(problem.path, "workbench/app.js");
  assert.equal(problem.problem, "size_mismatch");
  assert.equal(problem.actual, "0");
});

test("wrong content of the right length is caught by the digest, not the size", async () => {
  const fixture = await buildBaseline();
  const manifest = JSON.parse(await readFile(fixture.manifestPath, "utf8"));
  const expected = manifest.assets.find((asset) => asset.path === "workbench/atlas.js");
  await writeFile(join(fixture.site, "workbench/atlas.js"), "X".repeat(expected.bytes));
  const [problem] = await verifyAssetContents(fixture.site, manifest.assets);
  assert.equal(problem.problem, "digest_mismatch");
  assert.equal(problem.expected, expected.sha256);
  assert.notEqual(problem.actual, expected.sha256);
});

test("a directory standing in for a required file is rejected", async () => {
  const fixture = await buildBaseline();
  const manifest = JSON.parse(await readFile(fixture.manifestPath, "utf8"));
  await rm(join(fixture.site, "workbench/engine.js"));
  await mkdir(join(fixture.site, "workbench/engine.js"), { recursive: true });
  const [problem] = await verifyAssetContents(fixture.site, manifest.assets);
  assert.deepEqual(problem, { path: "workbench/engine.js", problem: "directory_at_file_path" });
});

test("an unsupported symlink at a required file path is rejected without following it", async () => {
  const fixture = await buildBaseline();
  const manifest = JSON.parse(await readFile(fixture.manifestPath, "utf8"));
  const target = join(fixture.root, "elsewhere.css");
  const expected = manifest.assets.find((asset) => asset.path === "workbench/styles.css");
  // Point the link at content that would otherwise satisfy the digest, so the
  // rejection cannot be mistaken for an ordinary content mismatch.
  await writeFile(target, "body{color:#111}");
  await rm(join(fixture.site, "workbench/styles.css"));
  await symlink(target, join(fixture.site, "workbench/styles.css"));
  const [problem] = await verifyAssetContents(fixture.site, manifest.assets);
  assert.deepEqual(problem, { path: "workbench/styles.css", problem: "unsupported_symlink" });
  assert.equal(sha256(Buffer.from("body{color:#111}")), expected.sha256);
});

// --- B. fresh isolated output and conflict handling -------------------------

test("a stale destination file cannot survive assembly and cannot be reported deployable", async () => {
  const fixture = await buildBaseline();
  const output = join(fixture.root, "out", "index.html");
  await writeFixture(join(fixture.root, "out"), "workbench/app.js", "STALE-PREVIOUS-BUILD");
  const result = await runCli(productionArgs(fixture, output, ["--require-complete-bundle"]));
  assert.notEqual(result.code, 0, "the CLI must exit nonzero for a conflicting destination");
  assert.match(result.stderr, /non-empty output directory/);
  assert.doesNotMatch(result.stdout, /"deployable_to_carbonwebsite": true/);
  // The pre-existing directory is refused, never silently deleted.
  assert.equal(await readFile(join(fixture.root, "out", "workbench/app.js"), "utf8"), "STALE-PREVIOUS-BUILD");
});

test("a fresh output directory assembles the baseline bytes rather than inheriting them", async () => {
  const fixture = await buildBaseline();
  const output = join(fixture.root, "fresh", "index.html");
  const result = await runCli(productionArgs(fixture, output, ["--require-complete-bundle"]));
  assert.equal(result.code, 0, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.deployable_to_carbonwebsite, true);
  assert.equal(await readFile(join(fixture.root, "fresh", "workbench/app.js"), "utf8"), "export const app = 'real';");
  // The staged bytes on disk are the identity the tool reported.
  assert.equal(bundleIdentity(await inventoryDirectory(join(fixture.root, "fresh"))), report.bundle_identity_sha256);
});

test("a failed build leaves no partial bundle behind", async () => {
  const fixture = await buildBaseline();
  await writeFile(join(fixture.site, "workbench/atlas-source.json"), "corrupted");
  const output = join(fixture.root, "aborted", "index.html");
  const result = await runCli(productionArgs(fixture, output, ["--require-complete-bundle"]));
  assert.notEqual(result.code, 0);
  await assert.rejects(readFile(output), /ENOENT/);
});

// --- C. inventory completeness ---------------------------------------------

test("a legitimate baseline asset outside the old hard-coded list survives the bundle", async () => {
  // Regression for the live `workbench/atlas-source.json`, which the previous
  // fixed REQUIRED_PRODUCTION_PATHS list omitted: a bundle built without it
  // would have withdrawn it from production while reporting readiness.
  const fixture = await buildBaseline({ extra: ["workbench/extra-data.json", '{"extra":true}'] });
  const output = join(fixture.root, "fresh", "index.html");
  const result = await runCli(productionArgs(fixture, output, ["--require-complete-bundle"]));
  assert.equal(result.code, 0, result.stderr);
  assert.equal(await readFile(join(fixture.root, "fresh", "workbench/extra-data.json"), "utf8"), '{"extra":true}');
  const report = JSON.parse(result.stdout);
  assert.ok(report.staged_inventory.some((entry) => entry.path === "workbench/extra-data.json"));
});

test("a complete verified baseline is preserved byte-for-byte except the replaced homepage", async () => {
  const fixture = await buildBaseline();
  const output = join(fixture.root, "fresh", "index.html");
  const result = await runCli(productionArgs(fixture, output, ["--require-complete-bundle"]));
  assert.equal(result.code, 0, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.baseline_assets_preserved, true);
  for (const asset of fixture.assets) {
    const staged = report.staged_inventory.find((entry) => entry.path === asset.path);
    assert.ok(staged, `${asset.path} must be staged`);
    if (asset.path === "index.html") {
      assert.notEqual(staged.sha256, asset.sha256, "index.html must be the integrated homepage");
      assert.equal(staged.sha256, report.output_sha256);
    } else {
      assert.equal(staged.sha256, asset.sha256, `${asset.path} must survive unchanged`);
    }
  }
});

test("an unenumerated inventory refuses certification even when every known asset verifies", async () => {
  const fixture = await buildBaseline({ complete: false });
  const output = join(fixture.root, "fresh", "index.html");
  const result = await runCli(productionArgs(fixture, output, ["--require-complete-bundle"]));
  assert.notEqual(result.code, 0);
  assert.match(result.stderr, /incomplete/);
  assert.doesNotMatch(result.stdout, /"deployable_to_carbonwebsite": true/);
});

test("the shipped baseline manifest is a complete, self-consistent inventory of the redesigned site", async () => {
  const manifest = await loadBaselineManifest();
  assert.equal(manifest.inventory_complete, true);
  assert.equal(manifest.inventory_status, "verified-complete");
  assert.ok(manifest.inventory_status_reason.length > 0);
  // Every path in the regression floor is covered.
  for (const path of REQUIRED_PRODUCTION_PATHS) {
    assert.ok(manifest.assets.some((asset) => asset.path === path), `${path} must be in the baseline manifest`);
  }
  assert.ok(manifest.assets.some((asset) => asset.path === "workbench/atlas-source.json"));
  // The retired ChatGPT-era homepage images must not be resurrected.
  assert.ok(!manifest.assets.some((asset) => asset.path.startsWith("assets/carbon-")));
  // No entry may be an empty file: /index.html 307-redirects to /, so a naive
  // download of the listed paths yields a zero-byte homepage.
  assert.ok(manifest.assets.every((asset) => asset.bytes > 0));
  // The upload archive is the provenance and must match the entry count.
  assert.equal(manifest.upload_archive.file_count, manifest.assets.length);
  assert.match(manifest.upload_archive.sha256, /^[0-9a-f]{64}$/);
  // The reviewed homepage source pin in the manifest is the entry the bundle replaces.
  const index = manifest.assets.find((asset) => asset.path === "index.html");
  assert.equal(manifest.homepage_source_authority.reviewed_source_index_sha256, index.sha256);
  assert.equal(manifest.homepage_source_authority.reconciliation_required, false);
  // The change set against the previous live version is explicit and additive-free.
  assert.deepEqual(manifest.changes_since_previous_live.added_paths, []);
  assert.deepEqual(manifest.changes_since_previous_live.removed_paths, []);
  assert.ok(manifest.changes_since_previous_live.changed_paths.includes("index.html"));
  // The routing configuration explains the redirect trap.
  assert.equal(manifest.routing_configuration.html_handling, "auto-trailing-slash");
  assert.equal(manifest.routing_configuration.authoritative, true);
  assert.match(manifest.routing_configuration.implication, /307/);
  // The rollback target is either a captured version id or the explicit
  // capture marker; the tool refuses certification on the marker.
  const target = manifest.deployment_target_observed.live_version_id;
  assert.ok(/^[0-9a-f-]{36}$/.test(target) || target === "CAPTURE_BEFORE_DEPLOY");
  assert.notEqual(target, "5a44ab03-ce7c-4100-ae42-71843b07246a", "the 2026-09-12 version was superseded on 2026-09-22");
});

test("a complete baseline without a captured rollback target refuses certification", async () => {
  const fixture = await buildBaseline({ rollback: "CAPTURE_BEFORE_DEPLOY" });
  const output = join(fixture.root, "fresh", "index.html");
  const result = await runCli(productionArgs(fixture, output, ["--require-complete-bundle"]));
  assert.notEqual(result.code, 0);
  assert.match(result.stderr, /rollback target/);
  await assert.rejects(readFile(output), /ENOENT/);
});

// --- completeness is not authorization --------------------------------------

test("a staging preview never carries production authorization", async () => {
  const fixture = await buildBaseline();
  const output = join(fixture.root, "preview", "index.html");
  const result = await runCli(productionArgs(fixture, output, ["--staging-preview"]));
  assert.equal(result.code, 0, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.preview_only, true);
  assert.equal(report.deployable_to_carbonwebsite, false);
  assert.equal(report.release_authorized, false);
});

test("a changed-source override cannot certify a production bundle", async () => {
  const fixture = await buildBaseline();
  const output = join(fixture.root, "changed", "index.html");
  const result = await runCli([
    "--input", fixture.input,
    "--output", output,
    "--existing-site", fixture.site,
    "--baseline-manifest", fixture.manifestPath,
    "--allow-changed-source",
    "--require-complete-bundle",
  ]);
  assert.notEqual(result.code, 0);
  assert.match(result.stderr, /never carry production authorization/);
});

test("even a fully deployable bundle does not report release authorization", async () => {
  const fixture = await buildBaseline();
  const output = join(fixture.root, "fresh", "index.html");
  const result = await runCli(productionArgs(fixture, output, ["--require-complete-bundle"]));
  assert.equal(result.code, 0, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.deployable_to_carbonwebsite, true);
  assert.equal(report.release_authorized, false);
  assert.match(report.release_authorization_note, /not release authorization/i);
});

// --- exit status at the real process boundary -------------------------------

test("rejection exit status is observed at the child-process boundary", async () => {
  const fixture = await buildBaseline();
  await rm(join(fixture.site, "workbench/atlas.js"));
  const output = join(fixture.root, "fresh", "index.html");
  const result = await runCli(productionArgs(fixture, output, ["--require-complete-bundle"]));
  assert.equal(result.code, 1, "a rejected build must exit 1, not merely print a warning");
  assert.match(result.stderr, /workbench\/atlas\.js: missing/);
  assert.equal(result.stdout, "", "a rejected build must not emit a success report");
});

test("a build that fails verification emits no deployment-ready result at all", async () => {
  const fixture = await buildBaseline();
  await writeFile(join(fixture.site, "workbench/engine.js"), "tampered");
  const output = join(fixture.root, "fresh", "index.html");
  const result = await runCli(productionArgs(fixture, output, ["--require-complete-bundle"]));
  assert.notEqual(result.code, 0);
  assert.doesNotMatch(result.stdout, /deployable_to_carbonwebsite/);
  assert.doesNotMatch(result.stdout, /"release_authorized"/);
});

// --- release record vs the bytes it claims to describe ----------------------

test("the release candidate's recorded asset digests match the files actually shipped", async () => {
  // Regression: candidate 2026-09-22.1 was authored by carrying static_integration
  // over from 2026-09-18.2, which left pilot_html_sha256 pointing at a revision
  // superseded on 2026-09-21 by f9635e0b. A recorded digest that no longer
  // matches the file on disk describes a bundle nobody is building.
  const candidate = JSON.parse(await readFile(new URL("../PUBLIC_RELEASE_CANDIDATE.json", import.meta.url), "utf8"));
  const recorded = candidate.static_integration;
  const sources = [
    ["component_css_sha256", new URL("../public/ask-carbon.css", import.meta.url)],
    ["component_js_sha256", new URL("../public/ask-carbon.js", import.meta.url)],
    ["release_contract_sha256", new URL("../public/release-contract.js", import.meta.url)],
    ["pilot_html_sha256", new URL("../../../Business/Carbon_Fit/workbench/Carbon_Client_Pilot_Designer_Preview.html", import.meta.url)],
  ];
  for (const [key, url] of sources) {
    const actual = sha256(await readFile(url));
    assert.equal(recorded[key], actual, `${key} must equal the digest of the file it names`);
  }
  // The reviewed homepage pin must be the source the bundle is actually built from.
  assert.match(recorded.integrated_index_sha256, /^[0-9a-f]{64}$/);
  assert.match(recorded.bundle_identity_sha256, /^[0-9a-f]{64}$/);
});
