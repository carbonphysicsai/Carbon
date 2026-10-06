## 2026-10-05 — COOLING-GRAPHITE-COMPARE-01: apply the measured public practice comparison

**Ticket:** CHALLENGE-AI-COOLING-12.
**Status:** IMPLEMENTED_WORKING_DECISION, subject to ticket tests and PR merge.

**Problem.** OWNER-GRAPHITE-TEST-WAVE-06 §1 approved Cooling's testing-only
paired comparison, and PR #598 committed the Test Lead's margin measurement,
but `CoolingPracticeRule.compare` still returned a descriptive/non-promoting
mean difference. The authority/code seam is `IMPLEMENTATION_LAG`.

**Decision.** Keep Cooling's public exam and construction unchanged. The
Cooling adapter uses OD-2's disposition logic with its own component keys and
the owner-approved settings (30 minimum pairs, 4,000 bootstrap replicates,
0.05 alpha, 10 important-region pairs) and the measured relative margin
`0.13157222884271824`. The deterministic bootstrap RNG seed `20261005` is
an engineering reproducibility choice, not a physics threshold. Pin the exact
margin record's canonical bytes by SHA-256 and advance the composite practice
rule identity to v2 prospectively. Require the complete 100-case
public set for a positive testing comparison; missing predictions fail the
existing schema gate. Report the algorithmic bootstrap interval as descriptive
for the adaptively seen fixed practice set, never as population confidence.

**Implementation:** `carbon/challenge_validator/cooling_scoring.py`,
`tests/cpu/test_cold_plate_scoring.py`; intended PR on branch
`codex/cooling-practice-comparison`.

**Alternatives rejected.** Importing Battery's `final_compare` directly would
couple Cooling to Battery's component vocabulary and live exam file. Keeping
the descriptive comparison contradicts WAVE-06 after PR #598's measurement.
Changing the score or the case set is outside this ticket.

**Interfaces and invariants.** The comparison identity is prospective and
testing-only. A mandatory gate failure remains non-compensable; unavailable
reference or infrastructure evidence cannot promote; public practice remains
outside protected and official evaluation. Historic results are not rescored.
The adapter's existing `promotable` field is a Graphite testing disposition,
not a frontier, settlement, customer or LIVE claim.

**Reversibility.** A new comparison version can supersede this policy without
reinterpreting old records. If the Test Lead revises the margin or sampling
interpretation, change this decision and the adapter's identity/pin in a new
ticket; do not edit the historical record.

**Human-reserved input.** Fresh protected confirmation population and analysis,
science qualification, production Score Pack metrics and winner-weight
authority remain HUMAN_INPUT and fail closed. No new value is selected here.
