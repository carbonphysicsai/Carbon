# VALIDATOR-09: development score variants

**Status:** slice 1 implemented (the registry and the one candidate
definition). It depends on #650 (Data Collection's SCORE-TUNE-B1), which must
merge first. Slice 2 (Graphite `--score-variant`) follows.

**Authority:**
- the Test Lead's approval of the design, 2026-10-05, with these corrections:
  - variant winners are judged on development data the optimiser never saw,
    never on a sealed confirmation set;
  - phase-4 variant support belongs to the Test Engineer, and is refused until
    then;
  - gate overrides are recorded in the variant's identity;
- OWNER-GRAPHITE-TEST-WAVE-08 §3: candidates are registered before they are
  computed, re-scored without retraining, and survivors become development
  score variants;
- the Test Lead, 2026-10-05: **one candidate definition.** The tuning registry
  (#650) and the variant registry describe a candidate identically, and a
  promoted survivor rescores byte-identically, proven by a test. The legs
  reach beyond the four exam components to the near-limit legs;
- OWNER-TESTNET-WEIGHTS-01 §2a: scores closest to 1 are best.

**Agreed with Data Collection, 2026-10-05.** The candidate is #650's
registry entry:
- `id`, `kind`, `weights` over the legs a, r, g, m, n and p, `gate`
  (`near` or `envelope`), `stable` and `basis`;
- scored only through `score_tuning.parse_candidate`, `score_member`,
  `gate_verdict` and `candidate_scores`.

The decision-region case weighting w(x) arrives as a new leg family in #650's
`LEGS`.

**Executor:** the Carbon Validator session. Branch
`claude/validator-09-score-variants`.

## Slice 1 (this PR)

- **`carbon/scoring/development_score_variants.py`** and
  `development_score_variant_policies/`, a digest-pinned registry that ships
  empty.
  - A variant (`carbon.development-score-variant.v1`) holds:
    - the tuning entry, verbatim;
    - the tuning registry it was promoted from (`candidate_registry`: SHA-256
      and commit);
    - the base rule, scope (`DEVELOPMENT_ONLY_NEVER_SERVED_TO_MINERS`), status
      (CANDIDATE or SURVIVOR) and authority.
  - Refused by name:
    - an unregistered, altered or malformed document;
    - a tuning entry that #650's own parser refuses;
    - `kind: deciding`, which is the base rule;
    - an undeclared leg;
    - an uncommitted origin;
    - a Challenge without a tuning module;
    - a fixture in the shipped registry.
- **`score_member` and `panel_scores`** score through the Challenge's tuning
  module, so they are byte-identical to the tuning loop (the parity test).
- **`ChallengeScoring.declared_score_components`**, data only. Battery
  declares `score_tuning.LEGS`.
- **The invariant** `tests/invariants/test_score_variants_unreachable.py`:
  no miner surface, validator or intake reaches the module.

## Slice 2 (next)

- **Graphite `--score-variant` in phase 3:**
  - a variant practice rule computes `member_legs` on the practice
    predictions and scores through `score_member`;
  - the variant is resolved before any spend;
  - it is pinned in the brief and in the permission profile;
  - the variant identity appears in feedback, in `summary()` and on every
    result's label.
- **Phase 4** refuses (`attacker_score_variant_not_supported`).
- **Refusal tests on every miner door,** each with a mutation-off twin.

## Maturity

IMPLEMENTED and TESTED (DEVELOPMENT). No variant is registered.

## Gate sweeps (evidence-driven gate candidates)

**Authority.** The owner, 2026-10-05, relayed by the Test Lead:

> We need to add gates if we see that showing up in design decisions and it's
> something we can filter out

Approving the plan:

> Send my approval. I think this is the right direction toward being active
> toward our goals. Max value alignment and max freedom.

**The candidates:**
- **G-FEAS:** a design predicted feasible whose reference is infeasible
  fails. This is the EV5 finding.
- **G-PLATE:** a plating false-acceptance rate above the threshold fails.
  This is run 5's 9.5%.

Each is defined once, in `score_tuning` (#674): the `feasibility` and
`plating_fa` gate measures, plus a `gate_sweep` entry expanded by
`expand_sweep`.

**Here:**
- **A sweep variant** carries the sweep entry and its base entry verbatim. It
  expands only through `expand_sweep` and stays CANDIDATE, with the threshold
  HUMAN_INPUT. Scores per cutoff are byte-identical to the tuning loop's
  (parity test). The owner picks the cutoff from the curve, and adoption is
  his.
- **Registered:** 10 sweeps, G-FEAS and G-PLATE each over CE, SR2, G-N,
  R-G-N and N-heavy, on the grid 0.005 to 0.5, plus 1.01 (ungated). They are
  promoted from registry v2 (`candidate_registry`: its SHA-256, commit
  ae3983d6).
- **The deciding rule (CE) with a gate** is now a candidate: a gate on the
  rule in force. CE alone is still refused as the base rule.
- **The practice value contract pin** accepts #668's `(file, digest)` form.
