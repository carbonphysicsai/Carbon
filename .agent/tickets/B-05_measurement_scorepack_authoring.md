# Ticket B-05 - MeasurementContract and Score Pack authoring bindings

**Wave:** B candidate
**Status:** todo
**Depends on:** B-04
**Build Out:** C5 Wave B authoring seam
**Master questions:** MQ-005, MQ-006
**Authority:** `Scoring.md`; `SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md` §§7-8

## Goal

Make measurements and their evidence-use roles explicit before A5 executes any production-shaped scoring policy.

## Definition of Done

- [ ] Before implementation, produce
      `Design_Specs/Measurement_and_ScorePack_Authoring_Contract.md`, obtain
      independent SciML/statistics/protocol review and explicit human
      ratification, and merge that contract normally; record the exact contract
      commit in the implementation plan.
- [ ] Define exact `MeasurementContract` identity, applicability, observable, discretization, sampling, normalization, aggregation, precision, tolerance/uncertainty, and implementation refs.
- [ ] Bind measurement outputs to Score Pack eligibility, admissibility, estimand, stratum, uncertainty, aggregation, ranking, and disclosure roles.
- [ ] Preserve mandatory admissibility before soft aggregation.
- [ ] Reject partial, non-finite, inapplicable, reference-failed, and uncertainty-unresolved measurement material through typed paths.
- [ ] Keep A5 as deterministic engine and prevent it from inventing physical thresholds or weights.
- [ ] Add fixture authoring, hash/pin, role-confusion, forbidden-input, and fail-closed tests.

## Human input

SciML/protocol owners approve real measurements, applicability, gates, tolerances, transforms, strata, and weights from Dossier evidence.

## Must not

Promote fixture thresholds, treat a diagnostic as a full PDE residual, compensate a mandatory failure, or allow mock/prior/resource fields into score.
