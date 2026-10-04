import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { programs, sources, evidenceRevision } from "../portfolio/content.mjs";
import { highlights, screeningImpact, screeningScenario } from "../portfolio/highlights.mjs";
import { visual } from "../portfolio/visuals.mjs";
import { impactCases, outcomes, calculateScale, scaleIllustration } from "../portfolio/impact.mjs";
import { solveIllustration, renderSolverIllustration } from "../portfolio/solver-preview.mjs";
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

test("eight concise cards contain the requested fields and distinct concept visuals", () => {
  assert.deepEqual(highlights.map((p) => p.id), programs.map((p) => p.id));
  for (const p of highlights) {
    for (const key of ["title", "highlight", "industry", "customers", "baseline", "basis", "state"]) assert.ok(typeof p[key] === "string" && p[key].length > 5, `${p.id}: missing ${key}`);
    assert.ok(sources[p.source]);
    assert.ok(outcomes[p.id]?.length > 15);
    const scale = scaleIllustration(p.id);
    for (const key of ["first", "firstLabel", "second", "secondLabel", "note"]) assert.ok(scale[key]?.length > 0, `${p.id}: missing ${key}`);
    assert.ok(p.basis.includes("Illustrative") || p.basis.includes("Historical"));
    assert.match(visual(p.id, p.title), /<svg[^>]+role="img"/);
    assert.ok(visual(p.id, p.title).includes(`<title>${p.title}</title>`));
  }
});

test("HTML is a compact static page, source-synchronized and complete without JavaScript", async () => {
  const html = await readFile(resolve(root, "site/portfolio/index.html"), "utf8");
  assert.equal(html, renderPortfolio());
  assert.equal((html.match(/<article class="pf-card"/g) ?? []).length, 8);
  assert.equal((html.match(/<svg /g) ?? []).length, 9);
  assert.equal((html.match(/<h3>Industrial use<\/h3>/g) ?? []).length, 8);
  assert.equal((html.match(/<h3>Customer targets<\/h3>/g) ?? []).length, 8);
  assert.equal((html.match(/<h3>Impact to prove<\/h3>/g) ?? []).length, 8);
  assert.equal((html.match(/If achieved at scale/g) ?? []).length, 8);
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]);
  assert.equal(new Set(ids).size, ids.length, "duplicate ID");
  for (const target of [...html.matchAll(/href="#([^"]+)"/g)].map((match) => match[1])) assert.ok(ids.includes(target), `missing anchor ${target}`);
  assert.ok(html.includes("25% Bittensor investor fit"));
  assert.ok(html.includes("not an emissions allocation or launch approval"));
  assert.ok(html.includes("not Carbon results, performance targets, forecasts or total ROI"));
  assert.ok(html.includes("Net value must include data, training, verification, integration, serving and upkeep"));
  assert.ok(html.includes("Operational gains require separate validation"));
  assert.ok(html.includes("Prototype costs and lead times need customer quotes"));
  assert.ok(!/run-hours|100 ms|1,000 candidate cases|Solve assumption|compute cost avoided/.test(html));
  assert.ok(html.includes("Customer types are targets, not clients"));
  assert.ok(!/<details|<input|pf-filter|pf-calculator/.test(html));
  const visibleCopy = html.replace(/<svg[\s\S]*?<\/svg>/g, "").replace(/<head>[\s\S]*?<\/head>/g, "").replace(/<[^>]*>/g, " ");
  assert.ok(visibleCopy.trim().split(/\s+/).length < 1100, "Keep the page concise even with the contest preview");
  assert.ok(!/fetch\(|<iframe|gtag|analytics|localStorage|api\/ask-carbon/.test(html));
});

test("value-at-scale illustrations use explicit units and correct conditional arithmetic", () => {
  assert.deepEqual(calculateScale(impactCases.cooling), { kwh: 876000, annualUsd: 87600 });
  assert.deepEqual(calculateScale(impactCases.thermal), { equivalents: 100 });
  assert.deepEqual(calculateScale(impactCases.photonics), { passingDevices: 10000 });
  assert.equal(calculateScale(impactCases.battery).hoursPerDay, 5000 / 60);
  assert.deepEqual(calculateScale(impactCases.motors), { rounds: 1 });
  assert.deepEqual(calculateScale(impactCases.vibration), { rounds: 1 });
  assert.deepEqual(calculateScale(impactCases.acoustics), { annualUsd: 100000 });
  assert.ok(Math.abs(calculateScale(impactCases.mixing).minutesAvoided - 480 * (1 - 1 / 1.1)) < 1e-10);
  assert.equal(scaleIllustration("mixing").second, "~44 min");
  assert.ok(!JSON.stringify(scaleIllustration("motors")).includes("$"), "Do not invent a prototype price");
  assert.ok(Object.values(impactCases).every(Object.isFrozen));
});

