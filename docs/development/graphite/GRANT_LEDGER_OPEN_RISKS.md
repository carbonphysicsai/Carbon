# Grant ledger: open risks

**What this is.** The cross-root grant and weekly-spend ledger (`carbon/agent_campaign/grant_runs.py`) is the sole
control on testnet testing spend since the owner lifted per-run approval (OWNER-TEST-GRANT-01, #1167). It binds on
worst-case RESERVATIONS, not on settled charges: the provider never reports a pod's charge, so a created pod stays
counted at its full reservation. This page lists what the ledger cannot see or cannot bound, so none of it is read as
covered. No dollar totals here; read the current line with `python -m carbon.agent_campaign.grant_runs weekly`.

Status words: OPEN (no mitigation in code), MITIGATED (a mitigation exists but depends on an operator step),
ACCEPTED (the owner or Test Lead accepted the residual). Owners are sessions, not people.

| # | What is uncounted | How it understates | Detection or mitigation | Owner | Status |
|---|---|---|---|---|---|
| 1 | **Roots never seeded.** Runs in a controller root that has neither claimed nor been seeded (`seed --root`) are unknown to the ledger. | Silently: the weekly line looks lower than the spend. | Compare the root directories the executor and operators use with the ledger's seeded stores after every campaign (`weekly` reports the seeded run count); re-run `seed` for each root after a root is added. No code lists the roots, so completeness is an operator check. | Executor (roots), Graphite Testing Manager (tool) | MITIGATED by the reseed; completeness not independently verifiable |
| 2 | **Controllers outside the ledger.** Dry runs, prelive, tests and any controller built without `shared_runs`; pods created by tools that do not go through a campaign controller (probe pods, operator compute, data-collection and score-proof pods). | Silently: their pods never enter the window although the pot is described as shared by all testnet testing. | A live phase-3 and phase-4 run builds its controller with `shared_runs`; a prelive or dry run is meant to create no real pod. Whether the other callers' pods are in the ledger is UNVERIFIED here: each owner should confirm their path claims through `grant_runs` or is reported to the Test Lead separately. | Test Lead (scope), each session owner (their path) | OPEN |
| 3 | **A pod that is not verified terminated.** The reservation is a fixed amount for a bounded pod time; a pod that keeps running after the session ends (`pod_terminate_unverified`) can bill more. | The count stays at the reservation while real charges grow. | The pod ledger keeps the reservation booked and lists the pod as live; reconcile and pod self-termination end it; the run runtime cap bounds the session, not a stranded pod. Provider-side billing review is the only direct check. | Executor (reconcile), Test Engineer (pod self-termination) | OPEN |
| 4 | **Start-dated roll-off.** A run's whole cost is dated at its start; a run that started up to its maximum runtime before the window edge but charged inside the window drops out of the window early. | Understates for at most one maximum run time at the edge. | Accept, or date a run at its end; leave headroom near a week boundary. | Graphite Testing Manager | ACCEPTED pending the owner's view |
| 5 | **Settlements after a run closed.** A later reconcile (a pod settled, a duplicate counted) updates the pod record, but the weekly line keeps the figure settled at close, and a re-seed adds only runs that are missing. | Understates only if the later figure is higher than the one recorded at close. | Re-settle on reconcile (not built); until then re-check a reconciled run's cost by hand. | Graphite Testing Manager | OPEN |
| 6 | **A dishonest worst case.** The cap binds on `worst_case_run_cost`. If a grant's worst case is lower than what a run can really cost, spend can pass the cap without a refusal. | Silently, by design (the owner's record names this trade). | The per-run cap (a run above it is refused) bounds one run; each grant's worst case is reviewed with the grant. | Test Lead, owner | ACCEPTED by the owner's record |
| 7 | **Spend before the ledger.** The window starts with the ledger. Runs before it are known only through a controller store that is later seeded. | Understates for any run whose store is gone or never seeded. | Seed every surviving store; treat older spend as outside the window. | Executor | ACCEPTED |
| 8 | **A pod or duplicate with no recorded reservation.** The pod record counts a pod at its reservation only when a reservation was recorded (`pod_reserved`); a created pod with none, and an unknown-charge duplicate of such a pod, count zero. The duplicate fix and the pod itself share this guard. | Silently, the same class as risks 1 and 2: the ledger shows less than the pods could cost. | Suggested follow-up (a separate ticket, not built): fail closed, so a pod or duplicate with no recorded reservation is counted at the grant's per-pod worst case, or the claim or the seeding refuses. In practice a reservation is written before any launch, so this needs a corrupted or partial pod record; a refund also requires a readable record with no created pod. | Graphite Testing Manager (ledger), Test Engineer (pod record) | OPEN |

**What is NOT a risk here.** A run slot refunded after a proved pre-pod infrastructure failure keeps its reported cost
in the window; the refund releases the slot only. A duplicate pod with an unknown charge is counted at the reservation
of the pod it duplicates (never zero). A run whose usage is unknown counts at its worst case.

**The three that can silently understate** are 1, 2 and 8; each is about what never reached the ledger, or was recorded without a reservation, rather than what the
ledger counted. The weekly line's `seeded` count and a periodic comparison against the real roots and pods are the
checks.

**The per-run cap and the live grants.** The ledger refuses a run whose worst-case reservation is above the per-run cap of USD 50. The largest worst-case run across the live grants is USD 18.24, so no live grant conflicts with the cap today; a grant above 50 is refused at claim (`per_run_cap_exceeded`) and needs its own owner record.
