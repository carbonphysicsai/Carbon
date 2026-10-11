# #929 — owner-returned main reconciliation

The owner explicitly returned #929 for conflict repair on 2026-10-09 before
CHALLENGE-WARPAGE-PACKET-01. Original PR head
`b4a8553ed0f7111cf4a876b2826518c9cf4545d1`; fetched main
`2e97aa1ba70806dc285e7eaceca1c7656f5495a3`.

Only the round-one README introduction conflicts: f13's reference-finding
notice and main's Motor peak notice occupy the same insertion point. Keep
both intact. Preserve the f13 diagnosis JSON/Markdown and toy tests verbatim.
All other main content merges mechanically; no reference package, live
runtime, safety limit or historical interpretation is changed.

Compare the main-relative path manifest and original-content hashes, rerun
focused and adjacent packet/reference/pipeline tests and quality checks, and
post a new exact-head handoff. Native/WSL results are diagnostic; applicable
exact-head CI remains required. PR Head owns the PR merge. No solver runs,
spend, hidden data or new authority.
