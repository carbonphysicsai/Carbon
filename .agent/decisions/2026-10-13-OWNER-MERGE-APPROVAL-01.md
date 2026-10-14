# OWNER-MERGE-APPROVAL-01 — reviewer approval is required only where it bites

Date: 2026-10-13
Status: APPROVED by the owner, confirmed directly in the PR Head session.
Authority: the owner. This supersedes the blanket receipt requirement in
`2026-10-13-PR-HEAD-MERGE-STANDARD-02.md` §2 for ordinary PRs, prospectively.
Maturity: engineering control. It creates no scientific, security or economic
authority and changes no threshold.

## What he decided

1. **An ordinary PR merges once `Merge gate` succeeds on the exact head**, with
   **no approval step**.
2. **A PR in any of these four categories still needs the Carbon Validator's
   approval first:**
   - it changes **scoring**;
   - it changes **gates or safety checks**;
   - it changes **reference data or labels**;
   - it changes **what miners can see**.
3. **Only PR Head merges.** Lane self-merges, such as #1309, remain out.

The scope in (2) was pinned down by the Carbon Validator in conversation with
him and then put to him here in those four terms. He confirmed it as scoped.

## Why this is not a loosening where it matters

The carve-out tracks where review actually caught defects on 2026-10-13. Every
real finding of that day falls inside one of the four categories:

| finding | category |
| --- | --- |
| #1222 near-onset +1 mV scored FEASIBLE against `OWNER-PLATING-REFERENCE-01` | reference data or labels |
| #1301 missing band-straddle check, all three labels derived from an unanchored band | scoring |
| #1282 `motor_pilot` accepting a reference band of 0 | reference data or labels |
| #1294 multi-intake scope and the miner surface | what miners can see |
| #1309 F1, composition admission resolving superseded variant versions | gates or safety checks |

What newly merges without approval is work of the kind of #1302's mojibake
hygiene guard and #1287's bank-sizing documentation line. So the step is removed
where it was ceremony and kept where it has been load-bearing.

## What this does not change

- **`OWNER-POD-LAUNCH-DELEGATION-01` and every money rule stand.** Grants, spend
  figures, release cuts, exposure records, security and isolation acceptances
  and signing paths still require the owner's own word in the session that
  records them. This record is about *reviewer* approval, not his.
- **The SHA-scoped gate requirement stands unchanged** and becomes more
  load-bearing, not less: for an ordinary PR it is now the only mechanical
  check. A `skipped` or absent gate is still not a pass.
- **Nothing is retroactive.** No merge already made is re-judged, and no PR
  already held for a receipt is released without one unless it is ordinary under
  (2).
- **D1's wording is not what he decided.** The claim recorded on main in D1 and
  its ticket — "scrap hub maintenance and human/GPT receipts" — arrived as a
  **relay** and is broader than the scope above; it was also used to justify a
  lane self-merge, which (3) explicitly forbids. See
  `2026-10-13-CONSTRUCTION-S1-REPAIR-D1.note-01.md`.
