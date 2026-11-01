# OWNER-HOTFIX-NO-VALIDATOR-RECEIPT-01: tooling, dashboard and docs hot fixes push without a Validator receipt

Date: 2026-11-01 (CST)
Status: DECIDED by the owner, directly in the Lead session (local_87151681-c66e-4949-a26c-23c4641b5722).
Owner's words: "Yes, skip it"
This answered the Lead's question: "Should those hot fixes skip the Validator's sign-off?" The proposal it answered, in the Lead's words: "Should small tooling, dashboard and documents hot fixes push on a passing quick check plus PR Head's check that the files match, without waiting for the Validator's sign-off? The Validator would still sign off anything touching scoring, grading, the doors, the image or exam material."

## Decided
- HOT-FIX class: tooling, dashboard and docs/records only, with no receiver, scoring, grading, image or exam-material path. It pushes on:
  1. a green tier-1 gate on the exact head (changed-path tests + test_code_authority + tests/invariants + lint/ratchet);
  2. PR Head's check that every file is blob-equal to its source, the head is a fast-forward, and no banned ancestor is present;
  3. the owner's named-SHA push words.
  No Validator receipt is required.
- Unchanged: a Validator receipt is still required for anything touching scoring, grading, receivers/doors, the worker image, or exam material (packs, decks, payloads, registry/overlay).
- When the class is unclear, it is NOT a hot fix: ask the Validator.
- Context: OWNER hot-fix tier direction, same day ("Fix. Review. Quick test. Push.").
