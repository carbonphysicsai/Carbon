# Carbon Agent Wave Status

**Current wave:** A  
**Mode:** Cheap inference (Hermes + Engy GLM/Kimi; Grok escalate on fail ×2)  
**Build_Out:** v1.3 §12 Wave A  

## Wave A checklist (maps to Build_Out components)

| ID | Build_Out | Item | Status | Evidence |
|----|-----------|------|--------|----------|
| A-1 | — | Orientation — repo map + ORIENTATION.md | todo | |
| A0 | C0 | Package layout (`carbon/` modules) | todo | |
| A1 | C0 | CI skeleton (pytest, CPU) | todo | |
| A2 | C2 | Strategy schema + dry_validate | todo | |
| A3 | C1 | Challenge registry + LIVE qualification gate | todo | |
| A4 | C6 | Seeding domains + leakage tests | todo | |
| A5 | C5 | Scoring engine + fixture Score Pack | todo | |
| A6 | C12 | Card store + Phase 0 disclosure filter | todo | |
| A7 | C13 | Fees + submission_id + FSM skeleton | todo | |
| A8 | §5 | TrainEvalAPI **stub** (emission_capable=False) | todo | |
| A9 | C9 | MCP tools: info, prior, scaffold, dry_validate, estimate, submit, get_submission_result | todo | |
| A10 | C14 | Leaderboard (public fields only) | todo | |
| A11 | C16 | Logging / redaction | todo | |
| A12 | §2 | Invariant suite green in CI | todo | |

**Statuses:** `todo` | `in_progress` | `done` | `blocked`

## Suggested order

```text
A-1 → A0 → A1 → A2 → A3 → A4 → A5 → A6 → A7 → A8 → A9 → A10 → A11 → A12
```

A9 depends on A2, A6, A7, A8. A12 depends on A4–A10.

## Notes

- Complete **A-1** before implementation.
- Do not mark done without test or file evidence.
- After all `done`, write `WAVE_A_REPORT.md`.
- Escalate to grok-4.6 only after fail ×2; log in DECISIONS.md.
- Wave B+ (generator, real TrainEval, validator neuron) is **out of scope** for this pack.
