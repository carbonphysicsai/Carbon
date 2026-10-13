# LP-03 — DASHBOARD-WORKER-COUNTS-TRANSPORT-01

Working contract: carry LP-02/#1244's optional miner-status counts through the
Cloudflare dashboard Worker in one PR to main. Reviewers: Launchpad, with
Carbon Validator for disclosure. Starting base:
`ad870e7d5d30f2840247f40e81c685091bd89b9b`.
The prerequisite merged as `f664977d91cd0b6149dd7db5e3f01cb14eae2448`.
The ticket-start open-PR file scan found no overlap on the Worker reader or
dashboard Worker tests. This ticket owns no other session's branch or item.

Authority: Platform queue LP-03, CONSTITUTION.md, INVARIANTS.md, current
delivery/delegated-decision protocols, OWNER-DASHBOARD-01, DASHBOARD_PLAN.md
and the merged LP-02 positive disclosure contract. WAVE.md's older selected
research campaign is closed; the owner's local queue selects this bounded
display work. No scientific value or disclosure beyond LP-02 is selected.

## Scope and working decisions

KEEP the signed-feed verification, numeric-lexeme parser, board models,
renderer and last-good serving path. WRAP the Worker reader with the same
allow-list and validation as Python `feed._miner_status`; project an explicit
copy into board.v2, matching `board_v2._status_rows`.

Only `hotkey`, `received`, `scored` and a map of closed refusal codes to counts
survive. Unknown and unclassified code names fold into `other` before either
board is returned. Every count and summed refusal total must be an integer
between zero and 2**53 - 1. Duplicate hotkeys or malformed rows refuse the
whole signed document. Absent/null remains absent; empty remains empty.
No names, scalar scores, cases or windows are carried by this block, and a
status-only miner receives no inferred rank or score.

Keep the JavaScript refusal vocabulary independent of validator imports;
test it against the existing Python vocabulary and test every code in signed
fixtures. The existing feed schema and optional-block semantics are unchanged.
This is IMPLEMENTATION_LAG in one serving path, not a scientific migration.
The port is reversible by removing the optional projection. Python remains
the parity oracle; do not weaken its checks to accommodate JavaScript.

REPAIR the parser's plain-object copy with object spread: Object.assign's
special handling of `__proto__` discarded a legitimate unknown refusal count
and changed the signed bytes. Preserve it as an own JSON data property, then
fold its count into `other`. Signed prototype-name cases test the repair.

## Plan and acceptance

1. Run canonical baseline Worker and LP-02 tests with actual Node execution.
2. Add the Worker reader and board.v2 copy. Cover signed fixture and test-key
   production-shaped documents, all closed codes, unknown/prototype-like
   names, safe-integer boundaries, aggregate overflow, malformed/duplicate
   rows, missing/null/empty blocks and before-first-release counts.
3. Prove complete Python/Worker parity for both boards and HTTP serving;
   a malformed or tampered newer feed retains the last accepted board.
4. Run canonical dashboard regressions and all invariants, pinned quality,
   delivery hygiene before pushing, and exact-head classified CI/Merge gate.

Canonical baseline: 33 Worker/LP-02 tests passed with Node running.
Final local canonical run (no skips): 568 tests passed, including all dashboard
tests, miner screening feed/disclosure tests and all invariants. The new parity
test covers 48 signed status variants in both compact and indented JSON,
against both boards and three rules-card states (384 complete comparisons).
HTTP tests use temporary generated test keys and stub feed transport only.
Pinned Black 26.5.1/Ruff 0.16.3 and `git diff --check` passed.

Exact regression command from the isolated Linux clone:
`CARBON_UV_GROUPS="science-jax chain archive mcp" ./scripts/dev/canonical.sh bash lp03-canonical-node.sh tests/cpu/test_dashboard_*.py tests/cpu/test_miner_screening_feed.py tests/cpu/test_miner_screening_disclosure.py tests/invariants`
The untracked validation wrapper installs CI-pinned Node 24.19.0 in the
temporary container after checking its official SHA256; repository environment
and dependency pins are unchanged.

No deploy: Launchpad deploys. No real signing key, chain, AX42, paid compute,
protected material, scoring rule or grain change. Test fixtures carry only
synthetic public canaries. Maturity ceiling: implemented/tested DEVELOPMENT
/ TESTNET display software, with no new scientific or production authority.
No unresolved human input is needed for this port.

Primary historical map_ref: WAVE-A/A6 (public disclosure). Hub maintenance is
retired by the current delivery protocol; no Hub source or derived edits.
Completion requires one delivered PR, green exact-head checks/Merge gate,
a Ready for PR Head comment naming both reviewers, a <=15-line untracked
report and LP-03 marked DONE. Never merge or approve in this session.
