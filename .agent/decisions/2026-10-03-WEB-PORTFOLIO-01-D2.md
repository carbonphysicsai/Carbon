# WEB-PORTFOLIO-01-D2 — Compact eight-card portfolio

Owner revision: replace the overlong portfolio with one page containing each
problem, highlight, industrial use, surrogate time/dollar impact, customers and
visual. This supersedes D1's long disclosures and calculator presentation only.

Decision: eight static cards with code-native SVG concepts. Remove the filters,
expandable dossiers, calculator and strategy sections. Preserve the detailed
source context and existing tested full-workflow arithmetic off the visible page.

Economics boundary: show a transparent operating scenario for a model already
trained: 1,000 candidate cases, 20 final solver checks, 100 ms predictions and an
assumed $5/run-hour. These are serial run-hours/compute spend, not elapsed project
time, measured model capability, actual provider prices, customer savings or ROI.
Build, data, training, calibration and upkeep are excluded and visibly disclosed.
The strong optimized solver and cheap reduced model remain necessary baselines.

Source choices: roadmap f02/f04/f06/f08/f13/f17 estimates; motor scenario uses
60 angles times the f09 per-angle estimate; battery uses a labelled historical
30-cycle median. None is a fresh matched-resource benchmark. Existing cheap
challenges are not silently represented as expensive expanded tasks. Visuals are
concepts; customer categories are prospects, never logos or invented clients.

Implementation: `portfolio/highlights.mjs`, `visuals.mjs`, `render.mjs`, route
CSS/JS, deterministic build, focused tests and local preview. Reuse four local
brand assets only after checking their existing baseline hashes. No new runtime,
backend, model, tracking, deployment, economic allocation or scientific authority.
The release seam and proprietary website licence remain unchanged from D1.
