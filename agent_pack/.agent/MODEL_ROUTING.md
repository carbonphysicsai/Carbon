# Model routing — optional / non-authoritative

**This file is not part of Carbon’s execution protocol.**

Wave work is defined by:

- root `AGENTS.md`
- `agent_pack/EXECUTION_PROTOCOL.md`
- tickets + tests

If your **harness** needs a default model table (Hermes, local router, etc.), keep operator preferences here or under `agent_pack/executors/`. Examples only:

| Role | Example | Notes |
|------|---------|--------|
| Bulk implement | whatever cheap capable model you use | Operator choice |
| Tool-heavy | optional stronger tool model | Operator choice |
| Hard escalate | optional frontier model after repeated failure | Operator choice |
| Diff review | separate reviewer model/human | Preferred over self-approval |

Soft spend caps and API keys are operator concerns, not subnet design.

See `executors/hermes.md` if using Hermes.
