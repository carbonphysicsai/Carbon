# carbonphysics.ai

`site/` is the complete public website, exactly as Cloudflare serves it from
the `carbonwebsite` static-assets Worker. It is the source of truth: change the
site here, by pull request, and deploy this folder. Do not upload site files
any other way, or the next deploy from here will silently undo that change.

The Ask Carbon API is a separate Worker (`ask-carbon-public`, in
`website/ask-carbon/`). Deploying this folder does not touch it.

## Change a page

Edit the files under `site/` and open a pull request. The diff is the change a
visitor will see. Shared pieces (header, footer, menus) are copied into each
page, so a header change touches every `index.html`, `404.html`, and the two
`zh/` pages, which have their own Chinese header.

## Deploy

Needs Node.js 18+ and `wrangler` logged in to the Carbon Cloudflare account.
From the repository root, on the merged `main`:

1. Write down the current version, which is your rollback target:

   ```sh
   npx wrangler deployments status --name carbonwebsite
   ```

2. Check what will change. Every file listed must be one your change meant to
   edit. Anything else means live was changed outside the repository; stop,
   bring that change into `site/` first, then continue.

   ```sh
   node website/carbonwebsite/tools/compare-live.mjs
   ```

3. Deploy. This replaces the whole site with `site/`:

   ```sh
   npx wrangler deploy --name carbonwebsite --assets website/carbonwebsite/site --compatibility-date 2026-09-12
   ```

4. Confirm live now matches the folder (prints `all identical`):

   ```sh
   node website/carbonwebsite/tools/compare-live.mjs
   ```

Rollback: `npx wrangler rollback <version id from step 1> --name carbonwebsite`.

## Where `site/` came from

On 2026-11-15 the live site no longer matched any copy in this repository (it
had gained Challenge Portfolio, the Chinese pages and the EN / 中文 switch
outside it). `site/` was rebuilt from live: every path in the October baseline
manifest (`website/ask-carbon/production-baseline.manifest.json`), the sitemap,
and every page, stylesheet, script, image and font those files reference, 178
files in all. Cloudflare's edge additions were removed: the bot-challenge
script and Web Analytics beacon in HTML, and the managed block Cloudflare puts
in front of `robots.txt` (the recovered `robots.txt` matches the October
manifest byte for byte). Every page was then loaded from this folder alone in
Chromium, desktop and phone, with no missing file.

Cloudflare offers no way to list the files a Worker serves, so a file that live
serves but nothing links to cannot be found this way. Of the October manifest's
100 files, 99 are here; `assets/team-harshdeep.webp` already returned 404 on
live.

`compare-live.mjs` checks every file in `site/` against live. It cannot see a
file that exists only on live, for the same reason.

The Ask Carbon release records under `website/ask-carbon/` (baseline manifest,
`site-replacements.json`, `site-additions.json`, `site/`) describe the site as
of October 2026 and are history for the live site.
