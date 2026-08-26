# Ticket B-E1 - R0/R1/R2 reproducibility harness

**Wave:** B candidate
**Status:** todo
**Depends on:** B-02A, B-02B, B-04, B-05
**Build Out:** Wave B evidence harness
**Master questions:** MQ-007, MQ-008
**Authority:** `SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md` §§6-11; `Evaluation_Evidence_and_Validator_Audit.md`

## Goal

Provide fixture machinery for distinguishing exact identity, numerical reproducibility, and decision reproducibility without inventing tolerances.

## Definition of Done

- [ ] Represent R0 exact artifact/configuration identity, R1 numerical comparison, and R2 decision comparison as separate results.
- [ ] Define repeated reconstruction-seed by evaluation-seed experiment matrices and exact evidence provenance.
- [ ] Represent resolved, unresolved/indeterminate, reference-failed, reconstruction-failed, and infrastructure-failed outcomes.
- [ ] Define typed contested-outcome plumbing without implementing frontier promotion.
- [ ] Inject all tolerances, sample sizes, and power criteria; missing values fail closed.
- [ ] Add deterministic fixture, variance, ordering, missing-evidence, hardware-profile, and failure-class tests.

## Human input

SciML/statistics owners derive numerical and decision tolerances, sample sizes, minimum resolvable improvement, and supported backend profiles.

## Must not

Treat exact bits as universal reproducibility, use arbitrary epsilons, rank inside an unresolved interval, or create a frontier event.
