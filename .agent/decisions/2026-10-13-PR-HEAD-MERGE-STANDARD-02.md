# PR-HEAD-MERGE-STANDARD-02 — what a merge requires of the head it merges

Date: 2026-10-13
Status: ADOPTED on merge. Supersedes
`2026-10-13-PR-HEAD-MERGE-STANDARD-01.md` and its amendments 01 and 02, which
remain untouched and in force until this record merges.
Owner of this record: PR Head (merge manager)
Authority: `AGENTS.md` §9, §10, §18; `.agent/DELIVERY_PROTOCOL.md`
Maturity: engineering control. This record qualifies nothing and creates no
scientific, security, economic or commercial authority.

## What this version is

A **consolidation** of version 01 and its two amendments, plus **exactly one
new rule** (standard 2's patch-identity clause, marked **NEW** where it
appears). Nothing else changes in substance. Version 01 accumulated two
amendments within hours of being written, and a chained procedure nobody can
read is not a procedure.

**Scope.** This applies **forward only, from its merge.** It re-judges no past
merge, and no merge made under 01 is reopened or criticised by it. Version 01
and both amendments stay in the repository as the record of how each rule was
learned; where this version and they differ in wording, the difference is
editorial unless marked NEW.

**Owner decisions are cited here, never restated.**
`2026-10-13-OWNER-CI-MERGE-VALIDATION-01.md` remains the owner's record of what
he adopted and what he declined — including the declined
`strict_required_status_checks_policy` flip. Nothing in this record changes,
softens or re-authorises any of it.

## Source table

Every clause below traces to 01 or an amendment. Nothing is new except the one
row marked NEW.

| clause here | source |
| --- | --- |
| 1, the SHA-scoped gate and the three gate states | 01 §1 |
| 1, absent is two states: pending vs never ran | amendment 01 |
| 1, test for a status that is not `completed` | amendment 02 |
| 1, strict required checks do not close the skipped hole | 01 §1 note |
| 2, a receipt is the named reviewer's own word, bound to an exact head | 01 §2 |
| 2, and that head must have a `success` gate (the conjunction) | 01 §2, added there on the #1294 finding |
| 2, cheap re-bind by byte-identity when the overlap is empty | 01 §2 corollary |
| 2, **patch identity when files overlap** | **NEW** |
| 3, a relayed approval is not the owner's words | 01 §3 |
| 4, content claims checked against the diff on the head being merged | 01 §4 |
| 4, a check that cannot complete has not passed, in both directions | 01 §4 corollary |
| 4, empty file overlap is not a pass; ancestry and inverse-dependency | 01 §4 |
| 5, a correction is only true once what it corrects to exists | 01 §5 |

## 1. A gate conclusion, for the exact SHA, distinguishing three states

A required check that concludes `skipped` **satisfies** the branch ruleset: the
only required context is `Merge gate`, and a PR can sit at
`mergeStateStatus: CLEAN` with every check `SKIPPED` and nothing having run. A
push made while a PR is a draft skips every job (the workflows guard on
`draft == false`), and `ready_for_review` does **not** re-trigger CI. Only a
**new commit** retests. A base sync is the available new commit and is a real
change, not a bare retrigger of the kind `AGENTS.md` §18 forbids.

The merge check is therefore **SHA-scoped**, never the PR aggregate:

```
gh api repos/<owner>/<repo>/commits/<head>/check-runs
```

requiring a run named exactly `Merge gate` with `conclusion == "success"` for
that SHA. The commit endpoint is keyed to the SHA by construction, so it cannot
return a conclusion belonging to an earlier head.

| state | meaning | action |
| --- | --- | --- |
| `success` | this commit was tested and passed | merge, if the other standards hold |
| `skipped` | the job ran and concluded nothing about this commit | do not merge |
| **absent** | no check-run exists — **two different situations** | see below |

**Absent splits, and conflating them costs a CI cycle.** Ask whether any
workflow run for the head is **not `completed`**:

```
gh api "repos/<owner>/<repo>/actions/runs?head_sha=<FULL 40-char sha>" \
  --jq '[.workflow_runs[] | select(.status != "completed")] | length'
```

Non-zero means the gate is **pending** — wait. Zero, with `total_count`
non-zero and no `Merge gate` among the head's check-runs, means the gate
**never ran** — base-sync, because only a new commit retests. `total_count`
zero is also the never-ran case.

Test for "not `completed`" rather than enumerating in-flight names.
`completed` is the API's only terminal status, so the test stays correct as
states are added; an allow-list of `in_progress` and `queued` omits `pending`,
`waiting` and `requested`, and fails **open towards an unnecessary sync**. The
full forty-character SHA is required — the endpoint silently returns nothing
for an abbreviation, which reads identically to "no runs exist".

