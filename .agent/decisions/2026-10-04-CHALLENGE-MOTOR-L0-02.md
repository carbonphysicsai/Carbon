# CHALLENGE-MOTOR-L0-02 — bounded Level-0 implementation decisions

**Date:** 2026-10-04

**Authority:** delegated engineering choices within
OWNER-GRAPHITE-TEST-WAVE-01 and OWNER-LAUNCH-PORTFOLIO-02. No scientific,
security, spend, qualification or LIVE authority is exercised here.

## Decision

Register the existing public Motor kernel-ridge reconstruction as the only
Level-0 family. Expose only the published calibration-grid choices for kernel
length and ridge, with the public calibration winner as the default. Represent
those finite values as stable canonical tokens at the declarative boundary
(`length_4`, `ridge_1e_4` for the default), and publish their exact numeric
mapping; the guarded compiler performs the conversion after validation. Bind
construction to the pinned public TRAIN artifact and the existing pinned CPU
carrier. Keep the attack budget and evaluator-held fresh confirmation
population unpinned.

## Rationale

This is the smallest contract Carbon can genuinely rebuild today. It reuses
the learned model already registered in Motor's public baseline and frozen
decision study, gives Graphite meaningful bounded construction freedom, and
introduces no new physical values or hidden-evidence access. Wider neural
models, optimizers, data surfaces or executable programs are new scope and are
not implied by the long-term construction ontology.

## Consequences

- Graphite discovery and compilation can reach Motor through the same
  Challenge-neutral seams as battery and cooling.
- Every accepted strategy deterministically reconstructs from public material.
- No accepted strategy can access the private 60-case pool, decision-study
  references or a future sealed confirmation set.
- The admission sheet remains `DRAFT_NOT_FROZEN` until owners supply the
  attack budget and fresh confirmation authority.
- Track B, validator/scoring, confirmation-set and counted reference work
  remain separate tickets and PRs.
