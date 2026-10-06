# CHALLENGE-AI-COOLING-11 — prospective unit-interval score candidate

**Status:** implementation and focused canonical validation complete;
applicable PR CI and PR Lead handoff pending. DEVELOPMENT candidate only.

**Authority:** SCORING-ARCH-01 (#643), OWNER-TESTNET-WEIGHTS-01 §2a,
OWNER-CHALLENGE-DESIGN-01, and the existing Cooling DEVELOPMENT exam.
**Predecessor:** CHALLENGE-AI-COOLING-07 and merged PR #638.
**Coordination:** Carbon Validator owns VALIDATOR-09's neutral variant registry,
VALIDATOR-13's hidden-batch route, and the weights pipeline. This ticket does
not edit those interfaces. PR Lead may take over after handoff.

## Outcome and boundary

Propose and measure one reproducible `[0,1]`, higher-is-better transform of
Cooling's existing raw mean TRAIN-normalized error on the pinned public
PRACTICE set. Keep the frozen exam gates, components, cases, scales, and
historical raw-error results unchanged. The candidate is not registered in
the validator, miner practice, Graphite, rewards, or network transport.

This is **not** the physics/robustness/accuracy Score Pack. The soft-physics
estimand and three-leg 45/30/25 candidate remain `HUMAN_INPUT` and nonnumeric.
No protected EVAL/STRESS case, seed, label, or score record is read here.

## Working contract

- Candidate formula: `u(e) = 1 / (1 + e / tau)`, where `e` is the existing
  complete-case raw mean error and proposed `tau = 0.1`. It maps zero error to
  one and is strictly decreasing for nonnegative finite error. It cannot
  change the ordering or repair decision-value misalignment of the base exam.
- The proposed scale is rounded from the public learned scaffold's registered
  PRACTICE mean error `0.09876205614850035`; it is a measured proposal, not
  a scientific threshold or an approved publication parameter.
- A mandatory gate failure is inadmissible and maps to zero only with complete
  usable evidence. Missing, invalid reference, infrastructure failure,
  incomplete coverage, or inconsistent aggregate is not a positive score.
- Every candidate result is marked DEVELOPMENT/public/adaptive and
  nonpromotable. Adoption and prospective variant registration are reserved
  to the science owner and VALIDATOR-09 integration.

## Definition of done

- Pure, typed candidate transform and stable candidate identity, with
  fail-closed evidence classification and no official caller.
- Reproducible measurement from the pinned *public PRACTICE* baseline summaries,
  including the score range and unchanged ordering.
- Focused regression tests for endpoints, ordering, gates, missing evidence,
  malformed aggregates, and non-authority.
- Design/evidence note that names the pending owner decision and explains why
  the two public baselines cannot establish optimal weights or promotion.
- One lessons record after execution; canonical CI acceptance before PR Lead
  handoff.

## Validation to date

- The candidate and existing Cooling scorer/exam matrix passed 127 tests in
  the pinned canonical Linux environment using `CARBON_UV_GROUPS=science-jax`.
- Changed Python files passed canonical Ruff and Black checks.
- The first baseline run collected only the new candidate tests (18 passed)
  under the default `dev` group; the combined run initially failed collection
  because `numpy` requires `science-jax`. That environment issue was corrected
  rather than changing code or tests.
- The temporary Linux checkout contains an exact mechanical copy of the
  candidate source/test/evidence note because a Windows-created Git worktree
  has a Windows `.git` path that WSL Git cannot resolve. GitHub's pinned CI
  remains the acceptance authority for the final PR head.

## Out of scope / follow-up

Cooling's paired independently held fresh-case promotion policy is a separate
ticket. So are Motor's candidate and promotion policy, the protected metric
operator, 45/30/25 Score Pack, and any counted/fresh campaign. None is enabled
by this ticket.
