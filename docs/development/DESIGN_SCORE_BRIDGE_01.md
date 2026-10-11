# Design score bridge (DEVELOPMENT)

`carbon.design_search.score_bridge.evaluate_design_score(bank, predictions,
rule)` is a pure Challenge-neutral q calculation for a validator-owned caller.
The bridge reads only its three input values. It never reads a file, queries a
model or solver, selects a production rule, changes a validator record, or
controls retries and slots.

## Inputs

The caller supplies:

1. `seal_score_bank(questions)`: an ordered, digest-bound bank of plain v2 or
   indexed tasks. Each question has a protected `question_id`, registered
   task, and a complete reference panel. A missing reference returns `VOID`;
   an unavailable or failed bank returns `FAILED_INFRA`. The caller owns
   provenance, retirement and exposure checks.
2. `commit_prediction_panels(model_id, questions)`: prediction panels bound to
   each question's task digest and to one enclosing prediction digest. A panel
   row is `{candidate, condition, values}`. An indexed question gives one
   ordered panel per registered index. The caller must commit these panels
   before it opens reference outcomes; digest checking cannot prove timing.
   Sparse panels are allowed for a multi-start path, but every query the
   frozen optimizer actually makes must have a finite panel value.
3. `register_score_rule(body)`: one Challenge and task contract version,
   objective quantity/unit/sense, unit-matched value-equivalence tolerance,
   regret multiplier and divisor, costs for every non-feasible outcome kind,
   and the explicit mean-loss and inverse-one-plus transform. There are no
   numeric defaults. Indexed task tolerances must match the rule exactly.

The bridge runs the frozen Carbon optimizer from the committed panels. Its
pick is committed by that optimizer before reference judgement. The internal
result includes ordered question outcomes, each objective-unit regret and
registered loss, the mean regret over priced feasible picks, mean loss over
all questions, and `q = 1/(1+mean_loss)`. A positive objective gap within the
registered tolerance has zero regret; a greater gap retains its full value.
False-feasible, missed-opportunity and band-unresolved picks take their
registered losses. No near-tie becomes UNRESOLVED solely for being near.

`INELIGIBLE` / `q_candidate_failed` means a candidate caused an invalid,
non-finite, missing, altered or model-failed prediction. `VOID` means a quiz
reference is missing. `FAILED_INFRA` means bank, rule or reference
infrastructure is unavailable or inconsistent. Both non-candidate states
have `eligible: null`, no q and no partial score; the validator owns retry and
slot restoration. Reference *band uncertainty* with available truth is a
different outcome and takes the registered uncertainty loss.

`miner_score_projection(result)` reveals only `{schema, outcome: "SEALED"}`.
The internal result contains protected question IDs and reference-dependent
decisions and must not be returned directly to a miner.

## Battery v8 parity and ownership

The toy v8-shaped fixture builds the same 117-point lattice tasks and
projected Q3 measurements as the producer adapter. It compares the neutral
pick kinds and losses with `battery.value.quiz.q3_judge`, then compares q
directly with `score_tuning.member_legs` on the same Q3 decision regret.
For that fixture only, the registered regret multiplier/divisor and kind
costs come from the existing EV4 contract. This does not register a new
battery rule or reinterpret historical results.

VALIDATOR-26 owns its caller, the A accuracy leg, G-FEAS gate, eligibility,
retries, slot semantics and prospective rule registration. It must pass the
same committed predictions and registered rule used by the scoring study.
Test Lead owns any adopted rule values and score use. This module supplies
DEVELOPMENT implementation and toy tests only; it earns no scientific or
production qualification.
