# Ticket A9 — Miner MCP skeleton (C9)

**Wave:** A  
**Build_Out:** C9; Miner_MCP.md tool surface  
**Depends on:** A2, A5, A6, A7, A8  

**Goal:** Miner-facing tools for free-loop iteration + submit, with disclosure and isolation guards.

**Required tools (Wave A):** info, prior, scaffold, dry_validate, estimate/light (mock only), submit, get_submission_result

**DoD:**
- [ ] Handlers exist (in-process OK)
- [ ] `dry_validate` → schema; `submit` → FSM; `get_submission_result` → budgeted card
- [ ] estimate/light cannot set emission_capable or write weights
- [ ] Prior path does not return official seeds or full champion strategy+weights
- [ ] Tests: each tool happy path + one reject/deny path

**Must not:** Implement production prior intelligence or real GPU train in this ticket.

**Tests:** `pytest tests/test_mcp_skeleton.py -q`
