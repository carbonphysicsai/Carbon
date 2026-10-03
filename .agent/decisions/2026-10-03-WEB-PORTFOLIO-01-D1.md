# WEB-PORTFOLIO-01-D1 — Static research portfolio, separate publication decision

Owner request: the investor-facing eight-program portfolio page, with economic
rationale, future design competitions, industry expansions and miner-resource
discipline. This is reversible local engineering, not live publication.

Decision: KEEP the existing static website and additions guard. Add a bounded
`/portfolio/` source, deterministic generated HTML, isolated styles, a small
progressive-enhancement module and a client-only illustrative cost calculator.
Keep the approved additions, replacements, live manifest, provider and release
decision unchanged. Generate a separate draft additions candidate.

Why: a new page is possible without altering the site's release authority or
introducing a framework, service, analytics, mutable investor metrics or private
exam material. Static details remain readable without JavaScript; source data
owns all eight public investment cases and their limits.

Alternatives rejected: a new hosted Site (different deployment plane); a new SPA
(unnecessary dependency/runtime cost); invented economic dashboards or a mock
solver leaderboard (no evidence); direct production deployment (not authorized).

Boundaries: proposed customer programs do not replace the technical queue or
adopted commercial canon. Investor fit is 25% of qualitative planning, never a
scientific grade or emissions formula. No scientific limits, allocation,
buyback operating terms, prices, revenue or qualification are selected here.
Website remains proprietary under OWNER-LICENSE-01.

Change path: `website/ask-carbon/portfolio/content.mjs`, `render.mjs`,
`site/portfolio/portfolio.css`, `portfolio.js` and their focused tests. Regenerate
HTML/module/additions digests with `node portfolio/build.mjs`. Rollback is removal
of the four proposed route files from a future reviewed bundle; current live
site has not changed. No runtime dependency or protocol migration follows.

Human input remains: public-content acceptance, current baseline/navigation/
sitemap reconciliation and exact release/deployment authority. No external lead
message was sent; this local handoff is visible directly to the requesting owner.
