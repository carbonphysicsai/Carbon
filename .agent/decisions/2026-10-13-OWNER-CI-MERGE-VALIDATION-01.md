# OWNER-CI-MERGE-VALIDATION-01 — testing the merge result, and what the strict flip actually costs

Date: 2026-10-13
Status: ADOPTED for the two engineering changes; the repository-configuration
flip is AUTHORISED BUT HELD on the owner's revised instruction (below).
Authority: the owner, confirmed directly in the PR Head session.
Scope: `#1246` / PLT-12 `CI-TEST-MERGE-VALIDATION-01`, `.github/workflows/ci.yml`,
`.github/rulesets/` and the branch ruleset "Carbon main merge gate" (id 24421474).
Maturity: engineering control. No scientific, economic or security acceptance
is created by this record.

## The defect

Carbon CI resolves its candidate as `.head.sha` — the PR head alone, not the
merge result. A green therefore proves nothing about head combined with main,
a rerun can never pick up a fix that landed on main, and only a base sync
tests the two together. This caused two red mains in the week to 2026-10-12
(#1179 after #1184, and #1211 after #1215).

Separately, the `Merge gate` job is guarded on `github.event.pull_request.draft
== false` (`ci.yml:648`). A push made while a PR is a draft skips the gate
entirely, `ready_for_review` does not re-trigger it, and the PR then reads
`mergeStateStatus: CLEAN` with nothing having run. On 2026-10-13 #1288, #1294
and #1297 each reached the merge manager in that state, and #1294's untested
head was carrying two reviewers' receipts that both named it.

## What the owner decided

He was first asked to authorise `strict_required_status_checks_policy: true`
and declined ("Not now"), on a stated cost of "CI runner time roughly
doubles".

**That cost was misattributed, and he challenged it.** The doubling comes from
#1246's own design — `ci.yml:138` and four further job families set
`revision: [head, merge]`, running every job twice — and not from the ruleset
flip, which only requires a PR to contain current main before merging. Asked
again on the corrected basis, he approved three changes:

1. **The ruleset flip** (`strict_required_status_checks_policy: true`) — his to
   apply, as a repository protection setting. **Subsequently held**: see below.
2. **Test the merge result only.** Drop `head` from the `revision` matrix in
   all five job families, keeping `candidate_sha` resolved and reported and
   keeping the live-head equality check (`ci.yml:58-60`). Net CI spend then
   stays near today's instead of doubling.
3. **Remove the `draft == false` guard on the `Merge gate` job.** The gate
   already uses `always()`, so aggregation is sound; the draft guard is the
   whole of the untested-but-CLEAN hole. Neither 1 nor 2 closes it.

## Why the flip is held after being authorised

A cost not identified at the time of approval was found before anything was
applied, and reported to him: **strict serialises merges.** It requires a PR to
contain the latest main *at merge time*, so every merge invalidates every other
open PR's currency, and each subsequent merge needs a fresh sync plus a full CI
run. At 16 open PRs and roughly 25-minute CI, that caps throughput near two
merges an hour, against four in forty minutes achieved by hand on 2026-10-13.

Change 2 also makes the flip largely redundant: once CI tests the merge result,
a stale base is caught at CI time, and #1246 already refuses when main moves
mid-resolution (`ci.yml:53-56`, "Main changed during resolution"). The residual
the flip would close is narrow — main moving *after* a green gate but *before*
the merge.

The recommendation put to him was therefore to adopt 2 and 3 and hold 1. **No
repository configuration has been changed.** The flip stays authorised in
principle; applying it is his action and his timing.

## Standing consequence while the flip is off

Manual stale-base discipline remains load-bearing rather than transitional:
base syncs by the merge manager, the ancestry test
(`git merge-base --is-ancestor <coupled merge> <pr head>`), and the inverse
grep for what on main depends on a module a PR is tightening. The Carbon
Validator has stated they will keep withholding receipts on heads far behind
main until those heads are synced.

## Boundaries

- A branch ruleset is a repository protection setting. The merge manager does
  not change it, with or without authorisation; the owner applies it.
- The live ruleset is **"Carbon main merge gate"**, id 24421474, whose single
  required context is `Merge gate`. It is **not** named `main.v1`, so applying
  `.github/rulesets/main.v1.json` wholesale could replace the live ruleset
  rather than flip one field. A change should edit the single parameter and
  preserve bypass actors, conditions and the required context.
- None of this relaxes standard 1 of
  `2026-10-13-PR-HEAD-MERGE-STANDARD-01.md`: a `skipped` required check still
  satisfies the ruleset, and the SHA-scoped gate check stays the merge
  requirement. Change 3, not the flip, is what addresses that.
