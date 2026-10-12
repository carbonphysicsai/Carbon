# PLT-08 — MINER-STATUS-AND-SCREENING-LADDER-01

Status: selected, bounded implementation. Owner-approved Platform queue item,
2026-10-12; reviewer Carbon Validator (public disclosure path).
Starting main: aa2f5391e6a9b3c8924ddfb51740ba20043e96bb.

Authority: owner queue; OWNER-BATTERY-CHAMPIONSHIP-03; owner's 2026-10-12
clarification; Test Engineer's latest screening-grain-vN.json and reference module in #1205;
current constitution, invariants, disclosure specification and delivery policy.

KEEP the signed v1 feed, its released-only historical sections and versioning,
the attempt ledger, stored pooled screening records and public finalized chain
snapshot. Add only cumulative per-hotkey counts and leaderboard.ladder. Never
publish case/window values or championship/fresh-batch data. Filter canaries,
development constructions, other device classes, invalid records and identities.

Use screening_grain.load() to read the latest committed grain file under docs/development/evidence/
battery-screening-grain. Exactly one entry must match the deployment's Challenge,
rule name, score section, registered candidate/registry digest when applicable,
and optional rule digest. Missing, malformed, ambiguous or mismatched registration
keeps the ladder SEALED_UNTIL_GRAIN. No fallback grain is supplied by code.

The owner specifies relative grain and a geometric grid (1+g)^k. Round toward
the worse side by declared sense; use screening_grain.update() to enforce the
registered evidence minimum, own noise floor and better grid step.
Replay immutable pooled screening records deterministically per chain coldkey;
the resulting display is stable across restarts and changes only at an allowed
step. Display policy never changes official scores, nomination, final comparison,
eligibility, weights, qualification or payout.

Plan: (1) bounded ledger count projection and file/grid loader; (2) signed feed
integration and deterministic ladder; (3) compatible Python/Worker grid checks;
(4) leakage, unknown-code/overflow, matching, rounding, monotonicity and restart
regressions; (5) canonical acceptance and one PR to main, naming Carbon Validator.
Baseline canonical feed/ledger/dashboard suite: 229 passed, 2 optional skips.
Use canonical.sh with science-jax/chain/archive groups for focused regressions,
then the exact-head CI/Merge gate. No actual chain, protected data, keys, spend,
merge, approval or release. Release timing is after cutover, per the owner.

Historical map_ref SYSTEM/AGENT-EXECUTION; Hub maintenance is retired by the
current delivery policy. Maturity ceiling: implemented/tested engineering only.
#1205's data remains inactive until merged and present in the release checkout.

Prospectively preserve scored case errors and design regrets in operator-only
records. Reuse the same scoring outputs; do not rerun evaluation or rewrite old
records. Missing historical noise evidence remains sealed. Replay score insertion
order so late worker completions cannot reorder display updates.
