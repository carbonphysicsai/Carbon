# Carbon research portfolio page

Compact investor-facing `/portfolio/` review candidate for WEB-PORTFOLIO-01.
Eight cards, each containing the problem, highlight, industrial use, physical
outcome to prove, conditional value at scale, customer targets and a concept visual.
One compact future model-versus-solver automated design-contest section follows.
No dossiers, filters, calculator, tracking, backend, storage or model calls.
The programs are proposals, not eight live products or new emission allocations.
Website content/source remains proprietary under `website/LICENSE`.

## Source and build

- `highlights.mjs`: concise cards and retained off-page historical timing context.
- `impact.mjs`: conditional economic/physical sensitivities, not savings forecasts.
- `solver-preview.mjs`: local finite-difference/conjugate-gradient illustration of
  a dimensionless steady 2D heat equation with a manufactured analytical control.
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

The old 1,000-case compute-savings figures and assumed latency are no longer on
the page. Scale examples instead convert an explicitly hypothetical physical
improvement into its value at a stated scale: electrical demand to annual energy
cost; throughput to accelerator-equivalents; percentage-point pass-rate gain to
devices; charge-time reduction to daily dwell; unit cost to manufacturing spend;
flow-rate gain to fixed-volume processing time. Prototype rounds deliberately
have no invented price or duration. None is a performance target, achieved gain,
actual tariff, customer quote or ROI. Net value needs data, training, verification,
integration, serving and upkeep. Operational claims need separate validation.
Customer categories are targets, not clients; card visuals are concepts.

The contest preview contains an actual locally solved public analytical test
field, not a cold-plate benchmark, optimization run, physical experiment, model
result or contest winner. Its matrix residual and refinement are checked. The
model panel is empty. The prospective comparison would require strong automated
solver/reduced-method baselines, common design bounds/constraints and fixed compute
and wall-clock budgets, independently checked final designs, and preparation plus
model-build/search costs. This page selects no production scientific contract.

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

No live challenge/physical experiment or matched-resource contest ran here.
Only the public synthetic numerical illustration and local UI checks were run.
UI diagnostics and illustrative arithmetic are not scientific, security,
commercial or production qualification.
