import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { REQUIRED_PRODUCTION_PATHS, integrateHtml, reconcileOwnerUploadedHomepage } from "../tools/integrate-static.mjs";
import { buildCsp } from "../tools/csp-report.mjs";
import { validateKnowledge } from "../tools/validate-knowledge.mjs";
import knowledge from "../knowledge/public-knowledge.v1.json" with { type: "json" };
import { activationStatus } from "../worker/core.mjs";

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

test("reviewed knowledge is approved for public display and production releasable", async () => {
  const preview = await validateKnowledge(knowledge, { mode: "staging", now: new Date("2026-09-16T00:00:00Z") });
  assert.equal(preview.valid, true);
  assert.equal(preview.card_count, knowledge.cards.length);
  assert.ok(knowledge.cards.some((card) => card.id === "population-training-separation"));
  assert.equal(preview.source_checks.filter((check) => check.matched).length, 9);
  // Approved for public display on 2026-09-22 under WEB-QA-07-D1. The card and
  // source content is unchanged from the staging-reviewed set; only the
  // release approval status changed, so the version pin stays valid.
  assert.equal(knowledge.release.status, "APPROVED_PUBLIC");
  assert.equal(knowledge.release.public_activation_allowed, true);
  assert.equal(knowledge.knowledge_version, "ask-carbon-release-candidate-2026-09-18.2");
  const production = await validateKnowledge(knowledge, { mode: "production", now: new Date("2026-09-16T00:00:00Z") });
  assert.equal(production.valid, true);
});

test("content approval alone does not serve answers: the worker activation flag is separate", async () => {
  // Three gates must agree before a visitor gets an answer. Two are in the
  // knowledge release record above; the third is the Worker's own flag, and
  // the committed release-candidate config must keep it disabled so that
  // redeploying that config stays the fail-closed incident response.
  const candidate = await readFile(new URL("../wrangler.public-release-candidate.toml", import.meta.url), "utf8");
  assert.match(candidate, /ASK_CARBON_ACTIVATION = "disabled"/);
  const active = await readFile(new URL("../wrangler.public-release-active.toml", import.meta.url), "utf8");
  assert.match(active, /ASK_CARBON_ACTIVATION = "enabled"/);
  // The two configs must not drift apart in anything except that one flag.
  const strip = (text) => text.split("\n").filter((line) => !line.trimStart().startsWith("#")).join("\n").replace(/ASK_CARBON_ACTIVATION = "(disabled|enabled)"/, "ASK_CARBON_ACTIVATION = <flag>").trim();
  assert.equal(strip(candidate), strip(active), "the activated config must differ from the candidate only in ASK_CARBON_ACTIVATION");
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
  assert.ok(REQUIRED_PRODUCTION_PATHS.includes("site.css"));
  assert.ok(REQUIRED_PRODUCTION_PATHS.includes("customers/index.html"));
  assert.ok(REQUIRED_PRODUCTION_PATHS.includes("assets/neue-0.otf"));
  assert.ok(REQUIRED_PRODUCTION_PATHS.includes("workbench/atlas-source.json"));
  // The ChatGPT-era homepage images were retired with the 2026-09-22 redesign.
  assert.ok(!REQUIRED_PRODUCTION_PATHS.includes("assets/carbon-66e3549179d4.png"));
  assert.ok(REQUIRED_PRODUCTION_PATHS.every((path) => !path.startsWith("/") && !path.includes("..")));
  assert.equal(new Set(REQUIRED_PRODUCTION_PATHS).size, REQUIRED_PRODUCTION_PATHS.length);
});

// Bundle-guard behaviour is covered in bundle-guard.test.mjs, which exercises
// real temporary files and real CLI child processes. The injected-probe tests
// that used to live here could not observe empty files, wrong content,
// directories at file paths, symlinks, or stale destination content.

test("the committed production config pairs its provider with that provider's notice posture", async () => {
  const active = await readFile(new URL("../wrangler.public-release-active.toml", import.meta.url), "utf8");
  const vars = Object.fromEntries([...active.split("[vars]")[1].matchAll(/^(ASK_CARBON_[A-Z_]+) = "([^"]*)"$/gm)].map((match) => [match[1], match[2]]));
  assert.equal(vars.ASK_CARBON_MODEL_CONFIG_ID, "gemma-4-31b-turbo-tee:v1");
  const env = {
    ...vars,
    ASK_CARBON_CHUTES_API_KEY: "test-chutes-key",
    ASK_CARBON_CONTINUATION_SIGNING_SECRET: "test-signing-secret",
    ASK_CARBON_USAGE_LEDGER: { idFromName: () => "id", get: () => ({}) },
    ASK_CARBON_EDGE_RATE_LIMITER: { limit: async () => ({ success: true }) },
  };
  const now = new Date("2026-09-26T12:00:00Z");
  const status = activationStatus(env, knowledge, now);
  assert.equal(status.reasons.includes("public_privacy_not_accepted"), false, JSON.stringify(status.reasons));
  assert.equal(status.reasons.includes("missing_ask_carbon_chutes_api_key"), false);
  // Specimens: the same config under the retired OpenAI notice posture is refused,
  // and so is the retired OpenAI profile under the Chutes posture.
  assert.ok(activationStatus({ ...env, ASK_CARBON_PRIVACY_MODE: "approved_public_privacy_v1" }, knowledge, now).reasons.includes("public_privacy_not_accepted"));
  assert.ok(activationStatus({ ...env, ASK_CARBON_MODEL_CONFIG_ID: "gpt-5.6-luna:low:v1", ASK_CARBON_APPROVED_MODEL_CONFIGS: "gpt-5.6-luna:low:v1", ASK_CARBON_OPENAI_API_KEY: "k" }, knowledge, now).reasons.includes("public_privacy_not_accepted"));
  // Without the Chutes secret the production config cannot activate.
  const { ASK_CARBON_CHUTES_API_KEY: _omitted, ...withoutSecret } = env;
  assert.ok(activationStatus(withoutSecret, knowledge, now).reasons.includes("missing_ask_carbon_chutes_api_key"));
});
