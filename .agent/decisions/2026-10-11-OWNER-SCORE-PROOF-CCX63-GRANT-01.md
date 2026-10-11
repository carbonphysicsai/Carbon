## 2026-10-11 — OWNER-SCORE-PROOF-CCX63-GRANT-01: one hourly CCX63 to solve the score proof's first 150 sealed questions

**Authority.**
- **The owner's choice.** The Test Lead relayed the owner's option B on
  2026-10-11: "run the score proof's first 150 questions on an hourly CCX63
  … He approved about €5; the grant cap is five euros."
- **Confirmed directly.** In the Test Engineer's session the owner answered
  "Yes, €5 cap" to: record a grant file with a €5 cap and write the run
  sheet for that host.
- **Custody.** OWNER-STARTUP-HOST-CUSTODY-02 (#1052) covers it. The owner
  confirmed the custody directly in the Carbon Validator's session.
- **When it takes effect.** The owner creates the server himself, and that
  act confirms the spend. This record binds the spend and takes effect when
  merged to main through PR Head.

**Decision.**

| Field | Value |
|---|---|
| Purpose | Solve the reference shards for SCORE-PROOF-01's first 150 sealed confirmation questions: the interim look of the pre-registered group-sequential design (`proof-sequential-v1.json`). The standard solves come first, then the refine round if the caps allow |
| Platform | Hetzner Cloud, one hourly-billed **CCX63** (48 dedicated vCPU, 192 GB RAM), Ubuntu 24.04, created by the owner from `startup-host.cloud-init.yaml` |
| Not this platform | The laptop, RunPod and any GPU. The AX42 keeps the sealed questions, the merge, the rebuilds and the proof |
| **Monetary cap** | **EUR 5 all-in**: server hours from creation to deletion, including setup and idle, plus the primary IP and traffic. No snapshots, volumes or backups. At the quoted EUR 1.37/h this is about 3.6 server-hours |
| **Node-hours cap** | **3.6** server-hours, created to deleted, whichever cap is reached first |
| Planning estimate | About 98 CPU-hours of standard solves (5,250 at about 67 s each, measured on EV4's pod CPUs), so about 2.1 h on 46 workers. The refine round is about 12 CPU-hours at fewer workers, for memory. Setup is about 0.5 h. About 3.2 h, or about EUR 4.4. This is an estimate: the host's own per-solve time replaces it |
| Paid fallback | None. Anything unsolved at the cap stays for the AX42. The interim look then uses the questions that resolved, at their actual information fraction |

**Delete-after rule.** The server is deleted, not powered off, when the
shards are merged, when either cap is reached, or 6 hours after creation,
whichever comes first. Before deletion, every file under the host's startup
directory is shredded (runbook §7). No snapshot, image, volume or backup is
kept. Only public counts and the per-solve wall-time p50 leave the
procedure. The final node-hours go in the private spend ledger, not in this
repository.

**Material.**
- **On the host:** the solve shards (case ids and inputs) and the pinned
  truth overlay.
- **On the AX42 only:** the sealed contract, its seed and the merged
  records. Nothing sealed reaches the PC.

**Maturity.** DEVELOPMENT evidence only. Results confer no qualification,
adoption, LIVE authority or production claim.
