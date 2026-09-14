# GOAL-WORKBENCH-03 next-integration handoff

## One recommended interface

Add a versioned, source-owned Measurement/ScorePack diagnostic response reader to the existing workbench handoff boundary.

## Why this is next

The supported Burgers path already preserves native authoring semantics, but its eight prospective score-behavior checks remain `NOT_EXECUTED`. A bound response closes the earliest evidence gap shared by requirement alignment, case coverage, reference adequacy, and later qualification review. It is more decision-relevant than automating Grok, CRM, calendar, or launch transport while the numerical meaning remains unresolved.

## Minimum request/response contract

- Exact request ID, job ID, design ID, and design revision.
- Source implementation/version and artifact digest.
- Per-example status for peak miss, smoothing, mandatory failure, nonfinite/withheld output, dropped work, unit/floor error, below-uncertainty improvement, and persistence/memorization where applicable.
- Actual implementation layer, environment/scope, limitations, missing/censored work, and `NOT_EXECUTED` preservation.
- Closed parsing, duplicate/conflict detection, stale/wrong-design rejection, and no authority-bearing fields without a trusted source-owned verifier.

## Owner and stop boundary

Native owner: Measurement and ScorePack authoring/qualification interface owner. The workbench owner may implement only the additive reader after that owner supplies an accepted versioned result contract or fixture. Do not emulate the scorer, select thresholds, alter weights, run protected material, or infer qualification.

Restart event: an accepted source-owned diagnostic result schema and one public/synthetic fixture bound to the existing diagnostic request.

Until then, the route remains manual and `NOT_EXECUTED`. No polling is required.
