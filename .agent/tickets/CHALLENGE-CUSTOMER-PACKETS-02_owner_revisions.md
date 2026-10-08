# CHALLENGE-CUSTOMER-PACKETS-02 — prospective Battery and Cooling revisions

**Authority:** Ryan's direct 2026-10-08 instruction, recorded in
OWNER-BATTERY-COOLING-PACKETS-02; OWNER-FIRST-THREE-CUSTOMER-ROUND-01 and
OWNER-PORTFOLIO-DEV-ROUND-01. Starting main:
`689692c0694ad4d184ef6bd58ce5decc811d4d4a`.
**Status:** candidate prepared for PR Lead; DEVELOPMENT documentation/static-test ticket; SPECIFIED
ceiling. One branch `codex/customer-packet-revisions-02`, one PR to PR Lead.

## Working contract and reuse

KEEP v1 packets, numeric sheet, feasibility follow-up, #776 proposal sheet and
Motor/Cooling quiz text as history. WRAP the ten-section format in two new
v2 packets. Add a versioned planning amendment and a #776 v2 amendment that
explicitly replaces only Battery/Cooling rows; inherit the other six rows and
common P/Q/w/exposure proposals unchanged. Indexes point to the new versions
and clearly identify old prose as history, not current instructions.

Implement the owner's objective/phase-scope and post-spreader heat-map choices,
not new science. Separate the reported 63.3-minute corrected observation from
the reported 32.9-minute best within limits. No independent solver replay is
claimed. Mark missing spreading inputs, reference support and sampling/gate
registration HUMAN_INPUT/UNRESOLVED. Flag Q2/Q3 and task/optimizer migration
for Test Lead/Carbon Validator without overlapping #802 or #783 runtime work.

## Definition of done

- New ten-section Battery packet removes the hard 30-minute deadline; hard
  45-C charging and 0-V plating remain. Test-discharge extrema are diagnostic;
  cooling is an optional reported action, not a mandatory selected solution.
- New Cooling packet is cell-only. Heat maps are at the cold-plate interface
  after a buyer-described spreader/lid. TIM/ratio/inlet alternatives are
  reported without selecting values. No new full-plate work.
- Source heads/counts and old/new observation meanings are explicit. Earlier
  sealed evidence and requirement versions are not re-scored.
- Grid and continuous laws reflect the new scope; no time-cap requirement
  axis survives in Battery v2. Diversity remains measured from a supported
  bank, not invented from thresholds. NONE_FEASIBLE is not redrawn away.
- Q2/Q3 impact and reference-credibility consequences are specified. Current
  runtime, EV5, sealed journal sequence 14, grants, #787 and #801 are untouched.
- Focused public static tests check the amendments, dimensional reasoning,
  version inheritance and preserved historical texts. Run applicable CI;
  native Windows tests are diagnostics only. Record execution lessons.
- Hand the existing f02/f08/f13 agent notes to Data Collection under
  REFERENCE-PACKAGES-01; package/deck/image ownership remains theirs.
- Notify #643/#42 and deliver with `Codex is done; PR Lead may take over.`

## Plan and boundaries

1. Read current authority, public packet/law implementations and ownership;
   baseline existing consistency tests.
2. Record owner decision; add v2 packets, planning/law amendments and quiz
   impact; point indexes to them without changing v1 observations.
3. Add static regression tests; inspect complete diff and run focused checks,
   quality and pipeline validation. Push once ready and hand off one PR.

No solvers, Docker builds/cleanup, remote dispatch, spend, hidden material,
runtime registration, score weights, family-queue transition or qualification.
Shared Docker engines must never be pruned; any future cleanup targets only
the executor's own explicit image tags. The Hub is retired and remains frozen.
Completion is conditional on applicable CI and PR Lead's normal merge.

## Coordination and initial evidence

Data Collection notes: issue #643 comment 6058122942. Packet start: #643
comment 6058124592 and science #42 comment 6058125042. Baseline native command:
`py -3.11 -X utf8 -m pytest tests/cpu/test_first_three_customer_packets.py
tests/cpu/test_challenge_question_laws.py tests/cpu/test_customer_reference_credibility.py
tests/cpu/test_customer_feasibility_panels.py -q`: **67 passed**. This is
public-document consistency, not canonical acceptance or physical evidence.

V2 focused diagnostic command adds `tests/cpu/test_customer_packet_revisions_v2.py`
to that baseline: **81 passed**, including14 new static/synthetic checks.
Six historical artifacts retain normalized UTF-8/LF content hashes. This is
not a runtime integration test or evidence of a feasible physical bank.

Final native diagnostics add `tests/cpu/test_challenge_pipeline.py` to the
above command: **109 passed in16.18s**. Ruff and Black checks on the new test
pass after a recorded initial formatting correction. Pipeline validation:
DEFINING,7 valid records,443 valid lessons,0 awaiting decisions,3 controllers
with3 pending identities before the final lesson. Missing reference identities
remain missing; no protocol state/queue/runtime changed. Local canonical
execution is unavailable in this environment; do not repeat the prior Docker
attempt. Pinned GitHub CI supplies acceptance. No engine prune or cleanup ran.
