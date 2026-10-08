# OWNER-BATTERY-COOLING-PACKETS-02 — owner-approved prospective scope revision

**Ticket:** CHALLENGE-CUSTOMER-PACKETS-02.
**Origin:** Ryan's direct owner-approved revisions dated 2026-10-08.
**Status:** selected mock DEVELOPMENT buyer requirements; not production
limits, adopted question-law sampling or scientific qualification.

## Owner selections

Battery's 10–80% session time is the **minimised objective**, not a hard
30-minute limit. Plating reaction overpotential >=0 V and the **45-C charging
thermal limit** stay hard. Split charging and test-discharge thermal scope;
report test discharge as a diagnostic. Cooling remains optional and reported.
Unchanged voltage/capacity requirements keep their v1 roles unless separately
superseded; do not infer permission to relax them.

Cooling's hotspot heat map is defined **at the cold-plate interface after a
die-side spreader or lid**. Its properties are stated buyer inputs. Report
TIM, hotspot-ratio and inlet alternatives; **select none**. Current work stays
cell-only under the earlier full-cold-plate exclusion. Retain 85 C at the
explicit TIM-interface proxy, not a claim about a modelled die junction.

## Reported evidence and correction, not a new execution

Data Collection's successor public feasibility branch is
`claude/motor-feasibility-02`. Owner-provided Battery source:
`031284d1a6f8c56f1355606908feaa737b5b9a86`, `battery-feasibility-02/`, 435
solves. Report **NO_VERIFIED_FEASIBLE_PROTOCOL at 25 C** for the old brief;
best within the limits **32.9 min**. The previously quoted **35.6 min** came
from 30-s voltage probes; the charge-integral observer gives **63.3 min** for
that reported observation. These are different facts: 63.3 is not the best
32.9, and neither is proof that the new complete-panel brief is feasible.
The old textual report remains history with this explicit correction.

Owner-provided Cooling source:
`3ab30becb6dcee0a2ec43272883c2800fb32a64a`, `cooling-feasibility-02/`, 128
solves. Uniform stratum best **81.2 C**, every reported hotspot stratum
**>=117 C**. At ratio 3 the stated TIM/local-flux jump is about25 K, leaving
15 K of plate-rise budget against about28 K best plate rise. The approximate
budget decomposition is explanatory; it is not a reconstruction of the
>=117-C hotspot result. No reported case is relabelled as post-spreader truth.
These source commits are not #758's merged head. Codex resolved the commit
identities but did not independently replay the reported physical results.

## Implementation and downstream seams

Add `round1/battery-ev-fast-charge-v2.md`, `round1/cooling-cell-v2.md`,
`round1/first-three-requirements-v2.json`, and versioned #776 law/quiz-impact
amendments. Preserve v1 data and six unaffected question-law rows. Update
indexes only. Test Lead/Carbon Validator own future role-aware observers,
answer keys, gates and optimizer/task integration; #802/#783 are not edited.
Classify obsolete packet/law directions as DOCUMENTATION_LAG resolved by
these versions; runtime phase projection and new reference coverage remain
MIGRATION_REQUIRED. Missing spreader properties/maps remain HUMAN_INPUT.

Rejected: retroactively passing the old Battery brief; replacing 35.6 with
32.9 or conflating 63.3 with a bank minimum; loosening plating/charging
temperature; making cooling compulsory; guessing a spreader or silently
lowering hotspot ratio/TIM/inlet; interpreting uniform feasibility as a
whole-panel pass; changing scores until existing models pass.

Reversibility: supersede these v2 amendments prospectively in a new version;
never rewrite sealed reference identities or old results. No runtime migration
is included. Recommendation if unchanged: KEEP. Sampling, refinement bands,
weights, spreader characterization, actual reference adequacy, security,
rights, qualification and launch remain with their named owners.

## Other owner clarifications and notification

Acquisition notes are handed to Data Collection / REFERENCE-PACKAGES-01 on
[#643](https://github.com/carbonphysicsai/Carbon/issues/643#issuecomment-6058122942).
Data Collection owns pinned builds/images/decks and feature receipts; no
competing package implementation here. #801 is the separate Hetzner triage
grant, not spare CPU. #787/#801 are unchanged and confer no authority through
this packet PR. No new reference run or spend occurs here.

Shared Docker engines: **never prune**; cleanup may remove only the executor's
own images by explicit tag. Read-only audit found no explicit Docker prune
command in this chat's recorded calls; that does not establish what other
sessions or commands inside wrapped scripts did.

Packet coordination: #643 comment6058124592; science #42 comment6058125042.
Battery EV5, sealed journal sequence14, live contract, protected material,
family queue and 45/30/25 candidate status remain unchanged. Hub is retired.
