# OPT-17 paired candidate comparison arms

Status: working engineering contract; PUBLIC DEVELOPMENT / synthetic fixture only.
Base: main `e627c260d326be679d09fddd50540a556f88e790`.
Scope: existing local OPT-17 and `L5_MEASUREMENT_BRIEF_01.md`, temporarily
assigned to Product by Test Lead under the owner's team delegation. Optimizer
retains domain coordination. Additive module/test/document paths were notified
before editing; no open PR touches them. PLT-27 #1311 remains adjacent and owns
the candidate build; pinned recipes/trainers, campaign, CLI and bank files stay
untouched. The Product primary queue remains empty.

KEEP the existing equal-budget `BudgetCap` / `BudgetLedger` and cost charges.
WRAP them for paired construction receipts; design-search replay alone does
not establish equal construction. Match declared architecture, data, seeds,
training steps, hardware, actual time/compute/token/work limits, and pin each
arm's exact construction identity. Every work event, including line-search
objective/gradient evaluations, must reconcile with the complete arm totals.
An unequal or incomplete receipt refuses before any value comparison. Values
are supplied public measurements, never trusted because a caller claims PASS.

Report paired seed/condition differences for target and each declared near
variant, preserving missing/failed observations and explicit sample coverage.
Use the existing paired-bootstrap design (joint seed/condition resampling) for
descriptive intervals. Exact observed equality is reportable; an interval that
spans zero is UNRESOLVED, never proof of equivalence. Acceptance thresholds,
minimum meaningful effects, adoption and stop/go remain HUMAN_INPUT. No scalar
rule selection, ranking, qualification, LIVE, training, reference solve,
private/holdout read, paid compute, deployment or chain operation is added.

The zero-cost stand-in uses OPT-15b's existing analytic target/neighbourhood
generator and identical arms to exercise a null result. It has explicit
synthetic provenance and cannot create public measured candidate benefit.
Public inputs require explicit receipt/artifact identities; this tool checks
structural/digest consistency, not executor authenticity or physical truth.
The brief's hunt-recovery caveat accompanies every result. Real execution and
its independently authenticated metering remain with GTM/host-side owners.

Expected manifest: this decision, `carbon/development_comparison/l5_candidate_arms.py`,
`tests/cpu/test_l5_candidate_comparison_arms.py`, and
`docs/development/evidence/l5-candidate-comparison/README.md`.
Baseline: existing equal-budget/budget-registration tests, native 30 passed.
Validation: focused discriminating controls, relevant budget/neighbourhood
regressions, formatting/type/quality and required canonical exact-head CI.
Completion: one main-based PR, queue-scope review, successful actual current-head
checks/Merge gate and Ready handoff; the current engineering merge owner merges.
Hub retired under OWNER-DX-03. No changes to WAVE or acceptance authority.

Reversible: remove these additive paths or prospectively version the input
contract. Material changes to equality, pairing or uncertainty semantics must
be recorded and reviewed; no historical receipt is silently reinterpreted.