test("scale illustrations refuse invalid units/counts instead of manufacturing value", () => {
  for (const c of Object.values(impactCases)) {
    for (const key of Object.keys(c).filter((k) => k !== "kind")) {
      for (const bad of [-1, 0, NaN, Infinity, "1", null]) assert.throws(() => calculateScale({ ...c, [key]: bad }), RangeError);
    }
  }
  for (const kind of ["prototype", "capacity", "yield", "dwell", "unitCost"]) {
    const c = Object.values(impactCases).find((item) => item.kind === kind);
    const key = ({ prototype: "rounds", capacity: "units", yield: "devices", dwell: "events", unitCost: "annualUnits" })[kind];
    assert.throws(() => calculateScale({ ...c, [key]: 1.5 }), RangeError);
  }
  assert.throws(() => calculateScale({ ...impactCases.cooling, hours: 8761 }), RangeError);
  assert.throws(() => calculateScale({ ...impactCases.photonics, gainPoints: 101 }), RangeError);
  assert.throws(() => calculateScale({ kind: "unknown" }), RangeError);
  assert.throws(() => scaleIllustration("unknown"), RangeError);
});

test("solver illustration actually solves a public manufactured field with refinement controls", () => {
  const coarse = solveIllustration(16), fine = solveIllustration(32);
  assert.equal(fine.values.length, 1024);
  assert.ok(fine.values.every((value) => Number.isFinite(value) && value > 0));
  assert.ok(fine.relativeResidual < 1e-8);
  assert.ok(fine.maxError < 0.001);
  assert.ok(fine.maxError < coarse.maxError / 3);
  assert.deepEqual(solveIllustration(32), fine, "Deterministic public illustration");
  for (const invalid of [0, 7, 65, 16.5, "32"]) assert.throws(() => solveIllustration(invalid), RangeError);
  assert.ok(renderSolverIllustration().includes("SYNTHETIC TEST"));
});

test("future contest reserves an empty model slot and makes no winner or benchmark claim", () => {
  const html = renderPortfolio();
  assert.ok(html.includes('id="design-contest"'));
  assert.ok(html.includes("Side by side when models ship"));
  assert.ok(html.includes("No model output or winner is shown yet"));
  assert.ok(html.includes("Not a cold-plate benchmark, optimization run or contest result"));
  assert.ok(html.includes("compute and wall-clock budgets"));
  assert.ok(html.includes("including preparation and model build"));
  assert.ok(html.includes("competitive reduced methods"));
});

test("screening savings include surrogate time and final solver checks", () => {
  const result = screeningImpact(1200);
  assert.equal(result.baselineSeconds, 1200000);
  assert.equal(result.surrogateSeconds, 24100);
  assert.equal(result.runHoursSaved, 1175900 / 3600);
  assert.equal(result.dollarsSaved, result.runHoursSaved * 5);
  assert.deepEqual(screeningScenario, { designs: 1000, solverChecks: 20, predictionSeconds: 0.1, dollarsPerRunHour: 5 });
  assert.ok(screeningImpact(0.01).runHoursSaved < 0, "A cheap solver must be allowed to win");
  assert.equal(screeningImpact(1200, { ...screeningScenario, dollarsPerRunHour: 0 }).dollarsSaved, 0);
});

test("screening rejects invalid cases and does not upgrade estimates into measurements", async () => {
  for (const bad of [0, -1, NaN, Infinity, "1200", null]) assert.throws(() => screeningImpact(bad), RangeError);
  for (const [key, bad] of [["designs", 0], ["designs", 1.5], ["solverChecks", -1], ["solverChecks", 1001], ["solverChecks", 1.5], ["predictionSeconds", -1], ["predictionSeconds", Infinity], ["dollarsPerRunHour", NaN], ["dollarsPerRunHour", "5"]]) assert.throws(() => screeningImpact(1200, { ...screeningScenario, [key]: bad }), RangeError);
  const families = JSON.parse(await readFile(resolve(repo, "carbon/challenge_pipeline/families.json"), "utf8"));
  const list = Array.isArray(families) ? families : families.families;
  const mapping = { cooling: "f04", thermal: "f02", photonics: "f06", vibration: "f08", acoustics: "f13", mixing: "f17" };
  for (const [id, family] of Object.entries(mapping)) {
    const entry = list.find((item) => item.id === family || item.family_id === family);
    assert.ok(entry, `missing ${family}`);
    assert.ok(highlights.find((p) => p.id === id).basis.includes(family));
    assert.equal(highlights.find((p) => p.id === id).solverSeconds, entry.est.typ);
  }
  assert.equal(highlights.find((p) => p.id === "motors").solverSeconds, 60 * list.find((p) => p.id === "f09").est.typ);
  assert.equal(highlights.find((p) => p.id === "battery").source, "batteryCost");
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
