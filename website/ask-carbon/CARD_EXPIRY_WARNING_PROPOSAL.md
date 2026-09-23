# Advance warning before a card expires — proposal for owner decision

**Status: PROPOSAL, NOT IMPLEMENTED.** Nothing in this document changes
behaviour. It asks for a decision on one small check.

## The gap

`public/release-contract.js` tests expiry in one place:

```js
if (expired(card?.expires_at, nowMs)) cardIssues.push("expired_or_invalid");
```

That handles a card which has **already** expired, and it handles it well: the
card lands in `ineligibleCards`, never reaches `reasons`, the release stays
eligible and every other card keeps answering. Failing closed on one card
instead of taking the component down is the right behaviour and this proposal
does not touch it.

What does not exist anywhere is a signal **before** that moment. There is no
check, no report and no gate output that says a card is about to stop
answering. The only way anyone learns is that the answer goes quiet.

The `current-progress` card reached three days from expiry on 2026-09-22 with
nobody aware of it. It was caught by someone reading the knowledge file for an
unrelated reason.

## Why this recurs, and worse

Current expiry distribution:

| Date | Cards |
| --- | --- |
| `2026-12-15` | 22 |
| `2026-10-16` | 5, becoming 6 once `current-progress` moves there |
| `2026-09-25` | 1 (`current-progress`, being refreshed now) |

The October group arrives the same way this one did — by going quiet — except
it is six cards at once rather than one. The December group is 22.

An expiry whose only signal is silence cannot say what it is waiting for. That
is the same shape as a watcher pinned to a revision that can no longer become
the head: from outside, "fine" and "about to stop" look identical.

## Proposed check

One addition to `tools/validate-knowledge.mjs`, which already runs in CI as
`npm run validate` and already walks every card:

- report any card whose `expires_at` is within **N days** of now;
- **warn** by default so a normal PR is not blocked by a date nobody on that
  branch chose;
- **fail** when `N` is small, so the last window before silence is a hard stop.

Suggested `N`: warn at 30 days, fail at 7. Both should be constants in the
validator, not flags, so the threshold is reviewed rather than passed.

Roughly twenty lines. No new file, no new workflow job, no new subsystem, no
scheduler, no notification transport, and no change to the release contract or
to what a visitor receives.

## What this deliberately does not do

- It does not change `release-contract.js` or any runtime behaviour.
- It does not auto-extend an expiry. Extending is a content decision and stays
  one; a check that renewed dates by itself would defeat the review the expiry
  exists to force.
- It does not notify anyone. It reports where CI already reports.

## Decision requested

1. Add the check, or leave expiry unsignalled?
2. If added: the warn and fail thresholds, and whether the December group's 22
   cards should be re-dated in one pass before the warning starts firing on all
   of them at once.

Question 2 matters more than it looks. Turning the check on with today's
distribution means 22 cards begin warning together on `2026-11-15`, which is a
useful signal exactly once and noise afterwards if the group is not staggered.
