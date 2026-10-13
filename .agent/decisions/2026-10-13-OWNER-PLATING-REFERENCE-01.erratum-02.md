# OWNER-PLATING-REFERENCE-01, erratum 02 — D3 moves to nine cpu5m pods at a USD 10 ceiling

Date: 2026-10-13
Status: ADOPTED. Additive erratum superseding the instance class and cap in
`2026-10-13-OWNER-PLATING-REFERENCE-01.erratum-01.md`, whose bytes are
unchanged. The original record's bytes are unchanged too.
Authority: the owner, **confirmed directly in the PR Head session**. Erratum 01
anticipated this supersession and required its own confirmation rather than an
amendment; this is that confirmation.

## What changed again

Erratum 01 recorded D3 running on a single 32-vCPU **cpu3g** pod at USD 1.28/h,
worst case USD 22.51, **cap USD 25**, after no cpu5m stock was available at 12
vCPU or more. That run has been **stopped**.

| | erratum 01 | now |
| --- | --- | --- |
| shape | one 32-vCPU cpu3g pod | **nine cpu5m pods** |
| worst case | USD 22.51 | **USD 9.03 total** |
| expected | — | **about USD 4** |
| ceiling | USD 25 | **USD 10** |

The stopped cpu3g pod's **USD 22.51 reservation stays in the live ledger until
RunPod reports its real charge**, which is about 25 minutes at USD 1.28/h. So
the ledger will overstate D3's cost until that settles; the reservation is not
the spend.

## Authority

Data Collection reported the owner's words in their session as "Approve!" for
six cpu5m shards up to USD 8 with the cpu3g stopped, then "Yes" for up to USD
10 once 8-vCPU stock ran out. **Two details differ from that first approval**
and are the reason this went back to him rather than being recorded from the
relay: the shard count is **nine, not six**, and the operative ceiling is
therefore **USD 10, not USD 8** — and the nine-pod worst case of USD 9.03 would
exceed the USD 8 of the first approval. He confirmed **USD 10** directly in the
PR Head session.

This remains inside the USD 50 per-run cap that
`OWNER-POD-LAUNCH-DELEGATION-01:13` delegates, and it **reduces** committed
spend rather than increasing it.

## What this does not change

- The single-pod direction at lines 24-25 of the original record was about not
  taking a **more expensive** four-pod fallback for identical compute. Nine
  cheaper pods at a lower total is not that fallback. If the owner reads the
  sharded shape as inconsistent with that direction, his reading governs.
- The D3/D4 substance — the near-onset re-reference, the annotation of EV4, EV5
  and the score proofs with the optimism, and the prohibition on re-scoring — is
  untouched.
- The accounting question erratum 01 left open is untouched: the static weekly
  sum counts only grants registered in `grant_binding`, while D3 as a pod job is
  counted only in the live ledger, and **whether the static sum ought to cover
  pod jobs is the owner's decision.** Lowering D3's figure makes that question
  less pressing, not answered.

## Follow-up owed

When RunPod settles the stopped cpu3g charge, the live ledger's D3 figure
should be reconciled against this ceiling. That is a reconciliation of actuals,
not a new figure, and needs no further confirmation unless the settled total
exceeds USD 10.
