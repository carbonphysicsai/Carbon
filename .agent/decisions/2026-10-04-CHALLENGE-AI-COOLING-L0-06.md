# CHALLENGE-AI-COOLING-L0-06 — bounded Level-0 implementation decisions

**Date:** 2026-10-04

**Authority:** delegated engineering choices within
OWNER-GRAPHITE-TEST-WAVE-01 and OWNER-LAUNCH-PORTFOLIO-02. No scientific,
security, spend, qualification or LIVE authority is exercised here.

## Decision

Register the existing public cold-plate kernel-ridge reconstruction as the
only Level-0 family. Expose only the published calibration-grid choices for
kernel length and ridge, with the public calibration winner as the default.
Represent those finite values as stable canonical tokens at the declarative
boundary (`length_8`, `ridge_1e_6` for the default), and publish their exact
numeric mapping; the guarded compiler performs the conversion after validation.
Bind construction to the pinned public TRAIN artifact and the existing pinned
CPU carrier. Keep the attack budget and evaluator-held fresh confirmation
population unpinned.

## Rationale

This is the smallest contract Carbon can genuinely rebuild today. It reuses
the learned model that the counted periodic-cell study actually evaluated,
gives Graphite meaningful bounded construction freedom, and introduces no new
physical values or hidden-evidence access. A wider neural-operator, optimizer,
data or executable-program surface would be new engineering/scientific scope
and is therefore not implied by the long-term ontology.

## Consequences

- Graphite discovery and compilation can reach cooling through the same
  Challenge-neutral seams as battery.
- Every accepted strategy deterministically reconstructs from public material.
- No accepted strategy can access the counted CFD campaign or a future sealed
  confirmation set.
- The admission sheet remains `DRAFT_NOT_FROZEN` until owners supply the
  attack budget and fresh confirmation authority.
- PB-ADV, Track B, validator/scoring and confirmation-set work remain separate
  tickets and PRs.
