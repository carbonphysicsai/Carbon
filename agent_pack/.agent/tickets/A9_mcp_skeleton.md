# Ticket A9 — MCP skeleton tools

**Wave:** A  
**Goal:** Miner-facing tool stubs aligned with Miner_MCP.md: info, prior, scaffold, dry_validate, estimate, submit, get_submission_result.

**DoD:**
- [ ] Tool handlers exist (can be in-process functions if full MCP server is heavy)
- [ ] dry_validate calls strategy schema
- [ ] submit returns submission_id via FSM
- [ ] get_submission_result returns budgeted card only when scored
- [ ] estimate/light paths do not write emissions
- [ ] Basic tests per tool happy-path + one reject path

**Must not:** Implement full production prior intelligence; placeholder prior JSON is fine.

**Tests:** `pytest tests/test_mcp_skeleton.py -q`
