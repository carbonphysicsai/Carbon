# VALUE-BAR-REGISTRATION-01 — VALUE-BAR-V1 development rule

**Status:** working contract. **Base:** exact merged `origin/main`
`5fbac3099eaae368b23d266cce31ed7409685722`. **Authority:** the Test
Lead's 2026-10-10 value limits under the owner's delegated instruction,
relayed in this ticket; OWNER-LAUNCH-STRATEGY-01's cheap-baseline requirement;
and #1003's development evaluator. This is a prospective development value
rule, not a LIVE scoring rule or scientific qualification.

## Scope and decisions

- Register `VALUE-BAR-V1` in the existing
  `carbon.challenge-value-rule.v1` envelope. Item 2 requires the upper paired
  fold-cluster bootstrap 95% bound of Carbon-minus-cheap-baseline regret to be
  strictly below zero, at matched admissibility on two independent held-out
  folds. A CI wholly against Carbon fails; one crossing zero is insufficient.
- Item 3 requires a measured median complete-decision-query speed-up of at
  least 100×. The 20× flagship allowance applies only with a separately
  measured reference solve costing at least 3,600 CPU-seconds. Missing solve
  CPU cost cannot establish the allowance.
- Item 5 requires the paired 95% cluster-bootstrap CI on solver-verified
  model-screen-then-verify minus solver-alone value to exclude zero in Carbon's
  favour at a *pre-registered* wall/core budget. No Challenge budget is given
  here: `budget: null` is explicit and yields INSUFFICIENT_EVIDENCE until a
  Challenge-specific prospective registration supplies it. No budget is
  selected from a post-hoc curve.
- Item 1 requires an owner decision receipt with two distinct source digests.
  Item 4 reports sourced or labelled ASSUMPTION value/volume ranges and does
  not gate the overall value-bar verdict.
- Keep #1003's legacy synthetic-rule path unchanged. The new rule ID selects
  the prospective semantics. Extend #998's aggregate replay with a paired
  value-delta interval; no per-job values enter the report.

Primary Development Hub map ref: `WAVE-C/VALUE-BAR-REGISTRATION-01` (retired
Hub; no active source regeneration). KEEP #1003 and #998; REPAIR the rule
interpretation and missing paired aggregate only. Owner/Test Lead control
Challenge budgets, source adequacy, population, and whether any development
PASS supports a Tested claim.

## Acceptance

Toy fixtures cover PASS, FAIL, INSUFFICIENT_EVIDENCE, the 100×/20× branch,
strict zero boundary, source count, non-gating ranges, missing budget, and
exact rule ID. No hidden/AX42 material, solver run, spend, LIVE change or
Challenge qualification. Run focused tests and exact-head canonical CI; open
one PR to PR Lead. Completion remains conditional on review and merge.
