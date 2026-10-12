# Explicit stage and active-effort records

ONBOARDING-EFFORT-RECORDS-01. The onboarding status command now appends a
recorded-process view, while preserving the artifact-history renderer and
immutable historical tool packs. It does not infer labour from Git gaps.

```text
python -m carbon.challenge_pipeline.onboarding status --challenge motor
python -m carbon.challenge_pipeline.onboarding status --challenge battery-v3 --format json
```

With no records, stage intervals and active effort are UNKNOWN, not zero.
Existing artifact dates, readiness counts and current_stage retain their
old meaning. Recorded process intervals do not set exit_verified, TESTED,
readiness or scientific/production acceptance.

## Record a stage attempt

```text
python -m carbon.challenge_pipeline.onboarding.telemetry entry --challenge motor --cycle motor-prep-01 --stage S1_packet --actor packets --actor-kind AI_AGENT --source docs/development/challenge_pipeline/round1/motor-precision-joint-v2.md
python -m carbon.challenge_pipeline.onboarding.telemetry exit --challenge motor --ref-id <entry-id> --disposition PREPARED
```

Each command writes one unique JSON event in this explicitly public directory,
using the current UTC clock. No existing event is overwritten. Sources and
the stage definition are digest-bound. ENTRY/EXIT pair by cycle, family and
stage; duplicate or reversed closures fail. Each stage can have multiple
attempts, reported individually rather than summing overlapping lead time.

EXIT dispositions are PREPARED, BLOCKED or ACCEPTANCE_RECORDED. The last is
a **recorded claim**, not authentication of a stage owner, scientific
qualification or an automatic accepted exit. The tool never substitutes a
timer for the canonical stage's exit evidence. Stage-definition drift and
current source revisions are visible; clocks and original identities are not
silently rewritten. Source drift does not erase recorded effort.

## Record active contribution, excluding idle time

```text
python -m carbon.challenge_pipeline.onboarding.telemetry start --challenge motor --cycle motor-prep-01 --stage S1_packet --milestone packet --actor packets --actor-kind AI_AGENT --source docs/development/challenge_pipeline/round1/motor-precision-joint-v2.md
python -m carbon.challenge_pipeline.onboarding.telemetry finish --challenge motor --ref-id <start-id>
```

Use HUMAN for a human contributor, AI_AGENT for an agent and TOOL for a
program's wall time. Finish **before** waiting on CI, another team, a provider,
or idle time; start another block on resumption. Contributors declare their
activity and identity; elapsed UTC seconds are measured, but actual continuous
activity is not independently verified. Totals are PARTIAL until coverage is
known. An open timer is reported, not extrapolated into earned labour.

Stage and preparation milestone must match #970/#1116's mapping. A solver
stage has separate generators/decks and verification-spec milestones; do not
allocate the same work to both. Blocks over 24 hours, duplicate closures and
overlapping blocks from the same contributor (including across Challenges)
are refused. Parallel contributors need distinct actual identities, not
aliases that double-charge one contributor's work. Shared work gets one
allocation, with its recipients explained separately.

Human labour hours, agent active hours and tool wall hours are **separate**.
Never report a subsecond generator run as person-hours saved. Never sum these
three categories into "labour" or turn an absent human record into evidence
that no human was involved.

## Feed the metrics tool and demonstrate improvement

```text
python -m carbon.challenge_pipeline.onboarding.telemetry export-effort --challenge motor
python scripts/dev/onboarding/build_metrics.py --effort-log <public-closed-human-events.json>
```

`export-effort` emits HUMAN records only, matching #1116's closed event input.
Agent/tool exports remain separately available in the status JSON under
`effort_exports_by_kind`; they must not become legacy team/person-hours.
Whole-second conversion rounds down; subsecond intervals remain visible in
the detailed clock view but do not become one fictitious second of labour.
New Challenges outside #1116's retrospective eleven-cohort set keep their
timers but need a prospective metrics source inventory before legacy export.

A valid speed comparison needs a matched task and scope, explicit active
baseline and assisted records, correct outputs, contributor kinds and wait
exclusions. Historical unrecorded labour remains UNKNOWN. An automation
rehearsal measures preparation, not completion of solver verification, banks,
Graphite or TESTED. A generator benchmark alone cannot establish onboarding
labour savings. Do not promise a positive speed-up before observing it.

## Privacy, authority and checks

Event tokens are public contributor handles, not raw prompts, customer data,
keys, addresses, spend ledgers or hidden case identities. Only explicitly
public source documents are read; secret/hidden/EV5/journal sources are
refused. No solver, cloud, network or spending action. No stage/qualification
rights are granted by an event or actor string.

Tests cover stage/effort separation, missing/open timers, overlapping shared
work, UTC requirements, source/definition drift, human-versus-agent/tool
accounting, append-only recording and the existing status/immutable-pack
regressions. Native results are diagnostic; canonical acceptance belongs to
the submitted exact head. Hub retired.
