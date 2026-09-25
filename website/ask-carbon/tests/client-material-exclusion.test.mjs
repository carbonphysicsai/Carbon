// E8: no code path from a Workbench client record to the public assistant.
//
// The assistant's runtime is `worker/` and `public/`. Everything it can ever
// read is what those files import, so the route is closed by showing the import
// set contains nothing outside this tree: no Workbench module, no `carbon/`
// module and no private store. Knowledge sources are contained to the public
// repository by `containedSourcePath`.
//
// Each absence below is paired with a specimen showing that the same scanner
// finds the thing where it really is, so a scanner that stopped matching would
// fail rather than pass quietly.
import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readdir, readFile, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { containedSourcePath } from "../tools/validate-knowledge.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const TREE = resolve(HERE, "..");
const REPO = resolve(TREE, "../..");
const RUNTIME = ["worker", "public"];
const ALLOWED = ["worker", "public", "knowledge"].map((name) => join(TREE, name));
const BUILTIN = /^(node:|cloudflare:)/;

// Every module specifier a file names: static imports and re-exports, dynamic
// import() and require(). A dynamic call whose argument is not a string
// literal is reported as unresolvable, because a runtime that can compute what
// it loads can load anything.
const specifiers = (source) => {
  const found = [], unresolved = [];
  const patterns = [
    /(?:^|;)\s*(?:import|export)\s[^;"'`]*?\bfrom\s*(["'])([^"']+)\1/gm, // import/export ... from "x"
    /(?:^|;)\s*import\s*(["'])([^"']+)\1/gm, // import "x"
    /\b(?:import|require)\s*\(\s*(["'])([^"']+)\1/g, // import("x"), require("x")
  ];
  for (const pattern of patterns) for (const match of source.matchAll(pattern)) found.push(match[2]);
  const dynamic = /\b(?:import|require)\s*\(\s*(?!["'])[^)]/g;
  for (const match of source.matchAll(dynamic)) unresolved.push(match[0]);
  return { found, unresolved };
};

const filesUnder = async (directory) => {
  const out = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) out.push(...(await filesUnder(path)));
    else if (/\.(m?js|cjs)$/.test(entry.name)) out.push(path);
  }
  return out;
};

const outsideTree = async (files) => {
  const escapes = [], unresolved = [];
  for (const file of files) {
    const scan = specifiers(await readFile(file, "utf8"));
    for (const name of scan.unresolved) unresolved.push(`${relative(REPO, file)}: ${name}`);
    for (const name of scan.found) {
      if (BUILTIN.test(name)) continue;
      if (!name.startsWith(".")) {
        escapes.push(`${relative(REPO, file)} -> package ${name}`);
        continue;
      }
      const target = resolve(dirname(file), name);
      if (!ALLOWED.some((root) => target === root || target.startsWith(root + "/")))
        escapes.push(`${relative(REPO, file)} -> ${relative(REPO, target)}`);
    }
  }
  return { escapes, unresolved };
};

test("the assistant's runtime imports nothing outside its own tree", async () => {
  const files = (await Promise.all(RUNTIME.map((name) => filesUnder(join(TREE, name))))).flat();
  assert.ok(files.length >= 8, "the runtime scan found the worker and public modules");
  const { escapes, unresolved } = await outsideTree(files);
  assert.deepEqual(escapes, []);
  assert.deepEqual(unresolved, []);
});

test("specimen: the same scanner finds a cross-tree import where one really exists", async () => {
  // The offline evaluation harness imports Workbench modules on purpose and is
  // not part of the deployed runtime. If this stops being found, the scan above
  // has stopped seeing imports, not become clean.
  const { escapes } = await outsideTree([join(TREE, "eval/pilot-design-runner.mjs")]);
  assert.ok(escapes.some((line) => line.includes("Business/Carbon_Fit/workbench/src/intake.js")), escapes.join("\n"));
});

test("specimen: a computed import is reported rather than trusted", () => {
  const { unresolved } = specifiers('const m = await import(name);\nconst r = require(`./${x}`);');
  assert.equal(unresolved.length, 2);
});

test("knowledge sources cannot name a file outside the public repository", async () => {
  // Specimen first: a real, committed source resolves.
  assert.ok(await containedSourcePath("CONSTITUTION.md"));
  for (const escape of ["/etc/hostname", "../outside.json", "Design_Specs/../../outside.json", "", null])
    assert.equal(await containedSourcePath(escape), null, String(escape));

  // A symlink inside the root that points outside it is refused as well.
  const root = await mkdtemp(join(tmpdir(), "ask-carbon-e8-"));
  const outside = await mkdtemp(join(tmpdir(), "ask-carbon-e8-private-"));
  await writeFile(join(outside, "store.json"), "{}");
  await writeFile(join(root, "public.md"), "public");
  await symlink(join(outside, "store.json"), join(root, "linked.json"));
  assert.ok(await containedSourcePath("public.md", root));
  assert.equal(await containedSourcePath("linked.json", root), null);
});

test("the internal Workbench build has no route to the assistant", async () => {
  // The internal Workbench page is where client records are held and edited.
  // Specimen: the public Pilot Designer preview, which is built from the same
  // tree, does name the assistant's endpoint, so a missing string below means
  // the internal page lacks the route rather than the search failing.
  const workbench = join(REPO, "Business/Carbon_Fit/workbench");
  const preview = await readFile(join(workbench, "Carbon_Client_Pilot_Designer_Preview.html"), "utf8");
  const internal = await readFile(join(workbench, "Carbon_Opportunity_Workbench.html"), "utf8");
  assert.ok(preview.includes("/api/ask-carbon"));
  assert.ok(!internal.includes("/api/ask-carbon"));
  assert.ok(!internal.includes("ask-carbon"));
});
