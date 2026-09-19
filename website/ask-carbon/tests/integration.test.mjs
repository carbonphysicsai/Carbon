import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { REQUIRED_PRODUCTION_PATHS, integrateHtml, missingProductionPaths, reconcileOwnerUploadedHomepage } from "../tools/integrate-static.mjs";
import { buildCsp } from "../tools/csp-report.mjs";
import { validateKnowledge } from "../tools/validate-knowledge.mjs";
import knowledge from "../knowledge/public-knowledge.v1.json" with { type: "json" };

test("static integration preserves existing content and routes", () => {
  const input = "<!doctype html><html><head><title>Existing Carbon</title></head><body><main id=home>Keep me</main><a href=\"/workbench/\">Workbench</a></body></html>";
  const output = integrateHtml(input, { assetPrefix: "./ask-carbon" });
  assert.match(output, /<main id=home>Keep me<\/main>/);
  assert.match(output, /href="\/workbench\/"/);
  assert.match(output, /<ask-carbon/);
  assert.match(output, /pilot-url="\.\/ask-carbon\/pilot-designer\.html"/);
  assert.doesNotMatch(output, /staging-preview/);
  assert.match(output, /ask-carbon\.js/);
  assert.throws(() => integrateHtml(output), /already integrated/);
  assert.throws(() => integrateHtml(input, { assetPrefix: "../../escape" }), /bounded relative/);
});

test("static integration can point a staging fixture at an unavailable knowledge route", () => {
  const output = integrateHtml("<html><head></head><body></body></html>", { knowledgeUrl: "/missing-knowledge.json", pilotUrl: "/pilot", stagingPreview: true });
  assert.match(output, /knowledge-url="\/missing-knowledge\.json"/);
  assert.match(output, /pilot-url="\/pilot"/);
  assert.match(output, /staging-preview/);
});

test("owner-upload reconciliation restores only the existing Workbench navigation delta", () => {
  const input = [
    "<html><head><style>",
    "/* Preserve the supplied Global Intelligence banner composition at every width. */",
    ".network-flow-art img{height:auto;object-fit:contain;object-position:center}",
    "</style></head><body>",
    '<nav id="main-nav" aria-label="Main"><a href="#company">Company</a></nav>',
    '<footer><nav aria-label="Footer"><a href="#faq">FAQ</a></nav></footer>',
    "</body></html>",
  ].join("\n");
  const output = reconcileOwnerUploadedHomepage(input);
  assert.match(output, /Workbench navigation: allow the existing links to wrap on tablets/);
  assert.equal(output.match(/href="\/workbench\/"/g)?.length, 2);
  assert.match(output, /<a href="#company">Company<\/a><a href="\/workbench\/">Workbench<\/a><\/nav>/);
  assert.match(output, /<a href="#faq">FAQ<\/a><a href="\/workbench\/">Workbench<\/a><\/nav>/);
  assert.throws(() => reconcileOwnerUploadedHomepage(output), /expected exactly one/);
});

