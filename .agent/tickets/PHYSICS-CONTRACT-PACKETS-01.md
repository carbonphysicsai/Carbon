# PHYSICS-CONTRACT-PACKETS-01

Owner queue PKT-06, 2026-10-12; engineering executor Packets Codex;
scientific reviewer Carbon Validator. Base main:
`4ab32a822811409165220b24a642ac551be57d1b`.

## Bounded working contract

Draft plain-data physics contracts for f02, the cooling cell at point C,
motor 10p/12s and f13. Reuse current decks, observers, kits and validity
declarations rather than changing them. Each proposed law needs its source,
applicability conditions, output inventory and image-bound calibration recipe.
Add an advisory to the buyer-field packet checker: missing physics contracts
are reported, never a new exit-code gate or evidence of scientific failure.

Basis: shared operator `PHYSICS_CONTRACT_01_DRAFT.md`, sections 0–1,
SHA256 `3de29124d7b34542b45107bb224322036876d5e0e474c6fac90677c1ed213369`.
Do not reproduce private paths/content in a public packet. RES-06's law review
is pending. Independently cited proposals remain DRAFT/HUMAN_INPUT until review.

## Plan and decisions

1. Map proposed laws to actually emitted model/reference outputs; distinguish
   source support from physical validity and code verification from calibration.
2. Write four JSON drafts and their common review/calibration instructions.
3. Add a bounded public-document notice to the checker CLI. Preserve historical
   v1 API reports; opt-in reports use v2, with no change to buyer-field results.
4. Test missing, malformed, unavailable, escaped and present-draft inputs;
   review every local source pointer; run applicable acceptance and hand off.

No solver execution, solves, spend, hidden material, runtime IDs, scoring/gate
adoption, qualification or historical reinterpretation. Point C stays a draft
scope, not a promotion over current central point B. No battery changes.
No material, demagnetisation or turbulence applicability is guessed.

## Definition of done and evidence

Four sourced drafts, explicit output gaps, no adopted tolerance, image/calibration
holds, a non-blocking checker notice, regression tests and lessons. Baseline
native diagnostic: packet-reconcile and packet-generator tests, 20 passed.
Native output is not canonical; GitHub exact-head acceptance is required for
the PR Head handoff. PR Head owns merges and base synchronisation.

Candidate checks (native diagnostics):
`pytest tests/cpu/test_physics_contract_drafts.py tests/cpu/test_packet_reconcile.py tests/cpu/test_onboarding_packet_generator.py tests/cpu/test_law_consistency.py tests/cpu/test_validity_envelope_rule.py -q`
— 63 passed, one Windows symlink-permission skip. Black/Ruff, historical
`scripts/dev/onboarding/reconcile_examples.py --check`, and
`python -m carbon.challenge_pipeline validate` exercised; lessons retain
host/sparse-checkout limitations and repairs. Linux CI covers the skipped test.

Maturity ceiling: draft scientific proposals and tested engineering tooling,
not scientific qualification. Development Hub maintenance is retired under
OWNER-WORKFLOW-SPEED-01. Primary placement: challenge pipeline onboarding.
