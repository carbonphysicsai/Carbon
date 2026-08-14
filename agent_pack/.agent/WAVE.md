# Carbon Agent Wave Status

**Current wave:** A  
**Mode:** Cheap inference (Hermes + Engy GLM/Kimi; Grok escalate on fail ×2)  
**Build_Out:** v1.3  

## Wave A checklist

| ID | Item | Status | Evidence |
|----|------|--------|----------|
| A-1 | **Orientation** — repo map + ORIENTATION.md | todo | |
| A0 | Repo layout + `.agent/` present | todo | |
| A1 | CI skeleton (pytest) runs | todo | |
| A2 | Strategy schema + dry_validate | todo | |
| A3 | Challenge registry (file-backed) + LIVE blocked without qualification | todo | |
| A4 | Seeding domains + mock_ guards + leakage tests | todo | |
| A5 | Scoring engine + fixture pack schema (HUMAN_INPUT thresholds) | todo | |
| A6 | Card store + Phase 0 disclosure filter | todo | |
| A7 | Fees + submission_id + FSM skeleton | todo | |
| A8 | TrainEvalAPI **stub** (emission_capable=False) | todo | |
| A9 | MCP skeleton tools (info, prior, scaffold, dry_validate, estimate, submit, get_submission_result) | todo | |
| A10 | Leaderboard API (public fields only) | todo | |
| A11 | Logging / basic observability | todo | |
| A12 | Invariant tests green in CI | todo | |

**Statuses:** `todo` | `in_progress` | `done` | `blocked`

## Notes

- Complete **A-1 orientation** before any implementation ticket.
- Do not mark done without test or file evidence.
- After all `done`, write `WAVE_A_REPORT.md`.
- Escalate to grok-4.6 only after fail ×2; log in DECISIONS.md.
