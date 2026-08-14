# Ticket A0 — Package layout (C0 foundation)

**Wave:** A  
**Build_Out:** C0 monorepo, §10 pack layout awareness  
**Depends on:** A-1  

**Goal:** Establish a Python package layout agents can grow into without destroying `poc/`, `neurons/`, or `Design_Specs/`.

**DoD:**
- [ ] Installable or importable package root, e.g. `carbon/` or `src/carbon/` with `__init__.py`
- [ ] Suggested submodules present as empty or stub packages: `schema/`, `registry/`, `seeding/`, `scoring/`, `cards/`, `fees/`, `traineval/`, `mcp/`, `leaderboard/`, `logging_utils/`
- [ ] `.agent/` control files present at repo root **or** document that agent_pack copies must be synced to root for runtime
- [ ] Note in `.agent/DECISIONS.md`: mapping current dirs → Build_Out roles (poc = TrainEval promotion source, Design_Specs = authority, agent_pack = agent control)
- [ ] No mass rename of Hydrogen→Carbon leftovers beyond what already exists

**Must not:** Delete `poc/`, `Design_Specs/`, or rewrite the whole repo tree.

**Tests:** `python -c "import carbon"` (or equivalent) succeeds; DECISIONS.md updated.

**Files (suggested):**
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
