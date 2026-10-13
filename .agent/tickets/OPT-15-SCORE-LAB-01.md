# OPT-15 SCORE-LAB-01 — working contract

Status: IN_PROGRESS, DEVELOPMENT only. Base: `origin/main` at
`ad870e7d5d30f2840247f40e81c685091bd89b9b` (2026-10-13).
Primary Hub map_ref: `WAVE-C` (development score evidence; no change to
runtime scoring, promotion, or qualification).

## Scope and decisions

- Add an offline `scripts/dev/score_lab` command. Its analytic truth is exact
  for its declared toy surfaces only; difficulty, model errors, and all cost
  values are labelled assumptions and varied as inputs.
- Keep scoring cases and decision-value cases disjoint. Python score functions
  receive scoring predictions/references/metadata only. Registered battery
  candidates reuse `score_tuning.parse_candidate` and `score_member`; the
  old rule is never overwritten or reinterpreted.
- Reuse `score_proof`'s tau/bootstrap machinery and the RES-07/08/09 public
  measurement definitions. Public EV4 replay reads only the explicitly public
  copy, verifies its source identity, and creates a local compact cache. No
  reconstruction, solver, hidden pack, or producer access.
- V2 rev-2 is a prospective development candidate. Its parameters remain
  HUMAN_INPUT; the lab requires explicit assumption values and never adopts
  them. A bank check is structural and a development-half winnability
  diagnostic, not a bank qualification.

## Plan and acceptance

1. Analytic generator, error controls, common scorer, deterministic bootstrap.
2. Public replay/cache and V2 bank-spec checker.
3. CLI, documented examples, synthetic fixtures, actual public-data findings.
4. Focused and canonical validation, exact-head PR to main and PR Lead handoff.

Invariants: P/Q/w remain separate; mandatory infeasibility precedes ranking;
missing reference evidence stays unscored; practice is not the official exam;
no fixture or retrospective result becomes LIVE, qualification, or a score
change. Completion is conditional on exact-head CI and review, with owner
adoption reserved.
