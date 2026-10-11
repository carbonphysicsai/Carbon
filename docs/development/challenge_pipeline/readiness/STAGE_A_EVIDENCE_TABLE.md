# Stage A readiness evidence table (battery, L0 and L1)

Prepared for the Test Lead's sign-off, 2026-10-09. For every battery item that baseline 2
(`BASELINE_2_2026-10-09.md`) left NOT_BUILT or REVIEW_REQUIRED, this lists what exists on main
(an existing test, decision or run record, each path checked to exist) and marks **GAP** where
nothing citable exists. "Handled by hand" as the gate spec allows: this table is evidence for a
human sign-off, not a PASS. Nothing here changes a gate status, and the Test Lead signs. The
evidence is level-agnostic unless noted: at L1 the same citations apply and the L1-specific
adapter tests are listed where they exist.

| Item | Evidence on main | Gap or sign-off |
|---|---|---|
| **O1** ownership map review | `carbon/challenge_pipeline/readiness/battery-fastcharge-ageing-development-v1/ownership.json` (committed map; the automated half passes) | **GAP:** the Test Lead's committed review `reviews/O1.json` |
| **P3** fixture phase-3 dry run | `tests/cpu/test_graphite_phase3.py` (end to end: proposal, pod run, frozen-rule score, bundle, clean rebuild, scripted model, no spend); phase-3 live runs 1 to 5 at Level 0 | **GAP (wiring):** the gate has no recorded per-challenge test for battery; the test above is the candidate to record in `readiness/challenges.json` |
| **R2** containment with a host canary | `tests/cpu/test_carrier_containment.py`, `tests/cpu/test_carrier_containment_mutations.py`; decision `.agent/decisions/2026-10-05-GRAPHITE-CARRIER-CONTAINMENT-01.md`; runs as the `carrier_containment` step of `phase4 prelive` | **GAP (wiring):** needs the analysis image manifest and Docker on the host; no readiness check wraps it separately from R1 |
| **R4** model settings | full-context defaults and charges: `.agent/decisions/2026-10-04-GRAPHITE-D34.md`, `.agent/decisions/2026-10-05-GRAPHITE-D35.md`; prelive reports `attacker_model` | **GAP:** an output cap sized from use (lesson E3 stays OPEN in the register) and per-role model blocks in the prelive report |
| **R5** grants | `docs/development/graphite/grants/GRAPHITE-GRANT-PHASE4.json`, `GRAPHITE-GRANT-PHASE3-R4.json`; binding `tests/cpu/test_graphite_phase4_grant.py` (R5's automated half verifies it); R4 arithmetic and headroom in `.agent/decisions/2026-10-05-OWNER-GRAPHITE-PHASE3-R4-01.md` | **Sign-off:** the Test Lead confirms pricing with lost-run headroom, tokens-only where no pods run. Stage A's own grants (Level 0 kimi-k3 Constructor, kimi-k3 Attacker share) are **GAP** until bound on main |
| **R6** host disk and window | disk policy `carbon/challenge_pipeline/readiness/policies.json` (30 GB); Data Collection's posted host window (about 10 threads and 8 GB), relayed 2026-10-09 | **GAP:** the written window is a message, not a committed artifact; the Test Lead records `reviews/R6.json` |
| **R7** budget text | `tests/cpu/test_agent_door_usability.py` (the "0 of 0 research trials left" line), `tests/cpu/test_attack_authoritative_boundary.py` (same section); decisions `.agent/decisions/2026-10-05-AGENT-DOOR-USABILITY-01.md`, `.agent/decisions/2026-10-05-RESEARCH-TOOL-USABILITY-01.md` | **Sign-off:** the register row E9 still reads OPEN; the Test Lead confirms these tests close it (no readiness check is wired) |
| **A2** attack family coverage | adapters at L0 to L4: `tests/cpu/test_attack_battery_adapter.py`, `test_attack_battery_level1_adapter.py`, `test_attack_battery_level23_adapters.py`, `test_attack_battery_level4_adapter.py` (every family has an attack example and controls) | **GAP:** the machine check that the Attacker has a route to each family (lesson A2) |
| **A3** coverage stop rule | `tests/cpu/test_graphite_attacker_stop_rule.py`; decision `.agent/decisions/2026-10-05-GRAPHITE-ATTACKER-STOP-RULE-01.md` | **GAP (wiring):** not recorded in `readiness/challenges.json`; confirm the rule is configured for the Level 0 and Level 1 sessions |
| **A5** attribution policies | registered and versioned: `carbon/agent_campaign/graphite/attribution_policies/registry.json` (pod-attribution-v1, v2), `carbon/agent_campaign/graphite/baseline_policies/registry.json` (baseline-retry-v1) | **GAP:** the Test Lead's `reviews/A5.json` (that the Attacker has a family probing each assumption) |
| **S1** promotion rule | `carbon/battery/exam.py` (`DEVELOPMENT_RULE`: comparison `n_min`, `n_boot`, `alpha`, `important_min`; `equivalence_margin_rel`, OD-2) | **GAP:** that the margin is measured from the challenge's noise source is a statement of the exam rule, not a committed measurement run recorded for the gate |
| **S2** gate failures rank last | `tests/cpu/test_battery_admissibility_gate.py` (an inadmissible model scores 0, so ranking cannot compensate), `tests/cpu/test_battery_ev5_run.py` (gate-failing members rank last), `carbon/battery/value/scoring.py`; run-5 fix #617 | **GAP (wiring):** no per-challenge readiness test id recorded |
| **S3** gate margin study | none that matches the item. `tests/cpu/test_battery_margin_component.py` and `test_battery_near_margin.py` concern error margins near the decision boundary, not a margin study of each gate (minimum reference margin and 1st percentile) | **GAP:** the gate audit's margin study (VALIDATOR-09) is not recorded for battery |
| **S4** noise source | seed (Test Lead's planned ruling, 2026-10-05); battery rule v2 evidence in `carbon/battery/exam.py` | **GAP:** the Test Lead's committed `reviews/S4.json` |
| **D1** frozen decision study | `docs/development/evidence/ev4-2026-10-01/freeze-manifest.json` and `decision-references.jsonl.gz`; EV5 frozen: `.agent/decisions/2026-10-03-OWNER-EV5-FREEZE-01.md`, `docs/development/evidence/ev5-2026-10-03/` | **GAP (wiring):** no readiness check; the Test Lead confirms these meet "finite comparator, commitment before reference access, representative and boundary groups" |
| **D2** equal-cost harness adapter | `carbon/battery/value/design_search_adapter.py`; `carbon/design_search/track_b.py`; `tests/cpu/test_design_search_track_b.py` | **Sign-off:** the Test Lead confirms the B ladder |
| **D3** timing calibration | reference solves on the host: `docs/development/evidence/battery-quiz-designs/README.md` (35 reference solves, median 82 CPU-s) | **GAP:** no counted-plan timeout set from a battery calibration (>= 2x p95); battery has no counted plan |
| **D4** importer on a real solver output | EV4 decision references from real solves: `docs/development/evidence/ev4-2026-10-01/decision-references.jsonl.gz`, `accounting/` | **GAP:** no readiness check; the Test Lead confirms EV4's import is the real-output run (the register's E7 concerned cooling's counted campaign) |
| **D5** reference coverage and refinement policy | coverage reported: 6 of 12 development scenarios resolvable on the common mask (`docs/development/evidence/graphite-run5-q1/q1-report.json`, `mask`); refinement policy `.agent/decisions/2026-10-05-OWNER-GRAPHITE-TEST-WAVE-07.md` section 2 | **Sign-off:** the Test Lead confirms the policy is decided; the report is not a gate artifact |
| **D6** confirmation analysis pinned | EV5: `carbon/battery/value/ev5_run.py`, `tests/cpu/test_battery_ev5_run.py`, EV5 results `docs/development/evidence/ev5-2026-10-03/` | **GAP (wiring):** none for the new confirmation set; the Test Lead confirms EV5's pin step satisfies this for battery |
| **V3** multi-seed promotion | the Test Lead's ruling that Graphite promotes on a single seed (lesson S2 OPEN) | **GAP:** a committed `reviews/V3.json` (decision FAIL by that ruling, until a multi-seed promotion policy lands) |
| **H2** tuning and confirmation sets disjoint | confirmation role registered: `carbon/challenge_validator/confirmation_sets/graphite-confirmation-v1.json`; tuning set specified in OWNER-GRAPHITE-TEST-WAVE-08 | **GAP:** no `graphite-tuning-v1` role and no overlap checker on main |
| **H4** gates tested on hidden and tuning data | none | **GAP:** the gate audit on hidden and tuning predictions does not exist (VALIDATOR-09) |

## V1 and V2 (run now, Level 0)

Built from the committed graphite-run5 panel with the EV4 references
(`scripts/dev/battery/readiness_q1_panel.py`, `readiness/q1.py build`,
`carbon/challenge_pipeline/readiness/battery-fastcharge-ageing-development-v1/q1_report.json`).

- **V1:** the report is recorded, current against the scoring rule digest, and consistent with
  its members. Kendall tau-b is **-0.473** and Spearman rho **-0.539** over 8 eligible members,
  with 6 score-value divergences. The tau band is 0.0 because one seed per recipe gives a single
  panel, so there is no noise band to read it against. A negative tau is recorded, not a blocker
  (gate item V1): the first Graphite runs are framed as alignment measurements, not improvement
  hunting. The gate reports V1 as REVIEW_REQUIRED (the automated half passes); the Test Lead's
  framing review is the remaining step.
- **V2:** PASS, 7 distinct decision-outcome vectors among the 8 eligible members, above the floor
  of 2.
- **Level 1:** there is no Level 1 Q1 report (run 5 was Level 0), so V1 and V2 at Level 1 still
  fail until one is recorded.
