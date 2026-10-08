# DESIGN-REPORTS-BATTERY-01 working contract

Status: DEVELOPMENT implementation, conditional on review and merge. Starting
base: `carbonphysicsai/Carbon#783` head
`6b7ad0d4f0a54987e5654ef1fabe59efa335aa8b`. One implementation PR on
main after #783 merges. Primary Development Hub `map_ref`:
`carbon/design_search`. The Hub is retired; its purpose, placement and
boundaries remain accurate, so no Hub source or generated output changes.

The primary source is the sealed battery v8 Q3 quiz work directory and its
matching seed-journal `quiz` commitment. The adapter reads all drawn Q3
scenarios and their settled 117-point references, then checks that the kept
eight are exactly v8's first feasible scenarios. It does not read the private
root, run a solver, or write to the producer directory.

The decision job is `battery-q3-v8`: one condition per scenario, minimize time
to CV onset with EV4's reach, plating and thermal constraints, v8 uncertainty
bands and lower-c1-then-c2 ties. The 117-point exhaustive task uses the
existing `design_search.tasks` optimizer and neutral behaviour controls.
The task's numeric reach flag is an internal representation of EV4's
PASS/UNRESOLVED/FAIL reach verdict; an unreached protocol's undefined time is
never represented as a physical time or a feasible option. Native EV4
reference assessment and outcome are the report's decision authority.

Report A describes exactly the sealed eight. It is conditional on the
identified seal, not a future-batch probability. Report B uses all settled
accepted Q3 draws as a small empirical sample of the v8 draw process,
resampling the observed draw support, generating a fresh 12-draw first round,
then adding four-draw rounds as v8 does until eight feasible scenarios are
selected.
It reports kept and not-kept separately, an underfilled-round rate, and
predictive percentile intervals that include resampling uncertainty. It does
not infer protected rejected draws or fit a continuous ambient/SOC response.
Each batch identity stays separate. No report is score or power qualification.

The proposed #776 EV buyer job is a different scientific contract. Its
five-condition programme, capacity output and requirement laws require a
separately approved solved bank. This ticket exercises only a fixture-shaped
forward adapter path; it makes no real-bank EV claim.

Expected paths: this decision, `carbon/design_search/battery_q3_v8.py`, the
registered v8 law, the producer CLI, battery report fixture tests, the AX42
runbook and package data. Required evidence: toy producer-format fixtures,
canonical focused and full validation, Black, Ruff and diff check. Completion
is conditional on #783 merging, a PR against exact main, CI, review and PR
Lead handoff. No local report declares LIVE or scientific qualification.

Evidence uses toy producer-format fixtures and canonical focused/full validation;
no protected material in repository tests. The output is aggregate-only:
no scenario or case IDs, candidate picks, conditions, reference values,
registered task identity, or digest pre-images. Test Lead chooses alpha,
power, control severities and any score interpretation. PR Lead owns merge.

Review correction on #808: synthetic control severity is now keyed by every
controlled limit quantity and carries that quantity's registered unit. The
neutral control schema advances to v2 and refuses a missing key or unit
mismatch. The battery producer CLI repeats each severity flag as
`quantity=value`, using the task's V and degC limit units. The historical
battery control adapter and prior results remain unchanged. Test Lead still
supplies the actual values; toy fixtures exercise only the shape.
