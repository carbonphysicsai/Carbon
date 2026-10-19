# PRD-03 bounded development evidence

[Package/API contract](../../../../carbon/product/decision_assistant/README.md)
and [working decision](../../../../.agent/decisions/2026-10-12-PRD03-BOUNDED-ASSISTANT-01.md)
describe authority, reuse, budget accounting and limitations.

[Timing fixture](timing-fixture.json) records 200 warm native repetitions of the
synthetic workflow, including Assistant construction and returned snapshot.
It performs 27 toy model calls and 3 arithmetic reference calls per workflow.
Median 35.993 ms, nearest-rank p95 63.045 ms, maximum 98.118 ms; one decision
digest. Imports and fixture assembly are outside that measurement boundary.
This is NATIVE_DIAGNOSTIC, not real-model or accepted production latency.
The timing record is pinned to the first PRD-03 candidate; later assessment-hold
repairs and the PRD-02b/c/d/e base-sync do not relabel it as a new measurement.
It is not a measurement of the current native receipt v4 composition. Production
latency remains HUMAN_INPUT; no timing pass is inferred from that old snapshot.

[Public panel gap](public-panel-gap.json) is an aggregate-only inspection of the
owner-named read-only calibration copy. The input manifest, whole records file,
all 800 JSONL line hashes and every image/overlay/version matched. Its recorded
wall_s median 108.438 s is a **DEVELOPMENT cost estimate only**. It supplies no
CPU core-seconds. The current owner hold is SOLVER_NOT_ACCEPTED, accepted false,
and the real comparison/regret remain GAP/null. Earlier manifest or acceptance
text cannot override that battery/plating use hold. Original inputs are never
committed or modified.

The runnable synthetic demo deliberately retains two false-feasible selected
picks, including a TRUST pick. Independent arithmetic reference checks reject
them and select the feasible slow action. The assumed equal-budget replay keeps
the following adverse outcome (one synthetic cluster, no confidence interval):

| Assumed wall/core budget (s) | Solver-only feasible pick | Assistant feasible pick | Assistant finite-bank regret |
| --- | --- | --- | --- |
| 2.1 / 2.1 | Yes | No | GAP/null |
| 4.1 / 4.1 | Yes | Yes | 0 s, synthetic only |
| 6.1 / 6.1 | Yes | Yes | 0 s, synthetic only |

These are synthetic interface calculations, not the real battery v3 question
law, an executed solver search, an independent population study or a value-bar
pass. Expected regret stays null without matching external assessment evidence.
No physical validation, qualification, compliance, security audit or LIVE claim.
