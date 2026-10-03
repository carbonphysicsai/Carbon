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
  HOMEPAGE_EDITS,
  PILOT_DESIGNER,
  REQUIRED_PRODUCTION_PATHS,
  applyHomepageEdit,
  bundleIdentity,
  inventoryDirectory,
  loadBaselineManifest,
  loadSiteAdditions,
  loadSiteReplacements,
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
const buildBaseline = async ({ complete = true, extra = null, rollback = "0f1e2d3c-4b5a-4978-8765-43210fedcba9", deployedAfter = null } = {}) => {
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
    deployment_target_observed: {
      worker: "carbonwebsite",
      live_version_id: rollback,
      ...(deployedAfter ? { deployed_after_capture: { version_id: deployedAfter } } : {}),
    },
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
  // The upload archive is the provenance: the site entries plus the Ask Carbon
  // assets the integration tool supplies, which are never baseline entries.
  assert.equal(manifest.upload_archive.site_file_count, manifest.assets.length);
  assert.equal(manifest.upload_archive.file_count, manifest.assets.length + manifest.upload_archive.ask_carbon_files.length);
  assert.ok(manifest.upload_archive.ask_carbon_files.every((path) => path.startsWith("ask-carbon/")));
  assert.ok(!manifest.assets.some((asset) => asset.path.startsWith("ask-carbon/")));
  assert.match(manifest.upload_archive.sha256, /^[0-9a-f]{64}$/);
  // The reviewed homepage source pin in the manifest is the entry the bundle replaces.
  const index = manifest.assets.find((asset) => asset.path === "index.html");
  assert.equal(manifest.homepage_source_authority.reviewed_source_index_sha256, index.sha256);
  assert.equal(manifest.homepage_source_authority.reconciliation_required, false);
  // Every entry states why it changed since the previous baseline, and the
  // change set agrees with those reasons: a baseline that changes without a
  // recorded reason is not a baseline.
  const reasonOf = (path) => manifest.assets.find((asset) => asset.path === path)?.change_since_previous_manifest ?? "";
  assert.ok(manifest.assets.every((asset) => /^(UNCHANGED|CHANGED|ADDED)\b/.test(asset.change_since_previous_manifest ?? "")));
  const { changed_paths: changed, added_paths: added, removed_paths: removed } = manifest.changes_since_previous_live;
  assert.ok(changed.length > 0 && changed.every((path) => reasonOf(path).startsWith("CHANGED")));
  assert.ok(added.every((path) => reasonOf(path).startsWith("ADDED")));
  assert.equal(manifest.assets.filter((asset) => /^(CHANGED|ADDED)/.test(asset.change_since_previous_manifest)).length, changed.length + added.length);
  // The manifest it supersedes is named, and the change counts agree.
  assert.equal(manifest.supersedes.manifest_version, manifest.manifest_version - 1);
  assert.equal(manifest.supersedes.counts.changed, changed.length);
  assert.equal(manifest.supersedes.counts.added, added.length);
  assert.equal(manifest.supersedes.counts.removed, removed.length);
  // Removed paths are gone from the inventory and each carries its own reason.
  for (const path of removed) {
    assert.ok(!manifest.assets.some((asset) => asset.path === path), `${path} was removed and must not be an entry`);
    assert.match(manifest.removed_since_previous.find((entry) => entry.path === path)?.reason ?? "", /^REMOVED\b/);
  }
  // Specimen: the same reason check does fail on an entry that lacks a reason.
  assert.equal(/^(UNCHANGED|CHANGED|ADDED)\b/.test(""), false);
  // The routing configuration explains the redirect trap.
  assert.equal(manifest.routing_configuration.html_handling, "auto-trailing-slash");
  assert.equal(manifest.routing_configuration.authoritative, true);
  assert.match(manifest.routing_configuration.implication, /307/);
  // The rollback target is either a captured version id or the explicit
  // capture marker; the tool refuses certification on the marker.
  const target = manifest.deployment_target_observed.live_version_id;
  assert.ok(/^[0-9a-f-]{36}$/.test(target) || target === "CAPTURE_BEFORE_DEPLOY");
  assert.notEqual(target, "5a44ab03-ce7c-4100-ae42-71843b07246a", "the 2026-09-12 version was superseded on 2026-09-22");
  // A deployment recorded after the capture must be a different version; the
  // tool then refuses to reuse the capture as the next rollback target.
  const after = manifest.deployment_target_observed.deployed_after_capture;
  if (after) {
    assert.match(after.version_id, /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/);
    assert.notEqual(after.version_id, target);
  }
});

