# DESIGN-SCORE-BRIDGE-01 working contract

Status: DEVELOPMENT implementation in progress. The owner's 2026-10-08
request is the active ticket. One implementation PR will be stacked on
DESIGN-TASKS-03 PR #820 until its indexed task API reaches main. Primary
map reference: `carbon/design_search`. The Development Hub is retired; its
purpose, placement, boundary and maturity remain accurate without a Hub edit.

## Authority and coordination

KEEP the runnable v2 and indexed task registrations, frozen Carbon optimizers,
reference assessment, and Q3 v8 semantics. WRAP them in a pure score bridge.
The bridge does not edit or import `carbon/challenge_validator`. VALIDATOR-26
owns its caller, retries, slot restoration, accuracy leg, G-FEAS gate and
prospective v3 deployment. The owner has now requested that the validator call
the neutral bridge for design q; this supersedes only VALIDATOR-26's proposed
direct `score_tuning` call, provided parity is exact. Coordination proposal:
https://github.com/carbonphysicsai/Carbon/pull/815#issuecomment-6063326610 .

## Input and result contract

`evaluate_design_score(sealed_bank, committed_predictions, registered_rule)`
has no filesystem, network, solver, model or clock access. The bank is an
integrity-bound ordered list of scoring questions. Each question has a
registered plain or indexed task and a complete, ordered reference panel.
The caller owns the reference/bank provenance and commits prediction panels
before reference access; a pure function can check digests but cannot prove
elapsed-time ordering. Its committed prediction panels bind the task digest
and are checked before any reference comparison. The bridge runs only the
registered Carbon optimizer over those values, then judges the pick.

The registered rule binds one Challenge and contract version, objective
quantity/unit, nonnegative value-equivalence tolerance, conversion from
objective-unit regret to loss, costs for false feasible and abstention kinds,
arithmetic question mean, and an inverse-one-plus-mean-loss q transform.
Every numeric slot is required; none is a scientific default. Indexed task
tolerance must match the rule exactly. Per-question regret remains in the
objective's unit; loss and q are separately labelled. The battery v8 fixture
uses its existing EV4 cost contract and must exactly reproduce
`score_tuning`'s `q = 1/(1 + mean Q3 decision_loss)`.

The internal result contains ordered per-question outcomes, status and cause,
mean regret/loss, and q only when fully scoreable. Candidate-caused malformed,
missing or non-finite predictions, altered digests, or model failures are
typed `INELIGIBLE` / `CANDIDATE_INVALID`. Missing or failed reference panels,
an unavailable bank, or a bad bank seal are `VOID` or `FAILED_INFRA` with no
candidate penalty and no q. Reference *band uncertainty* is distinct from
missing truth and follows the registered unresolved-pick loss. The validator
owns retry and slot accounting. A separate miner projection is a positive
allow-list showing only a sealed outcome, never case IDs, reference values,
per-question kinds, bank/task digests or hidden state.

## Plan and limits

Working sequence: contract; pure bank/rule/prediction registrations and score
bridge; disclosure projection; toy plain and indexed tests; battery-v8-shaped
parity fixture; canonical focused and required checks; one PR to PR Lead.
No hidden material, solver run, Challenge physics change, LIVE integration,
new score weight, or Test Lead decision is included. Test Lead owns adopted
rule values and score use. Historical v8/validator results are not rescored.

The ticket is ready for handoff only after exact-head validation and the
normal review gates. PR #820 and its prerequisite #808 must reconcile onto
main before this branch can merge.
