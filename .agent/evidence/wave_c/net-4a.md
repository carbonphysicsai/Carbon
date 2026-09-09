# NET-4A stable implementation evidence

Status: selected; canonical acceptance and merge pending.
Starting main: 505f08cde173eab197aa397a09536bb6bf576065 (PR #123).
Ticket: `.agent/tickets/NET-4A_weight_intents.md`.
Primary Hub map_ref: WAVE-C/NET-4A. Decision: NET-4A-D1.
Notification: https://github.com/carbonphysicsai/Carbon/issues/42#issuecomment-5610127520.

## Expected manifest and reuse

New carbon/rewards/intents.py, typed-boundary tests and WEIGHT_INTENTS contract.
KEEP existing reward, candidate, receipt and scientific owners. Extend only the
explicit focused network manifest. Reconcile actual C-REWARD merge and select
NET-4A in canonical authority before regenerating Hub. No dependency changes.

## Candidate diagnostics

Command: `.local/diagnostic-env/Scripts/python.exe -m pytest tests/cpu/test_net4a_intents.py tests/cpu/test_reward_core.py tests/cpu/test_reward_ledger.py tests/invariants/test_net4a_intent_boundary.py tests/cpu/test_select_cpu_profile.py -q`.
Result: 119 passed, one explicit canonical-Linux fixture skip, 10.30s.
Native results are diagnostic. Changed Python files pass Black and Ruff.

Native diagnostics exercise nominal references, exact ledger provenance, full
burn/no-winner, accepted winner, restart/replay, supersession, changed accepted
state, quarantine, funding-end validity, stale time/context, tampering and reserved
public-family rejection. These are fixture contract tests, not chain evidence.
Canonical acceptance retains installed-SDK/network/reward/A6/A7/A8 regressions,
all invariants, package/quality/authority, Hub/browser checks and Merge gate.

## Maturity and conditional delivery

Local fixture intent software only. Testnet-winner and treasury families have
distinct explicitly unavailable issuers; C2 real scientific eligibility and
optional custody admission remain their owning dependencies. No signing,
runtime burn, public transaction, scientific/security qualification, G2 or LIVE
claim follows. Intent expiry does not clear stored chain weights.

Completion requires the applicable canonical acceptance on the unchanged expected
head and normal guarded merge. Actual run/head/merge and completion comment stay
external. NET-4B is next under standing authorization.
