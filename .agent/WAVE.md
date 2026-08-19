# Carbon Agent Wave Status

**Current wave:** A  
**Executor:** any (Codex / Hermes / human / …) — see `agent_pack/EXECUTION_PROTOCOL.md`  
**Build_Out:** **v1.4** §12 Wave A  
**Constitution:** repo root `AGENTS.md`  
**Spec pin:** record commit SHA in `.agent/ORIENTATION.md` at start  

## Workflow

```text
A-1 orientation → one ticket → baseline tests → implement → tests → review/merge → next
```

- Sequential by default.
- Harness-native worktrees/branches preferred.
- Model routing is **not** part of this board (optional under `agent_pack/executors/`).

## Wave A checklist

| ID | Build_Out | Item | Status | Evidence |
|----|-----------|------|--------|----------|
| A-1 | — | Orientation — repo map, KEEP/WRAP table, ORIENTATION.md | done | `.agent/ORIENTATION.md` audits `0eed4e9`; DoD checked in `.agent/tickets/A-1_orientation.md`; maintainer dispositions in `.agent/DECISIONS.md` |
| A0 | C0 | Package layout (audit-first; map poc/Carbon_Logic) | done | Root `carbon/` + 14 reserved roles; isolated `pip install --no-deps -e` and outside-tree imports pass; exact base/head workflow delta has no A0 regression; evidence in `.agent/DECISIONS.md` |
| A1 | C0 | CI skeleton (pytest, CPU) + preserve existing CI | todo | |
| A2 | C2 | Strategy schema + dry_validate | todo | |
| A3 | C1 | Challenge registry + LIVE qualification **hash** gate | todo | |
| A4 | C6 | Seeding domains + leakage tests | todo | |
| A5 | C5 | Scoring engine + fixture Score Pack | todo | |
| A6 | C12 | Card store + Phase 0 disclosure filter | todo | |
| A7 | C13 | Fees + submission_id + FSM (**CANCELLED**, FAILED_INFRA refund) | todo | |
| A8 | §5 | TrainEvalAPI **stub** (emission_capable=False) | todo | |
| A9 | C9 | MCP tools: info, prior, scaffold, dry_validate, estimate, submit, get_submission_result | todo | |
| A10 | C14 | Leaderboard (public fields only) | todo | |
| A11 | C16 | Logging **+ metrics** / redaction / failure tags | todo | |
| A12 | §2 | Invariant suite green in CI | todo | |

**Statuses:** `todo` | `in_progress` | `done` | `blocked`

## Suggested order

```text
A-1 → A0 → A1 → A2 → A3 → A4 → A5 → A6 → A7 → A8 → A9 → A10 → A11 → A12
```

Recommended gate: human review after **A3**, then continue.

Start Codex (or any agent) with **A-1 only** first.

A9 depends on A2, A6, A7, A8. A12 depends on A4–A10.

## Notes

- Complete **A-1** before implementation.
- Do not mark done without test or file evidence.
- Before/after each ticket: run **baseline** pytest/PoC smoke.
- After all `done`, write `.agent/WAVE_A_REPORT.md`.
- Wave B+ out of scope unless human expands.
