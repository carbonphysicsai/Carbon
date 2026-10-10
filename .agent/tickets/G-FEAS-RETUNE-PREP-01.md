# G-FEAS-RETUNE-PREP-01 — prospective battery threshold curves

Owner direction: 2026-10-10. One development-only PR to PR Lead, based on
main `65ef88660fe02018c26f54d14655fe7b66354aa8`. No hidden material,
AX42 access, reference solver, spend, LIVE gate change or owner threshold
decision.

## Working contract

- Reuse `score_tuning.candidate_scores` and registry v5's `A-Q` weights, with
  the owner-recorded strict `exceeds` G-FEAS comparison. A supplied threshold
  grid makes prospective diagnostic candidates; historical v4 scores and the
  currently adopted gate are unchanged.
- Input is an explicit public/development summary with digest-bound v3
  accuracy, settled Q3 regret, scoring-set G-FEAS and common-mask development
  decision loss for each member. A predeclared good-recipe receipt names the
  good group. No predictions, case IDs or reference values are loaded.
- Report, per threshold, the mean member false-feasible rate among passing
  members, share with any false-feasible calls, good-recipe fail rate (any seed),
  and v3 score–value Kendall τ-b, including a descriptive recipe-cluster
  bootstrap band. Preserve null when a correlation is undefined. Unresolved,
  infrastructure and candidate failures make the common curve insufficient;
  never silently drop them.
- Run a reproducible aggregate-only synthetic demo using #961's public toy
  controls plus two explicitly assumed good boundary recipes. The existing
  committed run-5/EV data lack matched v3 input legs and cannot yield real
  retune curves yet. Stage A can later pass summary-only development records.

Primary Development Hub map ref: retired under current delivery protocol.
KEEP the scorer and registry; WRAP them with a read-only analysis command.
Maturity ceiling: implemented and toy-tested development tooling, not an
adopted score rule or a measured real-recipe threshold finding.

Acceptance: fixture tests cover strict > at the cutoff, deterministic replay,
good-recipe rejection, incomplete evidence, digest/scope refusal, explicit
grid, CLI no-overwrite and aggregate disclosure. Canonical exact-head CI is
required for PR handoff. PR Lead owns review/merge; Test Lead and the owner
reserve any threshold or score-use decision.
