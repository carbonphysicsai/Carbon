# CHALLENGE-AI-COOLING-PB-ADV-09 — serve Mode X without changing the frozen study

**Ticket:** `CHALLENGE-AI-COOLING-09_pb_adv_mode_x.md`

**Problem.** Cooling's Challenge-neutral search adapter advertises only
`PB-INV` and its `select_point` callback raises `pb_adv_not_served`, although
the neutral design-search engine already defines PB-ADV and registered methods
can execute it. The mechanism must become usable without choosing a new attack
budget, acceptance threshold, physical population or reference campaign.

## Agent-recommended working decision

Repair `carbon/cold_plate/customer_decision.py` in place. Preserve the exact
PB-INV contract text and digest construction. Add PB-ADV as an adapter/request
mode, reuse the existing normalized die and hydraulic margins, implement the
same deterministic predicted-feasible point ordering used by
`carbon.design_search.methods`, validate each point against the oracle log
before writing the commitment, and map each committed point to one existing
classified-reference job.

The request's required positive `verification_budget` is K. No default is
added. PB-INV continues to require enough evidence budget to check every
condition; PB-ADV requires only a positive K because each selected item is one
exact point. No reference object enters construction or search.

## Implementation location

- `carbon/cold_plate/customer_decision.py`
- `tests/cpu/test_cold_plate_customer_decision.py`
- `docs/development/AI_ACCELERATOR_COOLING_LEVEL0_LAUNCHPAD.md`
- the ticket and one lesson file per execution

Branch: `codex/cooling-pb-adv`; one PR to `main`.

## Alternatives considered

1. **Clone Battery's Mode-X optimizer into Cooling.** Rejected: the neutral
   search engine already owns registered methods and cloning would create two
   method authorities.
2. **Put PB-ADV into PR #587's attack adapter.** Rejected: that PR owns
   admission attack families and controls, while this ticket owns the
   customer-decision/search mechanism explicitly called out by the Test Lead.
3. **Choose K and a wider grid in this ticket.** Rejected: those are study
   design/science and spend inputs, not implementation details; the code can
   require them and fail closed.
4. **Rewrite the existing decision contract to include PB-ADV semantics.**
   Rejected: it would alter the digest-generating meaning of the already frozen
   PB-INV study for no execution need.
5. **Let PB-ADV verify every condition for every selected design.** Rejected:
   Mode X selects exact adversarial points; multiplying each into all
   conditions changes K's meaning and the registered verification accounting.

## Interfaces, invariants and downstream impact

- `SearchAdapter` remains Challenge-neutral; no Cooling or Battery literal is
  added to shared `carbon/design_search` code.
- Construction/commitment remains upstream of reference access.
- Attempted queries, typed infrastructure failure and sealed-oracle behavior
  remain unchanged.
- Missing study inputs fail closed; no placeholder becomes LIVE evidence.
- Reference failure remains separate from a model constraint violation.
- The frozen counted Cooling study and PR #587 controls remain unchanged.
- Track-B controls and fresh confirmation remain later bounded tickets.

## Reversibility and supersession

The change is local and additive. To supersede it, change the PB-ADV selection
and validation helpers in `customer_decision.py`, their focused tests, and this
ticket's working decisions. A future approved scientific policy can supply a
different frozen K/grid or acceptance rule without migrating the mechanism.

## Human-reserved input

No human-reserved value is needed to implement this mechanism. A real run
still requires an explicitly frozen design/condition set, K, model panel,
budgets, reference allocation, analysis policy and any applicable compute or
confirmation approval. The ticket dispatches none of those.
