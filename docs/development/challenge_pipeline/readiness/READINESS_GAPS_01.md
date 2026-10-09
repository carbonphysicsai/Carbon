# S3 and H2 producer evidence for `readiness`

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

The command's partial run is never globally green. `--no-history` is required whenever a producer panel path is supplied, so the ordinary append-only repository history cannot capture a report derived from private inputs. If `--json` is used, its output path must also be outside the repository. The two registration files contain no case rows. No real S3 or H2 registration is added by this ticket; real runs therefore remain `NOT_BUILT` until the producer and owners supply pinned evidence.

V3 remains a human review item. Its [draft](MULTI_SEED_PROMOTION_PROPOSAL.md) records the Test Lead's 2026-10-09 development working values for seed count, pairing, confidence bound, and any-seed gate failure. Owner adoption into a frozen rule and the remaining evidence details are still pending.
