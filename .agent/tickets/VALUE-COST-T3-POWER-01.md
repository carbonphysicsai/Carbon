# VALUE-COST-T3-POWER-01 working contract

**Status:** DEVELOPMENT implementation in progress under the owner's
2026-10-08 value-and-cost direction. One PR to PR Lead, starting from main
`bc650fd53826aaf752d1e9e96e1ead4328b653df`. Primary Development Hub
`map_ref`: `carbon/design_search`. The Hub's retired navigation entry already
places this code and its producer-only boundary; no Hub source change is
planned.

## Scope and authority

Implement Part T3 tooling for all eight Challenge families: battery v3,
motor, cooling cell, f02, f06, f08, f13 and f17. A producer-only adapter
accepts an integrity-bound, complete solved panel and its registered decision
task, question law, control severities, bank-cluster and exposure identities.
It maps to the existing neutral power harness, including indexed battery v3.
Incomplete or unregistered panel material fails closed. There is no solver,
hidden-bank construction, model execution, spend, LIVE activation, validator
change, score-policy decision, or Challenge-specific physical default.

Extend the power estimate from one batch to a registered grid of questions
per batch and accumulated windows. Draws retain the shared-bank cluster in
every window: repeated questions from one reference bank never become
independent sign-test evidence. Exposures cap eligible combinations, with
their unit explicitly registered. The report prints aggregate detection
probabilities, Monte Carlo uncertainty, and feasibility/abstention/regret
summaries only. P and Q remain separate. An unregistered P must be absent,
not copied from Q.

The owner's Part T3 working values (alpha 0.05, target power 0.8 and a
moderate registered severity) are **inputs**, never code defaults or an
acceptance decision. Test Lead judges the outcome and threshold; Data
Collection owns settled panel and law registration. `VALUE_COST_ANALYSIS.md`
is an owner-provided untracked workspace note, not a runtime authority file.

## Engineering plan

1. Inspect the registered panel output contracts and baseline neutral power
   tests. Agree one fail-closed producer export shape at the Data Collection
   boundary; keep small Challenge-family adapters free of physics constants.
2. Add single-law Q-only support where population P is not registered, while
   preserving old dual-law report behavior.
3. Add explicit cross-batch exposure registration and a deterministic,
   clustered k-by-window simulation to plain and indexed reports.
4. Add toy producer-format fixtures for all eight families, with battery v3
   indexed, incomplete-reference refusal, no P invention, clustering and
   aggregate-only output tests.
5. Run canonical focused/subsystem validation, quality and delivery checks;
   open one DEVELOPMENT PR for PR Lead. CI supplies exact-head acceptance.

Expected paths: `carbon/design_search/` producer adapter and power modules,
its CLI, this contract, a short producer runbook and toy tests under
`tests/cpu/`. No files under `carbon/challenge_validator` are in scope.

## Working decisions and open seam

The neutral producer export contract is the proposed interface if Data
Collection has not yet published the exact settled Cooling Set A and Motor
Stage 3 export schemas. The adapter must require complete registered task and
reference panels rather than infer objective, limits, scenario population or
missing physical results. The requested source paths/PRs are pending; this
contract will be updated prospectively when they arrive. These are
engineering interface choices, reversible before producer adoption. No
human-reserved scientific value is selected here.

Completion requires the intended adapter and cross-batch behavior, toy
tests, canonical/CI evidence on the exact PR head, review and PR Lead
handoff. A green implementation is not power qualification or score use.
