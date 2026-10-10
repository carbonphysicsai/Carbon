# Battery baseline: recorded milestone history

ONBOARDING-TIMELINE-01. The [automatic report](battery-v3.md) and
[full identities](battery-v3.json) map public artifacts to #970 S0–S10.
This is a **partial historical baseline**, not a completed onboarding benchmark.

The first reference module was committed 25 September 2026, before the
October customer packet. The common worked example was committed 6 October;
the EV customer packet 7 October; its v2 and ambient-indexed v3 successors
8 October; the round-2 law 9 October; the middle-band panel specification
10 October. Old versions keep their original identity and do not prove v3.
The initial customer brief's authoring start is not recorded. Code reuse is
not negative drafting time. The readiness JSON path has ambiguous history
(rename/reintroduction), and its dates are not solver-package acceptance.

Bank runbook, readiness reports, Graphite plans and the TESTED definition have
recorded dates. Their existence does not establish a current-law sealed bank,
all enabled-level launch readiness, completed A/B/C, T3, confirmed-recipe Q1,
incentive canary, cheap-baseline advantage or stage-end acceptance. Thus battery
brief-to-tested elapsed time remains UNKNOWN. #970's manual dated rows remain
history, not overwritten by a new interpretation.

## Automatic recording, no extra manual timestamps

`python -m carbon.challenge_pipeline.onboarding status --challenge battery --format json`
derives `artifact_timeline` each time from existing explicit path bindings.
All future configured Challenges get dates without another timestamp board.
Missing/untracked/refused paths and shallow history stay explicit. Git refs
are resolved once to immutable identities. No fetch/network or body read of
historical files occurs. The public supplement names older battery versions;
no private execution root or bank is examined.

`python scripts/dev/onboarding/build_timeline.py --challenge battery --out docs/development/challenge_pipeline/onboarding-timeline/battery-v3.json`
retains the same data as JSON plus a readable table. `--main-ref` may name a
local main ref; it never fetches it. The ledger generator from #975 now calls
the same implementation for PROCESS.artifact_calendar_timeline. At unchanged
refs and document bytes its output is deterministic; refreshes bind the new
refs rather than rewriting a historical snapshot silently. Existing cost and
cycle-time unknowns are preserved.

Only artifact timestamps are automated here. Accepted stage entry/exit,
effort and time lost still need explicit stage-owner evidence. Future cycle
comparisons must use the same contract and start/end definitions; they may
not subtract arbitrary artifact dates or compare machine milliseconds to
historical human/calendar work.
