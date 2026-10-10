# LAUNCHPAD-GATE-BREAKDOWN-01: local practice gate counts on both doors

**Status:** DEVELOPMENT working contract. **Authority:** owner direction,
2026-10-09; GATE-PASS-DIAGNOSIS-01 / merged PR #918. **Maturity ceiling:**
tested miner-local practice display. No exam-rule or gate-tolerance change.

## Contract and decisions

1. Derive one all-campaign aggregate from the miner's already-local public
   PRACTICE summaries. Count, for each public registered gate, trials with a
   positive failure count and the sum of failed cases. Use #918's validation,
   contradiction and coverage semantics; unverified summaries never become
   passes. Whitelist names from the Challenge's public contract. Unknown names
   are counted but never rendered, so a trial cannot inject arbitrary text.
2. The shared `campaign_view` document carries the aggregate. The browser
   Practice tab renders it and MCP `carbon_campaign_view` returns the same
   document. No new endpoint, telemetry, upload or remote write exists.
   Count across the full local experiment list, not the 50 recent rows shown
   in the table. The field never includes recipes, trial IDs, scores, cases,
   case IDs, predictions, or unrecognized gate names.
3. A missing public gate list or zero verified summaries has an explicit
   unavailable/insufficient state, not a claim that gates passed. Case counts
   are reported as counts; a trial can fail multiple gates and must be counted
   once for each such gate. Keep the one-miner local authorization boundary of
   `campaign_view` unchanged.

**Paths:** `scripts/dev/miner_launchpad` owns the present Launchpad runtime and
browser page. The owner also named `carbon/miner_launchpad`, which does not
exist on current main; this ticket records that fact rather than creating an
unrequested duplicate runtime package. PR Lead should treat the Launchpad
session as paused and review the `scripts/dev/miner_launchpad` overlap.

**Evidence:** synthetic fixtures for #918 parity, full-list counting,
unknown-name refusal, empty/incomplete coverage, browser rendering, and MCP/
HTTP document parity. One PR to PR Lead; no spend, solver runs, hidden/AX42
data, or LIVE change.

**Primary Hub map_ref:** `SYSTEM/AGENT-EXECUTION`. Hub impact is mapped
detail only; current delivery policy retires Hub maintenance and this ticket
does not alter the Hub's purpose, placement, status, dependencies, authority,
maturity, or primary links.
