import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { integrateHtml } from "../tools/integrate-static.mjs";
import { fetchBaseline, recoverBaselineBytes, removeAskCarbonIntegration, removeEdgeInjections } from "../tools/fetch-live-baseline.mjs";
import { DEFAULT_CHECKS, healthProblems } from "../tools/verify-publication.mjs";

const sha256 = (value) => createHash("sha256").update(value).digest("hex");
const PAGE = "<!doctype html>\n<html><head>\n<title>x</title>\n</head>\n<body>\n<p>page</p>\n<script>\n(function () { /* site script */ })();\n</script>\n</body>\n</html>\n";
const CHALLENGE = "<script>(function(){function c(){var b=a.contentDocument;}if(document.body){c()}})();</script>";
const BEACON = "<script defer src=\"https://static.cloudflareinsights.com/beacon.min.js/v1\" data-cf-beacon='{\"token\":\"t\"}' crossorigin=\"anonymous\"></script>\n";
const injected = (html) => html.replace("</body>", `${CHALLENGE}${BEACON}</body>`);

test("edge injections are removed and nothing else is", () => {
  assert.equal(removeEdgeInjections(injected(PAGE)), PAGE);
  // Specimen: the site's own inline script survives.
  assert.match(removeEdgeInjections(injected(PAGE)), /site script/);
  assert.equal(removeEdgeInjections(PAGE), PAGE);
});

test("the integrated homepage returns exactly to its reviewed source", () => {
  const integrated = integrateHtml(PAGE, { assetPrefix: "./ask-carbon" });
  assert.notEqual(integrated, PAGE);
  assert.equal(removeAskCarbonIntegration(integrated), PAGE);
  assert.equal(recoverBaselineBytes("index.html", Buffer.from(injected(integrated)), sha256(PAGE)).toString(), PAGE);
  // Only the homepage is un-integrated; another page keeps its bytes.
  assert.equal(recoverBaselineBytes("about/index.html", Buffer.from(integrated), sha256(PAGE)).toString(), integrated);
});

test("a binary or already-matching file is passed through untouched", () => {
  const png = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x3c, 0x2f]);
  assert.equal(recoverBaselineBytes("assets/a.png", png, "0".repeat(64)), png);
  assert.equal(recoverBaselineBytes("a.html", Buffer.from(PAGE), sha256(PAGE)).toString(), PAGE);
});

test("one path that differs from the manifest fails the baseline and is named", async () => {
  const other = "<html><head></head><body>other</body></html>";
  const manifest = { assets: [
    { path: "about/index.html", sha256: sha256(PAGE), bytes: Buffer.byteLength(PAGE) },
    { path: "workbench/index.html", sha256: sha256(other), bytes: Buffer.byteLength(other) },
  ] };
  const served = { "about/index.html": injected(PAGE), "workbench/index.html": other };
  const fetcher = async (url) => Buffer.from(served[new URL(url).pathname.slice(1)]);
  const clean = await fetchBaseline({ host: "example.test", manifest, fetcher });
  assert.deepEqual(clean.problems, []);
  assert.equal(clean.files.length, 2);

  served["workbench/index.html"] = "<html><head></head><body>moved on</body></html>";
  const moved = await fetchBaseline({ host: "example.test", manifest, fetcher });
  assert.equal(moved.files.length, 1);
  assert.equal(moved.problems.length, 1);
  assert.match(moved.problems[0], /^workbench\/index\.html: digest /);

  const failing = await fetchBaseline({ host: "example.test", manifest, fetcher: async () => { throw new Error("HTTP 404"); } });
  assert.equal(failing.files.length, 0);
  assert.ok(failing.problems.every((line) => line.endsWith("HTTP 404")));
});

test("health must read active, no reasons and the approved model", () => {
  assert.deepEqual(healthProblems({ active: true, reasons: [], model_config_id: "gemma-4-31b-turbo-tee:v1" }), []);
  assert.equal(healthProblems({ active: false, reasons: ["budget"], model_config_id: "other" }).length, 3);
  assert.equal(healthProblems(null).length, 3);
});

test("post-deploy checks cover the paths the owner named", () => {
  const paths = DEFAULT_CHECKS.map(([url]) => url);
  for (const required of ["/", "/workbench/", "/workbench/atlas-source.json", "/ask-carbon/pilot-designer.html", "/miners/", "/start-mining/", "/sitemap.xml"]) assert.ok(paths.includes(required), required);
  assert.equal(paths.filter((url) => /^\/assets\/[^/]+\.png$/.test(url)).length, 4);
});
