import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import { renderPortfolio } from "./render.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const target = resolve(here, "../site/portfolio/index.html");
const rendered = renderPortfolio();
const economics = await readFile(resolve(here, "economics.mjs"), "utf8");
const economicsTarget = resolve(here, "../site/portfolio/economics.mjs");
const additionPaths = ["index.html", "portfolio.css", "portfolio.js", "economics.mjs"];
const additions = [];
for (const name of additionPaths) {
  const bytes = name === "index.html" ? rendered : name === "economics.mjs" ? economics : await readFile(resolve(here, "../site/portfolio", name));
  additions.push({ path: `portfolio/${name}`, source: `site/portfolio/${name}`, sha256: createHash("sha256").update(bytes).digest("hex"), decision: "WEB-PORTFOLIO-01 local implementation; publication not authorized", reason: "Proposed investor-facing research portfolio addition. It neither replaces the live baseline nor changes challenge or reward policy." });
}
const manifest = JSON.stringify({ schema: "carbon.ask-carbon.site-additions.v1", status: "DRAFT_NOT_APPROVED_FOR_PUBLICATION", note: "Deterministic candidate only. Existing approved additions and release decisions are unchanged. Before publication, reconcile the current live baseline, approve public content, add reviewed navigation/sitemap changes and derive a new exact release candidate.", additions }, null, 2) + "\n";
const manifestTarget = resolve(here, "../portfolio-additions.candidate.json");
if (process.argv.includes("--check")) {
  if (await readFile(target, "utf8") !== rendered) throw new Error("Portfolio HTML is stale. Run node portfolio/build.mjs.");
  if (await readFile(economicsTarget, "utf8") !== economics) throw new Error("Portfolio economics module is stale. Run node portfolio/build.mjs.");
  if (await readFile(manifestTarget, "utf8") !== manifest) throw new Error("Portfolio additions candidate is stale. Run node portfolio/build.mjs.");
  console.log("Portfolio HTML matches its eight source investment cases.");
} else {
  await mkdir(dirname(target), { recursive: true });
  await writeFile(target, rendered);
  await writeFile(economicsTarget, economics);
  await writeFile(manifestTarget, manifest);
  console.log(`Built ${target}`);
}
