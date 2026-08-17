# AGENTS.md — Carbon repository instructions

Permanent instructions for **any** coding agent (Codex, Hermes, Claude Code, etc.) or human contributor working in this repo.

Keep this file concise. Detailed requirements live in `Design_Specs/` and `agent_pack/` tickets.

---

## Authority

1. `Design_Specs/SPEC.md` (if present) — system doctrine  
2. `Design_Specs/Miner_MCP.md` — miner-facing behaviour  
3. `Design_Specs/Scoring.md` — scoring semantics  
4. Generator / validation / evidence packs — science for a challenge  
5. `Design_Specs/Launch_Bar.md` — stop-ship before trust claims  
6. `Design_Specs/Build_Out.md` **v1.4** — implementation sequencing and Wave acceptance  

`agent_pack/` tickets implement Wave work; they do **not** override Miner_MCP or Scoring.

---

## What this repo is

Carbon is a Bittensor subnet for **physics-scored neural operator training strategies**: miners submit strategies; validators train/eval under hidden data and gates; emissions require surviving independent physics/robustness checks—not accuracy alone.

Phase 0 is the vertical loop + testnet path. Landscape/specialists are post-P0.

---

## Non-negotiable constraints

- **Never invent science.** No fabricated gate thresholds, envelopes, dossier pass/fail, or LIVE physics parameters. Use `HUMAN_INPUT` / `null` / `BLOCKED_FOR_LIVE_UNTIL_SET`.
- **Stubs never emit.** Mock/stub TrainEval metrics must not write emission weights or LIVE ranks (`emission_capable=False`).
- **Mock isolation.** `mock` / `light_*` paths must refuse official packs and official seeds.
- **No seed leakage.** Official seeds, draw IDs, or reversible hidden identifiers never appear in EvaluationCard, leaderboard, MCP outputs, or miner-visible logs.
- **Fee ≠ score.** Exam fees never enter scoring.
- **LIVE is human-gated.** Qualification manifests with **hashes bound to the exact challenge version** are required; non-null YAML alone is not enough. Agents implement the gate; humans sign.
- **Infra ≠ science.** `FAILED_INFRA` is refund/retry—not a physics failure.
- **Do not silently change public interfaces** (MCP tool contracts, card schemas, score pack keys) without an explicit ticket and DECISIONS note.

---

## Existing code policy

Classify before rewriting:

**KEEP → WRAP → REPAIR → REPLACE**

Prefer mapping `poc/` and `Carbon_Logic/` over forced renames or deletes. Working PoC, tests, and CI are assets—not obstacles.

---

## How to take work

1. Read relevant specs for the ticket (Build_Out § for that component, plus Miner_MCP/Scoring when touching miner or score paths).
2. For Wave work, follow `agent_pack/EXECUTION_PROTOCOL.md` and the ticket under `agent_pack/.agent/tickets/` (or synced `.agent/tickets/`).
3. **Baseline tests before** modifying code; **baseline + ticket tests after**.
4. Scope changes to the current ticket only.
5. Stop and report if the ticket needs an unresolved scientific or architectural decision.
6. Security, validator isolation, keys, and Bittensor weight paths require human review before merge to main.

---

## Verification (definition of done)

A ticket is done only when:

- Ticket DoD checkboxes are satisfied with evidence  
- Required tests pass (ticket tests + existing regression/smoke)  
- No new seed leakage or emission from stubs  
- `agent_pack/.agent/WAVE.md` (or `.agent/WAVE.md`) updated if using the wave board  

Do not declare complete on “implementation looks right” without tests.

---

## Build / test (common)

```bash
# Typical unit path (CPU)
pytest -q

# PoC smoke if present (see poc/ README)
# python -m poc...   # use the command documented in-repo
```

Exact commands may evolve; prefer what CI runs in `.github/workflows/`.

---

## Out of scope for agents unless explicitly assigned

- LIVE flip / signing qualification manifests  
- Inventing Score Pack thresholds or generator envelopes  
- Mainnet emission parameters  
- Landscape / specialist product claims  
- Parallel multi-agent rewrites of interdependent core contracts without human sequencing  

---

*Constitutional layer for Carbon. Details: `Design_Specs/Build_Out.md` v1.4 and `agent_pack/`.*
