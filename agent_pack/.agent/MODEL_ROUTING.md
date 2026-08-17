# Model routing — Carbon agent path

**Updated 2026-08-17** (Jereme pack review)

## Default stack

| Role | Model | Provider | Cost posture |
|------|--------|----------|--------------|
| Bulk implement + tests | **glm-5.2** | Engy (`api.engy.ai`) | Primary — cheapest capable |
| Tool / MCP-heavy tickets | **kimi-k3** | Engy | Selective |
| Hard coding escalate | **grok-4.6** | xAI | After fail ×2 only |
| Independent diff review | **Codex / Claude / frontier** | Human-triggered | Not agent self-approval |
| Human cleanup (later) | Fable / Sol / Claude | Anthropic / OpenAI | Post–Wave A polish |

## Escalate policy

1. Attempt ticket on `glm-5.2` (or `kimi-k3` if tools-primary).
2. On test failure: fix once more on same model.
3. On **second failure**: either
   - mark ticket `blocked` and stop for human, or
   - one attempt on `grok-4.6` if `XAI_API_KEY` is configured.
4. Record escalate + approximate tokens/$ in `.agent/DECISIONS.md`.
5. Never default whole Wave A to Grok.
6. Prefer external reviewer on the **diff** over the implementer marking its own work correct.

## Soft inference budgets

Cheap models can still burn money via repeated repo reads and loops. Soft caps (not hard API cutoffs — agent must self-enforce and report):

| Scope | Soft budget (guideline) | On exceed |
|-------|-------------------------|-----------|
| Single ticket | ~**$3–5** GLM-equivalent | Mark `blocked`, log, stop ticket |
| First gate (A-1→A3) | ~**$20–25** total | Human review before more funds |
| Full Wave A experiment | ~**$25–50** total | Write WAVE_A_REPORT even if incomplete |

Log rough spend in DECISIONS.md when known. Do not endlessly retry past budget.

## Price anchors (API, ~Aug 2026, per 1M tokens)

| Model | Input | Output |
|-------|-------|--------|
| GLM-5.2 (Engy) | ~$0.68 | ~$1.50 |
| Kimi K3 (Engy) | ~$1.50 | ~$7.50 |
| Grok 4.6 (xAI) | $2.00 | $6.00 (≥200K context doubles) |

## Hermes config

See `hermes_config.example.yaml` in this pack.

**Critical:** use `api_key: "${ENGY_API_KEY}"` — bare `$ENGY_API_KEY` is **not** expanded.
