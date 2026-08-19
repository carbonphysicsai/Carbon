# Ticket A0 — Package layout (C0 foundation, audit-first)

**Wave:** A  
**Build_Out:** **v1.4** C0 monorepo, §10 pack layout, §11 prefer map over rename; `Design_Specs/Build_Out_Protocol_Extension.md` §2 A0 package layout
**Depends on:** A-1  

**Goal:** Establish lowercase `carbon/` as the canonical Python package, following the maintainer dispositions in `.agent/DECISIONS.md`, while preserving `poc/`, `neurons/`, `Carbon_Logic/`, and `Design_Specs/` as auditable source/reference trees during this ticket.

**DoD:**
- [ ] **Baseline:** run existing tests/CI-equivalent before changes; record result in `.agent/DECISIONS.md`
- [ ] Installable/importable lowercase `carbon/` package root with `__init__.py`; record the chosen root (`carbon/` or `src/carbon/`) and why
- [ ] Required/reserved package roles present as empty/stub packages **or** WRAP existing modules into these roles: `schema/`, `registry/`, `seeding/`, `scoring/`, `cards/`, `fees/`, `traineval/`, `mcp/`, `leaderboard/`, `logging_utils/`, `evaluation/`, `audit/`, `chain/`, `qualification/`
- [ ] Preserve narrow adapter boundaries: scientific/evaluation modules must not couple directly to Bittensor SDK objects where an adapter can preserve portability and testability
- [ ] Confirm root `.agent/` control files are the runtime board (WAVE, tickets, INVARIANTS)
- [ ] Note in `.agent/DECISIONS.md`: mapping current dirs → Build_Out roles (`poc` = first Burgers TrainEval promotion source; `Carbon_Logic` = legacy source to audit for selective promotion, not a supported namespace; `Julia` = v0 generator verification path; `Design_Specs` = authority; `agent_pack` = protocol docs only)
- [ ] Inventory imports of `Carbon_Logic`, `hydrogen`, and `Carbon`; migrate only the paths required for the A0 import/layout acceptance test, and record all deferred callers
- [ ] No mass rename / no deletion of existing working trees for cosmetics
- [ ] Re-run the exact baseline commands; introduce no new failures and record the before/after delta (the A-1 baseline is already red)

**Must not:** Delete `poc/`, `Design_Specs/`, `Carbon_Logic/`, or rewrite the whole repo tree in A0. Do not preserve stale namespaces merely for compatibility, copy legacy modules wholesale, repair scoring/science/CI beyond layout acceptance, normalize context filenames, implement later receipt/audit/chain/qualification/Bittensor behavior, or start A1+; A0 reserves structure and adapter seams only.

**Tests:** `python -c "import carbon"` succeeds; DECISIONS.md updated; exact baseline commands re-run with no new failures.
