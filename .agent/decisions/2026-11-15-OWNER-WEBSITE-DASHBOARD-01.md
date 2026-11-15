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

**Limits.** The homepage, Customers, Validators, Investors, About, Technical
Papers and Workbench pages are served from the live baseline, not from
repository sources, so their headers do not yet show Dashboard. This records a
content instruction; it does not authorize deployment. Publication still needs
the owner's approval of an exact bundle, as for OWNER-WEBSITE-START-MINING-01.
