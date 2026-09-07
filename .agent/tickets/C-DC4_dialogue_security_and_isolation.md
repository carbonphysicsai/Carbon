# C-DC4 — Dialogue security, utility, recovery, and shared-resource isolation

**Wave:** C authenticated launch communication
**Status:** `future_reserved`; unselected and unstarted
**Goal:** Qualify the exact C-DC1/2/3 candidate for dialogue security/operations readiness without qualifying a Challenge.

**Prerequisites/owners:** C-DC3 and C-EA2/3 integration candidate; security, privacy/rights, SRE/Operations, capacity, disclosure, product utility, and incident owners. Human inputs: acceptance thresholds, provider policy, launch/deployment approval.

**Scope and reuse:** Test authentication, permissions, isolation, recovery, withdrawal/update handling, kill switches, and held-out research utility. Saturate shared DB connections/locks, object throughput/quotas, network, KMS, queues, compute, caches and telemetry; reserve official capture admission and degrade dialogue first.

**Interfaces/failure/limits:** Separate services are not assumed isolated. If capture guarantees cannot be preserved, non-essential service stops and official finalization follows its approved fail-closed rule. Dialogue failure never changes candidate treatment or scientific results.

**Acceptance tests:** cross-tenant extraction, repeated-query/cumulative disclosure, prompt injection, protected-state independence, provider abuse, restart/restore, withdrawal, duplicate notifications, load/resource starvation, capture reservation, observability leakage, kill-switch drills, groundedness/abstention/usefulness.

**Definition of Done:** [ ] Human security/operations/product owners accept the exact deployment candidate. [ ] Dialogue launch and Challenge qualification remain independent approvals. [ ] Rollback leaves official execution/capture safe.

**Handoff:** Wave D launch owner may activate the exact dialogue deployment; no scientific/LIVE authority follows automatically.
