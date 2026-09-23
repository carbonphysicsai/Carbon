# `current-progress` card refresh — proposal for owner decision

**Status: NOT APPROVED, NOT APPLIED.** No file under `knowledge/` is changed by
this document. Applying it is a knowledge change and is Ryan's decision.

**Deadline:** the card expires `2026-09-25T00:00:00Z`.

## What expiry actually costs

Verified in `public/release-contract.js` rather than assumed: an expired **card**
pushes `expired_or_invalid` into `ineligibleCards` and never reaches `reasons`.
So the release stays eligible, the component keeps rendering, and the other 26
cards keep answering.

What is lost is the ability to answer **"what is Carbon working on now"** —
which for a pre-launch project is plausibly the most common question a visitor
arrives with. It is a content deadline, not an outage.

## The finding that makes this a small decision

The card rests on one pinned source, `.agent/WAVE.md` at commit `90dd9670`.
That file at current `main` (`40174f92`) has **sha256
`543f8d99b72c55cc18c686e0111879b7b79aaa8f2abe851792a0915189e12097`** — which is
**byte-identical to the pinned digest**.

The source has not changed since it was pinned. `Current phase` still reads
`C-W1-D5 finite research program closed`, the three campaign slots are still
consumed, no successor is selected, and official C-W1 is still
`future_reserved`.

**So nothing in the card's answer has become false.** It is expiring on its
freshness window, not on its accuracy.

## Option A — extend the window, restate the date (recommended)

The minimum change that keeps the card answering, with no claim altered:

| Field | From | To |
|---|---|---|
| `expires_at` | `2026-09-25T00:00:00Z` | a date you choose |
| `maturity` | `DATED_STATUS_2026_09_17` | `DATED_STATUS_2026_09_22` |
| answer, first clause | "As of the pinned 17 September 2026 repository status" | "As of the pinned 22 September 2026 repository status" |

Everything else — the rest of the answer, the passage text, the source pin, the
questions, keywords, audiences and disclosure class — stays byte-identical,
because the source it paraphrases is byte-identical.

Optionally re-point the source `revision` and `url` to `40174f92` while keeping
the same `sha256`. That records that the pin was re-verified today rather than
merely still passing.

**Why this is the recommendation.** Every sentence in the card remains supported
by an unchanged source. A larger rewrite would require new source pins and a
fresh review of each new claim, on a 48-hour deadline, to say things the card
already says correctly.

## Option B — also say what has happened since

If you want the card to reflect the last five days, the honest additional
sentence is bounded engineering delivery, which changes **no** qualification
state:

> Since that status, engineering delivery has continued in bounded scope —
> client-facing problem definition, a private internal intake receiver on
> loopback with synthetic fixtures, and protocol conformance tooling. None of it
> is a scientific qualification, a production deployment or a customer
> commitment.

**This is a content change and needs more than a date review.** Each clause needs
a pinned source, and the sources for this week's work are pull requests rather
than a `WAVE.md` section, so it means new source records. I would not put that
through on a 48-hour clock unless you want it.

## What must not change either way

The qualification language is the point of the card and stays exactly as it is:

> Official scientific qualification, protected evaluation, production readiness
> and broader network authority remain unavailable. Engineering delivery is not
> evidence of a qualified production system, customer traction or measured
> network advantage.

## To apply, once approved

1. Edit `knowledge/public-knowledge.v1.json` — the `current-progress` card's
   `expires_at`, `maturity` and the answer's date clause, and only those.
2. Re-run `node --test "website/ask-carbon/tests/*.test.mjs"` (90 cases).
3. Record the approval basis on the release record the way
   `OWNER_PUBLIC_CONTENT_APPROVAL_2026_09_22_WEB_QA_07_D1` was recorded.
4. Nothing is deployed, rebuilt or activated by any of that. Ask Carbon is live
   and serving the current release; deployed state is read from `/health`.
