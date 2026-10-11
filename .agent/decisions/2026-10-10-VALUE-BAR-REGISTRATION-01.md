# VALUE-BAR-REGISTRATION-01-D1 — prospective value rule and budget seam

**Status:** implemented working rule registration; no Challenge verdict.

**Problem.** #1003 deliberately cannot decide without registered values. Its
single speed threshold and #998 probability-of-win proxy do not implement the
Test Lead's later conditional speed allowance and paired buyer-value interval.
The owner launch record's “no fixed targets” concerns onboarding execution;
VALUE-BAR-V1 is a later delegated *development value-bar* test, not an
onboarding-time commitment.

**Decision.** Add a rule-ID-selected `VALUE-BAR-V1` variant inside #1003's
existing rule envelope, with the Test Lead's supplied limits. Keep the
Challenge-specific budget null until it is prospectively registered. Add a
paired, cluster-bootstrap buyer-value delta to #998's aggregate report. Treat
unmeasured reference-solve CPU time as insufficient for the 20× allowance.
Require two independent decision-source digests. Report value and volume
ranges as sourced or explicit ASSUMPTION without gating.

**Location.** `docs/development/challenge_pipeline/value-bar-v1.json`,
`carbon/development_comparison/value_bar.py`,
`carbon/design_search/equal_budget.py` and toy tests, branch
`codex/value-bar-registration-01`.

**Alternatives.** Filling #1003's old `min_p_lower`, regret-excess and feasible
fraction fields with guessed values would silently replace the approved value
interval. Inferring an equal budget from observed curves permits post-hoc
selection. Inferring one-solve CPU cost from whole-query wall time mixes units.
All are rejected.

**Boundaries and supersession.** Development-only, aggregate output, no
production score, value qualification, solver execution or hidden material.
Owner/Test Lead can supersede the registered values or supply per-Challenge
budgets prospectively by changing the rule file and tests in a versioned PR.
The earlier #1003 synthetic-rule semantics remain replayable.
