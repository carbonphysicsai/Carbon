# Optional: Hermes executor

Only if you choose Hermes as the runner. **Not required** for Carbon Wave work.

## Config sketch

Hermes expands **`${VAR}`** only (bare `$VAR` is not expanded).

```yaml
model:
  provider: "custom"
  default: "glm-5.2"   # or whatever you prefer
  base_url: "https://api.engy.ai/v1"  # example
  api_key: "${ENGY_API_KEY}"
```

Secrets in `~/.hermes/.env` — never commit keys.

## Kickoff

1. Read root `AGENTS.md` and `agent_pack/EXECUTION_PROTOCOL.md`
2. Follow orientation + tickets exactly as any other executor
3. Do not treat model brand names as part of Carbon’s protocol

Legacy files `HERMES_KICKOFF.md` / `PASTE_INTO_HERMES.txt` (if still present) should defer to `EXECUTION_PROTOCOL.md` + `AGENTS.md`.
