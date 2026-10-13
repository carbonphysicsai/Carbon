# Scoring and validator producer evidence for `readiness`

READINESS-GAPS-01 adds automated checks while preserving `NOT_BUILT` for a Challenge with no registered study. The files below are **formats for future operator evidence**, not evidence that any Challenge has passed. No hidden case, reference margin, seed, or producer panel belongs in this repository or its tests.

## S3: margin study

Register `carbon/challenge_pipeline/readiness/<challenge>/gate-margin-registration.json` with schema `carbon.readiness.gate-margin-registration.v1`, the Challenge token, the exact `sha256:` **file digest** of the private panel, and the complete gate list. Each gate names its margin unit and an owner-registered `fragile_below` boundary in that unit. There is no default. The private `carbon.readiness.gate-margin-panel.v1` panel has `challenge` and `margins`, a map from every registered gate to its list of finite reference margins. These are already measured margins, positive toward passing. The checker refuses missing, extra, empty or non-finite rows and computes the observed minimum, linearly interpolated empirical first percentile, and `fragile = minimum <= fragile_below` for every gate. It does not decide whether a fragile flag blocks promotion; that belongs to the Test Lead.

## H2: tuning and other roles

Register `carbon/challenge_pipeline/readiness/<challenge>/tuning-overlap-registration.json` with schema `carbon.readiness.tuning-overlap-registration.v1`, the Challenge token, the private panel's exact `sha256:` file digest, one `tuning_role`, and exhaustive `sealed_roles` and `unsealed_roles` lists. Their union with the tuning role must equal **every role for that Challenge** in `carbon/challenge_validator/confirmation_sets/registry.json`; each role document's registry digest is verified. An operator must classify sealed versus unsealed against the custody journal before registering this file. The private `carbon.readiness.tuning-overlap-panel.v1` panel has `challenge` and `groups`: one list of distinct base-case input objects for the tuning role, each declared sealed role, and exactly `rotating_pool`, `TRAIN`, `PRACTICE`, `practice_decision`. The check compares canonical input objects in memory, refusing duplicates within a group or any overlap across groups. It reports only group and case counts, registration and panel digests, or a generic refusal code. It never prints an input, case ID, seed, or overlap witness.

These checks verify the **registered roster supplied to them**. A complete producer custody journal and correct public-source extraction remain prerequisites to a trustworthy real-panel H2 result; a fabricated roster cannot be detected from a stand-alone file. Registration or toy tests alone never earn a real-panel PASS.

## Read-only producer invocation

From the producer's development checkout, with both private panels outside the repository:

```sh
python -m carbon.challenge_pipeline readiness \
  --challenge CHALLENGE_ID --level LEVEL --only S3,H2 \
  --margin-panel /PRIVATE/gate-margin-panel.json \
  --overlap-panel /PRIVATE/tuning-overlap-panel.json \
  --no-history
```

The command's partial run is never globally green. `--no-history` is required whenever a producer panel path is supplied, so the ordinary append-only repository history cannot capture a report derived from private inputs. If `--json` is used, its output path must also be outside the repository. The registration files contain no case rows. PLT-09 batch 4 adds explicit L2/L3/L4 templates with unset panel digests, fragility values and custody classification; real runs remain `NOT_BUILT` until the producer and owners supply pinned evidence.

## PLT-09 batch 4 scoped contract

See the [working contract](SCORING_AND_VALIDATOR_CHECKS.md). `scoring_by_level` selects each check separately for levels 2, 3 and 4. Registrations and panels must name `levels: [2, 3, 4]`. Committed registration bytes must match HEAD. Private panel hashing and JSON decoding use the same bytes; duplicate keys are refused.

S1 reads the rule key shared with `BatteryPracticeRule`, its four comparison fields and equivalence margin. It reports `REVIEW_REQUIRED` until a committed `carbon.readiness.margin-measurement.v1` record binds `challenge`, `levels`, `rule_key`, canonical `rule_digest`, exact `equivalence_margin_rel`, `noise_source` and a `run` path/file sha256. The run uses `carbon.readiness.margin-measurement-run.v1`, repeats Challenge/levels/rule digest/margin/noise bindings, and supplies a nonempty `method` and finite nonempty `observations`. This verifies provenance and consistency; it neither estimates a new margin nor qualifies the experiment.

S3 compares the complete roster against public scorer metadata, including near-optimism (`VALUE_STUDY_ONLY`) and B15 (`OPT_IN_B15`). These scopes do not activate a gate in another exam. Schema validity and mixed-output paired-repeat checks have no invented scalar margin unit. Their units and every `fragile_below` value remain owner input. Newly implemented unregistered gates fail before reading a panel.

`scripts/dev/readiness_panels.py S3 --challenge CHALLENGE_ID --level 2 --out /PRIVATE/margins.json` packages committed public-reference margins only. Registration's `public_reference_margins` names a committed path and file sha256. Its `carbon.readiness.public-reference-margins.v1` source names Challenge/levels and the complete `margins` map. No measured source is supplied here.

The script's H2 mode accepts repeated `--group ROLE=/PRIVATE/prior.json` exports and optionally `--pool-config /PRIVATE/tuning-config.json` instead of a rotating-pool group. It verifies exhaustive operator custody classification and complete group coverage before invoking existing read-only `tuning.export_pool`. Prior files must be outside Git, owner-only, with `cases` containing input objects only. Output is exclusively created with owner-only permissions. Console output contains only digest/count or a fixed refusal code. Tests use synthetic inputs; no real export or hidden-host invocation is performed or authorized here.

## H4 aggregate audit

`gate-audit-registration.json` uses `carbon.readiness.gate-audit-registration.v1`, Challenge/levels/basis, complete public gate roster with units/scopes, and `panel_digest`. The outside-repository `carbon.readiness.gate-audit-panel.v1` panel names Challenge/levels and `populations`, exactly `practice`, `hidden`, `tuning`. Every population contains at least one registered gate with nonempty rows. A row has exactly `passed` (Boolean) and `margin` (finite signed scalar). Extra IDs/witnesses/paths are refused, as are positive failing or negative passing margins. Practice-only gates fail.

The reader emits only per-gate, per-population checked/pass/fail counts, minimum/p01 and digests. Missing gates in a population report zero checked and null margins, explicitly absent evidence. Machine PASS establishes that the declared report was computed. The auto+review item's framing still needs a committed Test Lead H4 review for the requested level, binding exact `panel_digest` and `registration_digest`; stale framing fails. Read using `--only H4 --audit-panel /PRIVATE/audit.json --no-history`; any `--json` output must be outside Git. No real audit panel or hidden-host producer is supplied by this ticket. Templates and synthetic tests earn no qualification or launch authority.

V3 remains a human review item. Its [draft](MULTI_SEED_PROMOTION_PROPOSAL.md) records the Test Lead's 2026-10-09 development working values for seed count, pairing, confidence bound, and any-seed gate failure. Owner adoption into a frozen rule and the remaining evidence details are still pending.
