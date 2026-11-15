# carbonphysics.ai

`site/` is the complete public website, exactly as Cloudflare serves it from
the `carbonwebsite` static-assets Worker. It is the source of truth: change the
site here, by pull request, and deploy this folder. Do not upload site files
any other way, or the next deploy from here will silently undo that change.

The Ask Carbon API is a separate Worker (`ask-carbon-public`, in
`website/ask-carbon/`). Deploying this folder does not touch it.

The Chinese pages under `/zh/` are also a separate Worker,
`carbon-zh-preview` (routes include `zh-preview.carbonphysics.ai` and
`carbonphysics.ai/zh/`), whose source is not in this repository. They are not in
this folder, deploying it does not change them, and `compare-live.mjs` skips
`/zh/`. The English pages' EN / 中文 switch links to them.

## Change a page

Edit the files under `site/` and open a pull request. The diff is the change a
visitor will see, and merging it publishes it. Shared pieces (header, footer,
menus) are copied into each page, so a header change touches every
`index.html` and `404.html`.

## Deploy

Merging a change to `site/` into `main` deploys it automatically
(`.github/workflows/website-deploy.yml`). The workflow:

1. checks that live is still what `main` held before this change. If someone
   changed live outside the repository, it stops rather than erase that change,
   and lists the files that differ;
2. records the version live was on (the rollback target, in the run summary);
3. deploys this folder, replacing the whole site;
4. confirms live now matches the folder.

You can also run it by hand from the Actions tab ("Website deploy"), for
example to retry a failed deploy. Its `overwrite_live_changes` option deploys
even when live has changes the repository lacks, which discards them.

### One-time setup

1. In Cloudflare, create an API token (My Profile → API Tokens → Create Token →
   "Edit Cloudflare Workers" template), limited to the Carbon account.
2. In GitHub, Settings → Environments → New environment, named
   `carbonwebsite-production`. Add the token there as the secret
   `CLOUDFLARE_API_TOKEN`.
3. Optional: in the same environment, add yourself under "Required reviewers".
   Each deploy then waits for your approval in the Actions tab.

Until the secret exists, the deploy step fails with a message saying so;
re-run it once the secret is added.

### Deploy by hand

Needs Node.js 18+ and `wrangler` logged in to the Carbon Cloudflare account.
From the repository root, on the merged `main`:

1. Write down the current version, which is your rollback target:

   ```sh
   npx wrangler@4.151.3 deployments status --name carbonwebsite
   ```

2. Check what will change. Every file listed must be one your change meant to
   edit. Anything else means live was changed outside the repository; stop,
   bring that change into `site/` first, then continue.

   ```sh
   node website/carbonwebsite/tools/compare-live.mjs
   ```

3. Deploy. This replaces the whole site with `site/`:

   ```sh
   npx wrangler@4.151.3 deploy --name carbonwebsite --assets website/carbonwebsite/site --compatibility-date 2026-09-12
   ```

4. Confirm live now matches the folder (prints `all identical`):

   ```sh
   node website/carbonwebsite/tools/compare-live.mjs
   ```

Rollback: `npx wrangler@4.151.3 rollback <version id> --name carbonwebsite`.

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
Chromium, desktop and phone, with no missing file. The 62 files under `zh/`
were later removed: the first deploy showed `/zh/` is served by the
`carbon-zh-preview` Worker, so 116 files remain.

Cloudflare offers no way to list the files a Worker serves, so a file that live
serves but nothing links to cannot be found this way. Of the October manifest's
100 files, 99 are here; `assets/team-harshdeep.webp` already returned 404 on
live.

`compare-live.mjs` checks every file in `site/` against live. It cannot see a
file that exists only on live, for the same reason.

The Ask Carbon release records under `website/ask-carbon/` (baseline manifest,
`site-replacements.json`, `site-additions.json`, `site/`) describe the site as
of October 2026 and are history for the live site.
