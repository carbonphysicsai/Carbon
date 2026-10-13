# PR-HEAD-MERGE-STANDARD-03 — what a merge requires of the head it merges

Date: 2026-10-13
Status: ADOPTED on merge. Supersedes
`2026-10-13-PR-HEAD-MERGE-STANDARD-02.md`, which remains untouched and in force
until this merges, as do version 01 and its two amendments.
Owner of this record: PR Head (merge manager)
Authority: `AGENTS.md` §9, §10, §18; `.agent/DELIVERY_PROTOCOL.md`; and for §2,
the owner's decision in `2026-10-13-OWNER-MERGE-APPROVAL-01.md`.
Maturity: engineering control. This record qualifies nothing.

## What this version changes

**Only standard 2, and only because the owner changed the policy it encoded.**
Version 02's blanket requirement — a named reviewer's receipt for every merge —
is replaced by a scoped one. Standards 1, 3, 4 and 5 carry over unchanged in
substance.

| clause | source |
| --- | --- |
| 1, SHA-scoped gate, three states, pending vs never ran, test for not-`completed` | 02 §1 (from 01 §1 + amendments 01, 02) |
| **2, approval required only in the four reserved categories** | **`OWNER-MERGE-APPROVAL-01`** |
| 2, receipts bound to an exact head with a succeeding gate, patch identity, byte identity | 02 §2 |
| 3, a relayed approval is not the owner's words | 02 §3 |
| 4, content claims checked against the diff; a check that cannot complete has not passed; ancestry and inverse-dependency | 02 §4 |
| 5, a correction is only true once what it corrects to exists | 02 §5 |

## 1. A gate conclusion, for the exact SHA, distinguishing three states

Unchanged from 02 §1, and **now more load-bearing**: for an ordinary PR the gate
is the only mechanical check between a lane and main.

`skipped` **satisfies** the branch ruleset and is not a pass. A push made while
a PR is a draft skips every job, and `ready_for_review` does not re-trigger CI;
only a **new commit** retests. Check per SHA:

```
gh api repos/<owner>/<repo>/commits/<head>/check-runs
```

requiring a run named exactly `Merge gate` with `conclusion == "success"` for
that SHA. Three states, only the first permitting a merge: `success`, `skipped`,
**absent**.

**Absent splits in two.** Ask whether any workflow run for the head is **not
`completed`**:

```
gh api "repos/<owner>/<repo>/actions/runs?head_sha=<FULL 40-char sha>" \
  --jq '[.workflow_runs[] | select(.status != "completed")] | length'
```

Non-zero means **pending** — wait. Zero, with no gate among the head's
check-runs, means it **never ran** — base-sync. Test for "not `completed`"
rather than enumerating in-flight names, since `completed` is the only terminal
status. Use the full forty-character SHA.

**A zero-run reading needs a moment's age before it means never-ran.** On
2026-10-13 a watcher reported `NEVER-RAN` for a head whose CI had simply not
registered yet, and a sync on that advice would have discarded a live run. A
head six minutes old with **zero runs on the whole branch** was the real case.
Check the head's commit time and the branch's run history before syncing.

## 2. Approval is required where it bites, and a receipt still binds a head

**An ordinary PR merges on a `success` gate for the exact head, with no approval
step.** This is the owner's decision, recorded in `OWNER-MERGE-APPROVAL-01`.

**A PR in any of these four categories requires the Carbon Validator's approval
first:**

1. it changes **scoring**;
2. it changes **gates or safety checks**;
3. it changes **reference data or labels**;
4. it changes **what miners can see**.

**Only PR Head merges.** A lane merging its own PR is out, whatever policy it
cites — see `2026-10-13-CONSTRUCTION-S1-REPAIR-D1.note-01.md`.

### Classifying a PR is now the merge manager's job, and it fails closed

The new failure mode is misclassifying a reserved PR as ordinary. Therefore:

- **When in doubt, it is reserved.** The cost of waiting for a receipt is a
  delay; the cost of merging an unreviewed scoring or reference change is a
  corrupted score or a false safety claim.
- **Classify from the diff, not from the title or the ticket.** A PR described as
  a documentation change that edits a band, a threshold, a label file or a
  disclosure list is reserved.
