## 2026-10-07 — REFERENCE-CREDIBILITY-01: distinguish a buyer's target from earned evidence

**Ticket:** CHALLENGE-REFERENCE-CREDIBILITY-01.
**Origin:** owner's direct 2026-10-07 addition to all eight customer packets.
**Status:** selected documentation approach; recommended tolerances HUMAN_INPUT.

Owner instruction includes:

> For each Challenge name: the tool the buyer most likely uses today, whether
> our current solver (PyBaMM, GetDP, OpenFOAM, Elmer, CalculiX, etc.) is that
> tool, the target tier, the benchmark cases to use, and the acceptance
> tolerance (HUMAN_INPUT with a recommendation).

> Claims stay “matches the reference simulator”, never “matches reality”,
> unless Tier 3 is met.

## Selected approach and rationale

Add one subsection within each packet's reference policy and a shared
interpretation companion. Mock buyer tool choices are role-play inferences
from engineering workflows and official tool capabilities, not market-share
findings, actual customers or licence access. Use primary vendor/benchmark/
author sources; name mismatched chemistry, geometry, material and observation
semantics rather than treating tutorials as task qualification.

Recommend Tier 2 for the seven offline design/simulation workflows. Battery's
EV-use buyer demands Tier 3 identified-cell experimental corroboration; interim
Tier 2 parity can support simulator screening only. Other buyers need Tier 3
only for the later, explicitly named hardware-performance use. Same tool name
does not establish Tier 1; actual buyer model/settings are absent. All eight
new-job credibility states are NOT_DEMONSTRATED, irrespective of older solver
verification. No tier, qualification or production claim is earned here.

Keep new comparison tolerances HUMAN_INPUT with numeric recommendations, even
where earlier DEVELOPMENT convergence criteria were selected under delegation.
Cross-tool agreement and self-convergence are different evidence; a tighter
agreement recommendation does not silently replace an existing numerical gate.
Failure to resolve a buyer boundary remains unresolved, never tolerance slack.

Cooling's ongoing truth remains the periodic cell. Under the owner's latest
“ignore the full cold plate” instruction, full-plate work is excluded from this
ticket; older assembly requirements remain deferred, not met by cell evidence.
Do not adopt the forwarded proposed 48-hour free-CPU budgets as an execution
grant or assert unmerged retired-bank publication code is active on main.

## Alternatives, interfaces and revision path

Rejected: treating open-source and commercial solvers as automatically
equivalent; requiring lab data for every offline simulator-matching job;
granting tiers from references to publications; presenting recommendation
numbers as approved thresholds; adding a second grader/qualification registry;
changing numeric sheets or #758/#759's owned files. The common ten-section
packet remains intact. Documentation-only interface; no runtime migration.

Locations: `docs/development/challenge_pipeline/round1/reference-credibility.md`
and the eight section-5 subsections, index and static tests. Branch
`codex/reference-credibility-tiers`, starting main `cd9d0bb253`.
To supersede, change the affected subsection and this decision prospectively;
retain historical evidence under its exact contract. Science visibility #42
(@harshaa765); PR Lead/Carbon Validator coordination #643. Recommendation: KEEP
the documentation approach; owner/science acceptance of tolerances, actual
buyer tool/settings, licence/data rights, experimental evidence, qualification
and execution authority remain separate HUMAN_INPUT. No response is required
to continue this bounded documentation implementation.
