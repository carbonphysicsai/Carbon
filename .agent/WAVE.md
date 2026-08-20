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
| A1 | C0 | CI skeleton (pytest, CPU) + preserve existing CI | done | Corrective PR #9 merged as `819da3c163c2fb9476a6881aab8740cc6984066e` after independent rereview; final-head CI run `32326384939` passed 27 CPU tests and the code-quality gate |
| A2 | C2 | Strategy schema + dry_validate | done | PR #12 reviewed final head `d73f697ebd9df9b8c96b7a46fd4c9986444f0928` merged as `bfc0b97e1b16625141de3950428bc2fdf69f42ea`; post-merge main CI run `32360050671` passed 258 default CPU tests and the code-quality job |
| A3 | C1 | Challenge registry + LIVE qualification **hash** gate | done | Exact base `e6fb20b1dc361ded442fcf41d118cea5f2c775cd`; independently reviewed/rereviewed final head `149f9a74351b02a9b615d0015c22b74187ab0f55` passed PR CI `32377387086`, merged as `69b938d1c4fd0aca58276940d15df50b1b68e5d1`, and is ancestral to current `main`; post-merge push CI `32379421897` passed 392 CPU tests and Code quality at unchanged `Ruff 757/776; Black 62/68` with no new debt and changed files clean; A4 remains `todo` and has not started |
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
