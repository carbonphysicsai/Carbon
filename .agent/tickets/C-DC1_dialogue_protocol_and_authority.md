# C-DC1 — Dialogue protocol, authority, permissions, and authentication

**Wave:** C authenticated launch communication
**Status:** `future_reserved`; unselected and unstarted
**Goal:** Define a separately versioned authenticated dialogue capability with closed authority, identity, permissions, quotas, request/outcome classes, and tool/source policy.

**Prerequisites/owners:** C0 authenticated transport/identity sequencing and the current Miner MCP protocols; security, privacy/rights, Operations, disclosure, and product owners. Human inputs: identity/tenant model, rate limits, provider policy, retention, source classes, launch owner.

**Scope and reuse:** Reuse current external identity and exact public research resources without changing `carbon_protocol_v1` or `carbon_research_v2`. Specify questions, follow-ups, comparisons, explanations, hypotheses, experiment requests, feedback, paid-interest, subscriptions, private inbox, idempotency, and closed failures.

**Interfaces/failure/limits:** Deterministic code owns authorization, quotas, tools, source eligibility, persistence and spend limits. Forbid official submission/evaluation authority, private archive/Landscape access, official predictions, arbitrary URL/SQL/code, commissioning, and spending. Model approval is not security approval.

**Acceptance tests:** protocol conformance/negative matrix, authn/authz ordering, tenant/thread binding, duplicate requests, bounded sizes/time/tools/cost, denied sources/actions, version negotiation, and no impact on official namespaces.

**Definition of Done:** [ ] Exact protocol and authority ceiling are ratified. [ ] Reserved security/rights/ops values fail closed. [ ] No runtime exists until selected implementation passes acceptance.

**Handoff:** C-DC2 owns durability; C-DC3 owns reasoning; C-DC4 owns launch acceptance.
