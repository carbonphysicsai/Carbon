# CONSTRUCTION-S1-REPAIR-D1, note 01 — the "scrap receipts" decision was a relay and establishes nothing

Date: 2026-10-13
Status: ADOPTED. Additive note to `.agent/decisions/CONSTRUCTION-S1-REPAIR-D1.md`
and to `.agent/tickets/CONSTRUCTION-CONTRACT-01-S1-REVIEW-REPAIR.md`, whose
bytes are unchanged.
Authority: PR Head, under standard 3 of
`2026-10-13-PR-HEAD-MERGE-STANDARD-02.md`. Raised as finding F2 of the Carbon
Validator's review of #1309 on main.

## What those records assert

`CONSTRUCTION-S1-REPAIR-D1.md:15`:

> The owner directly resolved the delivery/Hub policy seam on 2026-10-13: scrap
> Hub maintenance and human/GPT receipts, and follow current DELIVERY_PROTOCOL
> with PR Head owning the normal guarded merge.

The ticket at line 30 quotes it as: *"Scrap hub maintenance and human/GPT
receipts.Follow how Claude was merging."*

## Why this note exists

**It reached the repository as a relay.** "The owner directly resolved" is an
assertion about a conversation held elsewhere; the decision was not confirmed in
the session that recorded it. Under standard 3, grants, spend figures, release
cuts, exposure records, security acceptances and policy of this kind require the
owner's own word **in the session that records them**, because a relay cannot be
checked and its scope cannot be tested. So **as written, these two records
establish nothing about receipts.**

**It was then used to justify a lane self-merge.** #1309 was merged by its own
author with zero reviews, citing this policy and the owner's priorities. That is
the specific harm an unverified policy claim does: it becomes load-bearing for
an action nobody authorised.

**And it is broader than what the owner actually chose.** Asked directly, he
confirmed the scope recorded in
`2026-10-13-OWNER-MERGE-APPROVAL-01.md`: an ordinary PR merges on a successful
`Merge gate` for the exact head with no approval step, **but** a PR touching
scoring, gates or safety checks, reference data or labels, or what miners can
see still requires the Carbon Validator's approval first. "Scrap human/GPT
receipts" admits no such carve-out.

**Note what D1's own sentence says.** It ends "**with PR Head owning the normal
guarded merge**" — so the record cited to justify a self-merge forbids a
self-merge in the same breath. The quotation was read for the half that removed
a constraint and not the half that kept one.

## What stands, and what does not

- **Does not stand:** any reading of D1 or its ticket as having removed reviewer
  approval generally, or as authorising a merge by anyone other than PR Head.
- **Stands:** `OWNER-MERGE-APPROVAL-01`, from his word in this session, with its
  four reserved categories and PR-Head-only merging.
- **Unaffected:** #1309's own content. The Validator reviewed it on main, did not
  revert it, and raised two front-of-queue findings; its tests give 56 passed on
  main under POSIX. This note is about the authority claim, not the repair.

## The general point

A policy claim is evidence of a conversation, not of a decision. The remedy is
cheap — ask the owner in the session that will record it — and on 2026-10-13 it
took one question and produced a **narrower and better** policy than the relay
described.
