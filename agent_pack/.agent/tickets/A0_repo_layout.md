# Ticket A0 — Repo layout + agent files

**Wave:** A  
**Goal:** Ensure agent control files and a sane Python package root exist without destroying existing `poc/` / `neurons/` / `Design_Specs/`.

**DoD:**
- [ ] `.agent/WAVE.md`, `.agent/INVARIANTS.md`, `.agent/tickets/` present in repo
- [ ] Optional: `carbon/` or `src/carbon/` package dir if missing (do not delete `poc/`)
- [ ] Short note in `.agent/DECISIONS.md` mapping current dirs → Build_Out roles

**Must not:** Mass-rename the whole repo; delete Design_Specs or poc.

**Tests:** N/A (structure only)
