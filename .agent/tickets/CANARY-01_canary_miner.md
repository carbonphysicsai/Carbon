# CANARY-01: a Carbon-owned canary miner on the real path

**Authority:**
- OWNER-CANARY-MINER-01 (2026-10-08);
- the plan, `docs/development/CANARY_MINER_PLAN.md`.

**Status:** SPECIFIED. The plan is written; nothing is built.

**Scope:**
- a canary runner that drives the Launchpad's MCP door every cycle:
  freeze, commit, submit, then a sealed verdict and the weights check;
- stage deadlines and Ops 2 alerts.

**Depends on:**
- SIGNER-AUTOCONFIRM-01, for unattended commitments. It is blocked until
  the owner confirms it in the building session.
- A registered canary list on the validator, which is the Carbon
  Validator's work.
- The owner's decisions in plan §9.

**Boundaries:**
- Testnet 567 only.
- No hidden material, and no access to the AX42 or the distribution host.
- Canary scores never win (plan §5).
- No model spend: the canary is a scripted own-agent client.
- Deadlines are owner-set (HUMAN_INPUT).
- Engineering evidence only.