test("a complete baseline without a captured rollback target refuses certification", async () => {
  const fixture = await buildBaseline({ rollback: "CAPTURE_BEFORE_DEPLOY" });
  const output = join(fixture.root, "fresh", "index.html");
  const result = await runCli(productionArgs(fixture, output, ["--require-complete-bundle"]));
  assert.notEqual(result.code, 0);
  assert.match(result.stderr, /rollback target/);
  await assert.rejects(readFile(output), /ENOENT/);
});

test("a rollback target captured before a later deployment refuses certification", async () => {
  const fixture = await buildBaseline({ deployedAfter: "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d" });
  const output = join(fixture.root, "fresh", "index.html");
  const result = await runCli(productionArgs(fixture, output, ["--require-complete-bundle"]));
  assert.notEqual(result.code, 0);
  assert.match(result.stderr, /captured before deployment 1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d/);
  await assert.rejects(readFile(output), /ENOENT/);
  // Specimen: the identical baseline without the later deployment certifies.
  const control = await buildBaseline();
  const controlOutput = join(control.root, "fresh", "index.html");
  const passed = await runCli(productionArgs(control, controlOutput, ["--require-complete-bundle"]));
  assert.equal(passed.code, 0, passed.stderr);
  assert.equal(JSON.parse(passed.stdout).deployable_to_carbonwebsite, true);
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
    ["pilot_html_sha256", new URL("../release/pilot-designer.html", import.meta.url)],
  ];
  for (const [key, url] of sources) {
    const actual = sha256(await readFile(url));
    assert.equal(recorded[key], actual, `${key} must equal the digest of the file it names`);
  }
  // The reviewed homepage pin must be the source the bundle is actually built from.
  assert.match(recorded.integrated_index_sha256, /^[0-9a-f]{64}$/);
  assert.match(recorded.bundle_identity_sha256, /^[0-9a-f]{64}$/);
});

test("the shipped Pilot Designer is the release's own snapshot, never the Workbench's working copy", () => {
  // ASK-CARBON-PILOT-SNAPSHOT-01: a Workbench rebuild (for example a relayed
  // readiness record) must not change a certified bundle. The integrator reads
  // the committed snapshot inside this tree; refreshing it is a release step.
  const tree = fileURLToPath(new URL("..", import.meta.url));
  assert.equal(PILOT_DESIGNER, join(tree, "release", "pilot-designer.html"));
  assert.ok(!PILOT_DESIGNER.includes(`${"Business"}/`), PILOT_DESIGNER);
});

// --- declared site replacements ---------------------------------------------

const withReplacement = async (fixture, { path = "workbench/index.html", contents = "<html><body>moved</body></html>", declaredSha = null, source = "site/replacement.html" } = {}) => {
  await writeFixture(fixture.root, "site/replacement.html", contents);
  const file = join(fixture.root, "site-replacements.json");
  await writeFile(file, JSON.stringify({ replacements: [{ path, source, sha256: declaredSha ?? sha256(Buffer.from(contents)), reason: "fixture: retired page" }] }));
  return file;
};

test("a declared replacement is published in place of its baseline path, and everything else is preserved", async () => {
  const fixture = await buildBaseline();
  const replacements = await withReplacement(fixture);
  const output = join(fixture.root, "fresh", "index.html");
  const result = await runCli(productionArgs(fixture, output, ["--site-replacements", replacements, "--require-complete-bundle"]));
  assert.equal(result.code, 0, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.deployable_to_carbonwebsite, true);
  assert.deepEqual(report.site_replacements.map((item) => item.path), ["workbench/index.html"]);
  assert.equal(await readFile(join(fixture.root, "fresh", "workbench/index.html"), "utf8"), "<html><body>moved</body></html>");
  for (const asset of fixture.assets.filter((item) => !["index.html", "workbench/index.html"].includes(item.path))) {
    assert.equal(sha256(await readFile(join(fixture.root, "fresh", asset.path))), asset.sha256, asset.path);
  }
  // Specimen: without the declaration the same build publishes the baseline page.
  const plainOutput = join(fixture.root, "plain", "index.html");
  const plain = await runCli(productionArgs(fixture, plainOutput, ["--require-complete-bundle"]));
  assert.equal(plain.code, 0, plain.stderr);
  assert.equal(await readFile(join(fixture.root, "plain", "workbench/index.html"), "utf8"), "<html><head></head><body>workbench</body></html>");
});

