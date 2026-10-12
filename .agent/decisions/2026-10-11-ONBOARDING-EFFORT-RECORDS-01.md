# ONBOARDING-EFFORT-RECORDS-01 — explicit process events, not inferred labour

KEEP #970 stage authority, #979 status and #1116's descriptive metrics.
Add one public JSON event per record: ENTRY, EXIT, EFFORT_START, EFFORT_END.
Pairs bind cycle/family/stage and exact source/stage-definition provenance.
Only closed active timers contribute; open intervals are not extrapolated.
Human labour, AI-agent active time and tool wall time remain separate.

Timers are self-reported active blocks: contributors finish before idle/CI
wait and start another block on resumption. Clock duration is measured;
the declaration of activity and actor identity is not independently verified.
Reject duplicate closures and overlapping blocks by the same contributor,
including across Challenges, rather than inflating shared-work effort.

Recorded exits include PREPARED/BLOCKED/ACCEPTANCE_RECORDED. None authenticates
an approver or changes current_stage, exit_verified, readiness or TESTED.
Stage owners still adjudicate acceptance; claims and source drift are explicit.
No historical effort is fabricated. Reversibility: additive CLI/event tooling;
old status renderer and retained historical packs stay unchanged. Stage/event
values are engineering telemetry only; no reserved scientific choice selected.
