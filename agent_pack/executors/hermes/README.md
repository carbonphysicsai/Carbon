# Optional Hermes executor

**Not part of Carbon’s protocol.** Core instructions are root `AGENTS.md` + `agent_pack/EXECUTION_PROTOCOL.md` + `.agent/tickets/`.

## Config

Hermes expands **`${VAR}`** only:

```yaml
model:
  provider: "custom"
  default: "glm-5.2"
  base_url: "https://api.engy.ai/v1"
  api_key: "${ENGY_API_KEY}"
```

See `config.example.yaml` in this folder.

## Kickoff

Read root AGENTS.md and agent_pack/EXECUTION_PROTOCOL.md, then run **A-1 only** first.
