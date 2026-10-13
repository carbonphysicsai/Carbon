# OWNER-PLATING-REFERENCE-01, erratum 01 — D3's pod, instance class and cap

Date: 2026-10-13
Status: ADOPTED. Additive erratum to
`2026-10-13-OWNER-PLATING-REFERENCE-01.md`, whose bytes are unchanged.
Authority: the owner, **confirmed directly in the PR Head session**. He had
already approved the change in the Data Collection session; this record was not
written on that relay, because a money figure enters repository evidence only
on his word in the session that records it.

## What the record says

Line 17 prices D3 at **USD 4.3 worst case, cap USD 6** (attributed to the Test
Lead, 2026-10-13), noting at line 19 that it sits inside the standing grant and
below its USD 50 per-run cap. Lines 24-25 direct that it launch on the single
32-vCPU pod only, the four-pod fallback at USD 10 not being taken.

## What ran instead

| | recorded | actual |
| --- | --- | --- |
| instance class | cpu5m | **cpu3g** |
| size | 32 vCPU | 32 vCPU (unchanged) |
| rate | — | **USD 1.28/h** |
| worst case | USD 4.3 | **USD 22.51** |
| cap | USD 6 | **USD 25** |

Launched 18:52Z.

**Why.** RunPod had no cpu5m stock at 12 vCPU or more, and a 32-vCPU cpu5m pod
costs USD 2.08/h — so the recorded USD 1.76 ceiling was unattainable and also
wrong for that class. The single-pod direction at lines 24-25 is unchanged and
was honoured; only the instance class and therefore the price moved.

## Authority for the figure

`OWNER-POD-LAUNCH-DELEGATION-01:13` delegates runs at **at most USD 50 per
run** inside `OWNER-TEST-GRANT-01`, so USD 25 is within the delegated per-run
limit and needed no new permission to launch. Line 20 of that record
nevertheless reserves **every new grant figure** to the owner, and a cap moving
from USD 6 to USD 25 is a new figure. He approved it, first as "whatever you can
find at that size" and then, after being quoted the USD 25 cap, "Approved";
he then confirmed the figure again directly in the PR Head session for this
record.

## Open, and deliberately not resolved here

**Whether the rolling week has room for it is unverified.** The weekly
accounting in `tests/cpu/test_graphite_score_lab_research.py` asserts
`other_open + standing + research + 14.94 <= effective_weekly_cap()`, with
`other_open` a hard-coded `Decimal("184.56")` and the effective cap 260 after
the USD 40 held reserve. Its own comment puts the sum at **259.79 of 260** —
roughly 21 cents of headroom. If D3's USD 6 is inside that 184.56, raising it
to USD 25 adds USD 19 and the rolling week reaches about USD 278.79 against a
USD 260 effective cap.

This could not be settled from the repository: **184.56 appears nowhere in it
except that test.** The comment refers to "the weekly-budget record's other open
grants", and no decision record contains the number. Data Collection has been
asked to account for whether D3 is inside the term. The owner's instruction on
being told this was to confirm the USD 25 and **check the week**, and to come
back to him before anything further launches if the week is over.

## Follow-up this exposes

A weekly cap enforced by a hard-coded total whose components cannot be traced
from the repository cannot be checked by anyone who is not already holding the
answer. Either a record should name the 184.56's components, or the term should
be computed from the grant files the way the standing grants already are.
Nothing in this erratum changes a cap, a reserve or a rate.