test("a replacement whose bytes differ from its declared digest refuses and writes nothing", async () => {
  const fixture = await buildBaseline();
  const replacements = await withReplacement(fixture, { declaredSha: "0".repeat(64) });
  const output = join(fixture.root, "fresh", "index.html");
  const result = await runCli(productionArgs(fixture, output, ["--site-replacements", replacements, "--require-complete-bundle"]));
  assert.notEqual(result.code, 0);
  assert.match(result.stderr, /not the declared 0{64}/);
  await assert.rejects(readFile(output), /ENOENT/);
});

test("a replacement cannot add a path, touch the homepage or the Ask Carbon assets, or read outside its directory", async () => {
  for (const [options, message] of [
    [{ path: "workbench/new-page.html" }, /cannot add a path/],
    [{ path: "index.html" }, /integrated homepage or the Ask Carbon assets/],
    [{ source: "../outside.html" }, /must be inside/],
  ]) {
    const fixture = await buildBaseline();
    await writeFixture(fixture.root, "../outside.html", "x");
    const replacements = await withReplacement(fixture, options);
    const output = join(fixture.root, "fresh", "index.html");
    const result = await runCli(productionArgs(fixture, output, ["--site-replacements", replacements, "--require-complete-bundle"]));
    assert.notEqual(result.code, 0, JSON.stringify(options));
    assert.match(result.stderr, message);
    await assert.rejects(readFile(output), /ENOENT/);
  }
});

// --- declared site additions ------------------------------------------------

const withAddition = async (fixture, { path = "start-mining/index.html", contents = "<html><body>start</body></html>", declaredSha = null, source = "site/addition.html" } = {}) => {
  await writeFixture(fixture.root, "site/addition.html", contents);
  const file = join(fixture.root, "site-additions.json");
  await writeFile(file, JSON.stringify({ additions: [{ path, source, sha256: declaredSha ?? sha256(Buffer.from(contents)), reason: "fixture: new page" }] }));
  return file;
};

test("a declared addition is published at its new path, and every baseline asset is preserved", async () => {
  const fixture = await buildBaseline();
  const additions = await withAddition(fixture);
  const output = join(fixture.root, "fresh", "index.html");
  const result = await runCli(productionArgs(fixture, output, ["--site-additions", additions, "--require-complete-bundle"]));
  assert.equal(result.code, 0, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.deployable_to_carbonwebsite, true);
  assert.deepEqual(report.site_additions.map((item) => item.path), ["start-mining/index.html"]);
  assert.equal(await readFile(join(fixture.root, "fresh", "start-mining/index.html"), "utf8"), "<html><body>start</body></html>");
  for (const asset of fixture.assets.filter((item) => item.path !== "index.html")) {
    assert.equal(sha256(await readFile(join(fixture.root, "fresh", asset.path))), asset.sha256, asset.path);
  }
  // Specimen: without the declaration the path is not published.
  const plainOutput = join(fixture.root, "plain", "index.html");
  const plain = await runCli(productionArgs(fixture, plainOutput, ["--require-complete-bundle"]));
  assert.equal(plain.code, 0, plain.stderr);
  await assert.rejects(readFile(join(fixture.root, "plain", "start-mining/index.html")), /ENOENT/);
});

test("an addition cannot replace a baseline path, the homepage or the Ask Carbon assets, escape its directory, or carry other bytes", async () => {
  for (const [options, message] of [
    [{ path: "miners/index.html" }, /cannot replace a path/],
    [{ path: "index.html" }, /cannot replace a path/],
    [{ path: "ask-carbon/extra.js" }, /integrated homepage or the Ask Carbon assets/],
    [{ path: "../escape.html" }, /not a bounded site path/],
    [{ path: "/start-mining/index.html" }, /not a bounded site path/],
    [{ source: "../outside.html" }, /must be inside/],
    [{ declaredSha: "0".repeat(64) }, /not the declared 0{64}/],
  ]) {
    const fixture = await buildBaseline();
    await writeFixture(fixture.root, "../outside.html", "x");
    const additions = await withAddition(fixture, options);
    const output = join(fixture.root, "fresh", "index.html");
    const result = await runCli(productionArgs(fixture, output, ["--site-additions", additions, "--require-complete-bundle"]));
    assert.notEqual(result.code, 0, JSON.stringify(options));
    assert.match(result.stderr, message);
    await assert.rejects(readFile(output), /ENOENT/);
  }
});

test("an addition never overwrites a file the supplied site already has at that path", async () => {
  const fixture = await buildBaseline();
  // A stray file the manifest does not list: the build must stop, not pick one.
  await writeFixture(fixture.site, "start-mining/index.html", "<html><body>stray</body></html>");
  const additions = await withAddition(fixture);
  const output = join(fixture.root, "fresh", "index.html");
  const result = await runCli(productionArgs(fixture, output, ["--site-additions", additions, "--require-complete-bundle"]));
  assert.notEqual(result.code, 0);
  assert.match(result.stderr, /EEXIST/);
  await assert.rejects(readFile(output), /ENOENT/);
});

