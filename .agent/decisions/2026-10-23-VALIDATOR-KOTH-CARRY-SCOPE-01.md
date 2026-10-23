# VALIDATOR-KOTH-CARRY-SCOPE-01: the scope of OWNER-KOTH-CARRY-ACROSS-VERSIONS-01, and a version-neutral pack-set key

Date: 2026-10-23
Status: RECORDED by the Carbon Validator. It corrects the Validator's own wording in OWNER-KOTH-CARRY-ACROSS-VERSIONS-01; it changes no owner decision.
Relates to: OWNER-KOTH-CARRY-ACROSS-VERSIONS-01, which stays unchanged as the record, and OWNER-EXAM-CAP-ROTATION-01 (2026-10-19).

## Correction

The owner's answer "carries over" (OWNER-KOTH-CARRY-ACROSS-VERSIONS-01) was to one question: does the king carry over across construction versions of the same sealed exam?

That record's "Decided" item 3 adds that the king resets when "the sealed pack set changes (… a rotation), as today". **That clause was the Validator's own wording, and it is wrong.** OWNER-EXAM-CAP-ROTATION-01 already decides rotation:
- each rotation **regrades the king** on the new pack (a REGRADE slot that never counts toward the cap);
- the result is filed under the king's submission id on the new key;
- the king therefore carries through rotation.

**OWNER-EXAM-CAP-ROTATION-01 governs rotation.** Item 3 of the carry record applies only to a change of the sealed **evaluation version**: a new exam definition, where scores are not comparable.

## The rule, as implemented

1. **A construction-version change on the same evaluation version and the same pack set:** the king carries (OWNER-KOTH-CARRY-ACROSS-VERSIONS-01).
2. **A pack rotation on the same evaluation version:** the king is regraded on the new pack and carries (OWNER-EXAM-CAP-ROTATION-01).
   - Where a regrade is unavailable, for example the known graph-recipe gap, the comparison is UNAVAILABLE, as that record states. It is not a reset.
3. **A change of the sealed evaluation version:** the king resets, because the scores are not comparable (§7.6).

## The pack-set key is version-neutral

The pack-set key identifies the exam, so it must not name the construction version.

- **Key:** sha256 over the canonical form of {challenge_id, sealed evaluation_version, the ordered list of the batches' canonical manifest digests (M_c)}.
- This is the same canonical identity as the E4 ruling: every validator's copies share it.
- **Migration:** keys are derived again **prospectively**. Existing DEVELOPMENT pack-set records keep their stored keys and are read through a recorded map, never rescored.
