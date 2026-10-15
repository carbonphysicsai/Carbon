# PR-HEAD-MERGE-STANDARD-01, amendment 01 — "absent" is two states, not one

Date: 2026-10-13
Status: ADOPTED, prospective amendment to
`2026-10-13-PR-HEAD-MERGE-STANDARD-01.md` standard 1.
Authority: PR Head (merge manager), within the same engineering control as the
record it amends.
Form: additive. The amended record's bytes are unchanged, per standard 5 of
that record and invariant 10. Its table is not wrong; it is incomplete.

## The imprecision

Standard 1's table gives three states for the `Merge gate` on a head:
`success`, `skipped`, and **absent**, glossed as "the gate never ran for this
commit at all". That gloss conflates two materially different situations:

| observation | meaning | correct action |
| --- | --- | --- |
| absent, and the head's CI run is `in_progress` | the gate is **pending** — it `needs:` the shard jobs and has not started | wait |
| absent, and every CI run for the head is `completed` | the gate **never ran** — the draft-window case | base-sync; only a new commit retests |

Both read identically from the commit check-runs endpoint, because a job that
has not started yet produces no check-run, exactly like a job that was never
going to run.

## How to distinguish them

```
gh api "repos/<owner>/<repo>/actions/runs?head_sha=<full head sha>" \
  --jq '.workflow_runs[] | "\(.name): \(.status)/\(.conclusion // "-")"'
```

A `status` of `in_progress` or `queued` means pending. Use the **full** forty
character SHA: this endpoint silently returns nothing for an abbreviated one,
which looks the same as "no runs exist" and would argue for a sync that is not
needed.

## Why it matters

Treating pending as never-ran costs a wasted CI cycle and resets the clock on
the PR, because the sync commit supersedes a run that was about to conclude.
On 2026-10-13 four receipted heads — #1288 `a48a74ef9`, #1294 `6b604be86`,
#1303 `3889733d7` and #1297 `65a496de6` — showed the gate absent roughly forty
minutes after their pushes, with canonical shards already passing on #1288.
Read by the merged table alone that is the draft-window pattern and the
indicated action is a base sync. All four runs were in fact `in_progress`, and
syncing any of them would have thrown away a nearly complete run and added
another twenty-five minutes.

The underlying asymmetry is worth stating plainly: **a gate that has not
concluded `success` never licenses a merge, but it does not always call for a
sync.** Standard 1 is unchanged on the first half. This amendment constrains
only the remedy.
