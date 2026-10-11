# CHALLENGE-CUSTOMER-INPUTS-04 — thermal budget and Battery charge map

Authority: Ryan's direct 2026-10-08 follow-up to #817. One DEVELOPMENT /
SPECIFIED PR to PR Lead. Starting repository authority is main
`fa2cf02972a6ac7cce97bd5c5ab2236ac5080e5a`; this separate branch starts at
#817's handed-off `209ae6094e07de07e92692014c0504ffd4ec51f9` and depends on
that PR. No pushes to its branch, runtime changes, solves or spend.

## Working contract

1. KEEP earlier packets and evidence. Check the public feasibility branch,
   reference conventions and baseline static/synthetic tests.
2. Add an auditable resistance budget: coolant and bare plate, both TIMs,
   copper and unresolved spreading; distinguish the adopted interface plane
   from a prospective junction requirement. Put a hold on the 53-job recipe.
3. Record the owner's Battery v3 map decision; port continuous P/Q/w and
   per-band diversity, and amend the optimizer without changing frozen scores.
4. Test arithmetic, versioning, support gates, per-band hard constraints and
   value-equivalence semantics. Deliver one PR with lessons and lead handoff.

## Definition of done

- The 28-K plate anchor includes coolant rise; the old postprocessed TIM is
  not counted again. Uniform and ratio-3 die fluxes have explicit units.
- Interface and die-side temperatures are separately reported. Paper screens
  are not physical lower bounds or proof that every cold plate fails.
- Buyer levers have conditional numerical targets and applicability caveats;
  the owner selects the temperature plane/lever. Panel release stays null.
- Battery v3 has one protocol/switch/cooling action per band, local hard
  safety gates, weighted minutes and per-band value-equivalent regret. All five bands
  are mandatory even at a small buyer weight. No shared-protocol requirement.
- Numeric distributions and 0.5-min resolution remain HUMAN_INPUT. Mix-only
  draws do not claim new per-band answers. No NONE_FEASIBLE redraws or E reset.
- Public evidence distinguishes feasible-map existence from settled optima;
  SOC/ageing/action extensions require a pinned owning reference/observer.
- Earlier laws/evidence, Motor/five-family work, EV5/journal14/live contract,
  score rules, queue and permit state remain unchanged. Hub is retired.

## Evidence and coordination

Baseline native diagnostic: 87 passed in 7.08s across customer-inputs v3,
packet revisions, question laws, first-three packets and credibility tests.
Paper arithmetic executed with `carbon.cold_plate.domain.pg25` only: no
reference solver called. A subsequent rg glob diagnostic failed on Windows;
the arithmetic result was captured and is not a solver result.
Start coordination: #643 comment6062039290; science #42 comment6062225767.
Local Docker is unavailable; do not repeat its failed bootstrap. GitHub's
pinned CI supplies canonical acceptance. Engineering delivery does not
release a feasibility panel or imply valV2's permit is live.

Validation commands (Windows native diagnostics, not canonical acceptance):

```text
py -3.11 -X utf8 -m pytest tests/cpu/test_customer_inputs_v4.py tests/cpu/test_customer_inputs_v3.py tests/cpu/test_customer_packet_revisions_v2.py tests/cpu/test_challenge_question_laws.py tests/cpu/test_first_three_customer_packets.py tests/cpu/test_customer_reference_credibility.py tests/cpu/test_challenge_pipeline.py tests/cpu/test_design_tasks.py -q
147 passed in 20.34s
py -3.11 -X utf8 -m pytest tests/cpu/test_customer_inputs_v4.py -q
22 passed in 2.75s after the SOC support/observable clarification
py -3.11 -X utf8 -m pytest tests/cpu/test_customer_inputs_v4.py tests/cpu/test_customer_inputs_v3.py tests/cpu/test_customer_packet_revisions_v2.py tests/cpu/test_challenge_question_laws.py -q
74 passed in 14.51s after aligning the proposed regret rule with #820
py -3.11 -X utf8 -m black --check tests/cpu/test_customer_inputs_v4.py
1 file would be left unchanged after formatting
py -3.11 -X utf8 -m ruff check tests/cpu/test_customer_inputs_v4.py
All checks passed
git diff --check
No whitespace errors
```

Pipeline validation inspected 7 records and 452 lessons, with no awaiting
lessons; the protocol remained DEFINING and three controller identities
remained pending. These assertions validate documents, arithmetic and synthetic
semantics, not physical adequacy. Current delivery retires Hub maintenance;
no Hub source/event/regeneration changes are required. Conditional closeout
requires this bounded PR's applicable CI and PR Lead merge. No owner-reserved
panel release, qualification, map reference coverage or permit is earned here.
The indexed-task proposal is owned by #820 at
`e1d0fdbec3a77f464e936d2750b55a78dfb5d2a8`; this amendment does not duplicate
it. While #817 remains open, this follow-up is stacked on its branch. PR Lead
retargets it to main after #817 merges; main-targeted CI then supplies canonical
acceptance. Do not interpret absent stacked-PR checks as a pass.
