# Hermes + Cheap Inference Pack — Carbon Wave A

Hand this to **Hermes Agent** (or equivalent) to execute Carbon **Build_Out v1.3 Wave A**.

**Inference strategy (2026-08-14):**

```text
default:     glm-5.2   (Engy)     → volume
tools:       kimi-k3   (Engy)     → selective
escalate:    grok-4.6  (xAI)      → fail ×2 only
cleanup:     Fable/Sol (optional) → after WAVE_A_REPORT
```

## What’s in this pack

| Path | Purpose |
|------|---------|
| `HERMES_KICKOFF.md` | Master agent instructions |
| `PASTE_INTO_HERMES.txt` | One-shot start prompt |
| `hermes_config.example.yaml` | Engy default + Grok escalate notes |
| `.agent/WAVE.md` | Live checklist / scoreboard |
| `.agent/INVARIANTS.md` | Never-violate rules |
| `.agent/MODEL_ROUTING.md` | Model + cost policy |
| `.agent/DECISIONS.md` | Decision log |
| `.agent/tickets/A0–A12` | Bounded Wave A work units |
| `skills/carbon_wave_a.md` | Optional Hermes skill text |

## Setup (human, ~10 minutes)

1. Files live under **`agent_pack/`** in the Carbon repo (or copy to repo root).
2. Put keys in `~/.hermes/.env`:
   ```bash
   ENGY_API_KEY=...
   XAI_API_KEY=...    # optional; only for Grok escalate
   ```
3. Merge `hermes_config.example.yaml` into `~/.hermes/config.yaml` (default `glm-5.2`).
4. From Carbon repo, paste **`PASTE_INTO_HERMES.txt`** into Hermes.

## After Wave A

- Read `.agent/WAVE_A_REPORT.md`
- Human/SciML: Wave B science slots, real TrainEvalAPI
- Optional: **Grok or Fable cleanup** on architecture quality

## Out of scope

- Wave B/C/D full execution
- LIVE flip / qualification signoff
- Real GPU training backend
- Landscape / specialists
