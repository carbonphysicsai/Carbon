# Carbon research portfolio page

Local investor-facing `/portfolio/` implementation for WEB-PORTFOLIO-01.
All eight programs are commercial research proposals; existing development
evidence is labelled, and no production or live-economic policy is changed.
Website content/source remains proprietary under `website/LICENSE`.

## Source and build

- `content.mjs`: all eight investment cases and immutable repository citations.
- `render.mjs`: semantic HTML, complete without JS; native details and anchors.
- `economics.mjs`: bounded cost arithmetic in integer cents.
- `../site/portfolio/portfolio.css` and `portfolio.js`: responsive UI, filters,
  deep links, expandable cases, local calculator and print expansion.
- `build.mjs`: deterministic HTML, copied economics module and draft additions
  manifest. A stale generated artifact fails focused tests and `--check`.
- `preview.mjs`: local preview and self-contained HTML; downloads only four
  existing brand assets, checks each against the baseline digest and refuses
  existing output paths. It cannot deploy or build an approved release.

From `website/ask-carbon`:

```sh
node portfolio/build.mjs
node portfolio/build.mjs --check
node --test tests/portfolio.test.mjs
npm test
npm run validate
npm run eval:contract
```

The page adds no backend, dependency, tracking, storage or model call. Calculator
assumptions remain in the browser. Costs are illustrative—not current prices,
forecast savings or approved budgets. The funding checkpoints are planning
questions, not scientific gates, live allocations or automatic spend authority.

## Review preview

```sh
node portfolio/preview.mjs --out /path/to/new-preview-dir --single-file /path/to/new-portfolio.html
```

The single-file artifact opens locally with its embedded brand/fonts and all
interactions. The directory version is for an HTTP static preview at
`/portfolio/`; other website routes link to the existing production site.

## Publication seam — pending owner acceptance

Do not add these bytes to the existing approved release or deploy them with its
old identity. `../portfolio-additions.candidate.json` is a draft, not an approval.
No existing homepage, investor page, sitemap, baseline or provider is changed.

Before publishing:

1. Accept the public wording and confirm the proposed portfolio framing.
2. Inspect the current live site and approved/pending additions; re-derive the
   reviewed baseline rather than assuming the 2 October manifest is current.
3. Add reviewed Portfolio links to the desktop/mobile/footer navigation and
   investor/homepage entry points; add `/portfolio/` to the English sitemap.
   Preserve unrelated content, Chinese routes and Ask Carbon behavior. Local
   page controls and content are English-only; no translation is claimed.
4. Combine the four new additions with any independently approved unpublished
   additions, pin all changed bytes and derive a new exact release candidate
   using `tools/integrate-static.mjs`. Existing release identities are invalid
   for a bundle containing new files or navigation changes.
5. Run applicable CI and browser checks on that exact candidate. Obtain the
   production content/release/deployment decision, capture the actual rollback
   version, publish by the established process and verify both hostnames.

No live reference experiments or fixed-resource design competitions ran for
this page. UI tests, mock calculations, dry runs and previews are not scientific,
security, commercial or production qualification.
