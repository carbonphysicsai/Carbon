# G-PR1 — Entitlement, source permissions, quotes, and authorization

**Wave:** G commercial/private/sponsored plane
**Status:** `future_reserved`; unselected and unstarted
**Goal:** Implement exact service/source entitlement and bounded quote/authorization contracts before any paid research job can run.

**Prerequisites/owners:** G-PR0; commercial engagement, rights/privacy, identity/tenant, source/release, product, finance/legal and security owners. Human inputs: plan/price/rights/refund terms, delegation policy, source licences.

**Scope and reuse:** Extend existing CommercialEngagementSpec/RightsPolicy/DeliverableContract patterns. Bind organization/requester, source classes, scope/deliverables, quote issue/expiry/max cost, cancellation/refund, delegation and explicit acceptance authorization.

**Interfaces/failure/limits:** Interest, budget statement, subscription, agent request, or accepted terms without valid bounded authorization cannot spend. Paid access cannot reveal protected official content or alter official treatment. Unknown/expired/revoked rights fail closed.

**Acceptance tests:** source-entitlement matrix, delegated authority, expiry/revocation, quote replay/versioning, free/paid official-content equality, cancellation/refund terms, tenant isolation, and no worker dispatch without authorization.

**Definition of Done:** [ ] Exact authorized quote is independently verifiable and idempotent. [ ] Human legal/commercial/security approvals are recorded. [ ] No billing or execution is activated.

**Handoff:** G-PR2 stores campaign context; G-PR3/4 require the authorization.