**Branch protection does not close the skipped hole.** The
`strict_required_status_checks_policy` flip adds base currency; it does not
make a skipped conclusion unacceptable. The owner declined that flip for
separate reasons recorded in `OWNER-CI-MERGE-VALIDATION-01`; this clause would
hold either way.

## 2. A receipt: the named reviewer's own word, an exact head, and a gate on it

A receipt counts only from the named reviewer's **own word**, and it must name
the **exact head** reviewed. A role label, a lane comment naming a reviewer,
and a keyword match are finding aids; none is a merge basis. A reviewer who
lists several PRs as approved speaks for themselves, not for a second reviewer
the PR names. A receipt does not survive a head change, **including one the
merge manager causes by syncing**.

**Naming a head is necessary and not sufficient.** That head must itself have a
`Merge gate` concluding `success` for its SHA. A receipt bound to an untested
tree is a review of something nobody has run, and nothing in the PR's status
distinguishes it from a receipt bound to a tested one. The merge requires all
three together: the reviewer's own word, an exact head, and a `success` gate on
that head.

**The merge manager owes a cheap re-bind, not a re-review, when a sync
invalidates a receipt** — and which proof applies depends on overlap:

- **No overlap between the PR's files and main's changes:** show the PR's own
  files are **byte-identical** across the two heads
  (`git diff --stat <old head> <new head> -- <the PR's files>` empty), and name
  every commit of drift.
- **Overlap, so byte-identity cannot hold: use patch identity.** **(NEW)** The
  PR's merge-base-to-head `+`/`-` line set is identical at both heads, and
  every other changed file equals main. When main has touched the same files,
  the PR's files *must* differ after the sync — they now carry main's content
  too — so byte-identity is the wrong question and its failure is not a
  finding.

**State the scope of the command run.** A path-filtered diff is evidence about
those paths only. Describing one as the whole remaining delta is a false claim
even when every quoted line is true. Patch identity is preferred partly because
it is scope-free by construction.

## 3. A relayed approval is not the owner's words

Grants, spend figures, release cuts, exposure and publication records, security
and isolation acceptances, and signing paths require the owner's own word **in
the session that records them**. A peer relaying an approval, however
faithfully, does not supply it, and a relay's vocabulary must not be put to the
owner as though it were his. Where a record rests on a direct confirmation, it
says so; where wording came from a relay, it attributes it to the relay.

This does not impugn any relaying session, and it does not block work the owner
has already authorised elsewhere — it governs only what enters repository
evidence as his decision.

## 4. The merge verifies the claim against the diff, not the PR's state

Two different acts: the **reviewer** decides whether the work is right; the
**merge manager** decides whether what is being merged is what was reviewed.
The second is narrower and is not duplicated by the first. State claims — what
the head is, whether a PR is merged, what colour CI is — belong to whoever
tracks PR state. **Content claims belong to the merge**, checked on the head
about to be merged, never on the author's base.

**A check that cannot complete has not passed — and has not failed.** On a
Windows host, `import fcntl` and `import pwd` abort collection of whole suites,
and encoding fixtures fail for host reasons. A host failure and a real defect
are indistinguishable from the exit code. Re-run on the merged tree under a
POSIX environment before reporting either a pass or a finding.

**Empty file overlap is not a pass.** Behavioural coupling has no overlap
signature. Before merging a stale head, ask whether its tree already contains
the merges that could change its expectations
(`git merge-base --is-ancestor <that merge> <pr head>`), and, inversely, what
already on main depends on a module the PR is tightening.

**Ask the inverse question after every merge, too.** A merge can create
coupling for a PR whose CI is already running: the two were never tested
together, and the still-green PR looks unaffected. After merging, check the
in-flight PRs for ones touching the same files.

## 5. A correction is only true once the thing it corrects to exists

An erratum, migration note or supersession asserting a change that has not
landed is itself false, however certain the change is. Write it when the thing
it points at exists, and record **why** it is deferred so the next session
finds a stated reason rather than a gap it might fill wrongly. Corrections to
merged records are **additive** — a note beside the record, never an edit to
it — because a merged decision record is historical evidence under invariant 10
and must not be made to say what it did not say.

## What this record does not do

It constrains only when a merge may proceed. Where it is stricter than the
branch ruleset, the ruleset is not thereby loosened: a mechanical gate that
accepts a skipped check is the reason standard 1 exists. It alters no
threshold, no cap and no acceptance, and it gives the merge manager no
authority that `AGENTS.md` §3 reserves to a human.
