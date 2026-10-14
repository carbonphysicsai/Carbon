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

## The weekly envelope: reservations against actuals

**Actual spend has room, and the reserved total does trace.** Data Collection
reports that the launcher enforces the live `grant_runs` ledger at claim time,
and that ledger stands at **USD 56.56 of 260 used, with D3's cpu3g USD 25
included.** So the rolling week is not over on money actually committed, and the
pod did not launch outside an enforced limit.

The separate **reserved** accounting in
`tests/cpu/test_graphite_score_lab_research.py` asserts
`other_open + standing + research + 14.94 <= effective_weekly_cap()`, with
`other_open` a hard-coded `Decimal("184.56")` and the effective cap 260 after
the USD 40 held reserve; its comment puts the sum at 259.79 of 260.

**That 184.56 is traceable, and an earlier draft of this erratum wrongly said it
was not.** `2026-10-11-OWNER-TESTNET-WEEKLY-BUDGET-01.md:56` names the four
grants as **USD 86.71 + 44.85 + 25 + 16 = 172.56**, and `CONFIRM-02` raises that
25 to 37, which gives **86.71 + 44.85 + 37 + 16 = 184.56** exactly. The earlier
claim came from grepping for the string `184.56`, which the record does not
contain because it carries the **components** rather than the sum. A failed
search is a fact about the search.

**The 278.79 hypothetical an earlier draft raised does not arise either:** D3 is
not one of those four grants, so raising its cap adds nothing to the 184.56 and
the reserved sum is unaffected.

**The real residual is narrower and is an accounting question, not a breach.**
The static sum counts only grants registered in `grant_binding`; D3, as a pod
job, is counted only in the live ledger. So the two totals are measuring
different sets rather than disagreeing about one set, and neither is wrong on
its own terms. **Whether the static weekly sum ought to cover pod jobs like D3
is the owner's accounting decision** — it determines whether the reserved figure
is a complete weekly commitment or only the registered-grant part of one. It is
recorded here as open and is not decided by this erratum.

The owner's instruction on being told the headroom was unverified was to confirm
the USD 25 and **check the week**, and to come back to him before anything
further launches if the week is over. It is not over on either accounting, so
nothing is blocked.

**Also pending with the owner, not covered by this erratum:** replacing D3 with
six cpu5m shards at up to USD 7.86 worst case over about 1.25 h, which would
reduce the USD 25 figure. If he approves that, it needs its own confirmation
and supersedes the cap recorded here rather than amending it.

## Follow-up this exposes

A weekly cap enforced by a hard-coded total whose components cannot be traced
from the repository cannot be checked by anyone who is not already holding the
answer. Either a record should name the 184.56's components, or the term should
be computed from the grant files the way the standing grants already are.
Nothing in this erratum changes a cap, a reserve or a rate.
