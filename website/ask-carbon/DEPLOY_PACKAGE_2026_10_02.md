# Ask Carbon deploy package: bundle `b22f6d1c…` (Start mining, candidate 2026-10-02.1)

For a named operator (WEB-QA-05-D2), deploying from their own machine.
Everything needed is in this file and in the public repository. Nothing has to
be re-derived, and no file has to be obtained from the owner.

**Status: APPROVED for deployment (WEB-QA-12-D1, 2026-10-02). Not yet
deployed.** The owner approved this exact identity in session. At approval
(21:16Z) live still matched manifest v4 100/100 on both hostnames, and the
rebuild reproduced the identity below.

**The artifact.** Bundle identity
`b22f6d1cdaf5b3d9952ee3b802a2c09b8de8320fe566a238636bd53aac770f46`, 106 files.
If the build in step 2 prints any other identity, it is not this artifact.
Stop there.

## What a visitor will see change

The comparison is against production: `carbonwebsite` `c12d547a`, bundle
`86f51385…` (WEB-QA-11-D2). It was measured on 2026-10-02 at 19:49Z. Every
path was compared by SHA-256, with HTML compared after removing the
edge-injected scripts.

| Path | Production today | After this deploy |
| --- | --- | --- |
| `/` (`index.html`) | `b1e8e7cd…` (17,433 bytes) | `5b842bf6…` (17,816 bytes). The Miners card gains a "Start mining" link under "Learn more". |
| `/miners/` | `88517c7c…` (22,975 bytes) | `044edfef…` (22,970 bytes). The hero button reads "Start mining" and goes to `/start-mining/`; it was "Start a development run", to `#start`. |
| `/start-mining/` | HTTP 404 | `4adbf65e…` (13,230 bytes). New page: install the Control Center, start your signer, choose a Challenge. |
| `/sitemap.xml` | `18a8b163…` (511 bytes) | `51fb9148…` (574 bytes). Lists `/start-mining/`. |

The other 102 paths are byte-identical to production. They include the Pilot
Designer `be64f8b9…`, the `/workbench/` retirement page `9a44f683…`, the Q&A
component and the knowledge.

The Worker (`ask-carbon-public`) is not redeployed.

## Prerequisites

- Node.js 18 or later (CI uses 24.19.0). No `npm install` is needed.
- `wrangler`, logged in to the Carbon Cloudflare account, as for WEB-QA-11-D2.

```sh
git clone --depth 1 https://github.com/carbonphysicsai/Carbon.git carbon-deploy
cd carbon-deploy/website/ask-carbon
OUT="$HOME/ask-carbon-b22f6d1c"          # must not exist yet
BASE="$HOME/ask-carbon-baseline-v4"      # must not exist yet
```

## 0. Capture the rollback target (before anything else)

```sh
npx wrangler deployments status --name carbonwebsite
```

Write the version id down. **This capture is the rollback target. Do not
take it from this document.**

- **What the repository expects:** `c12d547a-1cd3-4dbd-a91a-8106ad3aa2b4`,
  the WEB-QA-11-D2 deploy.
- If your capture shows anything else, stop and tell the owner before
  deploying.
- **Never use `b694b20f`.** Rolling back to it would withdraw the v3 papers.
- **Do not touch the `AskCarbonUsageLedger` Durable Object.** It is never
  rolled back or deleted.
- **Do not enable Cloudflare Email Routing.** It breaks the Google Workspace MX
  records.

## 1. Re-derive the baseline from the live site

```sh
node tools/fetch-live-baseline.mjs --host carbonphysics.ai --out "$BASE"
node tools/fetch-live-baseline.mjs --host www.carbonphysics.ai --out "$BASE-www"
diff -r "$BASE" "$BASE-www" && echo "hostnames agree"
```

Each run must print `100/100 match the baseline manifest`, and the `diff` must
be silent. A mismatch means live is no longer the state this candidate was
built against. Stop: do not build or deploy.

## 2. Build the staged bundle

```sh
node tools/integrate-static.mjs \
  --input "$BASE/index.html" --output "$OUT/index.html" --asset-prefix ./ask-carbon \
  --existing-site "$BASE" --site-replacements site-replacements.json \
  --site-additions site-additions.json --homepage-edit start-mining-link-v1 \
  --require-complete-bundle > "$OUT.report.json"
grep -E '"bundle_identity_sha256"|"deployable_to_carbonwebsite"' "$OUT.report.json"
```

The output must read
`"bundle_identity_sha256": "b22f6d1cdaf5b3d9952ee3b802a2c09b8de8320fe566a238636bd53aac770f46"`
and `"deployable_to_carbonwebsite": true`. Any other identity means stop.

## 3. Check the bundle against live before publishing

```sh
node tools/verify-publication.mjs --bundle "$OUT"
```

Before the deploy, exactly eight lines must say `FAIL`: `/`, `/miners/`,
`/start-mining/` (HTTP 404) and `/sitemap.xml`, on each hostname. Those are the
four changes. Every other line, including health, must be `ok`.

## 4. Publish the static site (the only command that changes production)

Run it from `website/ask-carbon`, keeping compatibility date `2026-09-12`:

```sh
npx wrangler deploy --name carbonwebsite --assets "$OUT" --compatibility-date 2026-09-12
```

## 5. Verify the publish

```sh
node tools/verify-publication.mjs --bundle "$OUT"
```

It must end with `VERIFIED`. It checks these paths on **both** hostnames, each
against the byte it should serve:
- `/`, `/workbench/`, `/miners/`, `/start-mining/` and `/sitemap.xml`;
- the four `/assets/*.png`;
- `/workbench/atlas-source.json` and `/ask-carbon/pilot-designer.html`.

It then checks `/api/ask-carbon/health`. The health endpoint is rate-limited
per client. Running the check several times in a few minutes can return
HTTP 429 on one hostname. If so, wait a few minutes and run step 5 once more
before treating it as a failure; a 429 is not a content difference.

Also open these in a browser:
- `https://carbonphysics.ai/`: the Miners card shows "Start mining";
- `https://carbonphysics.ai/miners/`: the hero button reads "Start mining" and
  opens `/start-mining/`.

If any line fails, roll back with the id captured in step 0:

```sh
npx wrangler rollback <carbonwebsite id from step 0> --name carbonwebsite
```

## 6. Report back to the owner

Send these, so the deployment event can be recorded:
- the version id from step 0;
- the new `carbonwebsite` version id that wrangler printed;
- the `VERIFIED` output from step 5.
