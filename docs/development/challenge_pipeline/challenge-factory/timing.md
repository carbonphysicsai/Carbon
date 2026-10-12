# Measured clocks, missing labour, proposed same-family curve

Use the current stage map and #1127's append-only `onboarding.telemetry`; no
second timer or stage definition. The historical metrics report covers eleven
cohorts × ten **preparation milestones**, captured at source main
`2cfc2508e267e1b794d32fa617603bcc7e122397`. It is not today's live readiness.
All 110 rows have unknown accepted stage elapsed time and human effort. Git
commit/PR timestamps supply artifact arrivals, **not labour** or actual accepted
entry→exit durations. First publication and later revised packet integration
are separate facts. Shared work is counted once.

## Available measured baseline

| Observable | Median / maximum | Independent event count | Interpretation |
| --- | --- | ---: | --- |
| Packet artifact arrival gap | 25.69 / 25.97 calendar h | 3 | Not active drafting time; five cohort rows share only three events |
| Question-law arrival gap | 24.29 / 97.29 calendar h | 5 | Not six independent replications and not demonstrated blocking |
| Panel arrival gap | 19.60 / 68.70 calendar h | 4 | Six cohort rows; waits and reuse cannot be converted to labour |

These are the three slowest recurring preparation arrivals in the retained
report, not proof of today's three biggest labour bottlenecks. Relevant
automation is now implemented: `onboarding/reconcile.py`,
`law_consistency.py`, `panel_diff.py`, plus packet/law/panel generators.
Reuse their precise missing-field and reuse diffs; do not propose their
implementation again. Acceptance and new evidence still need owners.

Current-main public telemetry contains **24 motor TOOL events**, six paired
effort blocks and six PREPARED entry/exit attempts from the automation-checker
rehearsal. The three milestone active totals are:

| Recorded stage | Active TOOL seconds, two attempts | Stage calendar seconds, attempt 1 / 2 | Human/agent labour |
| --- | ---: | --- | --- |
| S1 packet checker | 0.957949 | 1.001335 / 0.587938 | UNKNOWN / UNKNOWN |
| S4 law checker | 0.727081 | 0.766282 / 0.559121 | UNKNOWN / UNKNOWN |
| S3 panel checker | 0.655636 | 0.700401 / 0.594269 | UNKNOWN / UNKNOWN |

Total declared-active tool time = **2.340666 s**. It is neither the original
battery drafting baseline nor person-hours saved, and PREPARED is not an
accepted stage exit. Unrecorded/other stages are UNKNOWN, never zero. The
timestamps carry UTC offsets; the telemetry renderer normalises them to UTC.
[timing.json](timing.json) and its tests bind these numbers to public records.

## PROPOSED target, not a measured improvement

For **matched same-family preparation scope only**, propose
`H(n) = H1 × (0.5 + 0.5 × 0.65^(n−1))`, where H1 is the first **actually
measured active contribution** for that scope after kit bootstrap. Floor 50%
and decay 0.65 are **ASSUMPTION / HUMAN_INPUT**, not scientific or service limits.
Keep HUMAN, AI_AGENT and TOOL curves separate; do not combine them into labour.

Illustrative H1 = **48 active h ASSUMPTION**, unrelated to Git gaps, gives
48 → 39.6 → 34.14 → 30.591 h for preparation cases 1–4 and approaches 24 h.
This is a falsifiable target, not a promise each complex job is faster. New
PDE/material/history/observer features belong to a new comparison stratum or
kit version. External waits, native execution and independent qualification
have separate lead-time/cost curves; full brief-to-TESTED duration is UNKNOWN.

## Prospective measurement protocol

1. Predeclare family/kit version, unchanged output/quality/claim scope, difficulty
   stratum, required inputs and exact accepted-stage evidence separately.
2. Record stage ENTRY/EXIT attempts and active start/finish blocks using the
   existing CLI. Finish before CI, provider, owner or idle waits; record resumes.
   Separate HUMAN/AI_AGENT/TOOL. Contributor declarations are not independently
   verified labour tracking. Shared tasks get one allocation plus recipients.
3. Record input-ready time, each missing input/feature and rework cause; compare
   drafting/checking work, not a script's wall time against a human calendar gap.
4. Compute actual stage lead time, partial active contribution, reuse fraction,
   rework and evidence-run cost. Report coverage. With incomplete baseline or
   missing human blocks, **speed-up UNKNOWN**. Do not claim zero labour.
5. Report H(n)/H1 only for complete matched records, with cohort count and
   differences. If worse, show why; improve the kit or revise the target
   prospectively, never delete slow jobs or lower accepted quality to fit it.

No fake retroactive timers are created here. The next authorized same-family
pilot/preparation supplies a real baseline; a target alone earns no improvement.
