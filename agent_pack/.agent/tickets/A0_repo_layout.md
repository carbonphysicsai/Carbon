# Ticket A0 — Package layout (C0 foundation, audit-first)

**Wave:** A  
**Build_Out:** **v1.4** C0 monorepo, §10 pack layout, §11 prefer map over rename  
**Depends on:** A-1  

**Goal:** Establish a Python package layout agents can grow into **without destroying** `poc/`, `neurons/`, `Carbon_Logic/`, or `Design_Specs/`.

**DoD:**
- [ ] **Baseline:** run existing tests/CI-equivalent before changes; record result in DECISIONS.md
- [ ] Installable or importable package root, e.g. `carbon/` or `src/carbon/` with `__init__.py` — **or** document that existing package root is KEPT and mapped
- [ ] Suggested submodules present as empty/stub packages **or** WRAP existing modules into these roles: `schema/`, `registry/`, `seeding/`, `scoring/`, `cards/`, `fees/`, `traineval/`, `mcp/`, `leaderboard/`, `logging_utils/`
- [ ] `.agent/` control files present at repo root **or** document that agent_pack copies must be synced to root for runtime
- [ ] Note in `.agent/DECISIONS.md`: mapping current dirs → Build_Out roles (`poc` = TrainEval promotion source, `Carbon_Logic` = logic to WRAP, `Design_Specs` = authority, `agent_pack` = agent control)
- [ ] No mass rename / no deletion of existing working trees for cosmetics
- [ ] **Baseline tests still pass** after layout work

**Must not:** Delete `poc/`, `Design_Specs/`, `Carbon_Logic/`, or rewrite the whole repo tree. Do not invent a second parallel package that orphans working code.

**Tests:** `python -c "import carbon"` (or equivalent) succeeds; DECISIONS.md updated; baseline pytest still green.

**Files (suggested if greenfield needed):**
```text
carbon/
  __init__.py
  schema/
  registry/
  seeding/
  scoring/
  cards/
  fees/
  traineval/
  mcp/
  leaderboard/
  logging_utils/
```
