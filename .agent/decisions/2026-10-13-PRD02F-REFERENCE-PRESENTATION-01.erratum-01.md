# PRD02F-REFERENCE-PRESENTATION-01, erratum 01 — a renamed status, not a changed hold

Date: 2026-10-13
Status: ADOPTED. Additive erratum to
`2026-10-13-PRD02F-REFERENCE-PRESENTATION-01.md`, whose bytes are unchanged.
Authority: PR Head, recording a rename landed by #1297 (PRD-04).
Trigger: the condition set by standard 5 of
`2026-10-13-PR-HEAD-MERGE-STANDARD-01.md` — this erratum was deliberately
withheld until #1297 merged, because a correction asserting a rename that had
not landed would itself have been false. #1297 merged at main
`95699f888` (second parent `65a496de6`).

## What the record says

Line 35 of the amended record reads, in part:

> The battery/plating `SOLVER_NOT_ACCEPTED` hold, Undeclared physical validity
> and all qualification, rights, LIVE and scientific acceptance decisions
> remain unchanged/human-owned.

## What changed

#1297 renamed that status to **`REFERENCE_ADEQUACY_NOT_ESTABLISHED`** across
nine occurrences in seven files, two of them test assertions. The new name says
what the hold means: the reference's adequacy has not been established, rather
than a solver having been rejected.

## What this erratum does and does not do

- **The record's words stand as written.** They were accurate when written and
  are not edited. A merged decision record is historical evidence under
  invariant 10 and must not be made to say what it did not say.
- **The hold is the same hold under a new name.** Nothing about its scope,
  ownership or effect changed: battery/plating reference adequacy, Undeclared
  physical validity, and all qualification, rights, LIVE and scientific
  acceptance decisions remain unchanged and human-owned. A reader encountering
  `SOLVER_NOT_ACCEPTED` in that record should read `REFERENCE_ADEQUACY_NOT_ESTABLISHED`
  and expect no difference in meaning.
- **No rescore or reinterpretation follows.** No evidence produced under the
  old label is re-read, re-scored or re-presented because of the rename.

## Where the old label still appears

After #1297, `SOLVER_NOT_ACCEPTED` survives in exactly two places on main, both
of them decision records and neither of them code:

1. `2026-10-13-PRD02F-REFERENCE-PRESENTATION-01.md:35` — the line this erratum
   covers.
2. `2026-10-13-PR-HEAD-MERGE-STANDARD-01.md` — where the label is named as the
   subject of this very correction.

Both are intentional. Neither is a missed rename, and neither should be
"fixed" by a later sweep.
