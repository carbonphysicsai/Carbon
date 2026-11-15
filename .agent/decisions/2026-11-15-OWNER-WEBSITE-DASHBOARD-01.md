## 2026-11-15 — OWNER-WEBSITE-DASHBOARD-01: the miner page's hero button goes to the dashboard, and Dashboard joins the top navigation

**Owner, verbatim, in session on 2026-11-15:** "Change the Vermillion CTA button
on the hero section to [Start Mining Carbon] Then update the link to:
https://dashboard.carbonphysics.ai/#/mine I would also like to add Dashboard to
the top Navigation bar. I'm not sure if it should go under the Explore Carbon
dropdown or have it's own spot on the bar? Dashboard can link to:
https://dashboard.carbonphysics.ai/"

**Content change (repository sources only).**

- `website/ask-carbon/site/miners/index.html`: the hero button reads
  "Start Mining Carbon" and links to `https://dashboard.carbonphysics.ai/#/mine`
  (was "Start mining", to `/start-mining/`).
- Placement, chosen by the agent because the owner asked for a recommendation:
  Dashboard is its own top-level link, directly after the Explore Carbon
  dropdown. The dropdown groups audience pages (Customers, Miners, Validators);
  Dashboard is a product destination for every audience, so it is not hidden
  behind it. The mobile menu lists it after Validators.
- The same header change is applied to `site/start-mining/index.html`, the
  other repository page that carries this header.
- `site-replacements.json` and `site-additions.json` pin the new digests.

**Owner, verbatim, later the same session:** "Yeah I want it on the nav bar of
every page" and "They should be in Cloudflare?"

**Live has diverged from the repository.** On 2026-11-15 every live HTML page
differed from manifest v4 and from candidate 2026-10-02.1: live adds a
Challenge Portfolio nav link, an EN / 中文 switch, `/portfolio/`, `/zh/` and
`/zh/portfolio/`; `/start-mining/` returns 404 and the miner hero still reads
"Start a development run". None of that live source is in any branch found. The
repository's `site/` copies and release manifest therefore do not describe live,
and building a bundle from them would revert those live changes.

**What was produced instead.** The twelve live HTML pages (home, 404, About,
Customers, Investors, Miners, Technical Papers, Challenge Portfolio,
Validators, Workbench, `/zh/`, `/zh/portfolio/`) were fetched from
carbonphysics.ai, the Cloudflare edge injections removed with
`tools/fetch-live-baseline.mjs`'s `removeEdgeInjections`, and only these edits
applied, checked by reversing them back to the stripped live bytes:

- English pages: Dashboard after Explore Carbon (desktop) and after Validators
  (mobile menu). Miners hero: "Start Mining Carbon" to
  `https://dashboard.carbonphysics.ai/#/mine`, with the up-right arrow.
- Chinese pages: 仪表盘 after 资料库 in the desktop and mobile navs.
- `site.css`: live bytes unchanged plus one appended block, in the form of the
  existing Challenge Portfolio block, so the six-link header stays on one line:
  compact spacing up to 1400px, 14px type up to 1260px, tighter spacing up to
  1160px, Menu sheet up to 1100px (was 1020px). Checked in Chromium every 2px
  from 1090px to 1608px and every 10px from 800px; no item wraps.

**Owner, verbatim, on how the site is deployed:** "Yeah I'm pretty sure we have
uploaded to replace the whole site. I'm open to a better way though. Guided by
you on this"

**Source of truth (agent's choice, as invited).** The complete live site is now
kept at `website/carbonwebsite/site/` (178 files, identical to live before this
change, checked with `website/carbonwebsite/tools/compare-live.mjs`). Site
changes are made there by pull request and deployed from that folder with the
same `wrangler deploy --assets` form used before; the folder's README gives the
steps and rollback. The Dashboard change is a separate commit on top of the
snapshot touching exactly the twelve pages and `site.css` above. The earlier
edits to the outdated `website/ask-carbon/site/` copies were reverted; those
records stay as October history.

**Limits.** Not deployed: deploying is the owner's action. Cloudflare cannot
list the files a Worker serves, so a live file nothing links to would not be in
the snapshot and a whole-site deploy would remove it; of the October manifest's
100 files, 99 were found and the other already returned 404.
