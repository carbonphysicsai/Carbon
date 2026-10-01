# Ask Carbon deploy package: bundle `86f51385…` (WEB-QA-11-D1, approved 2026-10-01)

For the operator (Nick Fitzpatrick), deploying from his own Mac. Everything
needed is in this file and in two scripts in the public repository. Nothing has
to be re-derived, and no file has to be obtained from the owner.

**Approved artifact.** Bundle identity
`86f51385e05d6d2aca50c612b11f986916c74210c2bda96ac33ed41dcbc3d14a`, 105 files.
If the build in step 2 prints any other identity, it is not the approved
artifact. Stop there.

## What a visitor will see change

The comparison is against production (bundle `48fd4680…`, WEB-QA-10-D1), not
against an earlier candidate. Measured on both hostnames on 2026-10-01 at
10:05Z, every path compared by SHA-256, with HTML compared after removing the
edge-injected scripts.

| Path | Production today | After this deploy |
| --- | --- | --- |
| `ask-carbon/pilot-designer.html` | `4c9f39169cabc3748662d64925828cfa07aa63fe277dff164735847ee907c6cd` (68,690 bytes) | `be64f8b9a2ab4f420cbe4acbd0087f987fbbe9ccf531d8fb7a3bcf82f8322496` (366,881 bytes): the GOAL-WORKBENCH-16 Pilot Designer |
| `workbench/index.html` | `05018e5c0a13219ddb70906b49c5637464f77356bd93b4852ff3e043b8073d3d` (38,076 bytes): the Workbench app page | `9a44f683c743a084b029644956ae19a9f513474acbc665c501e199af8f8b671b` (9,481 bytes): "Workbench is now part of the Pilot Designer", which links to `/ask-carbon/pilot-designer` and redirects there after 5 seconds |

The other 103 paths are byte-identical to production. They include the
homepage (`b1e8e7cd…`), the Q&A component, the knowledge (`fab55d5d…`) and the
remaining `workbench/` files, which stay so that saved drafts and bookmarks keep
working.

The Worker (`ask-carbon-public`) changes nothing a visitor sees. Its source,
knowledge and `wrangler.public-release-active.toml` are byte-identical to the
revision it was deployed from for WEB-QA-10-D1 (`368c713e`). Step 6 is in this
package because the owner's decision names it. It redeploys the same Worker.

## Prerequisites

- Node.js 18 or later (CI uses 24.19.0). No `npm install` is needed: the
  scripts and the Worker have no dependencies.
- `wrangler`, logged in to the Carbon Cloudflare account, as for WEB-QA-10-D1.

```sh
git clone --depth 1 https://github.com/carbonphysicsai/Carbon.git carbon-deploy
cd carbon-deploy/website/ask-carbon
OUT="$HOME/ask-carbon-86f51385"          # must not exist yet
BASE="$HOME/ask-carbon-baseline"         # must not exist yet
```

## 0. Capture the rollback targets (before anything else)

```sh
npx wrangler deployments status --name carbonwebsite
npx wrangler deployments status --name ask-carbon-public
```

Write both version ids down. **These captures are the rollback targets. Do not
take them from this document.**

- **What the repository expects for `carbonwebsite`:**
  `dc4469a7-f4da-4437-aaa1-2789277e57fc`. That is the WEB-QA-10-D1 deploy,
  captured by the owner on 2026-09-30.
- **What the owner's 2026-10-01 decision names:** `f7954cb2-b610-40f9-86e6-0a3fe6d04c93`.
  The repository records that id as the version *before* WEB-QA-10-D1. Rolling
  back to it would remove the live Pilot Designer `4c9f3916…` and knowledge
  `fab55d5d…`.
- If your capture shows something other than `dc4469a7`, stop and tell the
  owner before deploying.
- **Never use `b694b20f`.** It is withdrawn: it serves the v2 site, and rolling
  back to it would withdraw the v3 papers.
- **Do not touch the `AskCarbonUsageLedger` Durable Object.** It is never
  rolled back or deleted. A Worker rollback does not roll back Durable Object
  state.
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
  --require-complete-bundle > "$OUT.report.json"
grep -E '"bundle_identity_sha256"|"deployable_to_carbonwebsite"' "$OUT.report.json"
```

Required output: `"bundle_identity_sha256": "86f51385e05d6d2aca50c612b11f986916c74210c2bda96ac33ed41dcbc3d14a"`
and `"deployable_to_carbonwebsite": true`. Any other identity means stop.

## 3. Check the bundle against live before publishing

```sh
node tools/verify-publication.mjs --bundle "$OUT"
```

Before the deploy, exactly four lines must say `FAIL`:
`/workbench/` and `/ask-carbon/pilot-designer.html` on each hostname. Those are
the two changes. Every other line, including health, must be `ok`.

## 4. Publish the static site (command 1 of 2)

Run from `website/ask-carbon`, keeping compatibility date `2026-09-12`:

```sh
npx wrangler deploy --name carbonwebsite --assets "$OUT" --compatibility-date 2026-09-12
```

## 5. Verify the static publish

```sh
node tools/verify-publication.mjs --bundle "$OUT"
```

This checks, on **both** hostnames: `/`, `/workbench/`, all four
`/assets/*.png` (`logo-boeing`, `logo-usaf`, `og-carbon`, `x-logo`),
`/workbench/atlas-source.json` and `/ask-carbon/pilot-designer.html`, each
against the byte it should serve. It then checks `/api/ask-carbon/health` for
`active:true`, `reasons:[]` and `gemma-4-31b-turbo-tee:v1`. It must end with
`VERIFIED`. Also open `https://carbonphysics.ai/workbench/` in a browser: it
should show the moved notice and land on the Pilot Designer after about 5
seconds.

If any line fails, roll back the static site with the id captured in step 0:

```sh
npx wrangler rollback <carbonwebsite id from step 0> --name carbonwebsite
```

## 6. Activate the Worker (command 2 of 2)

```sh
npx wrangler deploy --config wrangler.public-release-active.toml
```

## 7. Verify the Worker

```sh
node tools/verify-publication.mjs --bundle "$OUT"
```

It must again end with `VERIFIED`. The health lines must read `active:true`,
`reasons:[]` and `gemma-4-31b-turbo-tee:v1` on both hostnames. If they do not,
roll back the Worker:

```sh
npx wrangler rollback <ask-carbon-public id from step 0> --name ask-carbon-public
```

## 8. Report back to the owner

Send these, so the deployment event can be recorded:
- the two version ids from step 0;
- the new `carbonwebsite` and `ask-carbon-public` version ids that wrangler
  printed;
- the `VERIFIED` output from step 7.

Last time the Worker ids never reached the repository.
