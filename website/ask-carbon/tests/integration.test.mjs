import test from "node:test";
import assert from "node:assert/strict";
import { integrateHtml } from "../tools/integrate-static.mjs";
import { buildCsp } from "../tools/csp-report.mjs";
import { validateKnowledge } from "../tools/validate-knowledge.mjs";
import knowledge from "../knowledge/public-knowledge.v1.json" with { type: "json" };

test("static integration preserves existing content and routes", () => {
  const input = "<!doctype html><html><head><title>Existing Carbon</title></head><body><main id=home>Keep me</main><a href=\"/workbench/\">Workbench</a></body></html>";
  const output = integrateHtml(input, { assetPrefix: "./ask-carbon" });
  assert.match(output, /<main id=home>Keep me<\/main>/);
  assert.match(output, /href="\/workbench\/"/);
  assert.match(output, /<ask-carbon/);
  assert.match(output, /ask-carbon\.js/);
  assert.throws(() => integrateHtml(output), /already integrated/);
  assert.throws(() => integrateHtml(input, { assetPrefix: "../../escape" }), /bounded relative/);
});

test("static integration can point a staging fixture at an unavailable knowledge route", () => {
  const output = integrateHtml("<html><head></head><body></body></html>", { knowledgeUrl: "/missing-knowledge.json" });
  assert.match(output, /knowledge-url="\/missing-knowledge\.json"/);
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

test("preview knowledge is internally valid but deliberately not production releasable", () => {
  const preview = validateKnowledge(knowledge);
  assert.equal(preview.valid, true);
  assert.ok(preview.warnings.includes("31_candidate_cards_not_received_or_reviewed"));
  const production = validateKnowledge(knowledge, { production: true, now: new Date("2026-09-16T00:00:00Z") });
  assert.equal(production.valid, false);
  assert.ok(production.errors.includes("knowledge_not_approved_for_production"));
  assert.ok(production.errors.includes("candidate_card_review_incomplete"));
});