test("CSP generation hashes existing inline code without unsafe-inline", () => {
  const html = "<!doctype html><html><head><style>body{color:#121212}</style></head><body><script>document.body.dataset.ready='yes'</script></body></html>";
  const result = buildCsp(html);
  assert.equal(result.inline_style_hashes.length, 1);
  assert.equal(result.inline_script_hashes.length, 1);
  assert.match(result.policy, /script-src 'self' 'sha256-/);
  assert.match(result.policy, /style-src 'self' 'sha256-/);
  assert.doesNotMatch(result.policy, /unsafe-inline/);
  assert.throws(() => buildCsp("<button onclick=\"alert(1)\">Bad</button>"), /Inline event handlers/);
});

test("reviewed knowledge is staging-valid but deliberately not production releasable", async () => {
  const preview = await validateKnowledge(knowledge, { mode: "staging", now: new Date("2026-09-16T00:00:00Z") });
  assert.equal(preview.valid, true);
  assert.equal(preview.card_count, knowledge.cards.length);
  assert.ok(knowledge.cards.some((card) => card.id === "population-training-separation"));
  assert.equal(preview.source_checks.filter((check) => check.matched).length, 9);
  const production = await validateKnowledge(knowledge, { mode: "production", now: new Date("2026-09-16T00:00:00Z") });
  assert.equal(production.valid, false);
  assert.ok(production.errors.includes("release_not_approved_public"));
  assert.ok(production.errors.includes("public_activation_not_allowed"));
});

test("knowledge validation rejects answer cards without a reviewed server-owned evidence basis", async () => {
  const missingBasis = structuredClone(knowledge);
  missingBasis.cards[0].passages = [];
  const result = await validateKnowledge(missingBasis, {
    mode: "staging",
    now: new Date("2026-09-18T00:00:00Z"),
    checkSourceBytes: false,
  });
  assert.equal(result.valid, false);
  assert.ok(result.errors.includes(`missing_answer_basis:${missingBasis.cards[0].id}`));
});

test("production candidate is inactive, path-bounded, and excludes staging Basic auth", async () => {
  const config = await readFile(new URL("../wrangler.public-release-candidate.toml", import.meta.url), "utf8");
  assert.match(config, /ASK_CARBON_ACTIVATION = "disabled"/);
  assert.match(config, /ASK_CARBON_RUNTIME_MODE = "production"/);
  assert.match(config, /ASK_CARBON_STAGING_ACCESS_MODE = "none"/);
  assert.doesNotMatch(config, /ASK_CARBON_STAGING_ACCESS_MODE = "http_basic_v1"/);
  assert.match(config, /pattern = "carbonphysics\.ai\/api\/ask-carbon\*"/);
  assert.match(config, /pattern = "www\.carbonphysics\.ai\/api\/ask-carbon\*"/);
  assert.match(config, /script_name = "ask-carbon-budget-authority"/);
  assert.match(config, /ASK_CARBON_MONTHLY_LIMIT_MICRO_USD = "50000000"/);
});

test("the required production path set covers the Workbench route and shared homepage assets", () => {
  // Regression: a carbonwebsite deployment replaces the entire asset set, so a
  // bundle containing only the integrated homepage would withdraw /workbench/
  // and the shared /assets images from production.
  assert.ok(REQUIRED_PRODUCTION_PATHS.includes("index.html"));
  assert.ok(REQUIRED_PRODUCTION_PATHS.includes("workbench/index.html"));
  assert.ok(REQUIRED_PRODUCTION_PATHS.includes("workbench/app.js"));
  assert.ok(REQUIRED_PRODUCTION_PATHS.includes("workbench/styles.css"));
  assert.ok(REQUIRED_PRODUCTION_PATHS.includes("assets/carbon-66e3549179d4.png"));
  assert.ok(REQUIRED_PRODUCTION_PATHS.includes("assets/carbon-f7ea9506b7b9.png"));
  assert.ok(REQUIRED_PRODUCTION_PATHS.every((path) => !path.startsWith("/") && !path.includes("..")));
  assert.equal(new Set(REQUIRED_PRODUCTION_PATHS).size, REQUIRED_PRODUCTION_PATHS.length);
});

test("an Ask-Carbon-only bundle is reported as an incomplete production asset set", async () => {
  const present = new Set(["/bundle/index.html", "/bundle/ask-carbon/ask-carbon.js"]);
  const missing = await missingProductionPaths("/bundle", async (path) => present.has(path.split("\\").join("/")));
  assert.ok(missing.includes("workbench/index.html"));
  assert.ok(missing.includes("workbench/app.js"));
  assert.ok(missing.includes("assets/carbon-66e3549179d4.png"));
  assert.ok(!missing.includes("index.html"));
});

test("a complete current-site copy plus the integrated homepage reports no missing production path", async () => {
  const present = new Set(REQUIRED_PRODUCTION_PATHS.map((path) => `/bundle/${path}`));
  const missing = await missingProductionPaths("/bundle", async (path) => present.has(path.split("\\").join("/")));
  assert.deepEqual(missing, []);
});
