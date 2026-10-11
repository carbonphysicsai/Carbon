# ECR-01-D1 — a pinned campaign DAG with a separate server cap

- **Ticket:** EVIDENCE-CAMPAIGN-RUNNER-01.
- **Problem:** #975 and #1056 analyze sealed panels, while producer reference
  and TRAIN entrypoints for these revised jobs are not registered in this
  branch. #1047 caps each decision arm, not the full rented server campaign.
- **Working decision:** pin producer stage modules and their output receipts;
  keep the all-campaign euro rental cap separate from the per-decision
  `BudgetLedger`. Require seven individually named YES receipts and explicit
  operator approval for real dispatch. Synthetic fixtures use a distinct route.
- **Placement:** `carbon/development_comparison/evidence_campaign.py`, its
  fixture adapter, tests and development runbook. The later score module is a
  separately pinned optional stage.
- **Alternatives rejected:** a free-form shell manifest (unbounded execution),
  treating 48 advertised vCPUs as measured throughput, and claiming a value
  verdict from fixture or missing producer evidence.
- **Interfaces/invariants:** #975 export/evidence pack, #1047 shared budget,
  #1056 prospective competitors, VALUE-BAR-V1; no hidden disclosure, no mock
  promotion, typed infra/reference failures, no invented Challenge values.
- **Reversibility:** one isolated development module and CLI; no historical
  rescore or public protocol migration. A producer adapter may be registered
  later without changing the campaign plan schema.
- **Readiness authority resolved:** use #1039 head 98a236bf6's native report
  and exact seven labels, distinct from Graphite readiness. Recompute it on
  exact merged main immediately before public dispatch; no seven arbitrary
  YES strings can stand in for that source.
- **Data Collection handoff:** await `EVIDENCE_ENTRYPOINTS.md`, including
  module/args, plan/menu pin, image digest, output format and main status.
  `script, not registered` is a Data Collection registration gap, not permission
  for Optimizer to create a solver adapter.
- **Updated handoff, same day:** the owner checkout's updated
  `EVIDENCE_ENTRYPOINTS.md` points to registered check/solve/export commands in
  open #1077 (f02) and #1078 (battery/motor, after #1050). Their CLI does not
  yet emit the campaign stage context/receipt or assembled #975/#1056 panel.
  The runner can sheet-plan these as explicit Data Collection registration gaps;
  public dispatch remains closed until the exact bridge is registered on main.
- **Human input:** revised-job registered modules and receipts, measured
  workload/throughput, a provider quote and exact euro approval remain
  external. Real dispatch refuses until supplied.