// --- reviewed homepage edits ------------------------------------------------

const MINERS_CARD = `<article class="audience-card"><p class="eyebrow">Miners</p><a class="text-link" href="/miners/" aria-label="Learn more for miners">Learn more <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-arrow-up-right" aria-hidden="true"><path d="M7 7h10v10"></path><path d="M7 17 17 7"></path></svg></a></article>`;

test("the start-mining homepage edit adds one link after the Miners card's Learn more, and only once", () => {
  const html = `<html><head></head><body>${MINERS_CARD}</body></html>`;
  const edited = applyHomepageEdit(html, "start-mining-link-v1");
  assert.equal(edited.split('href="/start-mining/"').length - 1, 1);
  assert.ok(edited.includes('aria-label="Learn more for miners">Learn more <svg'));
  assert.match(edited, /Learn more <svg[^]*?<\/svg><\/a><a class="text-link" href="\/start-mining\/" style="margin-top:12px">Start mining <svg[^]*?<\/svg><\/a><\/article>/);
  // Applying it again, or to a page without the card, stops the build.
  assert.throws(() => applyHomepageEdit(edited, "start-mining-link-v1"), /expected exactly one Miners card marker/);
  assert.throws(() => applyHomepageEdit("<html><body></body></html>", "start-mining-link-v1"), /expected exactly one Miners card marker/);
  assert.throws(() => applyHomepageEdit(html, "no-such-edit"), /Unknown homepage edit no-such-edit/);
  assert.deepEqual(Object.keys(HOMEPAGE_EDITS), ["start-mining-link-v1"]);
});

test("a homepage edit applies after the source pin, and the report names it and the edited source", async () => {
  const fixture = await buildBaseline();
  const inputHtml = `<html><head><title>Carbon</title></head><body>${MINERS_CARD}</body></html>`;
  await writeFile(fixture.input, inputHtml);
  const output = join(fixture.root, "fresh", "index.html");
  const result = await runCli(productionArgs({ ...fixture, inputSha256: sha256(Buffer.from(inputHtml)) }, output, ["--homepage-edit", "start-mining-link-v1", "--require-complete-bundle"]));
  assert.equal(result.code, 0, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.homepage_edit, "start-mining-link-v1");
  const edited = applyHomepageEdit(inputHtml, "start-mining-link-v1");
  assert.equal(report.edited_homepage_source_sha256, sha256(Buffer.from(edited)));
  assert.match(await readFile(output, "utf8"), /href="\/start-mining\/"/);
  // The pin is still the unedited source: pinning the edited bytes refuses.
  const pinned = await runCli(productionArgs({ ...fixture, inputSha256: sha256(Buffer.from(edited)) }, join(fixture.root, "pinned", "index.html"), ["--homepage-edit", "start-mining-link-v1"]));
  assert.notEqual(pinned.code, 0);
  assert.match(pinned.stderr, /does not match reviewed source/);
});

// --- the shipped declarations ----------------------------------------------

test("the shipped replacements and additions load against the shipped baseline and link the Start mining page", async () => {
  const root = fileURLToPath(new URL("..", import.meta.url));
  const manifest = await loadBaselineManifest();
  const replacements = await loadSiteReplacements(join(root, "site-replacements.json"), manifest);
  const additions = await loadSiteAdditions(join(root, "site-additions.json"), manifest);
  assert.deepEqual(replacements.map((item) => item.path), ["miners/index.html", "sitemap.xml"]);
  assert.deepEqual(additions.map((item) => item.path), ["start-mining/index.html"]);
  const page = additions[0].bytes.toString("utf8");
  assert.match(page, /<title>Start mining · Carbon<\/title>/);
  assert.match(page, /<link rel="canonical" href="https:\/\/carbonphysics.ai\/start-mining\/">/);
  assert.doesNotMatch(page, /get-started|Get started/i);
  // Link-only compute (OWNER-MINER-COMPUTE-LINK-ONLY-01): the page names no provider.
  assert.doesNotMatch(page, /RunPod|Lium|Targon/);
  const miners = replacements[0].bytes.toString("utf8");
  assert.match(miners, /<a class="button" href="\/start-mining\/">Start mining <svg/);
  assert.doesNotMatch(miners, /href="#start">Start a development run/);
  assert.match(replacements[1].bytes.toString("utf8"), /<loc>https:\/\/carbonphysics.ai\/start-mining\/<\/loc>/);
});
