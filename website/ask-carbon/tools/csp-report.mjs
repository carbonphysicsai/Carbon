import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const hashDirective = (value) => `'sha256-${createHash("sha256").update(value).digest("base64")}'`;

const extractInline = (html, tag) => {
  const expressions = [];
  const pattern = new RegExp(`<${tag}([^>]*)>([\\s\\S]*?)<\\/${tag}>`, "gi");
  for (const match of html.matchAll(pattern)) {
    if (tag === "script" && /\bsrc\s*=/i.test(match[1])) continue;
    expressions.push(match[2]);
  }
  return expressions;
};

export const buildCsp = (html) => {
  if (/<[^>]+\son[a-z]+\s*=/i.test(html)) throw new Error("Inline event handlers require removal before a strict CSP can be generated.");
  const styleHashes = extractInline(html, "style").map(hashDirective);
  const scriptHashes = extractInline(html, "script").map(hashDirective);
  const directives = [
    "default-src 'self'",
    "base-uri 'self'",
    "object-src 'none'",
    "frame-ancestors 'none'",
    "form-action 'self'",
    `script-src 'self'${scriptHashes.length ? ` ${scriptHashes.join(" ")}` : ""}`,
    `style-src 'self'${styleHashes.length ? ` ${styleHashes.join(" ")}` : ""}`,
    "img-src 'self' data: https:",
    "font-src 'self'",
    "connect-src 'self'",
    "media-src 'none'",
    "worker-src 'none'",
    "manifest-src 'self'",
    "upgrade-insecure-requests",
  ];
  return { policy: directives.join("; "), inline_script_hashes: scriptHashes, inline_style_hashes: styleHashes };
};

const main = async () => {
  const path = process.argv[2];
  if (!path) throw new Error("Usage: csp-report.mjs /path/to/integrated/index.html");
  const result = buildCsp(await readFile(path, "utf8"));
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
};

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 1;
  });
}
