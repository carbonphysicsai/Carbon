// Official AppBridge + App SDK, deterministic data. This is not a paid agent host.
const fs = require("node:fs"), path = require("node:path"), assert = require("node:assert/strict");
const { chromium } = require("playwright");
const [fixtureFile, bundleFile, artifactDirectory] = process.argv.slice(2);
const root = path.resolve(__dirname, "../../..");
const fixture = JSON.parse(fs.readFileSync(fixtureFile, "utf8"));
const appHtml = fs.readFileSync(path.join(root, "carbon/miner_mcp/apps_ui/workbench.html"), "utf8");
const bridge = fs.readFileSync(bundleFile, "utf8");
(async () => {
  fs.mkdirSync(artifactDirectory, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: process.env.CARBON_BROWSER || undefined });
  const evidence = [];
  try {
    for (const [name, width, height] of [["desktop", 1280, 900], ["mobile", 390, 844]]) {
      const context = await browser.newContext({ viewport: { width, height } });
      const page = await context.newPage(), errors = [], network = [];
      page.on("pageerror", (error) => { errors.push(error.message); process.stderr.write(error.message + "\n"); });
      page.on("console", (entry) => { if (entry.type() === "error") process.stderr.write(entry.text() + "\n"); });
      await page.route("**/*", (route) => {
        const url = route.request().url();
        if (url === "http://127.0.0.1:8877/") return route.fulfill({ contentType: "text/html", body: '<!doctype html><title>Deterministic official AppBridge host</title><iframe id="view" sandbox="allow-scripts" style="width:100%;height:850px;border:0"></iframe><script type="module">' + bridge.replaceAll("</script", "<\\/script") + "</script>" });
        network.push(url); return route.abort();
      });
      await page.addInitScript(({ fixture, appHtml }) => { globalThis.fixture = fixture; globalThis.appHtml = appHtml; }, { fixture, appHtml });
      await page.goto("http://127.0.0.1:8877/");
      await page.waitForFunction(() => globalThis.bridgeReady === true);
      const frame = page.frameLocator("#view");
      await frame.locator("#plot svg").waitFor();
      assert.equal(await frame.locator("#plot svg").count(), 1);
      assert.match(await frame.locator("#state").innerText(), /COMPLETE/);
      for (const action of ["status", "result", "cancel", "start"]) {
        await frame.locator("#" + action).click();
        await frame.locator("#message").filter({ hasText: "Received DEVELOPMENT data" }).waitFor();
      }
      assert.deepEqual(await page.evaluate(() => globalThis.calls), ["status", "result", "cancel", "start"]);
      await page.evaluate(() => { globalThis.delayStart = true; });
      await frame.locator("#start").click();
      await page.waitForFunction(() => globalThis.startWaiting === true);
      assert(await frame.locator("#start").isDisabled());
      assert(!(await frame.locator("#cancel").isDisabled()));
      await frame.locator("#cancel").click();
      await frame.locator("#state").filter({ hasText: "CANCEL_REQUESTED" }).waitFor();
      assert(await frame.locator("#start").isDisabled());
      assert.equal(await frame.locator("#plot svg").count(), 0);
      await page.evaluate(() => globalThis.releaseStart());
      await frame.locator("#plot svg").waitFor();
      await frame.locator("#message").filter({ hasText: "Received DEVELOPMENT data" }).waitFor();
      assert.match(await frame.locator("#state").innerText(), /COMPLETE/);
      assert.deepEqual(await page.evaluate(() => globalThis.calls.slice(-2)), ["start", "cancel"]);
      const blocked = await page.frames()[1].evaluate(async () => { try { await fetch("https://example.invalid/private"); return false; } catch (_) { return true; } });
      assert(blocked);
      await page.evaluate(() => globalThis.sendRejectedResult());
      await frame.locator("#message").filter({ hasText: "Study authority or status rejected" }).waitFor();
      assert.match(await frame.locator("#state").innerText(), /COMPLETE/);
      assert.equal(await frame.locator("#plot svg").count(), 1);
      assert.deepEqual(errors, []); assert.deepEqual(network, []);
      assert(await page.frames()[1].evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.screenshot({ path: path.join(artifactDirectory, name + ".png"), fullPage: true });
      evidence.push({ viewport: name, plots: 1, controls: 4, cancel_during_start: true, cancellation_ack_not_cleanup: true, page_errors: errors, external_requests: network, csp_blocked_fetch: blocked });
      await context.close();
    }
  } finally { await browser.close(); }
  const report = { fixture_only: true, agent_host: false, sdk: "@modelcontextprotocol/ext-apps@2.0.0", evidence };
  fs.writeFileSync(path.join(artifactDirectory, "report.json"), JSON.stringify(report, null, 2));
  process.stdout.write(JSON.stringify(report) + "\n");
})().catch((error) => { console.error(error); process.exitCode = 1; });
