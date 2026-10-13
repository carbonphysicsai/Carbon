# PLT-16 — UNIFIED-CONSTRUCTION-01 Phase 1, bounded

Authority: owner Platform3 queue; Test Lead's 2026-10-13 bounded reopening;
Carbon Validator's UNIFIED_CONSTRUCTION_01_DESIGN.md (operator design).
Starting main: af5906f56850bc15f77b586a556c8de7162b4179; PLT-13 merged
as 09003dfd2697a2e963f66d63465ec64aa4e9cb36. Reviewers: Carbon Validator
and Launchpad. One PR to main; never merge, release or deploy here.

Scope: pure Challenge-neutral public classifier, unified contract module,
level-free commitment library, and opt-in shadow diagnostics alongside the
existing ladder. Intake/commitment fact wiring is PLT-16b: do not edit
intake.py, intake_client.py or the service, currently owned by PR #1267.
No live signing, chain access, protected inputs, rented compute or new opening.

KEEP existing base validation, data-only variant readers, immutable policies,
child-process development compile and ladder evaluation. WRAP with additive
libraries and an opt-in operator shadow observer. Plans: (1) baseline; (2)
public contract/derivation/commitment; (3) receipt comparison and observer;
(4) canonical focused/invariant/quality acceptance, exact-head CI and handoff.

Working engineering decision PLT16-D1: distinguish content derivation from
opening/admission. derive() produces an observational binding from the same
core used by classify(); classify() applies the public ceiling/open/check
state and refuses before any signing. The shipped profile keeps every
widening INTERNAL and the external ceiling HUMAN_INPUT. A shadow observation
cannot grant admission, self-test acceptance, score, nomination or weight.
No compiler is imported by the public classifier. Combinations fail closed.

DOCUMENTATION_LAG: the current L2 policy includes pool_selection alongside
muon_spectral; L3 includes line_search alongside quasi_newton_family. Detect
all of each registered variant's fields, relative to its recorded defaults.
L1 arms resolve by content and canonical registry order, preserving each arm's
own bounds. Unknown top-level/parameter fields remain refused. A detection
binding pins the unified digest and registry version and can be re-derived.

Shadow equality reports separate derivation, compiled-route and rebuilt-
artifact bases. Absent second evidence stays incomplete, never MATCH/PASS.
No expression/recipe digest is relabeled as rebuilt artifact identity. The
optional observer records operator-only diagnostics after existing compile;
observer failure does not change legacy admission, scoring or eligibility.
Level 0 without the observer retains the full legacy behavior.

Acceptance: positive L0-L4/default/arm cases, malformed input and mixed types,
closed/open/ceiling/check failures, exact commitment and binding tamper cases,
cross-Challenge classifier fixture, shadow mismatch/missing evidence,
no-compiler import closure, legacy ladder/default golden; pinned canonical
focused tests, all invariants, Black/Ruff py310, hygiene and encoding check.
Historical map_ref WAVE-C/C-05; Hub retired, no maintenance. Ceiling:
DEVELOPMENT library/shadow engineering only. External security acceptance,
owner ceiling, combinations, production qualification and cutover stay closed.

Manifest: this ticket; .agent/decisions/PLT16-D1.md;
carbon/construction/unified.py; carbon/battery/unified_contract.py;
carbon/development_ladder/{unified_shadow,operate}.py;
tests/cpu/test_unified_construction.py;
tests/invariants/test_unified_classifier_unreachable.py;
docs/development/graphite/UNIFIED_CONSTRUCTION_SHADOW.md.
Validation: canonical.sh --focused tests/cpu/test_unified_construction.py
tests/invariants/test_unified_classifier_unreachable.py
tests/cpu/test_launchpad_construction_levels.py
tests/cpu/test_development_variant_daemon_intake.py; canonical.sh --focused
tests/invariants; Black/Ruff over changed Python; delivery hygiene against main.
Queue completion means tested PR handed to PR Head on a green exact head,
not merged, deployed, scientifically qualified or security accepted.
