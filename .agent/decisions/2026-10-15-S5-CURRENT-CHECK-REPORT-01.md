# S5-REPORT-D1 — diagnostic sidecar never authority

Ticket S5-CURRENT-CHECK-REPORT-01. Root explicitly authorized the six-path Slice A; this is a reversible engineering decision, not a reserved security decision. Notify Root/Product via the existing team route.

The authenticated provider already determines aggregate statuses, but the error path drops that basis. Preserve enforcing check() and its existing binding/code/issues, adding an optional fresh data-only report only after all subject/roster/arm validation. CLI attaches it only to the existing unavailable refusal; client validates it against the original Challenge/composition request and stores only a sanitized private exception attribute. Invalid or absent sidecar never changes the primary refusal. No new public response fields on MCP/HTTP.

Alternatives rejected: report in UnifiedContract would change immutable authority/schema; public exception echo could leak untrusted details; source imports/fixture/provider Boolean cannot establish security; replacing UNAVAILABLE or adding an authorization branch exceeds Slice A. Positive returns remain unchanged. Component evidence is not separately measured; authorization stays NOT_BOUND and admission false.

To supersede, change only the ticket/decision and three implementation files plus dedicated tests. Removing the optional report restores prior diagnostics with no migration or scientific history change. No new owner values or human decisions are needed for this diagnostic slice. Current086 target/provider authorization remains separately blocked/unbound under its reviewed proposal.
