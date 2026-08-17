# Carbon Agent Wave Status

**Current wave:** A  
**Mode:** Cheap inference (Hermes + Engy GLM/Kimi; Grok escalate on fail ×2)  
**Build_Out:** **v1.4** §12 Wave A  
**Spec pin:** record commit SHA in ORIENTATION.md at start  

## Workflow

```text
A-1 orientation → branch agent/wave-a/<id> → baseline tests → implement → tests → review/merge → next
```

- Sequential by default (no swarm on interdependent contracts).
- No direct pushes to `main` from the agent.
- Soft $ budget per ticket — see MODEL_ROUTING.md.

## Wave A checklist (maps to Build_Out v1.4 components)

| ID | Build_Out | Item | Status | Evidence |
|----|-----------|------|--------|----------|
| A-1 | — | Orientation — repo map, KEEP/WRAP table, ORIENTATION.md | todo | |
| A0 | C0 | Package layout (audit-first; map poc/Carbon_Logic) | todo | |
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

Recommended money gate: stop after **A3** for human review, then continue.

A9 depends on A2, A6, A7, A8. A12 depends on A4–A10.

## Notes

- Complete **A-1** before implementation.
- Do not mark done without test or file evidence.
- Before/after each ticket: run **baseline** pytest/PoC smoke.
- After all `done`, write `WAVE_A_REPORT.md`.
- Escalate to grok-4.6 only after fail ×2; log in DECISIONS.md with spend.
- Wave B+ (generator, real TrainEval, validator neuron) is **out of scope** for this pack unless human expands.
