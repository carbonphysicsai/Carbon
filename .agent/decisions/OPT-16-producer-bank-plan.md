# OPT-16 producer V2 bank plan

**Status:** development engineering choice, 2026-10-13. **Authority:** OPT-16
queue item and VALUE-METRIC-V2 `BANK_SPEC.md`; no scientific value adopted.

The planner consumes a registered, digest-bound deterministic draw from P.
It does not create a Challenge population or launch a solver. Data Collection
owns the per-Challenge drawer and reference execution. This keeps the generic
Score Lab interface reusable while refusing any unregistered question law,
reference policy or TRAIN-separation evidence.

The draw separates buyer `context` from `physical_context`. Every question's
action-condition requirement is listed, while identical physical cases in
the same block map to one reference job. A physical case shared across blocks
is refused so the block split cannot silently reuse a reference solve.

The full plan, split and job list are producer-only. The reconciliation command
returns aggregate counts and a development-half winnability diagnostic;
confirmation records are never sent to `bank.check`. Actual near-window jobs
and costs are calculated from this bank's coarse margins, with total cost
unknown until the complete coarse panel exists. A structural-ready diagnostic
does not qualify a bank, set a V2 threshold or open its confirmation half.
