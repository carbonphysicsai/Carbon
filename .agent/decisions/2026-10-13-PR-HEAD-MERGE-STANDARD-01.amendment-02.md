# PR-HEAD-MERGE-STANDARD-01, amendment 02 — test for "not completed", never for a list of in-flight names

Date: 2026-10-13
Status: ADOPTED. Additive amendment correcting the guidance in
`2026-10-13-PR-HEAD-MERGE-STANDARD-01.amendment-01.md`, whose bytes are
unchanged.
Authority: PR Head, within the same engineering control.

## The error in amendment 01

Amendment 01 said to distinguish a **pending** gate from one that **never ran**
by looking for a run `status` of `in_progress` or `queued`. That enumeration is
incomplete. GitHub also reports `pending`, `waiting` and `requested`, and a
run in any of those states is in flight exactly as much as a queued one.

**It misfired within minutes of being written.** A gate watch built on that
enumeration reported `NEVER-RAN #1301 cd816b090 runs=[pending]` and advised a
base sync. The run was in flight; syncing on that advice would have discarded
it and cost another full cycle — the precise mistake amendment 01 exists to
prevent, reintroduced by the fix for it.

## The correct test

Ask whether any run is **not `completed`**, rather than whether it matches an
in-flight name:

```
gh api "repos/<owner>/<repo>/actions/runs?head_sha=<FULL 40-char sha>" \
  --jq '[.workflow_runs[] | select(.status != "completed")] | length'
```

Non-zero means **pending** — wait. Zero, with `total_count` also non-zero and
no `Merge gate` among the head's check-runs, means the gate **never ran** —
base-sync, because only a new commit retests. A `total_count` of zero means no
run was ever created for the SHA, which is also the never-ran case.

`completed` is the only terminal status in the API, so this test stays correct
as states are added. The full forty-character SHA is still required: the
endpoint silently returns nothing for an abbreviation.

## The general point, which is the reason this is written down

The underlying mistake was not a missing status name. It was **enumerating the
states expected rather than testing for the one state that is definitive.** An
allow-list of in-flight names fails open towards "needs a sync" every time the
platform adds a state; a single `!= "completed"` cannot. Where a check can be
expressed as the negation of a terminal condition, prefer that to a list of
non-terminal ones.

This is the same shape as standard 1's finding that a `skipped` required check
satisfies the ruleset: in both cases a check appeared to answer a question it
had not been asked.
