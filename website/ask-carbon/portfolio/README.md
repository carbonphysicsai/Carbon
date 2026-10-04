# Carbon research portfolio page

Compact investor-facing `/portfolio/` review candidate for WEB-PORTFOLIO-01.
Eight cards, each containing the problem, highlight, industrial use, illustrative
surrogate screening impact, customer target categories and a concept visual.
No dossiers, filters, calculator, tracking, backend, storage or model calls.
The programs are proposals, not eight live products or new emission allocations.
Website content/source remains proprietary under `website/LICENSE`.

## Source and build

- `highlights.mjs`: concise cards and explicit trained-model screening arithmetic.
- `visuals.mjs`: eight accessible, distinct code-native SVG concept illustrations.
- `content.mjs`: retained investment context and immutable repository citations.
- `render.mjs`: complete semantic HTML with no JavaScript dependency.
- `../site/portfolio/portfolio.css` and `portfolio.js`: responsive layout; the
  tiny JS only retires the old review-page calculator anchor.
- `economics.mjs`: retained, tested whole-workflow utility, not visible-page UI.
- `build.mjs`: deterministic HTML/module and a draft additions manifest.
- `preview.mjs`: self-contained local HTML with four verified brand assets.

From `website/ask-carbon`:

```sh
node portfolio/build.mjs
node portfolio/build.mjs --check
node --test tests/portfolio.test.mjs
npm test
npm run validate
npm run eval:contract
```

Savings are an explicit operating illustration: 1,000 candidate cases, 20 final
solver checks, 100 ms predictions and an assumed $5/run-hour for a model already
trained. They are serial run-hours and compute spend, not elapsed project time,
current cloud prices, measured Carbon performance or total ROI. Build, data,
training, calibration and upkeep are excluded. Solver times are roadmap estimates
or labelled historical evidence. Optimized solvers and cheap reduced baselines
can erase the advantage. Customer categories are targets, never claimed clients.

## Review preview

```sh
node portfolio/preview.mjs --out /path/to/new-preview-dir --single-file /path/to/new-portfolio.html
```

Optionally reuse an existing preview's four brand assets with `--assets-from
/path/to/existing-preview-dir`; their hashes still must match the reviewed
baseline. Existing bounded review outputs can be refreshed with the explicit
`--refresh-local-preview` flag. The self-contained HTML opens with embedded fonts,
brand and visuals via `file://` without a server or network connection.

## Publication seam — pending owner acceptance

The additions manifest is a draft, not a release approval. The live homepage,
investor page, sitemap, approved baseline, release and providers are unchanged.
Before publication, accept the wording, reconcile the current site and pending
additions, add reviewed Portfolio navigation/sitemap entries, pin all changed
bytes into a new exact release candidate, run applicable checks and follow the
established owner-approved deployment/rollback process. Do not reuse an existing
release identity for new bytes. English-only page; no translation is claimed.

No live numerical/physical experiment or matched-resource contest ran here.
UI diagnostics and illustrative arithmetic are not scientific, security,
commercial or production qualification.
