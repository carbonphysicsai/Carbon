# Onboarding metrics: eleven public preparation cohorts

ONBOARDING-METRICS-01. Owner priority: onboarding is Carbon's specialty;
measure the process before claiming each Challenge is faster than the last.

[Full report](report.md) gives eleven cohort overviews and 110 milestone
rows. [Machine-readable report](report.json) retains source commits,
committer timestamps, first main integrations, revisions, PR lifetimes,
owners, reuse and censoring. [Source inventory](sources.json) binds main
`2cfc2508e267e1b794d32fa617603bcc7e122397` and explicit pending heads for
cooling #1074, warpage #1095, micromixer #1102 and structures #1109.
[Captured PR metadata](pull-requests.json) is a read-only API observation,
not a live status page or a claim of current-head acceptance.

## What is measured, and what is not

The ten requested milestones map to [the canonical stage map](../onboarding/stage_map.json):
brief S0; packet S1; question law and TRAIN/kit coverage S4; panel S3;
generators/decks and verification specification S2; comparator/equal-budget
S10; readiness bindings S6. They are deliberately **preparation artifacts**,
not ten accepted stage exits. A draft law is not approved; a panel proposal
is not registered, run or value-qualified; a verification spec is not a
successful solver verification; a TRAIN plan/hook is not solved TRAIN; a
readiness binding is not readiness YES. The full stage map also includes
bank and Graphite stages, outside this requested ten-column preparation audit.

Each row reports first artifact commit, last path revision, edit-span calendar
time, first-publication lag, PR open-to-merge time (JSON), and calendar gap
from the previous requested milestone. Main integration uses first-parent
Git history; GitHub mergedAt is used only where its merge identity matches.
The original publication of a file does not publish all subsequent revisions:
current source revision ancestry is reported separately. An open PR has no
merge duration; its age is right-censored. Timestamps are committer UTC,
not reconstructed work-session start times. Exact commit and PR identities
allow inspection of every basis without reading hidden historical material.

Shared components can predate a brief, and development often runs out of
order. Both remain visible; neither becomes a negative duration or zero work.
For public readiness bindings only, the collector reads the allowlisted
family JSON entry at immutable historical commits. This dates that family
entry's introduction, not the registry file's introduction for somebody else.
Missing historical paths or incomplete history mean UNKNOWN, never no work.

**Actual stage entry-to-accepted-exit time and historical person-hours are
NOT_RECORDED.** Git and PR timestamps cannot recover them. There are 72 unique
post-brief non-merge touch commits, 34 PR identities and three Git author
identities in this source inventory. These are activity proxies, not people,
hours, causal effort or accepted completions. Shared accounts represent many
sessions; shared PRs and commits are deduplicated, not charged to each family.
The observation cannot honestly establish "each onboarding faster" yet.

## Three slowest recurring observed arrivals, and concrete automation

Only positive, non-reuse, non-simultaneous arrival gaps enter this ranking.
A shared first-draft commit is **one delivery event**, using the median of
its cohort gaps. At least three distinct events are needed. No causal
owner-performance or independent-sample claim is made. In particular, one
shared code-verification spec cannot count as three recurring verification
delays simply because battery, motor and f02 reuse it.

| Preparation milestone | Median event gap | Largest cohort gap | Events / cohort rows | Next automation, owner and acceptance test |
|---|---:|---:|---:|---|
| Packet | 25.69 h | 25.97 h | 3 / 5 | Extend the existing packet generator with a source/decision-field reconciliation report. Packets owns it: each buyer limit, scope and observer links to its decision/source; unknowns remain HUMAN_INPUT; rerun on a decision amendment and show only the affected fields. Never auto-approve a buyer requirement. |
| Question law | 24.29 h | 97.29 h | 5 / 6 | Extend the law generator with a packet-to-law consistency linter. Packets + Test Lead: flag objective-vs-hard-limit, observer scope, P/Q/w, action resolution, NONE_FEASIBLE and two-refinement-band mismatches; battery time-as-objective and cooling case-interface changes are regression fixtures. Leave E/k/weights and measured thresholds under their actual authority. |
| Panel specification | 19.60 h | 68.70 h | 4 / 6 | Extend the panel generator with an immutable completed/scheduled physical-tuple reuse index and registration diff. Packets + Data Collection: every action × condition × rung is either retained, already scheduled or newly needed, never silently redrawn; report frontier coverage gaps and allocation-aware cost bounds. No registration or dispatch without authority. |

These are **proposals**, not new implementations or quantified labour savings.
KEEP the existing generators (#973/#976/#977), status/timeline tools
(#979/#985), ready-to-run panel preparation (#997), kit-domain checks and
readiness evidence checks. WRAP their outputs rather than replacing the
pipeline or duplicating Optimizer/Data Collection ownership. All three
automation acceptances must preserve buyer problem/value and scientific
decision authority, not improve timings by lowering the task's standard.

The largest observed law gap (97.29 h) is not an estimate of drafting effort:
laws can wait for changed buyer scope, reference evidence or another lane.
The source inventory includes sketches and generated drafts where those are
the existing artifacts; this is why cohort timings cannot be compared as
equivalent accepted deliverables. Original branches may also have been
rebuilt/cherry-picked; this measures the retained current-history lineage,
not unrecorded work before it. First packet and brief sometimes share one
commit; that is bundling, not instantaneous onboarding.

## Reproduce and measure future effort honestly

From the repository root, on a full public Git history with the captured
pending-head objects available:

```text
python scripts/dev/onboarding/build_metrics.py
python scripts/dev/onboarding/build_metrics.py --check
python scripts/dev/onboarding/build_metrics.py --capture-prs
```

Default and check replay retained API metadata against immutable source pins.
Capture refreshes read-only public PR metadata; API unavailability is explicit,
not absence or green. Source/API digests bind the report. No bodies from
protected case packs, private operator stores or hidden banks are opened;
only an explicit public readiness registry may have its JSON history read.
No solver, cloud lifecycle, payment or evidence execution is performed.

For future **team effort**, provide `--effort-log <public-duration-events.json>`.
Each closed event has `event_id`, `challenge`, `stage`, `actor`, integer
`duration_s`, `basis` (MEASURED_ACTIVE_DURATION or SELF_REPORTED_ACTIVE_DURATION),
and a nonempty `source`. IDs are unique; durations are 1–86,400 seconds per
event. Log active work only, excluding idle waits, CI/provider delay and
parallel work charged again to another family. Shared work needs one
allocation, not a copied event for every recipient. Do not put confidential
session text or customer inputs in the record. Totals are explicitly PARTIAL
until coverage is known; unrecorded stages remain UNKNOWN.

Future full-stage elapsed comparison also needs sourced entry and accepted
exit events under the stage map. This ticket does not invent or approve those
events. Compare same stage/scope and baseline; keep calendar lead time,
active team effort, solver/compute time and buyer-value outcomes separate.
For this first retrospective, there is no measured time-saved number and no
proof of a monotonic improvement trend.

## Boundaries and maturity

Engineering tool implemented and native diagnostic tests run; canonical
acceptance is required at the submitted head. Historical preparation report,
not scientific qualification, launch readiness, paid traction, a new spend
grant or runtime activation. Battery EV5, sealed journal 14 and live contracts
are untouched. Development Hub is retired under current delivery policy.
