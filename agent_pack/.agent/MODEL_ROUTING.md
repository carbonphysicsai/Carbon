# Model routing — Carbon agent path

**Locked 2026-08-14**

## Default stack

| Role | Model | Provider | Cost posture |
|------|--------|----------|--------------|
| Bulk implement + tests | **glm-5.2** | Engy (`api.engy.ai`) | Primary — cheapest capable |
| Tool / MCP-heavy tickets | **kimi-k3** | Engy | Selective |
| Hard coding escalate | **grok-4.6** | xAI | After fail ×2 only |
| Human cleanup (later) | Fable / Sol / Claude | Anthropic / OpenAI | Post–Wave A polish |

## Escalate policy

1. Attempt ticket on `glm-5.2` (or `kimi-k3` if tools-primary).
2. On test failure: fix once more on same model.
3. On **second failure**: either
   - mark ticket `blocked` and continue other tickets, or
   - one attempt on `grok-4.6` if `XAI_API_KEY` is configured.
4. Record escalate in `.agent/DECISIONS.md`.
5. Never default whole Wave A to Grok (≈3–5× Engy GLM output cost).

## Price anchors (API, ~Aug 2026, per 1M tokens)

| Model | Input | Output |
|-------|-------|--------|
| GLM-5.2 (Engy) | ~$0.68 | ~$1.50 |
| Kimi K3 (Engy) | ~$1.50 | ~$7.50 |
| Grok 4.6 (xAI) | $2.00 | $6.00 (≥200K context doubles) |

## Hermes config

See `hermes_config.example.yaml` in this pack.
