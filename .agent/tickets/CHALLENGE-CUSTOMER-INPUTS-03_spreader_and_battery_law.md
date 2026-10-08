# CHALLENGE-CUSTOMER-INPUTS-03 — Cooling inputs and Battery continuous law

Authority: Ryan's direct 2026-10-08 request following merged #804;
OWNER-FIRST-THREE-CUSTOMER-ROUND-01 and OWNER-BATTERY-COOLING-PACKETS-02.
Starting main: `ce0fe89b62beb0ff3cb2ce1f2511ee4856bf3545`.
One branch `codex/customer-inputs-v3`, one PR to PR Lead. DEVELOPMENT,
SPECIFIED only; completion conditional on applicable CI and normal merge.

## Scope and plan

1. KEEP v1/v2 packets, #776 rows and historical Battery optimizer as history.
   Inspect actual reference/task support; baseline public static tests.
2. Add sourced, owner-pending Cooling spreader/TIM proposals, an axial
   conduction-map specification and a public feasibility-panel recipe.
3. Make Battery continuous requirements primary by owner direction; specify
   service draws, support gates, P/Q/w, answer occupancy, refined edges and a
   versioned time-objective optimizer. Preserve the four-vector audit grid.
4. Add static and synthetic regression tests, lessons, index pointers and
   coordination; inspect the diff, validate, deliver one PR.

## Definition of done

- Copper-lid dimensions and both effective TIM joints have a recommended set,
  ranges, primary sources and explicit owner-pending status. No vendor figure
  is misrepresented as a modern accelerator package specification.
- Conduction pins, boundary coupling, map transfer, verification, joint
  uncertainty and reference-failure treatment are explicit. A Gaussian fit
  cannot substitute for an arbitrary solved map. Scope remains one periodic
  cell, never a full plate or manifold.
- A 30-case base panel plus separately counted controls/refinement/witnesses
  is reproducible as a recipe; accepted solver/package/case/grant pins stay
  null. Data Collection owns packaging and execution under later authority.
- Battery has continuous thermal/plating margins, separate P/Q/w, explicit
  ambient/SOC/ageing support, bank exposure and no redraws. Grid remains four
  vectors. Expected diversity has a computable definition, bounds and an
  honest NOT_DEMONSTRATED value, not an invented empirical count.
- Optimizer minimizes admissible session minutes without a time cap; charging
  thermal/plating scope, discharge diagnostics and optional cooling remain.
  Changing start SOC explicitly changes the time observable; arbitrary aged
  state is not supported by the current reference.
- Motor and five-family law/optimizer bytes are unchanged. Current runtime,
  #815/VALIDATOR-26, #808 reports, EV5/journal14/live contract are not edited.
- Native static tests and quality are diagnostics; pinned GitHub CI supplies
  acceptance. No Docker, solver, spend, hidden material or Hub changes.

## Evidence and coordination

Baseline: `py -3.11 -X utf8 -m pytest
tests/cpu/test_customer_packet_revisions_v2.py
tests/cpu/test_challenge_question_laws.py
tests/cpu/test_first_three_customer_packets.py
tests/cpu/test_customer_reference_credibility.py -q`: 69 passed.
Coordination: #643 comment6061301571; science #42 comment6061302513.
Reserved values are represented fail-closed; drafting does not wait for routine
lead approval. Owner approval of the spreader set and scientific adequacy is
separate from this specification's engineering delivery.

Final native diagnostic command adds `tests/cpu/test_customer_inputs_v3.py`,
`tests/cpu/test_challenge_pipeline.py` and `tests/cpu/test_design_tasks.py` to
the baseline: **125 passed in19.20s**, including18 new static/synthetic checks.
Black formatting and Ruff passed. Pipeline validation: DEFINING,7 records,
449 valid lessons,0 awaiting decisions,3 controllers/3 pending identities
before the final lesson. An initial float-conversion assertion failed and
was corrected; one interim invocation's completion was not captured and is
not claimed as passing. These are native diagnostics, not solver evidence
or pinned CI acceptance. No Docker/prune, reference run or spend occurred.
