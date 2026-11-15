// Compare website/carbonwebsite/site with what carbonphysics.ai serves now.
// Run before every deploy: a difference you did not make means someone changed
// live outside the repository, and a deploy would overwrite it. Pages served
// as `dir/` are fetched at `dir/`; the edge additions Cloudflare makes (the
// bot-challenge script, the Web Analytics beacon, the managed robots.txt
// block) are removed before comparing. Exit 1 on any difference.
//
//   node website/carbonwebsite/tools/compare-live.mjs [--host carbonphysics.ai] [--site <dir>]
//   (in a proxied environment: NODE_USE_ENV_PROXY=1)
//
// --site compares live with another copy of the folder, for example the one
// at an earlier commit; the deploy workflow uses it to refuse to overwrite a
// live change made outside the repository.
import { createHash } from "node:crypto";
import { readFile, readdir } from "node:fs/promises";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const option = (name, fallback) => { const i = process.argv.indexOf(name); return i > 0 ? process.argv[i + 1] : fallback; };
const SITE = option("--site", fileURLToPath(new URL("../site", import.meta.url)));
const HOST = option("--host", "carbonphysics.ai");
const sha = (b) => createHash("sha256").update(b).digest("hex");

export const removeEdgeAdditions = (path, bytes) => {
  if (path === "robots.txt") {
    const text = bytes.toString("utf8"), end = "# END Cloudflare Managed Content\n", i = text.indexOf(end);
    return i < 0 ? bytes : Buffer.from(text.slice(i + end.length).replace(/^\n+/, ""), "utf8");
  }
  if (!path.endsWith(".html")) return bytes;
  return Buffer.from(bytes.toString("utf8")
    .replace(/<script>\(function\(\)\{function c\(\)\{[\s\S]*?<\/script>/g, "")
    .replace(/<script[^>]*cloudflareinsights[^>]*><\/script>\n?/g, ""), "utf8");
};

const urlPath = (path) => path === "index.html" ? "" : path.endsWith("/index.html") ? path.slice(0, -"index.html".length) : path.endsWith(".html") ? path.slice(0, -".html".length) : path;
const walk = async (d) => (await Promise.all((await readdir(d, { withFileTypes: true })).map((e) => e.isDirectory() ? walk(join(d, e.name)) : [join(d, e.name)]))).flat();

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const files = (await walk(SITE)).map((f) => relative(SITE, f).split("\\").join("/")).sort();
  const problems = [];
  for (const path of files) {
    const response = await fetch(`https://${HOST}/${encodeURI(urlPath(path))}`, { headers: { "user-agent": "carbon-compare-live/1" } });
    if (!response.ok) { problems.push(`${path}: live HTTP ${response.status}`); continue; }
    const live = removeEdgeAdditions(path, Buffer.from(await response.arrayBuffer()));
    if (sha(live) !== sha(await readFile(join(SITE, path)))) problems.push(`${path}: differs from live`);
  }
  console.log(`${files.length} files compared with https://${HOST}/: ${problems.length ? `${problems.length} differ` : "all identical"}`);
  for (const p of problems) console.log(`  ${p}`);
  process.exitCode = problems.length ? 1 : 0;
}
