// Local review only: copies the four new static files and four existing,
// verified brand assets. It cannot build or deploy a production site bundle.
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve, join } from "node:path";
import { fileURLToPath } from "node:url";
import { loadBaselineManifest } from "../tools/integrate-static.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const option = (name) => args.includes(name) ? args[args.indexOf(name) + 1] : null;
const destination = option("--out");
const singleFile = option("--single-file");
const localAssets = option("--assets-from");
if (!destination || !singleFile) throw new Error("Usage: node portfolio/preview.mjs --out <new preview directory> --single-file <new HTML path>");
const out = resolve(destination);
const manifest = await loadBaselineManifest();
const publicAssets = ["assets/brand-2.svg", "assets/neue-0.otf", "assets/neue-1.otf", "favicon.svg"];
const verified = new Map();
for (const path of publicAssets) {
  const expected = manifest.assets.find((item) => item.path === path);
  if (!expected) throw new Error(`Not a reviewed asset: ${path}`);
  let bytes;
  if (localAssets) {
    bytes = await readFile(resolve(localAssets, path));
  } else {
    const response = await fetch(`https://carbonphysics.ai/${path}`, { signal: AbortSignal.timeout(20000) });
    if (!response.ok) throw new Error(`Asset ${path}: HTTP ${response.status}`);
    bytes = Buffer.from(await response.arrayBuffer());
  }
  if (bytes.length !== expected.bytes || createHash("sha256").update(bytes).digest("hex") !== expected.sha256) throw new Error(`Live brand asset changed: ${path}; review before previewing.`);
  verified.set(path, bytes);
}
const refresh = args.includes("--refresh-local-preview");
// An explicit local refresh only replaces the bounded portfolio files; assets
// still have to match the live manifest, and no production artifact is touched.
await mkdir(out, { recursive: refresh });
await mkdir(join(out, "portfolio"), { recursive: refresh });
await mkdir(join(out, "assets"), { recursive: refresh });
for (const [path, bytes] of verified) await writeFile(join(out, path), bytes, { flag: refresh ? "w" : "wx" });
for (const name of ["index.html", "portfolio.css", "portfolio.js", "economics.mjs"]) {
  await writeFile(join(out, "portfolio", name), await readFile(resolve(here, "../site/portfolio", name)), { flag: refresh ? "w" : "wx" });
}

// A shareable file:// review artifact needs no HTTP server or external assets.
// The inlined module is mechanical packaging of the tested source, not a
// second hand-maintained implementation.
let html = await readFile(join(out, "portfolio/index.html"), "utf8");
let css = await readFile(join(out, "portfolio/portfolio.css"), "utf8");
let js = await readFile(join(out, "portfolio/portfolio.js"), "utf8");
const economics = await readFile(join(out, "portfolio/economics.mjs"), "utf8");
js = js.replace('import { calculateEconomics } from "./economics.mjs";', economics.replace("export function", "function"));
for (const name of ["neue-0.otf", "neue-1.otf"]) css = css.replaceAll(`../assets/${name}`, `data:font/otf;base64,${verified.get(`assets/${name}`).toString("base64")}`);
html = html.replace('<link rel="stylesheet" href="./portfolio.css">', `<style>${css}</style>`).replace('<script type="module" src="./portfolio.js"></script>', `<script type="module">${js}</script>`);
html = html.replaceAll("../assets/brand-2.svg", `data:image/svg+xml;base64,${verified.get("assets/brand-2.svg").toString("base64")}`);
html = html.replace("../favicon.svg", `data:image/svg+xml;base64,${verified.get("favicon.svg").toString("base64")}`);
html = html.replace(/<link rel="preload"[^>]+>\s*/g, "");
html = html.replace("Carbon / Research portfolio", "Carbon / Portfolio review · not published");
await writeFile(resolve(singleFile), html, { flag: refresh ? "w" : "wx" });
console.log(`Local preview: ${join(out, "portfolio/index.html")}\nSelf-contained shareable preview: ${resolve(singleFile)}\n4 brand assets matched their recorded hashes; no production change.`);