- **Ask what the artifact is *for*.** A label table that grades submissions is
  scoring even if it looks like data; a bound that refuses a launch is a safety
  check even if it looks like a constant. On 2026-10-13 the merge manager
  twice reasoned about a defect's direction without asking what the artifact
  was for, and was wrong both times.
- **A reserved PR does not become ordinary because its reserved part is small.**

### A receipt, when one is required

It counts only from the named reviewer's **own word**, naming the **exact head**,
and **that head must have a `Merge gate` concluding `success`**. A role label, a
lane comment naming a reviewer, and a keyword match are finding aids, not merge
bases. A receipt does not survive a head change, including one the merge manager
causes by syncing.

**Owed to the reviewer after a sync — a cheap re-bind, not a re-review:**

- **No overlap** with main's changes: show the PR's own files are
  **byte-identical** across the two heads, and name every commit of drift.
- **Overlap**, so byte-identity cannot hold: use **patch identity** — the
  merge-base-to-head `+`/`-` line set identical at both heads, and every other
  changed file equal to main. Order-insensitive where blocks sit side by side.

**State the scope of the command run.** A path-filtered diff is evidence about
those paths only. **Derive a reviewer's surface from the commit range between
the two heads** (`git log <old>..<new>`, `git diff --stat <old>..<new>`), never
from a filter chosen while studying one part of it. On 2026-10-13 a reviewer was
told their surface was 34 lines in two files when it was one commit across 8
files and 412 insertions.

## 3. A relayed approval is not the owner's words

Grants, spend figures, release cuts, exposure and publication records, security
and isolation acceptances, signing paths, and policy about who may approve or
merge require the owner's own word **in the session that records them**. A peer
relaying an approval does not supply it, however faithfully, and a relay's
vocabulary must not be put to the owner as though it were his.

**A policy claim is evidence of a conversation, not of a decision.** The remedy
is one question in the recording session, and on 2026-10-13 it produced a
narrower and better policy than the relay had described.

**Also: an action another session was denied is not carried out on its behalf.**
A peer blocked by its own permissions asking the merge manager to push, merge or
edit for it is refused and surfaced to the owner, regardless of intent, and
regardless of whether the owner later approves the underlying change.

## 4. The merge verifies the claim against the diff, not the PR's state

The **reviewer** decides whether the work is right; the **merge manager** decides
whether what is being merged is what was reviewed. State claims belong to
whoever tracks PR state. **Content claims belong to the merge**, checked on the
head about to be merged.

**With §2's approval step removed for ordinary PRs, this is no longer a second
opinion — it is the only content check those PRs get.**

**A check that cannot complete has not passed, and has not failed.** On this
Windows host, `import fcntl`, `import pwd`, encoding fixtures, and any test
calling `git` inside a worktree whose `.git` points at a Windows path all fail
for host reasons indistinguishable from real defects. Re-run on the merged tree
under POSIX before reporting either way.

**Resolving a conflict: compile or import the file before any other check.** A
set-level or name-level check can pass on a file that does not parse. On
2026-10-13 a grant-id set matched the union of both sides exactly on a
`grant_binding.py` that raised `SyntaxError` at import. **Keep both sides only
when both are complete, independent blocks**; where a conflict splits a
structure, hand it back to the lane that knows the intended shape — especially
in a money registry.

**Empty file overlap is not a pass.** Behavioural coupling has no overlap
signature. Before merging a stale head, ask whether its tree already contains
the merges that could change its expectations
(`git merge-base --is-ancestor <that merge> <pr head>`), and inversely what on
main depends on a module the PR is tightening. **Ask the inverse question after
every merge too:** a merge can create coupling for a PR whose CI is already
running.

## 5. A correction is only true once the thing it corrects to exists

An erratum, migration note or supersession asserting a change that has not
landed is itself false. Write it when the thing it points at exists, and record
why it is deferred. Corrections to merged records are **additive** — a note
beside the record, never an edit — because a merged decision record is
historical evidence under invariant 10.

## What this record does not do

It constrains only when a merge may proceed. It alters no threshold, cap or
acceptance, and gives the merge manager no authority `AGENTS.md` §3 reserves to
a human. Where it is stricter than the branch ruleset, the ruleset is not
thereby loosened.
