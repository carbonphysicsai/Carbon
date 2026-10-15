# WEIGHTS-CURRENT-SOURCE-01: coherent current promotion selection

Root's urgent AX42 engineering assignment,2026-10-14; finding
WEIGHTS-NO-CURRENT-PROMOTION-01 independently reproduced by Validator/Test
Executor. Actual main base a3a0b382b62a34c04f0750e89b52b514d668df2f;
isolated codex/weights-current-source-01. Separate from observer PR1347.
Root retains PC steps, deployment and merge. No signatures/chain/private reads.

Authority read: current constitution/invariants/WAVE, OWNER-DX03/delegated
protocol; VALIDATOR14/15; OWNER-TESTNET-WEIGHTS-01, OWNER-VALV2-WEIGHTS-01,
WEIGHTS-AUTHORITY/HOLD-LIFT; registered policy/member note; current issuer,
ledger and shared publisher. Prior BuildOut/overlay/master/code/legacy
authority reads verified byte-identical8dc35..a3a0; no archive reuse. Hub retired.

Issue observes configured source None and freezes all-burn; resolve instead
uses the latest historical eligible record, refusing that same intent forever.
Preview agrees with issue. A missing configured source also reuses stale
history despite the registered/documented no-serving-validator burn contract.
Classification IMPLEMENTATION_LAG, not a new economic or scientific decision.

KEEP append-only WinnerLedger, eligibility/clock/decay/Q12/policy, immutable
per-epoch intent bytes, checked publisher/journal/reconcile/no-resend guards.
REPAIR one selector used by issue/read-only resolve/preview: no active source
or explicit None means no current promotion; source errors/malformed data
refuse, never substitute history. Present current model selects its matching
record and original clock, not the latest unrelated record. Read-only resolve
cannot append a new promotion; unknown/changed current model refuses. Preview
may derive a tentative new record with the existing decide function, without
writing it. Genuine source/identity/target/halving drift still refuses.

Plan: retain existing typed four-control reproduction as RED evidence; add
discriminating ordinary pytest regressions plus actual source-change/halving/
immutable-intent/older-matching-record/error controls. Baseline/focused
canonical validation using existing fixture backend; style/hygiene; one
main-based PR and distinct focused Validator review. No host data, wallet,
backend signing, journal deletion, new values or acceptance. Historical
terminal publications are not rescored. Existing epochs are never rewritten
to force acceptance; Root handles any actual host recovery after review.

Expected manifest: this ticket; one decision; testnet_winner_publication.py;
new focused source-selection tests; existing publication test's drift fixture
updated to change the actual source rather than merely append unrelated
history; bounded operator explanation. Fresh open-PR scan found no overlap.
Completion conditional on focused canonical controls and actual exact-head
gates/Root integration. Maturity DEVELOPMENT software tested only, never
security/scientific/mainnet/payment acceptance.

Canonical evidence (Ubuntu24.04/amd64, Python3.11.16): existing publication,
eligibility and decay baseline 56 passed. New source controls against old
runtime: 19 genuine discriminating failures plus one fixture property error;
the corrected halving control passed on old runtime before applying the repair.
Repaired four-file suite: 76 passed. Final exception-chain privacy assertion
and later-block halving fixture: 13 passed, 7 deselected. Canonical Black and
Ruff passed on all three changed Python files. Commands: canonical.sh python
-m pytest tests/cpu/test_reward_{current_winner_source,testnet_winner_publication,
winner_eligibility,winner_decay}.py -q -x; final focused selection -k
"unavailable or halving" -q. Validation uses synthetic scripted counters only.
