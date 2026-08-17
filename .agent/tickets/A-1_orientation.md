# Ticket A-1 — Full repo orientation (audit-first)

**Wave:** A (pre-work)  
**Build_Out:** **v1.4** §0 authority, §11 layout, §16 agent doctrine  
**Depends on:** nothing  

**Goal:** Learn the real Carbon repo before writing code. Produce a durable orientation note the rest of Wave A trusts. Prefer archaeology over greenfield.

**DoD:**
- [ ] Top-level tree listed (`Design_Specs/`, `poc/`, `neurons/`, `Carbon_Logic/`, `docs/`, `appendices/`, `agent_pack/`, `tests/`, CI, package roots)
- [ ] Read (or explicitly note missing): `Design_Specs/Build_Out.md` **v1.4** §0–§8 + §12 Wave A, `Miner_MCP.md`, `Scoring.md`, root README/`SPEC.md`, existing `poc/` / `Carbon_Logic/` / neurons / tests
- [ ] Record **git commit SHA** and **Build_Out version** string in `.agent/ORIENTATION.md`
- [ ] **KEEP / WRAP / REPAIR / REPLACE** table for major existing modules (PoC, CI, any Carbon_Logic, neurons)
- [ ] `.agent/ORIENTATION.md` written with:
  - Repo map (real vs missing)
  - Spec pin (commit + Build_Out v1.4)
  - Classification table
  - Authoritative docs for Wave A (authority order)
  - Gaps vs Build_Out Wave A checklist (§12)
  - Explicit non-goals (LIVE thresholds, Landscape, Specialist bank, inventing physics)
- [ ] `.agent/WAVE.md` A-1 marked done with path to ORIENTATION.md

**Must not:** Start A0–A12 implementation before ORIENTATION.md exists. Do not invent SPEC text not in the repo. Do not plan mass deletes of working PoC/CI.

**Suggested evidence:** `.agent/ORIENTATION.md` mentions Build_Out Wave A components (C0–C16 relevant set), at least one existing code path with KEEP/WRAP, and the commit pin.
