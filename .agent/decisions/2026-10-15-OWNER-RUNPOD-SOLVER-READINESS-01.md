## 2026-10-15 — OWNER-RUNPOD-SOLVER-READINESS-01: rent RunPod CPU pods for solver-readiness verification and the reference pilot

**Authority.** The owner, 2026-10-15, directly in a Claude Code session
(hello@carbonphysics.ai), answering the lead's proposal to rent a larger
machine for the verification phase. Verbatim: "yes. rent on runpod. be cost
effective".

**What is authorized.** Claude, as lead of the solver-readiness program
(OWNER-SOLVER-READINESS-SCIENCE-DELEGATION-01), may create and delete RunPod
**CPU** pods with the account key available to the session, for:

- verification, convergence and cost measurement of the program's families
  (f02, f06, f08, f13, f17) that the 4-vCPU development box cannot do quickly
  or at all (memory);
- running a family's frozen public reference manifest once its checks pass
  (the pilot stage of the bulk run).

**Caps (set by the lead under "be cost effective").**

| Field | Value |
|---|---|
| Campaign cap | USD 25 all-in for this phase, counted at each pod's worst case before create |
| Balance floor | the account never goes below USD 15 |
| Pods | CPU only, Secure cloud, on-demand; at most 4 live at once (raised from 2 on the owner's 2026-10-15 instruction "raise the limit to whatever you need") |
| Per pod | a deadline at create; the pod ends itself at the deadline; deleted, not stopped, when done |
| Rate | the cheapest CPU flavor whose vCPU and memory fit the job; no GPU |

A larger bulk run beyond this cap needs its own owner figure.

**Material.** Public decks, public recipe panels, solver sources from their
locks, and Carbon's code at a pushed commit only. Never hidden EVAL, STRESS,
quiz or tuning material, seeds, labels, validator state or private roots.

**Accounting.** Rates and machine ids stay in the private ledger beside the
key, never in the repository (the owner's 2026-10-02 rule in
`scripts/dev/exam_design/runpod/pod_control.py`). The public ledger records
events only.

**Maturity.** DEVELOPMENT. No qualification, LIVE, reward or network authority.
