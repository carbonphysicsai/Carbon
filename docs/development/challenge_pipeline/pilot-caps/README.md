# Six-family all-in pilot plans — RunPod primary

PILOT-PLANS-WITHIN-CAP-01, SPECIFIED only. Owner retarget 2026-10-11 after
Hetzner refused the new account a CCX63. No solver ran or money was spent.
[plans.json](plans.json) covers BFS, MG, f13, bolted joint, warpage and f17.
Each has a non-transferable EUR10 lifecycle cap **including** its EUR1 probe.

## Hosts and the conditional bound

Primary: **RunPod Secure Cloud CPU, 32 vCPU / 64 GB, USD0.96/hour**. A 32 vCPU /
256 GB USD1.76/hour profile is selectable **before** a probe if memory requires
it. Offers are the owner's console quotes recorded in
`OWNER-SCORE-PROOF-RUNPOD-GRANT-03`; that sealed-run grant is NOT borrowed.
CCX43 remains an alternative only if account limits, quote and capacity permit.
RunPod exact availability is confirmed before allocation, not promised here.

[RunPod's billing docs](https://docs.runpod.io/accounts-billing/billing) currently
say per-second metering; use conservative **whole-minute upward rounding**,
also enclosing the owner's per-minute basis. Billing includes the whole pod,
not just the 1 or 4 solver cores. Apply an explicit **<=EUR1.25 per USD inclusive
conversion ceiling**, including compute tax, currency spread and payment fees.
This is a conditional safety ceiling, NOT a current exchange-rate estimate.
Require a current inclusive quote receipt. All non-compute lifetime charges
combined (disk, retention, setup/export/termination fees) must be <=EUR0.20 on
RunPod, <=EUR0.40 on CCX43. Never double-count or omit a tax/fee.

| Selected host | Inclusive EUR/hour ceiling | Probe allocation-to-end | Probe ceiling | Entire lifecycle including probe | Total ceiling |
|---|---:|---:|---:|---:|---:|
| RunPod 32 / 64 GB, primary | 1.20 | 40 min | 1.00 | 8 h | 9.80 |
| RunPod 32 / 256 GB | 2.20 | 21 min | 0.97 | 4 h 20 min | 9.74 |
| CCX43, availability-dependent | 0.53 | 1 h | 0.93 | 18 h | 9.94 |

Cost in cents = ceil(ceil(seconds/quantum) × quantum × rate_cents/3600) +
extras_cents. Minute quantum for RunPod; hourly for CCX43. Round outwards,
not a prorated CPU-hours estimate. A larger quote/conversion/fees requires a
prospective revision, not silently consuming more money.

## Exact sequence

1. Data Collection freezes the ordered complete physical tuples on main with
   mesh/deck/observer/material/environment pins and retained/scheduled reuse.
   Null proposal manifests are not registered. Warpage full process-history
   physics remains missing; an elastic strip is not full-task C1.
2. Choose ONE host profile and obtain its exact grant, quote, capacity,
   lifecycle enforcement and ledger. Use stock `ubuntu:24.04` by exact digest,
   pinned solver/runtime trees pushed over host-key-verified SSH, following the
   transport pattern in `OWNER-STARTUP-HOST-CUSTODY-03`. These are **public
   development/representative** tasks: no sealed-material custody exception is
   needed or conferred. No hidden bank, quiz, tuning, validator or AX42 material.
3. Do not assume Docker-in-pod. Export each solver tree plus its dependencies
   from the pinned source; compare tree hashes, executable and library versions,
   ABI and environment on both sides. The proven battery transport path is not
   proof that every solver tree is complete. Native equivalence is a release
   hold. Log SSH transport package versions too. No mutable tag execution.
4. For primary 64 GB: setup/transfer <=300 s, ONE complete probe <=1500 s,
   export/confirmed termination420 s + safety180 s: <=2400 s. For 256 GB,
   same setup/tail but probe <=360 s: <=1260 s. For CCX43 retain setup1200 /
   probe1500 / tail900: <=3600 s. Setup allowances are hard ceilings, **not
   measured transfer times**. Preflight may find a full task cannot fit; HOLD
   or retain an incomplete timed-out probe, never truncate it to claim C1.
   MG includes normalization + both solvers; f13 the full frequency curve;
   warpage full3D history. High-memory21-minute economics may be unsuitable:
   a 64GB timing cannot certify a 256GB probe. No free retries.
5. From a completed same-host/profile/core/base/tree probe receipt, size an
   ordered prefix of follow-ons. Each job's cap = 2 × measured probe wall ×
   declared complexity multiplier. These are hypotheses, NOT observed p95.
   Require each full cap plus export/termination tail to fit the remaining
   allocation-to-end deadline. Setup, idle, transfer and failures all count.
6. Export <=2GB compressed records to the existing approved store. **Terminate
   RunPod (not stop)** and confirm absence by its deadline. Delete CCX43.
   No network volumes, snapshots, backups or retained pods. RunPod says stopped
   volumes keep billing and termination deletes local data, so export first.
   [RunPod management](https://docs.runpod.io/pods/manage-pods).

**Arithmetic is not an enforced provider guarantee.** Accepted independent
allocation-to-confirmed-termination enforcement, tested expiry and actual
invoice accounting remain release holds. No launcher/provider access is in
this ticket. Killing a process, stopping a pod or a local timer is insufficient.
No cap transfer, favorable redraws, host switches using old receipts or retries.

```text
python -m carbon.challenge_pipeline.pilot_caps docs/development/challenge_pipeline/pilot-caps/plans.json
python -m carbon.challenge_pipeline.pilot_caps docs/development/challenge_pipeline/pilot-caps/plans.json --family f13 --probe PUBLIC_PROBE_RECEIPT.json
```

Always `dispatch_allowed: false`. Record actual allocation-to-termination wall,
user+system CPU across children, allocated core-seconds (all32 billed), peak
RSS, mesh/DOFs/grid, every frequency/normalization, observer outputs, failures,
pins, ledger and inclusive invoice basis. Separate controls from full buyer
task C1. One probe establishes no p95, value-check, power or reference adequacy.
