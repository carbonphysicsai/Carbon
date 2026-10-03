import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { programs, sources, evidenceRevision } from "../portfolio/content.mjs";
import { renderPortfolio } from "../portfolio/render.mjs";
import { calculateEconomics } from "../portfolio/economics.mjs";
import { loadBaselineManifest, loadSiteAdditions } from "../tools/integrate-static.mjs";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repo = resolve(root, "../..");
const assumptions = { build: 50000, upkeep: 10000, baseline: 1200, model: 200, campaigns: 100 };

test("eight distinct, fully explained proposed programs, across five clusters", () => {
  assert.equal(programs.length, 8);
  assert.equal(new Set(programs.map((p) => p.id)).size, 8);
  assert.equal(new Set(programs.map((p) => p.group)).size, 5);
  for (const [index, p] of programs.entries()) {
    assert.equal(p.number, String(index + 1).padStart(2, "0"));
    for (const key of ["title", "decision", "driver", "buyer", "paidEntry", "economics", "repeat", "baseline", "contest", "scope", "reference", "status", "evidence", "next", "pause", "experiment"]) assert.ok(typeof p[key] === "string" && p[key].length > 10, `${p.id}: missing ${key}`);
    assert.equal(p.expansions.length, 4);
    assert.ok(p.sources.length >= 2);
    for (const key of p.sources) assert.ok(sources[key], `${p.id}: missing source ${key}`);
  }
});

test("public source links name real files at the stated immutable revision", () => {
  for (const source of Object.values(sources)) {
    const url = new URL(source.url);
    assert.equal(url.hostname, "github.com");
    assert.ok(url.pathname.startsWith(`/carbonphysicsai/Carbon/blob/${evidenceRevision}/`));
    const path = url.pathname.split("/").slice(5).join("/");
    assert.ok(existsSync(resolve(repo, path)), `Missing source ${path}`);
  }
});

test("HTML is static, source-synchronized, and complete without JavaScript", async () => {
  const html = await readFile(resolve(root, "site/portfolio/index.html"), "utf8");
  assert.equal(html, renderPortfolio());
  assert.equal((html.match(/<article class="pf-card"/g) ?? []).length, 8);
  assert.equal((html.match(/<details class="pf-dossier"/g) ?? []).length, 8);
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]);
  assert.equal(new Set(ids).size, ids.length, "duplicate ID");
  for (const target of [...html.matchAll(/href="#([^"]+)"/g)].map((match) => match[1])) assert.ok(ids.includes(target), `missing anchor ${target}`);
  assert.ok(html.includes("25% planning weight"));
  assert.ok(html.includes("75% is commercial and technical judgment"));
  assert.ok(html.includes("not eight live products"));
  assert.ok(html.includes("No matched-resource portfolio competition results"));
  assert.ok(html.includes("Harder to game, not declared ungameable"));
  assert.ok(html.includes("No prices, ROI, emissions allocation or returns are promised"));
  assert.ok(html.includes("All default numbers are illustrative"));
  assert.ok(html.includes("Battery remains the protocol-development lead"));
  assert.equal((html.match(/Not yet measured/g) ?? []).length, 5);
  assert.ok(!/fetch\(|<iframe|gtag|analytics|localStorage|api\/ask-carbon/.test(html));
});

test("economics includes fixed build, upkeep and recurring full-workflow costs", () => {
  assert.deepEqual(calculateEconomics(assumptions), { baselineTotal: 120000, modelTotal: 80000, difference: 40000, breakEven: 60, parity: false });
  assert.equal(calculateEconomics({ ...assumptions, campaigns: 60 }).difference, 0);
  assert.equal(calculateEconomics({ ...assumptions, campaigns: 59 }).difference, -1000);
  assert.equal(calculateEconomics({ ...assumptions, campaigns: 61 }).difference, 1000);
});

test("a fast baseline legitimately removes cost break-even", () => {
  for (const baseline of [0, 100, 200]) assert.equal(calculateEconomics({ ...assumptions, baseline }).breakEven, null);
  assert.ok(calculateEconomics({ ...assumptions, model: 1400 }).difference < 0);
  const equal = calculateEconomics({ ...assumptions, build: 0, upkeep: 0, model: 1200 });
  assert.equal(equal.parity, true);
  assert.equal(equal.difference, 0);
  assert.equal(equal.breakEven, 0);
});

test("cent precision, immediate savings, rounded campaign counts and bounded maxima", () => {
  const tiny = calculateEconomics({ build: 0.10, upkeep: 0, baseline: 0.30, model: 0.20, campaigns: 1 });
  assert.equal(tiny.breakEven, 1);
  assert.equal(tiny.difference, 0);
  assert.equal(calculateEconomics({ ...assumptions, build: 0, upkeep: 0 }).breakEven, 0);
  assert.equal(calculateEconomics({ ...assumptions, build: 50001 }).breakEven, 61);
  const maximum = calculateEconomics({ build: 1e9, upkeep: 1e9, baseline: 1e6, model: 1e6, campaigns: 1e6 });
  assert.equal(maximum.modelTotal, 1002000000000);
  assert.equal(maximum.difference, -2000000000);
});

test("invalid assumptions refuse output instead of manufacturing a saving", () => {
  for (const key of Object.keys(assumptions)) for (const bad of [NaN, Infinity, -1, "1", null, undefined]) assert.throws(() => calculateEconomics({ ...assumptions, [key]: bad }), RangeError);
  for (const campaigns of [0, 1.5, 1000001]) assert.throws(() => calculateEconomics({ ...assumptions, campaigns }), RangeError);
  for (const key of ["build", "upkeep", "baseline", "model"]) assert.throws(() => calculateEconomics({ ...assumptions, [key]: 0.001 }), RangeError);
  assert.throws(() => calculateEconomics({ ...assumptions, build: 1e9 + 1 }), RangeError);
  assert.throws(() => calculateEconomics({ ...assumptions, model: 1e6 + 1 }), RangeError);
});

test("new route is a pinned draft addition, not a replacement or approved release", async () => {
  const manifestPath = resolve(root, "portfolio-additions.candidate.json");
  const draft = JSON.parse(await readFile(manifestPath, "utf8"));
  assert.equal(draft.status, "DRAFT_NOT_APPROVED_FOR_PUBLICATION");
  const manifest = await loadBaselineManifest();
  const additions = await loadSiteAdditions(manifestPath, manifest);
  assert.deepEqual(additions.map((p) => p.path), ["portfolio/index.html", "portfolio/portfolio.css", "portfolio/portfolio.js", "portfolio/economics.mjs"]);
  for (const addition of additions) assert.ok(!manifest.assets.some((asset) => asset.path === addition.path));
  assert.equal(await readFile(resolve(root, "site/portfolio/economics.mjs"), "utf8"), await readFile(resolve(root, "portfolio/economics.mjs"), "utf8"));
});
