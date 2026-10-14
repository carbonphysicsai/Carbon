# PR-HEAD-MERGE-STANDARD-01 — what a merge requires of the head it merges

Date: 2026-10-13
Status: ADOPTED (engineering control; no scientific, economic or security
authority is created or altered by this record)
Owner of this record: PR Head (merge manager)
Authority: `AGENTS.md` §9, §10, §18; `.agent/DELIVERY_PROTOCOL.md`
Maturity: process evidence only. This record qualifies nothing.

## Why this exists

These five standards were applied as habits during 2026-10-13, and each one
caught a real defect that every other check in the pipeline passed over. A
habit does not survive the session that holds it, and the sessions holding
these are standing down or handing off. They are written here so the next
merge manager inherits them as procedure rather than rediscovering them.

Each standard states the rule, then the case that produced it. The cases are
kept because the rule without the failure reads like fussiness.

## 1. SKIPPED is not SUCCESS, and a push made inside a draft window is never tested

A required check that concluded `skipped` **satisfies** the branch ruleset: the
only required context is `Merge gate`, and a PR can sit at
`mergeStateStatus: CLEAN` with every check `SKIPPED` and no test having run.
A push made while a PR is a draft skips every job (the workflows guard on
`draft == false`), and `ready_for_review` does **not** re-trigger CI. Only a
**new commit** retests. A base sync is the available new commit and is a real
change, not a bare retrigger of the kind `AGENTS.md` §18 forbids.

Therefore the merge check is **SHA-scoped**, never the PR aggregate:

```
gh api repos/<owner>/<repo>/commits/<head>/check-runs
```

requiring a run named exactly `Merge gate` with `conclusion == "success"` **for
that SHA**. The commit endpoint is keyed to the SHA by construction, so it
cannot return a conclusion belonging to an earlier head the way a PR-level
query can. Three states must be distinguished, and only the first permits a
merge:

| state | meaning |
| --- | --- |
| `success` | this commit was tested and passed |
| `skipped` | the job ran and concluded nothing about this commit |
| **absent** | the gate never ran for this commit at all |

**Cases.** #1275 reached `CLEAN` with every check `SKIPPED`: `convert_to_draft`
15:07:08Z, push 15:10:34Z, `ready_for_review` 15:10:40Z, nothing re-ran. #1288,
#1294 and #1297 each presented a head with the gate **absent** — 14 check-runs
and none of them the gate — and #1294's absent gate sat underneath two reviewer
receipts that both named that head.

**Note for anyone proposing to close this with branch protection.** The
`strict_required_status_checks_policy` flip (PLT-12) does **not** close it.
Strict adds base currency; it does not make a skipped conclusion unacceptable.
Tested on #1275, which was `CLEAN` with the required context `SKIPPED`.

## 2. A thorough read by whoever reached the PR first is not a named receipt

A receipt counts only from the named reviewer's **own word**, and it must name
the **exact head** it reviewed. A role label, a lane comment naming a reviewer,
and a keyword match are all finding aids; none is a merge basis.

**Naming a head is necessary and not sufficient.** The head a receipt names
must itself have a `Merge gate` run concluding `success` for that SHA
(standard 1). A receipt bound to an untested tree is a review of something
nobody has run, and nothing in the PR's status distinguishes it from a receipt
bound to a tested one. On #1294 **two** careful reviewers were each bound to
the exact head whose gate was **absent**; both had done real reviews, and the
defect was invisible from the PR. So the merge requires the conjunction: a
named reviewer's own word, an exact head, and a `success` gate on that head. A reviewer who
lists several PRs as approved speaks for themselves and not for a second
reviewer the PR names. A receipt does not survive a head change — including a
head change the merge manager causes by syncing — because a receipt not bound
to a tree is a receipt for no particular tree.

**Cases, in both directions.** #1252 was merged on one receipt when its body
named two (Carbon Validator **and** Data Collection). #1286 went the other way:
a grep for `approve|receipt` matched the *lane's* own "Reviewer route: Carbon
Validator" comment, and the reviewer was told the PR was "green on your
receipt" when they had never looked at it. #1298 arrived with "Codex-side
read-only Test Lead review" — a role, not a binding. #1294's two reviewers each
restated their receipt against an exact SHA, then re-bound it after a base sync
moved the head; one of them also corrected a stale head the merge manager had
quoted from the API before three commits landed.

**Corollary the merge manager owes the reviewers.** When a sync invalidates a
receipt, prove the re-bind is cheap rather than demanding a re-review: show the
PR's own files are byte-identical across the two heads
(`git diff --stat <old head> <new head> -- <the PR's files>` empty) and name
every commit of drift. On #1294 the drift was four commits, all of them #1295.

