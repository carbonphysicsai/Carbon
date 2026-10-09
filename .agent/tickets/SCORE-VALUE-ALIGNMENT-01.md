# SCORE-VALUE-ALIGNMENT-01: prospective battery v3 versus historical value

**Status:** DEVELOPMENT analysis; no score-rule change, solver run, spend, hidden material, or LIVE claim.

**Owner request:** Determine whether the owner-approved `G-FEAS/A-Q` rule v3 fixes the negative score-to-value alignment measured for eight Graphite run-5 members under rule v2. Keep the rule versions and their evidence populations distinct. Report what cannot be calculated from committed evidence.

**Authority:** OWNER-BATTERY-SCORE-RULE-01 and VALIDATOR-26 define v3. The Test Lead owns score use and any new rule values. This ticket measures evidence and recommends; it does not activate or modify a scoring rule.

## Working contract and decisions

1. The eight-member Q1 panel's recorded score is the v2 **public PRACTICE** score, negated so that larger is better. Its value is EV4 development decision loss on the registered common resolved mask. Do not relabel a `control-exam-v1` score on EV4/EV5 as v2.
2. V3 requires each member's accuracy leg on the registered v3 screening cases, Q3 regret on the corresponding settled quiz, and false-feasible rate on the scoring set with case-level provenance and failure cause. Neither EV4 decision loss nor near-limit false acceptance is a substitute for either missing v3 measure.
3. Calculate historical alignment from committed panel data, with a deterministic member-resampling interval labelled descriptive. Verify the one-seed Graphite result against its recorded τ and ρ. Keep the panel identity and score version in every row.
4. Calculate v3 or a proposed variant only when a separately identified, case-compatible leg table exists. An unavailable comparison must say which inputs are missing; it must never be a numeric zero or an implied negative finding.
5. The six Graphite divergences may be attributed to the v2 accuracy-only ordering. They cannot be attributed to a v3 leg without that leg's per-member values. Prospective alternatives and held-out estimates remain proposals until a genuine v3 table and a split declared before inspecting its outcomes exist.

## Implementation plan

- Add a reproducible, read-only analyzer for the committed public panels and a report with exact source identities, τ/ρ, intervals, and coverage.
- Add toy tests for version separation, missing v3 inputs, deterministic intervals, and the recorded Graphite one-seed result.
- Run focused and canonical validation; submit one PR to PR Lead at its exact head.

**Maturity ceiling:** evidence analysis `TESTED` only. The v3 scientific rule is owner-approved but no Graphite v3 score-to-value result is inferred here.
