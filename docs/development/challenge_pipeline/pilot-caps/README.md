# Six-family all-in pilot plans

PILOT-PLANS-WITHIN-CAP-01, SPECIFIED only. Replaces the earlier fractional-hour
**planning arithmetic**, not historical invoices or grants. No solver ran.
[plans.json](plans.json) covers BFS, MG, f13, bolted joint, warpage and f17.
Each family keeps its own EUR10 cap **including** its initial EUR1 probe.

## The bound, and what is still missing

Propose a **CCX43 EU** lease (16 dedicated vCPU, 64 GB, 360 GB NVMe), serial
process, allocated cores/RSS as listed. The [provider hardware page](https://www.hetzner.com/cloud/general-purpose/)
reported unavailable when checked on 2026-10-11; this is NOT a capacity promise.
[Published EU pricing](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/)
is EUR0.4423/hour excluding VAT/IPv4. With an illustrative 19% VAT it is
EUR0.526337/hour; require a real inclusive quote **no greater than EUR0.53**.
All other fees combined must be <=EUR0.40. Otherwise HOLD, not a silent bigger cap.

The [billing policy](https://docs.hetzner.com/general/billing-and-account-management/billing-at-hetzner/billing-system-hetzner/)
rounds partial hours up and bills powered-off resources until deleted. A new
CCX63 at EUR1.3678/hour ex VAT therefore **cannot** meet the EUR1 probe.
Do not multiply solver CPU-hours by a prorated host price.

Exact proposed maximum: ceil(lifetime_seconds/3600) × EUR0.53 + EUR0.40.
One-hour probe lifetime <=EUR0.93; entire 18-hour lease <=EUR9.94, probe included.
Every minute starts at provider allocation, including setup, image transfer,
idle between phases, export and provider deletion. No snapshots, extra volumes
or unlimited retention. Export <=2 GB compressed to an existing approved store
within the quote; otherwise decline. Failed attempts consume time and money.

**This is a conditional mathematical cap, not an implemented provider guarantee.**
No spend until an independent accepted lifecycle/deletion bound exists, with
tested expiry and quote. Killing the solver or shutting down the VM does not
establish it. This ticket implements no launcher, deletion agent or security
acceptance. Operator cannot call a local timer an enforced all-in cap. The
owner's separate RunPod score-proof grant and AX42 data are out of scope.

## Exact sequence

1. Data Collection freezes the listed ordered candidate tuples on main with
   complete pins, mesh, observer, condition/material/history and reuse receipts.
   Proposals with null manifests are **not** registered runs. Warpage's missing
   full-history physics stays closed; an elastic control cannot stand in for it.
2. Obtain quote, capacity, exact grant, retained ledger and enforcement receipts.
   Same host/model/cores/image for probe and follow-on; no laptop extrapolation.
3. Initial phase: setup <=1200 s, one complete listed probe <=1500 s,
   export/deletion reserve 600 s, safety 300 s: <=3600 s and EUR0.93.
   Expected probe wall times are hypotheses, not cost measurements. MG includes
   normalization and both solvers; f13 includes the entire 201-frequency curve;
   warpage includes its complete 3D history. If any does not finish, stop and
   delete, retain incomplete evidence. Do not call it low C1 or retry for free.
4. A completed probe receipt supplies measured wall/CPU/RSS and immutable tuple,
   image, host, manifest and ledger identities. Run the sizing command below
   immediately, accounting for elapsed lease time (idle never stops the clock).
5. Select an **ordered prefix** of listed follow-on jobs fitting the remaining
   lifetime. Per-job maximum = 2 × measured probe wall × declared complexity
   multiplier. These multipliers are hypotheses, NOT p95 or mesh-cost facts.
   Larger actual cost leads to a timeout and incomplete pilot, not a bigger bill.
   Refuse each job if its whole cap plus 900 s tail exceeds the lease deadline.
   No omitted favorable redraw, unapproved retries or family budget transfer.
6. Stop compute before the export/deletion tail, confirm provider deletion no
   later than 64800 s from allocation. Retain all attempts and invoice basis.
   If the independent bound is unavailable, **do not start**.

```text
python -m carbon.challenge_pipeline.pilot_caps docs/development/challenge_pipeline/pilot-caps/plans.json
python -m carbon.challenge_pipeline.pilot_caps docs/development/challenge_pipeline/pilot-caps/plans.json --family f13 --probe PUBLIC_PROBE_RECEIPT.json
```

Pure planning; output always `dispatch_allowed: false`. The closed receipt
shape is in the code/tests. It is not proof of authority/store availability.
No reference input is generated or changed by this budget tool.

## Data Collection return

Actual allocation-to-deletion wall, user+system CPU across children, allocated
core-seconds (host billing remains for all 16), peak RSS, mesh/DOFs/grid, every
frequency/normalization call and refinement; pins and complete observer outputs;
errors/conservation/order, failures/timeouts and partial curves; invoice with
tax/fees/retention. Report control cost separately from complete buyer-task C1.
One probe cannot estimate p95, T2(a), statistical power or reference adequacy.
If memory cannot fit RSS limit (especially MG) HOLD for a different capped plan;
never coarsen a truth rung or truncate physics just to complete the pilot.

Main family proposals retain their original historical scope. This common
prospective plan is the cap authority for these six **proposed pilots**, not
an execution grant or a bank-startup estimate.
