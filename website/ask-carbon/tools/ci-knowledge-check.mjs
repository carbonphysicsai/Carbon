// Per-PR Ask Carbon knowledge check. Card and release expiry say the committed
// knowledge has aged, not that this change is wrong, so a PR that does not edit
// `knowledge/` validates with `--time-findings-as-warnings`. A PR that edits it,
// and any run where git cannot say whether it did, gets the strict check: a
// freshness check that silently relaxes when its own evidence is missing is
// worse than none. The scheduled Ask Carbon freshness workflow stays strict.
import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPOSITORY = resolve(HERE, "../../..");
const KNOWLEDGE = "website/ask-carbon/knowledge";

// `git diff --quiet` exits 0 for no difference and 1 for a difference; every
// other outcome (a missing base, a shallow history, git absent) is a failure.
export const decideMode = ({ repository = REPOSITORY, base = "origin/main" } = {}) => {
  const diff = spawnSync("git", ["-C", repository, "diff", "--quiet", `${base}...HEAD`, "--", KNOWLEDGE], { encoding: "utf8" });
  if (diff.error === undefined && diff.status === 0) {
    return { mode: "RELAXED", reason: `no change to ${KNOWLEDGE} against ${base}` };
  }
  if (diff.error === undefined && diff.status === 1) {
    return { mode: "STRICT", reason: `this change edits ${KNOWLEDGE}` };
  }
  const detail = diff.error ? diff.error.message : `exit ${diff.status}: ${(diff.stderr ?? "").trim()}`;
  return { mode: "STRICT", reason: `git could not compare ${KNOWLEDGE} against ${base} (${detail}); failing closed` };
};

const main = () => {
  const args = process.argv.slice(2);
  const baseIndex = args.indexOf("--base");
  const repoIndex = args.indexOf("--repository");
  const decision = decideMode({
    repository: repoIndex >= 0 ? resolve(args[repoIndex + 1]) : REPOSITORY,
    base: baseIndex >= 0 ? args[baseIndex + 1] : "origin/main",
  });
  process.stdout.write(`Ask Carbon knowledge check: ${decision.mode} (${decision.reason})\n`);
  if (args.includes("--decide-only")) return;
  const validator = resolve(HERE, "validate-knowledge.mjs");
  const flags = decision.mode === "RELAXED" ? ["--time-findings-as-warnings"] : [];
  const run = spawnSync(process.execPath, [validator, ...flags], { stdio: "inherit" });
  process.exitCode = run.status ?? 1;
};

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();
