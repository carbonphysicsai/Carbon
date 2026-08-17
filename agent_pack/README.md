# Hermes + Cheap Inference Pack — Carbon Wave A

Hand this to **Hermes Agent** (or equivalent) to execute Carbon **Build_Out v1.4 Wave A**.

**Inference strategy:**

```text
default:     glm-5.2   (Engy)     → volume
tools:       kimi-k3   (Engy)     → selective
escalate:    grok-4.6  (xAI)      → fail ×2 only
review:      Codex/Claude         → human-triggered diff review
cleanup:     Fable/Sol (optional) → after WAVE_A_REPORT
```

**Jereme review fixes applied (2026-08-17):** v1.4 pin, audit-first orientation, `${VAR}` Hermes keys, FSM/LIVE semantics, soft $ budget, branch-per-ticket, baseline tests, expanded observability ticket.

## Agent learns the repo first

Hermes **must** map and read the full Carbon repo (Build_Out **v1.4**, Miner_MCP, Scoring, poc/, Carbon_Logic/, CI) and write `.agent/ORIENTATION.md` with a **KEEP/WRAP/REPAIR/REPLACE** table **before** ticket A0. See `A-1_orientation.md`.

## Workflow (do not skip)

```text
Orientation → branch per ticket → baseline tests → implement → tests
  → independent review (human/Codex) → merge → next ticket
```

Sequential by default. No direct `main` writes from the agent.

## What’s in this pack

| Path | Purpose |
|------|---------|
| `HERMES_KICKOFF.md` | Master agent instructions |
| `PASTE_INTO_HERMES.txt` | One-shot start prompt |
| `hermes_config.example.yaml` | Engy default + Grok escalate (**`${VAR}`** expansion) |
| `.agent/WAVE.md` | Live checklist / scoreboard |
| `.agent/INVARIANTS.md` | Never-violate rules |
| `.agent/MODEL_ROUTING.md` | Model + cost + soft budgets |
| `.agent/DECISIONS.md` | Decision + spend log |
| `.agent/tickets/A-1, A0–A12` | Orientation + Wave A work units |
| `skills/carbon_wave_a.md` | Optional Hermes skill text |

## Setup (human, ~10 minutes)

1. Files live under **`agent_pack/`** in the Carbon repo (or copy control files to repo root if your harness expects `.agent/` at root).
2. Put keys in `~/.hermes/.env`:
   ```bash
   ENGY_API_KEY=...
   XAI_API_KEY=...    # optional; only for Grok escalate
   ```
3. Merge `hermes_config.example.yaml` into `~/.hermes/config.yaml`.
   - Use **`${ENGY_API_KEY}`** (with braces). Bare `$ENGY_API_KEY` is **not** expanded by Hermes.
4. Pin a starting commit if running a long agent session (`git rev-parse HEAD`).
5. From Carbon repo, paste **`PASTE_INTO_HERMES.txt`** into Hermes.
6. Recommended first money gate: fund ~**$25**, run **A-1 → A0 → A1 → A2 → A3**, review, then continue.

## After Wave A

- Read `.agent/WAVE_A_REPORT.md`
- Human/SciML: Wave B science slots, real TrainEvalAPI
- Optional: **Codex/Grok/Fable** cleanup on architecture quality

## Out of scope

- Wave B/C/D full execution (unless human expands)
- LIVE flip / qualification signoff
- Real GPU training backend as emission path
- Landscape / specialists
- Parallel multi-agent swarm on interdependent tickets