## 3. A relayed approval is not the owner's words

Grants, spend figures, release cuts, exposure and publication records, security
and isolation acceptances, and signing paths require the owner's own word in
the session that records them. A peer relaying an approval, however faithfully,
does not supply it, and a relay's vocabulary must not be put to the owner as
though it were his.

**Cases.** `producer-code-r8.6` was first authorised by a relayed "Approve both
1 and 2"; the cut was refused, the question was put to the owner directly, and
the tag was cut only on his own confirmation. An owner record was written with
the word **CONTAINED**, which appears in neither the probe schema nor the gate;
it came from the relay, while the owner's actual text was "passes all 6 sandbox
escape tests". The confirming question had inherited the relay's word and put it
back to him. Records written on direct confirmation now say so explicitly, and
attribute relayed wording to the relay.

## 4. A merge decision verifies the claim against the diff; it does not verify PR state

Two different acts: the **reviewer** decides whether the work is right; the
**merge manager** decides whether what is being merged is what was reviewed.
The second is narrower and is not duplicated by the first. State claims — what
the head is, whether a PR is merged, what colour CI is — belong to whoever
tracks PR state. **Content claims belong to the merge**, and are checked on the
head about to be merged, never on the author's base.

**The clearest case: a check that cannot complete has not passed.** #1295
changed the miner surface, adding `carbon/reconstruction/development_composition.py`.
The two invariants that most needed to hold —
`test_development_variants_unreachable` and
`test_score_variants_unreachable` — **cannot execute at all** on a Windows
host: collection aborts at `carbon/battery/intake.py:94`, `import fcntl`. A
host failure and a real unreachability break present identically in the exit
code, and "failed to run" must never be read as either a pass or a finding.
Re-run on the **trial-merged tree** under POSIX, they passed 10 cases, which
established that the author's `reach()`-is-empty claim held against main
rather than only against their base. That is the merge's own evidence and
duplicates no reviewer's work.

**Further cases.** #1275 arrived green with three of its four required items
missing. #1297's "one wording fix" was **ten references to one status**: nine
occurrences of the new label across seven files, two of them test assertions,
plus a tenth in an already-merged decision record that must not be edited at
all (standard 5). #1277's removal of a reserved amount was safe only because no
such grant file exists anywhere — had one existed it would have un-reserved
money for a live grant. #1288 cited a cost figure that had stopped matching its
own case count. #1300's real failure was two stale budget expectations, not the
pair the lane pointed at. #1296 passed its gate with exclusions dropping
silently out of a roster via `continue`, which the gate never asked about.

An empty file overlap is likewise not a pass: behavioural coupling has no
overlap signature, which is how #1211 broke #1215 on main. The sharper question
before merging a stale head is whether the PR's tree already contains the
merges that could change its expectations
(`git merge-base --is-ancestor <that merge> <pr head>`), and, inversely, what
already on main depends on the module the PR is tightening.

## 5. A correction is only true once the thing it corrects to exists

An erratum, migration note or supersession that asserts a change which has not
landed is itself false, however certain the change is. Write it when the thing
it points at exists, and record **why** it is being deferred so the next
session finds a stated reason rather than a gap it might fill wrongly.

**Case.** The `SOLVER_NOT_ACCEPTED` reference in
`2026-10-13-PRD02F-REFERENCE-PRESENTATION-01.md:35` needs an erratum because
#1297 renames that status to `REFERENCE_ADEQUACY_NOT_ESTABLISHED`. On
2026-10-13 that erratum was **not** written: #1297 had not merged, so the
erratum would have asserted a rename that did not yet exist anywhere. It is
additive when written — a note beside the record, never an edit to it, since a
merged decision record is historical evidence under invariant 10 and must not
be made to say what it did not say. The record's own words stand; the hold it
describes is the same hold under a new name.

## What this record does not do

It creates no scientific, security, economic or commercial authority, changes
no threshold, and qualifies nothing. It constrains only when a merge may
proceed. Where it is stricter than the branch ruleset, the ruleset is not
thereby loosened: a mechanical gate that accepts a skipped check is the reason
standard 1 exists.

## Follow-up

- The PRD02F erratum described in standard 5 is owed **on #1297's merge** and
  not before. At the synced head `65a496de6` the old label survives in exactly
  one place in the entire repository: that merged record's line 35. The PR's
  own files carry the new label in nine places across seven files, two of them
  test assertions.
- PLT-12 (`CI-TEST-MERGE-RESULT-01`) remains the real fix for standard 1's root
  cause: CI checks out `.head.sha` rather than the merge result, so a rerun can
  never pick up a fix that landed on main.
