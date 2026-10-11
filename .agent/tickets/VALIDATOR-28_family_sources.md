# VALIDATOR-28: reference family sources

**Owner:** Carbon Validator. **Plan:** the bank startup plan's item 4 (the
Test Lead's), as `SOURCE_ADAPTER_PLAN.md` on the operator share sets it out.
Data Collection writes each family's adapter (cooling cell, then f02, f13,
f06, f08, f17), and the Carbon Validator builds the interface and reviews
each adapter.

**Aim.** One producer source interface, generalized from motor's
(VALIDATOR-21), so that a new Challenge whose hidden batches are a population
draw and a reference solve is served by registering values, not by new
producer code.

## Slices

1. **The family source (this PR).**
   - `family_source.ReferenceFamily` is a frozen registration. It holds the
     population, the runner and pinned image under one CLI contract, the
     terminal statuses, the document and record checks, and the registered
     rule values. None has a default, so an unset value fails closed.
   - `family_source.FamilySource` is motor's source logic, extracted
     unchanged and parameterized by the registration.
   - `MotorBatchSource` becomes `FamilySource` with `motor_family()`.
   - `producer.source_for` looks families up in one registry
     (`family_source_class`) instead of a motor branch. Battery keeps its
     own source, because of its quiz and duplicates.
   - **Parity:** motor's own suite (`test_challenge_validator_motor_hidden.py`)
     runs unchanged through the extracted source.
2. **The family's bank (VALIDATOR-23).**
   - `FamilyBankSource` draws a tranche from the family's custody root by
     role, through its population. Published cases are refused.
   - `FamilySource.bank()` and `fill_tranche()` solve and seal a tranche
     through the family's runner, under the batch contract and resumably.
   - So a registered family is bankable. Its window rule values (B, E) stay
     the family owner's to register, and a startup host's sharding follows
     in a later slice.
3. **The validator's import (#883).** `family_hidden.FamilyHiddenImport`
   and `HiddenFamily` cover answer-key import, holds, withdraws, status, the
   per-hotkey window and the import-only refusals, generalized from
   `motor_hidden`. Scoring stays each family's own.
4. **A conformance kit** (`tests/cpu/family_conformance.py`): a family's
   test module calls `check_family` (or each of `CHECKS`) with its
   registration, validator, deployment writer and scripted runner. Motor is
   the reference (`test_challenge_validator_family_conformance.py`). It
   proves:
   - determinism by role;
   - published-case refusal;
   - resumable solve;
   - check refusals;
   - a sealed package that a validator verifies and imports;
   - a bank tranche fill.

   A family is reviewable when its conformance test passes.

## Bounds

- **No change to what motor commits.** Its documents, fingerprints, journal
  entries, references digests and refusal codes stay the same.
- **No new family values.** Each family's rule values (cadence, n, B, E) are
  registered by its owner, and stay unregistered (fail closed) until then.
- DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
