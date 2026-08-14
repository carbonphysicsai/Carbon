# Ticket A9 — Miner MCP skeleton (C9)

**Wave:** A  
**Build_Out:** C9; Miner_MCP.md tool surface  
**Depends on:** A2, A5, A6, A7, A8  

**Goal:** Miner-facing tools for free-loop iteration + submit, with disclosure and isolation guards.

**Required tools (Wave A):**
| Tool | Behavior |
|------|----------|
| `info` | Challenge list / status from registry (no secrets) |
| `prior` | Placeholder or redacted prior JSON (no full champ weights) |
| `scaffold` | Return mock scaffold stub |
| `dry_validate` | Calls A2 schema validator |
| `estimate` / light path | Optional; uses TrainEval **mock** only; never emissions |
| `submit` | FSM + submission_id |
| `get_submission_result` | Budgeted EvaluationCard only |

**DoD:**
- [ ] Handlers exist (in-process OK if full MCP server is heavy; keep interface clean for later transport)
- [ ] `dry_validate` → schema
- [ ] `submit` → A7 FSM
- [ ] `get_submission_result` → A6 budgeted card when SCORED
- [ ] estimate/light cannot set `emission_capable` or write weights
- [ ] Prior path does not return official seeds or full champion strategy+weights
- [ ] Tests: each tool happy path + one reject/deny path

**Must not:** Implement production prior intelligence or real GPU train in this ticket. Placeholder prior is fine.

**Tests:** `pytest tests/test_mcp_skeleton.py -q`

**Pin to Carbon:** Free Autoresearch loop is the miner UX; official exam remains validator-side only.
