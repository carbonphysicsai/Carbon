## 2026-10-11 — OWNER-SCORE-PROOF-RUNPOD-GRANT-03: the score proof's sealed solve on one RunPod Secure Cloud CPU pod, USD 15

**Authority.**
- **The cause.** Hetzner refused the CCX63 that OWNER-SCORE-PROOF-CCX63-GRANT-02 priced, because the owner's account is too new for that limit.
- **The owner's direction.** Relayed by the Test Lead: "Lets use runpods biggest machine".
- **The live options.** The owner read two from the RunPod console: 32 vCPU / 64 GB at USD 0.96/h, and 32 vCPU / 256 GB at USD 1.76/h.
- **Confirmed directly.** In the Test Engineer's session the owner answered: "Approve GRANT-03, RunPod score-proof run, 32 vCPU 256 GB at $1.76/h, fifteen US dollars cap."
- **Custody.** OWNER-STARTUP-HOST-CUSTODY-03 (#1087), accepted by the owner directly in the Carbon Validator session.
- **When it takes effect.** This record supersedes GRANT-02 for the interim look; GRANT-02 is not used. It binds the spend when merged to main through PR Head, after the owner confirms it in PR Head's session.

**Decision.**

| Field | Value |
|---|---|
| Purpose | Solve SCORE-PROOF-01's sealed confirmation questions for the interim look: about 267 offered, for 150 **resolved**. The AX42 draws them, keeps everything sealed, merges and retains them; the pod receives only its shard |
| Platform | One RunPod **Secure Cloud CPU** pod, 32 vCPU and 256 GB RAM, at the quoted **USD 1.76/h**. No network volume; container disk only; SSH over exposed TCP |
| Image | The pinned truth image by digest (`carbon.battery.truth.TRUTH_IMAGE`), never a substitute |
| **Monetary cap** | **USD 15 all-in**: pod time from creation to termination, setup and idle included. That is about **8.5 pod-hours** at USD 1.76/h |
| **Pod-hours cap** | **8.5**, created to terminated, whichever cap is reached first |
| Time limit | Terminate at the latest **10 hours** after creation; never stop instead |
| Planning estimate | About 174 CPU-hours of standard solves (9,345 at about 67 s), so about 5.8 h on 30 workers. Refine is about 20 CPU-hours, about 0.7 h at about 30 workers in 256 GB. Setup and the dry pass take about 0.5 h. **About 7 h in all, about USD 12.3.** The dry pass's measured per-solve time and memory replace this estimate |
| Who acts | The owner creates and terminates the pod in the console; no agent holds a RunPod key or touches the pod |

**Maturity.** DEVELOPMENT evidence only.
