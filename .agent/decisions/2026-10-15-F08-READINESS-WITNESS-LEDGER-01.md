# 2026-10-15 — F08-READINESS-WITNESS-LEDGER-01: the last four f08 mesh witnesses run in a separate local readiness ledger

**Decision.** The f08 #787 triage ledger closes at 13 launches (8 primaries,
2 controls, the cold repeat and the long-flexible h 2.25/1.7 witnesses, all
COMPLETED). The remaining four convergence witnesses (nominal and
relieved-tall at h 2.25 and 1.7) run on the same frozen decks, image and
per-case limits (1 CPU, 12 GiB, 7,200 s wall timeout, no retries, big lock)
but append to `triage-f08-readiness-ledger.jsonl`, where the runner's #787
family elapsed-clock ceiling is lifted.

**Reason.** The runner applies #787's 2 node-hour f08 ceiling as wall clock
since the family's first row. On this shared 4-vCPU box (load 11–15, f08
containers receiving 20–40 % of a CPU, a queue on the shared big lock) that
clock measures other tracks' contention and lock waits, not f08 cost; it would
censor correctness runs mid-solve and waste CPU. These witnesses judge the
V1–V9 bands of F08-SCIENCE-VALUES-01 and run under the owner's 2026-10-15
solver-readiness program on free local CPU, not under the paid #787 host grant.
The coordinator directed that correctness witnesses still run.

**Alternatives rejected.** Letting the runner censor and retrying (wastes the
consumed CPU and is a retry); dropping the nominal/relieved-tall ladders (the
packet requires full rungs on nominal, and V9 needs all three geometries);
raising the cap inside the #787 ledger (mixes accounting).

**Reversibility.** The two ledgers stay separate and both are committed; the
#787 accounting is unchanged. HUMAN_INPUT left: none.

Two #787 ledger rows (thick-low-ribs and relieved-tall primaries, and later
long-flexible h 1.7) were reconstructed from the case files because the agent
tool's 30-minute background limit killed the runner process while those
containers ran to completion; each such row carries a `ledger_note`.
