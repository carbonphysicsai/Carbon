# BATTERY-NEUTRAL-VERIFY-01 — public DEVELOPMENT neutral-path verification

**Status:** bounded verification complete; PR acceptance pending

**Authority:** the owner's three-Challenge DEVELOPMENT wave and its explicit
Battery verification instruction; `VALIDATOR-01_challenge_neutral_validator.md`
Interface v1; `CONSTITUTION.md`; `.agent/INVARIANTS.md`; current
`.agent/DELIVERY_PROTOCOL.md`.

**Base:** `d12b14f79e095f0e2adf80b0c7eba289d22378be` (main after Motor
Interface-v1 PR #706). One ticket, one PR.

## Outcome

Record whether Battery's existing `BatteryAdapter` still replays published
DEVELOPMENT examples through the Challenge-neutral validator on current main,
with its pinned rule/contract, protected-role refusals, disclosure boundary,
typed unavailability and infrastructure failures. Report the exact evidence
and readiness ceiling. Repair only a concrete regression found by this check.

## Scope and working decisions

1. KEEP Battery's validator, exam, deployment, live contract and sealed evidence
   unchanged. This is a read-only canonical regression of the existing path.
2. Use the checked-in published exam-design examples that the existing tests
   explicitly opt into. Do not access EV5's sealed batch, journal sequence 14,
   a fresh hidden set, or customer/private cases.
3. Keep test success distinct from scientific qualification, production worker
   isolation and Graphite readiness. Current readiness records remain
   authoritative; this ticket does not flip them.
4. Persist a small digest-bound verification report and the execution lesson.
   This is a DEVELOPMENT evidence record, not a new scoring rule, code seam,
   official result or retrigger-only evidence commit.

## Acceptance

- [x] Canonical Battery neutral replay, contract/scoring boundary and readiness
      tests run at the stated source commit, with exact command and count.
- [x] Report distinguishes what the tests exercise from worker isolation,
      protected evaluation and unresolved readiness/owner reviews.
- [x] No EV5, sealed journal, live contract, protected labels or scoring
      implementation is changed.
- [ ] The execution lesson validates and required PR checks pass.

**Evidence:** `docs/development/evidence/battery-neutral-path-verification-2026-10-06/README.md`.

## Maturity ceiling

At most TESTED for Battery's bounded neutral DEVELOPMENT path on published
examples. Not scientific, security, network, customer or LIVE qualification.
