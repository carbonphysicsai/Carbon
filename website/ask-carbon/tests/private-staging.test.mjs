import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { stagingRequestAuthorized } from "../worker/staging-auth.mjs";

const env = { ASK_CARBON_STAGING_BASIC_AUTH: "dGVzdDpwcml2YXRl" };

test("private staging credential check fails closed and is exact", () => {
  assert.equal(stagingRequestAuthorized(new Request("https://private.example/"), env), false);
  assert.equal(stagingRequestAuthorized(new Request("https://private.example/", {
    headers: { authorization: "Basic dGVzdDpwcml2YXRl" },
  }), env), true);
  assert.equal(stagingRequestAuthorized(new Request("https://private.example/", {
    headers: { authorization: "Basic dGVzdDpwcml2YXRlLXdoaXRlc3BhY2U=" },
  }), env), false);
});

test("private staging entrypoint gates every route before serving the integrated candidate or API", async () => {
  const source = await readFile(new URL("../worker/private-staging.mjs", import.meta.url), "utf8");
  assert.match(source, /if \(!stagingRequestAuthorized\(request, env\)\) return accessDenied\(\);/);
  assert.ok(source.indexOf("stagingRequestAuthorized") < source.indexOf("url.pathname === \"/pilot\""));
  assert.match(source, /location: "\/ask-carbon\/pilot-designer\.html"/);
  assert.match(source, /return askCarbon\.fetch\(request, env, context\)/);
  assert.match(source, /x-robots-tag/);
});
